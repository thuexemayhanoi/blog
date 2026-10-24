#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live URL audit — READ-ONLY (Issue #77).

Chạy trên GitHub runner qua `factory-liveness.yml` (workflow_dispatch, input `live_audit`),
vì môi trường agent không gọi được miền production. KHÔNG ghi gì vào repo, KHÔNG đổi URL,
sitemap, canonical hay bằng chứng QA; KHÔNG tự theo redirect (đọc đúng mã HTTP thật).

Chế độ:
  infra      DNS + header probe: lớp edge/CDN nào đứng trước máy chủ (GitHub Pages thuần hay
             Cloudflare...). Bằng chứng cho biết có đặt được HTTP 301 theo từng đường dẫn hay không.
  crawl      sitemap.xml + đồ thị liên kết nội bộ (`<a href>`) + tài nguyên (img/script/css): mọi
             URL sitemap, mọi đích liên kết nội bộ và mọi tài nguyên nội bộ được đo bằng HTTP thật.
             Sinh (1) CSV `source,target,status,fix,retest` (định dạng Issue #77), (2) bảng kiểm kê
             từng URL `url,status,final_url,error_type,cause,handling` (CSV/JSON) và tóm tắt.
             Phân loại: 404/410/5xx/3xx/lỗi mạng, soft 404, canonical lệch/thiếu/trùng, noindex trong
             sitemap, trang meta-refresh nằm trong sitemap, liên kết nội bộ trỏ vào trang chuyển
             hướng, tiền tố `/blog/` hoặc host cũ, đường dẫn không-ASCII, tài nguyên 404, trang mồ côi.
  stubs      Kiểm QA di trú slug đ→d theo registry (`slug-redirect-registry.csv`): URL CŨ phải là
             HTTP 200 chứa `<meta http-equiv="refresh" content="0; url=MỚI">` + canonical MỚI và
             KHÔNG nằm trong sitemap; URL MỚI phải HTTP 200, canonical tự trỏ, KHÔNG phải trang
             chuyển hướng (không chuỗi/vòng), CÓ trong sitemap, có H1 và nội dung. Đây KHÔNG phải
             HTTP 301: báo cáo gọi đúng tên "HTTP 200 + meta refresh".
  redirects  (dự phòng) Probe OLD -> NEW kiểu HTTP 301/308 thật của `slug-d-migration-map.csv`; chỉ
             có ý nghĩa nếu sau này có lớp edge. GitHub Pages thuần KHÔNG trả 301 theo đường dẫn.

Mã thoát: 0 = chạy xong; 1 = (stubs) có dòng không đạt; 2 = không đọc được nguồn bắt buộc.
Chỉ origin production (hoặc 127.0.0.1/localhost cho test offline) được phép.
"""
import argparse
import base64
import csv
import datetime
import gzip
import hashlib
import html
import json
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRODUCTION = 'https://blog.thuexemaynguyentu.com'
MAP_CSV = os.path.join(ROOT, 'reports/factory/seo-master/slug-d-migration-map.csv')
REGISTRY_CSV = os.path.join(ROOT, 'reports/factory/seo-master/slug-redirect-registry.csv')
UA = 'NguyenTu-live-audit/2.0 (read-only; GitHub Actions)'
MAX_BODY = 2 * 1024 * 1024
EVIDENCE_SCHEMA = 'slug-redirect-evidence/1'
STUB_EVIDENCE_SCHEMA = 'slug-stub-evidence/1'
INVENTORY_SCHEMA = 'live-url-inventory/1'
REDIRECT_CODES = (301, 302, 303, 307, 308)
SOFT_404_RE = re.compile(r'(?:\b404\b|không tìm thấy|page not found|not found)', re.I)
CANON_RE = re.compile(r'<link\s[^>]*?rel\s*=\s*["\']canonical["\'][^>]*?>', re.I)
ATTR_HREF_RE = re.compile(r'\bhref\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.I)
TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
TAG_RE = re.compile(r'<(a|img|script|link|source|iframe|meta)\b([^>]*)>', re.I)
ATTR_RE = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'>]+))')
REFRESH_RE = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*[;,]\s*(?:url\s*=\s*)?["\']?(.+?)["\']?\s*$', re.I | re.S)
STRIP_RE = re.compile(r'<(script|style)\b.*?</\1\s*>', re.I | re.S)
ANYTAG_RE = re.compile(r'<[^>]+>')
LEGACY_PREFIX_RE = re.compile(r'^/blog(?:/|$)')
LEGACY_HOSTS = ('thuexemayhanoi.github.io',)
# URL chủ đích không phải trang nội dung (không tính là lỗi nếu bị liên kết tới)
INTENTIONAL_GONE = frozenset(('/404.html',))
THIN_TEXT = 300


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def origin_ok(origin):
    p = urllib.parse.urlsplit(origin)
    if origin == PRODUCTION:
        return True
    return p.scheme in ('http', 'https') and p.hostname in ('127.0.0.1', 'localhost')


def encode_url(url):
    """Mã hóa phần đường dẫn/truy vấn (khoảng trắng, chữ Unicode -> %XX) mà KHÔNG mã hóa lại `%XX` sẵn có:
    liên kết cũ như `/chia sẻ/...` phải đo được thay vì làm sập cả lượt crawl."""
    p = urllib.parse.urlsplit(url)
    safe = "/%:@!$&'()*+,;=-._~"
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path, safe=safe),
                                    urllib.parse.quote(p.query, safe=safe + '?'), ''))


def fetch(url, method='GET', timeout=15.0, body=False, retries=1):
    """Một request, KHÔNG theo redirect. Trả dict: status (0 = lỗi mạng/URL), headers (chữ thường),
    body (bytes, tối đa MAX_BODY, chỉ khi body=True), error. KHÔNG bao giờ ném ngoại lệ."""
    last = ''
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(encode_url(url), method=method,
                                         headers={'User-Agent': UA, 'Cache-Control': 'no-cache'})
            with _OPENER.open(req, timeout=timeout) as r:
                data = r.read(MAX_BODY) if body and method == 'GET' else b''
                return {'status': r.status, 'headers': {k.lower(): v for k, v in r.headers.items()},
                        'body': data, 'error': ''}
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                last = 'HTTP %d' % e.code
                continue
            data = b''
            if body and method == 'GET':
                try:
                    data = e.read(MAX_BODY)
                except Exception:
                    data = b''
            return {'status': e.code, 'headers': {k.lower(): v for k, v in e.headers.items()},
                    'body': data, 'error': ''}
        except Exception as e:   # URLError, timeout, InvalidURL, UnicodeError...: ghi nhận, không sập cả lượt
            last = ('%s: %s' % (type(e).__name__, e))[:200]
    return {'status': 0, 'headers': {}, 'body': b'', 'error': last or 'request failed'}


def status_of(url, timeout=15.0):
    """HEAD, GET khi máy chủ không hỗ trợ HEAD."""
    r = fetch(url, 'HEAD', timeout)
    if r['status'] in (405, 501):
        r = fetch(url, 'GET', timeout)
    return r


# --------------------------------------------------------------------------- sitemap


def parse_sitemap(xml_bytes, origin):
    root = ET.fromstring(xml_bytes)
    urls, nested = [], []
    for node in root.iter():
        if node.tag.rsplit('}', 1)[-1] != 'loc' or not node.text:
            continue
        u = node.text.strip()
        host = urllib.parse.urlsplit(u).netloc
        if host != urllib.parse.urlsplit(origin).netloc:
            raise ValueError('foreign sitemap URL: %s' % u)
        (nested if u.endswith('.xml') else urls).append(u)
    return list(dict.fromkeys(urls)), nested


def load_sitemap(origin, timeout):
    r = fetch(origin + '/sitemap.xml', 'GET', timeout, body=True)
    if r['status'] != 200:
        raise RuntimeError('sitemap HTTP %s %s' % (r['status'], r['error']))
    urls, nested = parse_sitemap(r['body'], origin)
    for sub in nested:
        rr = fetch(sub, 'GET', timeout, body=True)
        if rr['status'] != 200:
            raise RuntimeError('nested sitemap %s HTTP %s' % (sub, rr['status']))
        u2, _ = parse_sitemap(rr['body'], origin)
        urls.extend(u2)
    return list(dict.fromkeys(urls))


# --------------------------------------------------------------------------- parse HTML


def norm_target(href, page_url, origin):
    """Chuẩn hóa liên kết về URL tuyệt đối cùng origin (bỏ fragment); None nếu không phải nội bộ."""
    href = html.unescape(href).strip()
    if not href or href.startswith('#') or re.match(r'(?i)^(mailto:|tel:|javascript:|data:|sms:|whatsapp:)', href):
        return None
    absu = urllib.parse.urljoin(page_url, href)
    p = urllib.parse.urlsplit(absu)
    base = urllib.parse.urlsplit(origin)
    if p.scheme not in ('http', 'https') or p.netloc != base.netloc:
        return None
    return urllib.parse.urlunsplit((base.scheme, base.netloc, p.path or '/', p.query, ''))


def _attrs(raw):
    out = {}
    for m in ATTR_RE.finditer(raw):
        v = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
        out.setdefault(m.group(1).lower(), html.unescape(v or ''))
    return out


def _is_legacy_ref(raw):
    raw = (raw or '').strip()
    if LEGACY_PREFIX_RE.match(raw):
        return True
    host = urllib.parse.urlsplit(raw).netloc.lower()
    return any(host == h or host.endswith('.' + h) for h in LEGACY_HOSTS)


def analyse_page(url, body, origin):
    text = body.decode('utf-8', 'replace')
    links, assets, legacy = [], [], []
    canon, robots, refresh = '', '', None
    for m in TAG_RE.finditer(text):
        tag = m.group(1).lower()
        a = _attrs(m.group(2))
        if tag == 'a':
            href = a.get('href')
            if href is None:
                continue
            if _is_legacy_ref(href):
                legacy.append(href)
            t = norm_target(href, url, origin)
            if t:
                links.append(t)
        elif tag == 'link':
            rel = a.get('rel', '').lower().split()
            href = a.get('href', '')
            if 'canonical' in rel:
                if not canon:
                    canon = href.strip()
            elif href and ('stylesheet' in rel or 'icon' in rel or 'preload' in rel or 'manifest' in rel):
                if _is_legacy_ref(href):
                    legacy.append(href)
                t = norm_target(href, url, origin)
                if t:
                    assets.append(t)
        elif tag in ('img', 'script', 'source', 'iframe'):
            src = a.get('src', '')
            if src:
                if _is_legacy_ref(src):
                    legacy.append(src)
                t = norm_target(src, url, origin)
                if t:
                    assets.append(t)
        elif tag == 'meta':
            he = a.get('http-equiv', '').lower()
            if he == 'refresh' and refresh is None:
                rm = REFRESH_RE.match(a.get('content', ''))
                if rm:
                    refresh = {'delay': float(rm.group(1)), 'target': rm.group(2).strip()}
            if a.get('name', '').lower() == 'robots' and not robots:
                robots = a.get('content', '').lower()
    tm = TITLE_RE.search(text)
    title = html.unescape(re.sub(r'\s+', ' ', tm.group(1))).strip() if tm else ''
    visible = re.sub(r'\s+', ' ', html.unescape(ANYTAG_RE.sub(' ', STRIP_RE.sub('', text)))).strip()
    return {'links': list(dict.fromkeys(links)), 'assets': list(dict.fromkeys(assets)),
            'canonical': html.unescape(canon), 'title': title, 'noindex': 'noindex' in robots,
            'size': len(body), 'meta_refresh': refresh, 'text_len': len(visible),
            'h1_count': len(re.findall(r'<h1\b', text, re.I)), 'legacy_refs': legacy[:5]}


def _empty_info(r):
    return {'links': [], 'assets': [], 'canonical': '', 'title': '', 'noindex': False, 'size': len(r['body']),
            'meta_refresh': None, 'text_len': 0, 'h1_count': 0, 'legacy_refs': []}


def _canon_key(u):
    p = urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.unquote(p.path), '', ''))


def final_of(origin, url, info):
    """URL cuối cùng mà trình duyệt/bot sẽ thấy: Location (3xx) hoặc đích meta refresh (200); không thì chính nó."""
    if info.get('location'):
        return urllib.parse.urljoin(url, info['location'])
    mr = info.get('meta_refresh')
    if mr and mr.get('target'):
        return urllib.parse.urljoin(url, mr['target'])
    return url


def suggest_fix(target, status, location, old_urls, new_urls, origin):
    path = urllib.parse.urlsplit(target).path
    if status in REDIRECT_CODES and location:
        return 'update_link_to:' + location
    if status in (404, 410):
        if path in INTENTIONAL_GONE:
            return ''
        if path in old_urls:
            return 'blocked:slug_d_old_url_removed_without_redirect'
        if path in new_urls:
            return 'blocked:slug_d_new_url_not_deployed'
        if not path.endswith('/'):
            return 'try_trailing_slash'
        return 'restore_url_or_update_link_or_redirect_to_equivalent'
    if status == 0:
        return 'retest_network_error'
    if status >= 500:
        return 'retest_server_error'
    return ''


def load_slug_paths():
    old, new = set(), set()
    if os.path.exists(MAP_CSV):
        with open(MAP_CSV, encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                old.add(row.get('old_url', ''))
                new.add(row.get('new_url', ''))
    return old, new


def load_registry(path):
    """Registry di trú: các dòng đã MIGRATED (cột status nếu có)."""
    rows = []
    if os.path.exists(path):
        with open(path, encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('old_url') and r.get('new_url') and r.get('status', 'MIGRATED') == 'MIGRATED':
                    rows.append(r)
    return rows


# --------------------------------------------------------------------------- crawl


def _page_info(r, origin, url):
    info = {'status': r['status'], 'location': r['headers'].get('location', ''), 'error': r['error'],
            'ctype': r['headers'].get('content-type', '')}
    if r['status'] == 200 and 'html' in info['ctype'].lower():
        info.update(analyse_page(url, r['body'], origin))
    else:
        info.update(_empty_info(r))
    return info


def crawl(origin, workers, timeout, max_pages, max_sources, probe_assets=True, registry_path=REGISTRY_CSV):
    sm = load_sitemap(origin, timeout)
    sm_set = set(sm)
    chosen = sm[:max_pages] if max_pages else sm
    pages = {}

    def get_page(u):
        return u, _page_info(fetch(u, 'GET', timeout, body=True), origin, u)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for u, info in pool.map(get_page, chosen):
            pages[u] = info

    sources = {}      # target -> [source pages]
    asset_sources = {}
    for u, info in pages.items():
        for t in info['links']:
            sources.setdefault(t, []).append(u)
        for t in info['assets']:
            asset_sources.setdefault(t, []).append(u)
    targets = {t: pages.get(t) for t in sources}
    pending = sorted(t for t, v in targets.items() if v is None)

    def probe(t):
        return t, _page_info(fetch(t, 'GET', timeout, body=True), origin, t)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for t, info in pool.map(probe, pending):
            targets[t] = info

    assets = {}
    if probe_assets:
        apending = sorted(t for t in asset_sources if t not in pages and t not in targets)

        def aprobe(t):
            r = status_of(t, timeout)
            return t, {'status': r['status'], 'location': r['headers'].get('location', ''), 'error': r['error']}

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for t, info in pool.map(aprobe, apending):
                assets[t] = info

    old_urls, new_urls = load_slug_paths()
    reg_old = {urllib.parse.unquote(r['old_url']) for r in load_registry(registry_path)}
    rows, soft, canon_bad, noindex, stubs_in_sitemap = [], [], [], [], []
    inventory = []
    inbound = {}
    for t, srcs in sources.items():
        inbound[t] = {s for s in srcs if s != t}
    canon_groups = {}

    def inv(url, kind, status, final, etype, cause, handling):
        inventory.append({'url': url, 'kind': kind, 'status': status, 'final_url': final, 'error_type': etype,
                          'cause': cause, 'handling': handling, 'inbound': len(inbound.get(url, ()))})

    for u in chosen:
        info = pages[u]
        st = info['status']
        path = urllib.parse.urlsplit(u).path
        if st != 200:
            fix = suggest_fix(u, st, info['location'], old_urls, new_urls, origin)
            rows.append(['sitemap.xml', u, st, fix, ''])
            etype = 'NETWORK_ERROR' if st == 0 else ('HTTP_3XX' if st in REDIRECT_CODES else
                                                     'HTTP_%d' % st if st in (404, 410) else
                                                     'HTTP_5XX' if st >= 500 else 'HTTP_%d' % st)
            inv(u, 'sitemap', st, final_of(origin, u, info), etype, info['error'] or fix or 'status khong phai 200',
                'NEEDS_FIX')
            continue
        flags = []
        if info.get('meta_refresh'):
            stubs_in_sitemap.append(u)
            rows.append(['sitemap.xml', u, 'STUB_IN_SITEMAP', 'remove_redirect_page_from_sitemap', ''])
            flags.append(('STUB_IN_SITEMAP', 'trang chuyen huong meta refresh nam trong sitemap', 'NEEDS_FIX'))
        if info['title'] and SOFT_404_RE.search(info['title']) and info['size'] < 20000:
            soft.append(u)
            rows.append(['sitemap.xml', u, '200-soft404', 'inspect_soft_404', ''])
            flags.append(('SOFT_404', 'tieu de/noi dung giong trang loi: ' + info['title'][:80], 'NEEDS_FIX'))
        if info['canonical']:
            c = urllib.parse.urlsplit(info['canonical'])
            c_norm = urllib.parse.urlunsplit((c.scheme, c.netloc, c.path, '', ''))
            u_norm = urllib.parse.urlunsplit(urllib.parse.urlsplit(u)[:3] + ('', ''))
            if c_norm != u_norm and _canon_key(c_norm) != _canon_key(u_norm):
                canon_bad.append((u, info['canonical']))
                rows.append([u, info['canonical'], 'CANONICAL_MISMATCH', 'self_canonical_should_equal_page_url', ''])
                flags.append(('CANONICAL_MISMATCH', 'canonical -> ' + info['canonical'], 'NEEDS_FIX'))
            canon_groups.setdefault(_canon_key(info['canonical']), []).append(u)
        else:
            canon_bad.append((u, ''))
            rows.append([u, '', 'CANONICAL_MISSING', 'add_self_canonical', ''])
            flags.append(('CANONICAL_MISSING', 'khong co link rel=canonical', 'NEEDS_FIX'))
        if info['noindex']:
            noindex.append(u)
            rows.append([u, u, 'NOINDEX_IN_SITEMAP', 'review_noindex_for_sitemap_url', ''])
            flags.append(('NOINDEX_IN_SITEMAP', 'robots noindex nhung nam trong sitemap', 'NEEDS_FIX'))
        if info['h1_count'] == 0 and not info.get('meta_refresh'):
            flags.append(('NO_H1', 'trang khong co the h1', 'INFO'))
        if info['text_len'] < THIN_TEXT and not info.get('meta_refresh'):
            flags.append(('THIN_PAGE', 'van ban hien thi %d ky tu' % info['text_len'], 'INFO'))
        if info['legacy_refs']:
            rows.append([u, info['legacy_refs'][0], 'LEGACY_BASE_PATH', 'replace_with_root_relative_url', ''])
            flags.append(('LEGACY_BASE_PATH', 'tham chieu /blog/ hoac host cu: ' + info['legacy_refs'][0][:80],
                          'NEEDS_FIX'))
        if re.search(r'[^\x00-\x7f]|%[0-9A-Fa-f]{2}| ', path):
            flags.append(('NON_ASCII_PATH', 'duong dan chua ky tu khong-ASCII/ma hoa: ' + path[:80], 'INFO'))
        if not flags:
            inv(u, 'sitemap', 200, u, 'OK', '', 'OK')
        for etype, cause, handling in flags:
            inv(u, 'sitemap', 200, final_of(origin, u, info), etype, cause, handling)
    dup = {k: v for k, v in canon_groups.items() if len(v) > 1}
    for k, v in dup.items():
        for u in v:
            rows.append([u, k, 'DUPLICATE_CANONICAL', 'make_canonical_unique_or_merge_pages', ''])
            inv(u, 'sitemap', 200, u, 'DUPLICATE_CANONICAL', '%d URL cung canonical %s' % (len(v), k[:80]),
                'NEEDS_FIX')
    orphans = [u for u in chosen if pages[u]['status'] == 200 and not inbound.get(u)
               and urllib.parse.urlsplit(u).path != '/']
    for u in orphans:
        inv(u, 'sitemap', 200, u, 'ORPHAN', 'khong co lien ket noi bo tro toi trong cac trang da quet', 'INFO')
    link_fail, links_to_stub = {}, {}
    for t, info in targets.items():
        st = info['status']
        path = urllib.parse.urlsplit(t).path
        if st == 200:
            mr = info.get('meta_refresh')
            if mr and t not in sm_set:
                dest = final_of(origin, t, info)
                links_to_stub[t] = dest
                for s in sources[t][:max_sources]:
                    rows.append([s, t, 'LINK_TO_REDIRECT_PAGE', 'update_link_to:' + dest, ''])
                inv(t, 'link_target', 200, dest, 'LINK_TO_REDIRECT_PAGE',
                    '%d lien ket noi bo tro vao trang chuyen huong meta refresh' % len(sources[t]),
                    'EXPECTED_STUB' if urllib.parse.unquote(path) in reg_old else 'NEEDS_FIX')
            continue
        if path in INTENTIONAL_GONE:
            continue
        link_fail[t] = (st, info['location'])
        fix = suggest_fix(t, st, info['location'], old_urls, new_urls, origin)
        for s in sources[t][:max_sources]:
            rows.append([s, t, st, fix, ''])
        etype = 'NETWORK_ERROR' if st == 0 else ('HTTP_3XX' if st in REDIRECT_CODES else
                                                 'HTTP_5XX' if st >= 500 else 'HTTP_%d' % st)
        inv(t, 'link_target', st, final_of(origin, t, info), etype, info['error'] or fix, 'NEEDS_FIX')
    asset_fail = {}
    for t, info in assets.items():
        if info['status'] == 200 or urllib.parse.urlsplit(t).path in INTENTIONAL_GONE:
            continue
        asset_fail[t] = info['status']
        for s in asset_sources[t][:max_sources]:
            rows.append([s, t, info['status'], 'restore_asset_or_fix_reference', ''])
        inv(t, 'asset', info['status'], final_of(origin, t, info), 'ASSET_%s' % (info['status'] or 'ERROR'),
            info['error'] or 'tai nguyen khong tai duoc', 'NEEDS_FIX')
    return {'sitemap_urls': len(sm), 'checked': len(chosen), 'pages': pages, 'rows': rows,
            'link_targets': len(targets), 'link_fail': link_fail, 'sources': sources,
            'soft404': soft, 'canonical_bad': canon_bad, 'noindex': noindex,
            'sitemap_set': sm_set, 'inventory': inventory, 'duplicate_canonical': dup,
            'orphans': orphans, 'stubs_in_sitemap': stubs_in_sitemap, 'links_to_stub': links_to_stub,
            'assets_checked': len(assets) + len([a for a in asset_sources if a in pages or a in targets]),
            'asset_fail': asset_fail, 'asset_unique': len(asset_sources)}


def summarize(res):
    by = {}
    for u, info in res['pages'].items():
        by[str(info['status'])] = by.get(str(info['status']), 0) + 1
    fail_by = {}
    for t, (st, _) in res['link_fail'].items():
        fail_by[str(st)] = fail_by.get(str(st), 0) + 1
    inv = res.get('inventory', [])
    etypes = {}
    for r in inv:
        etypes[r['error_type']] = etypes.get(r['error_type'], 0) + 1
    handling = {}
    for r in inv:
        handling[r['handling']] = handling.get(r['handling'], 0) + 1
    return {
        'sitemap_urls': res['sitemap_urls'], 'pages_checked': res['checked'],
        'sitemap_status_counts': dict(sorted(by.items())),
        'internal_link_targets': res['link_targets'],
        'failing_link_targets_by_status': dict(sorted(fail_by.items())),
        'failing_link_targets': len(res['link_fail']),
        'soft_404_pages': len(res['soft404']),
        'canonical_problem_pages': len(res['canonical_bad']),
        'noindex_in_sitemap': len(res['noindex']),
        'duplicate_canonical_groups': len(res.get('duplicate_canonical', {})),
        'stub_pages_in_sitemap': len(res.get('stubs_in_sitemap', [])),
        'links_to_redirect_pages': len(res.get('links_to_stub', {})),
        'orphan_pages': len(res.get('orphans', [])),
        'asset_unique': res.get('asset_unique', 0), 'asset_failing': len(res.get('asset_fail', {})),
        'error_type_counts': dict(sorted(etypes.items())),
        'handling_counts': dict(sorted(handling.items())),
        'csv_rows': len(res['rows']),
    }


def write_csv(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['source', 'target', 'status', 'fix', 'retest'])
        w.writerows(rows)


INVENTORY_COLUMNS = ['url', 'kind', 'status', 'final_url', 'error_type', 'cause', 'handling', 'inbound']


def write_inventory(base, res):
    """`base`.csv + `base`.json: mỗi dòng một URL: url, status, final_url, error_type, cause, handling."""
    os.makedirs(os.path.dirname(os.path.abspath(base)), exist_ok=True)
    inv = res['inventory']
    with open(base + '.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=INVENTORY_COLUMNS, lineterminator='\n')
        w.writeheader()
        w.writerows(inv)
    doc = {'schema': INVENTORY_SCHEMA, 'generated_at': datetime.datetime.now(datetime.timezone.utc)
           .isoformat(timespec='seconds'), 'summary': summarize(res), 'rows': inv}
    with open(base + '.json', 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


def dump_blob(name, obj, out=None):
    """In đối tượng JSON dạng gzip+base64 có sha256 vào log (runner không đẩy file về được sandbox;
    `scripts/seo/decode-log-blob.py` giải ngược lại từ log)."""
    out = out or sys.stdout
    raw = gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), 9, mtime=0)
    b = base64.b64encode(raw).decode('ascii')
    out.write('%s_BEGIN sha256=%s bytes=%d\n' % (name, hashlib.sha256(raw).hexdigest(), len(raw)))
    for i in range(0, len(b), 160):
        out.write(b[i:i + 160] + '\n')
    out.write('%s_END\n' % name)


# --------------------------------------------------------------------------- infra


def tls_info(host, port=443):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as s:
            with ctx.wrap_socket(s, server_hostname=host) as t:
                cert = t.getpeercert()
        flat = lambda seq: {k: v for part in seq for (k, v) in part}
        return {'issuer': flat(cert.get('issuer', ())).get('organizationName', ''),
                'subject_cn': flat(cert.get('subject', ())).get('commonName', ''),
                'not_after': cert.get('notAfter', '')}
    except Exception as e:  # diagnostics only
        return {'error': str(e)[:160]}


def edge_verdict(headers_list):
    seen = {}
    for h in headers_list:
        for k, v in h.items():
            seen.setdefault(k, v)
    server = seen.get('server', '').lower()
    if 'cf-ray' in seen or server == 'cloudflare':
        return 'cloudflare'
    if 'x-github-request-id' in seen or server == 'github.com':
        return 'github-pages'
    if 'x-vercel-id' in seen or server == 'vercel':
        return 'vercel'
    if 'x-served-by' in seen or 'fastly' in seen.get('via', '').lower():
        return 'fastly'
    if 'x-nf-request-id' in seen or server == 'netlify':
        return 'netlify'
    return 'unknown'


PROBE_HEADERS = ('server', 'via', 'cf-ray', 'cf-cache-status', 'x-github-request-id', 'x-served-by', 'x-vercel-id',
                 'age', 'cache-control', 'location', 'strict-transport-security', 'content-type', 'last-modified')


def infra(origin, timeout):
    host = urllib.parse.urlsplit(origin).hostname
    out = {'schema': 'live-infra-probe/1', 'origin': origin,
           'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
    try:
        name, aliases, addrs = socket.gethostbyname_ex(host)
        out['dns'] = {'canonical_name': name, 'aliases': aliases, 'ipv4': addrs}
    except OSError as e:
        out['dns'] = {'error': str(e)[:160]}
    if origin.startswith('https://'):
        out['tls'] = tls_info(host)
    old, new = '', ''
    if os.path.exists(MAP_CSV):
        with open(MAP_CSV, encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('old_url') and row.get('new_url'):
                    old, new = row['old_url'], row['new_url']
                    break
    paths = ['/', '/sitemap.xml', '/robots.txt', '/chu-de/']
    if old:
        paths += [old, new, new + '?probe=1']
    probes, hdrs = [], []
    for p in paths:
        r = fetch(origin + p, 'GET', timeout, body=False)
        hdrs.append(r['headers'])
        probes.append({'path': p, 'status': r['status'], 'error': r['error'],
                       'headers': {k: r['headers'][k] for k in PROBE_HEADERS if k in r['headers']}})
    out['probes'] = probes
    out['edge'] = edge_verdict(hdrs)
    out['per_path_301_possible_without_new_infra'] = False if out['edge'] == 'github-pages' else None
    out['note'] = ('github-pages: không có redirect HTTP theo từng đường dẫn; di trú URL dùng trang HTTP 200 + '
                   'meta refresh 0 giây + canonical (KHÔNG gọi là 301)' if out['edge'] == 'github-pages' else
                   'có lớp edge phía trước: cần xác nhận quyền cấu hình redirect rule trước khi di trú URL')
    return out


# --------------------------------------------------------------------------- redirects / stubs


def same_url(a, b, origin):
    pa, pb = (urllib.parse.urlsplit(urllib.parse.urljoin(origin + '/', x)) for x in (a, b))
    return (pa.netloc, urllib.parse.unquote(pa.path), pa.query) == (pb.netloc, urllib.parse.unquote(pb.path), pb.query)


def probe_redirect(origin, old, new, timeout):
    row = {'old': old, 'new': new}
    q = 'probe=1'
    r = fetch(origin + old, 'GET', timeout)
    row['old_status'] = r['status']
    loc = r['headers'].get('location', '')
    row['old_location'] = loc
    row['old_ok'] = r['status'] in (301, 308) and same_url(loc, new, origin)
    rq = fetch(origin + old + '?' + q, 'GET', timeout)
    lq = rq['headers'].get('location', '')
    row['query_preserved'] = rq['status'] in (301, 308) and same_url(lq, new + '?' + q, origin)
    n = fetch(origin + new, 'GET', timeout, body=True)
    row['new_status'] = n['status']
    canon = ''
    if n['status'] == 200:
        cm = CANON_RE.search(n['body'].decode('utf-8', 'replace'))
        if cm:
            hm = ATTR_HREF_RE.search(cm.group(0))
            if hm:
                canon = html.unescape(hm.group(1) if hm.group(1) is not None else hm.group(2)).strip()
    row['new_canonical'] = canon
    row['new_ok'] = n['status'] == 200 and bool(canon) and same_url(canon, new, origin)
    row['ok'] = bool(row['old_ok'] and row['query_preserved'] and row['new_ok'])
    return row


def redirects(origin, start, limit, workers, timeout, map_path):
    with open(map_path, encoding='utf-8', newline='') as f:
        pairs = [(r['old_url'], r['new_url']) for r in csv.DictReader(f) if r.get('old_url') and r.get('new_url')]
    chunk = pairs[start:start + limit] if limit else pairs[start:]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda p: probe_redirect(origin, p[0], p[1], timeout), chunk))
    return {'schema': EVIDENCE_SCHEMA, 'origin': origin,
            'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
            'start': start, 'count': len(rows), 'all_ok': bool(rows) and all(r['ok'] for r in rows),
            'ok': sum(1 for r in rows if r['ok']), 'rows': rows}


def probe_stub(origin, old, new, sitemap_set, old_set, timeout):
    """Một cặp OLD (trang chuyển hướng meta refresh) -> NEW (trang thật). Mọi điều kiện phải đạt."""
    row = {'old': old, 'new': new, 'problems': []}
    bad = row['problems']
    r = fetch(origin + old, 'GET', timeout, body=True)
    row['old_status'] = r['status']
    info = _page_info(r, origin, origin + old)
    mr = info.get('meta_refresh')
    row['old_meta_refresh'] = mr
    row['old_canonical'] = info.get('canonical', '')
    if r['status'] != 200:
        bad.append('OLD_STATUS_%s' % r['status'])
    elif not mr:
        bad.append('OLD_NO_META_REFRESH')
    else:
        if mr['delay'] != 0:
            bad.append('OLD_REFRESH_DELAY_%s' % mr['delay'])
        if not same_url(mr['target'], new, origin):
            bad.append('OLD_REFRESH_WRONG_TARGET')
    if r['status'] == 200 and not (info.get('canonical') and same_url(info['canonical'], new, origin)):
        bad.append('OLD_CANONICAL_NOT_NEW')
    if origin + old in sitemap_set:
        bad.append('OLD_STILL_IN_SITEMAP')
    n = fetch(origin + new, 'GET', timeout, body=True)
    row['new_status'] = n['status']
    ninfo = _page_info(n, origin, origin + new)
    row['new_canonical'] = ninfo.get('canonical', '')
    if n['status'] != 200:
        bad.append('NEW_STATUS_%s' % n['status'])
    else:
        if ninfo.get('meta_refresh'):
            bad.append('NEW_IS_REDIRECT_PAGE')
        if not (ninfo.get('canonical') and same_url(ninfo['canonical'], new, origin)):
            bad.append('NEW_CANONICAL_NOT_SELF')
        if ninfo.get('h1_count', 0) < 1:
            bad.append('NEW_NO_H1')
        if ninfo.get('text_len', 0) < THIN_TEXT:
            bad.append('NEW_THIN_CONTENT')
        if ninfo.get('noindex'):
            bad.append('NEW_NOINDEX')
        if origin + new not in sitemap_set:
            bad.append('NEW_NOT_IN_SITEMAP')
    if urllib.parse.unquote(new) in old_set:
        bad.append('NEW_IS_ALSO_OLD_CHAIN')
    row['ok'] = not bad
    return row


def stubs(origin, registry_path, start, limit, workers, timeout):
    reg = load_registry(registry_path)
    chunk = reg[start:start + limit] if limit else reg[start:]
    sm = set(load_sitemap(origin, timeout))
    old_set = {urllib.parse.unquote(r['old_url']) for r in reg}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda r: probe_stub(origin, r['old_url'], r['new_url'], sm, old_set, timeout), chunk))
    for r, reg_row in zip(rows, chunk):
        r['article_id'] = reg_row.get('article_id', '')
    counts = {}
    for r in rows:
        for p in r['problems']:
            counts[p] = counts.get(p, 0) + 1
    return {'schema': STUB_EVIDENCE_SCHEMA, 'origin': origin,
            'kind': 'HTTP 200 + meta refresh 0s + canonical (khong phai HTTP 301)',
            'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
            'registry_total': len(reg), 'start': start, 'count': len(rows),
            'all_ok': bool(rows) and all(r['ok'] for r in rows), 'ok': sum(1 for r in rows if r['ok']),
            'problem_counts': dict(sorted(counts.items())), 'rows': rows}


# --------------------------------------------------------------------------- CLI


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=('infra', 'crawl', 'redirects', 'stubs'))
    ap.add_argument('--origin', default=PRODUCTION)
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--timeout', type=float, default=15.0)
    ap.add_argument('--max-pages', type=int, default=0, help='0 = toàn bộ sitemap')
    ap.add_argument('--max-sources-per-target', type=int, default=25)
    ap.add_argument('--out', default='', help='đường dẫn CSV (crawl) hoặc JSON (infra/redirects/stubs)')
    ap.add_argument('--inventory-out', default='', help='(crawl) tiền tố tệp kiểm kê: ghi <tiền tố>.csv và .json')
    ap.add_argument('--dump-inventory', action='store_true', help='(crawl) in kiểm kê gzip+base64 vào log')
    ap.add_argument('--dump-evidence', action='store_true', help='(stubs/redirects) in bằng chứng gzip+base64 vào log')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--limit', type=int, default=50, help='0 = đến hết (stubs/redirects)')
    ap.add_argument('--map', default=MAP_CSV)
    ap.add_argument('--registry', default=REGISTRY_CSV)
    ap.add_argument('--show', type=int, default=150, help='số dòng lỗi in ra log')
    a = ap.parse_args(argv)
    if not origin_ok(a.origin):
        ap.error('chỉ origin production hoặc 127.0.0.1/localhost (test offline) được phép')
    if not 1 <= a.workers <= 16 or not 2 <= a.timeout <= 60 or a.start < 0 or a.limit < 0:
        ap.error('workers 1..16, timeout 2..60, start/limit >= 0')
    if a.mode == 'infra':
        out = infra(a.origin, a.timeout)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if a.out:
            with open(a.out, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
        return 0
    if a.mode == 'redirects':
        ev = redirects(a.origin, a.start, a.limit, a.workers, a.timeout, a.map)
        bad = [r for r in ev['rows'] if not r['ok']]
        print(json.dumps({k: v for k, v in ev.items() if k != 'rows'}, ensure_ascii=False, indent=2))
        for r in bad[:a.show]:
            print('FAIL', json.dumps(r, ensure_ascii=False))
        if a.out:
            with open(a.out, 'w', encoding='utf-8') as f:
                json.dump(ev, f, ensure_ascii=False, indent=2)
        return 0
    if a.mode == 'stubs':
        try:
            ev = stubs(a.origin, a.registry, a.start, a.limit, a.workers, a.timeout)
        except (RuntimeError, ValueError, ET.ParseError) as e:
            print('BLOCKED: không đọc được sitemap:', e, file=sys.stderr)
            return 2
        bad = [r for r in ev['rows'] if not r['ok']]
        print(json.dumps({k: v for k, v in ev.items() if k != 'rows'}, ensure_ascii=False, indent=2))
        for r in bad[:a.show]:
            print('FAIL', r['article_id'], r['old'], '->', r['new'], ','.join(r['problems']))
        if a.out:
            with open(a.out, 'w', encoding='utf-8') as f:
                json.dump(ev, f, ensure_ascii=False, indent=2)
        if a.dump_evidence:
            dump_blob('STUB_EVIDENCE', ev)
        return 0 if ev['all_ok'] else 1
    try:
        res = crawl(a.origin, a.workers, a.timeout, a.max_pages, a.max_sources_per_target)
    except (RuntimeError, ValueError, ET.ParseError) as e:
        print('BLOCKED: không đọc được sitemap:', e, file=sys.stderr)
        return 2
    summary = summarize(res)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    ranked = sorted(res['link_fail'].items(), key=lambda kv: (-len(res['sources'][kv[0]]), kv[0]))
    for t, (st, loc) in ranked[:a.show]:
        srcs = res['sources'][t]
        print('TARGET', st, t, 'sources=%d' % len(srcs), 'first=%s' % srcs[0], ('location=%s' % loc) if loc else '')
    if len(ranked) > a.show:
        print('... còn %d đích lỗi khác trong CSV' % (len(ranked) - a.show))
    shown = 0
    sitemap_kinds = ('CANONICAL_MISMATCH', 'CANONICAL_MISSING', 'NOINDEX_IN_SITEMAP', 'STUB_IN_SITEMAP',
                     'DUPLICATE_CANONICAL', 'LEGACY_BASE_PATH')
    for r in res['rows']:
        if r[0] != 'sitemap.xml' and r[2] not in sitemap_kinds:
            continue
        if shown >= a.show:
            print('... còn dòng sitemap/canonical khác trong CSV')
            break
        print('ROW', ','.join(str(x) for x in r))
        shown += 1
    if a.out:
        write_csv(a.out, res['rows'])
        with open(os.path.splitext(a.out)[0] + '.summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print('csv:', a.out)
    if a.inventory_out:
        doc = write_inventory(a.inventory_out, res)
        print('inventory:', a.inventory_out + '.csv/.json', len(doc['rows']), 'dòng')
    if a.dump_inventory:
        dump_blob('LIVE_INVENTORY', {'summary': summary, 'rows': res['inventory'],
                                     'sitemap': sorted(res['sitemap_set'])})
    return 0


if __name__ == '__main__':
    sys.exit(main())
