#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mechanical acceptance checks for the FAQ audit deliverables (READ-ONLY).

  python3 reports/seo-aeo/tools/verify_deliverables.py [--root reports/seo-aeo] [--sitemap <live_sitemap_locs.txt>]

Checks (exit 1 on any failure):
  D1  faq-matrix-first300.csv: exactly 300 rows, unique Article IDs equal to sample-first300-ids.csv, all 21 required
      columns present with the user's names (mapped), no empty cell in required columns;
  D2  faq-matrix-main-pages.csv: 77 rows == main-pages-list.csv; master == first300 + main pages;
  D3  enumerations: FAQ Status, Recommended Action, Priority, Schema Status, Implementation Method are valid;
      status/action consistency (NONE -> NO FAQ; Not recommended -> NO FAQ|MERGE; Explicit -> KEEP|IMPROVE|MERGE;
      Implicit -> ADD|NO FAQ|MERGE); ADD rows have >= 2 suggested questions and a quoted answer source;
  D4  every post/page canonical URL is a real URL of the live sitemap (when --sitemap is given) or starts with the site host;
  D5  honesty: no invented traffic metrics (impressions/clicks/CTR/ranking/AI-citation numbers) in free text columns;
  D6  required deliverable files exist (summary + implementation plan).
"""
import argparse
import csv
import pathlib
import re
import sys

REQUIRED = {  # user's column name -> column in our CSV
    'Article ID': 'Article ID', 'URL canonical': 'URL (canonical)', 'Page Type': 'Page Type', 'Topic Cluster': 'Topic Cluster',
    'Primary Intent': 'Primary Intent', 'Primary Keyword': 'Primary Keyword', 'FAQ Status': 'FAQ Status',
    'Existing Questions': 'Existing Questions', 'Existing Answers (location)': 'Existing Answers (location in post)',
    'FAQ Quality': 'FAQ Quality', 'Suggested Questions': 'Suggested Questions', 'Answer Source': 'Answer Source (existing passage)',
    'Schema Status': 'Schema Status', 'Cannibalization': 'Cannibalization (competing URLs)',
    'Internal Links': 'Internal Links (keep/add/fix)', 'AI Search Opportunity': 'AI Search Opportunity',
    'Recommended Action': 'Recommended Action', 'Priority': 'Priority', 'Risk': 'Risk',
    'Implementation Method': 'Implementation Method', 'QA Requirements': 'QA Requirements',
}
ALLOWED_EMPTY = {'Existing Questions', 'Existing Answers (location in post)', 'Suggested Questions', 'Answer Source (existing passage)',
                 'Cannibalization (competing URLs)', 'Primary Keyword'}
STATUS = {'Explicit', 'Implicit', 'None', 'Not recommended'}
ACTION = {'KEEP', 'IMPROVE', 'ADD', 'MERGE', 'NO FAQ'}
PRIORITY = {'P0', 'P1', 'P2', 'P3'}
SCHEMA = {'Existing', 'Missing', 'Invalid', 'Not applicable'}
METHOD = {'Template', 'Component', 'Generator', 'Content'}
OK_ACTIONS = {'None': {'NO FAQ'}, 'Not recommended': {'NO FAQ', 'MERGE'}, 'Explicit': {'KEEP', 'IMPROVE', 'MERGE'},
              'Implicit': {'ADD', 'NO FAQ', 'MERGE'}}
METRIC = re.compile(r'((?<![\w-])\d[\d.,]*\s*(?:lượt hiển thị|impressions?|clicks?|lượt nhấp|lượt truy cập|sessions?)|\bCTR\s*[:=]?\s*\d|vị trí trung bình\s*\d|'
                    r'average position\s*\d|được (?:Google|AI|ChatGPT|Gemini|Perplexity) trích dẫn \d|ranks? #?\d)', re.I)


def read(path):
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='reports/seo-aeo')
    ap.add_argument('--sitemap', default='')
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    errs = []
    posts = read(root / 'faq-matrix-first300.csv')
    pages = read(root / 'faq-matrix-main-pages.csv')
    master = read(root / 'faq-matrix-master.csv')
    sample = [r['Article ID'] for r in read(root / 'sample-first300-ids.csv')]
    page_ids = [r['Page ID'] for r in read(root / 'main-pages-list.csv')]

    # D1
    if len(posts) != 300:
        errs.append('D1: first300 matrix has %d rows (need 300)' % len(posts))
    ids = [r['Article ID'] for r in posts]
    if len(set(ids)) != len(ids):
        errs.append('D1: duplicate Article IDs in first300 matrix')
    if sorted(ids) != sorted(sample):
        errs.append('D1: Article IDs differ from sample-first300-ids.csv (missing %s, extra %s)'
                    % (sorted(set(sample) - set(ids))[:5], sorted(set(ids) - set(sample))[:5]))
    for need, col in REQUIRED.items():
        if col not in (posts[0] if posts else {}):
            errs.append('D1: missing required column %r (%s)' % (need, col))
    for tbl, name in ((posts, 'first300'), (pages, 'main-pages')):
        for r in tbl:
            for col in REQUIRED.values():
                if col not in ALLOWED_EMPTY and not (r.get(col) or '').strip():
                    errs.append('D1: %s %s empty %r' % (name, r['Article ID'], col))
    # D2
    if len(pages) != 77:
        errs.append('D2: main-pages matrix has %d rows (need 77)' % len(pages))
    if sorted(r['Article ID'] for r in pages) != sorted(page_ids):
        errs.append('D2: page IDs differ from main-pages-list.csv')
    if len(master) != len(posts) + len(pages):
        errs.append('D2: master has %d rows (expected %d)' % (len(master), len(posts) + len(pages)))
    # D3
    for r in posts + pages:
        i = r['Article ID']
        s, act, pr, sc, me = r['FAQ Status'], r['Recommended Action'], r['Priority'], r['Schema Status'], r['Implementation Method']
        if s not in STATUS:
            errs.append('D3: %s bad status %r' % (i, s))
        if act not in ACTION:
            errs.append('D3: %s bad action %r' % (i, act))
        if pr not in PRIORITY:
            errs.append('D3: %s bad priority %r' % (i, pr))
        if sc not in SCHEMA:
            errs.append('D3: %s bad schema status %r' % (i, sc))
        if me not in METHOD:
            errs.append('D3: %s bad method %r' % (i, me))
        if s in OK_ACTIONS and act not in OK_ACTIONS[s]:
            errs.append('D3: %s status %s inconsistent with action %s' % (i, s, act))
        if act == 'ADD':
            if (r['Suggested Questions'] or '').count('¦') < 1:
                errs.append('D3: %s ADD with < 2 suggested questions' % i)
            if '"' not in (r['Answer Source (existing passage)'] or ''):
                errs.append('D3: %s ADD without a quoted answer source' % i)
    # D4
    locs = set()
    if a.sitemap:
        locs = {x.strip() for x in open(a.sitemap, encoding='utf-8') if x.strip()}
    for r in posts + pages:
        u = r['URL (canonical)']
        if not u.startswith('https://blog.thuexemaynguyentu.com/'):
            errs.append('D4: %s canonical outside the blog host: %s' % (r['Article ID'], u))
        elif locs and u not in locs and u.rstrip('/') + '/' not in locs:
            errs.append('D4: %s canonical not in live sitemap: %s' % (r['Article ID'], u))
    # D5
    for r in posts + pages:
        for col, v in r.items():
            if col in ('Title', 'Existing Questions', 'Existing Answers (location in post)', 'Answer Source (existing passage)',
                       'Suggested Questions'):
                continue
            m = METRIC.search(v or '')
            if m:
                errs.append('D5: %s column %r contains a traffic/ranking-like metric: %r' % (r['Article ID'], col, m.group(0)))
    # D6
    for f in ('faq-audit-summary.md', 'faq-implementation-plan.md'):
        if not (root / f).exists():
            errs.append('D6: missing deliverable %s' % f)
    print('first300 rows: %d | main pages: %d | master: %d | errors: %d' % (len(posts), len(pages), len(master), len(errs)))
    for e in errs[:60]:
        print('ERROR', e)
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
