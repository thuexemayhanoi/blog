#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Site-wide FAQ question index (READ-ONLY).

Scans every live post (matrix status EXISTING / PUBLISHED, file present) with the same FAQ detector as
extract_audit_data.py and writes reports/seo-aeo/data/faq-index-site.json:

  * per post: FAQ section headings, Q&A pairs (question text), question-form headings
  * duplicate question clusters (same normalized question or token-set Jaccard >= 0.8) across posts
  * statistics for the whole site (context only: the audit sample is the first 300 live posts)

  python3 reports/seo-aeo/tools/faq_index.py [--out reports/seo-aeo/data]
"""
import argparse
import collections
import csv
import importlib.util
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]


def load_extractor():
    spec = importlib.util.spec_from_file_location('extract_audit_data', str(ROOT / 'reports/seo-aeo/tools/extract_audit_data.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def norm_question(ex, q):
    q = re.sub(r'^\s*(?:\d+[.)]|[-*•])\s*', '', q)            # leading "1." numbering
    q = re.sub(r'\?+\s*$', '', q)
    return ' '.join(ex.tokens(q))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='reports/seo-aeo/data')
    a = ap.parse_args()
    os.chdir(ROOT)
    ex = load_extractor()
    rows = list(csv.DictReader(open('data/content-matrix.csv', encoding='utf-8', newline='')))
    idn = lambda r: int(r['id'][4:])  # noqa: E731
    live = sorted([r for r in rows if r['status'] in ('EXISTING', 'PUBLISHED')], key=idn)

    per_post = {}
    stats = collections.Counter()
    for r in live:
        p = ROOT / r['output_path']
        if not p.is_file():
            stats['missing_file'] += 1
            continue
        fm, body = ex.parse_front_matter(p.read_text(encoding='utf-8'))
        heads = ex.md_headings(body)
        sig = ex.faq_signals(body, heads)
        questions = [x['question'] for x in sig['faq_pairs']]
        qheads = [h['text'] for h in sig['question_headings']]
        has_section = bool(sig['faq_section_headings'])
        stats['posts'] += 1
        stats['posts_status_' + r['status']] += 1
        stats['with_faq_section_heading'] += has_section
        stats['with_faq_pairs'] += bool(questions)
        stats['with_ge2_faq_pairs'] += len(questions) >= 2
        stats['with_question_headings'] += bool(qheads)
        stats['with_details'] += sig['details_blocks'] > 0
        if r['status'] == 'PUBLISHED':
            stats['published_with_faq_section_heading'] += has_section
            stats['published_with_ge2_faq_pairs'] += len(questions) >= 2
        else:
            stats['existing_with_faq_section_heading'] += has_section
            stats['existing_with_ge2_faq_pairs'] += len(questions) >= 2
        per_post[r['id']] = {'status': r['status'], 'faq_section_headings': sig['faq_section_headings'],
                             'pairs': questions, 'question_headings': qheads,
                             'pair_forms': sorted({x['form'] for x in sig['faq_pairs']})}

    # exact-normalized clusters
    by_norm = collections.defaultdict(list)
    for pid, d in per_post.items():
        for q in d['pairs'] + d['question_headings']:
            n = norm_question(ex, q)
            if n:
                by_norm[n].append((pid, q))
    exact = [{'normalized': n, 'count': len({pid for pid, _ in v}), 'ids': sorted({pid for pid, _ in v})[:30],
              'examples': sorted({q for _, q in v})[:3]}
             for n, v in by_norm.items() if len({pid for pid, _ in v}) >= 2]
    exact.sort(key=lambda c: (-c['count'], c['normalized']))

    # fuzzy: token-set Jaccard >= 0.8 between different normalized questions (>= 4 tokens)
    norms = [n for n in by_norm if len(n.split()) >= 4]
    inv = collections.defaultdict(set)
    for n in norms:
        for t in set(n.split()):
            inv[t].add(n)
    fuzzy = []
    seen = set()
    for n in norms:
        ts = set(n.split())
        cands = set()
        for t in ts:
            if len(inv[t]) < 300:
                cands |= inv[t]
        cands.discard(n)
        for m in cands:
            key = tuple(sorted((n, m)))
            if key in seen:
                continue
            seen.add(key)
            ms = set(m.split())
            j = len(ts & ms) / len(ts | ms)
            if j >= 0.8:
                ids = sorted({pid for pid, _ in by_norm[n]} | {pid for pid, _ in by_norm[m]})
                if len(ids) >= 2:
                    fuzzy.append({'a': n, 'b': m, 'jaccard': round(j, 2), 'ids': ids[:30]})
    fuzzy.sort(key=lambda c: (-len(c['ids']), -c['jaccard']))

    # generic-question frequency (questions appearing on many posts = template smell)
    generic = [c for c in exact if c['count'] >= 5][:40]

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'faq-index-site.json').write_text(json.dumps({
        'definition': 'all live posts (matrix EXISTING|PUBLISHED, file present); detector = extract_audit_data.faq_signals',
        'stats': dict(stats),
        'exact_duplicate_question_clusters': exact[:400],
        'fuzzy_duplicate_pairs': fuzzy[:400],
        'high_frequency_questions_ge5_posts': generic,
        'per_post': per_post,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'stats': dict(stats), 'exact_clusters': len(exact), 'fuzzy_pairs': len(fuzzy),
                      'high_frequency_ge5': len(generic)}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
