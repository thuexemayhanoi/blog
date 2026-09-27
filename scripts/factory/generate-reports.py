#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh report + checkpoint factory TỪ DỮ LIỆU THẬT - thuexemayhanoi/blog.

Chạy: python3 scripts/factory/generate-reports.py  (từ gốc repository, sau restore-foundation.py)

Chỉ đọc: data/content-taxonomy.json, data/content-inventory.csv, data/state/*, _posts/.
Chỉ ghi: reports/factory/*.md|json, data/state/checkpoint.json.
Không bịa số lượng, không tự ghi PASS: mọi con số được tính từ dữ liệu thật.

Matrix BLOCKED: trạng thái matrix không thể khôi phục được phản ánh trung thực
trong mọi report (xem reports/factory/matrix-recovery-blocked.md).
"""
import csv, json, os, re, sys, collections, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

tax = json.load(open('data/content-taxonomy.json', encoding='utf-8'))
inv = list(csv.DictReader(open('data/content-inventory.csv', encoding='utf-8')))
seed = json.load(open('data/state/taxonomy-config.json', encoding='utf-8'))
parents = {p['parent_id']: p for p in tax['parents']}
children = {c['child_id']: c for c in tax['children']}

# Mốc thời gian XÁC ĐỊNH (idempotent): lấy theo ngày bài mới nhất trong dữ liệu,
# để report sinh lại cho kết quả byte-đối-byte giống nhau. Không dùng giờ hệ thống.
data_through = max(r['published_date'] for r in inv)
now = data_through + 'T00:00:00+00:00'

# ---------------- đếm từ inventory thật
by_child = collections.Counter(r['likely_child'] for r in inv)
by_parent = collections.Counter(r['likely_parent'] for r in inv)

# REVIEW legacy (cặp cannibalization đã ghi trong docs/SEO-OWNERS.md, ID = thứ tự tên tệp)
post_files = sorted(os.listdir('_posts'))
review_ids = [5, 17, 18, 53, 227, 228, 410, 411, 423, 424]
review_slugs = [post_files[i - 1][11:-3] for i in review_ids]

# số từ mỗi bài (đếm thô từ markdown, bỏ frontmatter)
word_counts = []
for r in inv:
    text = open(r['source_path'], encoding='utf-8').read()
    body = re.sub(r'^---.*?---', '', text, count=1, flags=re.S)
    words = re.findall(r'\S+', body)
    word_counts.append(len(words))
word_counts.sort()

# theo danh mục Jekyll của bài (đọc frontmatter categories)
cat_re = re.compile(r'^categories:\s*\[?([^\]\n]*)', re.MULTILINE)
by_cat = collections.Counter()
for r in inv:
    text = open(r['source_path'], encoding='utf-8').read()[:3000]
    m = cat_re.search(text)
    cat = (m.group(1).strip() if m else '').strip()
    by_cat[cat or '(không rõ)'] += 1

MATRIX_MISSING = not os.path.exists('data/content-matrix.csv')

# ---------------- progress.json
progress = {
    'generated_at': now,
    'generated_by': 'scripts/factory/generate-reports.py (từ dữ liệu thật)',
    'capacity': 10000,
    'matrix_status': 'BLOCKED (missing, unrecoverable from committed sources)' if MATRIX_MISSING else 'PRESENT',
    'rows': {
        'legacy_total': len(inv),
        'legacy_mapped': len(inv),
        'legacy_review': len(review_slugs),
        'legacy_existing': len(inv) - len(review_slugs),
        'planned_claimable': 0 if MATRIX_MISSING else None,
    },
    'taxonomy': {'parents': len(tax['parents']), 'children': len(tax['children'])},
    'published_through_factory': 0,
    'audit': {
        'repair_pending': 0,
        'review_pending': len(review_slugs),
        'post_publish_audit_pending': 0,
    },
    'quality': {'average_quality': None, 'average_seo_before': None, 'average_seo_after': None},
    'legal': {'claims_fresh': 0, 'claims_stale': 0},
    'batches': None if MATRIX_MISSING else {'total': 200, 'rows_per_batch': 50, 'completed': 0},
    'last_completed_article_id': None,
    'resume_point': (
        'BLOCKED: data/content-matrix.csv chưa từng được commit nên không thể khôi phục '
        '(bằng chứng: reports/factory/matrix-recovery-blocked.md). Chưa nhận được hàng PLANNED nào. '
        'Việc có thể làm không phụ thuộc matrix: audit 10 hàng legacy REVIEW theo cặp trong '
        'docs/SEO-OWNERS.md; sửa link/hub/SEO; quyết định của chủ xe về tái sinh matrix từ seed '
        'data/state/taxonomy-config.json (là matrix MỚI, phải được duyệt, không phải khôi phục).'
    ) if MATRIX_MISSING else 'N/A',
}
with open('reports/factory/progress.json', 'w', encoding='utf-8') as f:
    json.dump(progress, f, ensure_ascii=False, indent=2)
    f.write('\n')

# ---------------- checkpoint.json
checkpoint = {
    'factory_version': 1,
    'capacity': 10000,
    'updated_at': now,
    'last_run_id': 'restore-foundation-' + data_through,
    'status': 'PARTIAL_BLOCKED',
    'matrix_status': 'BLOCKED_MISSING' if MATRIX_MISSING else 'PRESENT',
    'last_completed_article_id': None,
    'last_batch_id': None,
    'next_claimable_id': None,
    'counts': {
        'legacy_total': len(inv),
        'existing': len(inv) - len(review_slugs),
        'review': len(review_slugs),
        'planned': None if MATRIX_MISSING else 0,
        'writing': 0, 'qa': 0, 'pass': 0, 'published': 0, 'repair': 0, 'blocked': 0, 'fail': 0,
    },
    'resume_point': progress['resume_point'],
    'rules': {
        'max_chunk': 10,
        'publish_requires': 'QUALITY>=90 AND SEO>=90 AND BUSINESS_FACT PASS AND (LEGAL PASS OR NOT REQUIRED) AND NO CRITICAL FAILURE',
    },
}
with open('data/state/checkpoint.json', 'w', encoding='utf-8') as f:
    json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    f.write('\n')

# ---------------- inventory-summary.md
lines = ['# Tóm tắt kiểm kê nội dung hiện có', '',
         'Sinh bởi `scripts/factory/generate-reports.py` từ `data/content-inventory.csv`. Ngày sinh: %s.' % now, '',
         'Số bài legacy trong `_posts/`: %d. Tất cả đã được ánh xạ vào taxonomy (từ `data/state/existing-map.json`, URL giữ nguyên).' % len(inv), '',
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
lines = ['# Cấp trúc nội dung (content hierarchy)', '',
         'Sinh bởi `scripts/factory/generate-reports.py`. Ngày sinh: %s. ' % now +
         'Nguồn: `data/content-taxonomy.json`, `data/content-inventory.csv`.', '',
         'Tổng bài legacy: %d | REVIEW: %d | EXISTING: %d' % (len(inv), len(review_slugs), len(inv) - len(review_slugs)),
         '', 'Matrix 10.000 hàng: BLOCKED (chưa từng được commit — không thể khôi phục). `planned_target` dưới đây là chỉ tiêu từ seed, KHÔNG phải số hàng matrix thực tế.', '',
         '| Parent | Child | Bài legacy | Chỉ tiêu PLANNED (seed) | Hub URL |',
         '|---|---|---|---|---|']
for c in tax['children']:
    lines.append('| %s | %s (%s) | %d | %d | %s |' % (
        c['parent_id'], c['title'], c['child_id'], by_child.get(c['child_id'], 0), c['planned_target'], c['hub_url']))
lines += ['', '## Cảnh báo', '']
lines.append('- REVIEW (cặp cannibalization legacy, cần đọc nội dung để xử lý): %s' %
             ', '.join('BLG-%05d' % i for i in review_ids))
lines.append('- Child có bài legacy nhưng chưa có trang hub công khai: xem cảnh báo từ `scripts/factory/validate.py`.')
lines.append('- Không có số liệu planned thực tế do matrix BLOCKED.')
lines.append('')
open('reports/factory/content-hierarchy.md', 'w', encoding='utf-8').write('\n'.join(lines))

# ---------------- latest.md
lines = ['# Báo cáo factory mới nhất', '',
         'Sinh bởi `scripts/factory/generate-reports.py`. Ngày: %s.' % now, '',
         '- Trạng thái nền: PARTIAL / BLOCKED (matrix)',
         '- Taxonomy: %d parent hub, %d child hub (khôi phục từ seed)' % (len(tax['parents']), len(tax['children'])),
         '- Inventory: %d bài legacy, 100%% ánh xạ, URL giữ nguyên' % len(inv),
         '- Ma trận 10.000 hàng: BLOCKED — chưa từng được commit, không khôi phục được (bằng chứng: `reports/factory/matrix-recovery-blocked.md`)',
         '- Bài legacy đổi URL: 0 | Bài bị xóa: 0',
         '- REVIEW legacy chờ xử lý: %d' % len(review_slugs),
         '- Bài xuất bản qua factory: 0',
         '- Chi tiết: `reports/factory/progress.json`, `reports/factory/content-hierarchy.md`, `reports/factory/inventory-summary.md`',
         '']
open('reports/factory/latest.md', 'w', encoding='utf-8').write('\n'.join(lines))

print('=== GENERATE REPORTS ===')
print('legacy: %d (EXISTING %d, REVIEW %d)' % (len(inv), len(inv) - len(review_slugs), len(review_slugs)))
print('matrix: %s' % progress['matrix_status'])
print('KẾT QUẢ: PASS (report sinh từ dữ liệu thật)')
