#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests chặn tái diễn internal 404 — thuexemayhanoi/blog.

Bổ sung sau đợt "eliminate internal 404s" (homepage /blog/blog/, 335 link
{% post_url %} thiếu baseurl, 6 link sai ngày/danh mục legacy, hub thiếu,
favicon thiếu). Đối chiếu mục H của quy trình audit built-site:

  H1  homepage không chứa /blog/blog/ (nguồn + built HTML)
  H2  không internal link nào double-baseurl
  H3  mọi href nội bộ trong built HTML resolve
  H4  menu resolve (navigation.yml -> route truth)
  H5  footer resolve
  H6  hub resolve — MỌI child taxonomy có file hub
  H7  breadcrumb resolve (parent/child/chu-de/trang chủ)
  H8  related articles resolve (expected_url matrix/inventory trong truth)
  H9  CTA resolve (/bai-viet/ tồn tại; không còn '/blog/' | relative_url)
  H10 pagination resolve (trang phân hạng có route thật)
  H11 legacy Unicode URL resolve (percent-encoded, KHÔNG rewrite ascii)
  H12 ASCII rewrite sai của legacy PHẢI FAIL
  H13 matrix internal_links resolve
  H14 bài factory mới KHÔNG THỂ PASS khi link 404 (kể cả /blog/blog/)
  H15 check-built-links.py PHẢI exit 1 khi có internal 404 (chặn CI)

Chạy: python3 scripts/factory/tests/test_built_links.py
"""
import csv
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
PY = sys.executable
CHECKER = os.path.join(ROOT, 'scripts', 'factory', 'check-built-links.py')

# nguồn được Jekyll render công khai (en/ bị exclude — không quét)
RENDER_SKIP_DIRS = {'en', 'docs', 'data', 'reports', 'scripts', '_queue',
                    '_drafts', 'gemfiles', 'node_modules', 'vendor',
                    '.git', '.jekyll-cache', '__pycache__', 'listing'}


def load_checker():
    spec = importlib.util.spec_from_file_location('cbl', CHECKER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_operator_value(snippet):
    """Chạy snippet (đã có module fo là `m`) trong ngữ cảnh
    factory-operator tại ROOT; snippet in JSON ra stdout."""
    code = ('import importlib.util as u, json\n'
            's = u.spec_from_file_location("fo", '
            '"scripts/factory/factory-operator.py")\n'
            'm = u.module_from_spec(s)\n'
            's.loader.exec_module(m)\n'
            'm.BASEURL = m._site_baseurl()\n'
            + snippet)
    r = subprocess.run([PY, '-c', code], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout)


def _routes():
    return set(load_operator_value(
        'print(json.dumps(sorted(list(m.canonical_routes()))))'))


def _route_ok(link):
    return load_operator_value('print(json.dumps(m.link_route_ok(%r)))' % link)


def rendered_sources():
    """Mọi file .md/.html Jekyll render công khai (theo exclude của config)."""
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in RENDER_SKIP_DIRS]
        for fn in files:
            if fn.endswith(('.md', '.html')):
                yield os.path.join(root, fn)


# ---------------------------------------------------------------- H1, H9 (nguồn)

class SourceGuards(unittest.TestCase):
    """Không pattern double-baseurl trong nguồn render."""

    def test_h1_no_blog_blog_relative_url_pattern(self):
        bad = []
        for path in rendered_sources():
            t = open(path, encoding='utf-8').read()
            for m in re.finditer(r"['\"](/blog/[^\s'\"]*)['\"]\s*\|\s*relative_url", t):
                bad.append((os.path.relpath(path, ROOT), m.group(1)))
        self.assertEqual(bad, [],
                         'relative_url trên đường dẫn đã có /blog: %s' % bad[:10])

    def test_h1_no_blog_prefixed_frontmatter_permalink(self):
        bad = []
        for path in rendered_sources():
            head = open(path, encoding='utf-8').read()[:2500]
            m = re.search(r'^permalink:\s*(/\S+)', head, re.M)
            if m and m.group(1).startswith('/blog/'):
                bad.append(os.path.relpath(path, ROOT))
        self.assertEqual(bad, [], 'permalink chứa /blog/ -> ra /blog/blog/: %s' % bad)

    def test_h9_blog_listing_route_exists(self):
        routes = _routes()
        self.assertIn('/blog/bai-viet/', routes,
                       'trang listing /blog/bai-viet/ (blog.md) phải tồn tại')

    def test_h14b_post_url_always_has_baseurl_prefix(self):
        """{% post_url %} trả URL KHÔNG có baseurl — bắt buộc prefix
        {{ site.baseurl }} để không tạo lại 335 link 404 kiểu cũ."""
        bad = []
        for fn in sorted(os.listdir(os.path.join(ROOT, '_posts'))):
            if not fn.endswith('.md'):
                continue
            t = open(os.path.join(ROOT, '_posts', fn), encoding='utf-8').read()
            for m in re.finditer(r'\(\s*\{%\s*post_url', t):
                pre = t[max(0, m.start() - 40):m.start()]
                if 'site.baseurl' not in pre:
                    bad.append((fn, m.group(0)))
        self.assertEqual(bad, [], 'post_url thiếu {{ site.baseurl }}: %s' % bad[:8])


# ------------------------------------------------------- H4, H5, H6, H7, H8, H10, H13

class RouteTruthResolves(unittest.TestCase):
    """Menu/footer/hub/breadcrumb/related/pagination/matrix resolve."""

    @classmethod
    def setUpClass(cls):
        cls.routes = _routes()
        cls.operator_ok = True  # giữ cho tương thích; check riêng bên dưới

    def test_h4_h5_menu_footer_resolve(self):
        # navigation.yml không có thư viện YAML stdlib — parse tối giản
        text = open(os.path.join(ROOT, '_data', 'navigation.yml'),
                    encoding='utf-8').read()
        urls = re.findall(r'url:\s*["\']?(/[^\s"\']*)', text)
        self.assertTrue(urls, 'navigation.yml không đọc được url nào')
        bad = []
        for u in urls:
            route = '/blog' + urllib.parse.unquote(u.split('#', 1)[0])
            if not route.endswith('/'):
                route += '/'
            if route not in self.routes:
                bad.append(u)
        self.assertEqual(bad, [], 'menu/footer trỏ route không tồn tại: %s' % bad)

    def test_h6_every_taxonomy_child_has_hub(self):
        tax = json.load(open(os.path.join(ROOT, 'data', 'content-taxonomy.json'),
                             encoding='utf-8'))
        parents = {p['parent_id']: p for p in tax['parents']}
        missing = []
        for c in tax['children']:
            ps = parents[c['parent_id']]['slug']
            route = '/blog/%s/%s/' % (ps, c['slug'])
            if route not in self.routes:
                missing.append(route)
        self.assertEqual(missing, [],
                         'child hub chưa render (chạy generate-topic-hubs.py): %s'
                         % missing)

    def test_h7_breadcrumb_bases_resolve(self):
        for route in ('/', '/chu-de/'):
            self.assertIn('/blog' + route, self.routes,
                          'breadcrumb gốc %s phải tồn tại' % route)

    def test_h8_every_post_route_resolves(self):
        """Related articles/breadcrumb render từ post.url của mọi site.posts
        — nên MỌI tệp _posts phải cho route hợp lệ, không double-baseurl."""
        posts_dir = os.path.join(ROOT, '_posts')
        bad = []
        for fn in sorted(os.listdir(posts_dir)):
            if not fn.endswith('.md'):
                continue
            head = open(os.path.join(posts_dir, fn),
                        encoding='utf-8').read()[:2500]
            pm = re.search(r'^permalink:\s*(/\S*)', head, re.M)
            if pm and pm.group(1):
                if pm.group(1).startswith('/blog/'):
                    bad.append((fn, 'permalink double-baseurl %s' % pm.group(1)))
                elif ('/blog' + pm.group(1)) not in self.routes:
                    bad.append((fn, 'permalink %s không có route' % pm.group(1)))
                continue
            cm = re.search(r'^categories:\s*\[[^\]]*\]', head, re.M)
            dm = re.search(r'^date:\s*(\d{4})-(\d{2})-(\d{2})', head, re.M)
            if not (cm and dm):
                bad.append((fn, 'thiếu categories/date — không tính được route'))
                continue
            cat = re.sub(r'^categories:\s*\[\s*|\s*\]\s*$', '',
                         cm.group(0)).strip().lower()
            y, mo, d = dm.group(1), dm.group(2), dm.group(3)
            slug = fn[11:-3]
            route = '/blog/%s/%s/%s/%s/%s/' % (cat, y, mo, d, slug)
            if route not in self.routes:
                bad.append((fn, 'route legacy %s không có trong truth' % route))
        self.assertEqual(bad, [], 'bài _posts không resolve: %s' % bad[:8])

    def test_h8b_legacy_expected_urls_resolve(self):
        bad = []
        with open(os.path.join(ROOT, 'data', 'content-matrix.csv'),
                  encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row['status'] != 'EXISTING':
                    continue  # hàng factory: permalink có thể lệch expected_url
                u = (row.get('expected_url') or '').strip()
                if not u or '{date}' in u:
                    continue
                route = urllib.parse.unquote(u)
                if not route.endswith('/'):
                    route += '/'
                if route not in self.routes:
                    bad.append((row['id'], u))
        self.assertEqual(bad, [], 'expected_url legacy không resolve: %s' % bad[:8])

    def test_h10_pagination_sample_resolve(self):
        for rel in ('listing/kinh-nghiem/2.md', 'listing/chia-se/2.md',
                    'listing/topic/cung-duong/cung-duong-cuoi-tuan/2.md'):
            path = os.path.join(ROOT, rel)
            self.assertTrue(os.path.exists(path), 'thiếu trang phân hạng %s' % rel)

    def test_h13_matrix_internal_links_resolve(self):
        bad = []
        with open(os.path.join(ROOT, 'data', 'content-matrix.csv'),
                  encoding='utf-8') as f:
            for row in csv.DictReader(f):
                for l in (row['internal_links'] or '').split(';'):
                    l = l.strip().rstrip(';').strip()
                    if not l:
                        continue
                    route = urllib.parse.unquote(l.split('#', 1)[0])
                    if not route.endswith('/'):
                        route += '/'
                    if route not in self.routes:
                        bad.append((row['id'], l))
        self.assertEqual(bad, [], 'matrix internal_links 404: %s' % bad[:8])


# ---------------------------------------------------------------- H11, H12, H14

class LegacyUnicodeRoutes(unittest.TestCase):
    def test_h11_legacy_unicode_link_passes(self):
        r = _route_ok('/blog/kinh%20nghi%E1%BB%87m/2026/09/17/'
                     'thu-tuc-thue-xe-may-o-ha-noi-cho-nguoi-moi/')
        self.assertIs(r, True)

    def test_h12_ascii_rewrite_fails(self):
        r = _route_ok('/blog/kinh-nghiem/2026/09/17/'
                     'thu-tuc-thue-xe-may-o-ha-noi-cho-nguoi-moi/')
        self.assertIs(r, False, 'ASCII rewrite của URL legacy phải FAIL')

    def test_h14_new_article_404_link_fails(self):
        r = _route_ok('/blog/khong-ton-tai-xyz/')
        self.assertIs(r, False)

    def test_h14b_double_baseurl_link_fails(self):
        # /blog/blog/ từng là route thật (blog.md permalink cũ) — nay phải FAIL
        r = _route_ok('/blog/blog/')
        self.assertIs(r, False, 'link /blog/blog/ phải bị QA từ chối')


# ------------------------------------------------------- built-site fixture (H1-H3, H15)

def build_fixture(site_dir, broken=()):
    """_site tối giản: homepage, hub, child hub, legacy Unicode, asset, listing.
    broken: chuỗi chèn thêm vào homepage để tạo lỗi."""
    os.makedirs(os.path.join(site_dir, 'thue-xe', 'gia-thue'), exist_ok=True)
    os.makedirs(os.path.join(site_dir, 'kinh nghiệm', '2026', '09', '13', 'foo'),
                exist_ok=True)
    os.makedirs(os.path.join(site_dir, 'assets', 'css'), exist_ok=True)
    os.makedirs(os.path.join(site_dir, 'bai-viet'), exist_ok=True)
    files = {
        'index.html': ('<a href="/blog/">Trang chủ</a>'
                       '<a href="/blog/thue-xe/">Thuê xe</a>'
                       '<a href="/blog/thue-xe/gia-thue/">Giá thuê</a>'
                       '<a href="/blog/kinh%20nghi%E1%BB%87m/2026/09/13/foo/">'
                       'Bài legacy</a>'
                       '<a href="/blog/bai-viet/">Bài viết</a>'
                       '<img src="/blog/assets/css/base.css">'
                       + ''.join(broken)),
        'thue-xe/index.html': '<a href="/blog/">Về trang chủ</a>',
        'thue-xe/gia-thue/index.html': '<a href="/blog/thue-xe/">Cha</a>',
        'kinh nghiệm/2026/09/13/foo/index.html': '<a href="/blog/">Up</a>',
        'assets/css/base.css': 'body{}',
        'bai-viet/index.html': '<a href="/blog/">Trang chủ</a>',
    }
    for rel, content in files.items():
        with open(os.path.join(site_dir, rel), 'w', encoding='utf-8') as f:
            f.write(content)


class BuiltSiteChecker(unittest.TestCase):
    """check-built-links.py trên _site fixture (mode CI)."""

    def _run_checker(self, broken=()):
        tmp = tempfile.mkdtemp(prefix='builtlinks-')
        work = os.path.join(tmp, 'work')
        shutil.copytree(ROOT, work,
                        ignore=shutil.ignore_patterns('__pycache__', '.git',
                                                      '*.pyc', '_site'))
        try:
            site_dir = os.path.join(work, '_site')
            build_fixture(site_dir, broken)
            # matrix thu nhỏ cho fixture: chỉ link resolve được
            with open(os.path.join(work, 'data', 'content-matrix.csv'), 'w',
                      encoding='utf-8', newline='') as f:
                f.write('id,internal_links\n'
                        'T1,"/blog/thue-xe/; /blog/bai-viet/"\n')
            r = subprocess.run(
                [PY, os.path.join(work, 'scripts', 'factory',
                                  'check-built-links.py'),
                 '--site', site_dir, '--max-report', '50'],
                capture_output=True, text=True)
            return r.returncode, r.stdout + r.stderr
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_h15_clean_site_passes_exit0(self):
        rc, out = self._run_checker()
        self.assertEqual(rc, 0, out[:2000])
        self.assertIn('PASS', out)

    def test_h15_missing_site_blocked_exit2(self):
        tmp = tempfile.mkdtemp(prefix='builtlinks-')
        try:
            r = subprocess.run(
                [PY, CHECKER, '--site', os.path.join(tmp, 'khong-ton-tai')],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_h1_h2_home_blog_blog_fails(self):
        rc, out = self._run_checker(
            broken=('<a href="/blog/blog/">Xem Blog</a>',))
        self.assertEqual(rc, 1, out[:2000])
        self.assertRegex(out, r'DOUBLE_BASEURL : [1-9]')

    def test_h3_unknown_route_fails(self):
        rc, out = self._run_checker(
            broken=('<a href="/blog/khong-ton-tai-route-xyz/">X</a>',))
        self.assertEqual(rc, 1, out[:2000])
        self.assertRegex(out, r'INTERNAL_404\s*: [1-9]')
        self.assertIn('khong-ton-tai-route-xyz', out)

    def test_h2_double_baseurl_canonical_fails(self):
        rc, out = self._run_checker(
            broken=('<link rel="canonical" '
                    'href="https://thuexemayhanoi.github.io/blog/blog/">',))
        self.assertEqual(rc, 1, out[:2000])
        self.assertRegex(out, r'DOUBLE_BASEURL : [1-9]')

    def test_h12_ascii_rewrite_in_built_fails(self):
        rc, out = self._run_checker(
            broken=('<a href="/blog/kinh-nghiem/2026/09/13/foo/">'
                    'Sai ascii</a>',))
        self.assertEqual(rc, 1, out[:2000])
        self.assertRegex(out, r'INTERNAL_404\s*: [1-9]')
        self.assertIn('kinh-nghiem', out)

    def test_missing_baseurl_flagged(self):
        rc, out = self._run_checker(
            broken=('<a href="/thue-xe/">Thiếu baseurl</a>',))
        self.assertEqual(rc, 1, out[:2000])
        self.assertRegex(out, r'MISSING_BASEURL: [1-9]')

    def test_broken_asset_fails(self):
        rc, out = self._run_checker(
            broken=('<img src="/blog/assets/css/khong-co.css">',))
        self.assertEqual(rc, 1, out[:2000])
        self.assertRegex(out, r'BROKEN_ASSET_INTERNAL: [1-9]')

    def test_external_and_anchor_skipped(self):
        rc, out = self._run_checker(
            broken=('<a href="https://example.com/x/">Ngoài</a>'
                    '<a href="#muc-luc">Neo</a>'
                    '<a href="mailto: x@y.z">Mail</a>'))
        self.assertEqual(rc, 0, out[:2000])


class CheckerUnits(unittest.TestCase):
    """Unit cho hàm phân loại link của checker."""

    @classmethod
    def setUpClass(cls):
        cls.m = load_checker()

    def test_classify_variants(self):
        c = self.m.classify
        self.assertEqual(c('/blog/thue-xe/')[0], 'internal')
        self.assertEqual(c('/blog/blog/')[0], 'double')
        self.assertEqual(c('https://thuexemayhanoi.github.io/blog/x/')[0],
                         'internal')
        self.assertEqual(c('https://thuexemayhanoi.github.io/blog/blog/x')[0],
                         'double')
        self.assertEqual(c('/thue-xe/')[0], 'nobase')
        self.assertEqual(c('thue-xe/')[0], 'relative')
        self.assertEqual(c('#an-chor')[0], 'skip')
        self.assertEqual(c('mailto:a@b.c')[0], 'skip')
        self.assertEqual(c('https://example.com/')[0], 'skip')
        self.assertEqual(c('tel:0942467674')[0], 'skip')
        # percent-decode sớm — H11
        self.assertEqual(c('/blog/kinh%20nghi%E1%BB%87m/2026/09/13/x/')[1],
                         '/blog/kinh nghiệm/2026/09/13/x/')

    def test_candidates_and_asset(self):
        self.assertIn('/blog/x/', self.m.candidates('/blog/x'))
        self.assertTrue(self.m.is_asset('/blog/assets/css/base.css'))
        self.assertFalse(self.m.is_asset('/blog/thue-xe/'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
