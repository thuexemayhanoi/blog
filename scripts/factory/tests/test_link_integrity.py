#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test tính toàn vẹn liên kết nội bộ — canonical route /blog (QA hardening).

Bao trùm các kịch bản bắt buộc:
  R1  /blog/thue-xe/...        -> PASS (route thật trong repo)
  R2  /thue-xe/...             -> FAIL (thiếu baseurl /blog)
  R3  anchor hợp lệ /blog/.../#x -> PASS (anchor đối chiếu đúng base URL)
  R4  route không tồn tại       -> FAIL
  R5  generate-matrix sinh internal_links luôn có /blog (idempotent,
      tái sinh không làm mất prefix; hàng PUBLISHED giữ nguyên)
  R6  manifest export mang liên kết /blog
  R7  op qa chốt evidence links_routes_valid + bad_routes; link non-/blog
      không thể PASS chỉ vì khớp prefix

Chạy: python3 scripts/factory/tests/test_link_integrity.py (không đổi ROOT).
"""
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
PY = sys.executable

IGNORE = shutil.ignore_patterns('__pycache__', '.git', '*.pyc')


def fresh_copy():
    tmp = tempfile.mkdtemp(prefix='linkint-')
    work = os.path.join(tmp, 'work')
    shutil.copytree(ROOT, work, ignore=IGNORE)
    return work, tmp


def run(work, *args):
    return subprocess.run([PY] + list(args), cwd=work,
                          capture_output=True, text=True)


def probe(work, expr):
    """Chạy biểu thức trong ngữ cảnh module factory-operator tại work."""
    code = ('import importlib.util as u, json\n'
            's = u.spec_from_file_location("fo", "scripts/factory/factory-operator.py")\n'
            'm = u.module_from_spec(s)\n'
            's.loader.exec_module(m)\n'
            'm.BASEURL = m._site_baseurl()\n'
            'print(json.dumps(m.%s))\n' % expr)
    return json.loads(run(work, '-c', code).stdout)


def load_rows(work):
    with open(os.path.join(work, 'data/content-matrix.csv'),
              encoding='utf-8') as f:
        return list(csv.DictReader(f))


def set_status(work, aid, status):
    rows = load_rows(work)
    for r in rows:
        if r['id'] == aid:
            r['status'] = status
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    with open(os.path.join(work, 'data/content-matrix.csv'), 'w',
              encoding='utf-8', newline='') as f:
        f.write(buf.getvalue())
    # đồng bộ checkpoint + outputs deterministic để preflight validate PASS
    cp_path = os.path.join(work, 'data/state/checkpoint.json')
    with open(cp_path, encoding='utf-8') as f:
        cp = json.load(f)
    counts = {}
    for r in rows:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    cp['counts'] = {'legacy_total': cp['counts'].get('legacy_total', 483),
                     'existing': counts.get('EXISTING', 0),
                     'review': counts.get('REVIEW', 0),
                     'planned': counts.get('PLANNED', 0),
                     'writing': counts.get('WRITING', 0),
                     'qa': counts.get('QA', 0),
                     'pass': counts.get('PASS', 0),
                     'published': counts.get('PUBLISHED', 0),
                     'repair': counts.get('REPAIR', 0),
                     'blocked': counts.get('BLOCKED', 0),
                     'fail': counts.get('FAIL', 0)}
    with open(cp_path, 'w', encoding='utf-8') as f:
        json.dump(cp, f, ensure_ascii=False, indent=2)
    for script in ('generate-reports.py', 'generate-matrix.py',
                   'generate-listing-pages.py'):
        rr = run(work, 'scripts/factory/' + script)
        assert rr.returncode == 0, script + ': ' + rr.stdout + rr.stderr


def first_planned(work):
    for r in load_rows(work):
        if r['status'] == 'PLANNED':
            return r
    raise AssertionError('không còn PLANNED')


def write_draft(work, row, links_md):
    slug = row['output_path'][len('_posts/{date}-'):-3]
    d = '2026-09-27'
    path = os.path.join(work, '_drafts', '%s-%s.md' % (d, slug))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(links_md)
    return path


def draft_body(row, links):
    slug = row['output_path'][len('_posts/{date}-'):-3]
    d = '2026-09-27'
    date_url = '2026/09/27'
    perm = row['canonical_url'].replace('{date}', date_url)
    perm = perm[len('/blog'):]
    paras = '\n\n'.join('- Xem thêm [%s](%s).' % (l, l) for l in links)
    return ('---\ndate: %s 09:00:00 +0700\nlayout: post\n'
            'title: "%s"\nauthor: "Nguyễn Tú"\ndescription: "%s miêu tả '
            'đủ chiều dài một trăm bốn mươi ký tự trở lên cho kiểm tra mô tả '
            'bài viết chuẩn SEO của bài pilote Regression Test." \n'
            'categories: [Kinh nghiệm]\nlang: vi\n'
            'tags: [%s]\npermalink: %s\nparent_id: %s\nchild_id: %s\n'
            'article_id: %s\n---\n\n'
            'Đoạn mở bài chứa từ khóa chính %s để kiểm tra intent mở đầu '
            'của bài viết chạy thử nghiệm tại Hà Nội, khu vực Long Biên, '
            'Bồ Đề, phố Nguyễn Văn Cừ.\n\n'
            '## Mục thứ nhất nói về %s tại Hà Nội\n\n%s\n\n'
            '## Mục thứ hai về %s quanh Hồ Gươm Hoàn Kiếm\n\n'
            'Nội dung suy rộng đủ số từ trong khoảng mục tiêu của bài, '
            'không có số tiền ngoài whitelist, không từ cấm.\n'
            % (d, row['title'], row['primary_keyword'],
               row['primary_keyword'], perm, row['parent_id'],
               row['child_id'], row['id'], row['primary_keyword'],
               row['primary_keyword'], paras, row['primary_keyword']))


# ------------------------------------------------------------------ R1-R4
class RouteTruth(unittest.TestCase):
    """Đối chiếu route truth từ repository — không gọi network."""

    def test_r1_blog_route_passes(self):
        r = probe(ROOT, "link_route_ok('/blog/thue-xe/gia-thue/')")
        self.assertIs(r, True)

    def test_r2_root_relative_without_blog_fails(self):
        r = probe(ROOT, "link_route_ok('/thue-xe/gia-thue/')")
        self.assertIs(r, False)

    def test_r3_anchor_link_passes_on_correct_base(self):
        r = probe(ROOT, "link_route_ok('/blog/bang-gia/#tinh-gia')")
        self.assertIs(r, True)
        # anchor trên base SAI vẫn FAIL
        r2 = probe(ROOT, "link_route_ok('/bang-gia/#tinh-gia')")
        self.assertIs(r2, False)

    def test_r4_nonexistent_route_fails(self):
        r = probe(ROOT, "link_route_ok('/blog/khong-ton-tai-route-xyz/')")
        self.assertIs(r, False)

    def test_r4b_baseurl_from_config(self):
        r = probe(ROOT, "BASEURL")
        self.assertEqual(r, '/blog')

    def test_r4c_factory_post_permalink_in_routes(self):
        r = probe(ROOT, "link_route_ok('/blog/thue-xe/2026/09/27/"
                        "gia-thue-xe-may-theo-ngay-o-ha-noi/')")
        self.assertIs(r, True)


# ------------------------------------------------------------------ R5
class GeneratorPrefix(unittest.TestCase):
    def test_r5_matrix_never_loses_blog_prefix(self):
        work, tmp = fresh_copy()
        try:
            before = {r['id']: r for r in load_rows(work)}
            r1 = run(work, 'scripts/factory/generate-matrix.py')
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            rows1 = load_rows(work)
            self.assertEqual(len(rows1), len(before))
            # mọi liên kết nội bộ của hàng factory phải có /blog
            bad = []
            for r in rows1:
                if r['source'].startswith('legacy:') or r['status'] == 'PUBLISHED':
                    continue  # PUBLISHED bảo toàn bằng chứng, legacy không có link
                for l in (r['internal_links'] or '').split(';'):
                    l = l.strip()
                    if (l and not l.startswith('#')
                            and not l.startswith(('http://', 'https://',
                                                  'mailto:', 'tel:'))
                            and not l.startswith('/blog')):
                        bad.append((r['id'], l))
            self.assertEqual(bad, [], 'liên kết thiếu /blog: %s' % bad[:10])
            # hàng PUBLISHED giữ nguyên internal_links (không ghi đè)
            for r in rows1:
                o = before.get(r['id'])
                if o and o['status'] == 'PUBLISHED':
                    self.assertEqual(r['internal_links'],
                                     o['internal_links'],
                                     'PUBLISHED %s bị đổi' % r['id'])
                    self.assertEqual(r['status'], 'PUBLISHED')
            # trạng thái runtime bảo toàn
            counts = {}
            for r in rows1:
                counts[r['status']] = counts.get(r['status'], 0) + 1
            bcounts = {}
            for r in before.values():
                bcounts[r['status']] = bcounts.get(r['status'], 0) + 1
            self.assertEqual(counts, bcounts)
            # idempotent: chạy lần 2 ra byte-identical
            with open(os.path.join(work, 'data/content-matrix.csv'),
                      encoding='utf-8') as f:
                first = f.read()
            r2 = run(work, 'scripts/factory/generate-matrix.py')
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            with open(os.path.join(work, 'data/content-matrix.csv'),
                      encoding='utf-8') as f:
                second = f.read()
            self.assertEqual(first, second, 'generate-matrix không idempotent')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ R6
class ManifestPrefix(unittest.TestCase):
    def test_r6_manifest_carries_blog_links(self):
        work, tmp = fresh_copy()
        try:
            r = run(work, 'scripts/factory/generate-matrix.py')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            rows = load_rows(work)
            # Ưu tiên manifest đã có sẵn trong repo (WRITING/PASS là hàng đã
            # được generator sinh internal_links chuẩn /blog). Operator TỪ
            # CHỐI claim thêm khi transaction/chunk đang mở là ĐÚNG thiết kế.
            cand = [x for x in rows if x['status'] in ('WRITING', 'PASS')]
            mf = None
            for x in cand:
                pp = os.path.join(work, 'reports/factory/rows',
                                 x['id'] + '.json')
                if os.path.exists(pp):
                    mf = pp
                    break
            if mf is None:
                # Repo chưa có manifest nào: sinh một manifest qua operator
                # rồi kiểm tra (đường dẫn chuẩn vẫn phải /blog).
                r = run(work, 'scripts/factory/factory-operator.py',
                        'prepare-next', '--count', '1')
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                rows = load_rows(work)
                claimed = [x for x in rows if x['status'] == 'WRITING']
                self.assertEqual(len(claimed), 1)
                mf = os.path.join(work, 'reports/factory/rows',
                                  claimed[0]['id'] + '.json')
                self.assertTrue(os.path.exists(mf),
                                'manifest thiếu cho %s' % claimed[0]['id'])
            with open(mf, encoding='utf-8') as f:
                d = json.load(f)
            links = d['internal_links_matrix']
            self.assertTrue(links, 'manifest thiếu internal_links')
            for l in links:
                self.assertTrue(l.startswith('/blog'),
                                'manifest link thiếu /blog: %s' % l)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ R7
class QaRouteEvidence(unittest.TestCase):
    def _qa(self, links):
        work, tmp = fresh_copy()
        try:
            row = first_planned(work)
            set_status(work, row['id'], 'WRITING')
            write_draft(work, row, draft_body(row, links))
            r = run(work, 'scripts/factory/factory-operator.py',
                    'qa', '--ids', row['id'])
            evp = os.path.join(work, 'data/qa', row['id'] + '.json')
            if not os.path.exists(evp):
                raise AssertionError('op qa không sinh evidence. rc=%d\n'
                                     'STDOUT: %s\nSTDERR: %s'
                                     % (r.returncode, r.stdout[-1500:],
                                        r.stderr[-500:]))
            with open(evp, encoding='utf-8') as f:
                ev = json.load(f)
            return r, ev
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_r7_non_blog_link_fails_and_is_evidenced(self):
        r, ev = self._qa(['/thue-xe/gia-thue/', '/bang-gia/',
                          '/lien-he/', '/thue-xe/'])
        self.assertEqual(ev['checks']['links_routes_valid'], False)
        self.assertIn('/thue-xe/gia-thue/', ev['bad_routes'])
        self.assertIn('/bang-gia/', ev['bad_routes'])
        self.assertTrue(ev['critical_failure'])
        self.assertEqual(ev['result'], 'REPAIR')

    def test_r7b_blog_links_pass_route_check(self):
        r, ev = self._qa(['/blog/thue-xe/gia-thue/', '/blog/bang-gia/',
                          '/blog/lien-he/', '/blog/thue-xe/'])
        self.assertEqual(ev['checks']['links_routes_valid'], True)
        self.assertEqual(ev['bad_routes'], [])

    def test_r7c_anchor_and_nonexistent(self):
        r, ev = self._qa(['/blog/bang-gia/#tinh-gia',
                          '/blog/khong-ton-tai-route-xyz/',
                          '/blog/lien-he/', '/blog/thue-xe/'])
        self.assertEqual(ev['checks']['links_routes_valid'], False)
        self.assertIn('/blog/khong-ton-tai-route-xyz/', ev['bad_routes'])
        self.assertNotIn('/blog/bang-gia/#tinh-gia', ev['bad_routes'])

    def test_r7d_legacy_unicode_links_pass(self):
        # link tới bài legacy (URL chứa khoảng trắng/Unicode, percent-encoded
        # đúng như site phục vụ) PHẢI PASS links_routes_valid
        r, ev = self._qa([
            '/blog/kinh%20nghi%E1%BB%87m/2026/09/17/thu-tuc-thue-xe-may-o-ha-noi-cho-nguoi-moi/',
            '/blog/du%20l%E1%BB%8Bch/2026/09/13/goi-y-kham-pha-ha-noi-bang-xe-may-cho-nguoi-moi/',
            '/blog/lien-he/', '/blog/thue-xe/'])
        self.assertEqual(ev['checks']['links_routes_valid'], True)
        self.assertEqual(ev['bad_routes'], [])

    def test_r7e_ascii_rewritten_legacy_link_fails(self):
        # writer tự đổi /kinh nghiệm/ thành /kinh-nghiem/ (route không tồn
        # tại) -> QA PHẢI bắt ra, không "tự sửa" bằng route bịa
        r, ev = self._qa([
            '/blog/kinh-nghiem/2026/09/17/thu-tuc-thue-xe-may-o-ha-noi-cho-nguoi-moi/',
            '/blog/lien-he/', '/blog/thue-xe/', '/blog/bang-gia/'])
        self.assertEqual(ev['checks']['links_routes_valid'], False)
        self.assertIn('/blog/kinh-nghiem/2026/09/17/'
                      'thu-tuc-thue-xe-may-o-ha-noi-cho-nguoi-moi/',
                      ev['bad_routes'])


# ------------------------------------------------------------------ R8-R11
class SiteIntegrity(unittest.TestCase):
    """Bảo vệ vĩnh viễn sau đợt sửa link toàn site 2026-09-27:

    R8  mọi bài trong _posts KHÔNG còn liên kết nội bộ thiếu /blog
    R9  AGENTS.md bị exclude khỏi build công khai (không render /blog/AGENTS/)
    R10 mọi internal_links của matrix resolves vào route truth
    R11 generate-topic-hubs idempotent: hub được tham chiếu phải tồn tại
    """

    POST_LINK = re.compile(r'\]\(\s*/(?!blog)[^)\s]+')

    def test_r8_published_posts_no_prefixless_links(self):
        posts_dir = os.path.join(ROOT, '_posts')
        bad = []
        for fn in sorted(os.listdir(posts_dir)):
            text = open(os.path.join(posts_dir, fn), encoding='utf-8').read()
            body = text.split('---', 2)[2] if text.count('---') >= 2 else text
            for m in self.POST_LINK.finditer(body):
                bad.append((fn, m.group(0)))
        self.assertEqual(bad, [], 'liên kết thiếu /blog trong _posts: %s' % bad[:10])

    def test_r9_agents_md_excluded_from_public_build(self):
        cfg = open(os.path.join(ROOT, '_config.yml'), encoding='utf-8').read()
        self.assertTrue(re.search(r'^exclude:.*', cfg, re.M), 'thiếu exclude trong _config.yml')
        m = re.search(r'^exclude:\n((?:  - .*\n)+)', cfg, re.M)
        self.assertIn('AGENTS.md', m.group(1), 'AGENTS.md phải nằm trong exclude')
        self.assertTrue(os.path.exists(os.path.join(ROOT, 'AGENTS.md')),
                        'AGENTS.md vẫn phải tồn tại trong repository')

    def test_r10_matrix_internal_links_resolve_to_route_truth(self):
        work, tmp = fresh_copy()
        try:
            code = ('import importlib.util as u, json\n'
                    's = u.spec_from_file_location("fo", '
                    '"scripts/factory/factory-operator.py")\n'
                    'm = u.module_from_spec(s)\n'
                    's.loader.exec_module(m)\n'
                    'm.BASEURL = m._site_baseurl()\n'
                    'print(json.dumps(sorted(list(m.canonical_routes()))))\n')
            rr = run(work, '-c', code)
            self.assertEqual(rr.returncode, 0, rr.stderr)
            routes = set(json.loads(rr.stdout))
            bad = []
            with open(os.path.join(work, 'data/content-matrix.csv'),
                      encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    for l in (row['internal_links'] or '').split(';'):
                        l = l.strip().rstrip(';').strip()
                        if not l:
                            continue
                        if not l.startswith('/blog'):
                            bad.append((row['id'], row['status'], l, 'thiếu /blog'))
                            continue
                        route = l.split('#', 1)[0]
                        if not route.endswith('/'):
                            route += '/'
                        if route not in routes:
                            bad.append((row['id'], row['status'], l, 'route không tồn tại'))
            self.assertEqual(bad, [], 'matrix links lệch route truth: %s' % bad[:10])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_r11_topic_hubs_exist_and_generator_idempotent(self):
        work, tmp = fresh_copy()
        try:
            r1 = run(work, 'scripts/factory/generate-topic-hubs.py')
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            self.assertIn('idempotent', r1.stdout + ('hub mới' if False else ''))
            r2 = run(work, 'scripts/factory/generate-topic-hubs.py')
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            self.assertIn('OK: mọi hub', r2.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)



# ------------------------------------------------------------------ R12-R15
class LegacyUnicodeLinks(unittest.TestCase):
    """URL legacy chứa khoảng trắng/Unicode (ví dụ /blog/du lịch/...).

    R12 route truth phải lowercase category như Jekyll/sitemap công khai;
        link raw (chưa encode) và link percent-encoded đều PASS.
    R13 KHÔNG tự viết lại /du lịch/ thành /du-lich/ — route đó không tồn
        tại thì PHẢI FAIL (không được "sửa" bằng cách bịa route mới).
    R14 internal_links_in nhìn thấy link raw chứa khoảng trắng và tách
        được markdown title.
    R15 manifest internal_link_candidates cung cấp URL percent-encoded
        (markdown-safe, không chứa khoảng trắng thô) và URL đó hợp lệ.
    """

    RAW = '/blog/du lịch/2026/09/13/goi-y-kham-pha-ha-noi-bang-xe-may-cho-nguoi-moi/'
    RAW2 = '/blog/kinh nghiệm/2026/09/17/thu-tuc-thue-xe-may-o-ha-noi-cho-nguoi-moi/'

    def test_r12_legacy_unicode_route_ok(self):
        r = probe(ROOT, "link_route_ok('%s')" % self.RAW)
        self.assertIs(r, True)
        q = probe(ROOT, "public_url('%s')" % self.RAW)
        self.assertEqual(q, '/blog/du%20l%E1%BB%8Bch/2026/09/13/'
                           'goi-y-kham-pha-ha-noi-bang-xe-may-cho-nguoi-moi/')
        r2 = probe(ROOT, "link_route_ok('%s')" % q)
        self.assertIs(r2, True)
        r3 = probe(ROOT, "link_route_ok('%s')" % self.RAW2)
        self.assertIs(r3, True)

    def test_r13_ascii_rewrite_must_fail(self):
        # KHÔNG đổi /du lịch/ thành /du-lich/ khi route đó không tồn tại
        r = probe(ROOT, "link_route_ok('/blog/du-lich/2026/09/13/"
                        "goi-y-kham-pha-ha-noi-bang-xe-may-cho-nguoi-moi/')")
        self.assertIs(r, False)

    def test_r14_internal_links_in_raw_space_and_title(self):
        body = ('Xem [bài legacy](%s) và [bài khác](/blog/thue-xe/ '
                '"tiêu đề") cùng [bài nữa](%s).' % (self.RAW2, self.RAW))
        r = probe(ROOT, "internal_links_in(%r)" % body)
        self.assertIn(self.RAW2, r)
        self.assertIn(self.RAW, r)
        self.assertIn('/blog/thue-xe/', r)
        for l in r:
            self.assertNotIn('"', l)

    def test_r15_manifest_candidates_markdown_safe(self):
        expr = ("related_published(m.load_matrix(), next(r for r in m.load_matrix() "
                "if r['id'] == 'BLG-00695'))")
        cands = probe(ROOT, expr)
        self.assertTrue(cands, 'không có ứng viên liên kết')
        for c in cands:
            self.assertNotIn(' ', c['url'], 'URL chứa khoảng trắng thô')
            self.assertTrue(all(ord(ch) < 128 for ch in c['url']),
                            'URL chưa percent-encode Unicode')
        ok = all(probe(ROOT, "link_route_ok(%r)" % c['url']) for c in cands)
        self.assertIs(ok, True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
