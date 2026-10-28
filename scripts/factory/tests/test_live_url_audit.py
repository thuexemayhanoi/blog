#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test scripts/seo/live-url-audit.py (Issue #77) trên máy chủ HTTP cục bộ — OFFLINE.

Chứng minh:
  - crawl: đọc đúng mã HTTP thật (404, 301 không bị theo), liên kết tương đối, bỏ mailto/#/ngoài
    miền, phát hiện soft 404, canonical lệch/thiếu, ghi CSV `source,target,status,fix,retest`;
  - infra: nhận diện lớp edge từ header (cloudflare / github-pages) và bản đồ OLD/NEW mẫu;
  - redirects: OLD phải 301/308 một bước tới đúng NEW (giữ query) và NEW 200 canonical tự trỏ,
    nếu không thì all_ok=False (bằng chứng cho công cụ migration);
  - an toàn: từ chối origin lạ; công cụ KHÔNG bao giờ gửi method ngoài GET/HEAD;
  - v2: URL có dấu cách/Unicode không làm sập crawl (mã hóa %XX), phân tích meta refresh, tài nguyên 404, tiền
    tố /blog/, trang mồ côi, canonical trùng, trang chuyển hướng trong sitemap, liên kết vào trang chuyển
    hướng, kiểm kê CSV/JSON, chế độ `stubs` (HTTP 200 + meta refresh 0s + canonical, KHÔNG phải 301).

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
        self.assertEqual(rows[('/a/', '/missing/', '404')][3], 'restore_url_or_update_link_or_redirect_to_equivalent')
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


# ----------------------------------------------------------------------------- v2: bảng route tổng quát

def html_page(title, canonical='', body_html='', head_extra='', words=80):
    return ('<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>%s</title>%s%s</head>'
            '<body><h1>%s</h1>%s<p>%s</p></body></html>'
            % (title, ('<link rel="canonical" href="%s">' % canonical) if canonical else '', head_extra, title,
               body_html, ' '.join(['noidung'] * words))).encode('utf-8')


class RetiredStubProbeTest(unittest.TestCase):
    """Dòng RETIRED (URL cũ đã gỡ theo quyết định chủ 2026-10-27): URL cũ PHẢI 404/410 và không nằm trong sitemap; URL mới kiểm như
    dòng MIGRATED. Dòng MIGRATED vẫn kiểm trang chuyển hướng như cũ."""

    @classmethod
    def setUpClass(cls):
        def build(o):
            r = {}
            r['/hub/bai-moi/'] = (200, html_page('Bai moi', o + '/hub/bai-moi/', '<a href="/">x</a>', words=120), {})
            r['/hub/moi-2/'] = (200, html_page('Bai moi 2', o + '/hub/moi-2/', '<a href="/">x</a>', words=120), {})
            r['/hub/cu-con-stub/'] = (200, stub_html('/hub/moi-2/', o + '/hub/moi-2/'), {})
            r['/hub/cu-van-stub/'] = (200, stub_html('/hub/bai-moi/', o + '/hub/bai-moi/'), {})
            r['/sitemap.xml'] = (200, sitemap_xml(o, ['/hub/bai-moi/', '/hub/moi-2/', '/hub/cu-trong-sm/']), {})
            return r

        cls.srv = TableSrv(build)
        cls.tmp = tempfile.mkdtemp(prefix='retiredaudit-')
        cls.reg = os.path.join(cls.tmp, 'registry.csv')
        with open(cls.reg, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(['article_id', 'old_url', 'new_url', 'status'])
            w.writerow(['BLG-1', '/hub/cu-da-go/', '/hub/bai-moi/', 'RETIRED'])        # 404 + mới 200 = đạt
            w.writerow(['BLG-2', '/hub/cu-van-stub/', '/hub/bai-moi/', 'RETIRED'])     # đã gỡ nhưng vẫn phục vụ 200
            w.writerow(['BLG-3', '/hub/cu-trong-sm/', '/hub/bai-moi/', 'RETIRED'])     # 404 nhưng còn trong sitemap
            w.writerow(['BLG-4', '/hub/cu-con-stub/', '/hub/moi-2/', 'MIGRATED'])      # trang chuyển hướng hợp lệ

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()

    def test_retired_rows(self):
        ev = AUDIT.stubs(self.srv.origin, self.reg, 0, 0, 2, 5)
        self.assertEqual((ev['registry_total'], ev['retired_total']), (4, 3))
        by = {r['article_id']: r for r in ev['rows']}
        self.assertTrue(by['BLG-1']['ok'], by['BLG-1']['problems'])
        self.assertEqual(by['BLG-1']['old_status'], 404)
        self.assertEqual(by['BLG-2']['problems'], ['RETIRED_OLD_STATUS_200'])
        self.assertEqual(by['BLG-3']['problems'], ['OLD_STILL_IN_SITEMAP'])
        self.assertTrue(by['BLG-4']['ok'], by['BLG-4']['problems'])
        self.assertEqual(ev['ok'], 2)
        self.assertFalse(ev['all_ok'])
        self.assertEqual(len(AUDIT.load_registry(self.reg)), 1)           # crawl: chỉ dòng còn trang chuyển hướng


class TableSrv:
    """Máy chủ cục bộ theo bảng route: path đã giải mã (unquote) -> (status, body, headers)."""

    def __init__(self, build):
        self.methods, self.paths = [], []
        outer = self
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
        self.port = self.httpd.server_address[1]
        self.origin = 'http://127.0.0.1:%d' % self.port
        self.routes = build(self.origin)

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _go(self, head):
                import urllib.parse as up
                outer.methods.append(self.command)
                raw = self.path.partition('?')[0]
                outer.paths.append(raw)
                key = up.unquote(raw)
                status, body, headers = outer.routes.get(key, (404, b'not found', {}))
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                if not head:
                    self.wfile.write(body)

            def do_GET(self):
                self._go(False)

            def do_HEAD(self):
                self._go(True)

        self.httpd.RequestHandlerClass = H
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def sitemap_xml(origin, paths):
    locs = ''.join('<url><loc>%s%s</loc></url>' % (origin, p) for p in paths)
    return ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>'
            % locs).encode()


def stub_html(target, canonical, delay=0, extra=''):
    return ('<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><title>Dang chuyen huong</title>'
            '<link rel="canonical" href="%s"><meta http-equiv="refresh" content="%s; url=%s">%s</head>'
            '<body><p><a href="%s">Trang da chuyen</a></p></body></html>'
            % (canonical, delay, target, extra, target)).encode('utf-8')


class RobustCrawlTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        def build(o):
            r = {}
            r['/sitemap.xml'] = (200, sitemap_xml(o, ['/', '/hub/', '/chia sẻ/2026/09/18/bai-cu/', '/dup1/', '/dup2/',
                                                       '/stub-in-map/', '/lonely/', '/missing-asset/']), {})
            r['/'] = (200, html_page('Home', o + '/', '<a href="/hub/">hub</a><a href="/chia sẻ/2026/09/18/bai-cu/">cu</a>'
                                     '<a href="/old-stub/">stub</a><a href="/blog/legacy/">legacy</a>'
                                     '<a href="/dup1/">d1</a><a href="/dup2/">d2</a><a href="/stub-in-map/">sm</a>'
                                     '<a href="/missing-asset/">ma</a>'), {})
            r['/hub/'] = (200, html_page('Hub', o + '/hub/', '<a href="/">home</a>'), {})
            r['/chia sẻ/2026/09/18/bai-cu/'] = (200, html_page('Bai cu', o + '/chia%20s%E1%BA%BB/2026/09/18/bai-cu/',
                                                                  '<a href="/">home</a>'), {})
            r['/dup1/'] = (200, html_page('Dup 1', o + '/dup1/', '<a href="/">home</a>'), {})
            r['/dup2/'] = (200, html_page('Dup 2', o + '/dup1/', '<a href="/">home</a>'), {})
            r['/stub-in-map/'] = (200, stub_html('/hub/', o + '/hub/'), {})
            r['/old-stub/'] = (200, stub_html('/hub/', o + '/hub/'), {})
            r['/lonely/'] = (200, html_page('Lonely', o + '/lonely/'), {})
            r['/missing-asset/'] = (200, html_page('MA', o + '/missing-asset/', '<img src="/img/gone.png">'
                                                    '<script src="/js/ok.js"></script>', '<link rel="stylesheet" href="/css/x.css">'),
                                    {})
            r['/js/ok.js'] = (200, b'//js', {})
            return r

        cls.srv = TableSrv(build)
        cls.res = AUDIT.crawl(cls.srv.origin, workers=4, timeout=5, max_pages=0, max_sources=25,
                              registry_path=os.path.join(tempfile.mkdtemp(), 'none.csv'))

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()

    def inv(self, etype):
        return [r for r in self.res['inventory'] if r['error_type'] == etype]

    def test_space_and_unicode_url_is_measured_not_fatal(self):
        # trước v2 URL này ném InvalidURL làm sập cả lượt; nay được mã hóa %XX và đo được
        self.assertIn('/chia%20s%E1%BA%BB/2026/09/18/bai-cu/', self.srv.paths)
        self.assertEqual(self.res['pages'][self.srv.origin + '/chia sẻ/2026/09/18/bai-cu/']['status'], 200)
        self.assertTrue(any(r['error_type'] == 'NON_ASCII_PATH' and 'chia' in r['url'] for r in self.res['inventory']))

    def test_fetch_never_raises(self):
        for bad in ('http://127.0.0.1:1/\x00x', 'http://127.0.0.1:1/' + 'a' * 70000, 'not a url'):
            r = AUDIT.fetch(bad, 'GET', 2, retries=0)
            self.assertEqual(r['status'], 0)
            self.assertTrue(r['error'])

    def test_encode_url_keeps_existing_percent_escapes(self):
        self.assertEqual(AUDIT.encode_url('http://h/chia sẻ/a b/?q=1 2#f'), 'http://h/chia%20s%E1%BA%BB/a%20b/?q=1%202')
        self.assertEqual(AUDIT.encode_url('http://h/a%20b/'), 'http://h/a%20b/')

    def test_meta_refresh_page_in_sitemap_is_flagged(self):
        self.assertEqual([r['url'] for r in self.inv('STUB_IN_SITEMAP')], [self.srv.origin + '/stub-in-map/'])
        self.assertEqual(self.inv('STUB_IN_SITEMAP')[0]['final_url'], self.srv.origin + '/hub/')

    def test_link_to_redirect_page_reported_with_destination(self):
        rows = [r for r in self.res['rows'] if r[2] == 'LINK_TO_REDIRECT_PAGE']
        self.assertEqual([(r[0].replace(self.srv.origin, ''), r[1].replace(self.srv.origin, '')) for r in rows],
                         [('/', '/old-stub/')])
        self.assertEqual(rows[0][3], 'update_link_to:' + self.srv.origin + '/hub/')

    def test_asset_404_legacy_prefix_duplicate_canonical_orphan(self):
        self.assertEqual(sorted(r['url'] for r in self.inv('ASSET_404')),
                         sorted([self.srv.origin + '/img/gone.png', self.srv.origin + '/css/x.css']))
        self.assertTrue(any(r[2] == 'LEGACY_BASE_PATH' and r[1] == '/blog/legacy/' for r in self.res['rows']))
        dup = self.res['duplicate_canonical']
        self.assertEqual(sorted(u.replace(self.srv.origin, '') for u in dup[self.srv.origin + '/dup1/']),
                         ['/dup1/', '/dup2/'])
        # trang chuyển hướng nằm trong sitemap có canonical trùng trang đích -> cũng là nhóm trùng (đúng)
        self.assertEqual(len(dup), 2)
        self.assertEqual(sorted(u.replace(self.srv.origin, '') for u in self.res['orphans']),
                         ['/lonely/'])

    def test_inventory_has_one_row_per_sitemap_url_and_files(self):
        sm_rows = {r['url'] for r in self.res['inventory'] if r['kind'] == 'sitemap'}
        self.assertEqual(sm_rows, set(self.res['sitemap_set']))
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, 'nested', 'inv')
            doc = AUDIT.write_inventory(base, self.res)
            with open(base + '.csv', encoding='utf-8', newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(list(rows[0].keys()), AUDIT.INVENTORY_COLUMNS)
            with open(base + '.json', encoding='utf-8') as f:
                self.assertEqual(json.load(f)['schema'], AUDIT.INVENTORY_SCHEMA)
        self.assertEqual(len(rows), len(doc['rows']))

    def test_summary_counts(self):
        s = AUDIT.summarize(self.res)
        self.assertEqual(s['stub_pages_in_sitemap'], 1)
        self.assertEqual(s['links_to_redirect_pages'], 1)
        self.assertEqual(s['asset_failing'], 2)
        self.assertEqual(s['duplicate_canonical_groups'], 2)

    def test_dump_blob_roundtrip(self):
        import base64
        import gzip
        import io
        buf = io.StringIO()
        AUDIT.dump_blob('X', {'a': 'tiếng Việt', 'n': [1, 2]}, out=buf)
        lines = buf.getvalue().splitlines()
        self.assertTrue(lines[0].startswith('X_BEGIN sha256='))
        self.assertEqual(lines[-1], 'X_END')
        raw = base64.b64decode(''.join(lines[1:-1]))
        self.assertIn(hashlib_sha(raw), lines[0])
        self.assertEqual(json.loads(gzip.decompress(raw)), {'a': 'tiếng Việt', 'n': [1, 2]})


def hashlib_sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


class StubProbeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        def build(o):
            r = {}
            new_ok = html_page('Bai moi', o + '/hub/bai-moi/', '<a href="/">x</a>', words=120)
            r['/hub/bai-moi/'] = (200, new_ok, {})
            r['/hub/bai-cu/'] = (200, stub_html('/hub/bai-moi/', o + '/hub/bai-moi/'), {})
            # sai: delay 5s, canonical sai, nằm trong sitemap, đích 404, chuỗi
            r['/hub/cu-delay/'] = (200, stub_html('/hub/bai-moi/', o + '/hub/bai-moi/', delay=5), {})
            r['/hub/cu-canon/'] = (200, stub_html('/hub/bai-moi/', o + '/hub/khac/'), {})
            r['/hub/cu-404/'] = (200, stub_html('/hub/khong-co/', o + '/hub/khong-co/'), {})
            r['/hub/cu-chain/'] = (200, stub_html('/hub/bai-cu/', o + '/hub/bai-cu/'), {})
            r['/hub/cu-200/'] = (200, html_page('Van la bai', o + '/hub/cu-200/'), {})
            r['/hub/cu-trong-sitemap/'] = (200, stub_html('/hub/bai-moi/', o + '/hub/bai-moi/'), {})
            r['/sitemap.xml'] = (200, sitemap_xml(o, ['/hub/bai-moi/', '/hub/cu-trong-sitemap/']), {})
            return r

        cls.srv = TableSrv(build)
        cls.tmp = tempfile.mkdtemp(prefix='stubaudit-')
        cls.reg = os.path.join(cls.tmp, 'registry.csv')
        pairs = [('BLG-1', '/hub/bai-cu/', '/hub/bai-moi/'), ('BLG-2', '/hub/cu-delay/', '/hub/bai-moi/'),
                 ('BLG-3', '/hub/cu-canon/', '/hub/bai-moi/'), ('BLG-4', '/hub/cu-404/', '/hub/khong-co/'),
                 ('BLG-5', '/hub/cu-chain/', '/hub/bai-cu/'), ('BLG-6', '/hub/cu-200/', '/hub/bai-moi/'),
                 ('BLG-7', '/hub/cu-trong-sitemap/', '/hub/bai-moi/')]
        with open(cls.reg, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(['article_id', 'old_url', 'new_url', 'status'])
            for p in pairs:
                w.writerow(list(p) + ['MIGRATED'])
            w.writerow(['BLG-8', '/x/', '/y/', 'PENDING'])     # không phải MIGRATED: bị bỏ qua

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()

    def test_each_failure_mode_is_named(self):
        ev = AUDIT.stubs(self.srv.origin, self.reg, 0, 0, 2, 5)
        self.assertEqual(ev['schema'], AUDIT.STUB_EVIDENCE_SCHEMA)
        self.assertIn('khong phai HTTP 301', ev['kind'])
        self.assertEqual(ev['registry_total'], 7)
        by = {r['article_id']: r for r in ev['rows']}
        self.assertTrue(by['BLG-1']['ok'], by['BLG-1']['problems'])
        self.assertEqual(by['BLG-1']['old_status'], 200)          # 200 + meta refresh, không phải 3xx
        self.assertIn('OLD_REFRESH_DELAY_5.0', by['BLG-2']['problems'])
        self.assertIn('OLD_CANONICAL_NOT_NEW', by['BLG-3']['problems'])
        self.assertIn('NEW_STATUS_404', by['BLG-4']['problems'])
        self.assertIn('NEW_IS_REDIRECT_PAGE', by['BLG-5']['problems'])
        self.assertIn('NEW_IS_ALSO_OLD_CHAIN', by['BLG-5']['problems'])
        self.assertIn('OLD_NO_META_REFRESH', by['BLG-6']['problems'])
        self.assertIn('OLD_STILL_IN_SITEMAP', by['BLG-7']['problems'])
        self.assertFalse(ev['all_ok'])
        self.assertEqual(ev['ok'], 1)

    def test_batch_slice_and_all_ok(self):
        ev = AUDIT.stubs(self.srv.origin, self.reg, 0, 1, 1, 5)
        self.assertEqual(ev['count'], 1)
        self.assertTrue(ev['all_ok'])

    def test_cli_exit_codes(self):
        out = os.path.join(self.tmp, 'ev.json')
        self.assertEqual(AUDIT.main(['stubs', '--origin', self.srv.origin, '--registry', self.reg, '--start', '0',
                                     '--limit', '1', '--out', out]), 0)
        with open(out, encoding='utf-8') as f:
            self.assertTrue(json.load(f)['all_ok'])
        self.assertEqual(AUDIT.main(['stubs', '--origin', self.srv.origin, '--registry', self.reg, '--limit', '0']), 1)

    def test_only_get_and_head(self):
        self.assertTrue(set(self.srv.methods) <= {'GET', 'HEAD'})



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
