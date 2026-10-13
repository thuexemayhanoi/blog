#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the data-driven markdown snippets used by faq-audit-summary.md (READ-ONLY; writes data/summary-snippets.md).

  python3 reports/seo-aeo/tools/build_summary_snippets.py [--root reports/seo-aeo]

Reads data/faq-matrix.json, data/matrix-stats.json, data/deterministic-findings.json, data/faq-runin.json.
"""
import argparse
import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]


def md_table(headers, rows):
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|']
    for r in rows:
        out.append('| ' + ' | '.join(str(c).replace('|', '/').replace('\n', ' ') for c in r) + ' |')
    return '\n'.join(out)


def short(s, n=110):
    s = (s or '').strip().replace('\n', ' ')
    return s if len(s) <= n else s[:n - 1].rstrip() + '…'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='reports/seo-aeo')
    a = ap.parse_args()
    base = ROOT / a.root
    data = base / 'data'
    full = json.loads((data / 'faq-matrix.json').read_text(encoding='utf-8'))
    stats = json.loads((data / 'matrix-stats.json').read_text(encoding='utf-8'))
    det = json.loads((data / 'deterministic-findings.json').read_text(encoding='utf-8'))
    posts = [x for x in full if x['kind'] == 'Post']
    pages = [x for x in full if x['kind'] != 'Post']
    out = []

    def count(items, key, sub=None):
        c = collections.Counter()
        for x in items:
            v = x['analysis'][key]
            c[v[sub] if sub else v] += 1
        return c

    # 1) status x action tables
    def status_table(items, label):
        st = count(items, 'faq_status')
        ac = count(items, 'recommended_action')
        pr = count(items, 'priority')
        op = count(items, 'ai_search_opportunity', 'level')
        md = count(items, 'implementation_method')
        rk = count(items, 'risk', 'level')
        rows = [['FAQ status', ' ; '.join('%s: %d' % (k, st.get(k, 0)) for k in ('EXPLICIT', 'IMPLICIT', 'NONE', 'NOT_RECOMMENDED'))],
                ['Recommended action', ' ; '.join('%s: %d' % (k, ac.get(k, 0)) for k in ('KEEP', 'IMPROVE', 'ADD', 'MERGE', 'NO_FAQ'))],
                ['Priority', ' ; '.join('%s: %d' % (k, pr.get(k, 0)) for k in ('P0', 'P1', 'P2', 'P3'))],
                ['AI-search opportunity (qualitative)', ' ; '.join('%s: %d' % (k, op.get(k, 0)) for k in ('HIGH', 'MEDIUM', 'LOW'))],
                ['Risk (content/policy)', ' ; '.join('%s: %d' % (k, rk.get(k, 0)) for k in ('HIGH', 'MEDIUM', 'LOW'))],
                ['Implementation method', ' ; '.join('%s: %d' % (k, md.get(k, 0)) for k in ('TEMPLATE', 'COMPONENT', 'GENERATOR', 'CONTENT'))]]
        return '### %s (n=%d)\n\n%s\n' % (label, len(items), md_table(['Chỉ tiêu', 'Số lượng'], rows))

    out.append('## SNIPPET: status/action tables\n')
    out.append(status_table(posts, 'Bài viết'))
    out.append(status_table(pages, 'Trang chính'))
    by_type = collections.defaultdict(list)
    for x in pages:
        by_type[x['kind']].append(x)
    rows = []
    for k, items in by_type.items():
        st = count(items, 'faq_status')
        ac = count(items, 'recommended_action')
        rows.append([k, len(items), '/'.join(str(st.get(s, 0)) for s in ('EXPLICIT', 'IMPLICIT', 'NONE', 'NOT_RECOMMENDED')),
                     '/'.join(str(ac.get(s, 0)) for s in ('KEEP', 'IMPROVE', 'ADD', 'MERGE', 'NO_FAQ'))])
    out.append('### Trang chính theo loại\n\n' + md_table(['Loại', 'n', 'Explicit/Implicit/None/Not rec.', 'KEEP/IMPROVE/ADD/MERGE/NO FAQ'], rows) + '\n')

    # 2) the ten required numbers
    allx = full
    n_explicit = sum(1 for x in allx if x['analysis']['faq_status'] == 'EXPLICIT')
    n_implicit = sum(1 for x in allx if x['analysis']['faq_status'] == 'IMPLICIT')
    n_should = sum(1 for x in allx if x['analysis']['recommended_action'] in ('KEEP', 'IMPROVE', 'ADD'))
    n_add = sum(1 for x in allx if x['analysis']['recommended_action'] == 'ADD')
    n_improve = sum(1 for x in allx if x['analysis']['recommended_action'] == 'IMPROVE')
    n_not = sum(1 for x in allx if x['analysis']['recommended_action'] == 'NO_FAQ')
    n_merge = sum(1 for x in allx if x['analysis']['recommended_action'] == 'MERGE')
    out.append('## SNIPPET: required numbers\n')
    out.append(md_table(['#', 'Chỉ tiêu', 'Bài (300)', 'Trang (77)', 'Tổng (377)'], [
        [3, 'URL đã có FAQ hiển thị (EXPLICIT)', sum(1 for x in posts if x['analysis']['faq_status'] == 'EXPLICIT'), sum(1 for x in pages if x['analysis']['faq_status'] == 'EXPLICIT'), n_explicit],
        [4, 'Có nội dung trả lời nhưng chưa có FAQ (IMPLICIT)', sum(1 for x in posts if x['analysis']['faq_status'] == 'IMPLICIT'), sum(1 for x in pages if x['analysis']['faq_status'] == 'IMPLICIT'), n_implicit],
        [5, 'Nên có FAQ (KEEP + IMPROVE + ADD)', sum(1 for x in posts if x['analysis']['recommended_action'] in ('KEEP', 'IMPROVE', 'ADD')), sum(1 for x in pages if x['analysis']['recommended_action'] in ('KEEP', 'IMPROVE', 'ADD')), n_should],
        ['5a', '  trong đó cần THÊM mới (ADD)', sum(1 for x in posts if x['analysis']['recommended_action'] == 'ADD'), sum(1 for x in pages if x['analysis']['recommended_action'] == 'ADD'), n_add],
        ['5b', '  trong đó cần CẢI THIỆN FAQ đang có (IMPROVE)', sum(1 for x in posts if x['analysis']['recommended_action'] == 'IMPROVE'), sum(1 for x in pages if x['analysis']['recommended_action'] == 'IMPROVE'), n_improve],
        [6, 'Không nên có FAQ (NO FAQ)', sum(1 for x in posts if x['analysis']['recommended_action'] == 'NO_FAQ'), sum(1 for x in pages if x['analysis']['recommended_action'] == 'NO_FAQ'), n_not],
        ['6a', 'Cần GỘP/phân biệt ý định (MERGE)', sum(1 for x in posts if x['analysis']['recommended_action'] == 'MERGE'), sum(1 for x in pages if x['analysis']['recommended_action'] == 'MERGE'), n_merge],
    ]) + '\n')

    # 3) top 20
    out.append('## SNIPPET: top 20\n')
    rows = []
    for i, t in enumerate(stats['top20'], 1):
        rows.append([i, t['id'], t['priority'], t['action'].replace('_', ' '), {'EXPLICIT': 'Explicit', 'IMPLICIT': 'Implicit', 'NONE': 'None', 'NOT_RECOMMENDED': 'Not recommended'}[t['faq_status']], t['opportunity'], t['risk'], short(t['why'], 90), short(t['risk_reason'], 90)])
    out.append(md_table(['#', 'ID', 'Ưu tiên', 'Hành động', 'FAQ', 'Cơ hội', 'Rủi ro', 'Lý do cơ hội', 'Lý do rủi ro'], rows) + '\n')

    # 4) P0 list with claim evidence
    out.append('## SNIPPET: P0 list\n')
    rows = []
    for x in allx:
        r = x['analysis']
        if r['priority'] != 'P0':
            continue
        cl = r['content_assessment'].get('unverifiable_claims') or []
        rows.append([x['id'], x['kind'], r['recommended_action'].replace('_', ' '), short(r['risk']['reason'], 120),
                     '; '.join('[%s] "%s"' % (c['kind'], short(c['claim_quote'], 70)) for c in cl[:2])])
    out.append(md_table(['ID', 'Loại', 'Hành động', 'Lý do rủi ro', 'Khẳng định chưa xác minh (trích nguyên văn)'], rows) + '\n')

    # 5) existing FAQ inventory
    out.append('## SNIPPET: existing FAQ inventory\n')
    rows = []
    for x in allx:
        r = x['analysis']
        if r['faq_status'] == 'EXPLICIT':
            rows.append([x['id'], x['kind'], len(r['existing_faq']), r['faq_quality'], r['recommended_action'], r['priority'], short(r['faq_quality_notes'], 120)])
    out.append(md_table(['ID', 'Loại', '# cặp Q&A', 'Chất lượng', 'Hành động', 'Ưu tiên', 'Ghi chú'], rows) + '\n')

    # 6) implicit list
    out.append('## SNIPPET: implicit (answers exist, no FAQ)\n')
    rows = []
    for x in allx:
        r = x['analysis']
        if r['faq_status'] == 'IMPLICIT':
            rows.append([x['id'], x['kind'], r['recommended_action'], r['priority'], len(r['suggested_questions']), sum(1 for q in r['suggested_questions'] if q.get('needs_fact_check'))])
    out.append(md_table(['ID', 'Loại', 'Hành động', 'Ưu tiên', '# câu đề xuất', '# cần kiểm dữ kiện'], rows) + '\n')

    # 7) cannibalization groups + duplicate question clusters
    out.append('## SNIPPET: cannibalization groups\n')
    rows = [[len(g['ids']), g['level'], ', '.join(g['ids'][:8]), short(g['notes'], 140)] for g in sorted(stats.get('cannibalization_groups', []), key=lambda g: -len(g['ids']))[:40]]
    out.append(md_table(['# URL', 'Mức', 'IDs', 'Ghi chú'], rows) + '\n')
    dq = stats.get('duplicate_question_clusters', {})
    out.append('## SNIPPET: duplicate question clusters (count=%s)\n' % dq.get('count'))
    rows = [[c['n_urls'], ', '.join(c['urls'][:6]), ' ¦ '.join(short(q['q'], 70) for q in c['questions'][:3])] for c in dq.get('clusters', [])[:25]]
    out.append(md_table(['# URL', 'URLs', 'Ví dụ câu hỏi'], rows) + '\n')

    # 8) schema
    rp = det.get('rendered_posts', {})
    rg = det.get('rendered_pages', {})
    out.append('## SNIPPET: schema validity\n')
    out.append(md_table(['Chỉ tiêu', 'Bài (300)', 'Trang (77)'], [
        ['JSON-LD parse được (hợp lệ cú pháp)', '%s/%s' % (rp.get('jsonld_all_valid'), rp.get('n')), '%s/%s' % (rg.get('jsonld_all_valid'), rg.get('n'))],
        ['Có FAQPage JSON-LD', rp.get('jsonld_has_faqpage'), rg.get('jsonld_has_faqpage')],
        ['Có BreadcrumbList JSON-LD', rp.get('breadcrumb_list_jsonld_exactly_one'), rg.get('breadcrumb_list_jsonld')],
        ['BlogPosting thiếu image / mainEntityOfPage / inLanguage', '%s / %s / %s' % (rp.get('blogposting_missing_image'), rp.get('blogposting_missing_mainEntityOfPage'), rp.get('blogposting_missing_inLanguage')), 'n/a'],
        ['Schema FAQ "Missing" (URL nên có FAQ nhưng chưa có markup)', sum(1 for x in posts if x['row']['Schema Status'] == 'Missing'), sum(1 for x in pages if x['row']['Schema Status'] == 'Missing')],
        ['Schema FAQ "Existing / Invalid"', '0 / 0', '0 / 0'],
        ['Schema FAQ "Not applicable"', sum(1 for x in posts if x['row']['Schema Status'] == 'Not applicable'), sum(1 for x in pages if x['row']['Schema Status'] == 'Not applicable')],
    ]) + '\n')
    (data / 'summary-snippets.md').write_text('\n'.join(out), encoding='utf-8')
    print('written', data / 'summary-snippets.md', len('\n'.join(out)), 'chars')


if __name__ == '__main__':
    main()
