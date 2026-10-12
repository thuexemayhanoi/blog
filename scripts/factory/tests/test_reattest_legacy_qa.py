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
import subprocess
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / 'reattest-legacy-qa.py'
sys.path.insert(0, str(HERE))
from test_qa_modes import FxTestCase, matrix_rows  # noqa: E402

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
        self.history = {}
        self.stale_ids = []

    # ---- dựng ca "domain-only" trong fixture ---------------------------------
    def make_stale(self, aid, *, edit_after_migration=None, bad_amount=False,
                   unbound=False, annotations=None):
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
        ev_path.write_text(json.dumps(old_ev, ensure_ascii=False, indent=2),
                           encoding='utf-8')
        self.history[row['output_path']] = old
        self.history['data/qa/%s.json' % aid] = json.dumps(
            old_ev, ensure_ascii=False, indent=2).encode()
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

    def commit_worktree(self):
        """Commit the fixture tree as HEAD: plan/apply refuse a tree that differs from HEAD."""
        env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
                   GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
        for args in (['add', '-A'], ['commit', '-q', '-m', 'fixture HEAD']):
            r = subprocess.run(['git'] + args, cwd=self.fx, capture_output=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)

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
        self.commit_worktree()
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
        self.commit_worktree()
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
