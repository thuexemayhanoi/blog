#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse the RENDERED HTML of a local Jekyll build (READ-ONLY) for the FAQ / AEO audit.

The build is made outside the repository (detached worktree of the audited commit, JEKYLL_ENV=production,
github-pages gem set) and passed with --site. This script never writes inside the site or the repo sources;
it writes reports/seo-aeo/data/rendered-*.json and (optionally) plain-text exports for the analysis agents.

  python3 reports/seo-aeo/tools/extract_rendered.py --site <_site dir> [--out reports/seo-aeo/data] [--text-out <dir>]

Per page it records: <title>, meta description, canonical, robots, og/twitter presence, H1/H2/H3, every JSON-LD block
(parsed; JSON validity; @types; FAQPage?; BreadcrumbList names; BlogPosting properties), microdata types, visible FAQ markers
(<details> outside the TOC, FAQ-like headings), internal links classified by page region (breadcrumb, toc, article body,
prev/next, related, CTA, header, footer, other) and visible text length.
"""
import argparse
import collections
import json
import os
import pathlib
import re
import sys
import urllib.parse

from bs4 import BeautifulSoup, Comment  # type: ignore

ROOT = pathlib.Path(__file__).resolve().parents[3]
SITE = 'https://blog.thuexemaynguyentu.com'
FAQ_TEXT = re.compile(r'(câu hỏi thường gặp|hỏi đáp|\bfaq\b|câu hỏi nên|những câu hỏi)', re.I)


def region_of(a):
    for p in a.parents:
        if p.name is None:
            continue
        cls = ' '.join(p.get('class', []))
        if p.name == 'nav' and 'breadcrumb' in cls:
            return 'breadcrumb'
        if p.name == 'nav' and 'article-toc' in cls:
            return 'toc'
        if 'post-content' in cls or 'article-body' in cls:
            return 'article_body'
        if 'post-navigation' in cls:
            return 'prev_next'
        if 'article-related' in cls:
            return 'related'
        if 'post-cta' in cls:
            return 'cta'
        if p.name == 'header' or 'site-header' in cls:
            return 'site_header'
        if p.name == 'footer' or 'site-footer' in cls:
            return 'site_footer'
        if 'quick-contact' in cls or 'assistant' in cls:
            return 'widgets'
        if p.name == 'main':
            return 'main_other'
    return 'other'


def norm_target(href):
    if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
        return None
    h = href.split('#')[0]
    if h.startswith(SITE):
        h = h[len(SITE):]
    if h.startswith('http'):
        return None
    if not h.startswith('/'):
        return None
    return urllib.parse.unquote(h) or '/'


def ld_info(soup):
    blocks = []
    for s in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        raw = s.string if s.string is not None else s.get_text()
        info = {'chars': len(raw or ''), 'valid_json': True, 'types': [], 'error': None}
        try:
            data = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            info['valid_json'] = False
            info['error'] = str(exc)[:160]
            blocks.append(info)
            continue
        nodes = data.get('@graph', [data]) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for n in nodes:
            if not isinstance(n, dict):
                continue
            t = n.get('@type')
            info['types'].append(t if isinstance(t, str) else json.dumps(t))
            if t == 'BlogPosting':
                info['blogposting'] = {k: (k in n) for k in ('headline', 'description', 'datePublished', 'dateModified',
                                                             'author', 'publisher', 'image', 'mainEntityOfPage',
                                                             'inLanguage', 'keywords', 'articleSection', 'url')}
                info['blogposting_values'] = {k: n.get(k) for k in ('headline', 'description', 'datePublished', 'dateModified')}
            if t == 'BreadcrumbList':
                items = n.get('itemListElement') or []
                info['breadcrumb'] = {'n': len(items),
                                      'names': [i.get('name') for i in items if isinstance(i, dict)],
                                      'null_or_empty_names': sum(1 for i in items if isinstance(i, dict) and not i.get('name')),
                                      'null_items': sum(1 for i in items if isinstance(i, dict) and not i.get('item'))}
            if t == 'LocalBusiness':
                info['localbusiness_priceRange'] = n.get('priceRange')
            if t == 'FAQPage':
                info['faqpage_questions'] = len(n.get('mainEntity') or [])
        blocks.append(info)
    return blocks


def visible_faq(soup, main):
    det = []
    for d in (main.find_all('details') if main else []):
        if any('article-toc' in ' '.join(p.get('class', [])) for p in d.parents if p.name):
            continue                      # the post TOC is a <details>, not a FAQ
        det.append((d.find('summary').get_text(' ', strip=True) if d.find('summary') else '')[:120])
    heads = []
    if main:
        for h in main.find_all(re.compile(r'^h[1-6]$')):
            t = h.get_text(' ', strip=True)
            if FAQ_TEXT.search(t):
                heads.append(t[:160])
    micro = sorted({e.get('itemtype', '').rsplit('/', 1)[-1] for e in soup.find_all(attrs={'itemtype': True})})
    return {'details_outside_toc': det, 'faq_like_headings': heads, 'microdata_types': micro,
            'faq_microdata': any(m in ('FAQPage', 'Question', 'Answer') for m in micro)}


def text_export(main, max_list_items=12):
    """Plain text of <main> with markdown-ish headings; long repeated card lists are truncated (totals kept)."""
    for t in main.find_all(['script', 'style', 'svg', 'noscript']):
        t.decompose()
    for c in main.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    out = []

    def walk(el, depth=0):
        for ch in el.children:
            if getattr(ch, 'name', None) is None:
                s = str(ch).strip()
                if s:
                    out.append(re.sub(r'\s+', ' ', s))
                continue
            n = ch.name
            if re.match(r'^h[1-6]$', n):
                out.append('\n' + '#' * int(n[1]) + ' ' + ch.get_text(' ', strip=True))
            elif n in ('p', 'summary', 'figcaption', 'blockquote', 'dt', 'dd'):
                t = ch.get_text(' ', strip=True)
                if t:
                    out.append(t)
            elif n in ('ul', 'ol'):
                lis = ch.find_all('li', recursive=False)
                for i, li in enumerate(lis):
                    if i >= max_list_items:
                        out.append('[... %d more list items omitted; list total %d]' % (len(lis) - max_list_items, len(lis)))
                        break
                    out.append('- ' + li.get_text(' ', strip=True))
            elif n == 'table':
                for tr in ch.find_all('tr'):
                    out.append(' | '.join(c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])))
            elif n in ('div', 'section', 'article', 'nav', 'details', 'header', 'main', 'aside', 'span', 'a', 'form', 'label', 'button'):
                cls = ' '.join(ch.get('class', []))
                if 'post-grid' in cls or 'card-grid' in cls or 'topic-grid' in cls:
                    cards = [c for c in ch.children if getattr(c, 'name', None)]
                    for i, c in enumerate(cards):
                        if i >= max_list_items:
                            out.append('[... %d more cards omitted; total %d]' % (len(cards) - max_list_items, len(cards)))
                            break
                        out.append('* ' + c.get_text(' ', strip=True)[:220])
                else:
                    walk(ch, depth + 1)
            else:
                t = ch.get_text(' ', strip=True)
                if t:
                    out.append(t)

    walk(main)
    txt = '\n'.join(out)
    return re.sub(r'\n{3,}', '\n\n', txt).strip() + '\n'


def parse_page(path, text_dir=None, ident=None):
    html = pathlib.Path(path).read_text(encoding='utf-8')
    soup = BeautifulSoup(html, 'lxml')
    g = lambda sel, attr='content': (soup.select_one(sel) or {}).get(attr) if soup.select_one(sel) else None  # noqa: E731
    main = soup.find('main')
    h1 = [h.get_text(' ', strip=True) for h in soup.find_all('h1')]
    h2 = [h.get_text(' ', strip=True) for h in (main or soup).find_all('h2')]
    h3 = [h.get_text(' ', strip=True) for h in (main or soup).find_all('h3')]
    links = collections.defaultdict(list)
    for a in (main or soup).find_all('a', href=True):
        t = norm_target(a['href'])
        if t:
            links[region_of(a)].append({'t': t, 'x': a.get_text(' ', strip=True)[:80]})
    for a in soup.find_all('a', href=True):
        if region_of(a) in ('site_header', 'site_footer', 'widgets'):
            t = norm_target(a['href'])
            if t:
                links[region_of(a)].append({'t': t, 'x': a.get_text(' ', strip=True)[:60]})
    body_text = (main.get_text(' ', strip=True) if main else '')
    ld = ld_info(soup)
    rec = {
        'html_file': str(path),
        'title': (soup.title.string if soup.title and soup.title.string else None),
        'meta_description': g('meta[name=description]'),
        'canonical': g('link[rel=canonical]', 'href'),
        'robots': g('meta[name=robots]'),
        'html_lang': soup.html.get('lang') if soup.html else None,
        'og_url': g('meta[property="og:url"]'), 'og_title': g('meta[property="og:title"]'),
        'og_type': g('meta[property="og:type"]'),
        'hreflang': [l.get('hreflang') for l in soup.find_all('link', rel='alternate') if l.get('hreflang')],
        'h1': h1, 'h2_count': len(h2), 'h3_count': len(h3), 'h2': h2[:60], 'h3': h3[:80],
        'jsonld_blocks': ld,
        'jsonld_all_valid': all(b['valid_json'] for b in ld),
        'jsonld_types': sorted({t for b in ld for t in b['types']}),
        'jsonld_has_faqpage': any('FAQPage' in b['types'] for b in ld),
        'breadcrumb_list_count': sum(1 for b in ld if 'BreadcrumbList' in b['types']),
        'faq': visible_faq(soup, main),
        'links_by_region': {k: len(v) for k, v in links.items()},
        'links_related': links.get('related', []), 'links_breadcrumb': links.get('breadcrumb', []),
        'links_prev_next': links.get('prev_next', []), 'links_cta': links.get('cta', []),
        'links_article_body': links.get('article_body', [])[:60],
        'links_main_other': links.get('main_other', [])[:80],
        'toc_entries': len(soup.select('nav.article-toc li')),
        'visible_words_main': len(re.findall(r'\w+', body_text, re.U)),
        'post_cards_in_main': len(main.select('.post-card')) if main else 0,
    }
    if text_dir and ident and main:
        pathlib.Path(text_dir).mkdir(parents=True, exist_ok=True)
        pathlib.Path(text_dir, ident + '.txt').write_text(text_export(main), encoding='utf-8')
    return rec


def html_path_for(site, url_path):
    p = urllib.parse.unquote(url_path)
    cand = pathlib.Path(site) / p.lstrip('/')
    if p.endswith('/') or not cand.suffix:
        cand = cand / 'index.html'
    return cand


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', required=True)
    ap.add_argument('--out', default='reports/seo-aeo/data')
    ap.add_argument('--text-out', help='directory for plain-text exports of main pages (outside the repo)')
    a = ap.parse_args()
    os.chdir(ROOT)
    out = pathlib.Path(a.out)
    posts = json.loads((out / 'first300-extract.json').read_text(encoding='utf-8'))
    pages = json.loads((out / 'pages-extract.json').read_text(encoding='utf-8'))
    res_posts, missing = [], []
    for r in posts:
        hp = html_path_for(a.site, r['canonical_path'])
        if not hp.is_file():
            missing.append(r['id'])
            continue
        rec = parse_page(hp)
        rec['id'] = r['id']
        rec['canonical_path'] = r['canonical_path']
        res_posts.append(rec)
    res_pages = []
    for p in pages:
        hp = html_path_for(a.site, p['canonical_path'])
        if not hp.is_file():
            missing.append(p['page_id'])
            continue
        rec = parse_page(hp, a.text_out, p['page_id'])
        rec['page_id'] = p['page_id']
        rec['canonical_path'] = p['canonical_path']
        rec['page_type'] = p['page_type']
        res_pages.append(rec)
    (out / 'rendered-first300.json').write_text(json.dumps(res_posts, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'rendered-pages.json').write_text(json.dumps(res_pages, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'posts_parsed': len(res_posts), 'pages_parsed': len(res_pages), 'missing': missing}, ensure_ascii=False))


if __name__ == '__main__':
    main()
