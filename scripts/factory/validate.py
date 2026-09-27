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
  7. data/content-matrix.csv (schema TẠO MỚI): ID/URL/canonical duy nhất,
     legacy 483 hàng khớp inventory, 10 REVIEW không bị đổi, PLANNED đủ dữ liệu.
"""
import csv, json, os, re, sys, collections

ERRORS, WARNS, BLOCKED = [], [], []
def err(m): ERRORS.append(m)
def warn(m): WARNS.append(m)
def blocked(m): BLOCKED.append(m)

# ---------------- 1. tệp bắt buộc
REQUIRED = [
    'data/content-taxonomy.json',
    'data/content-inventory.csv',
    'data/content-matrix.csv',
    'data/state/checkpoint.json',
    'data/state/writer-lock.json',
    'data/state/transaction.json',
    'data/state/taxonomy-config.json',
    'data/state/existing-map.json',
    'data/state/matrix-seed.json',
    'data/business-facts.json',
    'reports/factory/progress.json',
    'reports/factory/latest.md',
    'reports/factory/content-hierarchy.md',
    'reports/factory/inventory-summary.md',
    'reports/factory/matrix-report.md',
    'reports/factory/matrix-recovery-blocked.md',
    'reports/factory/policy-conflicts.md',
    'docs/mistral/README.md', 'docs/CONTENT-FACTORY.md', 'docs/ARTICLE-RULES.md',
    'docs/TAXONOMY.md', 'docs/SEO-OWNERSHIP.md', 'docs/RECOVERY.md',
    'scripts/factory/validate.py', 'scripts/factory/manifest.py',
    'scripts/factory/restore-foundation.py', 'scripts/factory/generate-reports.py',
    'scripts/factory/generate-matrix.py', 'scripts/factory/publish-gate.py',
    '_data/factory-taxonomy.yml', '_data/factory-map.yml',
]
for p in REQUIRED:
    if not os.path.exists(p):
        err('THIẾU TỆP NỀN TẢNG: %s (chạy: python3 scripts/factory/restore-foundation.py và generate-matrix.py)' % p)

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
# URL legacy: đúng dạng Jekyll sinh. Quy tắc (phải khớp restore-foundation.py):
# /blog/{danh mục slug, chữ thường}/{Y}/{M}/{D}/{slug}/ với Y/M/D là ngày frontmatter
# sau khi Jekyll chuẩn hoá về UTC.
import datetime as _dt
date_re = re.compile(r'^date:\s*(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?\s*([+-]\d{2})(\d{2})?', re.MULTILINE)
def legacy_url(path, category, slug):
    dm = date_re.search(open(path, encoding='utf-8').read()[:2000])
    if not dm: return None
    off_h, off_m = int(dm.group(7)), int(dm.group(8) or 0)
    sign = 1 if dm.group(7).startswith('+') else -1
    fdt = _dt.datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)),
                       int(dm.group(4)), int(dm.group(5)), int(dm.group(6) or 0)) - sign * _dt.timedelta(hours=abs(off_h), minutes=off_m)
    return '/blog/%s/%04d/%02d/%02d/%s/' % (category.lower(), fdt.year, fdt.month, fdt.day, slug)
for r in inv:
    want = legacy_url(r['source_path'], r['category'], r['slug'])
    if want is None:
        err('không đọc được date frontmatter tại %s' % r['slug']); break
    if r['current_url'] != want:
        err('URL legacy sai tại %s: %s (mong đợi %s)' % (r['slug'], r['current_url'], want))
        break

# Đối chiếu một lần với sitemap công khai (nếu có mạng)
import urllib.request, urllib.parse as up
try:
    sm = urllib.request.urlopen('https://thuexemayhanoi.github.io/blog/sitemap.xml', timeout=30).read().decode('utf-8')
    live = set(re.findall(r'<loc>([^<]+)</loc>', sm))
    inv_urls = set('https://thuexemayhanoi.github.io' + up.quote(r['current_url'], safe='/:') for r in inv)
    miss = [u for u in inv_urls if u not in live]
    if miss:
        err('%d/%d URL legacy không khớp sitemap công khai (ví dụ: %s)' % (len(miss), len(inv_urls), sorted(miss)[0]))
    allowed_new = set()
    if os.path.exists('data/content-matrix.csv'):
        with open('data/content-matrix.csv', encoding='utf-8', newline='') as f:
            for mr in csv.DictReader(f):
                if mr['status'] == 'PUBLISHED' and mr['source'].startswith('planned:') and '{date}' not in mr['expected_url']:
                    allowed_new.add('https://thuexemayhanoi.github.io' + up.quote(mr['expected_url'], safe='/:'))
    extra = [u for u in live if '/2026/' in u and u not in inv_urls and u not in allowed_new]
    if extra:
        err('sitemap có %d URL bài không nằm trong inventory (ví dụ: %s)' % (len(extra), sorted(extra)[0]))
except Exception as e:
    warn('không kiểm tra được sitemap live (%s) — chỉ kiểm tra URL cục bộ' % e)

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

# ---------------- 7. matrix (schema TẠO MỚI - generate-matrix.py)
MATRIX = 'data/content-matrix.csv'
mstat = None
if os.path.exists(MATRIX):
    with open(MATRIX, encoding='utf-8', newline='') as f:
        mrows = list(csv.DictReader(f))
    mstat = collections.Counter(r['status'] for r in mrows)
    stat_valid = {'PLANNED','WRITING','QA','PASS','PUBLISHED','REVIEW','REPAIR','BLOCKED','FAIL','EXISTING'}
    ids = [r['id'] for r in mrows]
    if len(set(ids)) != len(ids): err('matrix id trùng')
    for key in ('output_path','canonical_url'):
        vals = [r[key] for r in mrows]
        if len(set(vals)) != len(vals): err('matrix %s trùng' % key)
    legacy = [r for r in mrows if r['source'].startswith('legacy:')]
    if len(legacy) != len(inv): err('matrix legacy rows != inventory: %d/%d' % (len(legacy), len(inv)))
    inv_by_slug = {r['slug']: r for r in inv}
    for r in legacy:
        iv = inv_by_slug.get(os.path.basename(r['output_path'])[11:-3])
        if not iv: err('matrix legacy không khớp inventory: %s' % r['id']); break
        if r['expected_url'] != iv['current_url'] or r['canonical_url'] != iv['current_url']:
            err('matrix legacy URL đổi so với inventory: %s' % r['id']); break
        if r['status'] not in ('EXISTING','REVIEW'):
            err('matrix legacy status phải EXISTING/REVIEW: %s=%s' % (r['id'], r['status'])); break
    rv = [r for r in legacy if r['status']=='REVIEW']
    if len(rv) != 10: err('matrix REVIEW legacy phải đúng 10 hàng (không tự PASS), có %d' % len(rv))
    for r in mrows:
        if r['status'] not in stat_valid: err('matrix status không hợp lệ: %s' % r['status'])
        if r['parent_id'] not in parents or r['child_id'] not in children:
            err('matrix parent/child không hợp lệ tại %s' % r['id'])
        if r['status'] == 'PLANNED':
            if not r['intent'].strip() or not r['primary_keyword'].strip() or not r['internal_links'].strip():
                err('PLANNED %s thiếu intent/từ khóa/liên kết nội bộ' % r['id'])
            ch = children[r['child_id']]
            if r['source_required'] != str(ch['source_required']).lower():
                err('PLANNED %s source_required lệch taxonomy' % r['id'])
            if r['legal_risk'] != ch['legal_risk']:
                err('PLANNED %s legal_risk lệch taxonomy' % r['id'])
    if cp['counts'].get('existing') != mstat.get('EXISTING', 0): err('checkpoint existing lệch matrix')
    if cp['counts'].get('review') != mstat.get('REVIEW', 0): err('checkpoint review lệch matrix')
    if cp['counts'].get('planned') != mstat.get('PLANNED', 0): err('checkpoint planned lệch matrix')
else:
    blocked('data/content-matrix.csv THIẾT — không thể khôi phục bản gốc. Bằng chứng: reports/factory/matrix-recovery-blocked.md. Đây là BLOCKED có chủ đích, không phải PASS.')

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
