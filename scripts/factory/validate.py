#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validator nền tảng cho BLOG FACTORY - thuexemayhanoi/blog
Chạy: python3 scripts/factory/validate.py  (từ gốc repository)

Mã thoát: 0 = PASS, 1 = FAIL, 2 = BLOCKED (thiếu dữ liệu nền không thể kiểm tra).

Kiểm tra theo thứ tự, báo thiếu tệp rõ ràng thay vì crash:
  1. Tệp nền tảng bắt buộc tồn tại.
  2. Taxonomy (khôi phục từ seed) nhất quán: 7 parent, 51 child, ID/slug/hub_url.
  3. Inventory khớp 100% _posts/ thực tế; URL legacy không đổi.
  4. _data/factory-taxonomy.yml và _data/factory-map.yml khớp taxonomy/inventory.
  5. Trang hub công khai cho mọi child có bài; frontmatter đúng.
  6. State + report phản ánh đúng số liệu thực (không nhận PASS tay).
  7. data/content-matrix.csv nếu có: kiểm tra toàn bộ như cũ (ID, batch, canonical...).
"""
import csv, json, os, sys, collections

ERRORS, WARNS, BLOCKED = [], [], []
def err(m): ERRORS.append(m)
def warn(m): WARNS.append(m)
def blocked(m): BLOCKED.append(m)

# ---------------- 1. tệp bắt buộc
REQUIRED = [
    'data/content-taxonomy.json',
    'data/content-inventory.csv',
    'data/state/checkpoint.json',
    'data/state/writer-lock.json',
    'data/state/transaction.json',
    'data/state/taxonomy-config.json',
    'data/state/existing-map.json',
    'data/business-facts.json',
    'reports/factory/progress.json',
    'reports/factory/latest.md',
    'reports/factory/content-hierarchy.md',
    'reports/factory/inventory-summary.md',
    'reports/factory/matrix-recovery-blocked.md',
    'reports/factory/policy-conflicts.md',
    'docs/mistral/README.md', 'docs/CONTENT-FACTORY.md', 'docs/ARTICLE-RULES.md',
    'docs/TAXONOMY.md', 'docs/SEO-OWNERSHIP.md', 'docs/RECOVERY.md',
    'scripts/factory/validate.py', 'scripts/factory/manifest.py',
    'scripts/factory/restore-foundation.py', 'scripts/factory/generate-reports.py',
    '_data/factory-taxonomy.yml', '_data/factory-map.yml',
]
for p in REQUIRED:
    if not os.path.exists(p):
        if p in ('data/content-matrix.csv',):
            continue
        err('THIẾU TỆP NỀN TẢNG: %s (chạy: python3 scripts/factory/restore-foundation.py)' % p)

if ERRORS:
    print('=== VALIDATE FOUNDATION ===')
    for e in ERRORS: print('FAIL:', e)
    print('KẾT QUẢ: FAIL (thiếu tệp nền tảng)')
    sys.exit(1)

# ---------------- 2. taxonomy
tax = json.load(open('data/content-taxonomy.json', encoding='utf-8'))
seed = json.load(open('data/state/taxonomy-config.json', encoding='utf-8'))
parents = {p['parent_id']: p for p in tax['parents']}
children = {c['child_id']: c for c in tax['children']}
if len(parents) != 7: err('taxonomy phải có đúng 7 parent, có %d' % len(parents))
if len(children) != 51: err('taxonomy phải có đúng 51 child, có %d' % len(children))
if len(seed['parents']) != 7 or len(seed['children']) != 51:
    err('seed taxonomy-config.json sai cấu trúc 7/51')
for c in tax['children']:
    if c['parent_id'] not in parents: err('child %s không thuộc parent hợp lệ' % c['child_id'])
    p = parents[c['parent_id']]
    want = '/blog/%s/%s/' % (p['slug'], c['slug'])
    if c['hub_url'] != want: err('hub_url sai tại %s: %s' % (c['child_id'], c['hub_url']))
# khớp seed (ID, slug không đổi so với nguồn)
seed_p = {s[0]: s for s in seed['parents']}
seed_c = {s[0]: s for s in seed['children']}
for pid, p in parents.items():
    if pid not in seed_p: err('parent %s không có trong seed' % pid)
    elif seed_p[pid][2] != p['slug']: err('parent %s đổi slug so với seed' % pid)
for cid, c in children.items():
    if cid not in seed_c: err('child %s không có trong seed' % cid)
    elif seed_c[cid][3] != c['slug'] or seed_c[cid][1] != c['parent_id']:
        err('child %s đổi slug/parent so với seed' % cid)

# ---------------- 3. inventory
inv = list(csv.DictReader(open('data/content-inventory.csv', encoding='utf-8')))
post_files = sorted(os.listdir('_posts'))
if len(inv) != len(post_files):
    err('inventory != số tệp _posts: %d/%d' % (len(inv), len(post_files)))
inv_paths = set(r['source_path'] for r in inv)
for fn in post_files:
    if '_posts/' + fn not in inv_paths: err('chưa ánh xạ: _posts/%s' % fn)
for r in inv:
    if r['likely_parent'] not in parents or r['likely_child'] not in children:
        err('inventory ánh xạ không hợp lệ: %s' % r['slug'])
    elif children[r['likely_child']]['parent_id'] != r['likely_parent']:
        err('inventory child/parent lệch nhau: %s' % r['slug'])
    # URL legacy: phải đúng dạng sinh từ tên tệp và KHÔNG đổi
    want = '/blog/%s/%s/' % (r['source_path'][7:17].replace('-', '/'), r['source_path'][18:-3])
    if r['current_url'] != want: err('URL legacy sai tại %s: %s' % (r['slug'], r['current_url']))

# ---------------- 4. _data cho layout
ft = open('_data/factory-taxonomy.yml', encoding='utf-8').read()
fm = open('_data/factory-map.yml', encoding='utf-8').read()
for c in tax['children']:
    if ('\n%s:\n' % c['child_id']) not in ft:
        err('_data/factory-taxonomy.yml thiếu child %s' % c['child_id'])
for r in inv:
    if ('\n%s:\n' % r['slug']) not in fm:
        err('_data/factory-map.yml thiếu slug %s' % r['slug'])

# ---------------- 5. trang hub công khai
by_child = collections.Counter(r['likely_child'] for r in inv)
for c in tax['children']:
    pslug = parents[c['parent_id']]['slug']
    page = os.path.join(pslug, c['slug'] + '.md')
    if by_child.get(c['child_id'], 0) > 0 and not os.path.exists(page):
        warn('child %s có %d bài nhưng chưa có trang hub công khai' % (c['child_id'], by_child[c['child_id']]))
for pslug_dir in [p['slug'] for p in tax['parents']]:
    if not os.path.exists(pslug_dir + '.md'):
        err('thiếu trang parent hub: %s.md' % pslug_dir)

# ---------------- 6. state + report
prog = json.load(open('reports/factory/progress.json', encoding='utf-8'))
cp = json.load(open('data/state/checkpoint.json', encoding='utf-8'))
if prog['rows']['legacy_total'] != len(inv): err('progress legacy_total lệch thực tế')
if prog['rows']['legacy_mapped'] != len(inv): err('progress legacy_mapped lệch thực tế')
if cp['counts']['legacy_total'] != len(inv): err('checkpoint legacy_total lệch thực tế')
if cp['counts']['existing'] + cp['counts']['review'] != len(inv):
    err('checkpoint existing+review != tổng bài legacy')
lock = json.load(open('data/state/writer-lock.json', encoding='utf-8'))
if lock.get('locked') is not False: warn('writer-lock đang bị giữ: kiểm tra writer sống')
txn = json.load(open('data/state/transaction.json', encoding='utf-8'))
if txn.get('active'): err('transaction đang treo active=true — cần recover trước khi sản xuất')

# ---------------- 7. matrix (nếu có)
MATRIX = 'data/content-matrix.csv'
mstat = None
if os.path.exists(MATRIX):
    with open(MATRIX, encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 10000: err('matrix số hàng != 10000: %d' % len(rows))
    ids = [r['id'] for r in rows]
    expected = ['BLG-%05d' % i for i in range(1, 10001)]
    if ids != expected: err('matrix ID không phải BLG-00001..BLG-10000 đúng thứ tự')
    dupc = [k for k, v in collections.Counter(r['canonical_url'] for r in rows).items() if v > 1]
    if dupc: err('matrix canonical_url trùng: %d' % len(dupc))
    batches = collections.Counter(r['batch_id'] for r in rows)
    if len(batches) != 200: err('matrix số batch != 200: %d' % len(batches))
    for i, r in enumerate(rows):
        if r['batch_id'] != 'BATCH-%03d' % (i // 50 + 1):
            err('matrix batch sai thứ tự tại %s' % r['id']); break
    stat_valid = {'PLANNED','WRITING','QA','PASS','PUBLISHED','REVIEW','REPAIR','BLOCKED','FAIL','EXISTING'}
    mstat = collections.Counter()
    can_seen = {}
    for r in rows:
        if r['status'] not in stat_valid: err('matrix status không hợp lệ: %s' % r['status'])
        mstat[r['status']] += 1
        if r['parent_id'] not in parents or r['child_id'] not in children:
            err('matrix parent/child không hợp lệ tại %s' % r['id'])
        k = r['cannibalization_key']
        if k in can_seen:
            if r['status'] == 'PLANNED': err('PLANNED %s trùng cannibalization_key với %s' % (r['id'], can_seen[k]))
            else: warn('cannibalization REVIEW: %s và %s' % (can_seen[k], r['id']))
        else:
            can_seen[k] = r['id']
        if r['status'] == 'PLANNED':
            p, c = parents[r['parent_id']], children[r['child_id']]
            want = '/%s/%s/%s/' % (p['slug'], c['slug'], r['slug'])
            if r['output_path'] != want: err('matrix output_path sai tại %s' % r['id'])
            if r['canonical_url'] != 'https://thuexemayhanoi.github.io/blog' + want:
                err('matrix canonical_url sai tại %s' % r['id'])
    if cp['counts'].get('existing') != mstat.get('EXISTING', 0) + mstat.get('PUBLISHED', 0) + mstat.get('REVIEW', 0):
        err('checkpoint lệch trạng thái matrix')
else:
    blocked('data/content-matrix.csv THIẾU — chưa từng được commit, không thể khôi phục. Bằng chứng và hướng xử lý: reports/factory/matrix-recovery-blocked.md. Không nhận hàng PLANNED. Đây là BLOCKED có chủ đích, không phải PASS.')

print('=== VALIDATE FOUNDATION ===')
print('Taxonomy: %d parent / %d child | Inventory: %d bài legacy | Matrix: %s' % (
    len(parents), len(children), len(inv), 'CÓ' if mstat else 'BLOCKED (thiếu)'))
if mstat: print('Trạng thái matrix: %s' % dict(mstat))
for b in BLOCKED: print('BLOCKED:', b)
for w_ in WARNS: print('WARN:', w_)
for e in ERRORS: print('FAIL:', e)
if ERRORS:
    print('KẾT QUẢ: FAIL'); sys.exit(1)
if BLOCKED:
    print('KẾT QUẢ: BLOCKED (nền trừ matrix hợp lệ)'); sys.exit(2)
print('KẾT QUẢ: PASS (%d cảnh báo)' % len(WARNS)); sys.exit(0)
