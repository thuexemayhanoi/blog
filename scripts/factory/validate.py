#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validator nền tảng cho BLOG FACTORY - thuexemayhanoi/blog

Chạy: python3 scripts/factory/validate.py [--scope chunk|batch|full] [--ids ID1,ID2]

Mã thoát: 0 = PASS, 1 = FAIL, 2 = BLOCKED (thiếu dữ liệu nền không thể kiểm tra).

PHẠM VI (scope) — xem docs/PROC-PUBLISH.md "QA modes":
  full  (mặc định): toàn bộ repository — mọi kiểm tra bên dưới, kèm đối
        chiếu sitemap công khai (mạng). Dùng cho CI (factory-validate.yml)
        và kiểm tra định kỳ/final verification. KHÔNG dùng làm điều kiện
        chặn mỗi chunk 10 bài.
  batch (DEEP QA): nền tảng + toàn bộ inventory/matrix/hub/state, KHÔNG
        quét sitemap live qua mạng. Dùng sau ~50 bài hoặc khi cần soát
        rộng hơn chunk.
  chunk (FAST QA): CHỈ chunk hiện tại (từ checkpoint.in_progress_chunk hoặc
        --ids) + phần nền bắt buộc phải nguyên vẹn để sản xuất an toàn
        (taxonomy, tồn tại matrix/checkpoint/lock/transaction, cấu trúc
        matrix toàn cục, đếm trạng thái). KHÔNG: quét sitemap live, tính
        lại URL legacy 483 bài, xác minh hash QA của MỌI bài PUBLISHED
        (chỉ.verify hash QA của các bài trong chunk), đối chiếu inventory
        từng bài legacy. Mục đích: một chunk 10 bài không bị chặn bởi
        audit toàn site (docs/PROC-PUBLISH.md). Phát hiện vấn đề hệ thống
        ở scope chunk =證 cứ để nâng lên batch/full, KHÔNG hạ gate.

Nội dung các phần kiểm tra (giữ nguyên ngữ nghĩa theo scope):
  1. Tệp nền tảng bắt buộc tồn tại (mọi scope).
  2. Taxonomy (khôi phục từ seed) nhất quán: 7 parent, >= 51 child.
  3. Inventory khớp _posts/ legacy; URL legacy không đổi (batch/full).
     Đối chiếu sitemap công khai (CHỈ full).
  4. _data/factory-*.yml khớp taxonomy/inventory.
  5. Trang hub công khai cho mọi child có bài (full; batch warn).
  6. State + report phản ánh đúng số liệu thực.
  7. data/content-matrix.csv: ID/URL/canonical duy nhất, legacy khớp
     inventory, 10 REVIEW không bị đổi, PLANNED đủ dữ liệu, bằng chứng
     QA gắn nội dung (chunk: chỉ bài trong chunk).
"""
import argparse
import csv
import json
import os
import re
import sys
import collections
import hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

SCOPES = ('chunk', 'batch', 'full')

ERRORS, WARNS, BLOCKED = [], [], []
SECTIONS_RUN = []


def err(m): ERRORS.append(m)


def warn(m): WARNS.append(m)


def blocked(m): BLOCKED.append(m)


def section(name):
    SECTIONS_RUN.append(name)
    return True


def _read_csv(path):
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


# ---------------- 1. tệp bắt buộc (mọi scope)

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
    '_data/factory-taxonomy.yml', '_data/factory-map.yml', '_data/factory-parents.yml',
    '_includes/topic-directory.html',
]


def check_required_files(scope):
    section('required_files')
    for p in REQUIRED:
        if not os.path.exists(p):
            err('THIẾU TỆP NỀN TẢNG: %s (chạy: python3 scripts/factory/restore-foundation.py và generate-matrix.py)' % p)


# ---------------- 2. taxonomy (mọi scope)

def check_taxonomy(scope):
    section('taxonomy')
    tax = json.load(open('data/content-taxonomy.json', encoding='utf-8'))
    seed = json.load(open('data/state/taxonomy-config.json', encoding='utf-8'))
    parents = {p['parent_id']: p for p in tax['parents']}
    children = {c['child_id']: c for c in tax['children']}
    if len(parents) != 7: err('taxonomy phải có đúng 7 parent, có %d' % len(parents))
    if len(children) < 51: err('taxonomy bị mất child (phải >= 51, có %d)' % len(children))
    if len(children) != len(seed['children']):
        err('taxonomy children (%d) != seed children (%d)' % (len(children), len(seed['children'])))
    if len(seed['children']) < 51:
        err('seed taxonomy-config.json mất child gốc (phải >= 51)')
    for c in tax['children']:
        if c['parent_id'] not in parents: err('child %s không thuộc parent hợp lệ' % c['child_id'])
        p = parents[c['parent_id']]
        want = '/blog/%s/%s/' % (p['slug'], c['slug'])
        if c['hub_url'] != want: err('hub_url sai tại %s: %s' % (c['child_id'], c['hub_url']))
    seed_p = {s[0]: s for s in seed['parents']}
    seed_c = {s[0]: s for s in seed['children']}
    for pid, p in parents.items():
        if pid not in seed_p: err('parent %s không có trong seed' % pid)
        elif seed_p[pid][2] != p['slug']: err('parent %s đổi slug so với seed' % pid)
    for cid, c in children.items():
        if cid not in seed_c: err('child %s không có trong seed' % cid)
        elif seed_c[cid][3] != c['slug'] or seed_c[cid][1] != c['parent_id']:
            err('child %s đổi slug/parent so với seed' % cid)
    return tax, seed, parents, children


# ---------------- 3. inventory (chunk: chỉ cấu trúc; batch/full: đầy đủ)

def check_inventory(scope, parents, children):
    section('inventory_structure')
    inv = list(csv.DictReader(open('data/content-inventory.csv', encoding='utf-8')))

    def _is_factory(fn):
        return re.search(r'^article_id:', open('_posts/' + fn, encoding='utf-8').read()[:2000], re.M)
    legacy_files = [fn for fn in sorted(os.listdir('_posts')) if not _is_factory(fn)]
    factory_files = [fn for fn in sorted(os.listdir('_posts')) if _is_factory(fn)]
    if len(inv) != len(legacy_files):
        err('inventory != số tệp _posts legacy: %d/%d' % (len(inv), len(legacy_files)))
    inv_paths = set(r['source_path'] for r in inv)
    for fn in legacy_files:
        if '_posts/' + fn not in inv_paths: err('chưa ánh xạ: _posts/%s' % fn)
    if factory_files and not os.path.exists('data/content-matrix.csv'):
        err('có %d bài factory nhưng thiếu matrix' % len(factory_files))
    for r in inv:
        if r['likely_parent'] not in parents or r['likely_child'] not in children:
            err('inventory ánh xạ không hợp lệ: %s' % r['slug'])
        elif children[r['likely_child']]['parent_id'] != r['likely_parent']:
            err('inventory child/parent lệch nhau: %s' % r['slug'])
    # URL legacy: tính lại từng bài — CHỈ batch/full (đọc 483 tệp).
    if scope in ('batch', 'full'):
        section('inventory_legacy_urls')
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
    # Đối chiếu sitemap công khai (mạng) — CHỈ full.
    if scope == 'full':
        section('live_sitemap')
        import urllib.request, urllib.parse as up
        try:
            import urllib.request as _ur
            sm = _ur.urlopen('https://thuexemayhanoi.github.io/blog/sitemap.xml', timeout=30).read().decode('utf-8')
            live = set(re.findall(r'<loc>([^<]+)</loc>', sm))
            inv_urls = set('https://thuexemayhanoi.github.io' + up.quote(r['current_url'], safe='/:') for r in inv)
            miss = [u for u in inv_urls if u not in live]
            if miss:
                err('%d/%d URL legacy không khớp sitemap công khai (ví dụ: %s)' % (len(miss), len(inv_urls), sorted(miss)[0]))
            allowed_new = set()
            if os.path.exists('data/content-matrix.csv'):
                for mr in _read_csv('data/content-matrix.csv'):
                    if mr['status'] == 'PUBLISHED' and mr['source'].startswith('planned:') and '{date}' not in mr['expected_url']:
                        allowed_new.add('https://thuexemayhanoi.github.io' + up.quote(mr['expected_url'], safe='/:'))
            extra = [u for u in live if '/2026/' in u and u not in inv_urls and u not in allowed_new]
            if extra:
                err('sitemap có %d URL bài không nằm trong inventory (ví dụ: %s)' % (len(extra), sorted(extra)[0]))
        except Exception as e:
            warn('không kiểm tra được sitemap live (%s) — chỉ kiểm tra URL cục bộ' % e)
    return inv, legacy_files, factory_files


# ---------------- 4. _data cho layout (mọi scope — rẻ)

def check_layout_data(scope, tax, inv):
    section('layout_data')
    ft = open('_data/factory-taxonomy.yml', encoding='utf-8').read()
    fm = open('_data/factory-map.yml', encoding='utf-8').read()
    children = tax['children']
    for c in children:
        if ('\n%s:\n' % c['child_id']) not in ft:
            err('_data/factory-taxonomy.yml thiếu child %s' % c['child_id'])
    for r in inv:
        if ('\n%s:\n' % r['slug']) not in fm:
            err('_data/factory-map.yml thiếu slug %s' % r['slug'])


# ---------------- 5. trang hub công khai (warn; full kiểm chặt hơn)

def check_hubs(scope, tax, inv):
    section('hubs')
    parents = {p['parent_id']: p for p in tax['parents']}
    by_child = collections.Counter(r['likely_child'] for r in inv)
    for c in tax['children']:
        pslug = parents[c['parent_id']]['slug']
        page = os.path.join(pslug, c['slug'] + '.md')
        if by_child.get(c['child_id'], 0) > 0 and not os.path.exists(page):
            warn('child %s có %d bài nhưng chưa có trang hub công khai' % (c['child_id'], by_child[c['child_id']]))
    for pslug_dir in [p['slug'] for p in tax['parents']]:
        if not os.path.exists(pslug_dir + '.md'):
            err('thiếu trang parent hub: %s.md' % pslug_dir)


# ---------------- 6. state + report (mọi scope)

def check_state(scope, inv):
    section('state_report')
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
    return cp


# ---------------- 7. matrix

def _row_fp(mr):
    basis = {k: mr[k] for k in ('title', 'intent', 'primary_keyword',
                                'expected_url', 'output_path', 'canonical_url')}
    return hashlib.sha256(json.dumps(basis, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def check_matrix(scope, inv, legacy_files, factory_files, cp, chunk_ids):
    MATRIX = 'data/content-matrix.csv'
    mstat = None
    if not os.path.exists(MATRIX):
        blocked('data/content-matrix.csv THIẾT — không thể khôi phục bản gốc. Bằng chứng: reports/factory/matrix-recovery-blocked.md. Đây là BLOCKED có chủ đích, không phải PASS.')
        return mstat
    section('matrix_structure')
    mrows = _read_csv(MATRIX)
    mstat = collections.Counter(r['status'] for r in mrows)
    stat_valid = {'PLANNED', 'WRITING', 'QA', 'PASS', 'PUBLISHED', 'REVIEW', 'REPAIR', 'BLOCKED', 'FAIL', 'EXISTING'}
    ids = [r['id'] for r in mrows]
    if len(set(ids)) != len(ids): err('matrix id trùng')
    for key in ('output_path', 'canonical_url'):
        vals = [r[key] for r in mrows]
        if len(set(vals)) != len(vals): err('matrix %s trùng' % key)
    # thứ tự batch_id không xen kẽ (bất invariant rẻ, giữ mọi scope)
    _pl = [r for r in mrows if r.get('batch_id')]
    for _i in range(1, len(_pl)):
        if _pl[_i]['batch_id'] < _pl[_i - 1]['batch_id']:
            err('batch_id xen kẽ/lệch thứ tự tại %s (%s sau %s)'
                % (_pl[_i]['id'], _pl[_i]['batch_id'], _pl[_i - 1]['batch_id']))
            break
    # khớp inventory: số hàng legacy + URL — CHỈ batch/full
    if scope in ('batch', 'full'):
        section('matrix_legacy_inventory')
        legacy = [r for r in mrows if r['source'].startswith('legacy:')]
        if len(legacy) != len(inv): err('matrix legacy rows != inventory: %d/%d' % (len(legacy), len(inv)))
        inv_by_slug = {r['slug']: r for r in inv}
        for r in legacy:
            iv = inv_by_slug.get(os.path.basename(r['output_path'])[11:-3])
            if not iv: err('matrix legacy không khớp inventory: %s' % r['id']); break
            if r['expected_url'] != iv['current_url'] or r['canonical_url'] != iv['current_url']:
                err('matrix legacy URL đổi so với inventory: %s' % r['id']); break
            if r['status'] not in ('EXISTING', 'REVIEW'):
                err('matrix legacy status phải EXISTING/REVIEW: %s=%s' % (r['id'], r['status'])); break
        rv = [r for r in legacy if r['status'] == 'REVIEW']
        if len(rv) != 10: err('matrix REVIEW legacy phải đúng 10 hàng (không tự PASS), có %d' % len(rv))
    # ---- hàng PLANNED đủ dữ liệu (rẻ, giữ mọi scope)
    parents = json.load(open('data/content-taxonomy.json', encoding='utf-8'))
    pmap = {p['parent_id']: p for p in parents['parents']}
    cmap = {c['child_id']: c for c in parents['children']}
    for r in mrows:
        if r['status'] not in stat_valid: err('matrix status không hợp lệ: %s' % r['status'])
        if r['parent_id'] not in pmap or r['child_id'] not in cmap:
            err('matrix parent/child không hợp lệ tại %s' % r['id'])
        if r['status'] == 'PLANNED':
            if not r['intent'].strip() or not r['primary_keyword'].strip() or not r['internal_links'].strip():
                err('PLANNED %s thiếu intent/từ khóa/liên kết nội bộ' % r['id'])
            ch = cmap[r['child_id']]
            if r['source_required'] != str(ch['source_required']).lower():
                err('PLANNED %s source_required lệch taxonomy' % r['id'])
            if r['legal_risk'] != ch['legal_risk']:
                err('PLANNED %s legal_risk lệch taxonomy' % r['id'])
            for col in ('slug', 'search_intent', 'parent_hub', 'child_cluster',
                        'cannibalization_key', 'word_target', 'batch_id'):
                if col not in r or not r[col].strip():
                    err('PLANNED %s thiếu cột schema v2: %s' % (r['id'], col))
            if r['search_intent'] != r['intent']:
                err('PLANNED %s search_intent != intent' % r['id'])
            if r['cannibalization_key'] != r['cannibalization_key'].lower().strip():
                err('PLANNED %s cannibalization_key chưa chuẩn hoá' % r['id'])
            try:
                if int(r['word_target']) < 800:
                    err('PLANNED %s word_target < 800' % r['id'])
            except ValueError:
                err('PLANNED %s word_target không phải số' % r['id'])
            if r['batch_id'] and not re.match(r'^B\d{3}$', r['batch_id']):
                err('PLANNED %s batch_id sai dạng B###' % r['id'])
    # bài factory trong _posts phải là hàng PUBLISHED của matrix (mọi scope:
    # đây là bất biến protect-and-advance của bài đã xuất bản)
    section('matrix_published_files')
    mpub = {r['id']: r for r in mrows if r['status'] == 'PUBLISHED' and r['source'].startswith('planned:')}
    seen_aids = set()
    for fn in factory_files:
        am = re.search(r'^article_id:\s*(BLG-\d+)', open('_posts/' + fn, encoding='utf-8').read()[:2000], re.M)
        if not am:
            err('bài factory _posts/%s thiếu article_id' % fn); continue
        aid = am.group(1)
        if aid in seen_aids: err('article_id trùng giữa các tệp factory: %s' % aid)
        seen_aids.add(aid)
        mr = mpub.get(aid)
        if mr is None:
            err('bài factory %s (_posts/%s) không phải hàng PUBLISHED trong matrix' % (aid, fn)); continue
        if mr['output_path'] != '_posts/' + fn:
            err('bài factory %s: output_path matrix (%s) != tệp thật (_posts/%s)' % (aid, mr['output_path'], fn))
        if '{date}' in mr['expected_url'] or '{date}' in mr['output_path']:
            err('bài factory %s vẫn còn placeholder {date} trong URL/đường dẫn' % aid)
    orphan = [aid for aid in mpub if aid not in seen_aids]
    if orphan:
        err('matrix PUBLISHED %s không có tệp _posts tương ứng' % ', '.join(sorted(orphan)))
    # bằng chứng QA gắn nội dung: chunk -> chỉ bài trong chunk hiện tại;
    # batch/full -> toàn bộ bài PUBLISHED.
    section('qa_evidence' + ('_chunk' if scope == 'chunk' else ''))
    targets = dict(mpub)
    if scope == 'chunk':
        targets = {aid: mr for aid, mr in mpub.items() if aid in chunk_ids}
    for aid, mr in targets.items():
        qap = os.path.join('data/qa', aid + '.json')
        if not os.path.exists(qap):
            err('bài PUBLISHED %s thiếu bằng chứng QA %s' % (aid, qap)); continue
        qa = json.load(open(qap, encoding='utf-8'))
        if not qa.get('content_sha256') or not qa.get('matrix_row_sha256'):
            err('QA %s thiếu content_sha256/matrix_row_sha256 (bắt buộc từ gate v3)' % aid); continue
        real_sha = hashlib.sha256(open(mr['output_path'], 'rb').read()).hexdigest()
        if real_sha != qa['content_sha256']:
            err('QA %s content_sha256 không khớp tệp %s (nội dung đổi sau QA?)' % (aid, mr['output_path']))
        if _row_fp(mr) != qa['matrix_row_sha256']:
            err('QA %s matrix_row_sha256 không khớp hàng matrix hiện tại' % aid)
        if not qa.get('source_path') or qa['source_path'] != mr['output_path']:
            err('QA %s source_path (%s) != output_path matrix (%s)' % (aid, qa.get('source_path'), mr['output_path']))
    if cp['counts'].get('existing') != mstat.get('EXISTING', 0): err('checkpoint existing lệch matrix')
    if cp['counts'].get('review') != mstat.get('REVIEW', 0): err('checkpoint review lệch matrix')
    if cp['counts'].get('planned') != mstat.get('PLANNED', 0): err('checkpoint planned lệch matrix')
    return mstat


def run(scope, ids=None):
    check_required_files(scope)
    if ERRORS:
        return None, None
    tax, seed, parents, children = check_taxonomy(scope)
    inv, legacy_files, factory_files = check_inventory(scope, parents, children)
    check_layout_data(scope, tax, inv)
    check_hubs(scope, tax, inv)
    cp = check_state(scope, inv)
    chunk_ids = set(ids or [])
    if not chunk_ids:
        try:
            chunk_ids = set((cp.get('in_progress_chunk') or []))
        except Exception:
            chunk_ids = set()
    mstat = check_matrix(scope, inv, legacy_files, factory_files, cp, chunk_ids)
    return tax, inv, mstat, cp


def main():
    ap = argparse.ArgumentParser(description='Validator nền tảng (scoped)')
    ap.add_argument('--scope', choices=SCOPES, default='full',
                    help='chunk = chỉ chunk hiện tại (FAST QA); batch = DEEP; full = toàn bộ (mặc định)')
    ap.add_argument('--ids', default='',
                    help='danh sách ID của chunk (phạm vi scope=chunk khi checkpoint trống)')
    args = ap.parse_args()
    ids = [i.strip() for i in (args.ids or '').split(',') if i.strip()]
    out = run(args.scope, ids)
    if out is None or (isinstance(out, tuple) and out[0] is None and ERRORS):
        print('=== VALIDATE FOUNDATION (scope=%s) ===' % args.scope)
        for e in ERRORS: print('FAIL:', e)
        print('KẾT QUẢ: FAIL (thiếu tệp nền tảng)')
        sys.exit(1)
    tax, inv, mstat, cp = out
    print('=== VALIDATE FOUNDATION (scope=%s) ===' % args.scope)
    print('Phạm vi đã chạy: %s' % ','.join(SECTIONS_RUN))
    print('Taxonomy: %d parent / %d child | Inventory: %d bài legacy | Matrix: %s' % (
        len(tax['parents']), len(tax['children']), len(inv), 'CÓ' if mstat else 'BLOCKED (thiếu)'))
    if mstat: print('Trạng thái matrix: %s' % dict(mstat))
    for b in BLOCKED: print('BLOCKED:', b)
    for w_ in WARNS: print('WARN:', w_)
    for e in ERRORS: print('FAIL:', e)
    # tóm tắt máy đọc được cho test/report
    print('SUMMARY_JSON: %s' % json.dumps(
        {'scope': args.scope, 'sections_run': SECTIONS_RUN,
         'errors': len(ERRORS), 'warnings': len(WARNS), 'blocked': len(BLOCKED)},
        ensure_ascii=False))
    if ERRORS:
        print('KẾT QUẢ: FAIL'); sys.exit(1)
    if BLOCKED:
        print('KẾT QUẢ: BLOCKED (nền trừ matrix hợp lệ)'); sys.exit(2)
    print('KẾT QUẢ: PASS (%d cảnh báo)' % len(WARNS)); sys.exit(0)


if __name__ == '__main__':
    main()
