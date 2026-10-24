#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test migrate-slug-urls.py trên bản sao hermetic của repo (FxTestCase) — OFFLINE (Issue #77).

Phủ: chỉ di trú bài PUBLISHED có evidence NGUYÊN VẸN, trong danh sách đóng băng; mọi ca khác bị TỪ CHỐI (không có cờ ép):
evidence lệch hash, lease, draft, slug/URL/đường dẫn trùng, không PUBLISHED, ngoài baseline; chỉ đổi ĐÚNG dòng permalink; ghi
nhất quán bài/evidence/matrix(4 cột)/registry/trang chuyển hướng (khớp byte với registry); provenance + chuỗi lịch sử, mốc lịch sử
giữ nguyên; manifest lỗi thời không ép được; lô <= 50, cần --approval-ref; chạy lặp là no-op; dry-run không ghi; rollback
byte-exact và không đè thay đổi của người khác; apply lỗi giữa chừng tự trả mọi thứ về byte cũ; dữ liệu phái sinh theo URL.

Chạy: python3 scripts/factory/tests/test_migrate_slug_urls.py (từ gốc repository)
"""
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / 'migrate-slug-urls.py'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from test_qa_modes import FxTestCase, matrix_rows  # noqa: E402

spec = importlib.util.spec_from_file_location('migrate_under_test', SCRIPT)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
R, A, SR = M.R, M.A, M.SR


def sha(b):
    return hashlib.sha256(b).hexdigest()


def tree_hashes(root, rels, skip=()):
    out = {}
    for rel in rels:
        p = pathlib.Path(root) / rel
        files = sorted(f for f in p.rglob('*') if f.is_file()) if p.is_dir() else ([p] if p.is_file() else [])
        for f in files:
            r = str(f.relative_to(root))
            if r not in skip:
                out[r] = sha(f.read_bytes())
    return out


WATCH = ('_posts', 'data/qa', 'data/content-matrix.csv', 'redirects', 'reports/factory/seo-master/slug-redirect-registry.csv',
         '_data')


class MigrateBase(FxTestCase):

    def setUp(self):
        super().setUp()
        self._cwd = os.getcwd()
        self.addCleanup(os.chdir, self._cwd)
        self.root = pathlib.Path(self.fx)
        shutil.rmtree(self.root / M.BACKUP_DIR, ignore_errors=True)
        self.focus = set()

    def ctx(self, approval='owner authorization (test)', batch='test-batch'):
        c = M.make_ctx(self.root, approval, batch)
        keep = self.focus
        c.rows = c.rows[:250] + [r for r in c.rows[250:] if r['id'] in keep]        # chấm nhanh: corpus thu gọn
        return c

    def intact_candidates(self, n):
        """n ID baseline còn evidence nguyên vẹn VÀ derive() thành công (đủ điều kiện)."""
        c = M.make_ctx(self.root, 'x', 'probe')
        out = []
        for aid, b in sorted(c.baseline.items()):
            if b['qa_evidence_intact'] != 'yes':
                continue
            self.focus.add(aid)
            try:
                M.derive(self.ctx(), aid)
            except R.Refuse:
                self.focus.discard(aid)
                continue
            out.append(aid)
            if len(out) == n:
                return out
        self.skipTest('fixture khong du bai du dieu kien')

    def manifest(self, ids):
        m = M.make_plan(self.ctx(), ids)
        self.assertEqual(sorted(m['eligible']), sorted(ids), m['excluded'])
        return m

    def row(self, aid):
        return next(r for r in matrix_rows(self.fx) if r['id'] == aid)

    def evidence(self, aid):
        return json.loads((self.root / 'data/qa' / (aid + '.json')).read_text(encoding='utf-8'))

    def apply(self, manifest, ids, **kw):
        return M.apply_batch(self.ctx(batch=kw.pop('batch', 'test-batch')), manifest, ids, **kw)


class TestHelpers(unittest.TestCase):
    FRONT = '---\ntitle: "T"\npermalink: /a/b/\narticle_id: BLG-1\n---\n'

    def test_replace_permalink_only_that_line(self):
        t = self.FRONT + 'Thân bài có permalink: /a/b/ trong văn bản.\n'
        out = M.replace_permalink(t, '/a/b/', '/a/c/')
        self.assertEqual(out, t.replace('permalink: /a/b/\n', 'permalink: /a/c/\n', 1))
        M.check_only_permalink_changed(t, out, '/a/b/', '/a/c/')
        with self.assertRaises(R.Refuse):
            M.replace_permalink(t, '/a/x/', '/a/c/')
        with self.assertRaises(R.Refuse):
            M.replace_permalink('khong front matter', '/a/b/', '/a/c/')
        with self.assertRaises(R.Refuse):
            M.replace_permalink(self.FRONT.replace('article_id', 'permalink: /a/b/\narticle_id'), '/a/b/', '/a/c/')

    def test_check_only_permalink_changed_catches_other_edits(self):
        t = self.FRONT + 'Thân\n'
        for bad in (t.replace('permalink: /a/b/', 'permalink: /a/c/').replace('Thân', 'Thân sửa'),
                    t.replace('permalink: /a/b/', 'permalink: /a/c/').replace('title: "T"', 'title: "U"')):
            with self.assertRaises(R.Refuse) as c:
                M.check_only_permalink_changed(t, bad, '/a/b/', '/a/c/')
            self.assertEqual(c.exception.code, 'POST_DIFF_NOT_PERMALINK_ONLY')

    def test_rewrite_is_token_exact(self):
        mp = {'/x/2026/10/07/at-xe/': '/x/2026/10/07/dat-xe/'}
        self.assertEqual(M._rewrite('a /x/2026/10/07/at-xe/ b /x/2026/10/07/at-xe-khac/', mp),
                         'a /x/2026/10/07/dat-xe/ b /x/2026/10/07/at-xe-khac/')
        self.assertEqual(M._rewrite('khong doi', {}), 'khong doi')


class TestPlan(MigrateBase):

    def test_01_plan_classifies_and_writes_nothing(self):
        good = self.intact_candidates(2)
        base = M.make_ctx(self.root, 'x', 'p').baseline
        drifted = next(a for a, b in sorted(base.items()) if b['qa_evidence_intact'] != 'yes')
        guard = tree_hashes(self.root, WATCH)
        for a in good + [drifted]:
            self.focus.add(a)
        m = M.make_plan(self.ctx(), good + [drifted, 'BLG-00001'])
        self.assertEqual(sorted(m['eligible']), sorted(good))
        self.assertEqual(m['entries'][drifted]['decision'], 'EVIDENCE_NOT_INTACT')
        self.assertEqual(m['entries']['BLG-00001']['decision'], 'NOT_IN_BASELINE')
        e = m['entries'][good[0]]
        self.assertEqual(e['decision'], M.ELIGIBLE)
        self.assertNotEqual(e['old_url'], e['new_url'])
        self.assertNotEqual(e['base_post_sha256'], e['new_post_sha256'])
        self.assertGreaterEqual(e['after']['quality'], e['before_scores']['quality'])
        self.assertTrue(m['head_bound'])
        self.assertEqual(tree_hashes(self.root, WATCH), guard)

    def test_02_refusals_are_specific(self):
        good = self.intact_candidates(1)[0]
        c = self.ctx()
        row = self.row(good)
        for aid in (good,):
            self.focus.add(aid)
        # lease
        reg = self.root / 'data/state/writer-claims.json'
        reg.write_text(json.dumps({'schema_version': '2', 'updated_at': None, 'leases': {
            'W1': {'ids': [good], 'session': 's-t', 'epoch': 1, 'expires_at': '2999-01-01T00:00:00+00:00'}}}))
        with self.assertRaises(R.Refuse) as e:
            M.derive(self.ctx(), good)
        self.assertEqual(e.exception.code, 'LEASED')
        reg.write_text(json.dumps({'schema_version': '2', 'updated_at': None, 'leases': {}}))
        # draft cùng slug MỚI
        new_slug = M.slugkit.slugify(row['title'])
        draft = self.root / '_drafts' / ('2026-10-24-%s.md' % new_slug)
        draft.write_text('---\ntitle: x\n---\n')
        with self.assertRaises(R.Refuse) as e:
            M.derive(self.ctx(), good)
        self.assertEqual(e.exception.code, 'HAS_DRAFT')
        draft.unlink()
        # slug mới trùng hàng khác / URL mới trùng / tệp đích đã tồn tại
        c = self.ctx()
        other = dict(c.rows[0], id='BLG-99998', slug=new_slug)
        c.rows = c.rows + [other]
        with self.assertRaises(R.Refuse) as e:
            M.derive(c, good)
        self.assertEqual(e.exception.code, 'SLUG_COLLISION')
        c = self.ctx()
        new_path = row['output_path'].replace(row['slug'], new_slug)
        (self.root / new_path).write_text('x')
        with self.assertRaises(R.Refuse) as e:
            M.derive(c, good)
        self.assertEqual(e.exception.code, 'PATH_EXISTS')
        (self.root / new_path).unlink()
        # bài đổi một byte sau QA -> evidence không còn nguyên vẹn
        p = self.root / row['output_path']
        R.atomic_write(p, p.read_bytes() + b'\n')
        with self.assertRaises(R.Refuse) as e:
            M.derive(self.ctx(), good)
        self.assertEqual(e.exception.code, 'EVIDENCE_NOT_INTACT')

    def test_03_not_published_and_already_migrated(self):
        good = self.intact_candidates(1)[0]
        c = self.ctx()
        c.by_id[good] = dict(c.by_id[good], status='REPAIR')
        with self.assertRaises(R.Refuse) as e:
            M.derive(c, good)
        self.assertEqual(e.exception.code, 'NOT_PUBLISHED')
        c = self.ctx()
        c.registry[good] = {'article_id': good}
        with self.assertRaises(R.Refuse) as e:
            M.derive(c, good)
        self.assertEqual(e.exception.code, 'ALREADY_MIGRATED')


class TestApply(MigrateBase):

    def test_01_apply_writes_everything_consistently_and_verifies(self):
        ids = self.intact_candidates(2)
        m = self.manifest(ids)
        before = tree_hashes(self.root, WATCH)
        olds = {a: self.row(a) for a in ids}
        old_posts = {a: (self.root / olds[a]['output_path']).read_bytes() for a in ids}
        old_ev = {a: self.evidence(a) for a in ids}
        rep = self.apply(m, ids)
        self.assertEqual(sorted(rep['written']), sorted(ids))
        after = tree_hashes(self.root, WATCH)
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        expect = {'data/content-matrix.csv', SR.REGISTRY_REL}
        for a in ids:
            expect |= {olds[a]['output_path'], self.row(a)['output_path'], 'data/qa/%s.json' % a, SR.stub_relpath(a)}
        self.assertEqual(changed, expect, 'chi dung cac tep nay duoc doi')
        for a in ids:
            row = self.row(a)
            self.assertEqual(row['slug'], M.slugkit.slugify(row['title']))
            self.assertNotEqual(row['slug'], olds[a]['slug'])
            for k in olds[a]:
                if k not in M.URL_COLS:
                    self.assertEqual(row[k], olds[a][k], k)
            new_post = (self.root / row['output_path']).read_bytes()
            self.assertFalse((self.root / olds[a]['output_path']).exists())
            old_url = M.front_permalink(old_posts[a].decode())
            self.assertEqual(new_post.decode(), old_posts[a].decode().replace('permalink: %s\n' % old_url,
                                                                               'permalink: %s\n' % row['expected_url'], 1))
            ev = self.evidence(a)
            rv = ev['revision']
            self.assertEqual((ev['content_sha256'], ev['source_path']), (sha(new_post), row['output_path']))
            self.assertEqual(ev['matrix_row_sha256'], A.fingerprint(row))
            self.assertEqual((rv['kind'], rv['old_url'], rv['new_url']), (M.KIND, old_url, row['expected_url']))
            self.assertTrue(rv['approval_ref'])
            for k in ('scored_at', 'published_at'):
                self.assertEqual(ev.get(k), old_ev[a].get(k), k)
            self.assertIn('HTTP 200 + meta refresh', rv['redirect'])
            self.assertNotIn('301', rv['redirect'].replace('khong phai HTTP 301', ''))
            stub = (self.root / SR.stub_relpath(a)).read_text(encoding='utf-8')
            self.assertIn('permalink: %s\n' % old_url, stub)
            self.assertIn('redirect_to: %s\n' % row['expected_url'], stub)
            self.assertIn('sitemap: false', stub)
        self.assertEqual(SR.source_errors(self.root, matrix_rows(self.fx)), [])
        self.assertEqual(SR.policy_errors(matrix_rows(self.fx), self.root), [])
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        self.assertEqual(M.verify_backup(self.ctx(), backup, rescore=True), [])

    def test_02_idempotent_dry_run_limits_and_approval(self):
        three = self.intact_candidates(3)
        ids, spare = three[:2], three[2]
        m = self.manifest(three)
        guard = tree_hashes(self.root, WATCH)
        rep = self.apply(m, ids, dry_run=True)
        self.assertEqual(sorted(rep['would_write']), sorted(ids))
        self.assertEqual(tree_hashes(self.root, WATCH), guard, 'dry-run khong ghi gi')
        with self.assertRaises(R.Refuse) as e:
            M.apply_batch(self.ctx(approval=''), m, ids)
        self.assertEqual(e.exception.code, 'NO_APPROVAL')
        with self.assertRaises(R.Refuse) as e:
            M.apply_batch(self.ctx(), m, ['BLG-%05d' % i for i in range(1, M.MAX_BATCH + 2)])
        self.assertEqual(e.exception.code, 'BATCH_TOO_LARGE')
        with self.assertRaises(R.Refuse) as e:
            M.apply_batch(self.ctx(), m, [])
        self.assertEqual(e.exception.code, 'NO_IDS')
        with self.assertRaises(R.Refuse) as e:
            M.apply_batch(self.ctx(batch='../x'), m, ids)
        self.assertEqual(e.exception.code, 'BAD_BATCH_ID')
        self.assertEqual(tree_hashes(self.root, WATCH), guard, 'moi tu choi deu khong ghi gi')
        self.apply(m, ids)
        done = tree_hashes(self.root, WATCH)
        rep2 = self.apply(m, ids, batch='test-batch-2')
        self.assertEqual(rep2.get('written', []), [])
        self.assertEqual(sorted(rep2['already_current']), sorted(ids))
        self.assertEqual(tree_hashes(self.root, WATCH), done, 'chay lai la no-op')
        with self.assertRaises(R.Refuse) as e:
            self.apply(m, [spare], batch='test-batch')       # trung ten sao luu cua lo truoc
        self.assertEqual(e.exception.code, 'BATCH_EXISTS')
        self.assertEqual(tree_hashes(self.root, WATCH), done)

    def test_03_stale_or_foreign_manifest_cannot_force(self):
        ids = self.intact_candidates(1)
        m = self.manifest(ids)
        bad = copy.deepcopy(m)
        bad['head_bound'] = False
        with self.assertRaises(R.Refuse) as e:
            self.apply(bad, ids)
        self.assertEqual(e.exception.code, 'MANIFEST_NOT_HEAD_BOUND')
        bad = copy.deepcopy(m)
        bad['scorer_code_sha256'] = '0' * 64
        with self.assertRaises(R.Refuse) as e:
            self.apply(bad, ids)
        self.assertEqual(e.exception.code, 'SCORER_CHANGED_SINCE_PLAN')
        bad = copy.deepcopy(m)
        bad['entries'][ids[0]]['new_post_sha256'] = '0' * 64
        with self.assertRaises(R.Refuse) as e:
            self.apply(bad, ids)
        self.assertEqual(e.exception.code, 'INPUT_CHANGED_SINCE_PLAN')
        bad = copy.deepcopy(m)
        bad['eligible'] = []
        with self.assertRaises(R.Refuse) as e:
            self.apply(bad, ids)
        self.assertEqual(e.exception.code, 'NOT_ELIGIBLE')
        row = self.row(ids[0])
        p = self.root / row['output_path']
        R.atomic_write(p, p.read_bytes() + b'\n')
        with self.assertRaises(R.Refuse) as e:
            self.apply(m, ids)
        self.assertEqual(e.exception.code, 'POST_CHANGED_SINCE_PLAN')

    def test_04_skip_ineligible_only_for_state_errors(self):
        ids = self.intact_candidates(2)
        m = self.manifest(ids)
        row = self.row(ids[1])
        p = self.root / row['output_path']
        R.atomic_write(p, p.read_bytes() + b'\n')
        rep = self.apply(m, ids, skip_ineligible=True)
        self.assertEqual(rep['written'], [ids[0]])
        self.assertEqual([x['id'] for x in rep['skipped_ineligible']], [ids[1]])


class TestRollback(MigrateBase):

    def test_01_rollback_restores_byte_exact_and_never_overwrites_foreign_changes(self):
        ids = self.intact_candidates(2)
        m = self.manifest(ids)
        before = tree_hashes(self.root, WATCH)
        rep = self.apply(m, ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        dry = M.rollback_backup(self.root, backup, dry_run=True)
        self.assertEqual(sorted(dry['restored']), sorted(ids))
        self.assertNotEqual(tree_hashes(self.root, WATCH), before)
        out = M.rollback_backup(self.root, backup)
        self.assertEqual(sorted(out['restored']), sorted(ids))
        self.assertEqual(tree_hashes(self.root, WATCH), before, 'rollback byte-exact (bai, evidence, matrix, registry, trang chuyen huong)')
        self.assertEqual(M.rollback_backup(self.root, backup)['restored'], [], 'rollback lan hai no-op')
        # áp dụng lại rồi sửa tay một bài: rollback phải TỪ CHỐI đè
        self.apply(m, ids, batch='test-batch-b')
        row = self.row(ids[0])
        p = self.root / row['output_path']
        R.atomic_write(p, p.read_bytes() + b'\nsua tay\n')
        backup2 = json.loads((self.root / M.BACKUP_DIR / 'test-batch-b.json').read_text(encoding='utf-8'))
        out = M.rollback_backup(self.root, backup2)
        self.assertEqual(out['skipped_changed_since_apply'], [ids[0]])
        self.assertEqual(out['restored'], [ids[1]])

    def test_02_failure_mid_apply_restores_everything(self):
        ids = self.intact_candidates(2)
        m = self.manifest(ids)
        before = tree_hashes(self.root, WATCH)
        real = M.atomic_write
        calls = {'n': 0}

        def flaky(path, data):
            calls['n'] += 1
            if calls['n'] == 6:                      # giữa ID thứ hai (sao lưu 1, ID1: 3 lần ghi, ID2: bài, evidence...)
                raise OSError('mat dien giua chung')
            return real(path, data)

        M.atomic_write = flaky
        try:
            with self.assertRaises(OSError):
                self.apply(m, ids)
        finally:
            M.atomic_write = real
        self.assertEqual(tree_hashes(self.root, WATCH), before, 'apply loi phai tra moi thu ve byte cu')
        self.assertFalse((self.root / M.BACKUP_DIR / 'test-batch.json').exists())

    def test_03_failure_after_shared_files_written_restores_them_too(self):
        ids = self.intact_candidates(1)
        m = self.manifest(ids)
        before = tree_hashes(self.root, WATCH)
        real = M.verify_backup

        def boom(ctx, backup, rescore=True):
            return ['gia lap: kiem tra sau ghi that bai']

        M.verify_backup = boom
        try:
            with self.assertRaises(R.Refuse) as e:
                self.apply(m, ids)
        finally:
            M.verify_backup = real
        self.assertEqual(e.exception.code, 'POST_VERIFY_FAILED')
        self.assertEqual(tree_hashes(self.root, WATCH), before)


class TestMatrixAndData(MigrateBase):

    def test_01_matrix_roundtrip_and_column_guard(self):
        raw = (self.root / M.MATRIX_REL).read_bytes()
        self.assertEqual(M.matrix_bytes_with(self.root, {}), raw)
        ids = self.intact_candidates(1)
        row = self.row(ids[0])
        bad = dict(row, title=row['title'] + ' x')
        with self.assertRaises(R.Refuse) as e:
            M.matrix_bytes_with(self.root, {ids[0]: bad})
        self.assertEqual(e.exception.code, 'MATRIX_UNEXPECTED_COLUMNS')
        with self.assertRaises(R.Refuse) as e:
            M.matrix_bytes_with(self.root, {'BLG-99999': row})
        self.assertEqual(e.exception.code, 'MATRIX_ROW_MISSING')

    def test_02_refresh_data_maps_notices_and_regenerates(self):
        c = M.make_ctx(self.root, 'x', 'p')
        data = {}
        for rel in (M.LEGAL_NOTICES_REL, M.LEADS_REL):
            data[rel] = (self.root / rel).read_text(encoding='utf-8')
        # bài nguyên vẹn có URL cũ nằm trong seo-leads.yml / legal-notices.json (nếu có)
        pick = None
        for aid, b in sorted(c.baseline.items()):
            if b['qa_evidence_intact'] == 'yes' and any(b['old_url'] in t for t in data.values()):
                pick = aid
                break
        if pick is None:
            self.skipTest('khong co bai nguyen ven nao nam trong du lieu khoa theo URL')
        self.focus.add(pick)
        m = self.manifest([pick])
        self.apply(m, [pick])
        # build-price-notices.py đọc _data/pricing.yml nên cần PyYAML; runner CI chỉ có thư viện chuẩn, khi đó chạy các bộ
        # sinh còn lại — bộ sinh price-notices vẫn được chạy ở máy có PyYAML (nơi chạy `refresh-data` thật).
        real_generated = M.GENERATED_DATA
        try:
            import yaml  # noqa: F401
        except ImportError:
            M.GENERATED_DATA = tuple(g for g in real_generated if 'price-notices' not in g[1])
        try:
            changed = M.refresh_data(self.root)
            old_url = c.baseline[pick]['old_url']
            new_url = c.baseline[pick]['new_url']
            for rel in (M.LEGAL_NOTICES_REL, M.LEADS_REL):
                t = (self.root / rel).read_text(encoding='utf-8')
                self.assertNotIn(old_url, t, rel)
            self.assertTrue(any(new_url in (self.root / rel).read_text(encoding='utf-8') for rel in (M.LEGAL_NOTICES_REL, M.LEADS_REL)))
            self.assertTrue(changed)
            self.assertEqual(M.refresh_data(self.root, check=True), [], 'sau khi lam moi khong con lech')
            self.assertEqual(M.refresh_data(self.root), [], 'lam moi lan hai no-op')
        finally:
            M.GENERATED_DATA = real_generated


if __name__ == '__main__':
    unittest.main(verbosity=1)
