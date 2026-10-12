#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""faq_parity_check.py — kiểm tra site ĐÃ BUILD: JSON-LD khớp 1:1 với nội dung hiển thị (READ-ONLY, chỉ stdlib).

  python3 scripts/faq/faq_parity_check.py --site ./_site [--json]

Với MỌI trang .html trong --site:
  P1  mọi khối <script type="application/ld+json"> phải parse được thành JSON (bắt lỗi escape của template);
  P2  tối đa MỘT FAQPage; FAQPage chỉ hợp lệ khi có khối hiển thị `section.faq` (không có schema "mồ côi");
  P3  `section.faq` có data-faq-schema="1"  <=>  có FAQPage JSON-LD (và ngược lại);
  P4  danh sách (câu hỏi, câu trả lời) của JSON-LD == các `.faq-item` hiển thị (h3 / p), cùng thứ tự, cùng chữ;
  P5  mỗi khối FAQ có >= 2 cặp hỏi–đáp; tối đa một `section.faq` mỗi trang.
Exit 1 nếu có lỗi. Không có FAQ nào trên site => OK.
"""
import argparse
import json
import os
import sys
from html.parser import HTMLParser


class Page(HTMLParser):
    """Thu: khối JSON-LD, các section.faq (kèm cặp h3/p của .faq-item)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ld_blocks = []          # chuỗi JSON thô
        self.faqs = []               # [{'schema': bool, 'items': [[q, a], ...]}]
        self._ld = None
        self._depth = 0              # độ sâu bên trong section.faq (0 = ngoài)
        self._cur = None
        self._item = None            # [q, a] đang thu
        self._field = None           # 'q' | 'a'
        self._item_depth = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get('class') or '').split()
        if tag == 'script' and (a.get('type') or '').lower() == 'application/ld+json':
            self._ld = []
            return
        if tag == 'section' and 'faq' in cls and self._depth == 0:
            self._cur = {'schema': a.get('data-faq-schema') == '1', 'items': []}
            self.faqs.append(self._cur)
            self._depth = 1
            return
        if self._depth:
            self._depth += 1 if tag not in ('br', 'img', 'hr', 'input', 'meta', 'link') else 0
            if tag == 'div' and 'faq-item' in cls and self._item is None:
                self._item = ['', '']
                self._item_depth = self._depth
            elif self._item is not None and tag == 'h3' and self._field is None:
                self._field = 'q'
            elif self._item is not None and tag == 'p' and self._field is None:
                self._field = 'a'

    def handle_endtag(self, tag):
        if tag == 'script' and self._ld is not None:
            self.ld_blocks.append(''.join(self._ld))
            self._ld = None
            return
        if self._depth:
            if self._field == 'q' and tag == 'h3' or self._field == 'a' and tag == 'p':
                self._field = None
            if self._item is not None and tag == 'div' and self._depth == self._item_depth:
                self._cur['items'].append([self._item[0].strip(), self._item[1].strip()])
                self._item = None
                self._item_depth = None
            if tag not in ('br', 'img', 'hr', 'input', 'meta', 'link'):
                self._depth -= 1

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
        elif self._item is not None and self._field:
            self._item[0 if self._field == 'q' else 1] += data


def faq_pages_from_ld(blocks, errors, rel):
    found = []
    for raw in blocks:
        try:
            doc = json.loads(raw)
        except ValueError as exc:
            errors.append('%s: JSON-LD không parse được (%s)' % (rel, exc))
            continue
        for node in (doc.get('@graph', [doc]) if isinstance(doc, dict) else (doc if isinstance(doc, list) else [])):
            if isinstance(node, dict) and node.get('@type') == 'FAQPage':
                found.append(node)
    return found


def check_site(site):
    errors, pages, with_faq = [], 0, 0
    for dp, _, fns in os.walk(site):
        for fn in sorted(fns):
            if not fn.endswith('.html'):
                continue
            path = os.path.join(dp, fn)
            rel = os.path.relpath(path, site)
            pages += 1
            with open(path, encoding='utf-8', errors='replace') as fh:
                html = fh.read()
            if 'ld+json' not in html and 'class="faq"' not in html:
                continue
            p = Page()
            p.feed(html)
            ld = faq_pages_from_ld(p.ld_blocks, errors, rel)
            if len(ld) > 1:
                errors.append('%s: %d khối FAQPage (chỉ được 1)' % (rel, len(ld)))
            if len(p.faqs) > 1:
                errors.append('%s: %d khối section.faq (chỉ được 1)' % (rel, len(p.faqs)))
            if ld and not p.faqs:
                errors.append('%s: FAQPage JSON-LD không có khối FAQ hiển thị' % rel)
            if not p.faqs:
                continue
            with_faq += 1
            f = p.faqs[0]
            if len(f['items']) < 2:
                errors.append('%s: khối FAQ có < 2 cặp hỏi–đáp' % rel)
            if f['schema'] and not ld:
                errors.append('%s: data-faq-schema=1 nhưng không có FAQPage JSON-LD' % rel)
            if ld and not f['schema']:
                errors.append('%s: có FAQPage JSON-LD nhưng khối hiển thị không đánh dấu data-faq-schema=1' % rel)
            if ld and f['schema']:
                try:
                    sch = [[q['name'].strip(), q['acceptedAnswer']['text'].strip()] for q in ld[0]['mainEntity']]
                except (KeyError, TypeError, AttributeError):
                    errors.append('%s: cấu trúc FAQPage JSON-LD sai' % rel)
                    continue
                if sch != f['items']:
                    errors.append('%s: câu hỏi/đáp trong JSON-LD KHÁC khối hiển thị' % rel)
    return errors, pages, with_faq


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--site', required=True)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    errors, pages, with_faq = check_site(a.site)
    if a.json:
        print(json.dumps({'errors': errors, 'pages': pages, 'pages_with_faq': with_faq}, ensure_ascii=False, indent=1))
    else:
        for e in errors:
            print('ERROR', e)
        print('pages scanned: %d, pages with FAQ: %d, errors: %d' % (pages, with_faq, len(errors)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
