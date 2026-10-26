#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test sync-matrix-urls.py trên bản sao hermetic của repo (FxTestCase) — OFFLINE (Issue #77, 50 URL BLG-00820…00869).

Phủ: chỉ sửa 2 cột expected_url/canonical_url của hàng PUBLISHED ngoài baseline đ→d có evidence NGUYÊN VẸN và đúng dạng lỗi đã biết
(`/cm/YYYY/MM/DD/slug/` -> permalink thật `/cm/YYYY-MM-DD/slug/` | `/cm/YYYY-MM-DD-slug/`); mọi ca khác bị TỪ CHỐI (không có cờ ép);
bài/permalink/redirects/registry không đổi một byte; evidence chấm lại độc lập + provenance + chuỗi lịch sử, mốc lịch sử giữ nguyên;
manifest lỗi thời không ép được; lô <= 50, cần --approval-ref; dry-run không ghi; verify bắt sửa tay; rollback byte-exact, không đè
thay đổi của người khác và chạy lại được sau khi bị ngắt; apply lỗi giữa chừng tự trả mọi thứ về byte cũ.

Chạy: python3 scripts/factory/tests/test_sync_matrix_urls.py (từ gốc repository)
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / 'sync-matrix-urls.py'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from test_qa_modes import FxTestCase, matrix_rows  # noqa: E402

spec = importlib.util.spec_from_file_location('sync_under_test', SCRIPT)
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
M, R, A, SR = S.M, S.R, S.A, S.SR


def sha(b):
    return hashlib.sha256(b).hexdigest()


def tree_hashes(root, rels):
    out = {}
    for rel in rels:
        p = pathlib.Path(root) / rel
        files = sorted(f for f in p.rglob('*') if f.is_file()) if p.is_dir() else ([p] if p.is_file() else [])
        for f in files:
            out[str(f.relative_to(root))] = sha(f.read_bytes())
    return out


WATCH = ('_posts', 'data/qa', 'data/content-matrix.csv', 'redirects', 'reports/factory/seo-master/slug-redirect-registry.csv', '_data')


class TestShapes(unittest.TestCase):

    def test_real_shapes_known_defect_only(self):
        self.assertEqual(S.real_shapes('/ky-nang/2026/09/29/tranh-goc-mu-xe-tai-o-vong-xuyen/'),
                         ('/ky-nang/2026-09-29/tranh-goc-mu-xe-tai-o-vong-xuyen/', '/ky-nang/2026-09-29-tranh-goc-mu-xe-tai-o-vong-xuyen/'))
        for bad in ('', None, '/ky-nang/2026-09-29/x/', '/ky-nang/x/', '/ky-nang/2026/09/29/x', 'ky-nang/2026/09/29/x/',
                    '/Ky-Nang/2026/09/29/x/', '/ky-nang/2026/9/29/x/', '/ky-nang/2026/09/29/x/y/', '/ky-nang/2026/09/29/x/?a=1',
                    'https://a.b/ky-nang/2026/09/29/x/', '/ky-nang/2026/09/29/đ/'):
            self.assertEqual(S.real_shapes(bad), (), repr(bad))


class SyncBase(FxTestCase):

    def setUp(self):
        super().setUp()
        self._cwd = os.getcwd()
        self.addCleanup(os.chdir, self._cwd)
        self.root = pathlib.Path(self.fx)
        self.focus = set()
        self._cands = None

    def ctx(self, approval='owner authorization (test)', batch='test-sync'):
        c = S.make_ctx(self.root, approval, batch)
        c.rows = c.rows[:250] + [r for r in c.rows[250:] if r['id'] in self.focus]          # chấm nhanh: corpus thu gọn
        return c

    def row(self, aid):
        return next(r for r in matrix_rows(self.fx) if r['id'] == aid)

    def evidence(self, aid):
        return json.loads((self.root / 'data/qa' / (aid + '.json')).read_text(encoding='utf-8'))

    def candidates(self):
        """ID PUBLISHED ngoài baseline/registry, evidence NGUYÊN VẸN, không lease/draft — ứng viên dựng lỗi nhân tạo trong fixture."""
        if self._cands is None:
            c = S.make_ctx(self.root, 'x', 'probe')
            out = []
            for r in c.rows:
                aid = r['id']
                if r['status'] != 'PUBLISHED' or aid in c.baseline or aid in c.registry:
                    continue
                ev_p = self.root / 'data/qa' / (aid + '.json')
                post_p = self.root / (r.get('output_path') or '-')
                if not ev_p.is_file() or not post_p.is_file():
                    continue
                ev = json.loads(ev_p.read_text(encoding='utf-8'))
                m = re.match(r'^_posts/(\d{4})-(\d{2})-(\d{2})-(.+)\.md\Z', r['output_path'])
                if not (m and m.group(4) == r['slug'] and r['expected_url'] == r['canonical_url']
                        and sha(post_p.read_bytes()) == ev.get('content_sha256') and A.fingerprint(r) == ev.get('matrix_row_sha256')
                        and ev.get('result') == 'PASS' and ev.get('scored_at') and 'revision' not in ev):
                    continue
                if not re.match(r'^/[a-z0-9-]+/', r['expected_url']):
                    continue
                out.append(aid)
                if len(out) >= 12:
                    break
            self._cands = out
        return self._cands

    def seal(self, aid):
        """Chấm lại + ghi evidence gắn đúng byte bài / hàng matrix HIỆN TẠI của fixture (giữ mốc lịch sử và chú thích cũ)."""
        c = self.ctx()
        row = c.by_id[aid]
        old = self.evidence(aid)
        ev = R.score_candidate(c, row, (self.root / row['output_path']).read_bytes())
        for k, v in old.items():
            if k not in ev or k in ('scored_at', 'published_at'):
                ev[k] = v
        (self.root / 'data/qa' / (aid + '.json')).write_text(R.evidence_text(ev), encoding='utf-8')

    def make_defect(self, aid, shape='dir'):
        """Dựng đúng lỗi 50 URL trong fixture: permalink thật `/cm/YYYY-MM-DD[/|-]slug/`, matrix `/cm/YYYY/MM/DD/slug/`; chấm lại + ghi evidence."""
        self.focus.add(aid)
        row = self.row(aid)
        cm = row['expected_url'].split('/')[1]
        y, mo, d = re.match(r'^_posts/(\d{4})-(\d{2})-(\d{2})-', row['output_path']).groups()
        real = '/%s/%s-%s-%s/%s/' % (cm, y, mo, d, row['slug']) if shape == 'dir' else '/%s/%s-%s-%s-%s/' % (cm, y, mo, d, row['slug'])
        wrong = '/%s/%s/%s/%s/%s/' % (cm, y, mo, d, row['slug'])
        post_p = self.root / row['output_path']
        text = post_p.read_text(encoding='utf-8')
        R.atomic_write(post_p, M.replace_permalink(text, M.front_permalink(text), real).encode('utf-8'))
        new_row = dict(row, expected_url=wrong, canonical_url=wrong)
        R.atomic_write(self.root / S.MATRIX_REL, M.matrix_bytes_with(self.root, {aid: new_row}))
        self.seal(aid)
        return real, wrong

    def defects(self, n, shapes=('dir', 'dash')):
        ids = self.candidates()[:n]
        if len(ids) < n:
            self.skipTest('fixture khong du bai ung vien')
        out = {}
        for i, aid in enumerate(ids):
            out[aid] = self.make_defect(aid, shapes[i % len(shapes)])
        return out

    def manifest(self, ids):
        m = S.make_plan(self.ctx(), ids)
        self.assertEqual(sorted(m['eligible']), sorted(ids), m['excluded'])
        return m

    def apply(self, manifest, ids, **kw):
        return S.apply_batch(self.ctx(batch=kw.pop('batch', 'test-sync')), manifest, ids, **kw)


class TestPlan(SyncBase):

    def test_01_plan_accepts_both_real_shapes_and_writes_nothing(self):
        defects = self.defects(2)
        guard = tree_hashes(self.root, WATCH)
        m = S.make_plan(self.ctx(), list(defects))
        self.assertEqual(sorted(m['eligible']), sorted(defects), m['excluded'])
        for aid, (real, wrong) in defects.items():
            e = m['entries'][aid]
            self.assertEqual((e['permalink'], e['old_matrix_url']), (real, wrong))
            self.assertEqual(e['decision'], S.ELIGIBLE)
            self.assertNotEqual(e['old_row_fingerprint'], e['new_row_fingerprint'])
            self.assertGreaterEqual(e['after']['quality'], 75)
        self.assertTrue(m['head_bound'])
        self.assertEqual(tree_hashes(self.root, WATCH), guard)

    def test_02_plan_needs_explicit_ids(self):
        with self.assertRaises(R.Refuse) as e:
            S.make_plan(self.ctx(), [])
        self.assertEqual(e.exception.code, 'NO_IDS')

    def test_03_refusals_are_specific(self):
        aid, other = list(self.defects(2))
        decide = lambda a, c=None: self.expect_code(c or self.ctx(), a)
        # đã khớp (không lệch) -> NO_DRIFT
        clean = self.candidates()[2] if len(self.candidates()) > 2 else None
        if clean:
            self.focus.add(clean)
            self.assertEqual(decide(clean), 'NO_DRIFT')
        # URL matrix không đúng dạng lỗi đã biết -> không đoán (evidence gắn vân tay hàng nên dựng bằng cách đổi matrix THẬT rồi chấm lại)
        wrong = self.row(aid)['expected_url']
        self.retarget(aid, '/khac/hoan-toan/', '/khac/hoan-toan/')
        self.assertEqual(decide(aid), 'MATRIX_URL_UNKNOWN_SHAPE')
        self.retarget(aid, wrong, wrong + 'x/')
        self.assertEqual(decide(aid), 'MATRIX_URL_INCONSISTENT')
        self.retarget(aid, wrong, wrong)
        # hàng khác trong matrix đã dùng permalink thật -> va chạm
        real, _ = self.make_defect_info(aid)
        c = self.ctx()
        c.rows = c.rows + [dict(c.rows[0], id='BLG-99998', expected_url=real, canonical_url=real)]
        self.assertEqual(decide(aid, c), 'URL_COLLISION')
        # bài KHÁC cũng khai cùng permalink -> va chạm
        op = self.root / self.row(other)['output_path']
        text = op.read_text(encoding='utf-8')
        R.atomic_write(op, M.replace_permalink(text, M.front_permalink(text), real).encode('utf-8'))
        self.assertEqual(decide(aid), 'URL_COLLISION')
        R.atomic_write(op, text.encode('utf-8'))
        # registry dùng URL đó
        c = self.ctx()
        c.registry['BLG-99997'] = {'article_id': 'BLG-99997', 'old_url': real, 'new_url': '/x/'}
        self.assertEqual(decide(aid, c), 'URL_COLLISION')
        # thuộc baseline / registry / không PUBLISHED
        c = self.ctx()
        c.baseline[aid] = {'article_id': aid}
        self.assertEqual(decide(aid, c), 'IN_BASELINE')
        c = self.ctx()
        c.registry[aid] = {'article_id': aid, 'old_url': '/o/', 'new_url': '/n/'}
        self.assertEqual(decide(aid, c), 'IN_REGISTRY')
        c = self.ctx()
        c.by_id[aid] = dict(c.by_id[aid], status='REPAIR')
        self.assertEqual(decide(aid, c), 'NOT_PUBLISHED')
        # lease / draft
        reg = self.root / 'data/state/writer-claims.json'
        reg.write_text(json.dumps({'schema_version': '2', 'updated_at': None, 'leases': {
            'W1': {'ids': [aid], 'session': 's-t', 'epoch': 1, 'expires_at': '2999-01-01T00:00:00+00:00'}}}))
        self.assertEqual(decide(aid), 'LEASED')
        reg.write_text(json.dumps({'schema_version': '2', 'updated_at': None, 'leases': {}}))
        draft = self.root / '_drafts' / ('2026-10-25-%s.md' % self.row(aid)['slug'])
        draft.write_text('---\ntitle: x\n---\n')
        self.assertEqual(decide(aid), 'HAS_DRAFT')
        draft.unlink()
        # bài đổi một byte sau QA -> evidence không còn nguyên vẹn (phải reattest trước)
        p = self.root / self.row(aid)['output_path']
        R.atomic_write(p, p.read_bytes() + b'\n')
        self.assertEqual(decide(aid), 'EVIDENCE_NOT_INTACT')

    def retarget(self, aid, expected, canonical):
        R.atomic_write(self.root / S.MATRIX_REL,
                       M.matrix_bytes_with(self.root, {aid: dict(self.row(aid), expected_url=expected, canonical_url=canonical)}))
        self.seal(aid)

    def expect_code(self, ctx, aid):
        try:
            S.derive(ctx, aid)
        except R.Refuse as e:
            return e.code
        return 'ELIGIBLE'

    def make_defect_info(self, aid):
        row = self.row(aid)
        return M.front_permalink((self.root / row['output_path']).read_text(encoding='utf-8')), row['expected_url']

    def test_04_slug_must_be_in_permalink(self):
        aid = list(self.defects(1))[0]
        c = self.ctx()
        c.by_id[aid] = dict(c.by_id[aid], slug='slug-khong-co-trong-url')
        self.assertEqual(self.expect_code(c, aid), 'BAD_URL_SHAPE')


class TestApply(SyncBase):

    def test_01_apply_changes_only_matrix_cols_and_evidence(self):
        defects = self.defects(2)
        ids = list(defects)
        m = self.manifest(ids)
        before = tree_hashes(self.root, WATCH)
        olds = {a: self.row(a) for a in ids}
        posts = {a: (self.root / olds[a]['output_path']).read_bytes() for a in ids}
        old_ev = {a: self.evidence(a) for a in ids}
        rep = self.apply(m, ids)
        self.assertEqual(sorted(rep['written']), sorted(ids))
        after = tree_hashes(self.root, WATCH)
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertEqual(changed, {'data/content-matrix.csv'} | {'data/qa/%s.json' % a for a in ids},
                         'chi matrix + evidence duoc doi; bai/redirects/registry/_data giu nguyen')
        for a in ids:
            row, real = self.row(a), defects[a][0]
            self.assertEqual((row['expected_url'], row['canonical_url']), (real, real))
            for k in olds[a]:
                if k not in S.SYNC_COLS:
                    self.assertEqual(row[k], olds[a][k], k)
            self.assertEqual((self.root / row['output_path']).read_bytes(), posts[a])
            ev = self.evidence(a)
            rv = ev['revision']
            self.assertEqual((rv['kind'], rv['old_matrix_url'], rv['new_matrix_url'], rv['permalink']), (S.KIND, defects[a][1], real, real))
            self.assertEqual((ev['content_sha256'], ev['matrix_row_sha256']), (sha(posts[a]), A.fingerprint(row)))
            self.assertTrue(rv['approval_ref'])
            self.assertEqual(rv['previous_matrix_row_sha256'], old_ev[a]['matrix_row_sha256'])
            for k in ('scored_at', 'published_at'):
                self.assertEqual(ev.get(k), old_ev[a].get(k), k)
            self.assertNotIn('history', rv)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        self.assertEqual(S.verify_backup(self.ctx(), backup, rescore=True), [])
        self.assertEqual(SR.policy_errors(matrix_rows(self.fx), self.root), [])

    def test_02_history_chain_keeps_earlier_revision(self):
        aid = list(self.defects(1))[0]
        ev_p = self.root / 'data/qa' / (aid + '.json')
        ev = self.evidence(aid)
        ev['revision'] = {'kind': 'content-revision', 'batch_id': 'cu'}
        ev['reattestation'] = {'note': 'giu'}
        ev_p.write_text(R.evidence_text(ev), encoding='utf-8')
        self.apply(self.manifest([aid]), [aid])
        new = self.evidence(aid)
        self.assertEqual(new['revision']['kind'], S.KIND)
        self.assertEqual(new['revision']['history'], [{'kind': 'content-revision', 'batch_id': 'cu'}])
        self.assertEqual(new['reattestation'], {'note': 'giu'})

    def test_03_dry_run_limits_and_approval(self):
        ids = list(self.defects(2))
        m = self.manifest(ids)
        guard = tree_hashes(self.root, WATCH)
        rep = self.apply(m, ids, dry_run=True)
        self.assertEqual(sorted(rep['would_write']), sorted(ids))
        self.assertEqual(tree_hashes(self.root, WATCH), guard)
        self.assertFalse((self.root / S.BACKUP_DIR).exists())
        for kw, code in (({'approval': ''}, 'NO_APPROVAL'),):
            with self.assertRaises(R.Refuse) as e:
                S.apply_batch(self.ctx(approval=kw['approval']), m, ids)
            self.assertEqual(e.exception.code, code)
        with self.assertRaises(R.Refuse) as e:
            S.apply_batch(self.ctx(), m, ['BLG-%05d' % i for i in range(1, S.MAX_BATCH + 2)])
        self.assertEqual(e.exception.code, 'BATCH_TOO_LARGE')
        with self.assertRaises(R.Refuse) as e:
            S.apply_batch(self.ctx(), m, [])
        self.assertEqual(e.exception.code, 'NO_IDS')
        with self.assertRaises(R.Refuse) as e:
            S.apply_batch(self.ctx(batch='../x'), m, ids)
        self.assertEqual(e.exception.code, 'BAD_BATCH_ID')
        with self.assertRaises(R.Refuse) as e:
            S.apply_batch(self.ctx(), dict(m, schema='khac'), ids)
        self.assertEqual(e.exception.code, 'BAD_MANIFEST')
        with self.assertRaises(R.Refuse) as e:
            S.apply_batch(self.ctx(), dict(m, head_bound=False), ids)
        self.assertEqual(e.exception.code, 'MANIFEST_NOT_HEAD_BOUND')

    def test_04_stale_manifest_cannot_be_forced(self):
        ids = list(self.defects(2))
        m = self.manifest(ids)
        a, b = ids
        with self.assertRaises(R.Refuse) as e:                      # ID không có trong manifest
            S.apply_batch(self.ctx(), m, ['BLG-99999'])
        self.assertEqual(e.exception.code, 'NOT_ELIGIBLE')
        pa = self.root / self.row(a)['output_path']
        R.atomic_write(pa, pa.read_bytes() + b'\n')                  # bài đổi sau plan
        with self.assertRaises(R.Refuse) as e:
            self.apply(m, [a])
        self.assertIn(e.exception.code, ('POST_CHANGED_SINCE_PLAN', 'EVIDENCE_NOT_INTACT'))
        rep = self.apply(m, [a, b], skip_ineligible=True)            # --skip-ineligible chỉ bỏ ID lỗi, vẫn ghi ID tốt
        self.assertEqual(rep['written'], [b])
        self.assertEqual([x['id'] for x in rep['skipped_ineligible']], [a])
        m2 = dict(m, scorer_code_sha256='0' * 64)
        with self.assertRaises(R.Refuse) as e:
            self.apply(m2, [b], batch='test-sync-2')
        self.assertEqual(e.exception.code, 'SCORER_CHANGED_SINCE_PLAN')

    def test_05_second_apply_is_refused_not_duplicated(self):
        ids = list(self.defects(1))
        m = self.manifest(ids)
        self.apply(m, ids)
        with self.assertRaises(R.Refuse) as e:
            self.apply(m, ids, batch='test-sync-2')
        self.assertEqual(e.exception.code, 'NO_DRIFT')
        rep = self.apply(m, ids, batch='test-sync-3', skip_ineligible=True)
        self.assertEqual((rep['written'], [x['code'] for x in rep['skipped_ineligible']]), ([], ['NO_DRIFT']))
        self.assertFalse((self.root / S.BACKUP_DIR / 'test-sync-3.json').exists())

    def test_06_failed_apply_restores_every_byte(self):
        ids = list(self.defects(2))
        m = self.manifest(ids)
        guard = tree_hashes(self.root, WATCH)
        real_write = S.atomic_write
        calls = {'n': 0}

        def flaky(path, data):
            if str(path).endswith('data/content-matrix.csv') and calls['n'] == 0:
                calls['n'] += 1
                raise OSError('loi ghi matrix gia lap')
            return real_write(path, data)

        S.atomic_write = flaky
        try:
            with self.assertRaises(OSError):
                self.apply(m, ids)
        finally:
            S.atomic_write = real_write
        self.assertEqual(tree_hashes(self.root, WATCH), guard)
        self.assertFalse((self.root / S.BACKUP_DIR / 'test-sync.json').exists(), 'sao luu chi xoa khi moi thu da ve byte cu')
        self.assertEqual(len(self.apply(m, ids)['written']), 2)       # chạy lại sau lỗi vẫn được

    def test_07_failed_verification_rolls_back(self):
        ids = list(self.defects(1))
        m = self.manifest(ids)
        guard = tree_hashes(self.root, WATCH)
        real_verify = S.verify_backup
        S.verify_backup = lambda ctx, backup, rescore=True: ['gia lap loi verify']
        try:
            with self.assertRaises(R.Refuse) as e:
                self.apply(m, ids)
        finally:
            S.verify_backup = real_verify
        self.assertEqual(e.exception.code, 'POST_VERIFY_FAILED')
        self.assertEqual(tree_hashes(self.root, WATCH), guard)


class TestVerifyRollback(SyncBase):

    def applied(self, n=2):
        ids = list(self.defects(n))
        m = self.manifest(ids)
        rep = self.apply(m, ids)
        return ids, json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))

    def test_01_verify_catches_hand_edits(self):
        ids, backup = self.applied(1)
        a = ids[0]
        self.assertEqual(S.verify_backup(self.ctx(), backup), [])
        ev_p = self.root / 'data/qa' / (a + '.json')
        good_ev = ev_p.read_bytes()
        bad = json.loads(good_ev)
        bad['quality'] = 100 if bad['quality'] != 100 else 99
        ev_p.write_text(R.evidence_text(bad), encoding='utf-8')
        self.assertTrue(S.verify_backup(self.ctx(), backup))
        ev_p.write_bytes(good_ev)
        post_p = self.root / self.row(a)['output_path']
        good_post = post_p.read_bytes()
        R.atomic_write(post_p, good_post + b'\n')
        self.assertTrue(any('bai khac' in p for p in S.verify_backup(self.ctx(), backup)))
        post_p.write_bytes(good_post)
        mx = self.root / S.MATRIX_REL
        good_mx = mx.read_bytes()
        title = self.row(a)['title'].encode('utf-8')
        R.atomic_write(mx, good_mx.replace(title, title + b' x', 1))          # sửa tay một cột KHÁC của hàng
        self.assertTrue(S.verify_backup(self.ctx(), backup))
        mx.write_bytes(good_mx)
        self.assertEqual(S.verify_backup(self.ctx(), backup), [])

    def test_02_rollback_is_byte_exact(self):
        ids = list(self.defects(2))
        before = tree_hashes(self.root, WATCH)
        m = self.manifest(ids)
        rep = self.apply(m, ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        self.assertNotEqual(tree_hashes(self.root, WATCH), before)
        dry = S.rollback_backup(self.root, backup, dry_run=True)
        self.assertEqual(sorted(dry['restored']), sorted(ids))
        self.assertNotEqual(tree_hashes(self.root, WATCH), before, 'dry-run khong ghi')
        out = S.rollback_backup(self.root, backup)
        self.assertEqual((sorted(out['restored']), out['skipped_changed_since_apply']), (sorted(ids), []))
        self.assertEqual(tree_hashes(self.root, WATCH), before)
        again = S.rollback_backup(self.root, backup)
        self.assertEqual((again['restored'], again['skipped_changed_since_apply']), ([], []))

    def test_03_rollback_does_not_overwrite_later_changes(self):
        ids, backup = self.applied(2)
        a, b = ids
        pa = self.root / 'data/qa' / (a + '.json')
        ev = json.loads(pa.read_text(encoding='utf-8'))
        ev['note_nguoi_khac'] = 'sua sau apply'
        pa.write_text(R.evidence_text(ev), encoding='utf-8')
        keep = pa.read_bytes()
        out = S.rollback_backup(self.root, backup)
        self.assertEqual((out['restored'], out['skipped_changed_since_apply']), ([b], [a]))
        self.assertEqual(pa.read_bytes(), keep)
        self.assertEqual(self.row(b)['expected_url'], backup['entries'][b]['old_row']['expected_url'])
        self.assertEqual(self.row(a)['expected_url'], backup['entries'][a]['new_row']['expected_url'])
        sub = S.rollback_backup(self.root, backup, ids={b})
        self.assertEqual(sub['restored'], [])
        with self.assertRaises(R.Refuse) as e:
            S.rollback_backup(self.root, backup, ids={'BLG-99999'})
        self.assertEqual(e.exception.code, 'UNKNOWN_IDS')

    def test_04_rollback_completes_after_interruption(self):
        ids, backup = self.applied(2)
        a = ids[0]
        old_ev = backup['entries'][a]['old_evidence_text'].encode('utf-8')
        R.atomic_write(self.root / 'data/qa' / (a + '.json'), old_ev)      # lần rollback trước chỉ kịp khôi phục evidence
        out = S.rollback_backup(self.root, backup)
        self.assertEqual((sorted(out['restored']), out['skipped_changed_since_apply']), (sorted(ids), []))
        for x in ids:
            self.assertEqual(self.row(x), backup['entries'][x]['old_row'])
            self.assertEqual(sha((self.root / 'data/qa' / (x + '.json')).read_bytes()), backup['entries'][x]['old_evidence_sha256'])

    def test_05_rollback_refuses_when_post_changed(self):
        ids, backup = self.applied(1)
        a = ids[0]
        post_p = self.root / self.row(a)['output_path']
        R.atomic_write(post_p, post_p.read_bytes() + b'\n')
        guard = tree_hashes(self.root, WATCH)
        with self.assertRaises(R.Refuse) as e:
            S.rollback_backup(self.root, backup)
        self.assertEqual(e.exception.code, 'POST_CHANGED_SINCE_APPLY')
        self.assertEqual(tree_hashes(self.root, WATCH), guard)

    def test_06_backup_shape_is_validated(self):
        ids, backup = self.applied(1)
        for mutate in (lambda b: b.update(schema='x'), lambda b: b.update(entries={}),
                       lambda b: b['entries'][ids[0]].update(post_path='README.md'),
                       lambda b: b['entries'][ids[0]].pop('old_evidence_text'),
                       lambda b: b['entries'][ids[0]]['new_row'].update(title='doi cot ngoai SYNC_COLS')):
            bad = json.loads(json.dumps(backup))
            mutate(bad)
            with self.assertRaises(R.Refuse) as e:
                S.check_backup_shape(bad)
            self.assertEqual(e.exception.code, 'BAD_BACKUP')


class TestGuards(SyncBase):
    """Mỗi rào của derive/prepare/apply/verify/rollback có một test đỏ khi rào bị gỡ (review độc lập 2026-10-26)."""

    def code(self, aid, ctx=None):
        try:
            S.derive(ctx or self.ctx(), aid)
        except R.Refuse as e:
            return e.code
        return 'ELIGIBLE'

    def write_ev(self, aid, ev):
        (self.root / 'data/qa' / (aid + '.json')).write_text(R.evidence_text(ev), encoding='utf-8')

    def patch_scores(self, aid, mutate_after):
        """Bọc scorer: đầu ra cho HÀNG MỚI (URL = permalink thật, không còn dạng /YYYY/MM/DD/) của `aid` bị `mutate_after` sửa."""
        real = R.score_candidate

        def fake(ctx, row, post):
            out = real(ctx, row, post)
            if row['id'] == aid and S.real_shapes(row['expected_url']) == ():
                out = mutate_after(dict(out, checks=dict(out.get('checks', {}))))
            return out
        R.score_candidate = fake
        self.addCleanup(setattr, R, 'score_candidate', real)

    def test_01_evidence_must_be_bound_and_pass(self):
        aid = list(self.defects(1))[0]
        good = self.evidence(aid)
        self.write_ev(aid, dict(good, matrix_row_sha256='0' * 64))
        self.assertEqual(self.code(aid), 'EVIDENCE_NOT_INTACT')
        self.write_ev(aid, dict(good, result='FAIL'))
        self.assertEqual(self.code(aid), 'EVIDENCE_NOT_INTACT')
        self.write_ev(aid, dict(good, source_path='_posts/khac.md'))
        self.assertEqual(self.code(aid), 'EVIDENCE_NOT_INTACT')
        self.write_ev(aid, good)
        self.assertEqual(self.code(aid), 'ELIGIBLE')

    def setUp(self):
        super().setUp()
        self._real = R.score_candidate
        self.addCleanup(setattr, R, 'score_candidate', self._real)

    def test_02_fresh_score_below_floor(self):
        aid = list(self.defects(1))[0]
        for mutate in (lambda o: dict(o, quality=74), lambda o: dict(o, seo=69), lambda o: dict(o, business_fact='FAIL'),
                       lambda o: dict(o, critical_failure=True), lambda o: dict(o, legal='FAIL')):
            R.score_candidate = self._real
            self.patch_scores(aid, mutate)
            self.assertEqual(self.code(aid), 'FRESH_QA_NOT_ELIGIBLE')

    def test_03_regression_of_any_passing_check(self):
        aid = list(self.defects(1))[0]
        row = self.row(aid)
        before = self._real(self.ctx(), row, (self.root / row['output_path']).read_bytes())
        k = next(k for k, v in sorted(before['checks'].items()) if v and k != 'permalink_canonical')

        def flip(o):
            o['checks'][k] = False
            return o
        self.patch_scores(aid, flip)
        self.assertEqual(self.code(aid), 'REGRESSION')
        if before['quality'] > 75:
            R.score_candidate = self._real
            self.patch_scores(aid, lambda o: dict(o, quality=before['quality'] - 1))
            self.assertEqual(self.code(aid), 'REGRESSION')

    def test_04_permalink_must_be_canonical_and_single(self):
        aid = list(self.defects(1))[0]
        self.patch_scores(aid, lambda o: dict(o, checks=dict(o['checks'], permalink_canonical=False)))
        self.assertEqual(self.code(aid), 'PERMALINK_NOT_CANONICAL')
        R.score_candidate = self._real
        self.assertEqual(self.code(aid), 'ELIGIBLE')
        # khoá permalink thứ hai (có khoảng trắng cuối: front_permalink bỏ qua, YAML/Jekyll lấy khoá sau) -> từ chối, không đoán
        p = self.root / self.row(aid)['output_path']
        text = p.read_text(encoding='utf-8')
        end = text.index('\n---\n', 4)
        R.atomic_write(p, (text[:end] + '\npermalink: /xe-may/trang-khac-han/ ' + text[end:]).encode('utf-8'))
        self.seal(aid)
        self.assertEqual(self.code(aid), 'PERMALINK_LINE')

    def test_05_batch_id_is_never_overwritten(self):
        a, b = list(self.defects(2))
        m = self.manifest([a, b])
        rep = self.apply(m, [a], batch='dup')
        first = (self.root / rep['backup']).read_bytes()
        guard = tree_hashes(self.root, WATCH)
        with self.assertRaises(R.Refuse) as e:
            self.apply(m, [b], batch='dup')
        self.assertEqual(e.exception.code, 'BATCH_EXISTS')
        self.assertEqual((self.root / rep['backup']).read_bytes(), first)
        self.assertEqual(tree_hashes(self.root, WATCH), guard)

    def test_06_inputs_changed_since_plan(self):
        a, b, c = list(self.defects(3))
        m = self.manifest([a, b, c])
        ev = self.evidence(a)
        ev['ghi_chu_moi'] = 'evidence doi sau plan'                 # vẫn nguyên vẹn (hash bài/hàng khớp) nhưng khác bản đã plan
        self.write_ev(a, ev)
        pb = self.root / self.row(b)['output_path']
        R.atomic_write(pb, pb.read_bytes() + b'\n')
        self.seal(b)                                                   # bài đổi + evidence chấm lại: derive vẫn qua, prepare phải chặn
        m2 = json.loads(json.dumps(m))
        m2['entries'][c]['after'] = dict(m2['entries'][c]['after'], quality=1)
        for aid, man, code in ((a, m, 'EVIDENCE_CHANGED_SINCE_PLAN'), (b, m, 'POST_CHANGED_SINCE_PLAN'),
                               (c, m2, 'INPUT_CHANGED_SINCE_PLAN')):
            guard = tree_hashes(self.root, WATCH)
            with self.assertRaises(R.Refuse) as e:
                self.apply(man, [aid], batch='chg-' + aid)
            self.assertEqual(e.exception.code, code, aid)
            self.assertEqual(tree_hashes(self.root, WATCH), guard)

    def forged(self, aid, backup, change):
        """Sửa evidence đã ghi VÀ cập nhật new_evidence_sha256 trong sao lưu cho khớp: verify phải bắt bằng kiểm sâu, không nhờ sha."""
        p = self.root / 'data/qa' / (aid + '.json')
        ev = json.loads(p.read_text(encoding='utf-8'))
        change(ev)
        raw = R.evidence_text(ev).encode('utf-8')
        p.write_bytes(raw)
        b = json.loads(json.dumps(backup))
        b['entries'][aid]['new_evidence_sha256'] = sha(raw)
        return b

    def test_07_verify_deep_checks_with_consistent_sha(self):
        ids = list(self.defects(1))
        a = ids[0]
        rep = self.apply(self.manifest(ids), ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        good = (self.root / 'data/qa' / (a + '.json')).read_bytes()
        cases = (('rescore', lambda ev: ev.update(seo=ev['seo'] - 1)),
                 ('provenance', lambda ev: ev['revision'].update(approval_ref='')),
                 ('provenance', lambda ev: ev['revision'].update(old_matrix_url='/khac/')),
                 ('nguong', lambda ev: ev.update(quality=10)),
                 ('permalink_canonical', lambda ev: ev['checks'].update(permalink_canonical=False)),
                 ('lich su', lambda ev: ev.update(scored_at='2099-01-01T00:00:00+00:00')))
        for want, change in cases:
            b = self.forged(a, backup, change)
            problems = S.verify_backup(self.ctx(), b, rescore=True)
            self.assertTrue(problems, want)
            (self.root / 'data/qa' / (a + '.json')).write_bytes(good)
        self.assertEqual(S.verify_backup(self.ctx(), backup, rescore=True), [])

    def test_08_cli_verify_exit_code_drives_the_gate(self):
        import subprocess
        ids = list(self.defects(1))
        rep = self.apply(self.manifest(ids), ids)
        tool = self.root / 'scripts/factory/sync-matrix-urls.py'
        run = lambda: subprocess.run([sys.executable, str(tool), 'verify', '--backup', rep['backup'], '--no-rescore'],
                                     cwd=str(self.root), capture_output=True, text=True)
        r = run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        p = self.root / 'data/qa' / (ids[0] + '.json')
        p.write_bytes(p.read_bytes() + b' ')
        r = run()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertFalse(json.loads(r.stdout)['ok'])

    def test_09_backup_rows_are_anchored(self):
        ids = list(self.defects(1))
        a = ids[0]
        rep = self.apply(self.manifest(ids), ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        guard = tree_hashes(self.root, WATCH)
        for mutate in (lambda e: e['old_row'].update(expected_url='/fake/url/', canonical_url='/fake/url/'),
                       lambda e: e.update(old_matrix_url='/fake/url/'),
                       lambda e: e['new_row'].update(expected_url='/x/', canonical_url='/x/'),
                       lambda e: e.update(post_sha256='0' * 64),
                       lambda e: e.update(old_evidence_text=e['old_evidence_text'] + ' ')):
            bad = json.loads(json.dumps(backup))
            mutate(bad['entries'][a])
            with self.assertRaises(R.Refuse) as e:
                S.rollback_backup(self.root, bad)
            self.assertEqual(e.exception.code, 'BAD_BACKUP')
            with self.assertRaises(R.Refuse):
                S.verify_backup(self.ctx(), bad)
        self.assertEqual(tree_hashes(self.root, WATCH), guard, 'sao luu bi sua tay: khong ghi gi')

    def test_10_abort_after_unrelated_matrix_write_is_not_partial(self):
        ids = list(self.defects(2))
        m = self.manifest(ids)
        mx = self.root / S.MATRIX_REL
        other = next(r for r in matrix_rows(self.fx) if r['id'] not in ids and r['status'] == 'PUBLISHED')
        real_write = S.atomic_write
        last = 'data/qa/%s.json' % sorted(ids)[-1]

        def racing(path, data):
            real_write(path, data)
            if str(path).endswith(last):                              # một tiến trình khác sửa hàng KHÁC đúng lúc này
                real_write(mx, mx.read_bytes().replace(other['title'].encode('utf-8'), other['title'].encode('utf-8') + b' (sua)', 1))
        S.atomic_write = racing
        try:
            with self.assertRaises(R.Refuse) as e:
                self.apply(m, ids)
        finally:
            S.atomic_write = real_write
        self.assertEqual(e.exception.code, 'FILES_CHANGED_DURING_APPLY')
        self.assertFalse((self.root / S.BACKUP_DIR / 'test-sync.json').exists(), 'khong giu sao luu khi moi evidence da ve byte cu')
        for aid in ids:
            self.assertEqual(self.evidence(aid).get('revision', {}).get('kind'), None)
        self.assertIn((other['title'] + ' (sua)').encode('utf-8'), mx.read_bytes(), 'khong de thay doi cua tien trinh khac')

    def test_11_quality_gate_verifies_matrix_sync_backups(self):
        wf = (pathlib.Path(__file__).resolve().parents[3] / '.github/workflows/quality-gate.yml').read_text(encoding='utf-8')
        self.assertIn('reports/qa-audit/matrix-sync/*.json)', wf)
        self.assertIn('python3 scripts/factory/sync-matrix-urls.py verify --backup "$f"', wf)


if __name__ == '__main__':
    unittest.main()
