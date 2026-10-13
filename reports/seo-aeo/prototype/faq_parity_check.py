#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROTOTYPE (not applied to the site): visible-vs-JSON-LD FAQ parity check on a built Jekyll site.

  python3 faq_parity_check.py <_site dir>

For every HTML page: at most ONE FAQPage JSON-LD block; if present it must parse as JSON and its questions/answers must be
EXACTLY the visible `.faq-item` question/answer pairs (h3 / p) in the same order; a visible `section.faq` without FAQPage
JSON-LD, or FAQPage JSON-LD without the visible section, is an error. Exit 1 on any error.
"""
import glob
import json
import os
import sys

from bs4 import BeautifulSoup


def main(site):
    errors, pages_with_faq = [], 0
    for path in sorted(glob.glob(os.path.join(site, '**', '*.html'), recursive=True)):
        soup = BeautifulSoup(open(path, encoding='utf-8').read(), 'lxml')
        blocks = []
        for s in soup.find_all('script', attrs={'type': 'application/ld+json'}):
            try:
                blocks.append(json.loads(s.string))
            except Exception as exc:  # noqa: BLE001
                errors.append('%s: invalid JSON-LD (%s)' % (path, exc))
        faq = [d for b in blocks for d in (b.get('@graph', [b]) if isinstance(b, dict) else []) if isinstance(d, dict) and d.get('@type') == 'FAQPage']
        vis = [(i.find('h3').get_text(), i.find('p').get_text()) for i in soup.select('section.faq .faq-item')]
        if len(faq) > 1:
            errors.append('%s: %d FAQPage blocks (must be 1)' % (path, len(faq)))
        if faq and not vis:
            errors.append('%s: FAQPage JSON-LD without a visible FAQ section' % path)
        if vis and not faq:
            errors.append('%s: visible FAQ without FAQPage JSON-LD' % path)
        if faq and vis:
            pages_with_faq += 1
            sch = [(q['name'], q['acceptedAnswer']['text']) for q in faq[0]['mainEntity']]
            if sch != vis:
                errors.append('%s: JSON-LD questions/answers differ from the visible FAQ' % path)
            if len(vis) < 2:
                errors.append('%s: fewer than 2 Q&A pairs' % path)
    print('pages with FAQ: %d, errors: %d' % (pages_with_faq, len(errors)))
    for e in errors:
        print('ERROR', e)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
