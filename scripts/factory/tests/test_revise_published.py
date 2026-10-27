#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test revise-published.py trên bản sao hermetic của repo (FxTestCase).

Phủ: chỉ sửa nhẹ thân bài/description của bài PUBLISHED có evidence NGUYÊN VẸN mới ghi (hoặc, với
--domain-drift, evidence lệch hash ĐÃ CHỨNG MINH chỉ do đổi domain v3 — TestDomainDrift); mọi ca
khác bị TỪ CHỐI (không có cờ ép): evidence lệch hash, lease, draft, front matter/liên kết/heading
đổi, sửa quá lớn, số tiền ngoài danh sách duyệt, tiêu chí QA tụt; manifest giả/lỗi thời không ép
được; lô nguyên tử; sao lưu + provenance + chuỗi lịch sử; chạy lặp no-op; rollback byte-exact và
không đè thay đổi của người khác; apply lỗi giữa chừng tự trả byte cũ; không đụng matrix/state/draft;
mốc lịch sử và chú thích lịch sử của evidence được giữ nguyên.
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
SCRIPT = HERE.parent / 'revise-published.py'
sys.path.insert(0, str(HERE))
from test_qa_modes import FxTestCase, matrix_rows  # noqa: E402

spec = importlib.util.spec_from_file_location('revise_under_test', SCRIPT)
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
A = R.A


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


# matrix, state, draft, checkpoint: tool KHÔNG được đụng; _posts chỉ đổi đúng file được duyệt
GUARD = ('data/content-matrix.csv', 'data/state', '_drafts')
PURPOSE, REASON = 'unit-test', 'kiem thu cong cu sua bai PUBLISHED'


def safe_edit(text):
    """Một sửa vô hại, duy nhất trong bài: thêm "(đã cập nhật)" trước dấu chấm cuối của một đoạn ngắn."""
    front = re.match(r'\A---\n.*?\n---\n', text, re.S)
    body_start = front.end()
    for m in re.finditer(r'^[A-ZÀ-Ỹ][^|*_#\n]{110,330}[.]$', text[body_start:], re.M):
        line = m.group(0)
        if '](' in line or '{{' in line or len(line.split()) > 90:
            continue
        for k in (30, 50, 80, len(line)):
            old = line[-k:]
            if text.count(old) == 1:
                return [{'old': old, 'new': old[:-1] + ' (đã cập nhật)' + old[-1]}]
    return None


def second_edit(text):
    """Một sửa vô hại KHÁC (đánh dấu "(lần hai)") trên bản đã sửa lần một; None nếu bài không có câu phù hợp."""
    for m2 in re.finditer(r'^[A-ZÀ-Ỹ][^|*_#\n]{110,330}[.]$', text, re.M):
        line = m2.group(0)
        if '](' in line or '{{' in line or '(đã cập nhật)' in line or len(line.split()) > 90:
            continue
        old = line[-40:]
        if text.count(old) == 1:
            return [{'old': old, 'new': old[:-1] + ' (lần hai)' + old[-1]}]
    return None


class TestEditPrimitives(unittest.TestCase):
    """Phần thuần văn bản: không cần repo."""
    FRONT = '---\ntitle: "T"\ndescription: "D"\npermalink: /a/\n---\n'
    BODY = '## H2\n\nMột đoạn có [liên kết](/bang-gia/) và giá 700.000đ mỗi tuần.\n\n### H3\n\nHết.\n'

    def test_apply_edits_exact_count_and_no_cascade(self):
        t = 'a b a'
        out, ch = R.apply_edits(t, [{'old': 'b', 'new': 'a'}])
        self.assertEqual(out, 'a a a')
        self.assertEqual(ch, 2)
        out, _ = R.apply_edits(t, [{'old': 'a', 'new': 'b', 'count': 2}])
        self.assertEqual(out, 'b b b')
        with self.assertRaises(R.Refuse) as c:
            R.apply_edits(t, [{'old': 'a', 'new': 'b'}])            # 2 lần, cần 1
        self.assertEqual(c.exception.code, 'EDIT_MISMATCH')
        with self.assertRaises(R.Refuse) as c:
            R.apply_edits(t, [{'old': 'zzz', 'new': 'b'}])
        self.assertEqual(c.exception.code, 'EDIT_MISMATCH')
        # sửa sau KHÔNG được khớp vào chữ vừa được sửa trước: tìm trên văn bản GỐC
        out, _ = R.apply_edits('x y', [{'old': 'x', 'new': 'y'}, {'old': 'y', 'new': 'z'}])
        self.assertEqual(out, 'y z')

    def test_apply_edits_rejects_bad_overlapping_and_too_many(self):
        for bad in ([], 'x', [{'old': 'a', 'new': 'a'}], [{'old': '', 'new': 'a'}], [{'old': 'a'}],
                    [{'old': 'a', 'new': 'b', 'count': 0}], [{'old': 'a', 'new': 'b', 'count': True}],
                    [{'old': 'a', 'new': 'b', 'extra': 1}], [5]):
            with self.assertRaises(R.Refuse) as c:
                R.apply_edits('a', bad)
            self.assertIn(c.exception.code, ('NO_EDITS', 'BAD_EDIT'), bad)
        with self.assertRaises(R.Refuse) as c:
            R.apply_edits('abcdef', [{'old': 'abc', 'new': '1'}, {'old': 'cde', 'new': '2'}])
        self.assertEqual(c.exception.code, 'EDIT_OVERLAP')
        many = [{'old': 'a%d' % i, 'new': 'b%d' % i} for i in range(R.MAX_EDITS + 1)]
        with self.assertRaises(R.Refuse) as c:
            R.apply_edits(' '.join('a%d' % i for i in range(R.MAX_EDITS + 1)), many)
        self.assertEqual(c.exception.code, 'TOO_MANY_EDITS')

    def check(self, new_front=None, new_body=None, changed=10):
        old = self.FRONT + self.BODY
        new = (new_front or self.FRONT) + (new_body or self.BODY)
        R.check_invariants(old, new, changed)

    def test_invariants_front_matter_only_description_may_change(self):
        self.check()                                                     # không đổi: ok
        self.check(new_front=self.FRONT.replace('description: "D"', 'description: "E"'))
        for old, new in (('title: "T"', 'title: "U"'), ('permalink: /a/', 'permalink: /b/')):
            with self.assertRaises(R.Refuse) as c:
                self.check(new_front=self.FRONT.replace(old, new))
            self.assertEqual(c.exception.code, 'FRONT_MATTER_CHANGED')
        with self.assertRaises(R.Refuse) as c:                          # thêm dòng
            self.check(new_front=self.FRONT.replace('permalink', 'x: 1\npermalink'))
        self.assertEqual(c.exception.code, 'FRONT_MATTER_CHANGED')
        with self.assertRaises(R.Refuse) as c:                          # description không còn một dòng chuỗi hợp lệ
            self.check(new_front=self.FRONT.replace('description: "D"', 'description: E'))
        self.assertEqual(c.exception.code, 'FRONT_MATTER_CHANGED')
        with self.assertRaises(R.Refuse) as c:                          # mất front matter
            R.check_invariants(self.FRONT + self.BODY, self.BODY, 1)
        self.assertEqual(c.exception.code, 'NO_FRONT_MATTER')

    def test_invariants_links_headings_and_size(self):
        for new_body in (self.BODY.replace('/bang-gia/', '/bang-gia-xe-ga/'),
                         self.BODY.replace('[liên kết](/bang-gia/)', 'liên kết'),
                         self.BODY.replace('[liên kết](/bang-gia/)', '[liên kết](/bang-gia/) [x](/y/)'),
                         self.BODY + '\n{% include faq.html %}\n'):
            with self.assertRaises(R.Refuse) as c:
                self.check(new_body=new_body)
            self.assertEqual(c.exception.code, 'LINKS_CHANGED')
        for new_body in (self.BODY.replace('### H3', '#### H3'), self.BODY.replace('## H2', 'H2'),
                         self.BODY + '\n## Mới\n'):
            with self.assertRaises(R.Refuse) as c:
                self.check(new_body=new_body)
            self.assertEqual(c.exception.code, 'HEADINGS_CHANGED')
        self.check(new_body=self.BODY.replace('700.000đ', '800.000đ'))      # đổi chữ trong heading/đoạn: ok
        with self.assertRaises(R.Refuse) as c:
            self.check(changed=int(R.MAX_CHANGE_RATIO * len(self.FRONT + self.BODY)) + 1)
        self.assertEqual(c.exception.code, 'CHANGE_TOO_LARGE')

    def test_edits_digest_is_stable_and_order_sensitive(self):
        a = [{'old': 'a', 'new': 'b'}]
        self.assertEqual(R.edits_digest(a), R.edits_digest([{'new': 'b', 'old': 'a'}]))
        self.assertNotEqual(R.edits_digest(a), R.edits_digest([{'old': 'a', 'new': 'c'}]))


class ReviseBase(FxTestCase):
    def setUp(self):
        super().setUp()
        self._cwd = os.getcwd()
        self.addCleanup(os.chdir, self._cwd)
        self.root = pathlib.Path(self.fx)
        # Các lô sao lưu thật nằm trong repo mà fixture sao chép: test chỉ khẳng định lô của chính nó.
        shutil.rmtree(self.root / R.BACKUP_DIR, ignore_errors=True)
        self.focus = set()
        self.history = None          # blob baseline tổng hợp (TestDomainDrift); None = không dùng --domain-drift

    def ctx(self, approval='owner authorization (test)', batch=None):
        drift = self.history is not None
        c = R.make_ctx(self.root, approval, batch, PURPOSE, REASON, domain_drift=drift,
                       history=dict(self.history) if drift else None)
        keep = self.focus
        # chấm điểm quét toàn bộ ~6.000 hàng cho mỗi lần gọi: thu gọn corpus cho test (cùng ctx cho mọi lệnh gọi)
        c.rows = [r for r in c.rows[:250]] + [r for r in c.rows[250:] if r['id'] in keep]
        return c

    def post_text(self, aid):
        row = next(r for r in matrix_rows(self.fx) if r['id'] == aid)
        return (self.root / row['output_path']).read_text(encoding='utf-8')

    def good_ids(self, n, accept=None):
        """n bài PUBLISHED có evidence nguyên vẹn, chấm lại PASS và có một sửa vô hại (`accept(văn bản)` lọc thêm nếu có).
        Chọn theo nội dung bài chứ không theo vị trí: evidence của bài được reattest/di trú dần nên bài đứng đầu đổi theo dữ liệu."""
        c = R.make_ctx(self.root, 'x', None, PURPOSE, REASON)
        out = []
        for row in c.rows:
            if row['status'] != 'PUBLISHED':
                continue
            post = (self.root / row['output_path'])
            ev_p = self.root / 'data/qa' / (row['id'] + '.json')
            if not post.is_file() or not ev_p.is_file():
                continue
            ev = json.loads(ev_p.read_text(encoding='utf-8'))
            raw = post.read_bytes()
            if (ev.get('content_sha256') != sha(raw) or ev.get('matrix_row_sha256') != A.fingerprint(row)
                    or ev.get('source_path') != row['output_path'] or ev.get('result') != 'PASS'):
                continue
            edits = safe_edit(raw.decode('utf-8'))
            if not edits or (accept is not None and not accept(raw.decode('utf-8'))):
                continue
            if row['id'] in c_leases(self.root):
                continue
            try:
                self.focus.add(row['id'])
                d = R.derive(self.ctx(), row['id'], edits)
            except R.Refuse:
                self.focus.discard(row['id'])
                continue
            if d.after.get('grade') is not None:
                out.append(row['id'])
            if len(out) == n:
                return out
        self.skipTest('fixture khong du bai PASS de dung kich ban')

    def patches(self, ids, edits_by_id=None):
        return {'schema': R.PATCHES_SCHEMA, 'purpose': PURPOSE, 'reason': REASON,
                'patches': {a: {'edits': (edits_by_id or {}).get(a) or safe_edit(self.post_text(a))} for a in ids}}

    def plan(self, ids, edits_by_id=None):
        return R.make_plan(self.ctx(), self.patches(ids, edits_by_id))

    def evidence(self, aid):
        return json.loads((self.root / 'data/qa' / (aid + '.json')).read_text(encoding='utf-8'))

    def evidence_path(self, aid):
        return self.root / 'data/qa' / (aid + '.json')

    def row(self, aid):
        return next(r for r in matrix_rows(self.fx) if r['id'] == aid)

    def posts_tree(self, skip_ids=()):
        skip = {self.row(a)['output_path'] for a in skip_ids}
        return tree_hashes(self.root, ['_posts'], skip)


def c_leases(root):
    try:
        return R.lease_ids(root)
    except R.Refuse:
        return set()


class TestPlan(ReviseBase):

    def test_01_eligible_when_everything_holds_and_nothing_is_written(self):
        a, = self.good_ids(1)
        guard = tree_hashes(self.root, GUARD + ('_posts', 'data/qa'))
        m = self.plan([a])
        e = m['entries'][a]
        self.assertEqual(m['eligible'], [a])
        self.assertEqual(e['decision'], R.ELIGIBLE)
        self.assertNotEqual(e['base_post_sha256'], e['new_post_sha256'])
        self.assertEqual(e['after']['result'], 'PASS')
        self.assertGreaterEqual(e['after']['quality'], 75)
        self.assertGreaterEqual(e['after']['quality'], e['before_scores']['quality'])
        self.assertEqual(e['edits_sha256'], R.edits_digest(e['edits']))
        self.assertEqual(m['purpose'], PURPOSE)
        self.assertTrue(m['head_bound'])
        # plan/derive/score_candidate KHÔNG ghi gì (kể cả bài ứng viên)
        self.assertEqual(tree_hashes(self.root, GUARD + ('_posts', 'data/qa')), guard)

    def test_02_refusals_are_specific_and_no_flag_can_force_them(self):
        a, = self.good_ids(1)
        text = self.post_text(a)
        ok = safe_edit(text)
        ctx = self.ctx()
        row = self.row(a)

        def refused(edits, code, aid=a, c=ctx):
            with self.assertRaises(R.Refuse) as ex:
                R.derive(c, aid, edits)
            self.assertEqual(ex.exception.code, code, ex.exception.msg)

        refused([{'old': 'khong-co-trong-bai-xyz', 'new': 'b'}], 'EDIT_MISMATCH')
        refused([], 'NO_EDITS')
        # title bất biến
        title = re.search(r'^title: .*$', text, re.M).group(0)
        refused([{'old': title, 'new': title[:-2] + 'x"'}], 'FRONT_MATTER_CHANGED')
        # permalink bất biến
        perm = re.search(r'^permalink: .*$', text, re.M).group(0)
        refused([{'old': perm, 'new': perm + 'x'}], 'FRONT_MATTER_CHANGED')
        # liên kết bất biến
        link = re.search(r'\]\((/[^)\s]+)\)', text).group(0)
        refused([{'old': link, 'new': link.replace('(/', '(/x', 1), 'count': text.count(link)}], 'LINKS_CHANGED')
        # heading bất biến theo cấp
        h2 = re.search(r'^## .*$', text, re.M).group(0)
        refused([{'old': h2, 'new': '#' + h2, 'count': text.count(h2)}], 'HEADINGS_CHANGED')
        # sửa nhẹ, không viết lại
        body = text[re.match(r'\A---\n.*?\n---\n', text, re.S).end():]
        big = max((l for l in body.split('\n') if '](' not in l and '{{' not in l and not l.startswith('#')), key=len)
        filler = 'x ' * int(R.MAX_CHANGE_RATIO * len(text))
        refused([{'old': big, 'new': filler}], 'CHANGE_TOO_LARGE')
        # số tiền ngoài danh sách duyệt => business_fact FAIL (critical)
        refused([{'old': ok[0]['old'], 'new': ok[0]['old'][:-1] + ' và giá 9.876.543đ.'}], 'FRESH_QA_NOT_ELIGIBLE')
        # tiêu chí đang đạt không được tụt: description ra ngoài 140–160 ký tự
        desc = re.search(r'^description: "(.*)"$', text, re.M)
        if desc and 140 <= len(desc.group(1)) <= 160:
            refused([{'old': desc.group(0), 'new': 'description: "%s"' % desc.group(1)[:100]}], 'REGRESSION')
        # không phải PUBLISHED
        planned = next(r['id'] for r in matrix_rows(self.fx) if r['status'] == 'PLANNED')
        refused(ok, 'NOT_PUBLISHED', aid=planned)
        refused(ok, 'BAD_ID', aid='../etc')
        # evidence lệch hash => TỪ CHỐI, hướng sang reattest (không sửa nội dung)
        ev_p = self.evidence_path(a)
        good_ev = ev_p.read_bytes()
        ev = json.loads(good_ev)
        for k in ('content_sha256', 'matrix_row_sha256'):
            bad = dict(ev, **{k: '0' * 64})
            ev_p.write_text(json.dumps(bad, ensure_ascii=False, indent=2), encoding='utf-8')
            refused(ok, 'EVIDENCE_NOT_INTACT')
        ev_p.write_text(json.dumps(dict(ev, result='REPAIR'), ensure_ascii=False, indent=2), encoding='utf-8')
        refused(ok, 'EVIDENCE_NOT_INTACT')
        ev_p.write_bytes(good_ev)
        # lease writer
        reg = self.root / 'data/state/writer-claims.json'
        reg.write_text(json.dumps({'schema_version': '2', 'updated_at': None, 'leases': {
            'W9': {'ids': [a], 'session': 's-x', 'expires_at': '2000-01-01T00:00:00Z'}}}), encoding='utf-8')
        refused(ok, 'LEASED')                              # kể cả lease đã hết hạn: bài xuất bản không được nằm trong lease
        reg.write_text(json.dumps({'schema_version': '2', 'updated_at': None, 'leases': {}}), encoding='utf-8')
        # registry hỏng => fail-closed
        reg.write_text('{khong phai json', encoding='utf-8')
        refused(ok, 'BAD_REGISTRY')
        reg.write_text(json.dumps({'schema_version': '2', 'updated_at': None, 'leases': {}}), encoding='utf-8')
        # draft cùng slug
        slug = pathlib.Path(row['output_path']).name[11:-3]
        draft = self.root / '_drafts' / ('2026-10-30-%s.md' % slug)
        draft.write_text('---\ntitle: x\n---\nx\n', encoding='utf-8')
        refused(ok, 'HAS_DRAFT')
        draft.unlink()
        # draft mang article_id này
        draft2 = self.root / '_drafts' / '2026-10-30-mot-slug-khac.md'
        draft2.write_text('---\ntitle: x\narticle_id: %s\n---\nx\n' % a, encoding='utf-8')
        refused(ok, 'HAS_DRAFT')
        draft2.unlink()
        # hết cản: vẫn đạt
        self.assertEqual(R.derive(ctx, a, ok).aid, a)

    def test_03_description_may_change_inside_the_scored_range(self):
        for aid in self.good_ids(3):
            text = self.post_text(aid)
            m = re.search(r'^description: "(.*)"$', text, re.M)
            if m and 140 <= len(m.group(1)) <= 160:
                d = m.group(1)
                new = d[:-3] + d[-2] + d[-3] + d[-1]       # cùng độ dài, khác nội dung
                if new == d:
                    continue
                dd = R.derive(self.ctx(), aid, [{'old': m.group(0), 'new': 'description: "%s"' % new}])
                self.assertIn('description: "%s"' % new, dd.new_post.decode('utf-8'))
                return
        self.skipTest('khong co bai co description 140-160 ky tu')


class TestApply(ReviseBase):

    def apply(self, ids, batch='revise-test-1', manifest=None, **kw):
        m = manifest or self.plan(ids)
        ctx = self.ctx(batch=batch)
        return ctx, m, R.apply_batch(ctx, m, ids, **kw)

    def test_01_apply_writes_post_and_independent_evidence_with_provenance_and_backup(self):
        a, b = self.good_ids(2)
        old_post = {x: self.post_text(x) for x in (a, b)}
        old_ev = {x: self.evidence(x) for x in (a, b)}
        outside = self.posts_tree(skip_ids=(a, b))
        guard = tree_hashes(self.root, GUARD)
        ctx, m, rep = self.apply([a, b])
        self.assertEqual(sorted(rep['written']), sorted([a, b]))
        for x in (a, b):
            new_text = self.post_text(x)
            self.assertNotEqual(new_text, old_post[x])
            expect, _ = R.apply_edits(old_post[x], m['entries'][x]['edits'])
            self.assertEqual(new_text, expect)
            ev = self.evidence(x)
            row = self.row(x)
            self.assertEqual(ev['content_sha256'], sha(new_text.encode('utf-8')))
            self.assertEqual(ev['matrix_row_sha256'], A.fingerprint(row))
            self.assertEqual(ev['source_path'], row['output_path'])
            self.assertEqual(ev['result'], 'PASS')
            self.assertGreaterEqual(ev['quality'], 75)
            self.assertGreaterEqual(ev['seo'], 70)
            self.assertEqual(ev['business_fact'], 'PASS')
            rev = ev['revision']
            self.assertEqual(rev['kind'], 'content-revision')
            self.assertEqual(rev['purpose'], PURPOSE)
            self.assertEqual(rev['approval_ref'], 'owner authorization (test)')
            self.assertEqual(rev['previous_content_sha256'], old_ev[x]['content_sha256'])
            self.assertEqual(rev['previous_matrix_row_sha256'], old_ev[x]['matrix_row_sha256'])
            self.assertEqual(rev['new_content_sha256'], ev['content_sha256'])
            self.assertEqual(rev['edits_sha256'], m['entries'][x]['edits_sha256'])
            self.assertEqual(rev['previous_evidence_sha256'], m['entries'][x]['old_evidence_sha256'])
            self.assertIn('scorer_code_sha256', rev)
            # mốc lịch sử giữ nguyên (watchdog đọc như tín hiệu hoạt động)
            self.assertEqual(ev.get('scored_at'), old_ev[x].get('scored_at'))
            self.assertEqual(ev.get('published_at'), old_ev[x].get('published_at'))
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        self.assertEqual(backup['entries'][a]['old_post_text'], old_post[a])
        self.assertEqual(backup['entries'][a]['old_evidence_text'], json.dumps(old_ev[a], ensure_ascii=False, indent=2))
        self.assertEqual(R.verify_backup(ctx, backup), [])
        # KHÔNG đụng bài khác / matrix / state / draft
        self.assertEqual(self.posts_tree(skip_ids=(a, b)), outside)
        self.assertEqual(tree_hashes(self.root, GUARD), guard)

    def test_02_rerun_is_noop_and_second_revision_chains_history(self):
        # cần bài có chỗ cho lần sửa thứ hai SAU lần sửa đầu
        a, = self.good_ids(1, accept=lambda t: second_edit(R.apply_edits(t, safe_edit(t))[0]) is not None)
        notes = {'post_publish_repair': {'type': 'test', 'note': 'chu thich lich su'}}
        ev = self.evidence(a)
        ev.update(notes)
        self.evidence_path(a).write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding='utf-8')
        ctx, m, rep = self.apply([a])
        first_ev = self.evidence(a)
        self.assertEqual(first_ev['post_publish_repair'], notes['post_publish_repair'])   # giữ nguyên ở cấp trên
        # chạy lại cùng manifest: no-op
        ctx2 = self.ctx(batch='revise-test-rerun')
        rep2 = R.apply_batch(ctx2, m, [a])
        self.assertEqual(rep2['already_current'], [a])
        self.assertEqual(rep2['written'], [])
        self.assertEqual(self.evidence(a), first_ev)
        self.assertFalse((self.root / R.BACKUP_DIR / 'revise-test-rerun.json').exists())
        # sửa lần hai (sửa khác trên bản mới): lịch sử nối chuỗi
        edits2 = second_edit(self.post_text(a))
        self.assertTrue(edits2)
        m_2 = R.make_plan(self.ctx(), self.patches([a], {a: edits2}))
        self.assertEqual(m_2['eligible'], [a])
        rep3 = R.apply_batch(self.ctx(batch='revise-test-2'), m_2, [a])
        self.assertEqual(rep3['written'], [a])
        ev3 = self.evidence(a)
        rev = ev3['revision']
        self.assertEqual(rev['previous_content_sha256'], first_ev['content_sha256'])
        # bài có thể đã có lịch sử revision từ trước (sửa giá, di trú permalink): chuỗi dài thêm đúng MỘT mắt xích, nối ở cuối
        base_history = len(first_ev['revision'].get('history') or [])
        self.assertEqual(len(rev['history']), base_history + 1)
        self.assertEqual(rev['history'][-1]['edits_sha256'], first_ev['revision']['edits_sha256'])
        self.assertEqual(ev3['post_publish_repair'], notes['post_publish_repair'])
        self.assertEqual(ev3['scored_at'], first_ev['scored_at'])

    def test_03_batch_is_atomic_one_bad_id_writes_nothing(self):
        a, b = self.good_ids(2)
        m = self.plan([a, b])
        # lệnh của b không còn áp được vào byte hiện tại (người khác đã sửa bài sau plan)
        row_b = self.row(b)
        p = self.root / row_b['output_path']
        p.write_text(p.read_text(encoding='utf-8') + '\nDong them sau plan.\n', encoding='utf-8')
        before = tree_hashes(self.root, ['_posts', 'data/qa', R.BACKUP_DIR])
        with self.assertRaises(R.Refuse) as ex:
            R.apply_batch(self.ctx(batch='revise-test-atomic'), m, [a, b])
        self.assertIn(ex.exception.code, ('POST_CHANGED_SINCE_PLAN', 'EVIDENCE_NOT_INTACT'))
        self.assertEqual(tree_hashes(self.root, ['_posts', 'data/qa', R.BACKUP_DIR]), before)
        self.assertFalse((self.root / R.BACKUP_DIR / 'revise-test-atomic.json').exists())
        # --skip-ineligible: b bị BỎ QUA (báo cáo), a vẫn được ghi
        rep = R.apply_batch(self.ctx(batch='revise-test-skip'), m, [a, b], skip_ineligible=True)
        self.assertEqual(rep['written'], [a])
        self.assertEqual([x['id'] for x in rep['skipped_ineligible']], [b])

    def test_04_manifest_is_a_proposal_tampering_or_staleness_is_refused(self):
        a, = self.good_ids(1)
        m = self.plan([a])
        guard = tree_hashes(self.root, ['_posts', 'data/qa', R.BACKUP_DIR])

        def refused(manifest, code, ctx=None, ids=(a,)):
            with self.assertRaises(R.Refuse) as ex:
                R.apply_batch(ctx or self.ctx(batch='revise-test-t'), manifest, list(ids))
            self.assertEqual(ex.exception.code, code, ex.exception.msg)
            self.assertEqual(tree_hashes(self.root, ['_posts', 'data/qa', R.BACKUP_DIR]), guard)

        # approval
        with self.assertRaises(R.Refuse) as ex:
            R.apply_batch(self.ctx(approval='  '), m, [a])
        self.assertEqual(ex.exception.code, 'NO_APPROVAL')
        t = copy.deepcopy(m)
        t['head_bound'] = False
        refused(t, 'MANIFEST_NOT_HEAD_BOUND')
        t = copy.deepcopy(m)
        t['schema'] = 'x'
        refused(t, 'BAD_MANIFEST')
        t = copy.deepcopy(m)
        t['entries'][a]['edits'][0]['new'] += ' x'                       # edits_sha256 không khớp
        refused(t, 'BAD_MANIFEST')
        t = copy.deepcopy(m)
        t['entries'][a]['edits'][0]['new'] += ' x'                       # sửa cả edits lẫn digest: byte ứng viên khác manifest
        t['entries'][a]['edits_sha256'] = R.edits_digest(t['entries'][a]['edits'])
        refused(t, 'INPUT_CHANGED_SINCE_PLAN')
        t = copy.deepcopy(m)
        t['entries'][a]['new_post_sha256'] = '0' * 64
        refused(t, 'INPUT_CHANGED_SINCE_PLAN')
        t = copy.deepcopy(m)
        t['eligible'] = []
        refused(t, 'NOT_ELIGIBLE')
        t = copy.deepcopy(m)
        t['entries'][a]['decision'] = 'FRESH_QA_NOT_ELIGIBLE'
        refused(t, 'NOT_ELIGIBLE')
        t = copy.deepcopy(m)
        t['thresholds'] = {'quality_min': 1, 'seo_min': 1}
        refused(t, 'SCORER_CHANGED_SINCE_PLAN')
        t = copy.deepcopy(m)
        t['business_facts_sha256'] = '0' * 64
        refused(t, 'SCORER_CHANGED_SINCE_PLAN')
        # ID ngoài danh sách / sai định dạng
        refused(m, 'BAD_ID', ids=('../x',))
        refused(m, 'NOT_ELIGIBLE', ids=('BLG-99999',))
        refused(m, 'NO_IDS', ids=())
        # lô quá lớn / batch-id sai / sao lưu đã tồn tại
        with self.assertRaises(R.Refuse) as ex:
            R.apply_batch(self.ctx(), m, ['BLG-%05d' % i for i in range(R.MAX_BATCH + 1)])
        self.assertEqual(ex.exception.code, 'BATCH_TOO_LARGE')
        for bad in ('../x', 'a/b', '-x', 'x' * 81):
            with self.assertRaises(R.Refuse) as ex:
                R.apply_batch(self.ctx(batch=bad), m, [a])
            self.assertEqual(ex.exception.code, 'BAD_BATCH_ID', bad)
        # scorer/business-facts đổi sau plan => TỪ CHỐI, chạy lại plan
        bf = self.root / 'data/business-facts.json'
        bf.write_text(bf.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        refused(m, 'SCORER_CHANGED_SINCE_PLAN')

    def test_05_dirty_tree_guard_runs_before_any_write(self):
        a, = self.good_ids(1)
        m = self.plan([a])
        ctx = self.ctx(batch='revise-test-guard')

        def boom():
            raise R.Refuse('DIRTY_TREE', 'cay lam viec khac HEAD')
        ctx.guard = boom
        before = tree_hashes(self.root, ['_posts', 'data/qa', R.BACKUP_DIR])
        with self.assertRaises(R.Refuse) as ex:
            R.apply_batch(ctx, m, [a])
        self.assertEqual(ex.exception.code, 'DIRTY_TREE')
        self.assertEqual(tree_hashes(self.root, ['_posts', 'data/qa', R.BACKUP_DIR]), before)
        # dry-run: kiểm hết nhưng không ghi gì (kể cả sao lưu)
        rep = R.apply_batch(self.ctx(batch='revise-test-dry'), m, [a], dry_run=True)
        self.assertEqual(rep['would_write'], [a])
        self.assertEqual(tree_hashes(self.root, ['_posts', 'data/qa', R.BACKUP_DIR]), before)

    def test_06_failure_mid_apply_restores_every_started_id_byte_exact(self):
        a, b = self.good_ids(2)
        m = self.plan([a, b])
        before = tree_hashes(self.root, ['_posts', 'data/qa'])
        real = R.atomic_write
        calls = {'n': 0}

        def flaky(path, data):
            if str(path).endswith('.json') and '/data/qa/' in str(path):
                calls['n'] += 1
                if calls['n'] == 2:                    # evidence của ID thứ hai: bài của nó đã được ghi
                    raise OSError('disk full (gia lap)')
            return real(path, data)
        R.atomic_write = flaky
        try:
            with self.assertRaises(OSError):
                R.apply_batch(self.ctx(batch='revise-test-abort'), m, [a, b])
        finally:
            R.atomic_write = real
        self.assertEqual(tree_hashes(self.root, ['_posts', 'data/qa']), before)
        self.assertFalse((self.root / R.BACKUP_DIR / 'revise-test-abort.json').exists())
        # khôi phục cũng hỏng => GIỮ sao lưu và báo ID còn lại
        calls['n'] = 0
        real_rb = R.rollback_backup
        R.atomic_write = flaky

        def broken_rollback(*a_, **k_):
            raise OSError('rollback hong (gia lap)')
        R.rollback_backup = broken_rollback
        try:
            with self.assertRaises(R.Refuse) as ex:
                R.apply_batch(self.ctx(batch='revise-test-abort2'), m, [a, b])
        finally:
            R.atomic_write, R.rollback_backup = real, real_rb
        self.assertEqual(ex.exception.code, 'PARTIAL_APPLY_BACKUP_KEPT')
        self.assertTrue((self.root / R.BACKUP_DIR / 'revise-test-abort2.json').is_file())
        # khôi phục thủ công từ sao lưu đã giữ
        backup = json.loads((self.root / R.BACKUP_DIR / 'revise-test-abort2.json').read_text(encoding='utf-8'))
        R.rollback_backup(self.root, backup, force_ids=set(backup['entries']))
        self.assertEqual(tree_hashes(self.root, ['_posts', 'data/qa']), before)


class TestVerifyRollback(ReviseBase):

    def applied(self, n=2, batch='revise-test-v'):
        ids = self.good_ids(n)
        m = self.plan(ids)
        ctx = self.ctx(batch=batch)
        rep = R.apply_batch(ctx, m, ids)
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        return ids, ctx, backup

    def test_01_rollback_restores_byte_exact_and_never_overwrites_later_changes(self):
        ids, ctx, backup = self.applied(2)
        a, b = ids
        orig = {x: backup['entries'][x]['old_post_text'] for x in ids}
        # bài b bị người khác sửa tiếp sau apply: rollback KHÔNG được đè
        pb = self.root / self.row(b)['output_path']
        pb.write_text(pb.read_text(encoding='utf-8') + '\nSua tiep.\n', encoding='utf-8')
        dry = R.rollback_backup(self.root, backup, dry_run=True)
        self.assertEqual(dry['restored'], [a])
        self.assertEqual(dry['skipped_changed_since_apply'], [b])
        self.assertNotEqual(self.post_text(a), orig[a])                  # dry-run không ghi
        out = R.rollback_backup(self.root, backup)
        self.assertEqual(out['restored'], [a])
        self.assertEqual(out['skipped_changed_since_apply'], [b])
        self.assertEqual(self.post_text(a), orig[a])
        self.assertEqual((self.root / 'data/qa' / (a + '.json')).read_text(encoding='utf-8'),
                         backup['entries'][a]['old_evidence_text'])
        self.assertIn('Sua tiep.', self.post_text(b))
        with self.assertRaises(R.Refuse) as ex:
            R.rollback_backup(self.root, backup, ids={'BLG-99999'})
        self.assertEqual(ex.exception.code, 'UNKNOWN_IDS')

    def test_02_verify_detects_every_kind_of_tampering(self):
        ids, ctx, backup = self.applied(1, 'revise-test-v2')
        a = ids[0]
        self.assertEqual(R.verify_backup(ctx, backup), [])
        self.assertEqual(R.verify_backup(ctx, backup, rescore=False), [])
        post_p = self.root / self.row(a)['output_path']
        ev_p = self.evidence_path(a)
        good_post, good_ev = post_p.read_bytes(), ev_p.read_bytes()
        ev = json.loads(good_ev)

        def forged(mutate, rescore=True):
            """Evidence bị sửa MÀ sao lưu được vá cho khớp sha: chỉ các kiểm sâu mới bắt được."""
            bad = copy.deepcopy(ev)
            mutate(bad)
            raw = json.dumps(bad, ensure_ascii=False, indent=2).encode('utf-8')
            ev_p.write_bytes(raw)
            b = copy.deepcopy(backup)
            b['entries'][a]['new_evidence_sha256'] = sha(raw)
            try:
                return R.verify_backup(ctx, b, rescore=rescore)
            finally:
                ev_p.write_bytes(good_ev)

        def joined(problems):
            return ' | '.join(problems)

        # bài bị đổi sau apply
        post_p.write_bytes(good_post + b'x')
        self.assertIn('bai khac ban da ghi', joined(R.verify_backup(ctx, backup)))
        post_p.write_bytes(good_post)
        # evidence bị đổi thẳng (không vá sao lưu)
        ev_p.write_text(json.dumps(dict(ev, quality=ev['quality'] - 1), ensure_ascii=False, indent=2), encoding='utf-8')
        self.assertIn('evidence khac ban da ghi', joined(R.verify_backup(ctx, backup)))
        ev_p.write_bytes(good_ev)
        # vá sha sao lưu nhưng điểm tự khai khác điểm chấm lại độc lập
        self.assertIn('khac diem cham lai doc lap', joined(forged(lambda e: e.update(quality=e['quality'] - 1))))
        self.assertEqual(forged(lambda e: e.update(quality=e['quality'] - 1), rescore=False), [])     # --no-rescore: chỉ cấu trúc
        # hash không khớp bài / hàng matrix / nguồn / article_id
        self.assertIn('content_sha256 khong khop', joined(forged(lambda e: e.update(content_sha256='0' * 64), False)))
        self.assertIn('matrix_row_sha256 khong khop', joined(forged(lambda e: e.update(matrix_row_sha256='0' * 64), False)))
        self.assertIn('source_path != output_path', joined(forged(lambda e: e.update(source_path='_posts/x.md'), False)))
        self.assertIn('article_id trong evidence', joined(forged(lambda e: e.update(article_id='BLG-1'), False)))
        # cổng QA bị hạ
        self.assertIn('khong dat nguong', joined(forged(lambda e: e.update(business_fact='FAIL'), False)))
        self.assertIn('khong dat nguong', joined(forged(lambda e: e.update(critical_failure=True), False)))
        # provenance: người duyệt, hash cũ, danh sách sửa
        self.assertIn('provenance khong khop', joined(forged(lambda e: e['revision'].update(approval_ref=''), False)))
        self.assertIn('provenance khong khop',
                      joined(forged(lambda e: e['revision'].update(previous_evidence_sha256='0' * 64), False)))
        self.assertIn('provenance khong khop', joined(forged(lambda e: e['revision'].update(edits_sha256='0' * 64), False)))
        # mốc lịch sử bị đổi / chú thích lịch sử bị mất
        self.assertIn('scored_at lich su', joined(forged(lambda e: e.update(scored_at='2030-01-01T00:00:00+00:00'), False)))
        self.assertIn('published_at lich su', joined(forged(lambda e: e.pop('published_at'), False)))
        # sao lưu bị sửa: bài cũ / danh sách sửa / đường dẫn
        bad_backup = copy.deepcopy(backup)
        bad_backup['entries'][a]['old_post_text'] += 'x'
        self.assertIn('sao luu bai cu hong', joined(R.verify_backup(ctx, bad_backup)))
        bad_backup = copy.deepcopy(backup)
        bad_backup['entries'][a]['edits'][0]['new'] += 'x'
        self.assertIn('bai hien tai != bai cu + danh sach sua', joined(R.verify_backup(ctx, bad_backup)))
        bad_backup = copy.deepcopy(backup)
        bad_backup['entries'][a]['path'] = '../etc/passwd'
        with self.assertRaises(R.Refuse) as ex:
            R.verify_backup(ctx, bad_backup)
        self.assertEqual(ex.exception.code, 'BAD_BACKUP')
        # không còn PUBLISHED => lỗi rõ ràng
        rows_backup = ctx.by_id[a]['status']
        ctx.by_id[a]['status'] = 'REPAIR'
        try:
            self.assertIn('khong con PUBLISHED', joined(R.verify_backup(ctx, backup)))
        finally:
            ctx.by_id[a]['status'] = rows_backup

    def test_03_floor_is_enforced_by_the_tool_not_by_the_repo(self):
        op = self.root / 'scripts/factory/factory-operator.py'
        src = op.read_text(encoding='utf-8')
        self.assertIn('QUALITY_MIN = 75', src)
        op.write_text(src.replace('QUALITY_MIN = 75', 'QUALITY_MIN = 60'), encoding='utf-8')
        with self.assertRaises(R.Refuse) as ex:
            R.make_ctx(self.root, 'x', None, PURPOSE, REASON)
        self.assertEqual(ex.exception.code, 'THRESHOLD_BELOW_FLOOR')



class TestDomainDrift(ReviseBase):
    """--domain-drift: evidence lệch hash do đổi domain v3 (chứng minh DOMAIN_ONLY_PROVEN như reattest-legacy-qa.py)
    được sửa + chấm lại độc lập trong một giao dịch; lệch hash KHÔNG chứng minh được thì vẫn từ chối."""

    def setUp(self):
        super().setUp()
        self.history = {}

    def make_stale(self, aid, *, unbound=False, edit_after_migration=None):
        """Biến evidence của `aid` thành evidence CŨ (hash của baseline chưa migrate: liên kết /blog/, URL /blog...)
        và nạp baseline vào self.history — đúng hình dạng ca thật của reattest-legacy-qa.py."""
        rows = matrix_rows(self.fx)
        row = next(r for r in rows if r['id'] == aid)
        post = self.root / row['output_path']
        current = post.read_bytes()
        old = current.replace(b'](/', b'](/blog/')
        if A.migrated(old) != current:
            self.skipTest('bai %s khong dung duoc de dung baseline tong hop' % aid)
        if edit_after_migration:
            post.write_bytes(current + edit_after_migration)
        old_row = dict(row)
        for key in ('expected_url', 'canonical_url'):
            old_row[key] = '/blog' + row[key]
        ev_path = self.evidence_path(aid)
        ev = json.loads(ev_path.read_text(encoding='utf-8'))
        old_ev = dict(ev, content_sha256='0' * 64 if unbound else sha(old),
                      matrix_row_sha256=A.fingerprint(old_row))
        raw = json.dumps(old_ev, ensure_ascii=False, indent=2).encode('utf-8')
        ev_path.write_bytes(raw)
        self.history[row['output_path']] = old
        self.history['data/qa/%s.json' % aid] = raw
        prev = self.history.get('data/content-matrix.csv')
        old_rows = list(csv.DictReader(io.StringIO(prev.decode()))) if prev else []
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(row.keys()), lineterminator='\n')
        w.writeheader()
        for r in old_rows + [old_row]:
            w.writerow(r)
        self.history['data/content-matrix.csv'] = buf.getvalue().encode()
        return old_ev

    def drift_ids(self, n):
        """n bài PASS có sửa vô hại mà evidence đã được biến thành lệch hash domain-only."""
        hist, self.history = self.history, None        # chọn bài trên evidence nguyên vẹn
        try:
            ids = self.good_ids(n)
        finally:
            self.history = hist
        for a in ids:
            self.make_stale(a)
        return ids

    def test_01_without_flag_drifted_evidence_is_refused(self):
        a, = self.drift_ids(1)
        edits = safe_edit(self.post_text(a))
        hist, self.history = self.history, None
        try:
            with self.assertRaises(R.Refuse) as ex:
                R.derive(self.ctx(), a, edits)
        finally:
            self.history = hist
        self.assertEqual(ex.exception.code, 'EVIDENCE_NOT_INTACT')

    def test_02_proven_drift_is_revised_rescored_and_verified_from_history(self):
        a, b = self.drift_ids(2)
        old_ev = {x: self.evidence(x) for x in (a, b)}
        m = self.plan([a, b])
        self.assertTrue(m['domain_drift'])
        self.assertEqual(sorted(m['eligible']), sorted([a, b]))
        for x in (a, b):
            self.assertEqual(m['entries'][x]['base'], R.BASE_DOMAIN)
            self.assertEqual(m['entries'][x]['domain_only_proof']['classification'], 'DOMAIN_ONLY_PROVEN')
        guard = tree_hashes(self.root, GUARD)
        ctx = self.ctx(batch='revise-test-drift')
        rep = R.apply_batch(ctx, m, [a, b])
        self.assertEqual(sorted(rep['written']), sorted([a, b]))
        for x in (a, b):
            ev = self.evidence(x)
            row = self.row(x)
            self.assertEqual(ev['content_sha256'], sha(self.post_text(x).encode('utf-8')))
            self.assertEqual(ev['matrix_row_sha256'], A.fingerprint(row))
            self.assertEqual(ev['result'], 'PASS')
            rev = ev['revision']
            self.assertEqual(rev['base'], R.BASE_DOMAIN)
            proof = rev['domain_only_proof']
            self.assertEqual(proof['baseline_content_sha256'], old_ev[x]['content_sha256'])
            self.assertEqual(proof['baseline_matrix_sha256'], old_ev[x]['matrix_row_sha256'])
            self.assertEqual(proof['pre_edit_content_sha256'], m['entries'][x]['base_post_sha256'])
            self.assertEqual(rev['previous_content_sha256'], old_ev[x]['content_sha256'])
            self.assertEqual(ev.get('scored_at'), old_ev[x].get('scored_at'))
        backup = json.loads((self.root / rep['backup']).read_text(encoding='utf-8'))
        self.assertEqual(R.verify_backup(self.ctx(), backup), [])
        self.assertEqual(tree_hashes(self.root, GUARD), guard)
        # verify chứng minh LẠI từ lịch sử: baseline không còn buộc hash cũ => lỗi, không tin sao lưu
        self.history['data/qa/%s.json' % a] = json.dumps(dict(old_ev[a], content_sha256='1' * 64)).encode()
        self.assertIn('khong chung minh lai duoc', ' | '.join(R.verify_backup(self.ctx(), backup)))
        # rollback byte-exact về bài + evidence lệch hash ban đầu
        out = R.rollback_backup(self.root, backup)
        self.assertEqual(sorted(out['restored']), sorted([a, b]))
        self.assertEqual(self.evidence(a), old_ev[a])

    def test_03_unproven_drift_is_refused(self):
        a, = self.good_ids(1)
        self.make_stale(a, unbound=True)                 # hash cũ không buộc byte baseline
        m = self.plan([a])
        self.assertEqual(m['eligible'], [])
        self.assertEqual(m['entries'][a]['decision'], 'NOT_DOMAIN_ONLY')
        b, = [x for x in self.good_ids(2) if x != a][:1]
        self.make_stale(b, edit_after_migration='\nCâu thêm sau migrate.\n'.encode())   # nội dung đổi thật
        m = self.plan([b])
        self.assertEqual(m['entries'][b]['decision'], 'NOT_DOMAIN_ONLY')

    def test_04_manifest_and_apply_must_use_the_same_mode(self):
        a, = self.drift_ids(1)
        m = self.plan([a])
        hist, self.history = self.history, None
        try:
            with self.assertRaises(R.Refuse) as ex:
                R.apply_batch(self.ctx(batch='revise-test-mode'), m, [a])
        finally:
            self.history = hist
        self.assertEqual(ex.exception.code, 'DOMAIN_DRIFT_MISMATCH')
        forged = copy.deepcopy(m)
        forged['entries'][a]['base'] = R.BASE_INTACT     # manifest khai sai nền => apply từ chối
        with self.assertRaises(R.Refuse) as ex:
            R.apply_batch(self.ctx(batch='revise-test-mode2'), forged, [a])
        self.assertEqual(ex.exception.code, 'INPUT_CHANGED_SINCE_PLAN')


if __name__ == '__main__':
    unittest.main()
