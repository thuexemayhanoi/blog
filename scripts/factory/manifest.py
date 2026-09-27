#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh manifest cho một hàng ma trận - BLOG FACTORY.
Chạy: python3 scripts/factory/manifest.py --id BLG-00484
Manifest là dữ liệu bắt buộc writer phải tuân theo: category/parent/child/
canonical/output_path KHÔNG được tự bịa.
"""
import argparse, csv, json, sys, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True, help='BLG-XXXXX')
    args = ap.parse_args()
    if not os.path.exists('data/content-matrix.csv'):
        print('BLOCKED: data/content-matrix.csv THIẾT — chưa từng được commit, không thể khôi phục '
              '(xem reports/factory/matrix-recovery-blocked.md). Không sinh manifest cho hàng PLANNED.')
        sys.exit(2)
    tax = json.load(open('data/content-taxonomy.json', encoding='utf-8'))
    parents = {p['parent_id']: p for p in tax['parents']}
    children = {c['child_id']: c for c in tax['children']}
    biz = json.load(open('data/business-facts.json', encoding='utf-8'))
    with open('data/content-matrix.csv', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            if r['id'] == args.id:
                p, c = parents[r['parent_id']], children[r['child_id']]
                print(json.dumps({
                    'article_id': r['id'],
                    'status': r['status'],
                    'title': r['title'],
                    'primary_keyword': r['primary_keyword'],
                    'secondary_keywords': r['secondary_keywords'].split('|') if r['secondary_keywords'] else [],
                    'search_intent': r['search_intent'],
                    'parent_id': r['parent_id'],
                    'parent_hub': p['title'],
                    'parent_hub_url': p['hub_url'],
                    'child_id': r['child_id'],
                    'child_hub': c['title'],
                    'child_hub_url': c['hub_url'],
                    'audience': r['audience'],
                    'location_scope': r['location_scope'],
                    'output_path': r['output_path'],
                    'source_path': r['source_path'],
                    'canonical_url': r['canonical_url'],
                    'breadcrumb_path': r['breadcrumb_path'],
                    'internal_links': r['internal_links'].split('|') if r['internal_links'] else [],
                    'commercial_target': '/bang-gia/' if r['commercial_intent'] in ('high', 'medium') else None,
                    'business_fact_policy': {
                        'source': 'data/business-facts.json',
                        'rules': biz['content_rules'],
                    },
                    'source_requirement': r['source_required'],
                    'legal_requirement': {
                        'legal_risk': r['legal_risk'],
                        'format': 'CLAIM -> SUBJECT -> CONDITION -> CURRENT RULE -> EFFECTIVE VERSION -> PRIMARY SOURCE' if r['source_required'] else 'NOT_REQUIRED',
                    },
                    'word_target': int(r['word_target']),
                    'batch_id': r['batch_id'],
                    'cannibalization_key': r['cannibalization_key'],
                    'notes': r['notes'],
                }, ensure_ascii=False, indent=2))
                return
    sys.exit('Không tìm thấy %s trong data/content-matrix.csv' % args.id)

if __name__ == '__main__':
    main()
