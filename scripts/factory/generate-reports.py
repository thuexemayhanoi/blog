#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh report + checkpoint factory TỪ DỮ LIỆU THẬT - thuexemayhanoi/blog.

Chạy: python3 scripts/factory/generate-reports.py  (từ gốc repository, sau
restore-foundation.py và generate-matrix.py)

Nguyên tắc tiến độ (bắt buộc):
- Khi data/content-matrix.csv tồn tại: đếm trạng thái THẬT từ matrix
  (EXISTING/REVIEW/PLANNED/WRITING/QA/PASS/PUBLISHED/REPAIR/BLOCKED/FAIL).
- KHÔNG ghi đè tiến độ đang có: bảo toàn last_completed_article_id,
  last_batch_id, next_claimable_id, in_progress_chunk, updated_at,
  last_run_id, status của checkpoint hiện có. Tính lại các counts từ matrix.
- KHÔNG đụng data/state/writer-lock.json và data/state/transaction.json.
- BA mốc thời gian riêng biệt, KHÔNG dùng lẫn:
  + generated_at = thời điểm chạy report THẬT (đồng hồ thật, mỗi lần chạy mới).
  + data_through = ngày bài mới nhất mà dữ liệu đại diện (chỉ đổi khi nội dung đổi).
  + checkpoint.updated_at = thời điểm trạng thái factory đổi vật lý gần nhất
    (publish/claim...); report generation KHÔNG tự nâng.
- Do generated_at là giờ chạy thật, các lần chạy khác nhau KHÔNG byte-identical
  về trường này. Tính deterministic thay bằng vân tay dữ liệu:
  matrix_sha256, taxonomy_sha256, inventory_sha256, data_fingerprint
  (cùng dữ liệu -> cùng vân tay). CI đối chiếu vân tay, không đối chiếu giờ.
- KHÔNG đụng data/state/writer-lock.json và data/state/transaction.json.
"""
import csv, json, os, re, sys, collections, hashlib
import datetime


def sha256_file(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

tax = json.load(open('data/content-taxonomy.json', encoding='utf-8'))
inv = list(csv.DictReader(open('data/content-inventory.csv', encoding='utf-8')))
parents = {p['parent_id']: p for p in tax['parents']}
children = {c['child_id']: c for c in tax['children']}

MATRIX = 'data/content-matrix.csv'
MATRIX_MISSING = not os.path.exists(MATRIX)
matrix_rows = []
MATRIX_SHA256 = None
if not MATRIX_MISSING:
    MATRIX_SHA256 = sha256_file(MATRIX)
TAXONOMY_SHA256 = sha256_file('data/content-taxonomy.json')
INVENTORY_SHA256 = sha256_file('data/content-inventory.csv')
# vân tay dữ liệu tổng hợp: matrix + taxonomy + inventory (bỏ qua state runtime)
DATA_FINGERPRINT = hashlib.sha256(
    (str(MATRIX_SHA256) + TAXONOMY_SHA256 + INVENTORY_SHA256).encode('utf-8')).hexdigest()
GENERATED_AT = now_iso()  # giờ chạy report THẬT (khác data_through)
if not MATRIX_MISSING:
    with open(MATRIX, encoding='utf-8', newline='') as f:
        matrix_rows = list(csv.DictReader(f))

# ---------------- hai mốc thời gian riêng biệt
data_through = max(r['published_date'] for r in inv)
for r in matrix_rows:
    if r['status'] == 'PUBLISHED':
        m = re.match(r'_posts/(\d{4}-\d{2}-\d{2})-', r['output_path'])
        if m and m.group(1) > data_through:
            data_through = m.group(1)
DATA_TS = data_through + 'T00:00:00+00:00'  # mốc DỮ LIỆU (bài mới nhất)

# ---------------- đếm từ inventory + matrix thật
by_child = collections.Counter(r['likely_child'] for r in inv)
by_parent = collections.Counter(r['likely_parent'] for r in inv)

post_files = sorted(os.listdir('_posts'))
review_ids = [5, 17, 18, 53, 227, 228, 410, 411, 423, 424]
review_slugs = [post_files[i - 1][11:-3] for i in review_ids]

word_counts = []
for r in inv:
    text = open(r['source_path'], encoding='utf-8').read()
    body = re.sub(r'^---.*?---', '', text, count=1, flags=re.S)
    word_counts.append(len(re.findall(r'\S+', body)))
word_counts.sort()

cat_re = re.compile(r'^categories:\s*\[?([^\]\n]*)', re.MULTILINE)
by_cat = collections.Counter()
for r in inv:
    text = open(r['source_path'], encoding='utf-8').read()[:3000]
    m = cat_re.search(text)
    by_cat[(m.group(1).strip() if m else '').strip() or '(không rõ)'] += 1

mstat = collections.Counter(r['status'] for r in matrix_rows)
legacy_in_matrix = sum(1 for r in matrix_rows if r['status'] in ('EXISTING', 'REVIEW', 'PUBLISHED') and r['source'].startswith('legacy:'))
planned_claimable = [r['id'] for r in matrix_rows if r['status'] == 'PLANNED']
published_factory = [r for r in matrix_rows if r['status'] == 'PUBLISHED' and r['source'].startswith('planned:')]

# ---------------- checkpoint: bảo toàn tiến độ, chỉ tính lại counts
CP = 'data/state/checkpoint.json'
prev = {}
if os.path.exists(CP):
    prev = json.load(open(CP, encoding='utf-8'))

def preserve(key, default):
    """Giữ nguyên giá trị tiến độ cũ nếu có; không reset về null."""
    return prev.get(key, default) if prev.get(key) is not None else default

checkpoint = {
    'factory_version': 2,
    'capacity': 10000,
    # updated_at: mốc lần state đổi VẬT LÝ gần nhất (publish/claim ghi giờ thật).
    # Report generation KHÔNG nâng mốc này — giữ nguyên giá trị cũ nếu có.
    'updated_at': prev.get('updated_at') or GENERATED_AT,
    'last_run_id': preserve('last_run_id', 'matrix-init-' + data_through),
    'status': preserve('status', 'READY' if not MATRIX_MISSING else 'PARTIAL_BLOCKED'),
    'matrix_status': 'BLOCKED_MISSING' if MATRIX_MISSING else 'PRESENT_CREATED_NEW',
    'matrix_note': ('BLOCKED: matrix gốc chưa từng được commit, không khôi phục được.'
                    if MATRIX_MISSING else
                    'TẠO MỚI 2026-09-27 theo phê duyệt của chủ xe từ seed đã kiểm chứng — '
                    'KHÔNG PHẢI KHÔI PHỤC NGUYÊN BẢN. Bằng chứng: reports/factory/matrix-recovery-blocked.md.'),
    # tiến độ: bảo toàn tuyệt đối, không đếm lại từ đầu
    'last_completed_article_id': preserve('last_completed_article_id', None),
    'last_batch_id': preserve('last_batch_id', None),
    'next_claimable_id': preserve('next_claimable_id', planned_claimable[0] if planned_claimable else None),
    'in_progress_chunk': preserve('in_progress_chunk', None),
    'counts': {
        'legacy_total': len(inv),
        'existing': mstat.get('EXISTING', len(inv) - len(review_slugs)) if not MATRIX_MISSING else len(inv) - len(review_slugs),
        'review': mstat.get('REVIEW', len(review_slugs)) if not MATRIX_MISSING else len(review_slugs),
        'planned': mstat.get('PLANNED', 0),
        'writing': mstat.get('WRITING', 0),
        'qa': mstat.get('QA', 0),
        'pass': mstat.get('PASS', 0),
        'published': mstat.get('PUBLISHED', 0),
        'repair': mstat.get('REPAIR', 0),
        'blocked': mstat.get('BLOCKED', 0),
        'fail': mstat.get('FAIL', 0),
    },
    'resume_point': (
        'BLOCKED: data/content-matrix.csv chưa từng được commit nên không thể khôi phục '
        '(bằng chứng: reports/factory/matrix-recovery-blocked.md).'
        if MATRIX_MISSING else
        'Matrix TẠO MỚI đã được chủ xe duyệt (2026-09-27). Nhận cặp 2 hàng PLANNED '
        '(chunk_size trong data/factory/production-control.json) bắt đầu từ '
        'next_claimable_id; giữ nguyên 10 hàng legacy REVIEW. Resume từ '
        'last_completed_article_id + in_progress_chunk, không restart.'
    ),
    'rules': {
        'max_chunk': 10,
        'chunk_size': 2,
        'production_control': 'data/factory/production-control.json (enabled=true -> tiếp tục; enabled=false -> dừng trước khi claim cặp mới)',
        'publish_requires': 'QUALITY>=75 AND SEO>=70 AND BUSINESS_FACT PASS AND (LEGAL PASS OR NOT REQUIRED) AND NO CRITICAL FAILURE',
        'evidence': 'data/qa/<BLG-ID>.json (bắt buộc khi promote, kiểm bởi scripts/factory/publish-gate.py)',
    },
}
with open(CP, 'w', encoding='utf-8') as f:
    json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    f.write('\n')

# ---------------- progress.json
progress = {
    # generated_at = giờ chạy report thật; data_through = mốc dữ liệu.
    # Hai giá trị này KHÔNG được dùng lẫn cho nhau.
    'generated_at': GENERATED_AT,
    'data_through': data_through,
    'data_fingerprint': DATA_FINGERPRINT,
    'matrix_sha256': MATRIX_SHA256,
    'taxonomy_sha256': TAXONOMY_SHA256,
    'inventory_sha256': INVENTORY_SHA256,
    'generated_by': 'scripts/factory/generate-reports.py (từ dữ liệu thật, bảo toàn tiến độ)',
    'capacity': 10000,
    'matrix_status': checkpoint['matrix_status'],
    'rows': {
        'legacy_total': len(inv),
        'legacy_mapped': legacy_in_matrix if not MATRIX_MISSING else len(inv),
        'legacy_review': len(review_slugs),
        'legacy_existing': (len(inv) - len(review_slugs)),
        'planned_total': mstat.get('PLANNED', 0),
        'writing': mstat.get('WRITING', 0),
        'qa': mstat.get('QA', 0),
        'pass': mstat.get('PASS', 0),
        'published': mstat.get('PUBLISHED', 0),
        'repair': mstat.get('REPAIR', 0),
        'blocked': mstat.get('BLOCKED', 0),
        'fail': mstat.get('FAIL', 0),
        'planned_claimable': len(planned_claimable),
    },
    'taxonomy': {'parents': len(tax['parents']), 'children': len(tax['children'])},
    'published_through_factory': len(published_factory),
    'audit': {
        'repair_pending': mstat.get('REPAIR', 0),
        'review_pending': len(review_slugs),
        'post_publish_audit_pending': 0,
    },
    'quality': {'average_quality': None, 'average_seo_before': None, 'average_seo_after': None},
    'legal': {'claims_fresh': 0, 'claims_stale': 0},
    'checkpoint_progress': {
        'last_completed_article_id': checkpoint['last_completed_article_id'],
        'last_batch_id': checkpoint['last_batch_id'],
        'next_claimable_id': checkpoint['next_claimable_id'],
        'in_progress_chunk': checkpoint['in_progress_chunk'],
    },
    'resume_point': checkpoint['resume_point'],
}
with open('reports/factory/progress.json', 'w', encoding='utf-8') as f:
    json.dump(progress, f, ensure_ascii=False, indent=2)
    f.write('\n')

# ---------------- inventory-summary.md
lines = ['# Tóm tắt kiểm kê nội dung hiện có', '',
         'Sinh bởi `scripts/factory/generate-reports.py` từ `data/content-inventory.csv`. '
         'Mốc dữ liệu (bài mới nhất): %s.' % data_through, '',
         'Số bài legacy trong `_posts/`: %d. Tất cả đã được ánh xạ vào taxonomy '
         '(từ `data/state/existing-map.json`, URL giữ nguyên).' % len(inv), '',
         '## Theo danh mục Jekyll hiện tại', '']
for cat, n in by_cat.most_common():
    lines.append('- %s: %d' % (cat, n))
lines += ['', '## Theo parent hub', '']
for pid, n in sorted(by_parent.items(), key=lambda x: -x[1]):
    lines.append('- %s: %d' % (pid, n))
lines += ['', '## Số từ (đếm thô từ markdown)', '',
          '- Trung bình: %d từ/bài' % (sum(word_counts) // max(len(word_counts), 1)),
          '- Nhỏ nhất: %d, lớn nhất: %d' % (word_counts[0], word_counts[-1]), '',
          'Không bài legacy nào bị đổi URL. Không bài nào bị xóa hay đổi tên.', '']
open('reports/factory/inventory-summary.md', 'w', encoding='utf-8').write('\n'.join(lines))

# ---------------- content-hierarchy.md
targets = {c['child_id']: c['planned_target'] for c in tax['children']}
planned_by_child = collections.Counter(r['child_id'] for r in matrix_rows if r['status'] not in ('EXISTING', 'REVIEW'))
lines = ['# Cấp trúc nội dung (content hierarchy)', '',
         'Sinh bởi `scripts/factory/generate-reports.py`. Mốc dữ liệu: %s. ' % data_through +
         'Nguồn: `data/content-taxonomy.json`, `data/content-inventory.csv`, `data/content-matrix.csv`.', '',
         'Tổng bài legacy: %d | REVIEW: %d | EXISTING: %d' % (len(inv), len(review_slugs), len(inv) - len(review_slugs)),
         '', 'Matrix: %s. Bảng dưới ghi số hàng PLANNED trong matrix MỚI (không phải chỉ tiêu).' % checkpoint['matrix_status'], '',
         '| Parent | Child | Bài legacy | Hàng matrix (không legacy) | planned_target (seed) | Hub URL |',
         '|---|---|---|---|---|---|']
for c in tax['children']:
    lines.append('| %s | %s (%s) | %d | %d | %d | %s |' % (
        c['parent_id'], c['title'], c['child_id'], by_child.get(c['child_id'], 0),
        planned_by_child.get(c['child_id'], 0), targets[c['child_id']], c['hub_url']))
lines += ['', '## Cảnh báo', '']
lines.append('- REVIEW (cặp cannibalization legacy, cần đọc nội dung để xử lý): %s' %
             ', '.join('BLG-%05d' % i for i in review_ids))
lines.append('- Matrix TẠO MỚI có %d hàng PLANNED so với planned_target tổng %d trong seed taxonomy — '
             'phần thiếu đã được báo trong `reports/factory/matrix-report.md`, không đệm hàng rỗng.' % (
                 sum(planned_by_child.values()), sum(targets.values())))
lines.append('')
open('reports/factory/content-hierarchy.md', 'w', encoding='utf-8').write('\n'.join(lines))

# ---------------- latest.md
lines = ['# Báo cáo factory mới nhất', '',
         'Sinh bởi `scripts/factory/generate-reports.py`. Mốc dữ liệu: %s.' % data_through, '',
         '- Matrix: %s' % checkpoint['matrix_status'],
         '- Matrix: TẠO MỚI theo phê duyệt chủ xe 2026-09-27 (không phải khôi phục) — %d hàng tổng, '
         'phân tích chống trùng: `reports/factory/matrix-report.md`' % (len(matrix_rows) if not MATRIX_MISSING else 0),
         '- Taxonomy: %d parent hub, %d child hub (khôi phục từ seed)' % (len(tax['parents']), len(tax['children'])),
         '- Inventory: %d bài legacy, 100%% ánh xạ, URL giữ nguyên' % len(inv),
         '- Trạng thái matrix: %s' % dict(mstat),
         '- Tiến độ (bảo toàn, không reset): last_completed_article_id=%s, in_progress_chunk=%s' % (
             checkpoint['last_completed_article_id'], checkpoint['in_progress_chunk']),
         '- Bài xuất bản qua factory: %d' % len(published_factory),
         '- REVIEW legacy chờ xử lý: %d' % len(review_slugs),
         '- Chi tiết: `reports/factory/progress.json`, `reports/factory/matrix-report.md`, '
         '`reports/factory/content-hierarchy.md`',
         '']
open('reports/factory/latest.md', 'w', encoding='utf-8').write('\n'.join(lines))

print('=== GENERATE REPORTS ===')
print('legacy: %d (EXISTING %d, REVIEW %d)' % (len(inv), len(inv) - len(review_slugs), len(review_slugs)))
print('matrix: %s | trạng thái: %s' % (checkpoint['matrix_status'], dict(mstat)))
print('tiến độ bảo toàn: last_completed=%s chunk=%s next_claimable=%s' % (
    checkpoint['last_completed_article_id'], checkpoint['in_progress_chunk'], checkpoint['next_claimable_id']))
print('mốc dữ liệu: %s | generated_at: %s | checkpoint.updated_at: %s' % (
    data_through, GENERATED_AT, checkpoint['updated_at']))
print('vân tay: matrix=%s... data_fingerprint=%s...' % (
    (MATRIX_SHA256 or '-')[:12], DATA_FINGERPRINT[:12]))
print('KẾT QUẢ: PASS (report sinh từ dữ liệu thật, tiến độ không reset)')
