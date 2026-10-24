#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra OUTPUT ĐÃ BUILD (trước khi deploy) của di trú slug đ -> d (Issue #77). READ-ONLY, offline.

  python3 scripts/factory/check-slug-redirects.py --site ./_site [--root .] [--max-stub-links N]
  python3 scripts/factory/check-slug-redirects.py --from-source [--write-ratchet --allow-raise]   # ước lượng ratchet KHÔNG cần build

Với MỌI dòng MIGRATED trong reports/factory/seo-master/slug-redirect-registry.csv:
  URL CŨ  : tệp <site>/<old>/index.html tồn tại; đúng MỘT `<meta http-equiv="refresh" content="0; url=MỚI">`
            (độ trễ 0, đích CHÍNH XÁC là URL MỚI — cùng host, không query/fragment); đúng MỘT canonical =
            https://blog.thuexemaynguyentu.com + MỚI; KHÔNG noindex; có liên kết dự phòng <a href=MỚI>; KHÔNG có trong sitemap.xml.
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
NOINDEX_RE = re.compile(r'<meta\s[^>]*?name\s*=\s*["\']robots["\'][^>]*content\s*=\s*["\'][^"\']*noindex', re.I)
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


def norm_path(href, site_host, strict=False):
    """Đường dẫn nội bộ của href. strict=True (đích chuyển hướng): từ chối query/fragment — đích phải CHÍNH XÁC là URL mới."""
    href = html.unescape(href).strip()
    if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
        return None
    p = urllib.parse.urlsplit(href)
    if p.scheme and p.netloc and p.netloc != site_host:
        return None
    if not p.path.startswith('/'):
        return None
    if strict and (p.query or p.fragment):
        return None
    return urllib.parse.unquote(p.path)


def anchor_paths(text, site_host):
    out = set()
    for m in A_HREF_RE.finditer(text):
        p = norm_path(m.group(1) if m.group(1) is not None else m.group(2), site_host)
        if p:
            out.add(p)
    return out


SOURCE_SKIP_DIRS = {'_site', '.git', '.jekyll-cache', '.sass-cache', 'node_modules', 'vendor', 'docs', 'reports', 'scripts', 'data',
                    '_drafts', 'redirects', 'tests', 'bin', 'build_info', 'cache'}
SOURCE_EXT = ('.md', '.html', '.yml', '.yaml', '.json')


def source_stub_links(root=None):
    """Đếm liên kết trỏ vào URL cũ (đã thành trang chuyển hướng) NGAY TỪ NGUỒN (bài, include, layout, trang, _data), không cần build.
    Mỗi lần xuất hiện của URL cũ (có/không '/' cuối, đủ token) = một liên kết. Khớp đúng số do `check()` đo trên output build ở cả lô thí
    điểm 10 bài (4) lẫn 50 bài (124); gate vẫn kiểm trên output build thật — số này chỉ để đặt ratchet nhanh cho mỗi lô."""
    root = root or SR.ROOT
    old_urls = [r['old_url'] for r in SR.load_registry(root) if r.get('status') == SR.MIGRATED]
    if not old_urls:
        return {'stub_links': 0, 'stub_link_sources': 0, 'registry': 0}
    forms = set()
    for u in old_urls:
        forms.add(u)
        forms.add(u.rstrip('/'))
    pat = re.compile('|'.join(re.escape(f) for f in sorted(forms, key=len, reverse=True)))
    total, sources = 0, 0
    for dp, dns, fns in os.walk(root):
        rel = os.path.relpath(dp, root)
        if rel == '.':
            dns[:] = [d for d in dns if d not in SOURCE_SKIP_DIRS or d in ('_data',)]
        for fn in fns:
            if not fn.endswith(SOURCE_EXT):
                continue
            path = os.path.join(dp, fn)
            try:
                text = read(path)
            except OSError:
                continue
            n = 0
            for m in pat.finditer(text):
                if m.group(0).endswith('/') or not re.match(r'[\w\-/]', text[m.end():m.end() + 1]):
                    n += 1
            if n:
                total += n
                sources += 1
    return {'stub_links': total, 'stub_link_sources': sources, 'registry': len(old_urls)}


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
                tp = norm_path(target, site_host, strict=True)
                if tp != new:
                    errors.append('%s: meta refresh trỏ %r, cần CHÍNH XÁC %r (cùng host, không query/fragment)' % (aid, target, new))
            cans = CANON_RE.findall(t)
            if cans != [want_canon]:
                errors.append('%s: canonical trang cũ %r, cần %r' % (aid, cans, want_canon))
            if NOINDEX_RE.search(t):
                errors.append('%s: trang chuyển hướng không được noindex' % aid)
            if new not in anchor_paths(t, site_host):
                errors.append('%s: trang chuyển hướng thiếu liên kết dự phòng <a href=%s>' % (aid, new))
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
                if p and (p if p.endswith('/') else p + '/') in old_set:     # thiếu '/' cuối cũng là liên kết vào trang chuyển hướng
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
        if limit is None and reg:
            errors.append('thiếu ngưỡng ratchet max_links_to_stub_pages trong %s (đã có %d mục di trú): kiểm tra không được tắt ngầm'
                          % (SR.RATCHET_REL, len(reg)))
    if limit is not None and stub_links > limit:
        top = sorted(per_source.items(), key=lambda kv: -kv[1])[:8]
        errors.append('liên kết nội bộ tới trang chuyển hướng: %d > ngưỡng %d (chỉ được giảm) — nguồn đầu: %s'
                      % (stub_links, limit, top))
    elif limit is not None and stub_links < limit:
        notes.append('ratchet có thể hạ từ %d xuống %d' % (limit, stub_links))
    return {'registry': len(reg), 'stub_links': stub_links, 'stub_link_sources': len(per_source),
            'ratchet': limit, 'errors': errors, 'notes': notes}


def write_ratchet(root, value, allow_raise):
    rp = os.path.join(root or SR.ROOT, SR.RATCHET_REL)
    doc = {}
    cur = None
    if os.path.isfile(rp):
        with open(rp, encoding='utf-8') as f:
            doc = json.load(f)
        cur = doc.get('max_links_to_stub_pages')
    if cur is not None and value > cur and not allow_raise:
        print('FAIL: --write-ratchet không được TĂNG ngưỡng (%d -> %d) nếu thiếu --allow-raise' % (cur, value))
        return 1
    doc['max_links_to_stub_pages'] = value
    with open(rp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('ratchet = %d (ghi %s)' % (value, os.path.relpath(rp)))
    return 0


def main_from_source(a):
    res = source_stub_links(a.root)
    print('registry=%d liên_kết_tới_trang_chuyển_hướng(nguồn)=%d (từ %d tệp)' % (res['registry'], res['stub_links'], res['stub_link_sources']))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    if a.write_ratchet:
        return write_ratchet(a.root, res['stub_links'], a.allow_raise)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--site', default='_site')
    ap.add_argument('--from-source', action='store_true',
                    help='đếm liên kết vào trang chuyển hướng từ NGUỒN (không cần build); với --write-ratchet ghi ngưỡng ratchet')
    ap.add_argument('--root', default=None)
    ap.add_argument('--max-stub-links', type=int, default=None)
    ap.add_argument('--json', default='')
    ap.add_argument('--write-ratchet', action='store_true',
                    help='ghi số liên kết đo được vào ngưỡng ratchet (chỉ khi kiểm tra sạch); mặc định chỉ cho phép GIẢM')
    ap.add_argument('--allow-raise', action='store_true',
                    help='cho phép TĂNG ngưỡng (chỉ khi di trú thêm bài: URL cũ mới sinh thêm liên kết vào trang chuyển hướng)')
    a = ap.parse_args(argv)
    if a.from_source:
        return main_from_source(a)
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
    if res['errors'] and not (a.write_ratchet and all('ngưỡng' in e for e in res['errors']) and a.allow_raise):
        return 1
    if a.write_ratchet:
        return write_ratchet(a.root, res['stub_links'], a.allow_raise)
    print('OK: di trú slug — mọi trang cũ = HTTP 200 + meta refresh 0s + canonical mới; trang mới hợp lệ (KHÔNG phải 301)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
