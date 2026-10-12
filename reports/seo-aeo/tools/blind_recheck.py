#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent blind re-judgement (inter-rater check) — READ-ONLY.

  python3 reports/seo-aeo/tools/blind_recheck.py make   --analysis <dir with B*.json/P*.json> --batches <dir> --out <dir> [--n-posts 21 --n-pages 6 --seed 20261012]
  python3 reports/seo-aeo/tools/blind_recheck.py compare --analysis <dir> --blind <dir with Q*.json> --out reports/seo-aeo/data/blind-recheck.json

`make` draws a seeded, stratified sample (by FAQ status of the first pass) and copies the ORIGINAL packs (no first-pass results inside) into
Q01..Qnn batch files, so fresh agents judge them without seeing earlier answers. `compare` reports exact / adjacent agreement on
faq_status, recommended_action, priority, risk level and AI-search opportunity.
"""
import argparse
import collections
import glob
import json
import os
import pathlib
import random

ENUMS = ['faq_status', 'recommended_action', 'priority']


def load(dirp, pat):
    recs = {}
    for f in sorted(glob.glob(os.path.join(dirp, pat))):
        for r in json.loads(pathlib.Path(f).read_text(encoding='utf-8'))['records']:
            recs[r['id']] = r
    return recs


def load_packs(dirp):
    packs = {}
    for f in sorted(glob.glob(os.path.join(dirp, '[BP]*.json'))):
        d = json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
        for it in d['items']:
            packs[it['id']] = (d, it)
    return packs


def make(a):
    first = {**load(a.analysis, 'B*.json'), **load(a.analysis, 'P*.json')}
    packs = load_packs(a.batches)
    rnd = random.Random(a.seed)
    chosen = []
    for kind, n in (('POST', a.n_posts), ('PAGE', a.n_pages)):
        ids = [i for i in first if packs[i][1]['kind'] == kind]
        by_status = collections.defaultdict(list)
        for i in sorted(ids):
            by_status[first[i]['faq_status']].append(i)
        order = sorted(by_status)
        picked = []
        while len(picked) < n and any(by_status.values()):
            for s in order:
                if by_status[s] and len(picked) < n:
                    picked.append(by_status[s].pop(rnd.randrange(len(by_status[s]))))
        chosen += picked
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    per = 7
    for k in range(0, len(chosen), per):
        grp = chosen[k:k + per]
        name = 'Q%02d' % (k // per + 1)
        base = packs[grp[0]][0]
        (out / (name + '.json')).write_text(json.dumps({
            'batch': name, 'rubric': base['rubric'], 'business_facts': base['business_facts'], 'repo_root': base['repo_root'],
            'items': [packs[i][1] for i in grp]}, ensure_ascii=False, indent=1), encoding='utf-8')
        print(name, grp)


def compare(a):
    first = {**load(a.analysis, 'B*.json'), **load(a.analysis, 'P*.json')}
    blind = load(a.blind, 'Q*.json')
    pri = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
    res = {'n': len(blind), 'exact': {}, 'priority_within_1': 0, 'disagreements': []}
    for k in ENUMS + ['risk.level', 'ai_search_opportunity.level', 'cannibalization.level']:
        ok = 0
        for i, b in blind.items():
            f = first[i]
            get = lambda r: r[k] if '.' not in k else r[k.split('.')[0]][k.split('.')[1]]  # noqa: E731
            ok += get(f) == get(b)
        res['exact'][k] = '%d/%d (%.0f%%)' % (ok, len(blind), 100.0 * ok / max(1, len(blind)))
    for i, b in blind.items():
        f = first[i]
        res['priority_within_1'] += abs(pri[f['priority']] - pri[b['priority']]) <= 1
        diffs = {k: (f[k], b[k]) for k in ENUMS if f[k] != b[k]}
        if diffs:
            res['disagreements'].append({'id': i, 'first_vs_blind': diffs})
    res['priority_within_1'] = '%d/%d' % (res['priority_within_1'], len(blind))
    # unanimous "must-fix" agreement: P0 flagged by either
    p0_first = {i for i in blind if first[i]['priority'] == 'P0'}
    p0_blind = {i for i, b in blind.items() if b['priority'] == 'P0'}
    res['p0_overlap'] = {'first_only': sorted(p0_first - p0_blind), 'blind_only': sorted(p0_blind - p0_first), 'both': sorted(p0_first & p0_blind)}
    pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('make')
    m.add_argument('--analysis', required=True)
    m.add_argument('--batches', required=True)
    m.add_argument('--out', required=True)
    m.add_argument('--n-posts', type=int, default=21)
    m.add_argument('--n-pages', type=int, default=6)
    m.add_argument('--seed', type=int, default=20261012)
    c = sub.add_parser('compare')
    c.add_argument('--analysis', required=True)
    c.add_argument('--blind', required=True)
    c.add_argument('--out', required=True)
    a = ap.parse_args()
    (make if a.cmd == 'make' else compare)(a)


if __name__ == '__main__':
    main()
