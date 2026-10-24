#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test scripts/seo/live-url-audit.py (Issue #77) trên máy chủ HTTP cục bộ — OFFLINE.

Chứng minh:
  - crawl: đọc đúng mã HTTP thật (404, 301 không bị theo), liên kết tương đối, bỏ mailto/#/ngoài
    miền, phát hiện soft 404, canonical lệch/thiếu, ghi CSV `source,target,status,fix,retest`;
  - infra: nhận diện lớp edge từ header (cloudflare / github-pages) và bản đồ OLD/NEW mẫu;
  - redirects: OLD phải 301/308 một bước tới đúng NEW (giữ query) và NEW 200 canonical tự trỏ,
    nếu không thì all_ok=False (bằng chứng cho công cụ migration);
  - an toàn: từ chối origin lạ; công cụ KHÔNG bao giờ gửi method ngoài GET/HEAD.

Chạy: python3 scripts/factory/tests/test_live_url_audit.py
"""
import csv
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load():
    spec = importlib.util.spec_from_file_location('live_url_audit_t', os.path.join(ROOT, 'scripts/seo/live-url-audit.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


AUDIT = load()


def page(title, canonical, links=(), extra=''):
    body = ''.join('<a href="%s">x</a>' % l for l in links)
    return ('<!doctype html><html><head><title>%s</title>%s%s</head><body><h1>%s</h1>%s%s</body></html>'
            % (title, ('<link rel="canonical" href="%s">' % canonical) if canonical else '', extra, title, body,
               'x' * 600)).encode('utf-8')


def make_handler(port, server_headers, methods):
    base = 'http://127.0.0.1:%d' % port

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body=b'', headers=None, head=False):
            self.send_response(code)
            for k, v in list(server_headers.items()) + list((headers or {}).items()):
                self.send_header(k, v)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def _route(self, head):
            methods.append(self.command)
            path, _, query = self.path.partition('?')
            if path == '/sitemap.xml':
                locs = ''.join('<url><loc>%s%s</loc></url>' % (base, p)
                               for p in ('/a/', '/b/', '/soft/', '/gone/', '/redir/', '/c/', '/old-ok/', '/new-ok/'))
                xml = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>'
                       % locs).encode()
                return self._send(200, xml, head=head)
            if path == '/a/':
                return self._send(200, page('Trang A', base + '/a/', ['/b/', '../b/', '/missing/', '/moved/', '/old-ok/',
                                                                      'mailto:a@b.c', '#top', 'https://example.com/x',
                                                                      '/b/#frag']), head=head)
            if path == '/b/':
                return self._send(200, page('Trang B', base + '/b/', ['/a/']), head=head)
            if path == '/c/':
                return self._send(200, page('Trang C', base + '/a/', []), head=head)
            if path == '/soft/':
                return self._send(200, ('<html><head><title>404 Không tìm thấy trang</title></head><body>?</body></html>'
                                        ).encode(), head=head)
            if path in ('/redir/', '/moved/'):
                return self._send(301, b'', {'Location': '/b/'}, head=head)
            if path == '/old-ok/':
                return self._send(301, b'', {'Location': '/new-ok/' + ('?' + query if query else '')}, head=head)
            if path == '/new-ok/':
                return self._send(200, page('Mới', base + '/new-ok/', []), head=head)
            if path == '/old-bad/':
                return self._send(200, page('Cũ', base + '/old-bad/', []), head=head)
            return self._send(404, b'not found', head=head)

        def do_GET(self):
            self._route(False)

        def do_HEAD(self):
            self._route(True)

    return H


class Srv:
    def __init__(self, server_headers=None):
        self.methods = []
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
        self.port = self.httpd.server_address[1]
        self.httpd.RequestHandlerClass = make_handler(self.port, server_headers or {}, self.methods)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.origin = 'http://127.0.0.1:%d' % self.port

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class CrawlTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = Srv()
        cls.res = AUDIT.crawl(cls.srv.origin, workers=4, timeout=5, max_pages=0, max_sources=25)

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()

    def rows(self):
        return {(r[0].replace(self.srv.origin, ''), r[1].replace(self.srv.origin, ''), str(r[2])): r
                for r in self.res['rows']}

    def test_real_http_codes_and_no_redirect_following(self):
        rows = self.rows()
        self.assertIn(('sitemap.xml', '/gone/', '404'), rows)
        r = rows[('sitemap.xml', '/redir/', '301')]
        self.assertEqual(r[3], 'update_link_to:/b/')
        self.assertEqual(self.res['pages'][self.srv.origin + '/redir/']['status'], 301)

    def test_internal_link_graph_targets(self):
        rows = self.rows()
        self.assertIn(('/a/', '/missing/', '404'), rows)
        self.assertEqual(rows[('/a/', '/missing/', '404')][3], 'restore_url_or_update_link_or_301_to_equivalent')
        self.assertIn(('/a/', '/moved/', '301'), rows)
        # liên kết tương đối ../b/ và /b/#frag chuẩn hóa về /b/ (200) nên không phải lỗi
        self.assertNotIn(('/a/', '/b/', '200'), rows)
        for bad in ('mailto', 'example.com', '#top'):
            self.assertFalse(any(bad in r[1] for r in self.res['rows']), bad)

    def test_soft_404_and_canonical_checks(self):
        rows = self.rows()
        self.assertIn(('sitemap.xml', '/soft/', '200-soft404'), rows)
        self.assertIn(('/c/', '/a/', 'CANONICAL_MISMATCH'), rows)
        # trang soft 404 không có canonical -> CANONICAL_MISSING (ghi nhận riêng, không nhầm với mismatch)
        self.assertIn(('/soft/', '', 'CANONICAL_MISSING'), rows)

    def test_summary_and_csv(self):
        s = AUDIT.summarize(self.res)
        self.assertEqual(s['sitemap_urls'], 8)
        self.assertEqual(s['sitemap_status_counts']['404'], 1)
        self.assertEqual(s['sitemap_status_counts']['301'], 2)   # /redir/ và /old-ok/
        self.assertGreaterEqual(s['failing_link_targets'], 2)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'x', 'audit.csv')
            AUDIT.write_csv(p, self.res['rows'])
            with open(p, encoding='utf-8', newline='') as f:
                rows = list(csv.reader(f))
        self.assertEqual(rows[0], ['source', 'target', 'status', 'fix', 'retest'])
        self.assertTrue(all(len(r) == 5 for r in rows))

    def test_only_get_and_head_are_used(self):
        self.assertTrue(set(self.srv.methods) <= {'GET', 'HEAD'}, set(self.srv.methods))

    def test_max_sources_caps_rows_per_target(self):
        res = AUDIT.crawl(self.srv.origin, workers=2, timeout=5, max_pages=0, max_sources=1)
        missing = [r for r in res['rows'] if r[1].endswith('/missing/')]
        self.assertEqual(len(missing), 1)


class InfraTest(unittest.TestCase):

    def test_cloudflare_detected_from_headers(self):
        srv = Srv({'server': 'cloudflare', 'cf-ray': 'abc-HAN'})
        try:
            out = AUDIT.infra(srv.origin, 5)
        finally:
            srv.close()
        self.assertEqual(out['edge'], 'cloudflare')
        self.assertIsNone(out['per_path_301_possible_without_new_infra'])
        self.assertIn('cf-ray', out['probes'][0]['headers'])

    def test_github_pages_detected_and_blocks_per_path_301(self):
        srv = Srv({'server': 'GitHub.com', 'x-github-request-id': 'AAAA:1'})
        try:
            out = AUDIT.infra(srv.origin, 5)
        finally:
            srv.close()
        self.assertEqual(out['edge'], 'github-pages')
        self.assertFalse(out['per_path_301_possible_without_new_infra'])

    def test_edge_verdict_unknown(self):
        self.assertEqual(AUDIT.edge_verdict([{'server': 'nginx'}]), 'unknown')


class RedirectProbeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.srv = Srv()
        cls.tmp = tempfile.mkdtemp(prefix='liveaudit-')
        cls.map = os.path.join(cls.tmp, 'map.csv')
        with open(cls.map, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(['article_id', 'old_url', 'new_url'])
            w.writerow(['BLG-1', '/old-ok/', '/new-ok/'])
            w.writerow(['BLG-2', '/old-bad/', '/new-bad/'])

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()

    def test_good_pair_ok_and_bad_pair_not_ok(self):
        ev = AUDIT.redirects(self.srv.origin, 0, 10, 2, 5, self.map)
        self.assertEqual(ev['schema'], 'slug-redirect-evidence/1')
        self.assertEqual(ev['count'], 2)
        self.assertFalse(ev['all_ok'])
        good, bad = ev['rows']
        self.assertTrue(good['ok'] and good['old_ok'] and good['query_preserved'] and good['new_ok'])
        self.assertEqual(good['old_status'], 301)
        self.assertFalse(bad['ok'])
        self.assertEqual(bad['old_status'], 200)      # 200 không được coi là redirect
        self.assertEqual(bad['new_status'], 404)

    def test_all_ok_only_when_every_row_ok(self):
        ev = AUDIT.redirects(self.srv.origin, 0, 1, 1, 5, self.map)
        self.assertTrue(ev['all_ok'])
        self.assertEqual(ev['ok'], 1)

    def test_empty_batch_is_not_all_ok(self):
        ev = AUDIT.redirects(self.srv.origin, 5, 10, 1, 5, self.map)
        self.assertEqual(ev['count'], 0)
        self.assertFalse(ev['all_ok'])


class GuardTest(unittest.TestCase):

    def test_foreign_origin_refused(self):
        self.assertFalse(AUDIT.origin_ok('https://example.com'))
        self.assertFalse(AUDIT.origin_ok('http://blog.thuexemaynguyentu.com'))
        self.assertTrue(AUDIT.origin_ok(AUDIT.PRODUCTION))
        self.assertTrue(AUDIT.origin_ok('http://127.0.0.1:8000'))
        with self.assertRaises(SystemExit):
            AUDIT.main(['crawl', '--origin', 'https://example.com'])

    def test_sitemap_foreign_host_rejected(self):
        xml = b'<urlset><url><loc>https://evil.example/a/</loc></url></urlset>'
        with self.assertRaises(ValueError):
            AUDIT.parse_sitemap(xml, AUDIT.PRODUCTION)

    def test_norm_target(self):
        o = AUDIT.PRODUCTION
        p = o + '/x/y/'
        self.assertEqual(AUDIT.norm_target('../z/#top', p, o), o + '/x/z/')
        self.assertEqual(AUDIT.norm_target('/a/?q=1', p, o), o + '/a/?q=1')
        self.assertIsNone(AUDIT.norm_target('https://example.com/', p, o))
        self.assertIsNone(AUDIT.norm_target('mailto:a@b.c', p, o))
        self.assertIsNone(AUDIT.norm_target('#frag', p, o))

    def test_blocked_exit_when_sitemap_unreachable(self):
        srv = Srv()
        origin = srv.origin
        srv.close()
        self.assertEqual(AUDIT.main(['crawl', '--origin', origin, '--timeout', '2']), 2)


if __name__ == '__main__':
    unittest.main(verbosity=1)
