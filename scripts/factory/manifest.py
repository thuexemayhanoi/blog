#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh manifest cho một hàng ma trận - BLOG FACTORY.
Chạy: python3 scripts/factory/manifest.py --id BLG-00484
Manifest là dữ liệu bắt buộc writer phải tuân theo: parent/child/canonical/
output_path KHÔNG được tự bịa. Schema matrix TẠO MỚI (generate-matrix.py).
"""
import argparse, csv, json, sys, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--id', required=True, help='BLG-XXXXX')
    args = ap.parse_args()
    if not os.path.exists('data/content-matrix.csv'):
        print('BLOCKED: data/content-matrix.csv THIẾT — không thể khôi phục bản gốc '
              '(xem reports/factory/matrix-recovery-blocked.md).')
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
                    'intent': r['intent'],
                    'primary_keyword': r['primary_keyword'],
                    'secondary_keywords': r['secondary_keywords'].split('; ') if r['secondary_keywords'] else [],
                    'group': r['group'],
                    'parent_id': r['parent_id'],
                    'parent_hub': p['title'],
                    'parent_hub_url': p['hub_url'],
                    'child_id': r['child_id'],
                    'child_hub': c['title'],
                    'child_hub_url': c['hub_url'],
                    'output_path': r['output_path'],
                    'canonical_url': r['canonical_url'],
                    'internal_links': r['internal_links'].split('; ') if r['internal_links'] else [],
                    'commercial_target': '/bang-gia/' if c['search_intent'] == 'commercial' else None,
                    'business_fact_policy': {
                        'source': 'data/business-facts.json',
                        'rules': biz.get('content_rules', biz),
                    },
                    'source_requirement': {
                        'required': r['source_required'] == 'true',
                        'legal_risk': r['legal_risk'],
                        'format': 'CLAIM -> SUBJECT -> CONDITION -> QUY ĐỊNH HIỆN HÀNH -> PHIÊN BẢN CÓ HIỆU LỰC -> NGUỒN CHÍNH THỨC' if r['source_required'] == 'true' else 'NOT_REQUIRED',
                    },
                    'notes': 'URL dự kiến chứa {date}: chốt ngày thật khi promote qua publish-gate.py.',
                }, ensure_ascii=False, indent=2))
                return
    sys.exit('Không tìm thấy %s trong data/content-matrix.csv' % args.id)

if __name__ == '__main__':
    main()
