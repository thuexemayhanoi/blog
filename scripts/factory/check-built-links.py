#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHECK LIÊN KẾT NỘI BỘ TRÊN SITE ĐÃ BUILD — thuexemayhanoi/blog.

Kiểm tra TOÀN BỘ HTML sau Jekyll build (không chỉ _posts/matrix):
homepage, menu, footer, trang tĩnh, parent/child hub, listing/pagination,
bài legacy, bài factory, breadcrumb, related articles, CTA, canonical/og:url,
JSON-LD BreadcrumbList, asset nội bộ — mọi href/src/srcset đều phải resolve.

Hai chế độ (chọn một):
  --site DIR   Parse cây _site do `jekyll build` sinh (deterministic, dùng CI:
               actions/jekyll-build-pages@v1 với destination ./_site).
  --live URL   Fetch HTML đã build từ GitHub Pages (sitemap.xml + từng trang)
               — dùng khi môi trường không có Ruby/Jekyll. Kết quả phụ thuộc
               cache CDN tại thời điểm chạy (404 cũ có thể do cache deploy —
               chạy lại sau khi deploy xong, ưu tiên URL dạng /index.html).

Quy tắc URL (đọc trực tiếp từ _config.yml):
  - Hỗ trợ cả project site có baseurl và custom domain có baseurl rỗng.
  - Với custom domain, mọi root-relative link bắt đầu bằng / và resolve trực tiếp.
  - Với project site, vẫn phát hiện double/missing baseurl như trước.

Legacy Unicode URL (/blog/du lịch/..., /blog/kinh nghiệm/...):
  - percent-decode trước khi map filesystem/live route — KHÔNG rewrite ascii.
  - link rewrite sai (/blog/du-lich/ khi route thật /blog/du%20l%E1%BB%8Bch/)
    tự thành INTERNAL_404 vì route không tồn tại.

Phân loại lỗi:
  INTERNAL_404          link nội bộ trỏ route không tồn tại sau build
  DOUBLE_BASEURL        URL chứa /blog/blog/ (baseurl bị lặp)
  MISSING_BASEURL       link root-relative thiếu /blog nhưng route thật có
  BROKEN_ASSET_INTERNAL asset nội bộ (css/js/svg/ảnh/xml) không tồn tại
  REDIRECT_LOOP         meta-refresh trỏ lại chính trang / double baseurl
  MATRIX_BAD_ROUTE      internal_links của content-matrix không resolve

Exit: 0 = PASS (0 lỗi), 1 = FAIL, 2 = BLOCKED (thiếu _site / lỗi mạng).

Chạy:
  python3 scripts/factory/check-built-links.py --site ./_site
  python3 scripts/factory/check-built-links.py --live https://blog.thuexemaynguyentu.com/
"""
import argparse
import csv
import os
import posixpath
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ASSET_EXT = ('.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.ico',
             '.xml', '.txt', '.webmanifest', '.woff', '.woff2', '.mp4', '.pdf')


def _site_baseurl():
    cfg = open(os.path.join(ROOT, '_config.yml'), encoding='utf-8').read()
    m = re.search(r'^baseurl:\s*["\']?([^"\'\s#]+)', cfg, re.M)
    if not m or not m.group(1).startswith('/'):
        raise SystemExit('QA: không đọc được baseurl /blog từ _config.yml')
    return m.group(1).rstrip('/')


BASEURL = _site_baseurl()
HOST = 'https://thuexemayhanoi.github.io'
SITE_URL = HOST + BASEURL      # https://thuexemayhanoi.github.io/blog


# ------------------------------------------------------------------ trích link

class LinkCollector(HTMLParser):
    """Thu mọi href/src/srcset/content (canonical, og:*, twitter:*) của 1 trang."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and a.get('href'):
            self.links.append(a['href'].strip())
        elif tag in ('link', 'script', 'img', 'iframe', 'source'):
            if a.get('href'):
                self.links.append(a['href'].strip())
            if a.get('src'):
                self.links.append(a['src'].strip())
            if a.get('srcset'):
                for part in a['srcset'].split(','):
                    u = part.strip().split(' ')[0]
                    if u:
                        self.links.append(u)
        elif tag == 'meta':
            if (a.get('http-equiv', '').lower() == 'refresh'
                    and a.get('content')):
                m = re.match(r'\s*(\d+)\s*;\s*url\s*=\s*(.+)\s*$',
                             a['content'], re.I)
                if m:
                    self.links.append('refresh:' + m.group(2).strip('\'"'))
            if a.get('content') and (a.get('property') in ('og:url', 'og:image')
                                     or a.get('name') in ('twitter:image',)):
                self.links.append(a['content'].strip())

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


JSONLD_ITEM = re.compile(r'"item"\s*:\s*"([^"]+)"')


def collect_links(html_text):
    p = LinkCollector()
    try:
        p.feed(html_text)
    except Exception:
        pass
    return list(p.links) + JSONLD_ITEM.findall(html_text)


# ------------------------------------------------------------------ chuẩn hoá link

SKIP_PREFIX = ('#', 'mailto:', 'tel:', 'javascript:', 'data:', 'sms:', 'zalo:')


def classify(link):
    """-> (status, path) với status in:
    skip | double | nobase | relative | internal"""
    link = (link or '').strip()
    if link.startswith('refresh:'):
        link = link[len('refresh:'):]
        is_refresh = True
    else:
        is_refresh = False
    if not link or link.startswith(SKIP_PREFIX):
        return 'skip', None, False
    if link.startswith(('http://', 'https://')):
        pr = urllib.parse.urlsplit(link)
        if (pr.scheme, pr.netloc) != ('https', HOST[8:]):
            return 'skip', None, False
        path = pr.path
    else:
        path = link
    path = path.split('#', 1)[0].split('?', 1)[0]
    if not path or path.startswith('//'):
        return 'skip', None, False
    # percent-decode sớm: mọi so khớp route/filesystem về sau đều trên dạng
    # đã decode (URL legacy Unicode: /kinh%20nghi%E1%BB%87m/ -> /kinh nghiệm/)
    path = urllib.parse.unquote(path)
    if BASEURL:
        if path.startswith(BASEURL + BASEURL + '/'):
            return 'double', path, is_refresh
        if path == BASEURL or path.startswith(BASEURL + '/'):
            return 'internal', path, is_refresh
        if path.startswith('/'):
            return 'nobase', path, is_refresh
    elif path.startswith('/'):
        return 'internal', path, is_refresh
    return 'relative', path, is_refresh


def candidates(path):
    """Các dạng path ứng viên khi tìm route (path đã percent-decode)."""
    out = [path]
    if not path.endswith('/'):
        out.append(path + '/')
    else:
        out.append(path.rstrip('/'))
    return out


def is_asset(path):
    ext = posixpath.splitext(path)[1].lower()
    return ext in ASSET_EXT


# ------------------------------------------------------------------ kiểm 1 trang

def check_page(route, html_text, resolver, findings, register=None):
    """resolver(path_dequoted) -> True nếu route tồn tại trong cây đã build.
    register(path, source) — chế độ live: gom target lạ để HEAD sau."""
    n_links = 0
    for raw in collect_links(html_text):
        status, path, is_refresh = classify(raw)
        if status == 'skip':
            continue
        n_links += 1
        if status == 'relative':
            base_dir = posixpath.dirname(route.rstrip('/') + '/') 
            path = posixpath.normpath(posixpath.join(base_dir, path))
            if not _inside_site(path):
                findings.append((route, raw, path,
                                 'INTERNAL_404: liên kết tương đối thoát khỏi site'))
                continue
        if status == 'double':
            findings.append((route, raw, path,
                             'REDIRECT_LOOP: baseurl %s bị lặp trong URL'
                             % BASEURL if is_refresh else
                             'DOUBLE_BASEURL: baseurl %s bị lặp trong URL' % BASEURL))
            continue
        if status == 'nobase':
            with_base = _with_base(path)
            if resolver(with_base):
                findings.append((route, raw, with_base,
                                 'MISSING_BASEURL: thiếu %s (phải qua relative_url)'
                                 % BASEURL))
            else:
                findings.append((route, raw, with_base,
                                 'INTERNAL_404: route không tồn tại sau build'))
            continue
        # internal
        dec = urllib.parse.unquote(path)
        if resolver(dec):
            if is_refresh and dec.rstrip('/') == route.rstrip('/'):
                findings.append((route, raw, route,
                                 'REDIRECT_LOOP: meta-refresh trỏ lại chính trang'))
            continue
        if register is not None:
            register(dec, route)
        else:
            exp = dec if dec.endswith('/') else dec + '/'
            cause = ('BROKEN_ASSET_INTERNAL: asset không tồn tại trong _site'
                     if is_asset(dec) else
                     'INTERNAL_404: route không tồn tại sau build')
            findings.append((route, raw, exp, cause))
    return n_links


# ------------------------------------------------------------------ chế độ --site

def build_site_index(site_dir):
    """route công khai -> file. Deterministic, chỉ từ cây _site."""
    routes = {}
    for root, dirs, files in os.walk(site_dir):
        dirs[:] = [d for d in dirs if d not in ('.jekyll-cache', '.git')]
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, site_dir).replace(os.sep, '/')
            routes[_with_base(rel)] = full
            if fn == 'index.html':
                routes[_with_base(posixpath.dirname(rel))] = full
            elif fn.endswith('.html'):
                routes[_with_base(rel[: -len('.html')])] = full
    return routes


def run_site(site_dir):
    if not os.path.isdir(site_dir):
        print('BLOCKED: không tìm thấy thư mục _site: %s' % site_dir)
        return None
    routes = build_site_index(site_dir)
    pages, links = 0, 0
    findings = []

    def resolver(p):
        return any(c in routes for c in candidates(p))

    for route in sorted(routes):
        f = routes[route]
        if not f.endswith('.html') or route.endswith('/index.html'):
            continue  # route thư mục (…/) đã phủ route …/index.html
        try:
            html_text = open(f, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        pages += 1
        links += check_page(route, html_text, resolver, findings)
    return pages, links, findings, resolver, routes


# ------------------------------------------------------------------ chế độ --live

def http_get(url, timeout=30):
    req = urllib.request.Request(
        url, headers={'User-Agent': 'factory-link-checker/1.0',
                      'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def run_live(base):
    if not base.endswith('/'):
        base += '/'
    status, sm = http_get(base + 'sitemap.xml')
    if status != 200:
        raise RuntimeError('không fetch được %ssitemap.xml (HTTP %d)'
                           % (base, status))
    locs = re.findall(r'<loc>([^<]+)</loc>', sm.decode('utf-8'))
    live_routes = set()
    for loc in locs:
        path = urllib.parse.urlsplit(loc).path
        path = urllib.parse.unquote(path)
        live_routes.add(path)
        if not path.endswith('/') and '.' not in posixpath.basename(path):
            live_routes.add(path + '/')
    # trang có sitemap:false (404 page) không nằm trong sitemap nhưng là route
    # thật — cho phép resolver kiểm tra thêm khi gặp link (HEAD 1 lần/target).
    probed = {}

    def probe(path):
        if path in probed:
            return probed[path]
        # path dạng '/blog/...' (đã có baseurl) -> URL tuyệt đối từ host root
        url = (HOST + urllib.parse.quote(path, safe='/:')
               if path.startswith('/')
               else base + urllib.parse.quote(path, safe='/:'))
        ok = False
        try:
            st, _ = http_get(url)
            ok = (st == 200)
        except Exception:
            ok = False
        probed[path] = ok
        return ok

    def resolver(p):
        if any(c in live_routes for c in candidates(p)):
            return True
        return probe(p)

    findings = []
    pages, links = 0, 0
    pending = {}   # path -> [source routes] — asset/target lạ, HEAD sau

    def register(path, source):
        pending.setdefault(path, []).append(source)

    for route in sorted(live_routes):
        if not route.endswith('/') or '.' in posixpath.basename(route):
            continue  # chỉ quét HTML page (sitemap có cả file xml...)
        url = HOST + urllib.parse.quote(route, safe='/:')  # route đã có /blog
        try:
            st, body = http_get(url)
        except Exception as e:
            findings.append((route, url, url, 'INTERNAL_404: FETCH_FAIL %s' % e))
            continue
        if st != 200:
            findings.append((route, url, url,
                             'INTERNAL_404: trang trong sitemap trả HTTP %d' % st))
            continue
        pages += 1
        links += check_page(route, body.decode('utf-8', 'replace'),
                            resolver, findings, register)
    # target chưa từng resolve: HEAD rồi phân loại
    for path in sorted(pending):
        ok = probe(path)
        exp = path if path.endswith('/') else path + '/'
        for src in pending[path]:
            if ok:
                continue
            cause = ('BROKEN_ASSET_INTERNAL: asset trả HTTP lỗi'
                     if is_asset(path) else
                     'INTERNAL_404: route không tồn tại trên site đã build')
            findings.append((src, path, exp, cause))
    return pages, links, findings, (lambda p: resolver(p)), live_routes


# ------------------------------------------------------------------ matrix

def check_matrix(resolver, findings):
    """Mọi internal_links của data/content-matrix.csv phải resolve vào cây
    đã build (nguồn QA route của factory — cây thật, không route hư cấu)."""
    mpath = os.path.join(ROOT, 'data', 'content-matrix.csv')
    if not os.path.exists(mpath):
        return 0
    n = 0
    for row in csv.DictReader(open(mpath, encoding='utf-8')):
        for l in (row['internal_links'] or '').split(';'):
            l = l.strip().rstrip(';').strip()
            if not l:
                continue
            expected_prefix = BASEURL + '/' if BASEURL else '/'
            if not l.startswith(expected_prefix):
                findings.append(('matrix:' + row['id'], l, _with_base(l),
                                 'MATRIX_BAD_ROUTE: route phải bắt đầu bằng %s'
                                 % expected_prefix))
                n += 1
                continue
            if not resolver(urllib.parse.unquote(l.split('#')[0])):
                findings.append(('matrix:' + row['id'], l, l,
                                 'MATRIX_BAD_ROUTE: route không tồn tại'))
                n += 1
    return n


# ------------------------------------------------------------------ main

def kind_of(f):
    c = f[3]
    for k in ('DOUBLE_BASEURL', 'MISSING_BASEURL', 'INTERNAL_404',
              'BROKEN_ASSET_INTERNAL', 'REDIRECT_LOOP', 'MATRIX_BAD_ROUTE'):
        if c.startswith(k):
            return k
    return 'OTHER'


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--site', help='thư mục _site sau jekyll build (CI)')
    g.add_argument('--live', help='URL gốc site đã build, ví dụ ' + SITE_URL)
    ap.add_argument('--max-report', type=int, default=200)
    args = ap.parse_args()

    if args.site:
        site_dir = (args.site if os.path.isabs(args.site)
                    else os.path.join(ROOT, args.site))
        out = run_site(site_dir)
        if out is None:
            return 2
        pages, links, findings, resolver, _ = out
        mode = 'site:' + args.site
    else:
        try:
            pages, links, findings, resolver, _ = run_live(args.live)
        except Exception as e:
            print('BLOCKED: không audit được live site (%s)' % e)
            return 2
        mode = 'live:' + args.live

    matrix_bad = check_matrix(resolver, findings)

    counts = {}
    for f in findings:
        k = kind_of(f)
        counts[k] = counts.get(k, 0) + 1

    print('MODE            : %s' % mode)
    print('PAGES_SCANNED   : %d' % pages)
    print('LINKS_SCANNED   : %d' % links)
    for k in ('INTERNAL_404', 'DOUBLE_BASEURL', 'MISSING_BASEURL',
              'BROKEN_ASSET_INTERNAL', 'REDIRECT_LOOP'):
        print('%-15s: %d' % (k, counts.get(k, 0)))
    print('MATRIX_BAD_ROUTE: %d' % matrix_bad)
    print()
    for f in findings[: args.max_report]:
        print('SOURCE PAGE : %s' % f[0])
        print('BROKEN LINK : %s' % f[1])
        print('EXPECTED    : %s' % f[2])
        print('CAUSE       : %s' % f[3])
        print('-' * 60)
    if len(findings) > args.max_report:
        print('... và %d lỗi khác' % (len(findings) - args.max_report))

    total = len(findings)
    if total or matrix_bad:
        print('\nFAIL: %d vấn đề liên kết nội bộ' % (total + matrix_bad))
        return 1
    print('\nPASS: mọi liên kết nội bộ trên site đã build đều resolve.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
