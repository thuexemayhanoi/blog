#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test reattest-legacy-qa.py trên bản sao hermetic của repo (FxTestCase).

Kịch bản "evidence cũ lệch hash vì migrate domain" được DỰNG LẠI trong fixture
(không đụng production): lấy một bài PUBLISHED hiện có, dựng bản baseline
"chưa migrate" (thêm tiền tố /blog/), ghi evidence trỏ hash của baseline —
đúng hình dạng 1.069 ca thật. Lịch sử git được tiêm qua dict `history`.

Phủ: chỉ ca domain-only + chấm lại độc lập PASS mới ghi; mọi ca khác bị TỪ CHỐI
(không có cờ ép); manifest giả/lỗi thời không ép được; batch nguyên tử; sao lưu
+ provenance; chạy lặp no-op; rollback byte-exact và không đè thay đổi của người
khác; không đụng _posts/matrix/checkpoint/lease; mốc lịch sử được giữ nguyên.
"""
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / 'reattest-legacy-qa.py'
sys.path.insert(0, str(HERE))
from test_qa_modes import FxTestCase, matrix_rows, save_matrix  # noqa: E402

spec = importlib.util.spec_from_file_location('reattest_under_test', SCRIPT)
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
A = R.A


def sha(b):
    return hashlib.sha256(b).hexdigest()


def tree_hashes(root, rels):
    out = {}
    for rel in rels:
        p = pathlib.Path(root) / rel
        if p.is_dir():
            for f in sorted(p.rglob('*')):
                if f.is_file():
                    out[str(f.relative_to(root))] = sha(f.read_bytes())
        elif p.is_file():
            out[rel] = sha(p.read_bytes())
    return out


GUARD = ('_posts', 'data/content-matrix.csv', 'data/state', '_drafts')


class ReattestBase(FxTestCase):
    def setUp(self):
        super().setUp()
        self._cwd = os.getcwd()
        self.addCleanup(os.chdir, self._cwd)
        self.root = pathlib.Path(self.fx)
        # Backups committed by real batches live in the repo this fixture copies: the tests
        # assert on the batches THEY create, so start from an empty backup directory.
        shutil.rmtree(self.root / R.BACKUP_DIR, ignore_errors=True)
        self.history = {}
        self.stale_ids = []

    # ---- dựng ca "domain-only" trong fixture ---------------------------------
    @staticmethod
    def evidence_bytes(obj, fmt='indent2'):
        if fmt == 'indent1_nl':
            return (json.dumps(obj, ensure_ascii=False, indent=1) + '\n').encode('utf-8')
        if fmt == 'crlf':
            return json.dumps(obj, ensure_ascii=False, indent=2).replace('\n', '\r\n').encode('utf-8')
        return json.dumps(obj, ensure_ascii=False, indent=2).encode('utf-8')

    def make_stale(self, aid, *, edit_after_migration=None, bad_amount=False,
                   unbound=False, annotations=None, old_scores=None, fmt='indent2',
                   drop_scored_at=False):
        """Biến evidence của bài PUBLISHED `aid` thành evidence CŨ (hash của
        baseline chưa migrate) và nạp baseline vào self.history."""
        rows = matrix_rows(self.fx)
        row = next(r for r in rows if r['id'] == aid)
        post = self.root / row['output_path']
        current = post.read_bytes()
        if bad_amount:
            current += '\nGiá thuê được cam kết là 9.876.543đ.\n'.encode()
            post.write_bytes(current)
        if edit_after_migration:
            current_for_baseline = current
            current = current + edit_after_migration
            post.write_bytes(current)
        else:
            current_for_baseline = current
        old = current_for_baseline.replace(b'](/', b'](/blog/')
        if A.migrated(old) != current_for_baseline:
            self.skipTest('bai %s khong dung duoc de dung baseline tong hop' % aid)
        old_row = dict(row)
        for key in ('expected_url', 'canonical_url'):
            old_row[key] = '/blog' + row[key]
        ev_path = self.root / 'data/qa' / (aid + '.json')
        ev = json.loads(ev_path.read_text(encoding='utf-8'))
        old_ev = dict(ev, content_sha256=sha(old),
                      matrix_row_sha256=A.fingerprint(old_row))
        if unbound:
            old_ev['content_sha256'] = '0' * 64
        if annotations:                     # chu thich lich su cua evidence that (hash_sync_note...)
            old_ev.update(annotations)
        if old_scores:                      # diem CU khac diem cham lai: bat tai su dung diem cu
            old_ev.update(old_scores)
        if drop_scored_at:
            old_ev.pop('scored_at', None)
        ev_path.write_bytes(self.evidence_bytes(old_ev, fmt))
        self.history[row['output_path']] = old
        self.history['data/qa/%s.json' % aid] = self.evidence_bytes(old_ev, fmt)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(row.keys()), lineterminator='\n')
        w.writeheader()
        prev = self.history.get('data/content-matrix.csv')
        old_rows = list(csv.DictReader(io.StringIO(prev.decode()))) if prev else []
        for r in old_rows + [old_row]:
            w.writerow(r)
        self.history['data/content-matrix.csv'] = buf.getvalue().encode()
        self.stale_ids.append(aid)
        return old_ev

    def good_ids(self, n):
        """n bài PUBLISHED mà chấm lại độc lập PASS (không phụ thuộc dữ liệu cố định)."""
        ctx = R.make_ctx(self.root, 'fixture-baseline', history={
            'data/content-matrix.csv': b''}, approval_ref='x')
        out = []
        for row in ctx.rows:
            if row['status'] != 'PUBLISHED':
                continue
            cur = (self.root / row['output_path']).read_bytes()
            ev = json.loads((self.root / 'data/qa' / (row['id'] + '.json')).read_text(encoding='utf-8'))
            if (ev.get('content_sha256') != sha(cur)
                    or ev.get('matrix_row_sha256') != A.fingerprint(row)):
                continue     # evidence da lech hash THAT: khong phai diem xuat phat sach
            fresh = A.rescore_published(ctx.op, row, ctx.rows, ctx.biz, ctx.tax)
            # con du cho vai tu them (test_13 them mot cau): khong sat tran word_target
            roomy = fresh.get('word_count', 0) <= fresh.get('word_target', 0) * 1.08
            if (fresh.get('result') == 'PASS' and roomy
                    and A.migrated(cur.replace(b'](/', b'](/blog/')) == cur):
                out.append(row['id'])
            if len(out) == n:
                return out
        self.skipTest('fixture khong du bai PASS de dung kich ban')

    def ctx(self, approval='owner authorization (test)', batch=None):
        return R.make_ctx(self.root, 'fixture-baseline', approval, batch,
                          history=self.history)

    def plan(self):
        return R.make_plan(self.ctx())

    def evidence(self, aid):
        return json.loads((self.root / 'data/qa' / (aid + '.json')).read_text(encoding='utf-8'))


class TestReattest(ReattestBase):

    def test_01_domain_only_and_fresh_pass_is_eligible_everything_else_is_not(self):
        a, b, c, d = self.good_ids(4)
        self.make_stale(a)
        self.make_stale(b, edit_after_migration=b'\nDong them sau migration.\n')
        self.make_stale(c, bad_amount=True)
        self.make_stale(d, unbound=True)
        m = self.plan()
        self.assertEqual(m['eligible'], [a])
        self.assertEqual(m['entries'][b]['classification'], 'CONTENT_OR_MATRIX_CHANGE')
        self.assertEqual(m['entries'][b]['decision'], 'MANUAL_REVIEW_REQUIRED')
        self.assertEqual(m['entries'][c]['decision'], 'FRESH_QA_FAILED')
        self.assertIn('business_amounts', m['entries'][c]['failed_checks'])
        self.assertEqual(m['entries'][d]['classification'], 'BASELINE_EVIDENCE_UNBOUND')
        self.assertEqual(m['entries'][d]['decision'], 'MANUAL_REVIEW_REQUIRED')

    def test_02_apply_writes_independent_evidence_with_provenance_and_backup(self):
        a, = self.good_ids(1)
        old_ev = self.make_stale(a)
        m = self.plan()
        guard = tree_hashes(self.root, GUARD)
        ctx = self.ctx(batch='reattest-test-1')
        rep = R.apply_batch(ctx, m, [a])
        self.assertEqual(rep['written'], [a])
        ev = self.evidence(a)
        row = next(r for r in matrix_rows(self.fx) if r['id'] == a)
        self.assertEqual(ev['content_sha256'], sha((self.root / row['output_path']).read_bytes()))
        self.assertEqual(ev['matrix_row_sha256'], A.fingerprint(row))
        self.assertEqual(ev['result'], 'PASS')
        self.assertGreaterEqual(ev['quality'], 75)
        self.assertGreaterEqual(ev['seo'], 70)
        self.assertEqual(ev['business_fact'], 'PASS')
        prov = ev['reattestation']
        self.assertEqual(prov['previous_evidence_sha256'], m['entries'][a]['old_evidence_sha256'])
        self.assertEqual(prov['previous_content_sha256'], old_ev['content_sha256'])
        self.assertEqual(prov['previous_matrix_row_sha256'], old_ev['matrix_row_sha256'])
        self.assertEqual(prov['approval_ref'], 'owner authorization (test)')
        self.assertEqual(prov['kind'], 'domain-migration-v3')
        # mốc lịch sử giữ nguyên (watchdog đọc như tín hiệu hoạt động)
        self.assertEqual(ev.get('scored_at'), old_ev.get('scored_at'))
        self.assertEqual(ev.get('published_at'), old_ev.get('published_at'))
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        self.assertEqual(backup['entries'][a]['old_evidence_text'],
                         json.dumps(old_ev, ensure_ascii=False, indent=2))
        self.assertEqual(R.verify_backup(ctx, backup), [])
        # KHÔNG đụng bài / matrix / state / draft
        self.assertEqual(tree_hashes(self.root, GUARD), guard)

    def test_02b_historical_annotations_are_carried_into_the_reattestation_block(self):
        """Real legacy evidence carries notes the scorer never produces (post_publish_repair,
        hash_sync_note, rescore_note, restamped_note). A fresh evidence object would silently
        drop them; the re-attestation copies them verbatim so the live file still says the old
        evidence had been re-stamped / repaired after publication."""
        a, b = self.good_ids(2)
        notes = {'post_publish_repair': {'type': 'missing-blog-prefix', 'repaired_links': 5,
                                         'note': 'test', 'previous_content_sha256': '0' * 64},
                 'hash_sync_note': 'cap nhat sau repair-frontmatter (test)'}
        self.make_stale(a, annotations=notes)
        self.make_stale(b)
        ctx = self.ctx(batch='reattest-test-notes')
        rep = R.apply_batch(ctx, self.plan(), [a, b])
        ev = self.evidence(a)
        self.assertEqual(ev['reattestation']['previous_evidence_annotations'], notes)
        for k in notes:       # never promoted to top level as if the fresh scorer had produced them
            self.assertNotIn(k, ev)
        self.assertNotIn('previous_evidence_annotations', self.evidence(b)['reattestation'])
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        self.assertEqual(R.verify_backup(ctx, backup), [])

    def test_02c_a_builder_that_drops_the_annotations_is_caught_and_rolled_back(self):
        a, = self.good_ids(1)
        self.make_stale(a, annotations={'hash_sync_note': 'cap nhat sau repair (test)'})
        m = self.plan()
        before = self.evidence(a)
        real = R.build_new_evidence

        def lossy(ctx, e, fresh, old_ev):
            new = real(ctx, e, fresh, old_ev)
            new['reattestation'].pop('previous_evidence_annotations', None)
            return new
        R.build_new_evidence = lossy
        self.addCleanup(setattr, R, 'build_new_evidence', real)
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(batch='reattest-test-lossy'), m, [a])
        self.assertEqual(cm.exception.code, 'POST_VERIFY_FAILED')
        self.assertEqual(self.evidence(a), before)
        self.assertFalse((self.root / R.BACKUP_DIR / 'reattest-test-lossy.json').exists())

    def test_03_no_approval_means_no_write(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        m = self.plan()
        before = self.evidence(a)
        for approval in ('', '   '):
            with self.assertRaises(R.Refuse) as cm:
                R.apply_batch(self.ctx(approval=approval), m, [a])
            self.assertEqual(cm.exception.code, 'NO_APPROVAL')
        self.assertEqual(self.evidence(a), before)
        self.assertFalse((self.root / R.BACKUP_DIR).exists())

    def test_04_post_or_evidence_changed_after_plan_is_refused(self):
        a, b = self.good_ids(2)
        self.make_stale(a)
        self.make_stale(b)
        m = self.plan()
        row = next(r for r in matrix_rows(self.fx) if r['id'] == a)
        post = self.root / row['output_path']
        post.write_bytes(post.read_bytes() + b'\nsua sau plan\n')
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(), m, [a])
        self.assertIn(cm.exception.code, ('INPUT_CHANGED_SINCE_PLAN', 'NOT_DOMAIN_ONLY'))
        ev = self.root / 'data/qa' / (b + '.json')
        ev.write_text(ev.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(), m, [b])
        self.assertEqual(cm.exception.code, 'EVIDENCE_CHANGED_SINCE_PLAN')

    def test_05_forged_manifest_cannot_force_an_ineligible_row(self):
        fail, unb, real = self.good_ids(3)
        self.make_stale(fail, bad_amount=True)
        self.make_stale(unb, unbound=True)
        self.make_stale(real, edit_after_migration=b'\nsua that\n')
        m = self.plan()
        self.assertEqual(m['eligible'], [])
        forged = copy.deepcopy(m)
        forged['eligible'] = [fail, unb, real]
        for aid, want in ((fail, 'FRESH_QA_NOT_ELIGIBLE'), (unb, 'NOT_DOMAIN_ONLY'),
                          (real, 'NOT_DOMAIN_ONLY')):
            forged['entries'][aid]['decision'] = R.ELIGIBLE
            with self.assertRaises(R.Refuse) as cm:
                R.apply_batch(self.ctx(), forged, [aid])
            self.assertEqual(cm.exception.code, want, aid)
        self.assertFalse((self.root / R.BACKUP_DIR).exists())

    def test_06_batch_is_atomic_one_bad_id_writes_nothing(self):
        a, b = self.good_ids(2)
        self.make_stale(a)
        self.make_stale(b)
        m = self.plan()
        ev_b = self.root / 'data/qa' / (b + '.json')
        ev_b.write_text(ev_b.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        before = self.evidence(a)
        with self.assertRaises(R.Refuse):
            R.apply_batch(self.ctx(), m, [a, b])
        self.assertEqual(self.evidence(a), before, 'ID dung truoc da bi ghi')
        self.assertFalse((self.root / R.BACKUP_DIR).exists())

    def test_06b_skip_ineligible_applies_the_good_ids_and_reports_the_rest(self):
        a, b = self.good_ids(2)
        self.make_stale(a)
        self.make_stale(b)
        m = self.plan()
        eb = self.root / 'data/qa' / (b + '.json')
        eb.write_text(eb.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        rep = R.apply_batch(self.ctx(batch='reattest-test-skip'), m, [a, b], skip_ineligible=True)
        self.assertEqual(rep['written'], [a])
        self.assertEqual([x['id'] for x in rep['skipped_ineligible']], [b])
        self.assertEqual(rep['skipped_ineligible'][0]['code'], 'EVIDENCE_CHANGED_SINCE_PLAN')
        self.assertEqual(self.evidence(a)['reattestation']['kind'], 'domain-migration-v3')
        # chon sai (ID khong co trong manifest) van dung ca batch du bat --skip-ineligible
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(batch='reattest-test-skip2'), m, ['BLG-99999'], skip_ineligible=True)
        self.assertEqual(cm.exception.code, 'NOT_ELIGIBLE')

    def test_07_apply_is_idempotent(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        m = self.plan()
        R.apply_batch(self.ctx(batch='reattest-test-1'), m, [a])
        after = (self.root / 'data/qa' / (a + '.json')).read_bytes()
        rep = R.apply_batch(self.ctx(batch='reattest-test-2'), m, [a])
        self.assertEqual(rep['already_current'], [a])
        self.assertEqual(rep.get('written', []), [])
        self.assertEqual((self.root / 'data/qa' / (a + '.json')).read_bytes(), after)
        self.assertFalse((self.root / R.BACKUP_DIR / 'reattest-test-2.json').exists())

    def test_08_rollback_restores_byte_exact_and_never_clobbers_other_changes(self):
        a, b = self.good_ids(2)
        self.make_stale(a)
        self.make_stale(b)
        orig = {i: (self.root / 'data/qa' / (i + '.json')).read_bytes() for i in (a, b)}
        m = self.plan()
        rep = R.apply_batch(self.ctx(batch='reattest-test-1'), m, [a, b])
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        # người khác sửa evidence b sau khi apply -> rollback KHÔNG được đè
        eb = self.root / 'data/qa' / (b + '.json')
        eb.write_text(eb.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        out = R.rollback_backup(self.root, backup)
        self.assertEqual(out['restored'], [a])
        self.assertEqual(out['skipped_changed_since_apply'], [b])
        self.assertEqual((self.root / 'data/qa' / (a + '.json')).read_bytes(), orig[a])

    def test_09_verify_detects_tampering(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        ctx = self.ctx(batch='reattest-test-1')
        rep = R.apply_batch(ctx, self.plan(), [a])
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        p = self.root / 'data/qa' / (a + '.json')
        ev = json.loads(p.read_text(encoding='utf-8'))
        ev['quality'] = 100
        ev['reattestation']['previous_evidence_sha256'] = '0' * 64
        p.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding='utf-8')
        self.assertTrue(R.verify_backup(ctx, backup))

    def test_10_batch_is_bounded_and_ids_must_be_chosen(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        m = self.plan()
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(), m, [])
        self.assertEqual(cm.exception.code, 'NO_IDS')
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(), m, ['BLG-%05d' % i for i in range(R.MAX_BATCH + 1)])
        self.assertEqual(cm.exception.code, 'BATCH_TOO_LARGE')

    def test_11_dry_run_writes_nothing(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        m = self.plan()
        before = self.evidence(a)
        rep = R.apply_batch(self.ctx(), m, [a], dry_run=True)
        self.assertEqual(rep['would_write'], [a])
        self.assertEqual(self.evidence(a), before)
        self.assertFalse((self.root / R.BACKUP_DIR).exists())

    def test_13_post_quoting_an_approved_price_is_eligible_unapproved_is_not(self):
        """Codex P1 (PR #9): thieu build_amount_whitelist thi gia da duyet bi coi la
        chua duyet. Bai trich dung gia da duyet phai du dieu kien; so la thi khong."""
        good, bad = self.good_ids(2)
        biz = json.loads((self.root / 'data/business-facts.json').read_text(encoding='utf-8'))
        approved = next(r['day'] for r in biz['approved_pricing'].values()
                        if isinstance(r, dict) and isinstance(r.get('day'), int))
        shown = '{:,}'.format(approved).replace(',', '.')
        for aid, line in ((good, '\nGia thue tham khao %s dong mot ngay.\n' % shown),
                          (bad, '\nGia thue duoc cam ket la 9.876.543 dong.\n')):
            row = next(r for r in matrix_rows(self.fx) if r['id'] == aid)
            post = self.root / row['output_path']
            post.write_bytes(post.read_bytes() + line.encode())
            self.make_stale(aid)
        m = self.plan()
        self.assertEqual(m['entries'][good]['decision'], R.ELIGIBLE, m['entries'][good])
        self.assertEqual(m['entries'][bad]['decision'], 'FRESH_QA_FAILED')
        self.assertIn('business_amounts', m['entries'][bad]['failed_checks'])
        self.assertEqual(m['eligible'], [good])

    def test_12b_manifest_must_be_bound_to_a_clean_commit(self):
        """plan --allow-dirty (head_bound false) and manifests that predate the field are
        proposals only: apply refuses them and writes nothing."""
        a, = self.good_ids(1)
        self.make_stale(a)
        ctx = self.ctx()
        self.assertIs(R.make_plan(ctx)['head_bound'], True)
        unbound = R.make_plan(ctx, head_bound=False)
        self.assertIs(unbound['head_bound'], False)
        legacy = R.make_plan(ctx)
        del legacy['head_bound']
        before = self.evidence(a)
        for manifest in (unbound, legacy, dict(R.make_plan(ctx), head_bound='yes')):
            with self.assertRaises(R.Refuse) as cm:
                R.apply_batch(self.ctx(), manifest, [a])
            self.assertEqual(cm.exception.code, 'MANIFEST_NOT_HEAD_BOUND')
            with self.assertRaises(R.Refuse) as cm:
                R.apply_batch(self.ctx(), manifest, [a], dry_run=True)
            self.assertEqual(cm.exception.code, 'MANIFEST_NOT_HEAD_BOUND')
        self.assertEqual(self.evidence(a), before)
        self.assertFalse((self.root / R.BACKUP_DIR).exists())

    def test_12_current_evidence_is_never_replaced(self):
        """Bài còn evidence KHỚP hash hiện tại không bao giờ là ứng viên."""
        a, = self.good_ids(1)
        m = self.plan()
        self.assertNotIn(a, m['entries'])
        self.assertEqual(m['eligible'], [])


class TestHardening(ReattestBase):
    """Findings of the independent adversarial review of the tool. Each test below fails on the
    tool as first written (or its safety check can be removed without any test noticing)."""

    # ---- helpers ------------------------------------------------------------------
    def hook_atomic_write(self, before=None, after=None):
        """Wrap R.atomic_write around EVIDENCE writes only: before(n, path) / after(n, path)."""
        real = R.atomic_write
        count = [0]

        def wrapped(path, data):
            ev = '/data/qa/' in str(path)
            if ev:
                count[0] += 1
                if before:
                    before(count[0], pathlib.Path(path))
            real(path, data)
            if ev and after:
                after(count[0], pathlib.Path(path))
        R.atomic_write = wrapped
        self.addCleanup(setattr, R, 'atomic_write', real)

    def ev_path(self, aid):
        return self.root / 'data/qa' / (aid + '.json')

    def applied(self, n=1, notes=None, batch='reattest-h'):
        ids = self.good_ids(n)
        for i in ids:
            self.make_stale(i, annotations=notes)
        ctx = self.ctx(batch=batch)
        rep = R.apply_batch(ctx, self.plan(), ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        return ids, ctx, backup

    def forge(self, aid, backup, mutate):
        """Edit the evidence AND the backup's recorded sha so the file passes the sha check
        (a consistent forgery): only the content checks can still notice."""
        p = self.ev_path(aid)
        ev = json.loads(p.read_text(encoding='utf-8'))
        mutate(ev)
        raw = R.evidence_text(ev).encode('utf-8')
        p.write_bytes(raw)
        backup['entries'][aid]['new_evidence_sha256'] = sha(raw)

    # ---- atomicity / failure handling -------------------------------------------------
    def test_20_failure_after_a_write_restores_every_id_and_removes_the_backup(self):
        a, b = sorted(self.good_ids(2))
        self.make_stale(a)
        self.make_stale(b)
        m = self.plan()
        before = {i: self.ev_path(i).read_bytes() for i in (a, b)}

        def boom(n, path):                    # interrupt AFTER the 2nd file was renamed into place
            if n == 2:
                raise KeyboardInterrupt()
        self.hook_atomic_write(after=boom)
        with self.assertRaises(KeyboardInterrupt):
            R.apply_batch(self.ctx(batch='reattest-h20'), m, [a, b])
        for i in (a, b):
            self.assertEqual(self.ev_path(i).read_bytes(), before[i], i)
        self.assertFalse((self.root / R.BACKUP_DIR / 'reattest-h20.json').exists())
        self.assertEqual(sorted(p.name for p in (self.root / 'data/qa').glob('*.tmp')), [])

    def test_21_when_a_rollback_cannot_restore_everything_the_backup_is_kept(self):
        a, b = sorted(self.good_ids(2))
        self.make_stale(a)
        self.make_stale(b)
        m = self.plan()

        def edit_behind_our_back(n, path):    # someone edits the 1st file right after our write
            if n == 1:
                path.write_bytes(path.read_bytes() + b'\n')
        self.hook_atomic_write(after=edit_behind_our_back)
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(batch='reattest-h21'), m, [a, b])
        self.assertEqual(cm.exception.code, 'PARTIAL_APPLY_BACKUP_KEPT')
        self.assertEqual(cm.exception.extra['left'], [a])
        backup_file = self.root / R.BACKUP_DIR / 'reattest-h21.json'
        self.assertTrue(backup_file.is_file(), 'the backup is the only way back: it must stay')
        backup = json.loads(backup_file.read_text(encoding='utf-8'))
        self.assertEqual(backup['entries'][a]['old_evidence_text'].encode(),
                         self.history['data/qa/%s.json' % a])
        self.assertEqual(sha(self.ev_path(b).read_bytes()), backup['entries'][b]['old_evidence_sha256'],
                         'the untouched second ID is still the old bytes')

    def test_22_the_backup_is_complete_on_disk_before_the_first_evidence_write(self):
        a, b = sorted(self.good_ids(2))
        self.make_stale(a)
        self.make_stale(b)
        m = self.plan()
        before = {i: self.ev_path(i).read_bytes() for i in (a, b)}
        seen = []

        def snapshot(n, path):
            bp = self.root / R.BACKUP_DIR / 'reattest-h22.json'
            seen.append(json.loads(bp.read_text(encoding='utf-8')) if bp.is_file() else None)
        self.hook_atomic_write(before=snapshot)
        R.apply_batch(self.ctx(batch='reattest-h22'), m, [a, b])
        self.assertEqual(len(seen), 2)
        for snap in seen:
            self.assertIsNotNone(snap, 'evidence was written before the backup existed')
            self.assertEqual(sorted(snap['entries']), [a, b])
            for i in (a, b):
                self.assertEqual(snap['entries'][i]['old_evidence_text'].encode(), before[i])

    def test_23_the_guard_is_rechecked_right_before_the_backup_is_written(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        m = self.plan()
        before = self.ev_path(a).read_bytes()
        ctx = self.ctx(batch='reattest-h23')
        calls = []

        def guard():
            calls.append((self.root / R.BACKUP_DIR / 'reattest-h23.json').exists())
            raise R.Refuse('DIRTY_TREE', 'simulated edit while the batch was being checked')
        ctx.guard = guard
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(ctx, m, [a])
        self.assertEqual(cm.exception.code, 'DIRTY_TREE')
        self.assertEqual(calls, [False])
        self.assertEqual(self.ev_path(a).read_bytes(), before)
        self.assertFalse((self.root / R.BACKUP_DIR / 'reattest-h23.json').exists())

    # ---- provenance: never reuse old scores, keep the historical stamps -------------------
    def test_24_old_scores_are_never_copied_into_the_new_evidence(self):
        a, = self.good_ids(1)
        self.make_stale(a, old_scores={'quality': 77, 'seo': 71, 'grade': 'C'})
        ctx = self.ctx(batch='reattest-h24')
        row = ctx.by_id[a]
        fresh = A.rescore_published(ctx.op, row, ctx.rows, ctx.biz, ctx.tax)
        self.assertNotEqual((fresh['quality'], fresh['seo']), (77, 71), 'fixture cannot tell the scores apart')
        R.apply_batch(ctx, self.plan(), [a])
        ev = self.evidence(a)
        self.assertEqual((ev['quality'], ev['seo'], ev['grade']), (fresh['quality'], fresh['seo'], fresh['grade']))

    def test_25_evidence_without_a_historical_scored_at_is_refused(self):
        a, = self.good_ids(1)
        self.make_stale(a, drop_scored_at=True)
        m = self.plan()
        self.assertIn(a, m['eligible'])
        before = self.ev_path(a).read_bytes()
        for skip in (False, True):            # a fresh scored_at would look like activity: never skippable
            with self.assertRaises(R.Refuse) as cm:
                R.apply_batch(self.ctx(), m, [a], skip_ineligible=skip)
            self.assertEqual(cm.exception.code, 'NO_HISTORICAL_SCORED_AT')
        self.assertEqual(self.ev_path(a).read_bytes(), before)

    # ---- selection / input validation ---------------------------------------------------------
    def test_26_a_row_that_stopped_being_published_after_the_plan_is_refused(self):
        a, b = sorted(self.good_ids(2))
        self.make_stale(a)
        self.make_stale(b)
        m = self.plan()
        rows = matrix_rows(self.fx)
        for r in rows:
            if r['id'] == a:
                r['status'] = 'REPAIR'
        save_matrix(self.fx, rows)
        before = self.ev_path(a).read_bytes()
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(), m, [a])
        self.assertEqual(cm.exception.code, 'NOT_PUBLISHED')
        rep = R.apply_batch(self.ctx(batch='reattest-h26'), m, [a, b], skip_ineligible=True)
        self.assertEqual(rep['written'], [b])
        self.assertEqual([(x['id'], x['code']) for x in rep['skipped_ineligible']], [(a, 'NOT_PUBLISHED')])
        self.assertEqual(self.ev_path(a).read_bytes(), before)

    def test_27_ids_batch_ids_and_output_paths_are_validated(self):
        a, b = sorted(self.good_ids(2))
        self.make_stale(a)
        self.make_stale(b)
        m = self.plan()
        R.apply_batch(self.ctx(batch='reattest-h27'), m, [a])
        first = (self.root / R.BACKUP_DIR / 'reattest-h27.json').read_bytes()
        eb = self.ev_path(b).read_bytes()
        with self.assertRaises(R.Refuse) as cm:       # same batch id again: never overwrite a backup
            R.apply_batch(self.ctx(batch='reattest-h27'), m, [b])
        self.assertEqual(cm.exception.code, 'BATCH_EXISTS')
        self.assertEqual((self.root / R.BACKUP_DIR / 'reattest-h27.json').read_bytes(), first)
        for bad in ('../../x', 'a/b', 'with space', 'x' * 81, '.hidden', '-x', 'a\nb'):
            with self.assertRaises(R.Refuse) as cm:
                R.apply_batch(self.ctx(batch=bad), m, [b])
            self.assertEqual(cm.exception.code, 'BAD_BATCH_ID', repr(bad))
        for bad in ('../../x', '/etc/passwd', 'BLG-00001\n', 'blg-1', 'BLG-\u0661'):
            with self.assertRaises(R.Refuse) as cm:
                R.apply_batch(self.ctx(), m, [bad])
            self.assertEqual(cm.exception.code, 'BAD_ID', repr(bad))
        self.assertEqual(sorted(p.name for p in (self.root / R.BACKUP_DIR).iterdir()), ['reattest-h27.json'])
        self.assertEqual(self.ev_path(b).read_bytes(), eb)
        rows = matrix_rows(self.fx)                   # an output_path that leaves _posts/ is refused
        for r in rows:
            if r['id'] == b:
                r['output_path'] = 'docs/ARTICLE-RULES.md'
        save_matrix(self.fx, rows)
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(batch='reattest-h27b'), m, [b])
        self.assertEqual(cm.exception.code, 'BAD_OUTPUT_PATH')

    def test_28_the_tool_never_runs_with_thresholds_below_its_own_floors(self):
        op = self.root / 'scripts/factory/factory-operator.py'
        original = op.read_text(encoding='utf-8')
        for old, new in (('SEO_MIN = 70', 'SEO_MIN = 65'), ('QUALITY_MIN = 75', 'QUALITY_MIN = 70')):
            self.assertIn(old, original)
            op.write_text(original.replace(old, new), encoding='utf-8')
            with self.assertRaises(R.Refuse) as cm:
                self.ctx()
            self.assertEqual(cm.exception.code, 'THRESHOLD_BELOW_FLOOR', new)
        op.write_text(original, encoding='utf-8')
        self.ctx()                                    # the real thresholds are accepted

    def test_29_a_manifest_made_for_another_scorer_or_threshold_is_refused(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        m = self.plan()
        op = self.root / 'scripts/factory/factory-operator.py'
        original = op.read_text(encoding='utf-8')
        op.write_text(original + '\n# edited after the plan\n', encoding='utf-8')
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(), m, [a])
        self.assertEqual(cm.exception.code, 'SCORER_CHANGED_SINCE_PLAN')
        op.write_text(original, encoding='utf-8')
        other = copy.deepcopy(m)
        other['thresholds']['seo_min'] = 65
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(), other, [a])
        self.assertEqual(cm.exception.code, 'SCORER_CHANGED_SINCE_PLAN')
        other = dict(m, baseline_commit='some-other-commit')
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(), other, [a])
        self.assertEqual(cm.exception.code, 'MANIFEST_BASELINE_MISMATCH')
        self.assertFalse((self.root / R.BACKUP_DIR).exists())

    # ---- idempotence must not trust a self-declared provenance ------------------------------
    def test_30_already_current_is_not_trusted_on_self_declared_provenance(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        m = self.plan()
        R.apply_batch(self.ctx(batch='reattest-h30'), m, [a])
        p = self.ev_path(a)
        ev = json.loads(p.read_text(encoding='utf-8'))
        ev['quality'], ev['result'] = 5, 'FAIL'       # hashes + reattestation block untouched
        p.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding='utf-8')
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(batch='reattest-h30b'), m, [a])
        self.assertEqual(cm.exception.code, 'UNEXPECTED_CURRENT_EVIDENCE')

    # ---- verify: not self-referential ---------------------------------------------------------
    def test_31_verify_rescores_so_a_consistent_forgery_is_caught(self):
        ids, ctx, backup = self.applied(1)
        a = ids[0]
        original = self.ev_path(a).read_bytes()
        original_sha = backup['entries'][a]['new_evidence_sha256']
        self.assertEqual(R.verify_backup(ctx, backup), [])
        cases = {
            'quality': lambda e: e.__setitem__('quality', 99 if e['quality'] == 100 else 100),
            'seo': lambda e: e.__setitem__('seo', 99 if e['seo'] == 100 else 100),
            'a check flipped': lambda e: e['checks'].__setitem__(
                'hanoi_example', not e['checks']['hanoi_example']),
            'scorer name': lambda e: e.__setitem__('scorer', 'forged-scorer'),
            'title': lambda e: e.__setitem__('title', 'Tieu de gia'),
            'word_count': lambda e: e.__setitem__('word_count', e['word_count'] + 1),
        }
        for name, mutate in cases.items():
            self.forge(a, backup, mutate)
            self.assertEqual(R.verify_backup(ctx, backup, rescore=False), [],
                             name + ': the structural checks alone cannot see this forgery')
            problems = R.verify_backup(ctx, backup)
            self.assertTrue(any('cham lai doc lap' in x for x in problems), (name, problems))
            self.ev_path(a).write_bytes(original)
            backup['entries'][a]['new_evidence_sha256'] = original_sha
        self.assertEqual(R.verify_backup(ctx, backup), [])

    def test_32_each_verify_field_check_fires_on_its_own(self):
        notes = {'hash_sync_note': 'cap nhat sau repair-frontmatter (test)'}
        ids, ctx, backup = self.applied(1, notes=notes)
        a = ids[0]
        original = self.ev_path(a).read_bytes()
        original_sha = backup['entries'][a]['new_evidence_sha256']

        def prov(key, value):
            return lambda e: e['reattestation'].__setitem__(key, value)

        def drop_notes(e):
            e['reattestation'].pop('previous_evidence_annotations')
        cases = [
            ('result', lambda e: e.__setitem__('result', 'FAIL'), 'diem/cong QA khong dat nguong'),
            ('business_fact', lambda e: e.__setitem__('business_fact', 'FAIL'), 'diem/cong QA khong dat nguong'),
            ('legal', lambda e: e.__setitem__('legal', 'FAIL'), 'diem/cong QA khong dat nguong'),
            ('critical_failure', lambda e: e.__setitem__('critical_failure', True), 'diem/cong QA khong dat nguong'),
            ('quality below floor', lambda e: e.__setitem__('quality', 74), 'diem/cong QA khong dat nguong'),
            ('seo below floor', lambda e: e.__setitem__('seo', 69), 'diem/cong QA khong dat nguong'),
            ('content_sha256', lambda e: e.__setitem__('content_sha256', '0' * 64), 'content_sha256 khong khop'),
            ('matrix_row_sha256', lambda e: e.__setitem__('matrix_row_sha256', '0' * 64), 'matrix_row_sha256 khong khop'),
            ('source_path', lambda e: e.__setitem__('source_path', '_posts/khac.md'), 'source_path'),
            ('article_id', lambda e: e.__setitem__('article_id', 'BLG-99999'), 'article_id'),
            ('previous_evidence_sha256', prov('previous_evidence_sha256', '0' * 64), 'provenance khong khop'),
            ('previous_content_sha256', prov('previous_content_sha256', '0' * 64), 'provenance khong khop'),
            ('previous_matrix_row_sha256', prov('previous_matrix_row_sha256', '0' * 64), 'provenance khong khop'),
            ('approval_ref blank', prov('approval_ref', '   '), 'provenance khong khop'),
            ('annotations dropped', drop_notes, 'chu thich lich su'),
        ]
        for name, mutate, fragment in cases:
            self.forge(a, backup, mutate)
            problems = R.verify_backup(ctx, backup, rescore=False)
            self.assertTrue(any(fragment in x for x in problems), (name, problems))
            self.ev_path(a).write_bytes(original)
            backup['entries'][a]['new_evidence_sha256'] = original_sha
        self.assertEqual(R.verify_backup(ctx, backup, rescore=False), [])
        self.ev_path(a).write_bytes(original + b'\n')      # plain edit: the sha check fires
        self.assertTrue(any('evidence khac ban da ghi' in x for x in R.verify_backup(ctx, backup)))
        self.ev_path(a).write_bytes(original)
        self.ev_path(a).unlink()
        self.assertTrue(any('thieu evidence' in x for x in R.verify_backup(ctx, backup)))

    def test_33_a_malformed_backup_is_refused_before_any_path_is_built(self):
        ids, ctx, backup = self.applied(1)
        a = ids[0]
        evil = copy.deepcopy(backup)
        evil['entries']['../../x'] = evil['entries'][a]
        for fn in (lambda: R.verify_backup(ctx, evil), lambda: R.rollback_backup(self.root, evil)):
            with self.assertRaises(R.Refuse) as cm:
                fn()
            self.assertEqual(cm.exception.code, 'BAD_BACKUP')
        with self.assertRaises(R.Refuse) as cm:
            R.rollback_backup(self.root, backup, ids={'BLG-99999'})
        self.assertEqual(cm.exception.code, 'UNKNOWN_IDS')
        with self.assertRaises(R.Refuse) as cm:
            R.verify_backup(ctx, dict(backup, entries={}))
        self.assertEqual(cm.exception.code, 'BAD_BACKUP')

    # ---- rollback --------------------------------------------------------------------------------
    def test_34_rollback_restores_every_historical_byte_format_verbatim(self):
        ids = sorted(self.good_ids(3))
        for i, fmt in zip(ids, ('indent2', 'indent1_nl', 'crlf')):
            self.make_stale(i, fmt=fmt)
        before = {i: self.ev_path(i).read_bytes() for i in ids}
        rep = R.apply_batch(self.ctx(batch='reattest-h34'), self.plan(), ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        for i in ids:
            self.assertNotEqual(self.ev_path(i).read_bytes(), before[i])
        dry = R.rollback_backup(self.root, backup, ids={ids[0]}, dry_run=True)
        self.assertEqual(dry['restored'], [ids[0]])
        self.assertNotEqual(self.ev_path(ids[0]).read_bytes(), before[ids[0]], '--dry-run wrote')
        out = R.rollback_backup(self.root, backup, ids={ids[1], ids[2]})
        self.assertEqual(sorted(out['restored']), [ids[1], ids[2]])
        self.assertNotEqual(self.ev_path(ids[0]).read_bytes(), before[ids[0]], '--ids was ignored')
        R.rollback_backup(self.root, backup)
        for i in ids:
            self.assertEqual(self.ev_path(i).read_bytes(), before[i], i)

    def test_35_rollback_refuses_a_corrupt_backup_entry(self):
        ids, ctx, backup = self.applied(1)
        a = ids[0]
        backup['entries'][a]['old_evidence_text'] += ' '       # text no longer matches its sha
        with self.assertRaises(R.Refuse) as cm:
            R.rollback_backup(self.root, backup)
        self.assertEqual(cm.exception.code, 'BACKUP_CORRUPT')

    def test_37_an_evidence_edited_between_the_check_and_the_write_is_never_overwritten(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        m = self.plan()
        ctx = self.ctx(batch='reattest-h37')

        def concurrent_edit():                # runs after every ID was checked, before the first write
            self.ev_path(a).write_bytes(self.ev_path(a).read_bytes() + b' ')
        ctx.guard = concurrent_edit
        edited = None
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(ctx, m, [a])
        self.assertEqual(cm.exception.code, 'EVIDENCE_CHANGED_DURING_APPLY')
        self.assertTrue(self.ev_path(a).read_bytes().endswith(b' '), 'the other writer\'s edit must survive')
        self.assertNotIn(b'reattestation', self.ev_path(a).read_bytes())
        self.assertFalse((self.root / R.BACKUP_DIR / 'reattest-h37.json').exists(),
                         'nothing of ours was written, so there is nothing to keep')

    def test_38_a_backup_that_does_not_read_back_stops_before_any_evidence_is_touched(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        m = self.plan()
        before = self.ev_path(a).read_bytes()
        real = R.atomic_write

        def corrupt_backup(path, data):
            real(path, b'{"schema": "not the backup"}' if R.BACKUP_DIR in str(path) else data)
        R.atomic_write = corrupt_backup
        self.addCleanup(setattr, R, 'atomic_write', real)
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(batch='reattest-h38'), m, [a])
        self.assertEqual(cm.exception.code, 'BACKUP_READBACK_FAILED')
        self.assertEqual(self.ev_path(a).read_bytes(), before)
        self.assertFalse((self.root / R.BACKUP_DIR / 'reattest-h38.json').exists())

    def test_39_a_row_that_already_matches_but_was_not_re_attested_is_not_idempotence(self):
        """Evidence that matches the hashes natively (no re-attestation block) must never be
        accepted as 'already current' just because a manifest lists the ID."""
        a, b = self.good_ids(2)
        self.make_stale(a)
        m = self.plan()
        forged = copy.deepcopy(m)
        forged['entries'][b] = dict(forged['entries'][a], id=b)
        forged['eligible'] = sorted(forged['eligible'] + [b])
        before = self.ev_path(b).read_bytes()
        with self.assertRaises(R.Refuse) as cm:
            R.apply_batch(self.ctx(batch='reattest-h39'), forged, [b])
        self.assertEqual(cm.exception.code, 'UNEXPECTED_CURRENT_EVIDENCE')
        self.assertEqual(self.ev_path(b).read_bytes(), before)

    def test_40_atomic_write_never_leaves_a_temp_file_or_a_half_written_target(self):
        d = self.root / 'zz-atomic'
        target = d / 'x.json'
        R.atomic_write(target, b'old')
        self.assertEqual(target.read_bytes(), b'old')
        real = os.replace

        def boom(src, dst):
            raise OSError('simulated rename failure')
        os.replace = boom
        self.addCleanup(setattr, os, 'replace', real)
        with self.assertRaises(OSError):
            R.atomic_write(target, b'new')
        os.replace = real
        self.assertEqual(target.read_bytes(), b'old')
        self.assertEqual(sorted(x.name for x in d.iterdir()), ['x.json'])

    def test_36_evidence_text_is_what_the_operators_writer_produces(self):
        ctx = self.ctx()
        obj = {'article_id': 'BLG-1', 'checks': {'a': True, 'b': False}, 'ghi_chu': 'tieng Viet co dau: đ',
               'n': [1, 2.5, None]}
        tmp = str(self.root / 'zz-format.json')
        ctx.op.write_json_atomic(tmp, obj)
        self.assertEqual(pathlib.Path(tmp).read_bytes(), R.evidence_text(obj).encode('utf-8'))


class TestCliEndToEnd(ReattestBase):
    """Đường CLI thật: lịch sử baseline nằm trong GIT (plumbing, không đụng HEAD),
    chạy bản sao của tool trong fixture bằng subprocess."""

    def commit_history(self):
        env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
                   GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')

        def git(*a, inp=None, e=None):
            r = subprocess.run(['git'] + list(a), cwd=self.fx, input=inp,
                               capture_output=True, env=e or env)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout.decode().strip()
        git('init', '-q')
        idx_env = dict(env, GIT_INDEX_FILE=os.path.join(self.fx, '.git', 'reattest-test-index'))
        for path, data in self.history.items():
            blob = git('hash-object', '-w', '--stdin', inp=data)
            git('update-index', '--add', '--cacheinfo', '100644,%s,%s' % (blob, path), e=idx_env)
        tree = git('write-tree', e=idx_env)
        return git('commit-tree', tree, '-m', 'baseline (pre-migration)')

    def git(self, *a, inp=None):
        env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
                   GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
        r = subprocess.run(['git'] + list(a), cwd=self.fx, input=inp, capture_output=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.decode().strip()

    def commit_worktree(self, baseline=None):
        """Commit the fixture tree as HEAD (plan/apply refuse a tree that differs from HEAD),
        descending from `baseline` when given: the tool refuses a baseline that is not an
        ancestor of HEAD."""
        self.git('add', '-A')
        tree = self.git('write-tree')
        commit = self.git(*(['commit-tree', tree, '-m', 'fixture HEAD'] + (['-p', baseline] if baseline else [])))
        self.git('update-ref', 'HEAD', commit)
        return commit

    def pin_baseline(self, baseline):
        """The tool only accepts the migration baseline pinned in its source. Point the
        fixture's COPY of the tool (never the real one) at the fixture's synthetic baseline;
        do it BEFORE commit_worktree so the tree stays clean."""
        tool = self.root / 'scripts/factory/reattest-legacy-qa.py'
        text = tool.read_text(encoding='utf-8')
        self.assertIn(R.PINNED_BASELINE, text)
        tool.write_text(text.replace(R.PINNED_BASELINE, baseline), encoding='utf-8')

    def cli(self, *args):
        r = subprocess.run([sys.executable, 'scripts/factory/reattest-legacy-qa.py'] + list(args),
                           cwd=self.fx, capture_output=True, text=True)
        try:
            out = json.loads(r.stdout)
        except ValueError:
            out = None
        return r.returncode, out, r.stdout, r.stderr

    def test_14_plan_apply_verify_rollback_via_cli_and_git_history(self):
        a, = self.good_ids(1)
        old_ev = self.make_stale(a)
        baseline = self.commit_history()
        self.pin_baseline(baseline)
        self.commit_worktree(baseline)
        before = (self.root / 'data/qa' / (a + '.json')).read_bytes()
        guard = tree_hashes(self.root, GUARD)
        rc, out, so, se = self.cli('plan', '--baseline', baseline, '--out', 'plan-e2e.json')
        self.assertEqual(rc, 0, (so, se))
        manifest = json.loads((self.root / 'plan-e2e.json').read_text(encoding='utf-8'))
        self.assertIn(a, manifest['eligible'])
        # khong co --approval-ref => TU CHOI, khong ghi gi
        rc, out, so, se = self.cli('apply', '--manifest', 'plan-e2e.json', '--ids', a)
        self.assertEqual(rc, 1, (so, se))
        self.assertEqual(out['code'], 'NO_APPROVAL')
        self.assertEqual((self.root / 'data/qa' / (a + '.json')).read_bytes(), before)
        rc, out, so, se = self.cli('apply', '--manifest', 'plan-e2e.json', '--ids', a,
                                   '--approval-ref', 'owner authorization (e2e test)',
                                   '--batch-id', 'e2e-1')
        self.assertEqual(rc, 0, (so, se))
        self.assertEqual(out['written'], [a])
        backup = 'reports/qa-audit/reattest/e2e-1.json'
        rc, out, so, se = self.cli('verify', '--backup', backup)
        self.assertEqual(rc, 0, (so, se))
        self.assertTrue(out['ok'])
        self.assertEqual(tree_hashes(self.root, GUARD), guard)
        rc, out, so, se = self.cli('rollback', '--backup', backup)
        self.assertEqual(rc, 0, (so, se))
        self.assertEqual(out['restored'], [a])
        self.assertEqual((self.root / 'data/qa' / (a + '.json')).read_bytes(), before)

    def test_15_clean_tree_guard_and_head_bound_manifests(self):
        """plan/apply refuse a tree that differs from HEAD (a score is only attributable
        to a commit when every input is that commit's); plan --allow-dirty is an explicit
        opt-out whose manifest apply refuses; verify/rollback are never guarded."""
        a, = self.good_ids(1)
        self.make_stale(a)
        baseline = self.commit_history()
        self.pin_baseline(baseline)
        self.commit_worktree(baseline)
        ev = self.root / 'data/qa' / (a + '.json')
        before = ev.read_bytes()
        approval = ('--approval-ref', 'owner authorization (e2e test)')
        rc, out, so, se = self.cli('plan', '--baseline', baseline, '--out', 'plan-clean.json')
        self.assertEqual(rc, 0, (so, se))
        clean = json.loads((self.root / 'plan-clean.json').read_text(encoding='utf-8'))
        self.assertIs(clean['head_bound'], True)
        self.assertIn(a, clean['eligible'])

        probe = self.root / 'AGENTS.md'                    # tracked file, scorer-irrelevant
        original = probe.read_bytes()
        probe.write_bytes(original + b'\n<!-- probe -->\n')
        rc, out, so, se = self.cli('plan', '--baseline', baseline, '--out', 'plan-dirty.json')
        self.assertEqual((rc, out and out['code']), (1, 'DIRTY_TREE'), (so, se))
        self.assertTrue(any('AGENTS.md' in d for d in out['dirty']), out)
        self.assertFalse((self.root / 'plan-dirty.json').exists())
        rc, out, so, se = self.cli('plan', '--baseline', baseline, '--out', 'plan-dirty.json',
                                   '--allow-dirty')
        self.assertEqual(rc, 0, (so, se))
        dirty = json.loads((self.root / 'plan-dirty.json').read_text(encoding='utf-8'))
        self.assertIs(dirty['head_bound'], False)
        # a good (head-bound) manifest still cannot be applied on a dirty tree, dry run included
        for extra in ((), ('--dry-run',)):
            rc, out, so, se = self.cli('apply', '--manifest', 'plan-clean.json', '--ids', a,
                                       *approval, *extra)
            self.assertEqual((rc, out and out['code']), (1, 'DIRTY_TREE'), (so, se))
        self.assertEqual(ev.read_bytes(), before)
        self.assertFalse((self.root / R.BACKUP_DIR).exists())

        # an untracked file inside an input directory is dirty as well
        probe.write_bytes(original)
        stray = self.root / 'data' / 'zz-untracked-probe.json'
        stray.write_text('{}', encoding='utf-8')
        rc, out, so, se = self.cli('apply', '--manifest', 'plan-clean.json', '--ids', a,
                                   *approval, '--dry-run')
        self.assertEqual((rc, out and out['code']), (1, 'DIRTY_TREE'), (so, se))
        stray.unlink()

        # clean again: the not-head-bound manifest is refused, the head-bound one works
        rc, out, so, se = self.cli('apply', '--manifest', 'plan-dirty.json', '--ids', a, *approval)
        self.assertEqual((rc, out and out['code']), (1, 'MANIFEST_NOT_HEAD_BOUND'), (so, se))
        self.assertEqual(ev.read_bytes(), before)
        rc, out, so, se = self.cli('apply', '--manifest', 'plan-clean.json', '--ids', a, *approval,
                                   '--batch-id', 'e2e-guard')
        self.assertEqual(rc, 0, (so, se))
        self.assertEqual(out['written'], [a])
        # the write leaves the tree dirty on purpose: one batch = one commit, then the next
        rc, out, so, se = self.cli('apply', '--manifest', 'plan-clean.json', '--ids', a, *approval)
        self.assertEqual((rc, out and out['code']), (1, 'DIRTY_TREE'), (so, se))
        # verify and rollback work on that dirty tree
        backup = 'reports/qa-audit/reattest/e2e-guard.json'
        rc, out, so, se = self.cli('verify', '--backup', backup)
        self.assertEqual(rc, 0, (so, se))
        rc, out, so, se = self.cli('rollback', '--backup', backup)
        self.assertEqual((rc, out['restored']), (0, [a]), (so, se))
        self.assertEqual(ev.read_bytes(), before)

    def test_16_cli_plan_ids_offset_verify_exit_code_rollback_options_and_relative_out(self):
        a, b = sorted(self.good_ids(2))
        self.make_stale(a)
        self.make_stale(b)
        baseline = self.commit_history()
        self.pin_baseline(baseline)
        self.commit_worktree(baseline)
        ev = {i: self.root / 'data/qa' / (i + '.json') for i in (a, b)}
        before = {i: ev[i].read_bytes() for i in (a, b)}
        approval = ('--approval-ref', 'owner authorization (e2e test)')
        # plan --ids only plans the selected IDs
        rc, out, so, se = self.cli('plan', '--baseline', baseline, '--out', 'plan-one.json', '--ids', a)
        self.assertEqual(rc, 0, (so, se))
        one = json.loads((self.root / 'plan-one.json').read_text(encoding='utf-8'))
        self.assertEqual((one['eligible'], sorted(one['entries'])), ([a], [a]))
        # a relative --out is relative to the CALLER's directory, not to the repo root
        other = tempfile.mkdtemp(prefix='reattest-cwd-')
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        r = subprocess.run([sys.executable, str(self.root / 'scripts/factory/reattest-legacy-qa.py'),
                            'plan', '--baseline', baseline, '--out', 'rel-plan.json'],
                           cwd=other, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((pathlib.Path(other) / 'rel-plan.json').is_file())
        self.assertFalse((self.root / 'rel-plan.json').exists())
        manifest = json.loads((pathlib.Path(other) / 'rel-plan.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['eligible'], [a, b])
        (self.root / 'plan.json').write_text(json.dumps(manifest), encoding='utf-8')
        # a traversing --batch-id is refused before anything is written
        rc, out, so, se = self.cli('apply', '--manifest', 'plan.json', '--ids', b, *approval,
                                   '--batch-id', '../../../data/state/zz-traversal')
        self.assertEqual((rc, out and out['code']), (1, 'BAD_BATCH_ID'), (so, se))
        self.assertFalse((self.root / 'data/state/zz-traversal.json').exists())
        self.assertEqual(ev[b].read_bytes(), before[b])
        # --limit/--offset select by position in the eligible list: offset 1 is the SECOND id
        rc, out, so, se = self.cli('apply', '--manifest', 'plan.json', *approval, '--limit', '1',
                                   '--offset', '1', '--batch-id', 'cli-offset')
        self.assertEqual((rc, out and out['written']), (0, [b]), (so, se))
        self.assertEqual(ev[a].read_bytes(), before[a])
        backup = 'reports/qa-audit/reattest/cli-offset.json'
        rc, out, so, se = self.cli('verify', '--backup', backup)
        self.assertEqual((rc, out['ok']), (0, True), (so, se))
        rc, out, so, se = self.cli('verify', '--backup', backup, '--no-rescore')
        self.assertEqual(rc, 0, (so, se))
        # --no-rescore keeps only the structural checks: a consistent forgery (a score edited
        # together with its backup entry) passes it and is caught by the default re-scoring verify
        raw = ev[b].read_bytes()
        forged = json.loads(raw)
        forged['quality'] = 99 if forged['quality'] == 100 else 100
        forged_raw = R.evidence_text(forged).encode('utf-8')
        bfile = self.root / backup
        bk = json.loads(bfile.read_text(encoding='utf-8'))

        def set_state(evidence_bytes):
            ev[b].write_bytes(evidence_bytes)
            bk['entries'][b]['new_evidence_sha256'] = sha(evidence_bytes)
            bfile.write_text(json.dumps(bk, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                             encoding='utf-8')
        set_state(forged_raw)
        rc, out, so, se = self.cli('verify', '--backup', backup, '--no-rescore')
        self.assertEqual(rc, 0, (so, se))
        rc, out, so, se = self.cli('verify', '--backup', backup)
        self.assertEqual((rc, out['ok']), (1, False), (so, se))
        set_state(raw)
        rc, out, so, se = self.cli('verify', '--backup', backup)
        self.assertEqual(rc, 0, (so, se))
        # rollback argument handling
        rc, out, so, se = self.cli('rollback', '--backup', backup, '--ids', 'BLG-99999')
        self.assertEqual((rc, out['code']), (1, 'UNKNOWN_IDS'), (so, se))
        rc, out, so, se = self.cli('rollback', '--backup', backup, '--ids', '')
        self.assertEqual((rc, out['code']), (1, 'BAD_IDS'), (so, se))
        written = ev[b].read_bytes()
        rc, out, so, se = self.cli('rollback', '--backup', backup, '--ids', b, '--dry-run')
        self.assertEqual((rc, out['restored'], out['dry_run']), (0, [b], True), (so, se))
        self.assertEqual(ev[b].read_bytes(), written, '--dry-run wrote')
        # a tampered evidence: verify exits 1 (names the problem) and rollback will not clobber it
        ev[b].write_bytes(written + b'\n')
        rc, out, so, se = self.cli('verify', '--backup', backup)
        self.assertEqual((rc, out['ok']), (1, False), (so, se))
        self.assertTrue(out['problems'])
        rc, out, so, se = self.cli('rollback', '--backup', backup)
        self.assertEqual((rc, out['restored'], out['skipped_changed_since_apply']), (0, [], [b]), (so, se))
        ev[b].write_bytes(written)
        rc, out, so, se = self.cli('rollback', '--backup', backup, '--ids', b)
        self.assertEqual((rc, out['restored']), (0, [b]), (so, se))
        self.assertEqual(ev[b].read_bytes(), before[b])

    def test_17_only_the_pinned_baseline_that_is_an_ancestor_of_head_is_accepted(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        baseline = self.commit_history()
        # (1) the tool still pins the REAL baseline: the fixture's synthetic one is refused
        self.commit_worktree(baseline)
        rc, out, so, se = self.cli('plan', '--baseline', baseline, '--out', 'p.json')
        self.assertEqual((rc, out and out['code']), (1, 'BASELINE_NOT_PINNED'), (so, se))
        self.assertFalse((self.root / 'p.json').exists())
        # (2) pinned, but HEAD does not descend from it
        self.pin_baseline(baseline)
        self.commit_worktree(None)
        rc, out, so, se = self.cli('plan', '--baseline', baseline, '--out', 'p.json')
        self.assertEqual((rc, out and out['code']), (1, 'BASELINE_NOT_ANCESTOR'), (so, se))
        # (3) pinned and an ancestor: accepted
        self.commit_worktree(baseline)
        rc, out, so, se = self.cli('plan', '--baseline', baseline, '--out', 'p.json')
        self.assertEqual(rc, 0, (so, se))
        # a manifest naming another baseline cannot be applied either
        manifest = json.loads((self.root / 'p.json').read_text(encoding='utf-8'))
        manifest['baseline_commit'] = '1' * 40
        (self.root / 'p2.json').write_text(json.dumps(manifest), encoding='utf-8')
        rc, out, so, se = self.cli('apply', '--manifest', 'p2.json', '--ids', a,
                                   '--approval-ref', 'owner authorization (e2e test)')
        self.assertEqual(rc, 1, (so, se))
        self.assertIn(out['code'], ('BAD_BASELINE', 'BASELINE_NOT_PINNED'))

    def test_18_the_clean_tree_guard_sees_skip_worktree_edits_to_the_scorer(self):
        a, = self.good_ids(1)
        self.make_stale(a)
        baseline = self.commit_history()
        self.pin_baseline(baseline)
        self.commit_worktree(baseline)
        scorer = 'scripts/factory/factory-operator.py'
        self.git('update-index', '--skip-worktree', scorer)
        text = (self.root / scorer).read_text(encoding='utf-8')
        (self.root / scorer).write_text(text.replace('SEO_MIN = 70', 'SEO_MIN = 65'), encoding='utf-8')
        self.assertEqual(self.git('status', '--porcelain'), '', 'git status is blind to the edit')
        for args in (('plan', '--baseline', baseline, '--out', 'p.json'),):
            rc, out, so, se = self.cli(*args)
            self.assertEqual((rc, out and out['code']), (1, 'DIRTY_TREE'), (so, se))
            self.assertTrue(any(scorer in d and d.startswith('!! S') for d in out['dirty']), out['dirty'])
        self.assertFalse((self.root / 'p.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
