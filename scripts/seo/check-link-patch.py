#!/usr/bin/env python3
"""Kiểm tra xác định một bản vá THÊM LIÊN KẾT NỘI BỘ cho bài (dùng cho bài legacy sửa trực tiếp được).

Bản vá (schema link-patches/1): {"schema": "link-patches/1", "patches": {"<BLG-ID>": {"file": "_posts/...md", "edits": [{"old": "...", "new": "..."}]}}}
Mỗi edit chỉ được BỌC một liên kết Markdown quanh chữ đã có: bỏ cú pháp [chữ](đích) khỏi `new` phải ra đúng `old`.

Quy tắc (đúng quy tắc liên kết nội bộ của chủ website):
  R1  `old` xuất hiện đúng 1 lần trong thân bài (sau front matter), các edit không chồng nhau, không đụng front matter.
  R2  `new` = `old` + đúng 1 liên kết Markdown mới; chữ còn lại giữ nguyên từng ký tự.
  R3  Đích là đường dẫn nội bộ (/...), tồn tại trong bản build (--site), không phải chính bài, không phải URL RETIRED.
  R4  Sau khi áp dụng: mỗi đoạn văn có tối đa 1 liên kết nội bộ; không đích nào xuất hiện 2 lần trong bài; không anchor trùng nhau.
  R5  Anchor dài 2–9 từ, không phải nguyên văn tiêu đề trang đích dài (tránh nhồi exact-match).
Thoát 0 khi mọi bài PASS; in JSON kết quả. --apply ghi tệp (chỉ khi mọi bài PASS).
"""
import argparse
import csv
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINK = re.compile(r'\[([^\]\n]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
BASE = 'https://blog.thuexemaynguyentu.com'


def internal(href):
    if href.startswith(BASE):
        href = href[len(BASE):] or '/'
    return href if href.startswith('/') and not href.startswith('//') else None


def exists(site, path):
    p = urllib.parse.unquote(path.split('#')[0])
    if p.endswith('/'):
        return os.path.isfile(os.path.join(site, p.lstrip('/'), 'index.html'))
    return os.path.isfile(os.path.join(site, p.lstrip('/')))


def split_fm(text):
    if text.startswith('---\n'):
        j = text.index('\n---\n', 4) + 5
        return text[:j], text[j:]
    return '', text


def permalink(fm):
    m = re.search(r'^permalink:\s*(\S+)', fm, re.M)
    return m.group(1).strip('"\'') if m else ''


def check_one(aid, patch, site, retired):
    errs = []
    path = os.path.join(ROOT, patch['file'])
    with open(path, encoding='utf-8') as f:
        text = f.read()
    fm, body = split_fm(text)
    self_url = permalink(fm)
    spans = []
    new_body = body
    added = []
    for i, e in enumerate(patch['edits']):
        old, new = e['old'], e['new']
        if body.count(old) != 1:
            errs.append('E%d R1: old xuất hiện %d lần' % (i, body.count(old)))
            continue
        s = body.index(old)
        spans.append((s, s + len(old), i))
        old_links = LINK.findall(old)
        new_links = LINK.findall(new)
        if LINK.sub(lambda m: m.group(1), new) != LINK.sub(lambda m: m.group(1), old) or len(new_links) != len(old_links) + 1:
            errs.append('E%d R2: new không chỉ bọc thêm đúng 1 liên kết quanh chữ có sẵn' % i)
            continue
        fresh = [l for l in new_links if l not in old_links]
        line_start = body.rfind('\n', 0, s) + 1
        if body[line_start:s + len(old)].lstrip().startswith('#'):
            errs.append('E%d R2: không chèn liên kết vào dòng tiêu đề' % i)
            continue
        anchor, href = fresh[0]
        p = internal(href)
        if not p:
            errs.append('E%d R3: đích không phải đường dẫn nội bộ: %s' % (i, href))
            continue
        if urllib.parse.unquote(p.split('#')[0]) in retired:
            errs.append('E%d R3: đích là URL RETIRED (404): %s' % (i, p))
        if not exists(site, p):
            errs.append('E%d R3: đích không tồn tại trong bản build: %s' % (i, p))
        if self_url and urllib.parse.unquote(p.split('#')[0]) == urllib.parse.unquote(self_url):
            errs.append('E%d R3: tự trỏ về chính bài' % i)
        nw = len(anchor.split())
        if nw < 2 or nw > 9:
            errs.append('E%d R5: anchor %d từ (cần 2-9): %r' % (i, nw, anchor))
        added.append((anchor, urllib.parse.unquote(p.split('#')[0])))
    spans.sort()
    for a, b in zip(spans, spans[1:]):
        if a[1] > b[0]:
            errs.append('R1: edit E%d và E%d chồng nhau' % (a[2], b[2]))
    if not errs:
        for e in patch['edits']:
            new_body = new_body.replace(e['old'], e['new'], 1)
        hrefs = [internal(h) for _, h in LINK.findall(new_body)]
        hrefs = [urllib.parse.unquote(h.split('#')[0]) for h in hrefs if h]
        for h in set(hrefs):
            if hrefs.count(h) > 1 and h in {x[1] for x in added}:
                errs.append('R4: đích %s xuất hiện %d lần trong bài' % (h, hrefs.count(h)))
        anchors = [x[0].strip().lower() for x in added]
        if len(anchors) != len(set(anchors)):
            errs.append('R4: anchor trùng nhau')
        for para in re.split(r'\n\s*\n', new_body):
            n = sum(1 for _, h in LINK.findall(para) if internal(h))
            if n > 1 and any(e['new'] in para for e in patch['edits']):
                errs.append('R4: một đoạn có %d liên kết nội bộ: %r' % (n, para.strip()[:90]))
    return errs, fm + new_body, added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--patches', required=True)
    ap.add_argument('--site', required=True)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    with open(a.patches, encoding='utf-8') as f:
        data = json.load(f)
    if data.get('schema') != 'link-patches/1':
        sys.exit('schema phải là link-patches/1')
    retired = set()
    reg = os.path.join(ROOT, 'reports', 'factory', 'seo-master', 'slug-redirect-registry.csv')
    with open(reg, encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            if r['status'] == 'RETIRED':
                retired.add(r['old_url'])
    out, ok, writes = {}, True, []
    for aid, patch in sorted(data['patches'].items()):
        errs, new_text, added = check_one(aid, patch, a.site, retired)
        out[aid] = {'pass': not errs, 'errors': errs, 'links_added': [{'anchor': x, 'target': y} for x, y in added]}
        ok = ok and not errs
        writes.append((patch['file'], new_text))
    print(json.dumps({'all_pass': ok, 'results': out}, ensure_ascii=False, indent=1))
    if a.apply:
        if not ok:
            sys.exit('không ghi: còn bài FAIL')
        for rel, text in writes:
            with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
                f.write(text)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
