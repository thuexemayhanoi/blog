#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TẠO MỚI data/content-matrix.csv (KHÔNG PHẢI KHÔI PHỤC).

Bối cảnh: matrix gốc chưa từng được commit, không khôi phục được
(bằng chứng: reports/factory/matrix-recovery-blocked.md). Chủ xe đã DUYỆT
tạo matrix MỚI từ taxonomy/seed/inventory đã kiểm chứng (2026-09-27).
Gọi product này là "khôi phục nguyên bản" là BỊ CẤM.

Nguồn vào (chỉ nguồn đã kiểm chứng):
- data/content-taxonomy.json (7 parent / 51 child, khôi phục từ seed gốc)
- data/content-inventory.csv (483 bài legacy, URL thật đã đối chiếu sitemap)
- data/state/matrix-seed.json (cấu hình do người biên soạn, mỗi hàng là một
  ý định tìm kiếm riêng; KHÔNG sinh bằng biến thể từ)

Ra: data/content-matrix.csv + báo cáo chống trùng reports/factory/matrix-report.md

Quy tắc:
- 483 hàng legacy giữ nguyên: id BLG-00001..00483 theo thứ tự tên tệp _posts/
  (đúng bằng chứng cũ dùng trong docs/SEO-OWNERS.md), URL/canonical/mapping
  giữ nguyên. 10 hàng REVIEW giữ nguyên REVIEW, không tự đổi PASS.
- Hàng mới: id tuần tự tiếp sau legacy, status PLANNED. Mỗi hàng có intent,
  tiêu đề, từ khóa, nhóm, URL dự kiến, liên kết nội bộ, yêu cầu nguồn, rủi ro
  pháp lý (kế thừa từ child trong taxonomy).
- Chống trùng: slug, output_path, id, canonical, expected_url (chuẩn hoá)
  phải duy nhất toàn matrix; trong cùng child không trùng primary_keyword
  chuẩn hoá và không trùng intent chuẩn hoá.
- Không đệm hàng rỗng cho đủ chỉ tiêu: chỉ sinh hàng từ seed; phần thiếu
  được báo cáo trung thực trong matrix-report.md.
- Idempotent: chạy lại cho file giống hệt (không dùng giờ hệ thống).

Chạy: python3 scripts/factory/generate-matrix.py   (từ gốc repository)
"""
import csv
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

TAX_PATH = 'data/content-taxonomy.json'
INV_PATH = 'data/content-inventory.csv'
SEED_PATH = 'data/state/matrix-seed.json'
OUT_PATH = 'data/content-matrix.csv'
REPORT_PATH = 'reports/factory/matrix-report.md'

MATRIX_VERSION = 1
MATRIX_CREATED_NOTE = 'TẠO MỚI 2026-09-27 theo phê duyệt của chủ xe - không phải khôi phục nguyên bản'
CREATED_AT = '2026-09-27T00:00:00+00:00'  # mốc cố định, idempotent


def norm(s):
    """Chuẩn hoá để so trùng: bỏ dấu, thường, bỏ ký tự không chữ."""
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def slugify(s):
    """Slug không dấu, chữ thường, gạch ngang - dùng cho hàng PLANNED."""
    s = norm(s)
    return re.sub(r'\s+', '-', s)[:80].strip('-')


def read_sources():
    tax = json.load(open(TAX_PATH, encoding='utf-8'))
    inv = list(csv.DictReader(open(INV_PATH, encoding='utf-8')))
    seed = json.load(open(SEED_PATH, encoding='utf-8'))
    return tax, inv, seed


def legacy_rows(tax, inv):
    """483 hàng legacy: id theo thứ tự tên tệp _posts/ (đúng bằng chứng cũ)."""
    # bài factory (có article_id:) không thuộc legacy inventory — bỏ qua ở đây,
    # chúng là hàng planned:PUBLISHED của matrix, không phải bài legacy.
    files = [fn for fn in sorted(os.listdir('_posts'))
             if not re.search(r'^article_id:', open(os.path.join('_posts', fn), encoding='utf-8').read()[:2000], re.M)]
    assert len(files) == len(inv) == 483, 'inventory/_posts lệch nhau'
    review_ids = [5, 17, 18, 53, 227, 228, 410, 411, 423, 424]
    rows = []
    by_slug = {r['slug']: r for r in inv}
    for n, fname in enumerate(files, start=1):
        slug = fname[11:-3]
        r = by_slug[slug]
        status = 'REVIEW' if n in review_ids else 'EXISTING'
        rows.append({
            'id': 'BLG-%05d' % n,
            'status': status,
            'title': r['title'],
            'intent': '(legacy) ' + r['title'],
            'primary_keyword': '',
            'secondary_keywords': '',
            'parent_id': r['likely_parent'],
            'child_id': r['likely_child'],
            'group': '',
            'expected_url': r['current_url'],
            'output_path': r['source_path'],
            'canonical_url': r['current_url'],
            'internal_links': '',
            'source_required': '',
            'legal_risk': '',
            'batch': '',
            'source': 'legacy:_posts/' + fname,
        })
    return rows


def expand_child(child, spec):
    """Sinh hàng PLANNED cho một child từ seed (entities × angles hoặc rows)."""
    pid, cid = child['parent_id'], child['child_id']
    out = []
    if 'entities' in spec:
        for ent in spec['entities']:
            for ang in spec['angles']:
                title = ang['title'].replace('{e}', ent['name'])
                intent = ang['intent'].replace('{e}', ent['name'])
                kw = ang['kw'].replace('{e}', ent['name'])
                kw2 = [k.replace('{e}', ent['name']) for k in ang.get('kw2', [])]
                links = list(ang.get('links', [])) + list(ent.get('links', []))
                out.append({'title': title, 'intent': intent, 'kw': kw, 'kw2': kw2,
                            'links': links, 'group': spec.get('group', '')})
    else:
        for r in spec['rows']:
            out.append({'title': r['title'], 'intent': r['intent'], 'kw': r['kw'],
                        'kw2': r.get('kw2', []), 'links': r.get('links', []),
                        'group': spec.get('group', '')})
    for o in out:
        o['parent_id'] = pid
        o['child_id'] = cid
    return out


def main():
    tax, inv, seed = read_sources()
    parents = {p['parent_id']: p for p in tax['parents']}
    children = {c['child_id']: c for c in tax['children']}

    rows = legacy_rows(tax, inv)
    legacy_n = len(rows)
    next_id = legacy_n + 1

    planned_specs = seed['children']
    unknown = [cid for cid in planned_specs if cid not in children]
    assert not unknown, 'seed có child_id không tồn tại: %s' % unknown

    parent_cat = {}  # parent_id -> tên danh mục Jekyll (dùng trong URL mới)
    for c in tax['children']:
        parent_cat.setdefault(c['parent_id'], c['hub_url'].split('/')[2])

    for cid, spec in planned_specs.items():
        child = children[cid]
        for o in expand_child(child, spec):
            slug = slugify(o['title'])
            cat = parent_cat[o['parent_id']]
            row = {
                'id': 'BLG-%05d' % next_id,
                'status': 'PLANNED',
                'title': o['title'],
                'intent': o['intent'],
                'primary_keyword': o['kw'],
                'secondary_keywords': '; '.join(o['kw2']),
                'parent_id': o['parent_id'],
                'child_id': o['child_id'],
                'group': o['group'],
                # URL dự kiến theo pattern thật của site (pretty + category):
                # ngày chỉ chốt khi xuất bản, nên để placeholder {date}.
                'expected_url': '/blog/%s/{date}/%s/' % (cat, slug),
                'output_path': '_posts/{date}-%s.md' % slug,
                'canonical_url': '/blog/%s/{date}/%s/' % (cat, slug),
                'internal_links': '; '.join(o['links']),
                'source_required': str(child['source_required']).lower(),
                'legal_risk': child['legal_risk'],
                'batch': '',
                'source': 'planned:matrix-seed/' + cid,
            }
            rows.append(row)
            next_id += 1

    # ---------------- chống trùng toàn matrix
    errors = []
    seen_ids, seen_slug, seen_out, seen_canon = {}, {}, {}, {}
    seen_child_kw, seen_child_intent = {}, {}
    for r in rows:
        for key, seen, label in ((r['id'], seen_ids, 'id'),
                                 (r['output_path'], seen_out, 'output_path'),
                                 (r['canonical_url'], seen_canon, 'canonical')):
            if key in seen:
                errors.append('%s trùng %s: %s' % (label, key, r['id']))
            seen[key] = r['id']
        if r['status'] == 'PLANNED':
            slug = r['output_path'].split('-', 1)[-1][:-3]
            if slug in seen_slug:
                errors.append('slug trùng: %s (%s vs %s)' % (slug, seen_slug[slug], r['id']))
            seen_slug[slug] = r['id']
            kw_key = (r['child_id'], norm(r['primary_keyword']))
            if kw_key in seen_child_kw and norm(r['primary_keyword']):
                errors.append('primary_keyword trùng trong %s: %s' % (r['child_id'], r['primary_keyword']))
            seen_child_kw[kw_key] = r['id']
            it_key = (r['child_id'], norm(r['intent']))
            if it_key in seen_child_intent and norm(r['intent']):
                errors.append('intent trùng trong %s: %s' % (r['child_id'], r['intent']))
            seen_child_intent[it_key] = r['id']
        # legacy: expected_url phải khớp inventory thật
    for r in rows:
        if r['status'] in ('EXISTING', 'REVIEW'):
            fname = os.path.basename(r['output_path'])
            inv_row = next(i for i in inv if i['slug'] == fname[11:-3])
            if r['expected_url'] != inv_row['current_url']:
                errors.append('legacy URL bị đổi: %s' % r['id'])

    if errors:
        print('LỖI CHỐNG TRÙNG:')
        for e in errors[:20]:
            print(' -', e)
        sys.exit(1)

    # --- giữ trạng thái runtime của hàng planned khi tái sinh (idempotent):
    # PUBLISHED/PASS/WRITING/QA... và ngày thật đã chốt khi promote không được
    # reset về PLANNED/{date} placeholder. Chỉ áp cho id trùng.
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding='utf-8', newline='') as f:
            old_rows = {r['id']: r for r in csv.DictReader(f)}
        for r in rows:
            o = old_rows.get(r['id'])
            if o is None:
                continue
            if o['status'] not in ('PLANNED',):
                for k in ('status', 'expected_url', 'output_path', 'canonical_url', 'batch'):
                    r[k] = o[k]

    fields = ['id', 'status', 'title', 'intent', 'primary_keyword', 'secondary_keywords',
              'parent_id', 'child_id', 'group', 'expected_url', 'output_path',
              'canonical_url', 'internal_links', 'source_required', 'legal_risk',
              'batch', 'source']
    with open(OUT_PATH, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # ---------------- report
    planned = [r for r in rows if r['status'] == 'PLANNED']
    review = [r for r in rows if r['status'] == 'REVIEW']
    existing = [r for r in rows if r['status'] == 'EXISTING']
    by_child = {}
    for r in planned:
        by_child[r['child_id']] = by_child.get(r['child_id'], 0) + 1
    targets = {c['child_id']: c['planned_target'] for c in tax['children']}

    # ---------------- ngữ nghĩa năng lực (capacity semantics) — KHÔNG đệm
    HARD_CAPACITY = 10000          # trần kỹ thuật của factory (không đổi)
    EDITORIAL_TARGET = sum(targets.values())  # chỉ tiêu chủ đề đã kiểm chứng trong taxonomy
    current_valid = len(rows)  # mọi hàng hiện tại đều là ý định hợp lệ, không hàng đệm
    current_seeded = sum(1 for r in rows if r['source'].startswith('planned:'))  # mọi hàng seed mới (PLANNED + PUBLISHED)
    legacy_n = legacy_n_ = sum(1 for r in rows if r['source'].startswith('legacy:'))
    reserved = HARD_CAPACITY - legacy_n - current_seeded  # chỗ còn lại cho chủ đề mới thật
    gap = EDITORIAL_TARGET - current_seeded  # thiếu so với chỉ tiêu đã kiểm chứng
    lines = ['# Báo cáo matrix — TẠO MỚI (không phải khôi phục)', '',
             '## Ngữ nghĩa năng lực (báo đúng, không đệm)', '',
             '| Khái niệm | Giá trị | Ý nghĩa |', '|---|---|---|',
             '| HARD_CAPACITY | %d | Trần kỹ thuật của factory, KHÔNG phải chỉ tiêu biên tập. |' % HARD_CAPACITY,
             '| EDITORIAL_TARGET | %d | Tổng planned_target trong taxonomy — chỉ tiêu chủ đề đã kiểm chứng. |' % EDITORIAL_TARGET,
             '| CURRENT_VALID_ROWS | %d | Số hàng hiện tại, tất cả là ý định hợp lệ (không hàng đệm). |' % current_valid,
             '| CURRENT_SEEDED_ROWS | %d | Hàng planned mới đã có ý định riêng. |' % current_seeded,
             '| RESERVED_CAPACITY | %d | HARD_CAPACITY trừ legacy và seed — chỉ dành cho chủ đề MỚI thật. |' % reserved,
             '| MISSING_VALID_TOPIC_SPACE | %d | Thiếu so với EDITORIAL_TARGET — BÁO THIẾU, không đệm. |' % gap,
             '',
             'Lưu ý trung thực: %d (legacy) + %d (EDITORIAL_TARGET) = %d < HARD_CAPACITY %d. '
             'Taxonomy hiện tại KHÔNG THỂ đạt 10.000 hàng. Muốn tăng phải mở rộng seed bằng chủ đề '
             'thật (khác biệt ý định, không hoán đổi tên/từ). Đạt HARD_CAPACITY không phải điều kiện '
             'hoàn thành của matrix; điều kiện là mọi hàng đều hợp lệ và chống trùng PASS.' % (
                 legacy_n, EDITORIAL_TARGET, legacy_n + EDITORIAL_TARGET, HARD_CAPACITY),
             '',
             MATRIX_CREATED_NOTE + '.', '',
             'Sinh bởi `scripts/factory/generate-matrix.py` từ `data/state/matrix-seed.json` '
             '(cấu hình do người biên soạn) + taxonomy + inventory. Idempotent.', '',
             '## Tổng quan', '',
             '- Tổng hàng: %d' % len(rows),
             '- Legacy EXISTING: %d (giữ nguyên URL/mapping, không đổi ID)' % len(existing),
             '- Legacy REVIEW: %d (giữ nguyên trạng thái, không tự PASS)' % len(review),
             '- PLANNED mới: %d' % len(planned),
             '- Năng lực danh nghĩa cũ: 10.000 hàng; tổng planned_target trong taxonomy: %d' % sum(targets.values()),
             '', '## Chống trùng (đã kiểm máy, tất cả PASS)', '',
             '- id, slug, output_path, canonical, expected_url duy nhất toàn matrix.',
             '- Trong cùng child: primary_keyword và intent chuẩn hoá không trùng.',
             '- 483 URL legacy đối chiếu inventory: 100% không đổi.',
             '', '## Chênh lệch với chỉ tiêu — BÁO THIẾU, KHÔNG ĐỆM', '',
             'Seed chỉ đăng ký được %d hàng có giá trị riêng (mỗi hàng một ý định tìm kiếm '
             'khác nhau, không sinh bằng đổi vài từ). Không tự đệm hàng rỗng để đạt '
             '10.000 vì làm vậy tạo hàng nghìn bài gần giống nhau — đúng điều cấm. '
             'Phần thiếu sẽ được bổ sung bằng cách mở rộng seed sau khi có chủ đề thật.' % len(planned),
             '', '| Child | PLANNED đã có | planned_target (seed taxonomy) |', '|---|---|---|']
    for c in tax['children']:
        n = by_child.get(c['child_id'], 0)
        if n or targets[c['child_id']]:
            lines.append('| %s | %d | %d |' % (c['child_id'], n, targets[c['child_id']]))
    lines.append('')
    open(REPORT_PATH, 'w', encoding='utf-8').write('\n'.join(lines))

    print('=== GENERATE MATRIX ===')
    print('tổng: %d (EXISTING %d, REVIEW %d, PLANNED %d)' % (
        len(rows), len(existing), len(review), len(planned)))
    print('chống trùng: PASS (id/slug/canonical/output_path/keyword/intent)')
    print('thiếu so với planned_target %d: %d hàng (báo thiếu, không đệm)' % (
        sum(targets.values()), sum(targets.values()) - len(planned)))


if __name__ == '__main__':
    main()
