#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# capacity-audit.py - kiem chung mo hinh nang luc 10K (read-only).
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
os.chdir(ROOT)

CAP_PATH = 'data/factory-capacity.json'
TAX_PATH = 'data/state/taxonomy-config.json'
MATRIX_PATH = 'data/content-matrix.csv'


def die(msg):
    print('CAPACITY FAIL: ' + msg)
    sys.exit(1)


def main():
    cap = json.load(open(CAP_PATH, encoding='utf-8'))
    tax = json.load(open(TAX_PATH, encoding='utf-8'))
    rows = list(csv.DictReader(open(MATRIX_PATH, encoding='utf-8')))
    hard = cap['hard_capacity']
    legacy_alloc = cap['legacy_allocation']
    child_caps = cap['child_editorial_capacity']
    th = cap['thresholds']
    child_sum = sum(child_caps.values())
    if child_sum + legacy_alloc != hard:
        die('tong child (%d) + legacy (%d) != hard (%d)'
            % (child_sum, legacy_alloc, hard))
    if cap['editorial_capacity_total'] != hard:
        die('editorial_capacity_total != hard_capacity')
    tax_kids = set(c[0] for c in tax['children'])
    cap_kids = set(child_caps)
    if tax_kids != cap_kids:
        die('child set lech taxonomy-config: %s'
            % sorted(cap_kids ^ tax_kids)[:6])
    by_child = {}
    for r in rows:
        cid = r.get('child_id', '')
        by_child[cid] = by_child.get(cid, 0) + 1
    over = [(cid, n, child_caps[cid]) for cid, n in by_child.items()
            if cid in child_caps and n > child_caps[cid]]
    if over:
        die('child vuot editorial_capacity: %s' % over[:5])
    materialized = len(rows)
    unmaterialized = hard - materialized
    if unmaterialized < 0:
        die('materialized (%d) vuot hard capacity' % materialized)
    claimable = sum(1 for r in rows if r['status'] == 'PLANNED')
    needs_refill = claimable < th['min_ready_queue']
    published = sum(1 for r in rows if r['status'] == 'PUBLISHED')
    existing = sum(1 for r in rows if r['status'] == 'EXISTING')
    print('=== CAPACITY AUDIT ===')
    print('hard_capacity          : %d' % hard)
    print('editorial allocated    : %d (children %d + legacy %d)'
          % (hard, child_sum, legacy_alloc))
    print('materialized topics    : %d' % materialized)
    print('unmaterialized capacity: %d' % unmaterialized)
    print('published (factory)    : %d' % published)
    print('legacy existing        : %d' % existing)
    print('claimable PLANNED      : %d (min_ready_queue %d)'
          % (claimable, th['min_ready_queue']))
    print('needs refill           : %s'
          % ('YES' if needs_refill else 'NO'))
    print('RESULT: PASS')
    sys.exit(0)


if __name__ == '__main__':
    main()
