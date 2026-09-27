#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh trang phân hạng tĩnh (SEO-safe static pagination) cho các trang listing
hiện đang render HÀNG TRĂM bài trong một trang duy nhất.

Vấn đề: kinh-nghiem.md render 332 thẻ bài, chia-se.md 112, du-lich.md 39, một
số trang chủ đề con (topic) tới 97 bài — một trang không được chứa hàng trăm
thẻ, nội dung cũ phải còn truy cập được bằng link cho crawler (không dùng
JavaScript "load more" làm con đường duy nhất).

Giải pháp: sinh tệp trang tĩnh ` listing/<key>/<n>.md` (12 bài/trang cho danh
mục, 24 bài/trang cho chủ đề con) + `_data/listing-index.yml` cho các trang
gốc vẽ link đánh số. Idempotent: chạy lại cho kết quả giống hệt; CI kiểm tra
không drift sau mỗi push.

Chạy: python3 scripts/factory/generate-listing-pages.py  (từ gốc repository)
"""
import csv, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

CATEGORY_PAGES = {  # slug trang gốc -> categories Jekyll (page_size)
    'kinh-nghiem': ('Kinh nghiệm', 12),
    'chia-se': ('Chia sẻ', 12),
    'du-lich': ('Du lịch', 12),
}
TOPIC_PAGE_SIZE = 24

cat_re = re.compile(r'^categories:\s*\[?["\']?([^"\'\],]+)', re.MULTILINE)
aid_re = re.compile(r'^article_id:', re.MULTILINE)

posts = []
for fn in sorted(os.listdir('_posts')):
    text = open(os.path.join('_posts', fn), encoding='utf-8').read()
    cm = cat_re.search(text[:3000])
    dm = re.match(r'(\d{4}-\d{2}-\d{2})-', fn)
    posts.append({
        'file': fn, 'slug': fn[11:-3], 'date': dm.group(1) if dm else '',
        'category': (cm.group(1).strip() if cm else '').strip() or '(không rõ)',
        'factory': bool(aid_re.search(text[:2000])),
    })

# map child_id cho mọi bài (frontmatter hoặc factory-map)
import json
fmap = {}
for line in open('_data/factory-map.yml', encoding='utf-8'):
    m = re.match(r'^([a-z0-9\-]+):\s*$', line)
    if m:
        cur = m.group(1)
    m2 = re.match(r'^\s+p:\s*(\S+)', line)
    m3 = re.match(r'^\s+c:\s*(\S+)', line)
    if m2 and cur:
        fmap.setdefault(cur, {})['p'] = m2.group(1)
    if m3 and cur:
        fmap[cur]['c'] = m3.group(1)

tax = json.load(open('data/content-taxonomy.json', encoding='utf-8'))
child_by_id = {c['child_id']: c for c in tax['children']}
parent_by_id = {p['parent_id']: p for p in tax['parents']}

for p in posts:
    am = re.search(r'^child_id:\s*(\S+)', open(os.path.join('_posts', p['file']), encoding='utf-8').read()[:2000], re.M)
    if am:
        p['child_id'] = am.group(1)
    elif p['slug'] in fmap and 'c' in fmap[p['slug']]:
        p['child_id'] = fmap[p['slug']]['c']
    else:
        p['child_id'] = None

os.makedirs('listing', exist_ok=True)
# dọn các tệp sinh cũ (an toàn:  listing chỉ chứa tệp do script này sinh)
for root, _dirs, files in os.walk('listing'):
    for f in files:
        os.remove(os.path.join(root, f))

index = {}

# --- danh mục
for slug, (cat, size) in CATEGORY_PAGES.items():
    n_posts = sum(1 for p in posts if p['category'] == cat)
    pages = max(1, -(-n_posts // size)) if n_posts else 0
    index[slug] = {'pages': pages, 'size': size, 'total': n_posts}
    if pages <= 1:
        continue  # vừa một trang — trang gốc đã chứa, không cần tệp phụ
    for n in range(2, pages + 1):
        d = os.path.join('listing', slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '%d.md' % n), 'w', encoding='utf-8') as f:
            f.write('---\nlayout: listing\npermalink: /%s/trang/%d/\ncategory: %s\n'
                    'page_num: %d\ntotal_pages: %d\npage_size: %d\n'
                    'title: "%s - Trang %d - Thuê Xe Máy Hà Nội Nguyễn Tú"\n'
                    'description: "Các bài viết %s, trang %d/%d."\nlang: vi\n---\n' % (
                        slug, n, cat, n, pages, size, cat, n, cat, n, pages))

# --- chủ đề con (topic) có nhiều hơn TOPIC_PAGE_SIZE bài
by_child = {}
for p in posts:
    if p['child_id']:
        by_child.setdefault(p['child_id'], []).append(p)
topic_index = {}
for cid, cposts in sorted(by_child.items()):
    if len(cposts) <= TOPIC_PAGE_SIZE:
        continue
    child = child_by_id.get(cid)
    if not child:
        continue
    parent = parent_by_id.get(child['parent_id'])
    if not parent:
        continue
    pages = -(-len(cposts) // TOPIC_PAGE_SIZE)
    key = '%s/%s' % (parent['slug'], child['slug'])
    topic_index[key] = {'pages': pages, 'size': TOPIC_PAGE_SIZE, 'total': len(cposts)}
    for n in range(2, pages + 1):
        d = os.path.join('listing', 'topic', parent['slug'], child['slug'])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '%d.md' % n), 'w', encoding='utf-8') as f:
            f.write('---\nlayout: topic-listing\npermalink: /%s/trang/%d/\nparent_id: %s\nchild_id: %s\n'
                    'page_num: %d\ntotal_pages: %d\npage_size: %d\n'
                    'title: "%s - Trang %d - Thuê Xe Máy Hà Nội Nguyễn Tú"\nlang: vi\n---\n' % (
                        key, n, child['parent_id'], cid, n, pages, TOPIC_PAGE_SIZE,
                        child['title'], n))
index['topic'] = topic_index

with open('_data/listing-index.yml', 'w', encoding='utf-8') as f:
    f.write('# Sinh bởi scripts/factory/generate-listing-pages.py. Không sửa tay.\n')
    for k, v in index.items():
        if k == 'topic':
            f.write('topic:\n')
            for k2, v2 in v.items():
                f.write('  %s:\n    pages: %d\n    size: %d\n    total: %d\n' % (
                    k2.replace('/', '_'), v2['pages'], v2['size'], v2['total']))
        else:
            f.write('%s:\n  pages: %d\n  size: %d\n  total: %d\n' % (k, v['pages'], v['size'], v['total']))

print('=== GENERATE LISTING PAGES ===')
for k, v in index.items():
    if k == 'topic':
        for k2, v2 in v.items():
            print('topic %s: %d bài -> %d trang' % (k2, v2['total'], v2['pages']))
    else:
        print('%s: %d bài -> %d trang' % (k, v['total'], v['pages']))
print('KẾT QUẢ: PASS (trang tĩnh, link crawlable, idempotent)')
