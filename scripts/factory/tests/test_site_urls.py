#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test check-site-urls.py (vệ sinh URL toàn site, Issue #77) — OFFLINE, site/nguồn tạm.

Chứng minh: site sạch => 0 lỗi; mỗi lỗi bị bắt và gọi đúng tên: permalink trùng, permalink có chữ hoa/dấu/'đ',
<loc> trùng, <loc> sai host, <loc> không ASCII, canonical URL sitemap không tự trỏ/không có, URL sitemap là trang meta refresh
hoặc noindex, hai trang cùng canonical; trang chuyển hướng (canonical sang URL mới) không bị tính là trùng; mã thoát CLI.
"""
import importlib.util
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
spec = importlib.util.spec_from_file_location('site_urls_t', os.path.join(ROOT, 'scripts/factory/check-site-urls.py'))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
S = C.SITE_URL


def page(url, canon=None, extra=''):
    canon = S + url if canon is None else canon
    return '<html><head><link rel="canonical" href="%s">%s</head><body><h1>x</h1></body></html>' % (canon, extra)


class SiteUrlsTest(unittest.TestCase):

    def setUp(self):
        self.src = tempfile.mkdtemp(prefix='urls-src-')
        self.site = tempfile.mkdtemp(prefix='urls-site-')
        os.makedirs(os.path.join(self.src, '_posts'))
        os.makedirs(os.path.join(self.src, 'redirects/slug-d'))
        self.post('a.md', '/thue-xe/2026/10/01/bai-a/')
        self.post('b.md', '/xe-may/bai-b/')
        self.put('/thue-xe/2026/10/01/bai-a/', page('/thue-xe/2026/10/01/bai-a/'))
        self.put('/xe-may/bai-b/', page('/xe-may/bai-b/'))
        self.put('/', page('/'))
        # trang chuyển hướng: canonical sang URL mới — đúng thiết kế, không phải "trùng canonical"
        self.put('/thue-xe/2026/10/01/bai-cu/', page('/x/', S + '/thue-xe/2026/10/01/bai-a/',
                                                     '<meta http-equiv="refresh" content="0; url=/thue-xe/2026/10/01/bai-a/">'))
        self.sitemap(['/', '/thue-xe/2026/10/01/bai-a/', '/xe-may/bai-b/'])

    def tearDown(self):
        shutil.rmtree(self.src, True)
        shutil.rmtree(self.site, True)

    def post(self, name, permalink, d='_posts'):
        with open(os.path.join(self.src, d, name), 'w', encoding='utf-8') as f:
            f.write('---\ntitle: x\npermalink: %s\n---\nnoi dung\n' % permalink)

    def put(self, url, text):
        d = os.path.join(self.site, url.strip('/'))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(text)

    def sitemap(self, urls, host=S):
        with open(os.path.join(self.site, 'sitemap.xml'), 'w', encoding='utf-8') as f:
            f.write('<urlset>%s</urlset>' % ''.join('<url><loc>%s%s</loc></url>' % (host, u) for u in urls))

    def errs(self):
        return C.check(self.site, self.src)['errors']

    def test_clean_site(self):
        self.assertEqual(self.errs(), [])
        self.assertEqual(C.main(['--site', self.site, '--root', self.src]), 0)

    def test_each_failure_is_named(self):
        cases = {
            'permalink trùng': lambda: self.post('c.md', '/xe-may/bai-b/', 'redirects/slug-d'),
            'ngoài [a-z0-9-/]': lambda: self.post('d.md', '/xe-may/Bai-Đẹp/'),
            '<loc> trùng': lambda: self.sitemap(['/', '/', '/xe-may/bai-b/']),
            'sai host': lambda: self.sitemap(['/'], host='https://thuexemayhanoi.github.io'),
            'không ASCII': lambda: (self.put('/xe-may/bài/', page('/xe-may/bài/')), self.sitemap(['/xe-may/bài/'])),
            'cần đúng một, tự trỏ': lambda: self.put('/xe-may/bai-b/', page('/xe-may/bai-b/', S + '/khac/')),
            'là trang chuyển hướng': lambda: self.put('/xe-may/bai-b/', page('/xe-may/bai-b/', extra='<meta http-equiv="refresh" content="0; url=/">')),
            'có noindex': lambda: self.put('/xe-may/bai-b/', page('/xe-may/bai-b/', extra='<meta name="robots" content="noindex">')),
            'nhiều trang cùng canonical': lambda: self.put('/xe-may/bai-b-ban-sao/', page('/xe-may/bai-b/')),
        }
        for needle, mutate in cases.items():
            self.tearDown()
            self.setUp()
            mutate()
            errs = self.errs()
            self.assertTrue(any(needle in e for e in errs), (needle, errs))
        self.assertEqual(C.main(['--site', self.site, '--root', self.src]), 1)

    def test_missing_inputs(self):
        self.assertEqual(C.main(['--site', os.path.join(self.site, 'khong-co'), '--root', self.src]), 2)
        os.remove(os.path.join(self.site, 'sitemap.xml'))
        self.assertEqual(C.main(['--site', self.site, '--root', self.src]), 2)


if __name__ == '__main__':
    unittest.main()
