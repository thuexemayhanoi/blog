#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""True inbound-link graph from the RENDERED site (READ-ONLY).

Parses every live post page of the local build (all matrix rows EXISTING|PUBLISHED) and counts, per target URL, links that
arrive from (a) article bodies, (b) the layout's "related posts" block, (c) prev/next navigation. Also keeps the list of source
ids for the audited sample. The source-level regex of extract_audit_data.py cannot see links written with Liquid
(`[text]({{ '/bang-gia/' | relative_url }})`, `{% post_url ... %}`), so the rendered HTML is the ground truth.

  python3 reports/seo-aeo/tools/inbound_graph.py --site <_site dir> [--out reports/seo-aeo/data]
"""
import argparse
import collections
import csv
import json
import os
import pathlib
import urllib.parse

from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[3]
SITE = 'https://blog.thuexemaynguyentu.com'


def norm(href):
    if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
        return None
    h = href.split('#')[0]
    if h.startswith(SITE):
        h = h[len(SITE):]
    if h.startswith('http') or not h.startswith('/'):
        return None
    h = urllib.parse.unquote(h)
    while '//' in h:
        h = h.replace('//', '/')
    return h or '/'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', required=True)
    ap.add_argument('--out', default='reports/seo-aeo/data')
    a = ap.parse_args()
    os.chdir(ROOT)
    rows = [r for r in csv.DictReader(open('data/content-matrix.csv', encoding='utf-8', newline=''))
            if r['status'] in ('EXISTING', 'PUBLISHED')]
    import re

    def real_url(r):
        # explicit front-matter permalink wins over the matrix expected_url (50 factory posts use /<cat>/YYYY-MM-DD/<slug>/)
        try:
            head = pathlib.Path(r['output_path']).read_text(encoding='utf-8').split('\n---', 2)[0]
            m = re.search(r'^permalink:\s*(\S+)\s*$', head, re.M)
            if m:
                return urllib.parse.unquote(m.group(1).strip('"\''))
        except OSError:
            pass
        return urllib.parse.unquote(r['expected_url'])

    url_to_id, id_to_url, permalink_mismatch = {}, {}, []
    for r in rows:
        u = real_url(r)
        url_to_id[u] = r['id']
        id_to_url[r['id']] = u
        if u != urllib.parse.unquote(r['expected_url']):
            permalink_mismatch.append(r['id'])
    body_in, related_in, prevnext_in = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(set)
    nonslash_variants = collections.Counter()
    parsed = 0
    for r in rows:
        u = id_to_url[r['id']]
        p = pathlib.Path(a.site) / u.lstrip('/') / 'index.html'
        if not p.is_file():
            continue
        parsed += 1
        raw = p.read_text(encoding='utf-8')
        soup = BeautifulSoup(raw, 'lxml')
        for anchor in soup.select('.post-content a[href], .article-body a[href]'):
            raw_href = anchor['href']
            t = norm(raw_href)
            if t:
                if '//' in urllib.parse.unquote(raw_href).replace('://', ''):
                    nonslash_variants[r['id']] += 1
                if t in url_to_id and url_to_id[t] != r['id']:
                    body_in[url_to_id[t]].add(r['id'])
        for anchor in soup.select('.article-related a[href]'):
            t = norm(anchor['href'])
            if t in url_to_id and url_to_id[t] != r['id']:
                related_in[url_to_id[t]].add(r['id'])
        for anchor in soup.select('.post-navigation a[href]'):
            t = norm(anchor['href'])
            if t in url_to_id and url_to_id[t] != r['id']:
                prevnext_in[url_to_id[t]].add(r['id'])
    first300 = json.loads((pathlib.Path(a.out) / 'first300-extract.json').read_text(encoding='utf-8'))
    ids = [x['id'] for x in first300]
    per = {i: {'inbound_body': len(body_in.get(i, ())), 'inbound_related': len(related_in.get(i, ())),
               'inbound_prev_next': len(prevnext_in.get(i, ())),
               'from_body': sorted(body_in.get(i, ()))[:12]} for i in ids}
    top_body = sorted(((len(v), k) for k, v in body_in.items()), reverse=True)[:15]
    doc = {
        'definition': 'inbound links counted from the rendered HTML of every live post (article body / related block / prev-next)',
        'posts_parsed': parsed,
        'sample': per,
        'sample_zero_inbound_body': sum(1 for v in per.values() if v['inbound_body'] == 0),
        'sample_zero_inbound_body_and_related': sum(1 for v in per.values() if v['inbound_body'] == 0 and v['inbound_related'] == 0),
        'sample_zero_inbound_anywhere': sum(1 for v in per.values() if v['inbound_body'] == v['inbound_related'] == v['inbound_prev_next'] == 0),
        'top_linked_by_body_across_site': [{'id': k, 'inbound_body': n} for n, k in top_body],
        'posts_with_double_slash_body_links': len(nonslash_variants),
        'matrix_expected_url_differs_from_real_permalink': {'count': len(permalink_mismatch), 'ids': permalink_mismatch[:60]},
    }
    (pathlib.Path(a.out) / 'inbound-graph.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in doc.items() if k != 'sample'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
