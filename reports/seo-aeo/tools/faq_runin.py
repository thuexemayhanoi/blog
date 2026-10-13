#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detect RUN-IN Q&A (questions answered inside ordinary paragraphs) — the form most legacy / factory posts use.

The heading-based detector in extract_audit_data.py only finds Q&A built from headings / bold lines. Many posts instead write
"Hỏi một: ...? <answer> Hỏi hai: ...?", "Hỏi: ... Trả lời: ...", "Câu hỏi đầu tiên: ... Câu hỏi thứ hai: ...". This script counts those
labels (READ-ONLY) and writes reports/seo-aeo/data/faq-runin.json: per post (sample + whole site) the number of run-in Q labels, A labels,
and whether they sit under a FAQ-like heading. Used only as an independent cross-check of the agents' EXPLICIT / IMPLICIT calls.

  python3 reports/seo-aeo/tools/faq_runin.py
"""
import csv
import json
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
NUM = r'(?:một|hai|ba|bốn|tư|năm|sáu|bảy|tám|chín|mười|\d+)'
Q_LABEL = re.compile(r'(?:\bHỏi(?:\s+' + NUM + r')?\s*[:：]|\bCâu\s+hỏi\s+(?:đầu\s+tiên|thứ\s+' + NUM + r'|số\s+' + NUM + r'|tiếp\s+theo)\s*[:：]|^\s*Q\s*[:：.])', re.I | re.M)
A_LABEL = re.compile(r'(?:\bTrả\s+lời\s*[:：]|\bĐáp\s*[:：]|^\s*A\s*[:：.])', re.I | re.M)
FAQ_HEAD = re.compile(r'^#{2,3}\s+.*(?:câu hỏi|hỏi đáp|hỏi nhanh|thắc mắc|giải đáp|faq).*$', re.I | re.M)


def body_of(text):
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n?', text, re.S)
    return text[m.end():] if m else text


def main():
    os.chdir(ROOT)
    rows = [r for r in csv.DictReader(open('data/content-matrix.csv', encoding='utf-8', newline='')) if r['status'] in ('EXISTING', 'PUBLISHED')]
    out, tot = {}, {'posts': 0, 'with_runin_q_ge2': 0, 'with_runin_q_ge2_and_faq_heading': 0}
    for r in sorted(rows, key=lambda r: int(r['id'][4:])):
        p = pathlib.Path(r['output_path'])
        if not p.is_file():
            continue
        body = body_of(p.read_text(encoding='utf-8'))
        q = len(Q_LABEL.findall(body))
        a = len(A_LABEL.findall(body))
        heads = FAQ_HEAD.findall(body)
        tot['posts'] += 1
        if q >= 2:
            tot['with_runin_q_ge2'] += 1
            if heads:
                tot['with_runin_q_ge2_and_faq_heading'] += 1
        out[r['id']] = {'status': r['status'], 'runin_q_labels': q, 'a_labels': a, 'faq_like_headings': [h.strip('# ').strip() for h in heads][:3]}
    first300 = json.loads(pathlib.Path('reports/seo-aeo/data/first300-extract.json').read_text(encoding='utf-8'))
    ids = [x['id'] for x in first300]
    sample = {i: out.get(i) for i in ids}
    stats = {
        'sample_posts': len(ids),
        'sample_with_runin_q_ge2': sum(1 for v in sample.values() if v and v['runin_q_labels'] >= 2),
        'sample_with_runin_q_ge2_and_faq_heading': sum(1 for v in sample.values() if v and v['runin_q_labels'] >= 2 and v['faq_like_headings']),
        'site': tot,
    }
    pathlib.Path('reports/seo-aeo/data/faq-runin.json').write_text(
        json.dumps({'definition': 'labels: "Hỏi [số]:", "Câu hỏi đầu tiên/thứ N:", "Q:" ; answers: "Trả lời:", "Đáp:", "A:"',
                    'stats': stats, 'per_post': out}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
