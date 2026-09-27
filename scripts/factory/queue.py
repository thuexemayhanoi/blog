#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# queue.py - lop queue nhe PHIA TREN data/content-matrix.csv.
# KHONG tao nguon su that thu hai: matrix van la nguon duy nhat.
#   queue.py --stats         in thong ke queue
#   queue.py --needs-refill  exit 0 neu claimable < min_ready_queue
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
os.chdir(ROOT)

CAP_PATH = 'data/factory-capacity.json'
MATRIX_PATH = 'data/content-matrix.csv'


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else '--stats'
    cap = json.load(open(CAP_PATH, encoding='utf-8'))
    rows = list(csv.DictReader(open(MATRIX_PATH, encoding='utf-8')))
    th = cap['thresholds']
    child_caps = cap['child_editorial_capacity']
    claimable = [r for r in rows if r['status'] == 'PLANNED']
    per_child = {}
    for r in rows:
        per_child[r['child_id']] = per_child.get(r['child_id'], 0) + 1
    if mode == '--stats':
        print('=== QUEUE STATS (view over matrix) ===')
        print('claimable PLANNED : %d' % len(claimable))
        print('min_ready_queue    : %d' % th['min_ready_queue'])
        print('refill_target      : %d' % th['refill_target'])
        print('next refill need   : %d'
              % max(0, th['refill_target'] - len(claimable)))
        print('--- per-child: materialized / editorial capacity ---')
        for cid in sorted(child_caps):
            m = per_child.get(cid, 0)
            print('%-22s %5d / %5d (con %d)'
                  % (cid, m, child_caps[cid],
                     child_caps[cid] - m))
        sys.exit(0)
    if mode == '--needs-refill':
        if len(claimable) < th['min_ready_queue']:
            print('NEEDS REFILL: claimable %d < %d'
                  % (len(claimable), th['min_ready_queue']))
            sys.exit(0)
        print('NO REFILL NEEDED: claimable %d >= %d'
              % (len(claimable), th['min_ready_queue']))
        sys.exit(1)
    print('usage: queue.py --stats | --needs-refill')
    sys.exit(2)


if __name__ == '__main__':
    main()
