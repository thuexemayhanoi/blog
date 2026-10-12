#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the analysis batches handed to the semantic-audit agents (READ-ONLY on the repo).

  python3 reports/seo-aeo/tools/build_agent_batches.py posts --size 12 --out <dir>
  python3 reports/seo-aeo/tools/build_agent_batches.py calibration --out <dir>
  python3 reports/seo-aeo/tools/build_agent_batches.py pages --size 8 --out <dir> --site <rendered _site text export>

A batch file holds one compact "pack" per item: deterministic facts (front matter, matrix row, headings,
FAQ detector signals, link counts, canonical-scorer signals, similarity candidates) plus the path of the
source text the agent must read and the list of internal link targets it may suggest.
"""
import argparse
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
DATA = ROOT / 'reports/seo-aeo/data'

PRICING = ['/bang-gia/', '/bang-gia-xe-so/', '/bang-gia-xe-ga/', '/bang-gia-xe-dien/', '/bang-gia-xe-50cc/']
STATIC = ['/lien-he/', '/gioi-thieu/']
CALIBRATION_IDS = ['BLG-00003', 'BLG-00036', 'BLG-00049', 'BLG-00001']


def fm_offset(path):
    """Number of file lines taken by the front matter (so body line + offset = file line as printed by Read)."""
    text = pathlib.Path(path).read_text(encoding='utf-8')
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n?', text, re.S)
    return m.group(0).count('\n') if m else 0


def short_headings(heads, offset=0):
    return ['H%d@L%d: %s' % (h['level'], h['line'] + offset, h['text']) for h in heads]


def post_pack(rec, faq_index, rendered=None):
    sc = rec.get('qa_scorer') or {}
    rendered = rendered or {}
    present = set()
    rl = {}
    if rendered:
        for region, key in (('breadcrumb', 'links_breadcrumb'), ('related_posts', 'links_related'),
                            ('prev_next', 'links_prev_next'), ('cta', 'links_cta')):
            rl[region] = [{'target': x['t'], 'text': x['x']} for x in rendered.get(key, [])]
            present |= {x['t'] for x in rendered.get(key, [])}
        rl['toc_entries'] = rendered.get('toc_entries', 0)
        rl['body_links'] = len(rendered.get('links_article_body', []))
    targets = []
    tx = rec['taxonomy']
    for t in (tx.get('hub_url'), tx.get('topic_url')):
        if t:
            targets.append(t)
    targets += PRICING + STATIC
    for s in rec.get('similar', [])[:5]:
        if s.get('url'):
            targets.append(s['url'])
    seen, allowed = set(), []
    for t in targets:
        if t not in seen and t not in present:
            seen.add(t)
            allowed.append(t)
    fi = (faq_index.get('per_post') or {}).get(rec['id'], {})
    off = fm_offset(ROOT / rec['file'])
    return {
        'id': rec['id'],
        'kind': 'POST',
        'source_text_path': str(ROOT / rec['file']),
        'source_note': 'markdown file; the front matter (between the first two --- lines) is NOT page text, the body is. Line numbers (L<n>) in the headings list are FILE line numbers, the same numbers the Read tool prints.',
        'canonical_url': rec['canonical_url'],
        'canonical_path': rec['canonical_path'],
        'title': rec['title'],
        'description': rec['description'],
        'categories': rec['categories'],
        'tags': rec['tags'],
        'matrix': rec['matrix'],
        'taxonomy': {k: tx.get(k) for k in ('parent_title', 'child_title', 'hub_url', 'topic_url')},
        'word_count': rec['word_count'],
        'meta': rec['meta'],
        'headings': short_headings(rec['headings'], off),
        'detector_faq_signals': {
            'faq_section_headings': rec['faq']['faq_section_headings'],
            'detected_pairs': len(rec['faq']['faq_pairs']),
            'question_form_headings': [h['text'] for h in rec['faq']['question_headings']],
            'details_blocks': rec['faq']['details_blocks'],
        },
        'links': {'body_internal_links': rec['links']['internal_count'],
                  'body_external_links': len(rec['links']['external']),
                  'inbound_links_from_other_post_bodies': rec['links']['inbound_from_posts']},
        'qa_scorer_signals_informational': {
            'non_approved_amounts': sc.get('non_approved_amounts'), 'forbidden_hits': sc.get('forbidden_hits'),
            'failed_checks': sc.get('failed_checks')},
        'similar': [{'id': s['id'], 'title': s['title'], 'url': s['url'], 'score': s['score'],
                     'same_child_cluster': s['same_child']} for s in rec.get('similar', [])[:5]],
        'site_faq_index_for_this_post': {'faq_section_headings': fi.get('faq_section_headings', []),
                                         'question_lines': (fi.get('pairs') or [])[:8]},
        'rendered_links_from_layout': rl,
        'layout_links_already_present': sorted(present),
        'allowed_link_targets': allowed,
    }


def write_batches(items, size, out, prefix):
    out.mkdir(parents=True, exist_ok=True)
    names = []
    for i in range(0, len(items), size):
        chunk = items[i:i + size]
        name = '%s%02d' % (prefix, i // size + 1)
        (out / (name + '.json')).write_text(json.dumps({
            'batch': name,
            'rubric': str(ROOT / 'reports/seo-aeo/tools/agent-rubric.md'),
            'business_facts': str(ROOT / 'data/business-facts.json'),
            'repo_root': str(ROOT),
            'items': chunk}, ensure_ascii=False, indent=1), encoding='utf-8')
        names.append((name, chunk[0]['id'], chunk[-1]['id'], len(chunk)))
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['posts', 'calibration', 'pages'])
    ap.add_argument('--size', type=int, default=12)
    ap.add_argument('--out', required=True)
    ap.add_argument('--site', help='directory with rendered text exports for pages')
    a = ap.parse_args()
    os.chdir(ROOT)
    out = pathlib.Path(a.out)
    faq_index = json.loads((DATA / 'faq-index-site.json').read_text(encoding='utf-8'))
    if a.mode in ('posts', 'calibration'):
        recs = json.loads((DATA / 'first300-extract.json').read_text(encoding='utf-8'))
        rend = {r['id']: r for r in json.loads((DATA / 'rendered-first300.json').read_text(encoding='utf-8'))}
        if a.mode == 'calibration':
            by = {r['id']: r for r in recs}
            ids = list(CALIBRATION_IDS)
            # add one legal, one Q&A-hub and one pricing-heavy post (first matching in id order)
            for pid_prefix, pred in (('legal', lambda r: r['matrix'].get('parent_id') == 'P-PHAP-LY'),
                                     ('hoidap', lambda r: r['matrix'].get('parent_id') == 'P-HOI-DAP'),
                                     ('amounts', lambda r: (r.get('qa_scorer') or {}).get('non_approved_amounts')
                                      and r['matrix'].get('parent_id') == 'P-THUE-XE')):
                for r in recs:
                    if r['id'] not in ids and pred(r):
                        ids.append(r['id'])
                        break
            items = [post_pack(by[i], faq_index, rend.get(i)) for i in ids]
            names = write_batches(items, 20, out, 'CAL')
        else:
            items = [post_pack(r, faq_index, rend.get(r['id'])) for r in recs]
            names = write_batches(items, a.size, out, 'B')
    else:
        sys.exit('pages mode is implemented in build_page_batches.py')
    for n in names:
        print(n)


if __name__ == '__main__':
    main()
