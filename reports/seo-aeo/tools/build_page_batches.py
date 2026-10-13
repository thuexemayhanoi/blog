#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build analysis batches for the MAIN PAGES (home, hubs, categories, topic pages, static pages). READ-ONLY.

  python3 reports/seo-aeo/tools/build_page_batches.py --text-dir <dir with PG-*.txt exports> --out <batch dir> [--size 8]

Needs reports/seo-aeo/data/{pages-extract,rendered-pages}.json (extract_audit_data.py + extract_rendered.py).
The agent reads the plain-text export of the RENDERED page (what a visitor / crawler sees in <main>); long card lists are
truncated in the export, totals are kept in the pack (post_cards_in_main, list totals).
"""
import argparse
import collections
import csv
import importlib.util
import json
import math
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
DATA = ROOT / 'reports/seo-aeo/data'
PRICING = ['/bang-gia/', '/bang-gia-xe-so/', '/bang-gia-xe-ga/', '/bang-gia-xe-dien/', '/bang-gia-xe-50cc/']
STATIC = ['/lien-he/', '/gioi-thieu/']


def load_ex():
    spec = importlib.util.spec_from_file_location('extract_audit_data', str(ROOT / 'reports/seo-aeo/tools/extract_audit_data.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--text-dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--size', type=int, default=8)
    a = ap.parse_args()
    os.chdir(ROOT)
    ex = load_ex()
    pages = json.loads((DATA / 'pages-extract.json').read_text(encoding='utf-8'))
    rend = {r['page_id']: r for r in json.loads((DATA / 'rendered-pages.json').read_text(encoding='utf-8'))}
    rows = [r for r in csv.DictReader(open('data/content-matrix.csv', encoding='utf-8', newline='')) if r['status'] in ('EXISTING', 'PUBLISHED')]
    # token index over live post titles (for "posts that compete with this page")
    toks = {r['id']: set(ex.tokens(r['title'])) for r in rows}
    df = collections.Counter(t for s in toks.values() for t in s)
    N = len(rows)
    idf = {t: math.log((N + 1) / (c + 1)) + 1 for t, c in df.items()}
    title_of = {r['id']: r['title'] for r in rows}
    url_of = {r['id']: ex.norm_path(r['expected_url']) for r in rows}

    def similar_posts(page_title, desc, k=6):
        q = set(ex.tokens(page_title + ' ' + desc))
        if not q:
            return []
        sc = []
        for pid, s in toks.items():
            inter = q & s
            if not inter:
                continue
            w = sum(idf.get(t, 1) for t in inter) / (sum(idf.get(t, 1) for t in q | s) or 1)
            sc.append((w, pid))
        sc.sort(reverse=True)
        return [{'id': pid, 'title': title_of[pid], 'url': url_of[pid], 'score': round(w, 3)} for w, pid in sc[:k]]

    by_hub = collections.defaultdict(list)
    for p in pages:
        if p['page_type'] == 'Topic cluster page':
            by_hub[p['canonical_path'].split('/')[1]].append(p['canonical_path'])

    items = []
    for p in pages:
        r = rend.get(p['page_id'])
        if not r:
            continue
        txt = pathlib.Path(a.text_dir) / (p['page_id'] + '.txt')
        hub = p['canonical_path'].split('/')[1] if p['page_type'] == 'Topic cluster page' else None
        allowed = []
        if hub:
            allowed.append('/%s/' % hub)
            allowed += [u for u in by_hub[hub] if u != p['canonical_path']][:12]
        else:
            allowed += ['/', '/chu-de/']
        allowed += PRICING + STATIC
        seen, al = set(), []
        for x in allowed:
            if x not in seen and x != p['canonical_path']:
                seen.add(x)
                al.append(x)
        items.append({
            'id': p['page_id'], 'kind': 'PAGE', 'page_type': p['page_type'], 'layout': p['layout'],
            'source_text_path': str(txt),
            'source_note': 'plain-text export of the rendered <main> of the page as built from the repo (headings are prefixed with #; '
                           'card/list blocks are truncated after 12 items with the total noted). No front matter. "line" numbers do not exist; '
                           'cite the nearest heading text as the location.',
            'repo_source_file': p['source'], 'canonical_path': p['canonical_path'], 'canonical_url': p['canonical_url'],
            'title': r['title'], 'meta_description': r['meta_description'], 'h1': r['h1'], 'h2': r['h2'][:20], 'h3_count': r['h3_count'],
            'visible_words_main': r['visible_words_main'], 'post_cards_in_main': r['post_cards_in_main'],
            'jsonld_types': r['jsonld_types'], 'jsonld_has_faqpage': r['jsonld_has_faqpage'],
            'breadcrumb_list_jsonld': r['breadcrumb_list_count'],
            'visible_faq_markers': r['faq'],
            'links_by_region': r['links_by_region'],
            'main_links_sample': [x['t'] for x in r['links_main_other'][:25]],
            'source_has_liquid_loops': p['source_has_liquid_loops'],
            'similar_posts_by_title_tokens': similar_posts(r['title'] or '', r['meta_description'] or ''),
            'allowed_link_targets': al,
        })
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(items), a.size):
        chunk = items[i:i + a.size]
        name = 'P%02d' % (i // a.size + 1)
        (out / (name + '.json')).write_text(json.dumps({
            'batch': name, 'rubric': str(ROOT / 'reports/seo-aeo/tools/agent-rubric.md'),
            'business_facts': str(ROOT / 'data/business-facts.json'), 'repo_root': str(ROOT), 'items': chunk},
            ensure_ascii=False, indent=1), encoding='utf-8')
        print(name, chunk[0]['id'], chunk[-1]['id'], len(chunk))


if __name__ == '__main__':
    main()
