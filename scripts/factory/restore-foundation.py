#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Khôi phục dữ liệu nền factory từ seed đã commit - thuexemayhanoi/blog.

Chạy: python3 scripts/factory/restore-foundation.py  (từ gốc repository)

Nguồn sự thật (đã commit, không được chỉnh sửa):
  - data/state/taxonomy-config.json  (seed bootstrap: 7 parent, 51 child, pools, templates, quota)
  - data/state/existing-map.json     (ánh xạ 483 bài legacy: slug -> [date_index, parent_index, child_index])
  - _posts/                          (danh sách tệp bài legacy thực tế)

Sinh ra (idempotent, không bịa dữ liệu):
  - data/content-taxonomy.json       (taxonomy máy đọc được, khôi phục từ seed)
  - data/content-inventory.csv       (kiểm kê 483 bài legacy, URL giữ nguyên)
  - _data/factory-taxonomy.yml      (child_id -> parent/slug/title cho layout hub)
  - _data/factory-map.yml           (slug bài legacy -> parent/child cho layout hub)
  - _data/factory-parents.yml       (parent_id -> slug/title cho topic-directory)

LƯU Ý QUAN TRỌNG: data/content-matrix.csv KHÔNG thể khôi phục từ nguồn nào
đã commit (không có trong lịch sử git, không có trong seed). Script này KHÔNG
sinh matrix. Trạng thái matrix: BLOCKED - xem reports/factory/matrix-recovery-blocked.md.

Thoát mã 0 = thành công, 1 = lỗi.
"""
import csv, json, os, re, sys, io

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

def die(msg):
    print('FAIL:', msg)
    sys.exit(1)

# ---------------- đọc seed
try:
    seed = json.load(open('data/state/taxonomy-config.json', encoding='utf-8'))
    emap = json.load(open('data/state/existing-map.json', encoding='utf-8'))
except OSError as e:
    die('thiếu seed: %s' % e)

parents_seed = seed['parents']
children_seed = seed['children']

# ---------------- taxonomy
parents = []
for pid, title, slug, desc in parents_seed:
    parents.append({
        'parent_id': pid, 'title': title, 'slug': slug,
        'hub_url': '/%s/' % slug, 'description': desc,
    })
children = []
for cid, pid, title, slug, desc, kw_head, kw_cluster, group, planned_target, \
        intent, level, legal_risk, source_required in children_seed:
    pslug = {p['parent_id']: p['slug'] for p in parents}[pid]
    children.append({
        'child_id': cid, 'parent_id': pid, 'title': title, 'slug': slug,
        'hub_url': '/%s/%s/' % (pslug, slug), 'description': desc,
        'cluster_keyword': kw_cluster, 'group': group,
        'planned_target': planned_target,
        'search_intent': intent, 'commercial_level': level,
        'legal_risk': legal_risk, 'source_required': bool(source_required),
    })

taxonomy = {
    'version': 1,
    'restored_from': 'data/state/taxonomy-config.json',
    'parents': parents,
    'children': children,
    'note': 'Khôi phục từ seed bootstrap 2026-09-27. ID và slug giữ nguyên. Không chỉnh sửa tay.',
}
with open('data/content-taxonomy.json', 'w', encoding='utf-8') as f:
    json.dump(taxonomy, f, ensure_ascii=False, indent=2)
    f.write('\n')

# ---------------- inventory từ _posts thật + existing-map
post_files = sorted(os.listdir('_posts'))
emap_map = emap['map']
emap_children = emap['children']
emap_parents = emap['parents']
emap_dates = emap['dates']
parent_by_id = {p['parent_id']: p for p in parents}
child_by_id = {c['child_id']: c for c in children}

rows = []
title_re = re.compile(r'^title:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)
cat_re = re.compile(r'^categories:\s*\[?["\']?([^"\'\],]+)', re.MULTILINE)
date_re = re.compile(r'^date:\s*(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?\s*([+-]\d{2})(\d{2})?', re.MULTILINE)
# bài factory (có article_id:) KHÔNG thuộc legacy inventory — validate.py
# kiểm chứng riêng đối chiếu matrix PUBLISHED; legacy = không có article_id.
post_files = [fn for fn in post_files
              if not re.search(r'^article_id:', open(os.path.join('_posts', fn), encoding='utf-8').read()[:2000], re.M)]
for fn in post_files:
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)\.md$', fn)
    if not m:
        die('tên tệp _posts không đúng dạng: %s' % fn)
    date, slug = m.group(1) + '-' + m.group(2) + '-' + m.group(3), m.group(4)
    if slug not in emap_map:
        die('bài legacy không có trong existing-map: %s' % fn)
    di, pi, ci = emap_map[slug]
    pid, cid = emap_parents[pi], emap_children[ci]
    if pid not in parent_by_id or cid not in child_by_id:
        die('ánh xạ không hợp lệ tại %s: %s/%s' % (fn, pid, cid))
    if child_by_id[cid]['parent_id'] != pid:
        die('child %s không thuộc parent %s tại %s' % (cid, pid, fn))
    text = open(os.path.join('_posts', fn), encoding='utf-8').read()
    tm = title_re.search(text[:2000])
    title = (tm.group(1) if tm else '').strip()
    cm = cat_re.search(text[:2000])
    category = (cm.group(1) if cm else '').strip()
    if not category: die('thiếu categories tại %s' % fn)
    dm = date_re.search(text[:2000])
    if not dm: die('thiếu date hợp lệ tại %s' % fn)
    # URL dùng ngày frontmatter sau khi Jekyll chuẩn hoá về UTC
    # (ví dụ 2026-09-20 01:10 +0700 -> 2026-09-19 18:10 UTC -> URL .../2026/09/19/...)
    import datetime as _dt
    off_h, off_m = int(dm.group(7)), int(dm.group(8) or 0)
    sign = 1 if dm.group(7).startswith('+') else -1
    fdt = _dt.datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)),
                       int(dm.group(4)), int(dm.group(5)), int(dm.group(6) or 0)) - sign * _dt.timedelta(hours=abs(off_h), minutes=off_m)
    y, mo, d = '%04d' % fdt.year, '%02d' % fdt.month, '%02d' % fdt.day
    # URL legacy THẬT do Jekyll sinh (permalink pretty gồm tên danh mục có dấu):
    # /{Danh mục}/YYYY/MM/DD/slug/ — giữ nguyên, không đổi.
    rows.append({
        'source_path': '_posts/' + fn,
        'slug': slug,
        'published_date': emap_dates[di],
        'category': category,
        'current_url': '/%s/%s/%s/%s/%s/' % (category.lower(), y, mo, d, slug),
        'likely_parent': pid,
        'likely_child': cid,
        'title': title,
    })

if len(rows) != len(post_files):
    die('inventory lệch số tệp _posts')

with open('data/content-inventory.csv', 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)

# ---------------- _data cho layout hub
with open('_data/factory-taxonomy.yml', 'w', encoding='utf-8') as f:
    f.write('# Sinh bởi scripts/factory/restore-foundation.py từ data/state/taxonomy-config.json.\n')
    f.write('# child_id -> p(parent_id), s(slug), t(title). Không sửa tay.\n')
    for c in children:
        f.write('%s:\n  p: %s\n  s: %s\n  t: "%s"\n' % (c['child_id'], c['parent_id'], c['slug'], c['title']))

with open('_data/factory-map.yml', 'w', encoding='utf-8') as f:
    f.write('# Sinh bởi scripts/factory/restore-foundation.py từ data/state/existing-map.json.\n')
    f.write('# slug bài legacy -> p(parent_id), c(child_id). Không sửa tay.\n')
    for r in rows:
        f.write('%s:\n  p: %s\n  c: %s\n' % (r['slug'], r['likely_parent'], r['likely_child']))

print('=== RESTORE FOUNDATION ===')
print('taxonomy: %d parent, %d child (khôi phục từ seed)' % (len(parents), len(children)))
print('inventory: %d bài legacy, URL giữ nguyên' % len(rows))
with open('_data/factory-parents.yml', 'w', encoding='utf-8') as f:
    f.write('# Sinh bởi scripts/factory/restore-foundation.py từ data/state/taxonomy-config.json.\n')
    f.write('# parent_id -> s(slug), t(title). Không sửa tay.\n')
    for p in parents:
        f.write('%s:\n  s: %s\n  t: "%s"\n' % (p['parent_id'], p['slug'], p['title']))

print('_data/factory-taxonomy.yml + _data/factory-map.yml + _data/factory-parents.yml: đã sinh')
if not os.path.exists('data/content-matrix.csv'):
    print('BLOCKED: data/content-matrix.csv không thể khôi phục từ nguồn đã commit — xem reports/factory/matrix-recovery-blocked.md')
print('KẾT QUẢ: PASS')
