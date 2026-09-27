#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# refill-queue.py - refill chu de LAZY cho queue 10K.
# Ledger: data/state/refill-candidates.json (candidate STAGED).
#   refill-queue.py --plan         in claimable + thoi diem refill
#   refill-queue.py --verify        kiem gate G1-G7; ghi bao cao
#                                  reports/factory/refill-verify.md
#   refill-queue.py --commit --yes  merge ledger vao matrix-seed
# Gate (KHONG ha nguong):
#  G1 child ton tai + headroom editorial_capacity
#  G2 kw chuan hoa duy nhat trong child (vs matrix + candidates)
#  G3 intent chuan hoa duy nhat trong child
#  G4 slug duy nhat (vs candidate; matrix kiem lai o
#     generate-matrix.py khi materialize)
#  G5 depth: word_target >= 1200
#  G6 candidate_id duy nhat trong ledger
#  G7 child phai thuoc taxonomy (ke thua source policy)
import csv
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
os.chdir(ROOT)

CAP_PATH = 'data/factory-capacity.json'
TAX_PATH = 'data/state/taxonomy-config.json'
MATRIX_PATH = 'data/content-matrix.csv'
LEDGER_PATH = 'data/state/refill-candidates.json'
SEED_PATH = 'data/state/matrix-seed.json'
REPORT_PATH = 'reports/factory/refill-verify.md'
MIN_WORD = 1200


def norm(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def slugify(s):
    s = norm(s)
    return re.sub(r'\s+', '-', s)[:80].strip('-')


def write_report(passed, cands, rej, errors):
    lines = [
        '# Refill verify report (tu dong, khong sua tay)',
        '',
        'Sinh boi scripts/factory/refill-queue.py --verify.',
        'Deterministic: chi phu thuoc matrix + ledger + capacity.',
        '',
        '- Candidates staged: %d' % len(cands),
        '- Rejected recorded: %d' % len(rej),
        '- Gate violations: %d' % len(errors),
        '- RESULT: %s' % ('PASS' if passed else 'FAIL'),
        '',
        '## Gate violations',
        '',
    ]
    if errors:
        for e in errors:
            lines.append('- %s' % e)
    else:
        lines.append('- (khong co)')
    lines.append('')
    lines.append('## Candidates staged')
    lines.append('')
    lines.append('| candidate | child | kw | word |')
    lines.append('|---|---|---|---|')
    for c in cands:
        lines.append('| %s | %s | %s | %s |'
                      % (c['candidate_id'], c['child_id'],
                         c['kw'], c.get('word_target', '')))
    lines.append('')
    os.makedirs('reports/factory', exist_ok=True)
    open(REPORT_PATH, 'w', encoding='utf-8').write(
        '\n'.join(lines))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else '--plan'
    cap = json.load(open(CAP_PATH, encoding='utf-8'))
    tax = json.load(open(TAX_PATH, encoding='utf-8'))
    rows = list(csv.DictReader(open(MATRIX_PATH, encoding='utf-8')))
    tax_kids = set(c[0] for c in tax['children'])
    child_caps = cap['child_editorial_capacity']
    th = cap['thresholds']
    if mode == '--plan':
        claimable = sum(1 for r in rows if r['status'] == 'PLANNED')
        print('=== REFILL PLAN ===')
        print('claimable PLANNED : %d' % claimable)
        print('min_ready_queue   : %d' % th['min_ready_queue'])
        print('refill_target     : %d' % th['refill_target'])
        if claimable < th['min_ready_queue']:
            print('ACTION: refill den %d candidate'
                  % th['refill_target'])
        else:
            print('ACTION: khong can refill (queue con kho)')
        sys.exit(0)
    ledger = json.load(open(LEDGER_PATH, encoding='utf-8'))
    cands = ledger['candidates']
    rej = ledger.get('rejected', [])
    if mode == '--verify':
        errors = []
        mat_kw, mat_int = {}, {}
        per_child_mat = {}
        for r in rows:
            cid = r['child_id']
            per_child_mat[cid] = per_child_mat.get(cid, 0) + 1
            if norm(r['primary_keyword']):
                mat_kw[(cid, norm(r['primary_keyword']))] = r['id']
            if norm(r['intent']):
                mat_int[(cid, norm(r['intent']))] = r['id']
        staged_child = {}
        seen_cid, seen_kw = set(), {}
        seen_int, seen_slug = {}, set()
        for c in cands:
            cid = c['candidate_id']
            if cid in seen_cid:
                errors.append('%s: G6 candidate_id trung' % cid)
            seen_cid.add(cid)
            if c['child_id'] not in tax_kids:
                errors.append('%s: G1 child khong ton tai'
                              % cid)
                continue
            if c['child_id'] not in child_caps:
                errors.append('%s: G1 child khong co capacity'
                              % cid)
                continue
            staged_child[c['child_id']] = (
                staged_child.get(c['child_id'], 0) + 1)
            used = (per_child_mat.get(c['child_id'], 0)
                    + staged_child[c['child_id']])
            if used > child_caps[c['child_id']]:
                errors.append(
                    '%s: G1 vuot editorial_capacity' % cid)
            k = (c['child_id'], norm(c['kw']))
            if k in mat_kw:
                errors.append('%s: G2 kw trung matrix %s'
                              % (cid, mat_kw[k]))
            if k in seen_kw:
                errors.append('%s: G2 kw trung candidate %s'
                              % (cid, seen_kw[k]))
            seen_kw[k] = cid
            k = (c['child_id'], norm(c['intent']))
            if k in mat_int:
                errors.append('%s: G3 intent trung matrix %s'
                              % (cid, mat_int[k]))
            if k in seen_int:
                errors.append('%s: G3 intent trung candidate %s'
                              % (cid, seen_int[k]))
            seen_int[k] = cid
            sl = slugify(c['title'])
            if sl in seen_slug:
                errors.append('%s: G4 slug trung candidate'
                              % cid)
            seen_slug.add(sl)
            if int(c.get('word_target', 0)) < MIN_WORD:
                errors.append('%s: G5 word_target < %d'
                              % (cid, MIN_WORD))
        passed = not errors
        write_report(passed, cands, rej, errors)
        print('=== REFILL VERIFY (smoke test gates) ===')
        print('candidates staged : %d' % len(cands))
        print('rejected recorded : %d' % len(rej))
        print('report            : %s' % REPORT_PATH)
        if errors:
            print('GATE VIOLATIONS: %d' % len(errors))
            for e in errors[:20]:
                print(' -', e)
            sys.exit(1)
        print('ALL GATES: PASS (G1-G7)')
        sys.exit(0)
    if mode == '--commit':
        if '--yes' not in sys.argv:
            print('REFILL COMMIT can --yes (owner phe duyet)')
            sys.exit(2)
        seed = json.load(open(SEED_PATH, encoding='utf-8'))
        added = 0
        for c in cands:
            spec = seed['children'].setdefault(c['child_id'], {
                'group': '', 'rows': []})
            spec.setdefault('rows', [])
            spec['rows'].append({
                'title': c['title'], 'intent': c['intent'],
                'kw': c['kw'], 'kw2': c['kw2'],
                'links': c['links'],
                'subtopic': c.get('subtopic', ''),
                'audience': c.get('audience', ''),
                'location_scope': c.get('location_scope', ''),
                'word_target': c.get('word_target', 1200)})
            added += 1
        with open(SEED_PATH, 'w', encoding='utf-8') as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print('REFILL COMMIT: +%d rows vao matrix-seed' % added)
        print('BUOC KE: chay generate-matrix.py roi commit matrix')
        sys.exit(0)
    print('usage: refill-queue.py --plan | --verify | --commit --yes')
    sys.exit(2)


if __name__ == '__main__':
    main()
