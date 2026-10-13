#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic, READ-ONLY extraction for the SEO / AEO / GEO FAQ audit.

Reads the repository working tree (matrix, _posts, _data, _layouts) and a snapshot of the live
sitemap; writes JSON under reports/seo-aeo/data/. It never writes anywhere else, never calls the
network, and never touches posts, evidence, matrix or state.

  python3 reports/seo-aeo/tools/extract_audit_data.py --sitemap <live_sitemap_locs.txt> --out reports/seo-aeo/data

Outputs
  sample-first300.json     the exact sample (ids, urls, status) + the alternative (factory-only) sample
  first300-extract.json    one object per sample post: front matter, headings, FAQ signals, links,
                           JSON-LD validity simulation, canonical QA scorer signals, cannibalization
                           candidates, inbound-link counts
  pages-extract.json       one object per main page (home, hubs, categories, topic pages, static pages)
  extract-summary.json     counts used by the summary report
"""
import argparse
import collections
import csv
import importlib.util
import json
import math
import os
import pathlib
import re
import sys
import unicodedata
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[3]
SITE = 'https://blog.thuexemaynguyentu.com'
SITE_TITLE = 'Thuê Xe Máy Hà Nội Nguyễn Tú'

FAQ_HEAD = re.compile(
    r'(câu hỏi thường gặp|câu hỏi|hỏi đáp|hỏi nhanh|\bfaq\b|q&a|q & a|thắc mắc|giải đáp|những câu hỏi)', re.I)
QUESTION_START = re.compile(
    r'^(tại sao|vì sao|làm sao|làm thế nào|làm gì|có nên|có cần|có thể|có được|có phải|có nào|bao nhiêu|bao lâu|'
    r'khi nào|lúc nào|ở đâu|nên |thế nào|như thế nào|ai |cái nào|loại nào|xe nào|là gì|là ai|mấy |phải )', re.I)
STOP = set('''và của cho là các một những được với trong khi để có không này đó như thì ở tại từ hay hoặc cũng
đã sẽ đang bị bởi theo về trên dưới sau trước nên cần rất lại còn nhưng nếu vì sao đi lên ra vào thế nào gì ai
the a of and to in for on at by with'''.split())


# --------------------------------------------------------------------------- helpers
def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').replace('đ', 'd').replace('Đ', 'D')


def norm_text(s):
    return re.sub(r'\s+', ' ', strip_accents(s).lower()).strip()


def tokens(s):
    return [t for t in re.findall(r'[a-z0-9]+', norm_text(s)) if t not in STOP and len(t) > 1]


def unquote_yaml(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        inner = v[1:-1]
        inner = inner.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')
        return inner
    if len(v) >= 2 and v[0] == "'" and v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def parse_list(v):
    v = v.strip()
    if v.startswith('[') and v.endswith(']'):
        return [unquote_yaml(x.strip()) for x in v[1:-1].split(',') if x.strip()]
    return [v] if v else []


def parse_front_matter(text):
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n?', text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).split('\n'):
        mm = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$', line.rstrip('\r'))
        if mm:
            fm[mm.group(1)] = mm.group(2)
    return fm, text[m.end():]


def yaml_map(path):
    """Tiny parser for the generated _data maps: `key:` then indented `k: v` lines."""
    out, cur = {}, None
    for line in pathlib.Path(path).read_text(encoding='utf-8').split('\n'):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if not line.startswith(' '):
            cur = line.split(':')[0].strip().strip('"')
            out[cur] = {}
        elif cur is not None:
            k, _, v = line.strip().partition(':')
            out[cur][k.strip()] = unquote_yaml(v)
    return out


def post_url_path(fm, matrix_row):
    if matrix_row and matrix_row.get('expected_url'):
        return matrix_row['expected_url']
    return unquote_yaml(fm.get('permalink', ''))


def norm_path(p):
    p = urllib.parse.unquote(p.split('#')[0].split('?')[0])
    if not p.startswith('/'):
        return None
    if not p.endswith('/') and not re.search(r'\.[a-z0-9]{2,5}$', p):
        p += '/'
    return p


LINK_MD = re.compile(r'\[([^\]]*)\]\(\s*((?:\{\{.*?\}\}|\{%.*?%\}|[^)\s])+(?:\s*\{\{.*?\}\})?(?:\{%.*?%\})?[^)\s]*)\s*\)')
LINK_HTML = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
LIQUID_PATH = re.compile(r"""['"](/[^'"]*)['"]\s*\|\s*(?:relative_url|absolute_url)""")


def extract_links(body):
    links = []
    for text, href in LINK_MD.findall(body):
        links.append((text.strip(), href))
    for href, text in LINK_HTML.findall(body):
        links.append((re.sub(r'<[^>]+>', '', text).strip(), href))
    out = []
    for text, href in links:
        lm = LIQUID_PATH.search(href)
        if lm:
            href = lm.group(1)
        out.append((text, href))
    return out


def classify_target(path):
    p = path or ''
    if p == '/':
        return 'home'
    if p in ('/bang-gia/', '/bang-gia-xe-so/', '/bang-gia-xe-ga/', '/bang-gia-xe-dien/', '/bang-gia-xe-50cc/'):
        return 'pricing'
    if p in ('/lien-he/', '/gioi-thieu/', '/dieu-khoan/', '/bao-mat/'):
        return 'static'
    if re.match(r'^/[a-z-]+/$', p):
        return 'hub_or_category'
    if re.match(r'^/[a-z-]+/[a-z0-9-]+/$', p) and not re.search(r'/\d{4}/', p):
        return 'topic'
    return 'post'


def md_headings(body):
    heads, in_code = [], False
    for i, line in enumerate(body.split('\n')):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r'^(#{1,6})\s+(.*?)\s*#*\s*$', line)
        if m:
            heads.append({'level': len(m.group(1)), 'text': m.group(2).strip(), 'line': i + 1})
    return heads


def first_sentences(text, n=2, limit=260):
    t = re.sub(r'\s+', ' ', re.sub(r'[*_`>#]', '', text)).strip()
    parts = re.split(r'(?<=[.!?])\s+', t)
    return ' '.join(parts[:n])[:limit]


def section_text(body_lines, start_line, end_line):
    return '\n'.join(body_lines[start_line:end_line]).strip()


def faq_signals(body, heads):
    lines = body.split('\n')
    # next heading index helper
    def end_of(idx):
        lvl = heads[idx]['level']
        for j in range(idx + 1, len(heads)):
            if heads[j]['level'] <= lvl:
                return heads[j]['line'] - 1
        return len(lines)
    faq_sections = []
    for i, h in enumerate(heads):
        if h['level'] in (2, 3) and FAQ_HEAD.search(h['text']) and not h['text'].strip().endswith('?'):
            faq_sections.append(i)
    pairs = []
    for i in faq_sections:
        h = heads[i]
        end = end_of(i)
        sub = [x for x in heads[i + 1:] if x['line'] <= end and x['level'] == h['level'] + 1]
        for k, sh in enumerate(sub):
            nxt = sub[k + 1]['line'] - 1 if k + 1 < len(sub) else end
            ans = section_text(lines, sh['line'], nxt)
            pairs.append({'question': sh['text'], 'answer_snippet': first_sentences(ans, 2),
                          'where': 'H%d under "%s" line %d' % (sh['level'], h['text'], sh['line']), 'form': 'heading'})
        block = section_text(lines, h['line'], end)
        for m in re.finditer(r'^\s*(?:[-*]\s+)?\*\*([^*\n]{6,200}\?)\*\*\s*[:\-–]?\s*(.*)$', block, re.M):
            pairs.append({'question': m.group(1).strip(), 'answer_snippet': first_sentences(m.group(2), 2),
                          'where': 'bold Q in "%s"' % h['text'], 'form': 'bold'})
        for m in re.finditer(r'^\s*(?:Q|Hỏi|Câu hỏi)\s*[:.]\s*(.+?\?)\s*$\n+\s*(?:A|Đáp|Trả lời)\s*[:.]\s*(.+)$', block, re.M):
            pairs.append({'question': m.group(1).strip(), 'answer_snippet': first_sentences(m.group(2), 2),
                          'where': 'Q:/A: in "%s"' % h['text'], 'form': 'qa-lines'})
    question_heads = [h for h in heads if h['level'] in (2, 3, 4) and (
        h['text'].strip().endswith('?') or QUESTION_START.match(norm_text(h['text']) + ' ') is not None
        and h['text'].strip().endswith('?'))]
    qh_all = [h for h in heads if h['level'] in (2, 3, 4) and h['text'].strip().endswith('?')]
    inline_q = []
    for m in re.finditer(r'^\s*\*\*([^*\n]{6,200}\?)\*\*\s*$', body, re.M):
        inline_q.append(m.group(1).strip())
    details = len(re.findall(r'<details', body, re.I))
    return {
        'faq_section_headings': [heads[i]['text'] for i in faq_sections],
        'faq_pairs': pairs,
        'question_headings': [{'level': h['level'], 'text': h['text'], 'line': h['line']} for h in qh_all],
        'bold_question_lines': inline_q,
        'details_blocks': details,
    }


def json_unsafe(s):
    return bool(s) and any(c in s for c in ('"', '\\', '\n', '\r', '\t'))


def load_scorer():
    sys.path.insert(0, str(ROOT / 'scripts/factory'))
    spec = importlib.util.spec_from_file_location('audit_mod_ro', str(ROOT / 'scripts/factory/audit-legacy-qa.py'))
    A = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(A)
    spec2 = importlib.util.spec_from_file_location('operator_ro', str(ROOT / 'scripts/factory/factory-operator.py'))
    op = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(op)
    biz = json.loads((ROOT / 'data/business-facts.json').read_text(encoding='utf-8'))
    tax = json.loads((ROOT / 'data/content-taxonomy.json').read_text(encoding='utf-8'))
    return A, op, biz, tax


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sitemap', required=True, help='text file: one live sitemap <loc> per line')
    ap.add_argument('--out', default='reports/seo-aeo/data')
    ap.add_argument('--no-scorer', action='store_true')
    a = ap.parse_args()
    os.chdir(ROOT)
    out_dir = ROOT / a.out
    out_dir.mkdir(parents=True, exist_ok=True)

    locs = [l for l in pathlib.Path(a.sitemap).read_text(encoding='utf-8').split('\n') if l.strip()]
    live_paths = {urllib.parse.unquote(re.sub(r'^https://blog\.thuexemaynguyentu\.com', '', u)) for u in locs}

    rows = list(csv.DictReader(open('data/content-matrix.csv', encoding='utf-8', newline='')))
    by_path = {r['output_path']: r for r in rows}
    idn = lambda r: int(r['id'][4:])  # noqa: E731
    live_rows = sorted([r for r in rows if r['status'] in ('EXISTING', 'PUBLISHED')], key=idn)
    sample = live_rows[:300]
    alt_sample = sorted([r for r in rows if r['status'] == 'PUBLISHED'], key=idn)[:300]
    excluded_in_span = [{'id': r['id'], 'status': r['status'], 'title': r['title']}
                        for r in rows if idn(r) <= idn(sample[-1]) and r['status'] not in ('EXISTING', 'PUBLISHED')]

    fmap = yaml_map('_data/factory-map.yml')
    parents = yaml_map('_data/factory-parents.yml')
    children = yaml_map('_data/factory-taxonomy.yml')

    # ---- read every live post once (links, similarity, inbound graph)
    posts = {}
    for r in rows:
        if r['status'] not in ('EXISTING', 'PUBLISHED', 'REVIEW'):
            continue
        p = ROOT / r['output_path']
        if not p.is_file():
            continue
        text = p.read_text(encoding='utf-8')
        fm, body = parse_front_matter(text)
        posts[r['id']] = {'row': r, 'fm': fm, 'body': body, 'text': text}
    inbound = collections.defaultdict(set)
    path_to_id = {}
    for pid, d in posts.items():
        url = norm_path(post_url_path(d['fm'], d['row']) or '')
        if url:
            path_to_id[url] = pid
        d['url'] = url
    for pid, d in posts.items():
        for _, href in extract_links(d['body']):
            tgt = norm_path(href[len(SITE):] if href.startswith(SITE) else href)
            if tgt and tgt in path_to_id and path_to_id[tgt] != pid:
                inbound[path_to_id[tgt]].add(pid)

    # ---- similarity index (title + H2/H3 + keyword)
    doc_tokens, df = {}, collections.Counter()
    for pid, d in posts.items():
        heads = md_headings(d['body'])
        title = unquote_yaml(d['fm'].get('title', d['row']['title']))
        toks = set(tokens(title + ' ' + d['row'].get('primary_keyword', '')))
        toks2 = set(tokens(' '.join(h['text'] for h in heads if h['level'] in (2, 3))))
        bigrams = set(zip(sorted(tokens(title))[:-1], sorted(tokens(title))[1:])) if False else set()
        tl = tokens(title)
        bigr = {a_ + '_' + b_ for a_, b_ in zip(tl, tl[1:])}
        doc_tokens[pid] = (toks, toks2, bigr)
        for t in toks | toks2:
            df[t] += 1
    N = len(posts)
    idf = {t: math.log((N + 1) / (c + 1)) + 1 for t, c in df.items()}
    inv = collections.defaultdict(set)
    for pid, (t1, t2, _) in doc_tokens.items():
        for t in t1 | t2:
            inv[t].add(pid)

    def similar(pid, k=5):
        t1, t2, bg = doc_tokens[pid]
        mine = t1 | t2
        cand = set()
        for t in t1:
            if len(inv[t]) < 400:
                cand |= inv[t]
        cand.discard(pid)
        scored = []
        for q in cand:
            q1, q2, qb = doc_tokens[q]
            theirs = q1 | q2
            inter_t = t1 & q1
            title_j = len(inter_t) / max(1, len(t1 | q1))
            wsum = sum(idf.get(t, 1) for t in inter_t)
            wtot = sum(idf.get(t, 1) for t in (t1 | q1)) or 1
            weighted = wsum / wtot
            full = len(mine & theirs) / max(1, len(mine | theirs))
            bscore = len(bg & qb) / max(1, len(bg | qb))
            score = 0.5 * weighted + 0.2 * title_j + 0.15 * full + 0.15 * bscore
            scored.append((score, q, sorted(inter_t)[:8]))
        scored.sort(reverse=True)
        res = []
        for s, q, shared in scored[:k]:
            rr = posts[q]['row']
            res.append({'id': q, 'score': round(s, 3), 'title': rr['title'], 'url': posts[q].get('url'),
                        'status': rr['status'], 'shared_title_tokens': shared,
                        'same_child': rr['child_id'] == posts[pid]['row']['child_id']})
        return res

    # ---- canonical QA scorer (read-only), best-effort
    scorer = None
    if not a.no_scorer:
        try:
            scorer = load_scorer()
        except Exception as exc:  # pragma: no cover
            print('scorer unavailable:', exc, file=sys.stderr)

    def qa_signals(row):
        if not scorer:
            return None
        A, op, biz, tax = scorer
        try:
            op.build_amount_whitelist(biz)
            res = A.rescore_published(op, row, rows, biz, tax)
        except Exception as exc:
            return {'error': str(exc)[:200]}
        return {
            'scorer': res.get('scorer'), 'quality': res.get('quality'), 'seo': res.get('seo'),
            'business_fact': res.get('business_fact'), 'legal': res.get('legal'),
            'critical_failure': res.get('critical_failure'), 'result': res.get('result'),
            'word_count': res.get('word_count'),
            'failed_checks': sorted(k for k, v in (res.get('checks') or {}).items() if not v),
            'non_approved_amounts': res.get('non_approved_amounts'),
            'forbidden_hits': res.get('forbidden_hits'),
            'cannibalization_clash': res.get('cannibalization_clash'),
            'duplicate_title_clash': res.get('duplicate_title_clash'),
            'bad_routes': res.get('bad_routes'),
        }

    def build_post(r):
        d = posts[r['id']]
        fm, body = d['fm'], d['body']
        title = unquote_yaml(fm.get('title', r['title']))
        desc = unquote_yaml(fm.get('description', ''))
        heads = md_headings(body)
        words = len(re.findall(r'\w+', re.sub(r'[#*_`>\[\]()|-]', ' ', body), re.U))
        links = extract_links(body)
        internal, external, broken = [], [], []
        for text, href in links:
            tgt = norm_path(href[len(SITE):] if href.startswith(SITE) else href)
            if tgt:
                ok = tgt in live_paths
                internal.append({'text': text[:80], 'target': tgt, 'type': classify_target(tgt), 'live': ok})
                if not ok:
                    broken.append(tgt)
            elif href.startswith('http'):
                external.append({'text': text[:80], 'href': href[:160]})
        cat_key = (norm_path(r['expected_url']) or '')
        parent_id = unquote_yaml(fm.get('parent_id', '')) or fmap.get(r['slug'], {}).get('p') or r['parent_id']
        child_id = unquote_yaml(fm.get('child_id', '')) or fmap.get(r['slug'], {}).get('c') or r['child_id']
        bc_parent = parents.get(parent_id)
        bc_child = children.get(child_id)
        faq = faq_signals(body, heads)
        excerpt_para = ''
        for para in re.split(r'\n\s*\n', body.strip()):
            if para.strip() and not para.lstrip().startswith(('#', '|', '-', '*', '>')):
                excerpt_para = re.sub(r'\s+', ' ', re.sub(r'[*_`\[\]]', '', para)).strip()
                break
        desc_for_ld = desc or excerpt_para
        meta_title = title if SITE_TITLE in title else title + ' - ' + SITE_TITLE
        tables = len(re.findall(r'^\s*\|.+\|\s*$', body, re.M))
        lists = len(re.findall(r'^\s*(?:[-*]|\d+\.)\s+', body, re.M))
        h2 = [h for h in heads if h['level'] == 2]
        item = {
            'id': r['id'], 'status': r['status'], 'file': r['output_path'],
            'canonical_path': cat_key, 'canonical_url': SITE + urllib.parse.quote(cat_key, safe="/%:@") if cat_key else None,
            'in_live_sitemap': cat_key in live_paths,
            'title': title, 'description': desc, 'date': fm.get('date', '').strip(),
            'categories': parse_list(fm.get('categories', '')), 'tags': parse_list(fm.get('tags', '')),
            'front_matter_keys': sorted(fm.keys()),
            'author': unquote_yaml(fm.get('author', '')), 'lang': fm.get('lang', '').strip(),
            'matrix': {k: r[k] for k in ('intent', 'primary_keyword', 'secondary_keywords', 'parent_id', 'child_id',
                                         'child_cluster', 'parent_hub', 'slug', 'search_intent', 'group') if k in r},
            'taxonomy': {'parent_id': parent_id, 'child_id': child_id,
                         'parent_title': (bc_parent or {}).get('t'), 'parent_slug': (bc_parent or {}).get('s'),
                         'child_title': (bc_child or {}).get('t'), 'child_slug': (bc_child or {}).get('s'),
                         'hub_url': ('/%s/' % bc_parent['s']) if bc_parent else None,
                         'topic_url': ('/%s/%s/' % (bc_parent['s'], bc_child['s'])) if bc_parent and bc_child else None},
            'meta': {'title_for_serp': meta_title, 'title_len': len(meta_title), 'description_len': len(desc),
                     'description_missing': not desc, 'robots_meta': fm.get('robots', '').strip() or None,
                     'canonical_override': fm.get('canonical_url', '').strip() or None},
            'word_count': words, 'headings': heads,
            'h1_in_body': sum(1 for h in heads if h['level'] == 1), 'h2_count': len(h2),
            'h3_count': sum(1 for h in heads if h['level'] == 3),
            'tables': tables, 'list_items': lists, 'images': len(re.findall(r'!\[', body)),
            'opening_paragraph': first_sentences(excerpt_para, 2, 320),
            'faq': faq,
            'links': {'internal_count': len(internal), 'internal': internal[:40], 'external': external[:10],
                      'broken_internal': sorted(set(broken)), 'to_pricing': sum(1 for x in internal if x['type'] == 'pricing'),
                      'to_hub_or_topic': sum(1 for x in internal if x['type'] in ('hub_or_category', 'topic')),
                      'to_posts': sum(1 for x in internal if x['type'] == 'post'),
                      'inbound_from_posts': len(inbound.get(r['id'], ()))},
            'jsonld_sim': {
                'graph': ['Organization', 'LocalBusiness', 'WebSite', 'BlogPosting'],
                'breadcrumb_list': 'ok' if (bc_parent and bc_child) else ('parent-only' if bc_parent else 'MISSING-TAXONOMY (null names)'),
                'blogposting_headline_json_unsafe': json_unsafe(title),
                'blogposting_description_json_unsafe': json_unsafe(desc_for_ld),
                'blogposting_valid_json': not (json_unsafe(title) or json_unsafe(desc_for_ld)),
                'dateModified_equals_datePublished': True,
                'missing_recommended': ['mainEntityOfPage', 'image', 'inLanguage'],
                'faqpage': False,
            },
            'qa_scorer': qa_signals(r),
        }
        return item

    sample_items = []
    for r in sample:
        item = build_post(r)
        item['similar'] = similar(r['id'])
        sample_items.append(item)

    # ---- main pages
    pages = []
    for root, dirs, files in os.walk('.'):
        parts = root.split('/')
        if any(p in ('.git', '_posts', '_drafts', 'docs', 'scripts', 'data', 'reports', 'assets', 'node_modules', 'en',
                     '_queue', '.jekyll-cache', '_site', '_includes', '_layouts', 'listing', '_data') for p in parts):
            continue
        for f in files:
            if not f.endswith(('.md', '.html')) or f in ('README.md', 'AGENTS.md', '404.html'):
                continue
            path = os.path.join(root, f)[2:]
            text = pathlib.Path(path).read_text(encoding='utf-8')
            fm, body = parse_front_matter(text)
            perm = unquote_yaml(fm.get('permalink', ''))
            if not perm:
                continue
            layout = fm.get('layout', '').strip()
            ptype = {'home': 'Homepage', 'hub': 'Hub', 'category': 'Category', 'topic': 'Topic cluster page'}.get(layout, 'Page')
            ident = 'PG-HOME' if perm == '/' else 'PG-' + re.sub(r'[^A-Z0-9]+', '-', strip_accents(perm.strip('/')).upper()).strip('-')
            heads = md_headings(body)
            pages.append({
                'page_id': ident, 'page_type': ptype, 'layout': layout, 'source': path, 'canonical_path': perm,
                'canonical_url': SITE + perm, 'in_live_sitemap': perm in live_paths,
                'title': unquote_yaml(fm.get('title', '')), 'description': unquote_yaml(fm.get('description', '')),
                'front_matter': {k: v for k, v in fm.items() if k not in ('title', 'description', 'permalink', 'layout')},
                'source_words': len(re.findall(r'\w+', body, re.U)), 'source_headings': heads[:40],
                'source_has_liquid_loops': bool(re.search(r'{%\s*for\s', body)),
                'faq_signals_source': faq_signals(body, heads),
                'internal_links_source': [x for x in (norm_path(h) for _, h in extract_links(body)) if x][:40],
                'jsonld_sim': {'graph': ['Organization', 'LocalBusiness', 'WebSite'],
                               'breadcrumb': 'topic-breadcrumb microdata only (no BreadcrumbList JSON-LD)' if layout in ('hub', 'topic') else 'breadcrumb include' if layout not in ('home',) else 'none',
                               'faqpage': False},
            })
    pages.sort(key=lambda p: (['Homepage', 'Hub', 'Category', 'Page', 'Topic cluster page'].index(p['page_type']), p['canonical_path']))

    summary = {
        'sample_definition': ('first 300 live articles (matrix status EXISTING or PUBLISHED) by article id ascending, '
                              'excluding REVIEW/BLOCKED/PLANNED/draft'),
        'sample_first_id': sample[0]['id'], 'sample_last_id': sample[-1]['id'],
        'sample_status_counts': dict(collections.Counter(r['status'] for r in sample)),
        'excluded_ids_inside_span': excluded_in_span,
        'sample_all_in_live_sitemap': all(i['in_live_sitemap'] for i in sample_items),
        'alt_sample_definition': 'first 300 rows with status PUBLISHED (factory-published) by id ascending',
        'alt_sample_first_id': alt_sample[0]['id'], 'alt_sample_last_id': alt_sample[-1]['id'],
        'live_sitemap_urls': len(locs), 'main_pages': len(pages), 'main_pages_in_sitemap': sum(p['in_live_sitemap'] for p in pages),
    }
    (out_dir / 'sample-first300.json').write_text(json.dumps({
        'definition': summary['sample_definition'],
        'sample': [{'id': r['id'], 'status': r['status'], 'canonical_path': norm_path(r['expected_url']),
                    'title': r['title']} for r in sample],
        'excluded_ids_inside_span': excluded_in_span,
        'alternative_sample_factory_published': [{'id': r['id'], 'canonical_path': norm_path(r['expected_url'])} for r in alt_sample],
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    (out_dir / 'first300-extract.json').write_text(json.dumps(sample_items, ensure_ascii=False, indent=1), encoding='utf-8')
    (out_dir / 'pages-extract.json').write_text(json.dumps(pages, ensure_ascii=False, indent=1), encoding='utf-8')
    (out_dir / 'extract-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
