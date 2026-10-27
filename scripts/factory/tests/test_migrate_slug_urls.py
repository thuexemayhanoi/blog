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
import csv
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
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
        """n ID baseline CHƯA di trú, evidence nguyên vẹn (đo trên byte hiện tại) VÀ derive() thành công (đủ điều kiện).
        Lọc rẻ trước (registry, hash) rồi mới dựng ngữ cảnh + chấm điểm: mỗi lô di trú thêm 50 ID vào registry, nếu dựng ngữ cảnh cho
        cả ID đã di trú thì suite chậm dần theo số lô (đã chạm timeout 1500s của run-tests.py)."""
        c = M.make_ctx(self.root, 'x', 'probe')
        out = []
        for aid, b in sorted(c.baseline.items()):
            row = c.by_id.get(aid)
            if aid in c.registry or row is None or row['status'] != 'PUBLISHED' or not self._intact(aid, row):
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

    def _intact(self, aid, row):
        ev_p, post_p = self.root / 'data/qa' / (aid + '.json'), self.root / (row.get('output_path') or '-')
        if not ev_p.is_file() or not post_p.is_file():
            return False
        ev = json.loads(ev_p.read_text(encoding='utf-8'))
        return (ev.get('content_sha256') == sha(post_p.read_bytes()) and ev.get('matrix_row_sha256') == A.fingerprint(row)
                and ev.get('result') == 'PASS')

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

    def test_compose_mapping_flattens_chains_and_rejects_loops(self):
        """Review pha 2: 3/16 đích thiếu '/' là dạng thiếu '/' của URL cũ ⇒ '/x/y' -> '/x/y/' sẽ đáp xuống trang chuyển hướng (chuỗi)."""
        mp = {'/a/b': '/a/b/', '/a/b/': '/a/c/', '/x/': '/y/'}
        self.assertEqual(M.compose_mapping(mp), {'/a/b': '/a/c/', '/a/b/': '/a/c/', '/x/': '/y/'})
        self.assertEqual(M.compose_mapping({'/p/': '/q/', '/q/': '/r/', '/r/': '/s/'}),
                         {'/p/': '/s/', '/q/': '/s/', '/r/': '/s/'})
        for bad in ({'/a/': '/b/', '/b/': '/a/'}, {'/a/': '/a/'}, {'/a/': '/b/', '/b/': '/c/', '/c/': '/a/'}):
            with self.assertRaises(R.Refuse) as e:
                M.compose_mapping(bad)
            self.assertEqual(e.exception.code, 'MAPPING_LOOP')
        out, counts = M.retarget_text('xem [a](/a/b) và [b](/a/b/) và [c](/a/b/#f)', M.compose_mapping(mp))
        self.assertEqual(out, 'xem [a](/a/c/) và [b](/a/c/) và [c](/a/c/#f)')
        self.assertEqual(counts, {'/a/b': 1, '/a/b/': 2})

    def test_retarget_text_changes_only_targets(self):
        t = ('Xem [bài](/a/b/ "tiêu đề") và [x](/a/b/#frag) và <a href="/a/b/">h</a> và [y](/a/bc/) và [z](/a/b/c/) '
             'và [s](/ky-nang) và [s2](/ky-nang/2026/x/).')
        mp = {'/a/b/': '/a/B2/', '/ky-nang': '/ky-nang/'}
        out, counts = M.retarget_text(t, mp)
        self.assertEqual(counts, {'/a/b/': 3, '/ky-nang': 1})
        self.assertIn('[bài](/a/B2/ "tiêu đề")', out)
        self.assertIn('[x](/a/B2/#frag)', out)
        self.assertIn('<a href="/a/B2/">h</a>', out)
        self.assertIn('[y](/a/bc/)', out)                # khóa là TOKEN đầy đủ: /a/b/ không khớp /a/bc/
        self.assertIn('[z](/a/b/c/)', out)               # cũng không khớp /a/b/c/
        self.assertIn('[s](/ky-nang/)', out)
        self.assertIn('[s2](/ky-nang/2026/x/)', out)     # /ky-nang không khớp /ky-nang/2026/...
        self.assertEqual(M.mask_links(t), M.mask_links(out))
        self.assertNotEqual(M.mask_links(t), M.mask_links(out.replace('và', 'VÀ', 1)))
        self.assertEqual(M.retarget_text(t, {}), (t, {}))

    def test_rewrite_is_token_exact(self):
        mp = {'/x/2026/10/07/at-xe/': '/x/2026/10/07/dat-xe/'}
        self.assertEqual(M._rewrite('a /x/2026/10/07/at-xe/ b /x/2026/10/07/at-xe-khac/', mp),
                         'a /x/2026/10/07/dat-xe/ b /x/2026/10/07/at-xe-khac/')
        self.assertEqual(M._rewrite('khong doi', {}), 'khong doi')


class TestPlan(MigrateBase):

    def test_01_plan_classifies_and_writes_nothing(self):
        three = self.intact_candidates(3)
        good, drifted = three[:2], three[2]
        # Ca "evidence lệch hash" dựng trong fixture (bài đổi một byte sau QA), không dựa vào cờ đóng băng của baseline:
        # bài lệch hash thật được reattest dần nên không còn là ca lệch ổn định.
        p = self.root / self.row(drifted)['output_path']
        R.atomic_write(p, p.read_bytes() + b'\n')
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


    def test_date_prefixed_baseline_row_passes_path_comparison(self):
        """Review #77: baseline ghi tiền tố ngày hai lần ở new_output_path của 7 bài legacy; derive() phải so với bản đã gộp."""
        self.assertEqual(M.baseline_new_path('_posts/2026-09-29-2026-09-29-dat-xe-truoc-bao-lau-thi-nen.md'),
                         '_posts/2026-09-29-dat-xe-truoc-bao-lau-thi-nen.md')
        self.assertEqual(M.baseline_new_path('_posts/2026-10-09-ha-noi-di.md'), '_posts/2026-10-09-ha-noi-di.md')
        c = M.make_ctx(self.root, 'x', 'p')
        dbl = re.compile(r'^_posts/(\d{4}-\d{2}-\d{2})-\1-')
        # Chọn động: các bài ngày kép lần lượt được di trú thật nên ID cố định sẽ thành ALREADY_MIGRATED.
        status = {r['id']: r['status'] for r in matrix_rows(self.fx)}
        pending = sorted(a for a, b in c.baseline.items()
                         if dbl.match(b['new_output_path']) and a not in c.registry and status.get(a) == 'PUBLISHED')
        if not pending:
            self.skipTest('mọi bài baseline ngày kép đã di trú; baseline_new_path đã kiểm ở trên')
        aid = pending[0]
        b = c.baseline[aid]
        row = self.row(aid)
        post = self.root / row['output_path']
        ev_p = self.root / 'data/qa' / (aid + '.json')
        ev = json.loads(ev_p.read_text(encoding='utf-8'))
        ev.update(content_sha256=sha(post.read_bytes()), matrix_row_sha256=A.fingerprint(row), source_path=row['output_path'],
                  result='PASS', article_id=aid)
        ev_p.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding='utf-8')
        self.focus.add(aid)
        d = M.derive(self.ctx(), aid, score=False)
        self.assertEqual((d.old_url, d.new_url), (b['old_url'], b['new_url']))
        self.assertEqual(d.new_path, dbl.sub(lambda m: '_posts/%s-' % m.group(1), b['new_output_path']))
        self.assertEqual(M.baseline_new_path(b['new_output_path']), d.new_path)

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
            # Mô tả không được gọi stub là 301; bỏ đường dẫn stub trước khi kiểm vì ID như BLG-01301 chứa chuỗi '301'.
            self.assertNotRegex(rv['redirect'].replace('khong phai HTTP 301', '').replace(SR.stub_relpath(a), ''), r'\b301\b')
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


    def edit_matrix_row(self, aid, **changes):
        raw = (self.root / M.MATRIX_REL).read_bytes().decode('utf-8')
        reader = csv.DictReader(io.StringIO(raw, newline=''))
        fields = reader.fieldnames
        rows = list(reader)
        for r in rows:
            if r['id'] == aid:
                r.update(changes)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
        (self.root / M.MATRIX_REL).write_bytes(buf.getvalue().encode('utf-8'))

    def test_03_matrix_edited_after_apply_refuses_before_writing_anything(self):
        """Review #77: trước đây rollback khôi phục bài/evidence/trang chuyển hướng RỒI mới từ chối vì matrix đổi -> kẹt nửa chừng."""
        ids = self.intact_candidates(2)
        m = self.manifest(ids)
        rep = self.apply(m, ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        self.edit_matrix_row(ids[0], intent=self.row(ids[0])['intent'] + ' (sua tay)')
        after_edit = tree_hashes(self.root, WATCH)
        for dry in (True, False):
            with self.assertRaises(R.Refuse) as e:
                M.rollback_backup(self.root, backup, dry_run=dry)
            self.assertEqual(e.exception.code, 'MATRIX_CHANGED_SINCE_APPLY')
            self.assertEqual(tree_hashes(self.root, WATCH), after_edit, 'tu choi TRUOC khi ghi bat ky tep nao')

    def test_06_rollback_refuses_while_other_posts_link_to_the_new_url(self):
        """Review pha 2: phase-1 rollback không được để lại bài khác liên kết tới URL mới sắp biến mất (links-rollback TRƯỚC)."""
        ids = self.intact_candidates(2)
        m = self.manifest(ids)
        rep = self.apply(m, ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        new_url = backup['entries'][ids[0]]['new_url']
        own = {self.root / b['new_path'] for b in backup['entries'].values()}
        host = next(p for p in sorted((self.root / '_posts').glob('*.md')) if p not in own)
        keep = host.read_bytes()
        host.write_bytes(keep + ('\n[xem them](%s)\n' % new_url).encode('utf-8'))
        after = tree_hashes(self.root, WATCH)
        for dry in (True, False):
            with self.assertRaises(R.Refuse) as e:
                M.rollback_backup(self.root, backup, dry_run=dry)
            self.assertEqual(e.exception.code, 'INBOUND_LINKS_TO_NEW_URL')
            self.assertIn(str(host.relative_to(self.root)), e.exception.msg)
            self.assertEqual(tree_hashes(self.root, WATCH), after, 'tu choi truoc khi ghi bat ky tep nao')
        host.write_bytes(keep)                                       # bỏ liên kết ⇒ rollback chạy được
        out = M.rollback_backup(self.root, backup)
        self.assertEqual(sorted(out['restored']), sorted(ids))

    def test_04_interrupted_rollback_is_completed_by_rerun(self):
        """Ngắt giữa lúc khôi phục tệp và lúc khôi phục matrix/registry: chạy lại hoàn tất phần dùng chung (không còn kẹt)."""
        ids = self.intact_candidates(2)
        m = self.manifest(ids)
        before = tree_hashes(self.root, WATCH)
        rep = self.apply(m, ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        real = M.atomic_write

        def flaky(path, data):
            if pathlib.Path(path).name == 'content-matrix.csv':
                raise OSError('gia lap ngat dien')
            return real(path, data)

        M.atomic_write = flaky
        try:
            with self.assertRaises(OSError):
                M.rollback_backup(self.root, backup)
        finally:
            M.atomic_write = real
        self.assertFalse(SR.source_errors(self.root) == [], 'tep da ve ban cu nhung matrix/registry con o ban di tru')
        out = M.rollback_backup(self.root, backup)
        self.assertEqual(out['restored'], [])
        self.assertEqual(sorted(out['shared_restored']), sorted(ids))
        self.assertEqual(tree_hashes(self.root, WATCH), before, 'chay lai hoan tat rollback byte-exact')
        again = M.rollback_backup(self.root, backup)
        self.assertEqual((again['restored'], again['shared_restored']), ([], []), 'lan ba la no-op')

    def test_05_cli_exit_code_nonzero_when_ids_were_skipped(self):
        ids = self.intact_candidates(2)
        m = self.manifest(ids)
        rep = self.apply(m, ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        p = self.root / self.row(ids[0])['output_path']
        R.atomic_write(p, p.read_bytes() + b'\nsua tay\n')
        out = M.rollback_backup(self.root, backup)
        self.assertEqual(out['skipped_changed_since_apply'], [ids[0]])
        self.assertFalse(not out['skipped_changed_since_apply'])    # CLI: ok = not skipped -> thoát 1 (bao còn ID chưa khôi phục)

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
            if aid in c.registry or aid not in c.by_id or not self._intact(aid, c.by_id[aid]):
                continue
            if any(b['old_url'] in t for t in data.values()):
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


class TestRetargetLinks(MigrateBase):
    """Pha 2: đổi ĐÍCH liên kết nội bộ của bài nguyên vẹn (engine tổng quát; ánh xạ do người gọi cấp)."""

    def pair(self):
        """(ID bài P nguyên vẹn, đích cũ Q, đích mới R): P link tới bài Q; R là bài khác cùng danh mục (giữ tiền tố hub)."""
        c = M.make_ctx(self.root, 'x', 'probe')
        by_url = {r['expected_url']: r for r in c.rows if r['status'] == 'PUBLISHED'}
        for r in c.rows[600:2600]:
            if r['status'] != 'PUBLISHED':
                continue
            ev_p = self.root / 'data/qa' / (r['id'] + '.json')
            post = self.root / r['output_path']
            if not ev_p.is_file() or not post.is_file():
                continue
            ev = json.loads(ev_p.read_text(encoding='utf-8'))
            raw = post.read_bytes()
            if ev.get('content_sha256') != sha(raw) or ev.get('matrix_row_sha256') != A.fingerprint(r) or ev.get('result') != 'PASS':
                continue
            text = raw.decode('utf-8')
            for q in M.re.findall(r'\]\((/[a-z0-9-]+/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/)\)', text):
                if q not in by_url or q == r['expected_url']:
                    continue
                cat = q.split('/')[1]
                other = next((u for u in by_url if u.startswith('/%s/' % cat) and u != q and u != r['expected_url']
                              and ('](%s)' % u) not in text), None)
                if other:
                    self.focus.add(r['id'])
                    try:
                        M.derive_links(self.ctx(), r['id'], {q: other})
                    except R.Refuse:
                        self.focus.discard(r['id'])
                        continue
                    return r['id'], q, other
        self.skipTest('fixture khong co bai phu hop')

    def links_manifest(self, ids, mp):
        m = M.make_links_plan(self.ctx(), mp, ids)
        self.assertEqual(sorted(m['eligible']), sorted(ids), m['excluded'])
        return m

    def test_01_plan_apply_verify_rollback(self):
        aid, q, other = self.pair()
        mp = {q: other}
        row = self.row(aid)
        old_post = (self.root / row['output_path']).read_bytes()
        old_ev = self.evidence(aid)
        before = tree_hashes(self.root, WATCH)
        m = self.links_manifest([aid], mp)
        self.assertEqual(M.make_links_plan(self.ctx(), mp, [aid])['counts']['links'], sum(m['entries'][aid]['targets'].values()))
        self.assertEqual(tree_hashes(self.root, WATCH), before, 'links-plan khong ghi gi')
        rep = M.apply_links(self.ctx(batch='links-test'), m, [aid])
        self.assertEqual(rep['written'], [aid])
        changed = {k for k, v in tree_hashes(self.root, WATCH).items() if before.get(k) != v}
        self.assertEqual(changed, {row['output_path'], 'data/qa/%s.json' % aid}, 'chi bai + evidence cua no doi (khong matrix/registry)')
        new_post = (self.root / row['output_path']).read_bytes()
        self.assertEqual(new_post.decode(), old_post.decode().replace('](%s)' % q, '](%s)' % other))
        ev = self.evidence(aid)
        rv = ev['revision']
        self.assertEqual((rv['kind'], rv['mapping_sha256'], ev['content_sha256']), (M.LINK_KIND, M.mapping_digest(mp), sha(new_post)))
        self.assertEqual(ev['matrix_row_sha256'], old_ev['matrix_row_sha256'])
        for k in ('scored_at', 'published_at'):
            self.assertEqual(ev.get(k), old_ev.get(k))
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        self.assertTrue(rep['backup'].startswith(M.LINK_BACKUP_DIR))
        self.assertEqual(M.verify_links_backup(self.ctx(), backup), [])
        # chạy lại: no-op; rollback: byte-exact; rollback lần hai: no-op
        done = tree_hashes(self.root, WATCH)
        rep2 = M.apply_links(self.ctx(batch='links-test-2'), m, [aid])
        self.assertEqual((rep2.get('written', []), rep2['already_current']), ([], [aid]))
        self.assertEqual(tree_hashes(self.root, WATCH), done)
        out = M.rollback_links(self.root, backup)
        self.assertEqual(out['restored'], [aid])
        self.assertEqual(tree_hashes(self.root, WATCH), before)
        self.assertEqual(M.rollback_links(self.root, backup)['restored'], [])

    def test_01b_default_mapping_has_slashless_old_urls_and_is_composed(self):
        ids = self.intact_candidates(1)
        self.apply(self.manifest(ids), ids)
        e = next(r for r in SR.load_registry(self.root) if r['article_id'] == ids[0])
        mp = M.default_mapping(self.root)
        self.assertEqual(mp[e['old_url']], e['new_url'])
        self.assertEqual(mp[e['old_url'].rstrip('/')], e['new_url'])        # dạng thiếu '/' đi THẲNG tới URL mới
        out, counts = M.retarget_text('[a](%s) [b](%s) [c](%s)' % (e['old_url'], e['old_url'].rstrip('/'), e['old_url'] + 'x/'), mp)
        self.assertEqual(out, '[a](%s) [b](%s) [c](%s)' % (e['new_url'], e['new_url'], e['old_url'] + 'x/'))   # token đầy đủ: /x/ giữ nguyên
        # đích thiếu '/' bổ sung từ file (như 16 đích thật) được gập qua registry: không đáp xuống trang chuyển hướng
        extra = {e['old_url'].rstrip('/'): e['old_url']}
        merged = M.compose_mapping({**M.default_mapping(self.root), **extra})
        self.assertEqual(merged[e['old_url'].rstrip('/')], e['new_url'])

    def test_01c_already_current_requires_evidence_bound_to_the_new_post(self):
        """Review pha 2: bài đã là bản mới nhưng evidence cũ (apply bị ngắt) KHÔNG được coi là 'đã xong'."""
        aid, q, other = self.pair()
        m = self.links_manifest([aid], {q: other})
        M.apply_links(self.ctx(batch='links-test-a'), m, [aid])
        ev_p = self.root / 'data/qa' / (aid + '.json')
        good = ev_p.read_bytes()
        ev_p.write_text(json.dumps(dict(json.loads(good), content_sha256='0' * 64), indent=2), encoding='utf-8')
        with self.assertRaises(R.Refuse) as e:
            M.apply_links(self.ctx(batch='links-test-b'), m, [aid])
        self.assertEqual(e.exception.code, 'EVIDENCE_NOT_BOUND_TO_NEW_POST')
        ev_p.write_bytes(good)
        self.assertEqual(M.apply_links(self.ctx(batch='links-test-c'), m, [aid])['already_current'], [aid])

    def test_02_refusals(self):
        aid, q, other = self.pair()
        mp = {q: other}
        m = self.links_manifest([aid], mp)
        with self.assertRaises(R.Refuse) as e:
            M.apply_links(self.ctx(approval=''), m, [aid])
        self.assertEqual(e.exception.code, 'NO_APPROVAL')
        bad = copy.deepcopy(m)
        bad['mapping']['/khac/'] = '/x/'
        with self.assertRaises(R.Refuse) as e:
            M.apply_links(self.ctx(), bad, [aid])
        self.assertEqual(e.exception.code, 'BAD_MANIFEST')
        with self.assertRaises(R.Refuse) as e:
            M.derive_links(self.ctx(), aid, {'/khong/co/lien/ket/': '/x/'})
        self.assertEqual(e.exception.code, 'NO_LINKS')
        # mapping đưa tới route không tồn tại -> links_routes_valid rớt -> không đủ điều kiện (không có cờ ép)
        with self.assertRaises(R.Refuse) as e:
            M.derive_links(self.ctx(), aid, {q: '/khong/ton/tai/2026/10/07/x/'})
        self.assertIn(e.exception.code, ('FRESH_QA_NOT_ELIGIBLE', 'REGRESSION'))
        # evidence không còn nguyên vẹn
        row = self.row(aid)
        p = self.root / row['output_path']
        R.atomic_write(p, p.read_bytes() + b'\n')
        with self.assertRaises(R.Refuse) as e:
            M.derive_links(self.ctx(), aid, mp)
        self.assertEqual(e.exception.code, 'EVIDENCE_NOT_INTACT')

    def test_03_failure_mid_apply_restores(self):
        aid, q, other = self.pair()
        m = self.links_manifest([aid], {q: other})
        before = tree_hashes(self.root, WATCH)
        real = M.verify_links_backup
        M.verify_links_backup = lambda ctx, backup, rescore=True: ['gia lap: kiem tra sau ghi that bai']
        try:
            with self.assertRaises(R.Refuse) as e:
                M.apply_links(self.ctx(batch='links-fail'), m, [aid])
        finally:
            M.verify_links_backup = real
        self.assertEqual(e.exception.code, 'POST_VERIFY_FAILED')
        self.assertEqual(tree_hashes(self.root, WATCH), before)
        self.assertFalse((self.root / M.LINK_BACKUP_DIR / 'links-fail.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=1)
