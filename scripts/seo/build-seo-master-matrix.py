#!/usr/bin/env python3
"""MASTER_SEO_MATRIX.csv — một hàng cho mỗi URL thật của site (32 cột theo lệnh SEO Autopilot 2026-11-17 + cột bổ sung).

CHỈ ĐỌC nguồn; chỉ ghi reports/factory/seo-master/MASTER_SEO_MATRIX.csv (+ .xlsx khi có --xlsx) và
reports/factory/seo-master/autopilot/matrix-summary.json. Không gọi mạng. Cùng đầu vào -> cùng byte đầu ra.

Nguồn (không nguồn nào bị suy đoán thay):
  url-inventory.csv           kiểm kê sẵn có (build-inventory.py + enrich-inventory.py): loại trang, intent, từ khóa, số từ, heading, liên kết
  --site <_site>              HTML đã build: <title>, meta description, canonical, robots, H1, JSON-LD (kiểm parse), ảnh/ALT, liên kết nội bộ hỏng
  data/content-matrix.csv     hàng factory (secondary_keywords, legal_risk)
  data/qa/<ID>.json           evidence QA: result, quality/seo, nguyên vẹn hash hay lệch (INTACT / HASH_DRIFT / LEGACY)
  gsc/gsc-snapshot.json + CSV dữ liệu Google Search Console thật (import-gsc-snapshot.py); URL không có hàng -> NO_GSC_DATA
  slug-redirect-registry.csv  URL cũ (đ->d) của bài; số liệu GSC của URL cũ ghi ở cột riêng, KHÔNG cộng lẫn vào URL mới
  content-fix-blocked.csv, legal-verification.csv, _data/legal-notices.json, _data/price-notices.json, _data/post-modified.json
  autopilot/batch-log.csv     kết quả từng lô autopilot (nếu có): ghi đè phân loại/trạng thái/QA/commit cho URL đã xử lý
  autopilot/index-inspection.csv  mẫu URL Inspection của Search Console (nếu có)

Quy tắc phân loại (cột classification, ưu tiên từ trên xuống; nhãn INFERRED trừ khi ghi FACT):
  TECHNICAL_FIX   lỗi kỹ thuật đo được trên HTML build: noindex ngoài ý muốn, canonical không tự trỏ, H1 != 1, JSON-LD không parse,
                  liên kết nội bộ hỏng, thiếu meta description, URL nội dung không có trong sitemap (FACT)
  BLOCKED         bài nằm trong content-fix-blocked.csv, hoặc cần sửa nội dung nhưng evidence lệch hash (chỉ sửa qua reattest có chủ duyệt)
  LEGAL_REVIEW    legal_risk=high + nội dung có cả số tiền và từ ngữ pháp lý (staleness HIGH) + chưa có trong legal-verification.csv
                  và chưa có lớp đính chính
  OPTIMIZE        GSC: vị trí trung bình 5-20 và >= 100 lượt hiển thị (cộng URL cũ + URL mới của cùng bài) — "striking distance"
  CONTENT_UPGRADE GSC: >= 100 lượt hiển thị nhưng vị trí > 20; hoặc < 800 từ
  DUPLICATE_REVIEW cùng cannibalization_key với bài khác (SUPPORT/NEAR_TITLE) hoặc chia sẻ >= 3 truy vấn GSC có hiển thị với bài khác
  KEEP            không phát hiện vấn đề nào ở trên (KHÔNG có nghĩa bài kém hay tốt — chỉ là chưa có tín hiệu cần sửa)
  QA_PASS         (từ batch-log) đã sửa qua công cụ chính thức và verify PASS
"""
import argparse
import csv
import glob
import io
import json
import os
import re
import sys
import urllib.parse
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SM = os.path.join(ROOT, 'reports', 'factory', 'seo-master')
AP = os.path.join(SM, 'autopilot')
BASE = 'https://blog.thuexemaynguyentu.com'

COLUMNS = [
    # 32 cột của lệnh SEO Autopilot (thứ tự giữ nguyên)
    'url', 'content_id', 'category', 'primary_keyword', 'secondary_keywords', 'search_intent', 'title', 'meta_description',
    'h1', 'word_count', 'content_quality_findings', 'internal_links', 'broken_links', 'image_alt', 'canonical', 'indexability',
    'schema', 'sitemap_status', 'gsc_clicks', 'gsc_impressions', 'gsc_ctr', 'gsc_avg_position', 'data_source', 'data_freshness',
    'priority', 'issue', 'proposed_fix', 'execution_status', 'qa_result', 'commit_sha', 'date_updated', 'next_action',
    # bổ sung
    'classification', 'page_type', 'matrix_status', 'evidence_state', 'legal_risk', 'gsc_old_url', 'gsc_old_clicks',
    'gsc_old_impressions', 'gsc_old_position', 'gsc_old_impressions_last7d', 'gsc_top_queries', 'gsc_query_overlap',
    'gsc_index_status_sample', 'batch_id',
]

RX_TITLE = re.compile(r'<title>(.*?)</title>', re.S)
RX_META = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"')
RX_CANON = re.compile(r'<link\s+rel="canonical"\s+href="([^"]*)"')
RX_ROBOTS = re.compile(r'<meta\s+name="robots"\s+content="([^"]*)"')
RX_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
RX_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)
RX_TAG = re.compile(r'<[^>]+>')
RX_HREF = re.compile(r'<a\s[^>]*?href="([^"]+)"')
RX_IMG = re.compile(r'<img\s[^>]*>')
RX_ALT = re.compile(r'\balt="([^"]*)"')


def rd(path):
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def text(s):
    return re.sub(r'\s+', ' ', unescape(RX_TAG.sub('', s))).strip()


def ld_types(obj, out):
    if isinstance(obj, dict):
        t = obj.get('@type')
        if isinstance(t, str):
            out.add(t)
        elif isinstance(t, list):
            out.update(x for x in t if isinstance(x, str))
        for k in ('@graph',):
            if k in obj:
                ld_types(obj[k], out)
    elif isinstance(obj, list):
        for x in obj:
            ld_types(x, out)


def built_paths(site):
    paths = set()
    for dp, _, fns in os.walk(site):
        rel = '/' + os.path.relpath(dp, site).replace(os.sep, '/').lstrip('.').lstrip('/')
        rel = rel if rel.endswith('/') else rel + '/'
        if rel == '//':
            rel = '/'
        for fn in fns:
            paths.add((rel + fn) if rel != '/' else '/' + fn)
            if fn == 'index.html':
                paths.add(rel)
    return paths


def page_file(site, url):
    p = url.split('#')[0]
    if p.endswith('/'):
        return os.path.join(site, p.lstrip('/'), 'index.html')
    return os.path.join(site, p.lstrip('/'))


def parse_html(site, url, paths):
    f = page_file(site, url)
    if not os.path.isfile(f):
        return None
    with open(f, encoding='utf-8', errors='replace') as fh:
        h = fh.read()
    head = h.split('</head>', 1)[0]
    main = h
    i = h.find('<main')
    if i >= 0:
        j = h.find('</main>', i)
        main = h[i:j if j > 0 else len(h)]
    r = {}
    m = RX_TITLE.search(head)
    r['title'] = text(m.group(1)) if m else ''
    m = RX_META.search(head)
    r['meta'] = unescape(m.group(1)) if m else ''
    m = RX_CANON.search(head)
    r['canonical'] = urllib.parse.unquote(m.group(1)) if m else ''
    m = RX_ROBOTS.search(head)
    r['robots'] = m.group(1) if m else ''
    h1s = RX_H1.findall(h)
    r['h1_count'] = len(h1s)
    r['h1'] = text(h1s[0]) if h1s else ''
    types, bad = set(), 0
    for blk in RX_LD.findall(h):
        try:
            ld_types(json.loads(blk), types)
        except ValueError:
            bad += 1
    r['ld_types'] = sorted(types)
    r['ld_errors'] = bad
    imgs = RX_IMG.findall(main)
    miss = 0
    for tag in imgs:
        a = RX_ALT.search(tag)
        if not a or not a.group(1).strip():
            miss += 1
    r['img'] = len(imgs)
    r['img_missing_alt'] = miss
    broken = set()
    for href in RX_HREF.findall(h):
        href = urllib.parse.unquote(unescape(href))
        if href.startswith(BASE):
            href = href[len(BASE):] or '/'
        if not href.startswith('/') or href.startswith('//'):
            continue
        p = href.split('#')[0].split('?')[0]
        if not p:
            continue
        if p not in paths and (p + '/') not in paths and not p.startswith('/cdn-cgi/'):
            broken.add(p)
    r['broken'] = sorted(broken)
    return r


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_gsc():
    snap_p = os.path.join(SM, 'gsc', 'gsc-snapshot.json')
    if not os.path.isfile(snap_p):
        return None
    with open(snap_p, encoding='utf-8') as f:
        snap = json.load(f)
    files = {x['file']: x for x in snap['files']}
    pages = [x for x in snap['files'] if x['dimensions'] == ['page'] and not x.get('compare')]
    primary = max(pages, key=lambda x: (x['period']['days'], x['period']['end']))
    out = {'snap': snap, 'primary': primary, 'pages': {}, 'last7': {}, 'pq': [], 'last7_file': None}

    def agg(rows, key='url'):
        d = {}
        for r in rows:
            u = r[key]
            c = d.setdefault(u, [0.0, 0.0, 0.0])
            c[0] += float(r['clicks'])
            c[1] += float(r['impressions'])
            c[2] += float(r['position']) * float(r['impressions'])
        return d
    out['pages'] = agg(rd(os.path.join(SM, 'gsc', primary['file'])))
    cmp_ = [x for x in snap['files'] if x['dimensions'] == ['page'] and x.get('compare')]
    if cmp_:
        last = max(cmp_, key=lambda x: x['period']['end'])
        out['last7_file'] = last
        out['last7'] = agg(rd(os.path.join(SM, 'gsc', last['file'])))
    pq = [x for x in snap['files'] if x['dimensions'] == ['page', 'query']]
    if pq:
        out['pq'] = rd(os.path.join(SM, 'gsc', max(pq, key=lambda x: x['period']['days'])['file']))
    return out


def fmt(v, nd=0):
    if v is None:
        return ''
    return ('%.' + str(nd) + 'f') % v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', required=True, help='thư mục _site đã build (jekyll build)')
    ap.add_argument('--xlsx', action='store_true', help='ghi thêm MASTER_SEO_MATRIX.xlsx (cần openpyxl)')
    a = ap.parse_args()

    inv = rd(os.path.join(SM, 'url-inventory.csv'))
    mx = {r['id']: r for r in rd(os.path.join(ROOT, 'data', 'content-matrix.csv'))}
    mx_by_url = {}
    for r in mx.values():
        mx_by_url.setdefault(r['canonical_url'], r['id'])
        mx_by_url.setdefault(r['expected_url'], r['id'])
    reg = rd(os.path.join(SM, 'slug-redirect-registry.csv'))
    reg_by_new = {r['new_url']: r for r in reg}
    blocked = {r['id']: r for r in rd(os.path.join(SM, 'content-fix-blocked.csv'))}
    legal_ver = set()
    for r in rd(os.path.join(SM, 'legal-verification.csv')):
        legal_ver.update(x.strip() for x in r['claim_post_ids'].split('|') if x.strip())
    with open(os.path.join(ROOT, '_data', 'legal-notices.json'), encoding='utf-8') as f:
        legal_notice_ids = {v.get('id') for v in json.load(f).get('posts', {}).values()}
    with open(os.path.join(ROOT, '_data', 'price-notices.json'), encoding='utf-8') as f:
        pn = json.load(f).get('posts', {})
        price_notice_ids = {k if k.startswith('BLG-') else (v.get('id') if isinstance(v, dict) else None) for k, v in pn.items()}
    with open(os.path.join(ROOT, '_data', 'post-modified.json'), encoding='utf-8') as f:
        modified = {k: v.get('modified', '') for k, v in json.load(f).get('posts', {}).items()}
    batch = {}
    bl = os.path.join(AP, 'batch-log.csv')
    if os.path.isfile(bl):
        for r in rd(bl):
            batch[r['article_id']] = r  # hàng sau ghi đè hàng trước (lô mới nhất thắng)
    inspect = {}
    ip = os.path.join(AP, 'index-inspection.csv')
    if os.path.isfile(ip):
        for r in rd(ip):
            inspect[r['url']] = r
    gsc = load_gsc()
    paths = built_paths(a.site)

    # GSC: truy vấn dùng chung giữa các bài khác nhau (URL cũ quy về bài của URL mới)
    url2id = {r['url']: (r['article_id'] or mx_by_url.get(r['url'], '')) for r in inv if r['type'] == 'Post'}
    url2id = {k: v for k, v in url2id.items() if v}
    for r in reg:
        url2id[r['old_url']] = r['article_id']
    overlap = {}
    if gsc and gsc['pq']:
        by_q = {}
        for r in gsc['pq']:
            aid = url2id.get(r['url'])
            if aid and float(r['impressions']) >= 1:
                by_q.setdefault(r['query'], set()).add(aid)
        for q, ids in by_q.items():
            if len(ids) >= 2:
                for i in ids:
                    overlap.setdefault(i, {}).setdefault(q, ids - {i})

    top_q = {}
    if gsc and gsc['pq']:
        for r in gsc['pq']:
            aid = url2id.get(r['url'])
            if aid:
                top_q.setdefault(aid, []).append((float(r['impressions']), r['query'], float(r['position'])))

    fresh = ''
    src = 'NO_GSC_DATA'
    if gsc:
        p = gsc['primary']['period']
        fresh = 'GSC %s..%s (lấy %s)' % (p['start'], p['end'], gsc['snap']['fetched_on'])
        src = 'GSC Performance (%s) %s..%s' % (gsc['snap']['connector'].split(' (')[0], p['start'], p['end'])

    rows, counts = [], {}
    for r in inv:
        url, typ = r['url'], r['type']
        aid = r['article_id'] or (mx_by_url.get(url, '') if typ == 'Post' else '')
        h = parse_html(a.site, url, paths) or {}
        m = mx.get(aid, {})
        ev_state, qa = 'N/A', ''
        if typ == 'Post':
            evp = os.path.join(ROOT, 'data', 'qa', aid + '.json')
            if os.path.isfile(evp):
                with open(evp, encoding='utf-8') as f:
                    ev = json.load(f)
                import hashlib
                src_path = os.path.join(ROOT, r['source_file'])
                with open(src_path, 'rb') as f:
                    sha = hashlib.sha256(f.read()).hexdigest()
                ev_state = 'INTACT' if sha == ev.get('content_sha256') and ev.get('source_path') == r['source_file'] else 'HASH_DRIFT'
                qa = '%s q%s/s%s %s' % (ev.get('result'), ev.get('quality'), ev.get('seo'), ev_state)
            else:
                ev_state = 'LEGACY'
                qa = 'LEGACY_NO_EVIDENCE'
        # GSC
        g = gsc['pages'].get(url) if gsc else None
        rr = reg_by_new.get(url)
        go = gsc['pages'].get(rr['old_url']) if (gsc and rr) else None
        go7 = gsc['last7'].get(rr['old_url']) if (gsc and rr) else None
        tot_i = (g[1] if g else 0) + (go[1] if go else 0)
        tot_pos = (((g[2] if g else 0) + (go[2] if go else 0)) / tot_i) if tot_i else None
        issues, findings, fixes = [], [], []
        # --- kỹ thuật (FACT, trên HTML build)
        robots = h.get('robots', '')
        canon = h.get('canonical', '')
        self_url = BASE + url
        if h:
            if 'noindex' in robots and typ not in ('Page',) and url != '/404.html':
                issues.append('NOINDEX_UNEXPECTED')
            if typ != 'RedirectStub' and canon != self_url:
                issues.append('CANONICAL_NOT_SELF')
            if h.get('h1_count') != 1:
                issues.append('H1_COUNT_%d' % h.get('h1_count', 0))
            if h.get('ld_errors'):
                issues.append('JSONLD_PARSE_ERROR')
            if h.get('broken'):
                issues.append('BROKEN_INTERNAL_LINK')
            if not h.get('meta') and typ != 'RedirectStub' and url != '/404.html':
                issues.append('META_DESCRIPTION_MISSING')
        else:
            issues.append('NOT_BUILT')
        if r['in_sitemap'] != 'True' and typ in ('Post', 'Hub', 'Pillar', 'Listing'):
            issues.append('NOT_IN_SITEMAP')
        technical = list(issues)
        # --- nội dung (INFERRED)
        words = int(r['words'] or 0)
        if typ == 'Post':
            if words and words < 800:
                findings.append('THIN_LT_800_WORDS')
            if int(r['title_len'] or 0) > 70:
                findings.append('TITLE_GT_70_CHARS(title bị khóa: chỉ đề xuất)')
            if int(r['description_len'] or 0) > 170:
                findings.append('META_GT_170_CHARS(meta bị khóa: chỉ đề xuất)')
            if r['body_internal_links'] == '0':
                findings.append('NO_BODY_INTERNAL_LINK')
            if h and h.get('img', 0) == 0:
                findings.append('NO_CONTENT_IMAGE')
            if r['staleness_risk'] == 'HIGH':
                findings.append('FRESHNESS_REVIEW_HIGH')
            if aid in legal_notice_ids:
                findings.append('HAS_LEGAL_NOTICE_LAYER')
            if aid in price_notice_ids:
                findings.append('HAS_PRICE_NOTICE_LAYER')
            if r['cannibalization_role']:
                findings.append('CANNIBALIZATION_' + r['cannibalization_role'])
        ov = overlap.get(aid, {})
        if len(ov) >= 3:
            issues.append('GSC_QUERY_OVERLAP')
        if go and go[1] > 0:
            issues.append('OLD_URL_404_STILL_IN_GOOGLE')
        # --- phân loại
        cls = 'KEEP'
        striking = tot_pos is not None and 5 <= tot_pos <= 20 and tot_i >= 100
        weak = tot_pos is not None and tot_pos > 20 and tot_i >= 100
        if typ == 'Home':
            cls = 'KEEP'
            findings.append('FROZEN_HOMEPAGE')
        elif typ == 'RedirectStub' or url == '/404.html':
            cls = 'KEEP'
        elif technical:
            cls = 'TECHNICAL_FIX'
        elif typ == 'Post':
            if aid in blocked:
                cls = 'BLOCKED'
                issues.append('CONTENT_FIX_BLOCKED:' + blocked[aid]['blocked_reason'].split(' ')[0])
            elif (striking or weak) and ev_state == 'HASH_DRIFT':
                cls = 'BLOCKED'
                issues.append('EVIDENCE_HASH_DRIFT_EDIT_LOCKED')
            elif (m.get('legal_risk') == 'high' and r['staleness_risk'] == 'HIGH' and aid not in legal_ver
                  and aid not in legal_notice_ids):
                cls = 'LEGAL_REVIEW'
                issues.append('LEGAL_CLAIMS_UNVERIFIED')
            elif striking:
                cls = 'OPTIMIZE'
                issues.append('GSC_STRIKING_DISTANCE_5_20')
            elif weak or 'THIN_LT_800_WORDS' in findings:
                cls = 'CONTENT_UPGRADE'
                issues.append('GSC_IMPRESSIONS_POS_GT_20' if weak else 'THIN_CONTENT')
            elif r['cannibalization_role'] in ('SUPPORT', 'NEAR_TITLE') or len(ov) >= 3:
                cls = 'DUPLICATE_REVIEW'
                if r['cannibalization_role']:
                    issues.append('CANNIBALIZATION_' + r['cannibalization_role'])
        # batch-log ghi đè
        b = batch.get(aid) if aid else None
        exec_status, commit, batch_id, next_action = '', '', '', ''
        if b:
            batch_id = b['batch_id']
            commit = b.get('commit_sha', '')
            if b.get('classification'):
                cls = b['classification']
            exec_status = b.get('execution_status', '')
            if b.get('qa_result'):
                qa = b['qa_result'] + ' | ' + qa
            if b.get('proposed_fix'):
                fixes.append(b['proposed_fix'])
            next_action = b.get('next_action', '')
        # ưu tiên
        if 'NOINDEX_UNEXPECTED' in issues or 'CANONICAL_NOT_SELF' in issues or 'NOT_IN_SITEMAP' in issues or 'NOT_BUILT' in issues:
            pri = 'P0'
        elif technical or striking or (go and go[1] >= 100):
            pri = 'P1'
        elif cls in ('LEGAL_REVIEW', 'BLOCKED') or tot_i >= 30:
            pri = 'P2'
        elif cls != 'KEEP' or issues:
            pri = 'P3'
        else:
            pri = 'P4'
        default_fix = {
            'TECHNICAL_FIX': 'Sửa nguyên nhân ở template/nguồn (không sửa tay _site), build lại, check-regressions + check-built-links',
            'BLOCKED': 'Chờ chủ duyệt: reattest-legacy-qa.py apply (hoặc --domain-drift) rồi revise-published.py; trong lúc chờ giữ lớp đính chính',
            'LEGAL_REVIEW': 'Đối chiếu văn bản chính thức còn hiệu lực (SOURCE-RESEARCH lớp C); sai thì sửa qua revise-published.py hoặc lớp legal-notice',
            'OPTIMIZE': 'Sửa nhẹ thân bài theo truy vấn GSC thật: đoạn mở đầu trả lời thẳng, bổ sung thông tin đã kiểm chứng; KHÔNG đổi title/meta/URL',
            'CONTENT_UPGRADE': 'Rà intent theo truy vấn GSC; bổ sung nội dung còn thiếu đã kiểm chứng (revise-published, <= 20% bài)',
            'DUPLICATE_REVIEW': 'Xác định URL chủ lực theo intent; phân biệt góc/ liên kết hai chiều; không gộp/redirect khi chưa có chủ duyệt',
            'KEEP': '',
            'QA_PASS': '',
        }
        if not fixes and default_fix.get(cls):
            fixes.append(default_fix[cls])
        if not exec_status:
            exec_status = {'KEEP': 'MONITORING', 'BLOCKED': 'BLOCKED', 'QA_PASS': 'QA_PASS'}.get(cls, 'TODO')
            if 'FROZEN_HOMEPAGE' in findings:
                exec_status = 'MONITORING'
        if not next_action:
            next_action = {
                'TECHNICAL_FIX': 'Lô kỹ thuật kế tiếp', 'BLOCKED': 'OWNER_REVIEW', 'LEGAL_REVIEW': 'Lô pháp lý (ưu tiên theo GSC)',
                'OPTIMIZE': 'Lô OPTIMIZE theo thứ tự lượt hiển thị GSC', 'CONTENT_UPGRADE': 'Lô CONTENT_UPGRADE',
                'DUPLICATE_REVIEW': 'Rà nhóm cannibalization', 'KEEP': 'Theo dõi GSC 28 ngày', 'QA_PASS': 'Chờ deploy + đo GSC sau 28 ngày',
            }.get(cls, '')
        # cột hiển thị
        h1 = h.get('h1', '')
        title_src = r['title']
        cat = r['child_title'] or typ
        tq = sorted(top_q.get(aid, []), reverse=True)[:3] if aid else []
        row = {
            'url': url,
            'content_id': aid,
            'category': cat,
            'primary_keyword': r['primary_keyword'],
            'secondary_keywords': r['secondary_keywords'] or m.get('secondary_keywords', ''),
            'search_intent': r['search_intent'],
            'title': h.get('title', ''),
            'meta_description': h.get('meta', ''),
            'h1': '=TITLE' if (h1 and h1 == title_src) else h1,
            'word_count': r['words'],
            'content_quality_findings': ';'.join(findings),
            'internal_links': 'body=%s inbound=%s' % (r['body_internal_links'] or '0', r['inbound_links_html'] or '0'),
            'broken_links': str(len(h.get('broken', []))) + ((':' + ' '.join(h['broken'][:3])) if h.get('broken') else ''),
            'image_alt': ('NO_CONTENT_IMAGES' if h and h.get('img', 0) == 0 else
                          '%d img, %d thiếu ALT' % (h.get('img', 0), h.get('img_missing_alt', 0)) if h else ''),
            'canonical': 'SELF' if canon == self_url else canon,
            'indexability': ('NOINDEX' if 'noindex' in robots else 'INDEXABLE') if h else 'NOT_BUILT',
            'schema': '|'.join(h.get('ld_types', [])) + (' (LỖI JSON)' if h.get('ld_errors') else ''),
            'sitemap_status': 'IN_SITEMAP' if r['in_sitemap'] == 'True' else 'NOT_IN_SITEMAP',
            'gsc_clicks': fmt(g[0]) if g else 'NO_GSC_DATA',
            'gsc_impressions': fmt(g[1]) if g else 'NO_GSC_DATA',
            'gsc_ctr': fmt(100 * g[0] / g[1], 2) + '%' if g and g[1] else 'NO_GSC_DATA',
            'gsc_avg_position': fmt(g[2] / g[1], 2) if g and g[1] else 'NO_GSC_DATA',
            'data_source': src if g else ('NO_GSC_DATA: property có dữ liệu, URL không có hàng nào trong kỳ' if gsc else 'NO_GSC_DATA'),
            'data_freshness': fresh,
            'priority': pri,
            'issue': ';'.join(dict.fromkeys(issues)),
            'proposed_fix': ' | '.join(fixes),
            'execution_status': exec_status,
            'qa_result': qa,
            'commit_sha': commit,
            'date_updated': (modified.get(aid, '')[:10] if aid else '') or r['date'],
            'next_action': next_action,
            'classification': cls,
            'page_type': typ,
            'matrix_status': r['matrix_status'],
            'evidence_state': ev_state,
            'legal_risk': m.get('legal_risk', ''),
            'gsc_old_url': rr['old_url'] if rr else '',
            'gsc_old_clicks': fmt(go[0]) if go else '',
            'gsc_old_impressions': fmt(go[1]) if go else '',
            'gsc_old_position': fmt(go[2] / go[1], 2) if go and go[1] else '',
            'gsc_old_impressions_last7d': fmt(go7[1]) if go7 else '',
            'gsc_top_queries': ' | '.join('%s (%d, %.1f)' % (q, i, p) for i, q, p in tq),
            'gsc_query_overlap': ('%d truy vấn chung; vd %s' % (len(ov), ', '.join(sorted({x for s in ov.values() for x in s})[:3]))) if ov else '',
            'gsc_index_status_sample': inspect.get(url, {}).get('coverage_state', ''),
            'batch_id': batch_id,
        }
        rows.append(row)
        counts.setdefault('classification', {}).setdefault(cls, 0)
        counts['classification'][cls] += 1
        counts.setdefault('priority', {}).setdefault(pri, 0)
        counts['priority'][pri] += 1
        for code in dict.fromkeys(issues):
            k = code.split(':')[0]
            counts.setdefault('issues', {}).setdefault(k, 0)
            counts['issues'][k] += 1
        for code in findings:
            k = code.split('(')[0]
            counts.setdefault('findings', {}).setdefault(k, 0)
            counts['findings'][k] += 1
        counts.setdefault('page_type', {}).setdefault(typ, 0)
        counts['page_type'][typ] += 1
        counts.setdefault('execution_status', {}).setdefault(exec_status, 0)
        counts['execution_status'][exec_status] += 1

    rows.sort(key=lambda x: (x['priority'], -float(x['gsc_impressions']) if x['gsc_impressions'] not in ('NO_GSC_DATA', '') else 1, x['url']))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    out_csv = os.path.join(SM, 'MASTER_SEO_MATRIX.csv')
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        f.write(buf.getvalue())
    os.makedirs(AP, exist_ok=True)
    with_gsc = sum(1 for x in rows if x['gsc_impressions'] != 'NO_GSC_DATA')
    summary = {
        'schema': 'seo-master-matrix-summary/1',
        'urls': len(rows),
        'posts': counts['page_type'].get('Post', 0),
        'urls_with_gsc_rows': with_gsc,
        'urls_no_gsc_data': len(rows) - with_gsc,
        'gsc_window': fresh,
        'counts': {k: dict(sorted(v.items())) for k, v in sorted(counts.items())},
    }
    with open(os.path.join(AP, 'matrix-summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')
    if a.xlsx:
        write_xlsx(rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def write_xlsx(rows, summary):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = 'Tổng quan'
    ws.append(['MASTER SEO MATRIX — blog.thuexemaynguyentu.com'])
    ws['A1'].font = Font(bold=True, size=14)
    ws.append(['Nguồn GSC', summary['gsc_window']])
    ws.append(['Tổng URL', summary['urls']])
    ws.append(['Bài (Post)', summary['posts']])
    ws.append(['URL có dữ liệu GSC', summary['urls_with_gsc_rows']])
    ws.append(['URL NO_GSC_DATA', summary['urls_no_gsc_data']])
    for sec in ('classification', 'priority', 'execution_status', 'issues', 'findings', 'page_type'):
        ws.append([])
        ws.append([sec.upper()])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        for k, v in summary['counts'].get(sec, {}).items():
            ws.append([k, v])
    ws.column_dimensions['A'].width = 48
    ws.column_dimensions['B'].width = 40
    m = wb.create_sheet('Matrix')
    m.append(COLUMNS)
    for c in range(1, len(COLUMNS) + 1):
        cell = m.cell(row=1, column=c)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1F4E78')
        cell.alignment = Alignment(wrap_text=True, vertical='top')
    numeric = {'word_count', 'gsc_clicks', 'gsc_impressions', 'gsc_avg_position', 'gsc_old_clicks', 'gsc_old_impressions',
               'gsc_old_position', 'gsc_old_impressions_last7d'}
    for r in rows:
        vals = []
        for k in COLUMNS:
            v = r[k]
            if k in numeric and v not in ('', 'NO_GSC_DATA'):
                try:
                    v = float(v) if '.' in v else int(v)
                except ValueError:
                    pass
            vals.append(v)
        m.append(vals)
    m.freeze_panes = 'B2'
    m.auto_filter.ref = 'A1:%s%d' % (get_column_letter(len(COLUMNS)), len(rows) + 1)
    widths = {'url': 60, 'title': 50, 'meta_description': 50, 'h1': 30, 'issue': 40, 'proposed_fix': 50, 'content_quality_findings': 40,
              'search_intent': 40, 'secondary_keywords': 30, 'primary_keyword': 25, 'gsc_top_queries': 50}
    for i, k in enumerate(COLUMNS, 1):
        m.column_dimensions[get_column_letter(i)].width = widths.get(k, 14)
    bl = os.path.join(AP, 'batch-log.csv')
    if os.path.isfile(bl):
        s = wb.create_sheet('Batch log')
        rr = rd(bl)
        if rr:
            s.append(list(rr[0].keys()))
            for r in rr:
                s.append(list(r.values()))
    iss = os.path.join(SM, 'SEO_ISSUES.csv')
    if os.path.isfile(iss):
        s = wb.create_sheet('Issues')
        rr = rd(iss)
        if rr:
            s.append(list(rr[0].keys()))
            for r in rr:
                s.append(list(r.values()))
    wb.save(os.path.join(SM, 'MASTER_SEO_MATRIX.xlsx'))


if __name__ == '__main__':
    sys.exit(main())
