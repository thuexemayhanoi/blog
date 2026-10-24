#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live URL audit — READ-ONLY (Issue #77).

Chạy trên GitHub runner qua `factory-liveness.yml` (workflow_dispatch, input `live_audit`),
vì môi trường agent không gọi được miền production. KHÔNG ghi gì vào repo, KHÔNG đổi URL,
sitemap, canonical hay bằng chứng QA; KHÔNG tự theo redirect (đọc đúng mã HTTP thật).

Chế độ:
  infra      DNS + header probe: lớp edge/CDN nào đứng trước máy chủ (GitHub Pages thuần hay
             Cloudflare...), OLD/NEW mẫu của bản đồ slug đ→d trả gì. Bằng chứng để quyết định
             có đặt được HTTP 301 theo từng đường dẫn hay không.
  crawl      sitemap.xml + đồ thị liên kết nội bộ (`<a href>`): mọi URL sitemap và mọi đích liên
             kết nội bộ được đo bằng HTTP thật; sinh CSV `source,target,status,fix,retest`
             (404, 410, 5xx, redirect, soft 404, canonical lệch, lỗi mạng).
  redirects  Probe OLD -> NEW theo lô của `slug-d-migration-map.csv`: OLD phải trả 301/308,
             `Location` đúng NEW (một bước, giữ query), NEW trả 200 với canonical tự trỏ.
             Ghi JSON bằng chứng `slug-redirect-evidence/1` cho công cụ migration.

Mã thoát: 0 = chạy xong (kết quả nằm trong báo cáo), 2 = không đọc được nguồn bắt buộc.
Chỉ origin production (hoặc 127.0.0.1/localhost cho test offline) được phép.
"""
import argparse
import csv
import datetime
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
UA = 'NguyenTu-live-audit/1.0 (read-only; GitHub Actions)'
MAX_BODY = 2 * 1024 * 1024
EVIDENCE_SCHEMA = 'slug-redirect-evidence/1'
REDIRECT_CODES = (301, 302, 303, 307, 308)
SOFT_404_RE = re.compile(r'(?:\b404\b|không tìm thấy|page not found|not found)', re.I)
HREF_RE = re.compile(r'<a\s[^>]*?\bhref\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.I)
CANON_RE = re.compile(r'<link\s[^>]*?rel\s*=\s*["\']canonical["\'][^>]*?>', re.I)
ATTR_HREF_RE = re.compile(r'\bhref\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.I)
TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
ROBOTS_RE = re.compile(r'<meta\s[^>]*?name\s*=\s*["\']robots["\'][^>]*?>', re.I)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def origin_ok(origin):
    p = urllib.parse.urlsplit(origin)
    if origin == PRODUCTION:
        return True
    return p.scheme in ('http', 'https') and p.hostname in ('127.0.0.1', 'localhost')


def fetch(url, method='GET', timeout=15.0, body=False, retries=1):
    """Một request, KHÔNG theo redirect. Trả dict: status (0 = lỗi mạng), headers (chữ thường),
    body (bytes, tối đa MAX_BODY, chỉ khi body=True), error."""
    last = ''
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, method=method, headers={'User-Agent': UA, 'Cache-Control': 'no-cache'})
        try:
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
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = str(e)[:200]
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


# --------------------------------------------------------------------------- crawl


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


def analyse_page(url, body, origin):
    text = body.decode('utf-8', 'replace')
    links = []
    for m in HREF_RE.finditer(text):
        t = norm_target(m.group(1) if m.group(1) is not None else m.group(2), url, origin)
        if t:
            links.append(t)
    canon = ''
    cm = CANON_RE.search(text)
    if cm:
        hm = ATTR_HREF_RE.search(cm.group(0))
        if hm:
            canon = html.unescape(hm.group(1) if hm.group(1) is not None else hm.group(2)).strip()
    tm = TITLE_RE.search(text)
    title = html.unescape(re.sub(r'\s+', ' ', tm.group(1))).strip() if tm else ''
    rm = ROBOTS_RE.search(text)
    noindex = bool(rm and 'noindex' in rm.group(0).lower())
    return {'links': list(dict.fromkeys(links)), 'canonical': canon, 'title': title,
            'noindex': noindex, 'size': len(body)}


def suggest_fix(target, status, location, old_urls, new_urls, origin):
    path = urllib.parse.urlsplit(target).path
    if status in REDIRECT_CODES and location:
        return 'update_link_to:' + location
    if status in (404, 410):
        if path in old_urls:
            return 'blocked:slug_d_old_url_removed_without_301'
        if path in new_urls:
            return 'blocked:slug_d_new_url_not_deployed'
        if not path.endswith('/'):
            return 'try_trailing_slash'
        return 'restore_url_or_update_link_or_301_to_equivalent'
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


def crawl(origin, workers, timeout, max_pages, max_sources):
    sm = load_sitemap(origin, timeout)
    sm_set = set(sm)
    chosen = sm[:max_pages] if max_pages else sm
    pages = {}

    def get_page(u):
        r = fetch(u, 'GET', timeout, body=True)
        info = {'status': r['status'], 'location': r['headers'].get('location', ''), 'error': r['error'],
                'ctype': r['headers'].get('content-type', '')}
        if r['status'] == 200 and 'html' in info['ctype'].lower():
            info.update(analyse_page(u, r['body'], origin))
        else:
            info.update({'links': [], 'canonical': '', 'title': '', 'noindex': False, 'size': len(r['body'])})
        return u, info

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for u, info in pool.map(get_page, chosen):
            pages[u] = info

    sources = {}      # target -> [source pages]
    for u, info in pages.items():
        for t in info['links']:
            sources.setdefault(t, []).append(u)
    targets = {}
    for t in sources:
        if t in pages:
            targets[t] = pages[t]
        else:
            targets[t] = None
    pending = sorted(t for t, v in targets.items() if v is None)

    def probe(t):
        r = status_of(t, timeout)
        return t, {'status': r['status'], 'location': r['headers'].get('location', ''), 'error': r['error']}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for t, info in pool.map(probe, pending):
            targets[t] = info

    old_urls, new_urls = load_slug_paths()
    rows, soft, canon_bad, noindex = [], [], [], []
    for u in chosen:
        info = pages[u]
        st = info['status']
        if st != 200:
            rows.append(['sitemap.xml', u, st, suggest_fix(u, st, info['location'], old_urls, new_urls, origin), ''])
            continue
        if info['title'] and SOFT_404_RE.search(info['title']) and info['size'] < 20000:
            soft.append(u)
            rows.append(['sitemap.xml', u, '200-soft404', 'inspect_soft_404', ''])
        if info['canonical']:
            c = urllib.parse.urlsplit(info['canonical'])
            c_norm = urllib.parse.urlunsplit((c.scheme, c.netloc, c.path, '', ''))
            u_norm = urllib.parse.urlunsplit(urllib.parse.urlsplit(u)[:3] + ('', ''))
            if c_norm != u_norm:
                canon_bad.append((u, info['canonical']))
                rows.append([u, info['canonical'], 'CANONICAL_MISMATCH', 'self_canonical_should_equal_page_url', ''])
        else:
            canon_bad.append((u, ''))
            rows.append([u, '', 'CANONICAL_MISSING', 'add_self_canonical', ''])
        if info['noindex']:
            noindex.append(u)
            rows.append([u, u, 'NOINDEX_IN_SITEMAP', 'review_noindex_for_sitemap_url', ''])
    link_fail = {}
    for t, info in targets.items():
        st = info['status']
        if st == 200:
            continue
        link_fail[t] = (st, info['location'])
        for s in sources[t][:max_sources]:
            rows.append([s, t, st, suggest_fix(t, st, info['location'], old_urls, new_urls, origin), ''])
    return {'sitemap_urls': len(sm), 'checked': len(chosen), 'pages': pages, 'rows': rows,
            'link_targets': len(targets), 'link_fail': link_fail, 'sources': sources,
            'soft404': soft, 'canonical_bad': canon_bad, 'noindex': noindex,
            'sitemap_set': sm_set}


def summarize(res):
    by = {}
    for u, info in res['pages'].items():
        by[str(info['status'])] = by.get(str(info['status']), 0) + 1
    fail_by = {}
    for t, (st, _) in res['link_fail'].items():
        fail_by[str(st)] = fail_by.get(str(st), 0) + 1
    return {
        'sitemap_urls': res['sitemap_urls'], 'pages_checked': res['checked'],
        'sitemap_status_counts': dict(sorted(by.items())),
        'internal_link_targets': res['link_targets'],
        'failing_link_targets_by_status': dict(sorted(fail_by.items())),
        'failing_link_targets': len(res['link_fail']),
        'soft_404_pages': len(res['soft404']),
        'canonical_problem_pages': len(res['canonical_bad']),
        'noindex_in_sitemap': len(res['noindex']),
        'csv_rows': len(res['rows']),
    }


def write_csv(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['source', 'target', 'status', 'fix', 'retest'])
        w.writerows(rows)


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
    out['note'] = ('github-pages: không có redirect HTTP theo từng đường dẫn; cần lớp edge (ví dụ Cloudflare '
                   'proxied) trước khi di trú URL' if out['edge'] == 'github-pages' else
                   'có lớp edge phía trước: cần xác nhận quyền cấu hình redirect rule trước khi di trú URL')
    return out


# --------------------------------------------------------------------------- redirects


def same_url(a, b, origin):
    pa, pb = (urllib.parse.urlsplit(urllib.parse.urljoin(origin + '/', x)) for x in (a, b))
    return (pa.netloc, pa.path, pa.query) == (pb.netloc, pb.path, pb.query)


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


# --------------------------------------------------------------------------- CLI


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=('infra', 'crawl', 'redirects'))
    ap.add_argument('--origin', default=PRODUCTION)
    ap.add_argument('--workers', type=int, default=12)
    ap.add_argument('--timeout', type=float, default=15.0)
    ap.add_argument('--max-pages', type=int, default=0, help='0 = toàn bộ sitemap')
    ap.add_argument('--max-sources-per-target', type=int, default=25)
    ap.add_argument('--out', default='', help='đường dẫn CSV (crawl) hoặc JSON (infra/redirects)')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--limit', type=int, default=50)
    ap.add_argument('--map', default=MAP_CSV)
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
    for r in res['rows']:
        if r[0] != 'sitemap.xml' and r[2] not in ('CANONICAL_MISMATCH', 'CANONICAL_MISSING', 'NOINDEX_IN_SITEMAP'):
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
    return 0


if __name__ == '__main__':
    sys.exit(main())
