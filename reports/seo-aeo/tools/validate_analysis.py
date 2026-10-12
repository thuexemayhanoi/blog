#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate one agent analysis file against its batch pack (READ-ONLY).

  python3 reports/seo-aeo/tools/validate_analysis.py --batch-file <batch.json> --analysis <analysis.json> [--json]

Errors (exit 1): invalid JSON/shape, wrong ids/order, bad enumerations, quotes that are NOT found verbatim in
the source text, rule violations (status/action consistency, suggested questions without a quote, link
targets outside the allowed list, competing ids that do not exist). Warnings are style limits only.
"""
import argparse
import json
import pathlib
import re
import sys
import unicodedata

ENUM = {
    'primary_intent.type': {'INFORMATIONAL', 'COMMERCIAL', 'TRANSACTIONAL', 'LOCAL', 'NAVIGATIONAL'},
    'primary_keyword.source': {'MATRIX', 'INFERRED'},
    'answer_directness.level': {'DIRECT', 'PARTIAL', 'INDIRECT'},
    'ai_extractability.level': {'HIGH', 'MEDIUM', 'LOW'},
    'headings.level': {'GOOD', 'OK', 'WEAK'},
    'content_assessment.accuracy_risk': {'LOW', 'MEDIUM', 'HIGH'},
    'content_assessment.completeness': {'COMPLETE', 'PARTIAL', 'THIN'},
    'faq_status': {'EXPLICIT', 'IMPLICIT', 'NONE', 'NOT_RECOMMENDED'},
    'faq_quality': {'GOOD', 'FAIR', 'WEAK', 'NA'},
    'faq_duplication.risk': {'NONE', 'LOW', 'HIGH'},
    'cannibalization.level': {'NONE', 'LOW', 'MEDIUM', 'HIGH'},
    'title_meta.assessment': {'OK', 'IMPROVE'},
    'ai_search_opportunity.level': {'HIGH', 'MEDIUM', 'LOW'},
    'recommended_action': {'KEEP', 'IMPROVE', 'ADD', 'MERGE', 'NO_FAQ'},
    'priority': {'P0', 'P1', 'P2', 'P3'},
    'risk.level': {'LOW', 'MEDIUM', 'HIGH'},
    'implementation_method': {'TEMPLATE', 'COMPONENT', 'GENERATOR', 'CONTENT'},
    'confidence': {'HIGH', 'MEDIUM', 'LOW'},
}
CLAIM_KINDS = {'LEGAL', 'PRICE', 'DEPOSIT', 'STATISTIC', 'THIRD_PARTY_FACT', 'DATE', 'OTHER'}
REQUIRED = ['id', 'primary_intent', 'primary_keyword', 'semantic_entities', 'answer_directness', 'ai_extractability',
            'headings', 'content_assessment', 'faq_status', 'faq_status_reason', 'existing_faq', 'faq_quality',
            'faq_quality_notes', 'implicit_questions', 'suggested_questions', 'faq_duplication', 'schema_fit',
            'cannibalization', 'internal_links', 'title_meta', 'ai_search_opportunity', 'recommended_action',
            'priority', 'risk', 'implementation_method', 'qa_requirements', 'confidence']
LIMITS = {'primary_intent.description': 160, 'ai_extractability.reason': 200, 'headings.notes': 200,
          'content_assessment.notes': 240, 'faq_status_reason': 240, 'faq_quality_notes': 240,
          'faq_duplication.notes': 200, 'schema_fit.notes': 200, 'cannibalization.notes': 240,
          'internal_links.assessment': 200, 'title_meta.notes': 200, 'ai_search_opportunity.reason': 200,
          'risk.reason': 200, 'qa_requirements': 240}
STATUS_ACTION = {
    'NONE': {'NO_FAQ'},
    'NOT_RECOMMENDED': {'NO_FAQ', 'MERGE'},
    'EXPLICIT': {'KEEP', 'IMPROVE', 'MERGE'},
    'IMPLICIT': {'ADD', 'NO_FAQ', 'MERGE'},
}
TYPO = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-',
                      '−': '-', '…': '...', ' ': ' '})


def canon(s):
    s = unicodedata.normalize('NFC', s or '').translate(TYPO)
    s = re.sub(r'[*_`]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def source_variants(text):
    """Return two normalised renderings of the source (with / without list markers)."""
    t = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)
    t = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', t)
    t = re.sub(r'<[^>]+>', ' ', t)
    keep, strip = [], []
    for ln in t.split('\n'):
        a = re.sub(r'^\s*#{1,6}\s+', '', ln)
        a = re.sub(r'^\s*>\s?', '', a)
        a = a.replace('|', ' ')
        keep.append(a)
        b = re.sub(r'^\s*(?:[-*+]|\d+[.)])\s+', '', a)
        strip.append(b)
    return canon(' '.join(keep)), canon(' '.join(strip))


def body_of(path):
    text = pathlib.Path(path).read_text(encoding='utf-8')
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n?', text, re.S)
    return text[m.end():] if m else text


def get(d, dotted):
    cur = d
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def validate(batch, analysis, existing_ids=None):
    errors, warnings = [], []
    items = batch['items']
    recs = analysis.get('records') if isinstance(analysis, dict) else None
    if not isinstance(recs, list):
        return ['top-level "records" list missing'], []
    if analysis.get('batch') != batch['batch']:
        errors.append('batch id mismatch: %r != %r' % (analysis.get('batch'), batch['batch']))
    if [r.get('id') for r in recs] != [i['id'] for i in items]:
        errors.append('record ids/order differ from the batch: got %s expected %s' %
                      ([r.get('id') for r in recs], [i['id'] for i in items]))
    by_id = {r.get('id'): r for r in recs}
    for it in items:
        pid = it['id']
        r = by_id.get(pid)
        if r is None:
            continue
        E = lambda m: errors.append('%s: %s' % (pid, m))   # noqa: E731
        W = lambda m: warnings.append('%s: %s' % (pid, m))  # noqa: E731
        for k in REQUIRED:
            if k not in r:
                E('missing key %s' % k)
        if any(k not in r for k in REQUIRED):
            continue
        extra = sorted(set(r) - set(REQUIRED))
        if extra:
            W('unknown keys: %s' % extra)
        for path, allowed in ENUM.items():
            v = get(r, path)
            if v not in allowed:
                E('%s=%r not in %s' % (path, v, sorted(allowed)))
        for path, lim in LIMITS.items():
            v = get(r, path)
            if isinstance(v, str) and len(v) > lim * 1.5:
                W('%s too long (%d > %d)' % (path, len(v), lim))
            if not isinstance(v, str):
                E('%s must be a string' % path)
        src_path = it['source_text_path']
        text = body_of(src_path) if it.get('kind') == 'POST' else pathlib.Path(src_path).read_text(encoding='utf-8')
        sv = source_variants(text)

        def found(q):
            c = canon(q)
            return bool(c) and (c in sv[0] or c in sv[1])

        def need_quote(label, q, optional=False):
            if not isinstance(q, str):
                E('%s must be a string' % label)
                return
            if not q.strip():
                if not optional:
                    E('%s empty' % label)
                return
            if len(q.split()) > 40:
                E('%s longer than 40 words' % label)
            elif not found(q):
                E('%s NOT found verbatim in source: %r' % (label, q[:90]))

        need_quote('answer_directness.evidence_quote', r['answer_directness'].get('evidence_quote'), optional=True)
        ca = r['content_assessment']
        ucl = ca.get('unverifiable_claims')
        if not isinstance(ucl, list) or len(ucl) > 5:
            E('content_assessment.unverifiable_claims must be a list of <= 5')
        else:
            for i, c in enumerate(ucl):
                need_quote('unverifiable_claims[%d].claim_quote' % i, c.get('claim_quote'))
                if c.get('kind') not in CLAIM_KINDS:
                    E('unverifiable_claims[%d].kind invalid' % i)
        ef = r['existing_faq']
        if not isinstance(ef, list):
            E('existing_faq must be a list')
            ef = []
        for i, x in enumerate(ef):
            need_quote('existing_faq[%d].question' % i, x.get('question'))
            need_quote('existing_faq[%d].answer_quote' % i, x.get('answer_quote'))
        iq = r['implicit_questions']
        if not isinstance(iq, list) or len(iq) > 6:
            E('implicit_questions must be a list of <= 6')
            iq = []
        for i, x in enumerate(iq):
            if not isinstance(x.get('question'), str) or not x['question'].strip():
                E('implicit_questions[%d].question empty' % i)
            need_quote('implicit_questions[%d].answer_quote' % i, x.get('answer_quote'))
        sq = r['suggested_questions']
        if not isinstance(sq, list) or len(sq) > 5:
            E('suggested_questions must be a list of <= 5')
            sq = []
        for i, x in enumerate(sq):
            if not isinstance(x.get('question'), str) or not x['question'].strip():
                E('suggested_questions[%d].question empty' % i)
            src = x.get('answer_source') or {}
            need_quote('suggested_questions[%d].answer_source.quote' % i, src.get('quote'))
            if not isinstance(x.get('needs_fact_check'), bool):
                E('suggested_questions[%d].needs_fact_check must be boolean' % i)
        # consistency rules
        st, act = r['faq_status'], r['recommended_action']
        if act not in STATUS_ACTION.get(st, set()):
            E('faq_status %s is inconsistent with recommended_action %s' % (st, act))
        if st == 'EXPLICIT':
            if len(ef) < 2:
                E('EXPLICIT requires existing_faq with >= 2 pairs')
        elif ef:
            E('existing_faq must be empty unless faq_status is EXPLICIT')
        if st in ('NONE', 'NOT_RECOMMENDED') and sq:
            E('suggested_questions must be empty for %s' % st)
        if act == 'ADD' and len(sq) < 2:
            E('ADD requires >= 2 suggested_questions with source quotes')
        if st == 'EXPLICIT' and r['faq_quality'] == 'NA':
            E('EXPLICIT needs a faq_quality other than NA')
        if st != 'EXPLICIT' and r['faq_quality'] != 'NA':
            E('faq_quality must be NA unless EXPLICIT')
        fe = get(r, 'schema_fit.faqpage_eligible_now')
        if not isinstance(fe, bool):
            E('schema_fit.faqpage_eligible_now must be boolean')
        elif fe and st != 'EXPLICIT':
            E('faqpage_eligible_now=true requires faq_status EXPLICIT (visible Q&A)')
        if r['priority'] == 'P0' and not (r['risk']['level'] == 'HIGH' or act in ('IMPROVE', 'MERGE')):
            W('P0 without HIGH risk or IMPROVE/MERGE — check')
        # links / cannibalization
        il = r['internal_links']
        add = il.get('add', [])
        if not isinstance(add, list) or len(add) > 3:
            E('internal_links.add must be a list of <= 3')
            add = []
        fixes = il.get('fix', [])
        if not isinstance(fixes, list) or not all(isinstance(x, str) for x in fixes):
            E('internal_links.fix must be a list of strings')
        allowed = set(it.get('allowed_link_targets') or [])
        for i, x in enumerate(add):
            if x.get('target') not in allowed:
                E('internal_links.add[%d].target %r not in allowed_link_targets' % (i, x.get('target')))
        cb = r['cannibalization']
        for cid in cb.get('competing_ids') or []:
            ok = cid in {s['id'] for s in it.get('similar', [])} or (existing_ids is not None and cid in existing_ids)
            if not ok:
                E('cannibalization.competing_ids has unknown id %r' % cid)
        if act == 'MERGE' and not cb.get('competing_ids'):
            E('MERGE requires cannibalization.competing_ids (canonical target first)')
        if cb.get('level') in ('MEDIUM', 'HIGH') and not cb.get('competing_ids'):
            E('cannibalization level %s requires competing_ids' % cb.get('level'))
        # keyword source
        pk = r['primary_keyword']
        mk = (it.get('matrix') or {}).get('primary_keyword', '')
        if pk.get('source') == 'MATRIX' and canon(pk.get('value', '')) != canon(mk):
            E('primary_keyword.source MATRIX but value differs from the matrix row (%r)' % mk)
        if pk.get('source') == 'INFERRED' and mk and canon(mk):
            W('matrix has primary_keyword %r; INFERRED used' % mk)
        if not isinstance(pk.get('value'), str) or not pk['value'].strip() or len(pk['value'].split()) > 10:
            E('primary_keyword.value must be 1-10 words')
        if not isinstance(r['semantic_entities'], list) or not 1 <= len(r['semantic_entities']) <= 10:
            E('semantic_entities must have 1-10 items')
    return errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch-file', required=True)
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    batch = json.loads(pathlib.Path(a.batch_file).read_text(encoding='utf-8'))
    try:
        analysis = json.loads(pathlib.Path(a.analysis).read_text(encoding='utf-8'))
    except Exception as exc:  # noqa: BLE001
        print('INVALID JSON: %s' % exc)
        sys.exit(1)
    ids = None
    root = pathlib.Path(batch.get('repo_root', '.'))
    cm = root / 'data/content-matrix.csv'
    if cm.is_file():
        import csv
        ids = {r['id'] for r in csv.DictReader(open(cm, encoding='utf-8', newline=''))}
        pe = root / 'reports/seo-aeo/data/pages-extract.json'
        if pe.is_file():
            ids |= {x['page_id'] for x in json.loads(pe.read_text(encoding='utf-8'))}
    errors, warnings = validate(batch, analysis, ids)
    if a.json:
        print(json.dumps({'errors': errors, 'warnings': warnings}, ensure_ascii=False, indent=1))
    else:
        for w in warnings:
            print('WARN  ' + w)
        for e in errors:
            print('ERROR ' + e)
        print('OK' if not errors else '%d error(s)' % len(errors))
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
