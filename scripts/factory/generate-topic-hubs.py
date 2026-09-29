#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SINH TRANG HUB CHỦ ĐỀ THIẾU — thuexemayhanoi/blog.

Vấn đề: hàng PLANNED của matrix có internal_links trỏ tới hub của taxonomy
(/blog/<parent>/<child>/) nhưng trang hub chưa tồn tại -> QA route-truth
từ chối hàng (bảo vệ đúng), nhưng dependency không bao giờ được "im lặng":
hub phải được sinh TRƯỚC khi bài được xuất bản.

Giải pháp nguồn (root-cause), deterministic + idempotent:
quét internal_links mọi hàng matrix (PLANNED/WRITING/QA/REPAIR/PASS/PUBLISHED),
rút gọn về route hub dạng /<parent>/<child>/ theo taxonomy; ĐỒNG THỜI yêu
cầu hub cho MỌI child của taxonomy — vì topic-directory (homepage, /chu-de/)
và article-breadcrumb render link toàn bộ children, một child thiếu hub là
link 404 công khai ngay cả khi chưa có bài nào gắn child đó. Với mỗi hub
chưa có tệp <parent>/<child>.md — sinh trang hub tối thiển từ taxonomy
(layout topic chuẩn của site).

Không đụng: checkpoint, writer-lock, transaction, REVIEW, PUBLISHED nội dung.

Chạy: python3 scripts/factory/generate-topic-hubs.py  (từ gốc repository)
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

TAX_PATH = 'data/content-taxonomy.json'
MATRIX = 'data/content-matrix.csv'
LINK_STATUS = ('PLANNED', 'WRITING', 'QA', 'REPAIR', 'PASS', 'PUBLISHED', 'REVIEW')


def main():
    tax = json.load(open(TAX_PATH, encoding='utf-8'))
    parents = {p['parent_id']: p for p in tax['parents']}
    by_route = {}
    for c in tax['children']:
        pslug = parents[c['parent_id']]['slug']
        by_route['/%s/%s/' % (pslug, c['slug'])] = (pslug, c)

    # Mọi child taxonomy đều cần hub: topic-directory (homepage, /chu-de/)
    # và breadcrumb render link toàn bộ children — thiếu hub = 404 công khai.
    required = set(by_route)
    rows = list(csv.DictReader(open(MATRIX, encoding='utf-8')))
    for r in rows:
        if r['status'] not in LINK_STATUS:
            continue
        for l in (r['internal_links'] or '').split(';'):
            l = l.strip().rstrip(';').strip()
            if not l:
                continue
            route = l.split('#', 1)[0]
            if route.startswith('/blog'):
                route = route[len('/blog'):]
            if route in by_route:
                required.add(route)

    created = []
    for route in sorted(required):
        pslug, child = by_route[route]
        path = os.path.join(pslug, child['slug'] + '.md')
        if os.path.exists(path):
            continue
        parent = parents[child['parent_id']]
        desc = (child.get('description') or child['title']).strip()
        title = '%s - %s' % (child['title'], parent['title'])
        os.makedirs(pslug, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('---\n'
                    'layout: topic\n'
                    'title: "%s"\n'
                    'description: "%s"\n'
                    'lang: vi\n'
                    'permalink: %s\n'
                    'parent_id: %s\n'
                    'parent_title: %s\n'
                    'parent_slug: %s\n'
                    'child_id: %s\n'
                    '---\n\n'
                    '%s\n' % (title, desc, route, child['parent_id'],
                              parent['title'], pslug, child['child_id'], desc))
        created.append(route)

    if created:
        print('Đã sinh hub mới: %d' % len(created))
        for r in created:
            print(' -', r)
    else:
        print('OK: mọi hub được matrix tham chiếu đều đã tồn tại (idempotent).')
    # báo cáo route yêu cầu mà vẫn thiếu (không thể xảy ra với taxonomy khớp)
    missing = [r for r in sorted(required)
               if not os.path.exists(os.path.join(*r.strip('/').split('/')) + '.md')]
    if missing:
        print('THIẾU (STOP):', missing)
        sys.exit(1)


if __name__ == '__main__':
    main()
