#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vệ sinh URL toàn site (Issue #77) — READ-ONLY, offline, chạy trên OUTPUT ĐÃ BUILD + nguồn.

  python3 scripts/factory/check-site-urls.py --site ./_site [--root .]

Chặn trước khi deploy:
  NGUỒN   permalink trùng giữa hai tệp (bài/trang/trang chuyển hướng) — Jekyll ghi đè im lặng một trong hai;
          permalink có ký tự ngoài [a-z0-9-/] (chữ hoa, dấu tiếng Việt, 'đ' chưa chuẩn hóa...) — slug phải do slugkit sinh (đ -> d).
  SITEMAP <loc> trùng; host khác https://blog.thuexemaynguyentu.com; đường dẫn ngoài [a-z0-9-/._] (không ASCII, chữ hoa,
          %-encode) — trừ danh sách ĐÓNG BĂNG reports/factory/seo-master/non-ascii-url-baseline.txt (483 bài legacy có danh mục
          tiếng Việt, đã sống trước 2026-10-27; chỉ được co lại); mỗi URL trong sitemap: đúng MỘT canonical == chính nó,
          KHÔNG meta refresh, KHÔNG noindex.
  BUILD   hai trang HTML khác nhau (không phải trang chuyển hướng) khai cùng canonical (URL trùng nội dung).
Mã thoát 0 = sạch, 1 = có lỗi, 2 = thiếu đầu vào.
"""
import argparse
import json
import os
import re
import sys
import urllib.parse

SITE_URL = 'https://blog.thuexemaynguyentu.com'
LOC_RE = re.compile(r'<loc>\s*([^<\s]+)\s*</loc>')
CANON_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]*)"', re.I)
REFRESH_RE = re.compile(r'<meta\s[^>]*?http-equiv\s*=\s*["\']refresh["\']', re.I)
NOINDEX_RE = re.compile(r'<meta\s[^>]*?name\s*=\s*["\']robots["\'][^>]*content\s*=\s*["\'][^"\']*noindex', re.I)
PERMALINK_RE = re.compile(r'^permalink:\s*["\']?([^"\'\s]+)["\']?\s*$', re.M)
SAFE_PERMALINK_RE = re.compile(r'^/[a-z0-9\-/]*(?:\.(?:html|xml|txt|json))?\Z')     # /404.html, /feed.xml...
SAFE_PATH_RE = re.compile(r'^/[a-z0-9\-/._]*\Z')
NON_ASCII_BASELINE_REL = 'reports/factory/seo-master/non-ascii-url-baseline.txt'
NON_ASCII_BASELINE_MAX = 483          # số dòng lúc đóng băng (2026-10-27): danh sách chỉ được CO LẠI, thêm = đổi mã + review
# thư mục không dựng thành trang (khớp `exclude:` của _config.yml + thư mục hệ thống)
SOURCE_SKIP_DIRS = {'_site', '.git', '.jekyll-cache', '.sass-cache', 'node_modules', 'vendor', 'docs', 'reports', 'scripts', 'data',
                    '_drafts', 'tests', 'bin', 'build_info', 'cache', '_layouts', '_includes', '_data', 'en', 'gemfiles', '_queue'}


def read(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def page_file(site, path):
    rel = urllib.parse.unquote(path).lstrip('/')
    if not rel:
        return os.path.join(site, 'index.html')
    if path.endswith('/'):
        return os.path.join(site, rel, 'index.html')
    for cand in (os.path.join(site, rel), os.path.join(site, rel + '.html'), os.path.join(site, rel, 'index.html')):
        if os.path.isfile(cand):
            return cand
    return os.path.join(site, rel)


def source_permalinks(root):
    """{permalink: [tệp nguồn]} từ front matter của mọi trang dựng thành site (bài, trang, trang chuyển hướng)."""
    out = {}
    for dp, dns, fns in os.walk(root):
        if os.path.relpath(dp, root) == '.':
            dns[:] = [d for d in dns if d not in SOURCE_SKIP_DIRS and not d.startswith('.')]
        for fn in fns:
            if not fn.endswith(('.md', '.html', '.markdown')):
                continue
            p = os.path.join(dp, fn)
            try:
                with open(p, encoding='utf-8', errors='replace') as f:
                    head = f.read(4000)
            except OSError:
                continue
            if not head.startswith('---'):
                continue
            parts = head.split('---', 2)
            if len(parts) < 3:
                continue
            m = PERMALINK_RE.search(parts[1])
            if m:
                out.setdefault(m.group(1), []).append(os.path.relpath(p, root).replace(os.sep, '/'))
    return out


def non_ascii_baseline(root):
    p = os.path.join(root, NON_ASCII_BASELINE_REL)
    if not os.path.isfile(p):
        return set()
    with open(p, encoding='utf-8') as f:
        return {ln.strip() for ln in f if ln.strip() and not ln.startswith('#')}


def check(site, root):
    errors = []
    frozen = non_ascii_baseline(root)
    if len(frozen) > NON_ASCII_BASELINE_MAX:
        errors.append('%s có %d dòng > %d lúc đóng băng — danh sách ngoại lệ chỉ được co lại'
                      % (NON_ASCII_BASELINE_REL, len(frozen), NON_ASCII_BASELINE_MAX))
    perms = source_permalinks(root)
    for u, files in sorted(perms.items()):
        if len(files) > 1:
            errors.append('permalink trùng %s: %s' % (u, ', '.join(sorted(files)[:5])))
        if not SAFE_PERMALINK_RE.match(u):
            errors.append('permalink ngoài [a-z0-9-/] (slug phải do slugkit sinh, đ -> d): %s (%s)' % (u, files[0]))
    smp = os.path.join(site, 'sitemap.xml')
    if not os.path.isfile(smp):
        raise FileNotFoundError('thiếu sitemap.xml trong %s' % site)
    locs = LOC_RE.findall(read(smp))
    seen = set()
    host = urllib.parse.urlsplit(SITE_URL).netloc
    for loc in locs:
        if loc in seen:
            errors.append('sitemap <loc> trùng: %s' % loc)
            continue
        seen.add(loc)
        sp = urllib.parse.urlsplit(loc)
        if sp.scheme != 'https' or sp.netloc != host or sp.query or sp.fragment:
            errors.append('sitemap <loc> sai host/dạng: %s' % loc)
            continue
        if not SAFE_PATH_RE.match(sp.path) and sp.path not in frozen:
            errors.append('sitemap <loc> có đường dẫn ngoài [a-z0-9-/._] (không ASCII/chữ hoa/%%-encode): %s' % loc)
        pf = page_file(site, sp.path)
        if not pf.endswith('.html') or not os.path.isfile(pf):
            continue                                  # tệp không phải HTML (feed...) hoặc thiếu tệp: bước "Sitemap targets" kiểm
        t = read(pf)
        cans = CANON_RE.findall(t)
        if cans != [loc]:
            errors.append('URL sitemap %s: canonical %r (cần đúng một, tự trỏ)' % (loc, cans[:3]))
        if REFRESH_RE.search(t):
            errors.append('URL sitemap %s là trang chuyển hướng meta refresh' % loc)
        if NOINDEX_RE.search(t):
            errors.append('URL sitemap %s có noindex' % loc)
    by_canon = {}
    for dp, _, fns in os.walk(site):
        for fn in fns:
            if not fn.endswith('.html'):
                continue
            p = os.path.join(dp, fn)
            t = read(p)
            if REFRESH_RE.search(t) or NOINDEX_RE.search(t):
                continue                              # trang chuyển hướng/noindex trỏ canonical sang trang khác là đúng thiết kế
            cans = CANON_RE.findall(t)
            if len(cans) == 1:
                by_canon.setdefault(cans[0], []).append(os.path.relpath(p, site).replace(os.sep, '/'))
    for c, pages in sorted(by_canon.items()):
        if len(pages) > 1:
            errors.append('nhiều trang cùng canonical %s: %s' % (c, ', '.join(sorted(pages)[:5])))
    stale = sorted(frozen - {urllib.parse.urlsplit(u).path for u in seen})
    return {'permalinks': len(perms), 'sitemap_urls': len(locs), 'non_ascii_frozen': len(frozen),
            'non_ascii_frozen_gone': len(stale), 'errors': errors}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--site', default='_site')
    ap.add_argument('--root', default='.')
    ap.add_argument('--json', default='')
    a = ap.parse_args(argv)
    if not os.path.isdir(a.site):
        print('LỖI: không có thư mục site %s' % a.site, file=sys.stderr)
        return 2
    try:
        res = check(a.site, a.root)
    except FileNotFoundError as e:
        print('LỖI:', e, file=sys.stderr)
        return 2
    for e in res['errors'][:200]:
        print('FAIL:', e)
    print('permalink(nguồn)=%d sitemap=%d không-ASCII đóng băng=%d (đã rời sitemap: %d) lỗi=%d'
          % (res['permalinks'], res['sitemap_urls'], res['non_ascii_frozen'], res['non_ascii_frozen_gone'], len(res['errors'])))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    if res['errors']:
        return 1
    print('OK: URL sạch — permalink không trùng, ASCII; sitemap không trùng, canonical tự trỏ, không chuyển hướng/noindex')
    return 0


if __name__ == '__main__':
    sys.exit(main())
