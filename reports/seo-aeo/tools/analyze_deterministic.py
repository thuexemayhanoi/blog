#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic findings for the FAQ / AEO audit (READ-ONLY): metadata hygiene, permalink hygiene, duplicate
titles/descriptions, similarity (cannibalization) clusters, slug defects, JSON-LD / link evidence from the rendered
build. Writes reports/seo-aeo/data/deterministic-findings.json.

  python3 reports/seo-aeo/tools/analyze_deterministic.py [--out reports/seo-aeo/data]
"""
import argparse
import collections
import csv
import json
import os
import pathlib
import re
import unicodedata
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[3]


def slug_without_d_fix(title):
    t = unicodedata.normalize('NFD', title)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    t = re.sub(r'[^a-z0-9 ]', '', t.lower()).strip()
    return re.sub(r'\s+', '-', t)[:80].strip('-')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='reports/seo-aeo/data')
    ap.add_argument('--text-dir', help='directory with PG-*.txt text exports of the rendered pages')
    a = ap.parse_args()
    os.chdir(ROOT)
    out = pathlib.Path(a.out)
    posts = json.loads((out / 'first300-extract.json').read_text(encoding='utf-8'))
    res = {}

    # ---- metadata hygiene (source-derived: title + site suffix as rendered by _includes/seo.html)
    tl = [p['meta']['title_len'] for p in posts]
    dl = [p['meta']['description_len'] for p in posts]
    res['metadata'] = {
        'rendered_title_len_gt_60': sum(1 for x in tl if x > 60),
        'rendered_title_len_gt_70': sum(1 for x in tl if x > 70),
        'rendered_title_len_max': max(tl), 'rendered_title_len_median': sorted(tl)[len(tl) // 2],
        'description_len_lt_70': sum(1 for x in dl if x < 70),
        'description_len_gt_160': sum(1 for x in dl if x > 160),
        'description_len_min': min(dl), 'description_len_max': max(dl),
        'description_missing': sum(1 for p in posts if p['meta']['description_missing']),
        'robots_meta_set': sum(1 for p in posts if p['meta']['robots_meta']),
        'canonical_override_set': sum(1 for p in posts if p['meta']['canonical_override']),
    }
    dup_t = collections.Counter(p['title'].strip().lower() for p in posts)
    dup_d = collections.Counter(p['description'].strip().lower() for p in posts if p['description'])
    res['duplicates_in_sample'] = {
        'duplicate_titles': [{'title': t, 'n': n} for t, n in dup_t.items() if n > 1],
        'duplicate_descriptions': [{'description': t[:120], 'n': n} for t, n in dup_d.items() if n > 1],
    }
    # titles/descriptions: does the title/description repeat the site name?
    res['metadata']['title_already_contains_site_name'] = sum(1 for p in posts if 'Nguyễn Tú' in p['title'])

    # ---- permalink hygiene
    non_ascii = [p for p in posts if re.search(r'[^\x00-\x7f]', p['canonical_path'])]
    spaces = [p for p in posts if ' ' in p['canonical_path']]
    cat_slugs = collections.Counter(p['canonical_path'].split('/')[1] for p in posts)
    res['permalinks'] = {
        'urls_with_non_ascii_path': len(non_ascii), 'urls_with_space_in_path': len(spaces),
        'first_segment_counts': dict(cat_slugs),
        'example': [{'id': p['id'], 'canonical_url': p['canonical_url']} for p in non_ascii[:3]],
        'note': 'Legacy posts use the Jekyll category name (e.g. "Kinh nghiệm") verbatim as the first URL segment (permalink: pretty); '
                'factory posts use ASCII category slugs. Changing a URL needs redirects: NOT in scope of this audit.',
    }

    # ---- structure / content hygiene
    wc = [p['word_count'] for p in posts]
    res['structure'] = {
        'word_count_min': min(wc), 'word_count_median': sorted(wc)[len(wc) // 2], 'word_count_max': max(wc),
        'body_h1_present': [p['id'] for p in posts if p['h1_in_body']],
        'posts_with_table': sum(1 for p in posts if p['tables']),
        'posts_without_h3': sum(1 for p in posts if p['h3_count'] == 0),
        'posts_with_ge4_h2': sum(1 for p in posts if p['h2_count'] >= 4),
        'posts_with_question_form_heading': sum(1 for p in posts if p['faq']['question_headings']),
        'posts_with_faq_like_heading': sum(1 for p in posts if p['faq']['faq_section_headings']),
        'posts_with_detected_qa_pairs': sum(1 for p in posts if p['faq']['faq_pairs']),
        'posts_with_nonapproved_amounts_signal': [p['id'] for p in posts if (p.get('qa_scorer') or {}).get('non_approved_amounts')],
        'posts_with_forbidden_claim_hits': [p['id'] for p in posts if (p.get('qa_scorer') or {}).get('forbidden_hits')],
        'body_internal_links_total': sum(p['links']['internal_count'] for p in posts),
        'body_external_links_total': sum(len(p['links']['external']) for p in posts),
    }
    def skips(heads):
        prev, bad = 1, []
        for h in heads:
            if h['level'] > prev + 1:
                bad.append('H%d after H%d (line %d)' % (h['level'], prev, h['line']))
            prev = h['level']
        return bad
    skipped = {p['id']: skips(p['headings']) for p in posts if skips(p['headings'])}
    res['structure']['heading_level_skips'] = {'posts': len(skipped), 'examples': dict(list(skipped.items())[:8])}
    generic = collections.Counter()
    for p in posts:
        for h in p['headings']:
            if h['level'] in (2, 3):
                generic[re.sub(r'^\d+\.\s*', '', h['text']).strip().lower()] += 1
    res['structure']['generic_repeated_headings_top'] = [{'heading': k, 'posts_count_occurrences': v} for k, v in generic.most_common(15)]
    cl = collections.Counter()
    for p in posts:
        cl[(p['matrix']['parent_id'], p['matrix']['child_id'])] += 1
    res['clusters'] = {'by_parent': dict(collections.Counter(p['matrix']['parent_id'] for p in posts)),
                       'by_child_top': {'%s/%s' % k: v for k, v in cl.most_common(20)}}

    # ---- similarity / cannibalization candidates (deterministic; semantic judgement is done per post later)
    ids = {p['id'] for p in posts}
    pairs = {}
    for p in posts:
        for s in p['similar']:
            if s['score'] >= 0.4:
                key = tuple(sorted((p['id'], s['id'])))
                pairs[key] = max(pairs.get(key, 0), s['score'])
    adj = collections.defaultdict(set)
    for (x, y), sc in pairs.items():
        adj[x].add(y)
        adj[y].add(x)
    seen, comps = set(), []
    for n in sorted(adj):
        if n in seen:
            continue
        stack, comp = [n], set()
        while stack:
            c = stack.pop()
            if c in comp:
                continue
            comp.add(c)
            stack.extend(adj[c] - comp)
        seen |= comp
        comps.append(sorted(comp))
    titles = {p['id']: p['title'] for p in posts}
    res['similarity'] = {
        'threshold': 0.4,
        'sample_posts_with_top_similar_ge_0_4': sum(1 for p in posts if p['similar'] and p['similar'][0]['score'] >= 0.4),
        'sample_posts_with_top_similar_ge_0_5': sum(1 for p in posts if p['similar'] and p['similar'][0]['score'] >= 0.5),
        'pairs_inside_or_crossing_sample_ge_0_4': len(pairs),
        'connected_components': [{'ids': c, 'size': len(c), 'in_sample': [i for i in c if i in ids],
                                  'titles': [titles.get(i, '(outside sample)') for i in c[:6]]} for c in sorted(comps, key=len, reverse=True)[:40]],
        'method': 'title tokens + H2/H3 tokens + bigrams, IDF-weighted, ascii-folded; advisory only',
    }

    # ---- slug defect (site-wide, outside the sample but material for the factory)
    rows = list(csv.DictReader(open('data/content-matrix.csv', encoding='utf-8', newline='')))
    c = collections.Counter()
    ex = []
    for r in rows:
        if r['status'] not in ('PUBLISHED', 'PLANNED', 'EXISTING'):
            continue
        has_d = 'đ' in r['title'].lower()
        c['rows_' + r['status']] += 1
        if has_d:
            c['title_has_d_' + r['status']] += 1
            if r['slug'] == slug_without_d_fix(r['title']):
                c['slug_drops_d_' + r['status']] += 1
                if r['status'] == 'PUBLISHED' and len(ex) < 8:
                    ex.append({'id': r['id'], 'title': r['title'], 'slug': r['slug'], 'expected_url': r['expected_url']})
    res['slug_defect_dropped_d'] = {
        'counts': dict(c), 'examples': ex,
        'root_cause': 'slugify() in scripts/factory/refill-queue.py:82 and scripts/factory/generate-matrix.py:62 call norm(), which NFD-decomposes '
                      'and strips combining marks, then deletes every character outside [a-z0-9 ]. The Vietnamese letter "đ" (U+0111) has no '
                      'decomposition, so it is DELETED instead of being mapped to "d" (e.g. "điện" -> "ien", "đạp" -> "ap").',
        'scope_note': 'Outside the 300-post sample (legacy slugs are hand-made) but it affects the factory output and therefore any URL-level '
                      'SEO/AEO work. NOT changed here (no URL/redirect changes in this phase).',
    }
    # ---- rendered evidence: posts + pages (needs extract_rendered.py output)
    rp_path, rpg_path = out / 'rendered-first300.json', out / 'rendered-pages.json'
    if rp_path.is_file() and rpg_path.is_file():
        rposts = json.loads(rp_path.read_text(encoding='utf-8'))
        rpages = json.loads(rpg_path.read_text(encoding='utf-8'))
        pg_meta = {x['page_id']: x for x in json.loads((out / 'pages-extract.json').read_text(encoding='utf-8'))}
        def region_stat(key):
            vals = [(r.get('links_by_region') or {}).get(key, 0) for r in rposts]
            return {'min': min(vals), 'max': max(vals), 'posts_with_zero': sum(1 for v in vals if v == 0)}
        res['rendered_posts'] = {
            'n': len(rposts),
            'jsonld_all_valid': sum(1 for r in rposts if r['jsonld_all_valid']),
            'jsonld_has_faqpage': sum(1 for r in rposts if r['jsonld_has_faqpage']),
            'jsonld_types_union': sorted({t for r in rposts for t in r['jsonld_types']}),
            'breadcrumb_list_jsonld_exactly_one': sum(1 for r in rposts if r['breadcrumb_list_count'] == 1),
            'breadcrumb_null_names': sum(1 for r in rposts for b in r['jsonld_blocks'] if b.get('breadcrumb', {}).get('null_or_empty_names')),
            'blogposting_missing_image': sum(1 for r in rposts for b in r['jsonld_blocks'] if 'blogposting' in b and not b['blogposting']['image']),
            'blogposting_missing_mainEntityOfPage': sum(1 for r in rposts for b in r['jsonld_blocks'] if 'blogposting' in b and not b['blogposting']['mainEntityOfPage']),
            'blogposting_missing_inLanguage': sum(1 for r in rposts for b in r['jsonld_blocks'] if 'blogposting' in b and not b['blogposting']['inLanguage']),
            'dateModified_equals_datePublished': sum(1 for r in rposts for b in r['jsonld_blocks'] if 'blogposting_values' in b and b['blogposting_values']['dateModified'] == b['blogposting_values']['datePublished']),
            'localbusiness_priceRange_values': sorted({b.get('localbusiness_priceRange') for r in rposts for b in r['jsonld_blocks'] if b.get('localbusiness_priceRange')}),
            'title_h1_mismatch': [r['id'] for r in rposts if not r['h1'] or r['h1'][0] != (r['title'] or '').rsplit(' - ', 1)[0]],
            'h1_count_not_one': [r['id'] for r in rposts if len(r['h1']) != 1],
            'canonical_mismatch': [r['id'] for r in rposts if (r['canonical'] or '') != next(p['canonical_url'] for p in posts if p['id'] == r['id'])],
            'robots_meta_present': sum(1 for r in rposts if r['robots']),
            'details_faq_visible': sum(1 for r in rposts if r['faq']['details_outside_toc']),
            'faq_like_headings_visible': sum(1 for r in rposts if r['faq']['faq_like_headings']),
            'two_breadcrumb_navs': sum(1 for r in rposts if (r.get('links_by_region') or {}).get('breadcrumb', 0) > 5),
            'links_by_region': {k: region_stat(k) for k in ('breadcrumb', 'related', 'prev_next', 'cta', 'article_body')},
            'toc_present': sum(1 for r in rposts if r.get('toc_entries', 0) > 0),
        }
        pages_res = {
            'n': len(rpages),
            'jsonld_all_valid': sum(1 for r in rpages if r['jsonld_all_valid']),
            'jsonld_has_faqpage': sum(1 for r in rpages if r['jsonld_has_faqpage']),
            'breadcrumb_list_jsonld': sum(1 for r in rpages if r['breadcrumb_list_count']),
            'pages_with_visible_faq_heading': [r['page_id'] for r in rpages if r['faq']['faq_like_headings']],
            'pages_not_h1_equal_title_prefix': [r['page_id'] for r in rpages if not r['h1'] or not (r['title'] or '').startswith(r['h1'][0])],
            'duplicate_meta_descriptions': [{'description': d[:100], 'pages': [r['page_id'] for r in rpages if r['meta_description'] == d]}
                                            for d, n in collections.Counter(r['meta_description'] for r in rpages).items() if n > 1],
        }
        if a.text_dir:
            dup_lead, editorial = [], collections.defaultdict(list)
            for r in rpages:
                t = pathlib.Path(a.text_dir, r['page_id'] + '.txt').read_text(encoding='utf-8')
                d = (r['meta_description'] or '').strip()
                if d and t.count(d) >= 2:
                    dup_lead.append(r['page_id'])
                ed = sum(len(re.findall(r'\w+', l)) for l in t.split('\n') if not l.startswith(('* ', '- ', '[...', '#')))
                editorial[pg_meta[r['page_id']]['page_type']].append(ed)
            pages_res['description_text_repeated_in_main'] = {'count': len(dup_lead), 'pages': dup_lead}
            pages_res['editorial_words_by_type'] = {k: {'n': len(v), 'median': sorted(v)[len(v) // 2], 'min': min(v), 'max': max(v)} for k, v in editorial.items()}
        res['rendered_pages'] = pages_res
    (out / 'deterministic-findings.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: (v if k in ('metadata', 'permalinks', 'slug_defect_dropped_d') else '...') for k, v in res.items()},
                     ensure_ascii=False, indent=1)[:3500])


if __name__ == '__main__':
    main()
