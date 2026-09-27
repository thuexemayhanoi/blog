#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validator nền tảng cho BLOG FACTORY - thuexemayhanoi/blog
Chạy: python3 scripts/factory/validate.py  (từ gốc repository)
Kiểm tra data/content-matrix.csv, data/content-taxonomy.json, inventory, state, reports.
Thoát mã 0 = PASS, 1 = FAIL.
"""
import csv, json, os, sys, re, unicodedata, collections

def norm_tokens(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    return [t for t in s.split() if t]

ERRORS, WARN = [], []
def err(m): ERRORS.append(m)
def warn(m): WARN.append(m)

# ---------------- taxonomy
tax = json.load(open('data/content-taxonomy.json', encoding='utf-8'))
parents = {p['parent_id']: p for p in tax['parents']}
children = {c['child_id']: c for c in tax['children']}
if len(parents) < 5 or len(parents) > 8: warn('Số parent ngoài khuyến nghị 5-8: %d' % len(parents))
for c in tax['children']:
    if c['parent_id'] not in parents: err('child %s không thuộc parent hợp lệ' % c['child_id'])
child_ids = set(children)
for p in tax['parents']:
    if not any(c['parent_id'] == p['parent_id'] for c in tax['children']):
        err('parent %s không có child nào' % p['parent_id'])

# ---------------- matrix
with open('data/content-matrix.csv', encoding='utf-8', newline='') as f:
    rows = list(csv.DictReader(f))
if len(rows) != 10000: err('Số hàng != 10000: %d' % len(rows))
ids = [r['id'] for r in rows]
expected = ['BLG-%05d' % i for i in range(1, 10001)]
if ids != expected: err('ID không phải chuỗi BLG-00001..BLG-10000 đúng thứ tự')
if len(set(ids)) != 10000: err('ID trùng')
canon = collections.Counter(r['canonical_url'] for r in rows)
dupc = [k for k, v in canon.items() if v > 1]
if dupc: err('canonical_url trùng: %d' % len(dupc))
slugs = collections.Counter(r['slug'] for r in rows)
if [k for k, v in slugs.items() if v > 1]: err('slug trùng')
batches = collections.Counter(r['batch_id'] for r in rows)
if len(batches) != 200: err('Số batch != 200: %d' % len(batches))
for b, v in batches.items():
    if v != 50: err('batch %s có %d hàng (phải 50)' % (b, v))
    n = int(b.split('-')[1])
    for r in rows:
        pass  # thứ tự kiểm tra dưới
for i, r in enumerate(rows):
    if r['batch_id'] != 'BATCH-%03d' % (i // 50 + 1): err('batch sai thứ tự tại %s' % r['id']); break
stat_valid = {'PLANNED','WRITING','QA','PASS','PUBLISHED','REVIEW','REPAIR','BLOCKED','FAIL','EXISTING'}
can_seen = {}
ex_count = collections.Counter()
for i, r in enumerate(rows):
    if r['status'] not in stat_valid: err('status không hợp lệ: %s' % r['status'])
    if r['parent_id'] not in parents: err('parent không hợp lệ tại %s' % r['id'])
    if r['child_id'] not in child_ids: err('child không hợp lệ tại %s' % r['id'])
    if children[r['child_id']]['parent_id'] != r['parent_id']:
        err('child %s không thuộc parent %s tại %s' % (r['child_id'], r['parent_id'], r['id']))
    k = r['cannibalization_key']
    if k in can_seen:
        if r['status'] == 'PLANNED': err('PLANNED %s trùng cannibalization_key với %s' % (r['id'], can_seen[k]))
        else: warn('cannibalization REVIEW: %s và %s' % (can_seen[k], r['id']))
    else:
        can_seen[k] = r['id']
    if r['status'] in ('EXISTING', 'PUBLISHED', 'REVIEW'):
        ex_count[r['child_id']] += 1
    if r['status'] == 'EXISTING' and not r['source_path'].startswith('_posts/'):
        err('EXISTING không có source_path hợp lệ: %s' % r['id'])
    if r['status'] == 'PLANNED' and r['source_path']:
        err('PLANNED không được có source_path: %s' % r['id'])
    if r['status'] in ('EXISTING','PUBLISHED','REVIEW') and not r['published_date'] and r['status'] != 'REVIEW':
        err('hàng đã xuất bản thiếu published_date: %s' % r['id'])
# output path collision
outs = collections.Counter(r['output_path'] for r in rows)
if [k for k, v in outs.items() if v > 1]: err('output_path trùng')

# ---------------- inventory mapping
inv = list(csv.DictReader(open('data/content-inventory.csv', encoding='utf-8')))
post_files = sorted(os.listdir('_posts'))
if len(inv) != len(post_files): err('inventory != số tệp _posts: %d/%d' % (len(inv), len(post_files)))
inv_paths = set(r['source_path'] for r in inv)
for fn in post_files:
    if '_posts/' + fn not in inv_paths: err('chưa ánh xạ: _posts/%s' % fn)
for r in inv:
    if r['likely_parent'] not in parents or r['likely_child'] not in child_ids:
        err('inventory ánh xạ không hợp lệ: %s' % r['slug'])
# legacy URLs unchanged: so khớp URL sinh từ tên tệp
for r in inv:
    date, slug = r['source_path'][7:17], r['source_path'][18:-3]
    want = '/blog/%s/%s/' % (date.replace('-', '/'), slug)
    if r['current_url'] != want: err('URL legacy sai tại %s' % r['slug'])

# ---------------- child hub pages only where content exists (soft check)
for c in tax['children']:
    pslug = parents[c['parent_id']]['slug']
    page = os.path.join(pslug, c['slug'] + '.md')
    has_page = os.path.exists(page)
    if ex_count[c['child_id']] > 0 and not has_page:
        warn('child %s có %d bài nhưng chưa có trang hub công khai' % (c['child_id'], ex_count[c['child_id']]))

# ---------------- state + reports
for p in ['data/state/checkpoint.json', 'data/state/writer-lock.json', 'data/state/transaction.json',
          'reports/factory/progress.json', 'data/content-taxonomy.json', 'data/content-matrix.csv',
          'data/content-inventory.csv', 'data/business-facts.json',
          'docs/mistral/README.md', 'docs/CONTENT-FACTORY.md', 'docs/ARTICLE-RULES.md',
          'docs/TAXONOMY.md', 'docs/SEO-OWNERSHIP.md', 'docs/RECOVERY.md',
          'scripts/factory/validate.py', 'scripts/factory/manifest.py']:
    if not os.path.exists(p): err('thiếu tệp nền tảng: %s' % p)
prog = json.load(open('reports/factory/progress.json', encoding='utf-8'))
mstat = collections.Counter(r['status'] for r in rows)
pr = prog['rows']
for k, v in mstat.items():
    if pr.get(k.lower(), 0) != v: err('progress.json lệch state %s: %d vs %d' % (k, pr.get(k.lower(), 0), v))
if prog['capacity'] != 10000: err('progress capacity sai')
lock = json.load(open('data/state/writer-lock.json', encoding='utf-8'))
if lock['locked'] is not False: warn('writer-lock đang bị giữ: kiểm tra writer sống')
txn = json.load(open('data/state/transaction.json', encoding='utf-8'))
if txn.get('active'): err('transaction đang treo active=true — cần recover trước khi sản xuất')

# ---------------- đường dẫn hub công khai trong matrix khớp taxonomy
for r in rows:
    p, c = parents[r['parent_id']], children[r['child_id']]
    if r['status'] == 'PLANNED':
        want = '/%s/%s/%s/' % (p['slug'], c['slug'], r['slug'])
        if r['output_path'] != want: err('output_path sai tại %s' % r['id']); break
        if r['canonical_url'] != 'https://thuexemayhanoi.github.io/blog' + want:
            err('canonical_url sai tại %s' % r['id']); break

print('=== VALIDATE FOUNDATION ===')
print('Hàng: %d | Trạng thái: %s' % (len(rows), dict(mstat)))
for w_ in WARN: print('WARN:', w_)
for e in ERRORS: print('FAIL:', e)
print('KẾT QUẢ:', 'FAIL' if ERRORS else 'PASS (%d cảnh báo)' % len(WARN))
sys.exit(1 if ERRORS else 0)
