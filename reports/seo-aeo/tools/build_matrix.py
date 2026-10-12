#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the FAQ SEO master matrix (READ-ONLY on the site; writes only under reports/seo-aeo/).

  python3 reports/seo-aeo/tools/build_matrix.py --analysis <dir with B*.json / P*.json> [--out reports/seo-aeo]

Inputs : data/first300-extract.json, data/rendered-first300.json, data/pages-extract.json, data/rendered-pages.json,
         data/deterministic-findings.json, validated agent analyses (B*.json for posts, P*.json for pages)
Outputs: faq-matrix-first300.csv (300 posts) | faq-matrix-main-pages.csv (77 pages) | faq-matrix-master.csv (union)
         data/faq-matrix.json (full-fidelity records for a future generator) | data/matrix-stats.json (numbers for the report)
"""
import argparse
import collections
import csv
import glob
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
SEP = ' ¦ '

COLUMNS = [
    'Article ID', 'URL (canonical)', 'Page Type', 'Topic Cluster', 'Primary Intent', 'Primary Keyword', 'FAQ Status',
    'Existing Questions', 'Existing Answers (location in post)', 'FAQ Quality', 'Suggested Questions',
    'Answer Source (existing passage)', 'Schema Status', 'Cannibalization (competing URLs)', 'Internal Links (keep/add/fix)',
    'AI Search Opportunity', 'Recommended Action', 'Priority', 'Risk', 'Implementation Method', 'QA Requirements',
    # extra evidence columns
    'Title', 'Word Count (visible)', 'Semantic Entities', 'Answer Directness', 'AI Extractability', 'Heading Structure',
    'Content Accuracy / Completeness', 'Unverifiable Claims', 'Title / Meta / Canonical / Indexability',
    'JSON-LD on page (rendered)', 'Inbound Links From Other Post Bodies', 'FAQ Duplication', 'Confidence',
]
STATUS_LABEL = {'EXPLICIT': 'Explicit', 'IMPLICIT': 'Implicit', 'NONE': 'None', 'NOT_RECOMMENDED': 'Not recommended'}
ACTION_LABEL = {'KEEP': 'KEEP', 'IMPROVE': 'IMPROVE', 'ADD': 'ADD', 'MERGE': 'MERGE', 'NO_FAQ': 'NO FAQ'}
LEVEL_LABEL = {'HIGH': 'High', 'MEDIUM': 'Medium', 'LOW': 'Low'}
METHOD_LABEL = {'TEMPLATE': 'Template', 'COMPONENT': 'Component', 'GENERATOR': 'Generator', 'CONTENT': 'Content'}
QUALITY_LABEL = {'GOOD': 'Good', 'FAIR': 'Fair', 'WEAK': 'Weak', 'NA': 'N/A'}
PRIORITY_ORDER = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
LEVEL_ORDER = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}


def j(*parts):
    return SEP.join(p for p in parts if p)


def load_analyses(pattern):
    recs = {}
    for f in sorted(glob.glob(pattern)):
        d = json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
        for r in d['records']:
            recs[r['id']] = r
    return recs


def schema_status(a, rend):
    if rend.get('jsonld_has_faqpage'):
        return 'Existing'
    if a['faq_status'] == 'EXPLICIT' or a['recommended_action'] in ('KEEP', 'IMPROVE', 'ADD'):
        return 'Missing'
    return 'Not applicable'


def jsonld_summary(rend):
    blocks = rend.get('jsonld_blocks') or []
    types = rend.get('jsonld_types') or []
    bad = [b for b in blocks if not b['valid_json']]
    bc_null = sum(b.get('breadcrumb', {}).get('null_or_empty_names', 0) for b in blocks)
    return '%s | blocks=%d valid=%s%s%s' % (
        ','.join(types) or 'none', len(blocks), 'yes' if not bad else 'NO(%d)' % len(bad),
        ' | FAQPage=yes' if rend.get('jsonld_has_faqpage') else ' | FAQPage=no',
        ' | breadcrumb null names=%d' % bc_null if bc_null else '')


def meta_summary(det, rend, expected_canonical):
    t = rend.get('title') or ''
    d = rend.get('meta_description') or ''
    canon_ok = (rend.get('canonical') or '') == expected_canonical
    h1 = rend.get('h1') or []
    return 'title %dc%s | description %dc%s | canonical %s | robots %s | in sitemap %s | H1 x%d' % (
        len(t), ' (>60)' if len(t) > 60 else '', len(d), ' (>160)' if len(d) > 160 else '',
        'OK' if canon_ok else 'MISMATCH', rend.get('robots') or 'none (indexable)',
        'yes' if det.get('in_live_sitemap') else 'NO', len(h1))


def links_summary(rend, a, is_post):
    reg = rend.get('links_by_region') or {}
    keep = []
    if is_post:
        keep.append('keep: breadcrumb x%d (hub+topic), TOC x%d, prev/next x%d, related x%d, CTA->/bang-gia/ x%d, body x%d' % (
            reg.get('breadcrumb', 0), reg.get('toc', 0), reg.get('prev_next', 0), reg.get('related', 0), reg.get('cta', 0),
            reg.get('article_body', 0)))
    else:
        keep.append('keep: breadcrumb x%d, main x%d' % (reg.get('breadcrumb', 0), reg.get('main_other', 0)))
    il = a['internal_links']
    add = ['add: %s (%s)' % (x['target'], x['reason']) for x in il.get('add', [])]
    fix = ['fix: %s' % x if isinstance(x, str) else 'fix: %s' % json.dumps(x, ensure_ascii=False) for x in il.get('fix', [])]
    return j(il.get('assessment', ''), *keep, *add, *fix)


def row_for(kind, ident, det, rend, a, url_of):
    is_post = kind == 'Post'
    cb = a['cannibalization']
    comp = []
    for cid in cb.get('competing_ids') or []:
        comp.append('%s %s' % (cid, url_of.get(cid, '')))
    existing_q = SEP.join('%d) %s' % (i + 1, x['question']) for i, x in enumerate(a['existing_faq']))
    existing_loc = SEP.join('%d) %s' % (i + 1, x['answer_location']) for i, x in enumerate(a['existing_faq']))
    sugg_q = SEP.join('%d) %s%s' % (i + 1, x['question'], ' [needs fact-check]' if x.get('needs_fact_check') else '')
                      for i, x in enumerate(a['suggested_questions']))
    sugg_src = SEP.join('%d) %s: "%s"' % (i + 1, x['answer_source']['location'], x['answer_source']['quote'])
                        for i, x in enumerate(a['suggested_questions']))
    ucl = a['content_assessment'].get('unverifiable_claims') or []
    pk = a['primary_keyword']
    row = {
        'Article ID': ident,
        'URL (canonical)': det.get('canonical_url') or '',
        'Page Type': kind,
        'Topic Cluster': det['_cluster'],
        'Primary Intent': '%s - %s' % (a['primary_intent']['type'], a['primary_intent']['description']),
        'Primary Keyword': pk['value'] + ('' if pk['source'] == 'MATRIX' else ' (inferred)'),
        'FAQ Status': STATUS_LABEL[a['faq_status']],
        'Existing Questions': existing_q,
        'Existing Answers (location in post)': existing_loc,
        'FAQ Quality': j(QUALITY_LABEL[a['faq_quality']], a.get('faq_quality_notes', '')),
        'Suggested Questions': sugg_q,
        'Answer Source (existing passage)': sugg_src,
        'Schema Status': schema_status(a, rend),
        'Cannibalization (competing URLs)': j(LEVEL_LABEL.get(cb['level'], 'None') if cb['level'] != 'NONE' else 'None',
                                              cb.get('notes', ''), *comp),
        'Internal Links (keep/add/fix)': links_summary(rend, a, is_post),
        'AI Search Opportunity': '%s - %s' % (LEVEL_LABEL[a['ai_search_opportunity']['level']], a['ai_search_opportunity']['reason']),
        'Recommended Action': ACTION_LABEL[a['recommended_action']],
        'Priority': a['priority'],
        'Risk': '%s - %s' % (LEVEL_LABEL[a['risk']['level']], a['risk']['reason']),
        'Implementation Method': METHOD_LABEL[a['implementation_method']],
        'QA Requirements': a['qa_requirements'],
        'Title': (rend.get('title') or '').strip(),
        'Word Count (visible)': rend.get('visible_words_main', ''),
        'Semantic Entities': ', '.join(a['semantic_entities']),
        'Answer Directness': '%s%s' % (a['answer_directness']['level'],
                                       ' - "%s"' % a['answer_directness']['evidence_quote'] if a['answer_directness'].get('evidence_quote') else ''),
        'AI Extractability': '%s - %s' % (a['ai_extractability']['level'], a['ai_extractability']['reason']),
        'Heading Structure': '%s - %s' % (a['headings']['level'], a['headings']['notes']),
        'Content Accuracy / Completeness': 'accuracy risk %s; %s. %s' % (
            a['content_assessment']['accuracy_risk'], a['content_assessment']['completeness'], a['content_assessment'].get('notes', '')),
        'Unverifiable Claims': SEP.join('[%s] "%s" - %s' % (c['kind'], c['claim_quote'], c.get('note', '')) for c in ucl),
        'Title / Meta / Canonical / Indexability': j(meta_summary(det, rend, det.get('canonical_url') or ''),
                                                      a['title_meta']['assessment'] + ': ' + a['title_meta'].get('notes', '')),
        'JSON-LD on page (rendered)': jsonld_summary(rend),
        'Inbound Links From Other Post Bodies': det.get('_inbound', ''),
        'FAQ Duplication': '%s - %s' % (a['faq_duplication']['risk'], a['faq_duplication'].get('notes', '')),
        'Confidence': a['confidence'],
    }
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--out', default='reports/seo-aeo')
    ap.add_argument('--allow-missing', action='store_true', help='build a partial matrix (reports which ids are missing)')
    a = ap.parse_args()
    os.chdir(ROOT)
    out = pathlib.Path(a.out)
    data = out / 'data'
    posts = json.loads((data / 'first300-extract.json').read_text(encoding='utf-8'))
    pages = json.loads((data / 'pages-extract.json').read_text(encoding='utf-8'))
    rposts = {r['id']: r for r in json.loads((data / 'rendered-first300.json').read_text(encoding='utf-8'))}
    rpages = {r['page_id']: r for r in json.loads((data / 'rendered-pages.json').read_text(encoding='utf-8'))}
    an_posts = load_analyses(os.path.join(a.analysis, 'B*.json'))
    an_pages = load_analyses(os.path.join(a.analysis, 'P*.json'))
    mat = {r['id']: r for r in csv.DictReader(open('data/content-matrix.csv', encoding='utf-8', newline=''))}
    url_of = {i: (r['expected_url'] or '') for i, r in mat.items()}
    for p in pages:
        url_of[p['page_id']] = p['canonical_path']

    missing = [p['id'] for p in posts if p['id'] not in an_posts] + [p['page_id'] for p in pages if p['page_id'] not in an_pages]
    if missing and not a.allow_missing:
        raise SystemExit('missing analyses for %d ids: %s' % (len(missing), missing[:20]))

    rows_posts, rows_pages, full = [], [], []
    for p in posts:
        if p['id'] not in an_posts:
            continue
        tx = p['taxonomy']
        p['_cluster'] = '%s / %s' % (tx.get('parent_title') or '?', tx.get('child_title') or '?')
        p['_inbound'] = p['links']['inbound_from_posts']
        row = row_for('Post', p['id'], p, rposts[p['id']], an_posts[p['id']], url_of)
        rows_posts.append(row)
        full.append({'id': p['id'], 'kind': 'Post', 'url': p['canonical_url'], 'row': row, 'analysis': an_posts[p['id']],
                     'deterministic': {k: p[k] for k in ('file', 'title', 'description', 'categories', 'tags', 'word_count', 'meta', 'faq', 'links', 'similar', 'qa_scorer')},
                     'rendered': {k: rposts[p['id']][k] for k in ('title', 'meta_description', 'canonical', 'robots', 'h1', 'h2_count', 'h3_count', 'jsonld_types', 'jsonld_all_valid', 'jsonld_has_faqpage', 'links_by_region')}})
    for pg in pages:
        if pg['page_id'] not in an_pages:
            continue
        kind = {'Homepage': 'Homepage', 'Hub': 'Hub', 'Category': 'Category', 'Topic cluster page': 'Topic', 'Page': 'Page'}[pg['page_type']]
        parts = [x for x in pg['canonical_path'].strip('/').split('/') if x]
        pg['_cluster'] = ' / '.join(parts) if parts else 'Trang chủ'
        pg['_inbound'] = ''
        row = row_for(kind, pg['page_id'], pg, rpages[pg['page_id']], an_pages[pg['page_id']], url_of)
        rows_pages.append(row)
        full.append({'id': pg['page_id'], 'kind': kind, 'url': pg['canonical_url'], 'row': row, 'analysis': an_pages[pg['page_id']],
                     'rendered': {k: rpages[pg['page_id']][k] for k in ('title', 'meta_description', 'canonical', 'robots', 'h1', 'h2_count', 'h3_count', 'jsonld_types', 'jsonld_all_valid', 'jsonld_has_faqpage', 'links_by_region')}})

    def write_csv(path, rows):
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            for r in rows:
                w.writerow({k: re.sub(r'[\r\n]+', ' ', str(v)) for k, v in r.items()})

    write_csv(out / 'faq-matrix-first300.csv', rows_posts)
    write_csv(out / 'faq-matrix-main-pages.csv', rows_pages)
    write_csv(out / 'faq-matrix-master.csv', rows_posts + rows_pages)
    (data / 'faq-matrix.json').write_text(json.dumps(full, ensure_ascii=False, indent=1), encoding='utf-8')

    # ------------------------------------------------------------------ statistics for the report
    def stats(recs, rend, label):
        s = collections.Counter()
        for i, r in recs.items():
            s['n'] += 1
            s['status_' + r['faq_status']] += 1
            s['action_' + r['recommended_action']] += 1
            s['priority_' + r['priority']] += 1
            s['opportunity_' + r['ai_search_opportunity']['level']] += 1
            s['method_' + r['implementation_method']] += 1
            s['risk_' + r['risk']['level']] += 1
            s['canni_' + r['cannibalization']['level']] += 1
            s['dup_' + r['faq_duplication']['risk']] += 1
            s['directness_' + r['answer_directness']['level']] += 1
            s['extract_' + r['ai_extractability']['level']] += 1
            s['headings_' + r['headings']['level']] += 1
            s['unverifiable_claims_urls'] += bool(r['content_assessment'].get('unverifiable_claims'))
            s['faqpage_eligible_now'] += bool(r['schema_fit']['faqpage_eligible_now'])
            s['intent_' + r['primary_intent']['type']] += 1
            if r['faq_status'] == 'EXPLICIT':
                s['explicit_quality_' + r['faq_quality']] += 1
            sr = rend.get(i) or {}
            s['jsonld_all_valid_' + str(bool(sr.get('jsonld_all_valid')))] += 1
            s['has_faqpage_jsonld'] += bool(sr.get('jsonld_has_faqpage'))
            s['should_have_faq'] += r['recommended_action'] in ('KEEP', 'IMPROVE', 'ADD')
            s['should_not_have_faq'] += r['recommended_action'] in ('NO_FAQ',)
            s['merge'] += r['recommended_action'] == 'MERGE'
        s['label'] = label
        return dict(s)

    stats_doc = {'posts': stats(an_posts, rposts, 'posts'), 'pages': stats(an_pages, rpages, 'pages')}
    both = {**{k: v for k, v in an_posts.items()}, **{k: v for k, v in an_pages.items()}}

    def top20():
        rows = []
        for i, r in both.items():
            rows.append((PRIORITY_ORDER[r['priority']], LEVEL_ORDER[r['ai_search_opportunity']['level']],
                         0 if r['risk']['level'] == 'HIGH' else 1 if r['risk']['level'] == 'MEDIUM' else 2, i, r))
        rows.sort(key=lambda x: x[:4])
        fm = {x['id']: x for x in full}
        return [{'id': i, 'url': fm[i]['url'], 'priority': r['priority'], 'action': r['recommended_action'],
                 'faq_status': r['faq_status'], 'opportunity': r['ai_search_opportunity']['level'], 'risk': r['risk']['level'],
                 'why': r['ai_search_opportunity']['reason'], 'risk_reason': r['risk']['reason']}
                for _, _, _, i, r in rows[:20]]

    stats_doc['top20'] = top20()
    stats_doc['rows'] = {'posts': len(rows_posts), 'pages': len(rows_pages), 'missing': missing}
    cann = collections.defaultdict(list)
    for i, r in both.items():
        if r['cannibalization']['level'] in ('MEDIUM', 'HIGH'):
            cann[tuple(sorted([i] + list(r['cannibalization'].get('competing_ids') or [])))].append(i)
    stats_doc['cannibalization_groups'] = [{'ids': list(k), 'level': both[v[0]]['cannibalization']['level'], 'notes': both[v[0]]['cannibalization'].get('notes', '')}
                                           for k, v in cann.items()]
    (data / 'matrix-stats.json').write_text(json.dumps(stats_doc, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'posts_rows': len(rows_posts), 'pages_rows': len(rows_pages), 'missing': len(missing),
                      'posts': stats_doc['posts'], 'pages': stats_doc['pages']}, ensure_ascii=False, indent=1)[:4000])


if __name__ == '__main__':
    main()
