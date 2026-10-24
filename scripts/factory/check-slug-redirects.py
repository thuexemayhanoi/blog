#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra OUTPUT ĐÃ BUILD (trước khi deploy) của di trú slug đ -> d (Issue #77). READ-ONLY, offline.

  python3 scripts/factory/check-slug-redirects.py --site ./_site [--root .] [--max-stub-links N]

Với MỌI dòng MIGRATED trong reports/factory/seo-master/slug-redirect-registry.csv:
  URL CŨ  : tệp <site>/<old>/index.html tồn tại; đúng MỘT `<meta http-equiv="refresh" content="0; url=MỚI">`
            (độ trễ 0, đích là URL MỚI); đúng MỘT canonical = https://blog.thuexemaynguyentu.com + MỚI;
            KHÔNG có trong sitemap.xml.
  URL MỚI : tệp tồn tại, đúng một canonical tự trỏ, KHÔNG có meta refresh, có <h1>, CÓ trong sitemap.xml.
  Chuỗi/vòng: URL MỚI không phải URL CŨ của mục nào.
Toàn site:
  mọi trang có meta refresh PHẢI nằm trong registry (không có trang chuyển hướng lạ);
  số liên kết nội bộ <a href> trỏ vào URL CŨ (đã thành trang chuyển hướng) không được vượt ngưỡng ratchet
  reports/factory/seo-master/slug-stub-link-ratchet.json (chỉ được giảm) — bài mới không được link vào URL cũ.

Đây là kiểm tra "HTTP 200 + meta refresh", KHÔNG phải HTTP 301. Mã thoát 0 = sạch, 1 = có lỗi, 2 = thiếu đầu vào.
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import slug_redirects as SR  # noqa: E402

REFRESH_TAG_RE = re.compile(r'<meta\s[^>]*?http-equiv\s*=\s*["\']refresh["\'][^>]*>', re.I)
CONTENT_RE = re.compile(r'content\s*=\s*["\']([^"\']*)["\']', re.I)
CANON_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]*)"', re.I)
A_HREF_RE = re.compile(r'<a\s[^>]*?href\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.I)


def page_file(site, url_path):
    p = urllib.parse.unquote(url_path).strip('/')
    return os.path.join(site, p, 'index.html') if p else os.path.join(site, 'index.html')


def read(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def sitemap_paths(site):
    p = os.path.join(site, 'sitemap.xml')
    if not os.path.isfile(p):
        raise FileNotFoundError('thiếu sitemap.xml trong %s' % site)
    return {urllib.parse.unquote(urllib.parse.urlsplit(u).path)
            for u in re.findall(r'<loc>([^<]+)</loc>', read(p))}


def refresh_info(text):
    tags = REFRESH_TAG_RE.findall(text)
    out = []
    for t in tags:
        m = CONTENT_RE.search(t)
        content = html.unescape(m.group(1)) if m else ''
        mm = re.match(r'^\s*(\d+(?:\.\d+)?)\s*[;,]\s*(?:url\s*=\s*)?(.+?)\s*$', content, re.I)
        out.append((float(mm.group(1)), mm.group(2).strip('"\' ')) if mm else (None, content))
    return out


def norm_path(href, site_host):
    href = html.unescape(href).strip()
    if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
        return None
    p = urllib.parse.urlsplit(href)
    if p.scheme and p.netloc and p.netloc != site_host:
        return None
    if not p.path.startswith('/'):
        return None
    return urllib.parse.unquote(p.path)


def check(site, root=None, max_stub_links=None):
    errors, notes = [], []
    reg = [r for r in SR.load_registry(root) if r.get('status') == SR.MIGRATED]
    site_host = urllib.parse.urlsplit(SR.SITE_URL).netloc
    smap = sitemap_paths(site)
    old_set = {r['old_url'] for r in reg}
    new_set = {r['new_url'] for r in reg}
    for r in reg:
        aid, old, new = r['article_id'], r['old_url'], r['new_url']
        want_canon = SR.SITE_URL + new
        of = page_file(site, old)
        if not os.path.isfile(of):
            errors.append('%s: thiếu trang chuyển hướng %s' % (aid, of))
        else:
            t = read(of)
            refs = refresh_info(t)
            if len(refs) != 1:
                errors.append('%s: trang cũ có %d thẻ meta refresh (cần đúng 1)' % (aid, len(refs)))
            else:
                delay, target = refs[0]
                if delay != 0:
                    errors.append('%s: meta refresh trễ %r giây (cần 0)' % (aid, delay))
                tp = norm_path(target, site_host)
                if tp != new:
                    errors.append('%s: meta refresh trỏ %r, cần %r' % (aid, target, new))
            cans = CANON_RE.findall(t)
            if cans != [want_canon]:
                errors.append('%s: canonical trang cũ %r, cần %r' % (aid, cans, want_canon))
            if old in smap:
                errors.append('%s: URL cũ %s vẫn nằm trong sitemap' % (aid, old))
        nf = page_file(site, new)
        if not os.path.isfile(nf):
            errors.append('%s: thiếu trang mới %s' % (aid, nf))
        else:
            t = read(nf)
            if refresh_info(t):
                errors.append('%s: trang mới %s là trang chuyển hướng (chuỗi)' % (aid, new))
            cans = CANON_RE.findall(t)
            if cans != [want_canon]:
                errors.append('%s: canonical trang mới %r, cần tự trỏ %r' % (aid, cans, want_canon))
            if '<h1' not in t.lower():
                errors.append('%s: trang mới không có <h1> (thiếu nội dung?)' % aid)
            if new not in smap:
                errors.append('%s: URL mới %s không có trong sitemap' % (aid, new))
        if new in old_set:
            errors.append('%s: URL mới %s cũng là URL cũ của mục khác (chuỗi)' % (aid, new))
    # toàn site: trang meta refresh lạ + liên kết vào trang chuyển hướng
    stub_links, per_source = 0, {}
    unregistered = []
    for dp, _, files in os.walk(site):
        for fn in files:
            if not fn.endswith('.html'):
                continue
            path = os.path.join(dp, fn)
            text = read(path)
            rel = '/' + os.path.relpath(dp, site).replace(os.sep, '/').strip('.') + '/'
            rel = re.sub(r'/+', '/', rel)
            is_stub = False
            if REFRESH_TAG_RE.search(text):
                if urllib.parse.unquote(rel) not in old_set:
                    unregistered.append(rel)
                is_stub = True
            if is_stub:
                continue
            for m in A_HREF_RE.finditer(text):
                p = norm_path(m.group(1) if m.group(1) is not None else m.group(2), site_host)
                if p and p in old_set:
                    stub_links += 1
                    per_source[rel] = per_source.get(rel, 0) + 1
    for u in sorted(unregistered)[:30]:
        errors.append('trang meta refresh không có trong registry: %s' % u)
    if len(unregistered) > 30:
        errors.append('... còn %d trang meta refresh lạ' % (len(unregistered) - 30))
    limit = max_stub_links
    if limit is None:
        rp = os.path.join(root or SR.ROOT, SR.RATCHET_REL)
        if os.path.isfile(rp):
            with open(rp, encoding='utf-8') as f:
                limit = json.load(f).get('max_links_to_stub_pages')
    if limit is not None and stub_links > limit:
        top = sorted(per_source.items(), key=lambda kv: -kv[1])[:8]
        errors.append('liên kết nội bộ tới trang chuyển hướng: %d > ngưỡng %d (chỉ được giảm) — nguồn đầu: %s'
                      % (stub_links, limit, top))
    elif limit is not None and stub_links < limit:
        notes.append('ratchet có thể hạ từ %d xuống %d' % (limit, stub_links))
    return {'registry': len(reg), 'stub_links': stub_links, 'stub_link_sources': len(per_source),
            'ratchet': limit, 'errors': errors, 'notes': notes}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--site', default='_site')
    ap.add_argument('--root', default=None)
    ap.add_argument('--max-stub-links', type=int, default=None)
    ap.add_argument('--json', default='')
    a = ap.parse_args(argv)
    if not os.path.isdir(a.site):
        print('LỖI: không có thư mục site %s' % a.site, file=sys.stderr)
        return 2
    try:
        res = check(a.site, a.root, a.max_stub_links)
    except FileNotFoundError as e:
        print('LỖI:', e, file=sys.stderr)
        return 2
    for n in res['notes']:
        print('NOTE:', n)
    for e in res['errors'][:200]:
        print('FAIL:', e)
    print('registry=%d liên_kết_tới_trang_chuyển_hướng=%d (từ %d trang) ngưỡng=%s lỗi=%d'
          % (res['registry'], res['stub_links'], res['stub_link_sources'], res['ratchet'], len(res['errors'])))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    if res['errors']:
        return 1
    print('OK: di trú slug — mọi trang cũ = HTTP 200 + meta refresh 0s + canonical mới; trang mới hợp lệ (KHÔNG phải 301)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
