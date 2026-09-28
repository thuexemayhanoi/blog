#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DIAGNOSE read-only: publish-gate dry-run cho BLG-00635..00644.
Khong mutate: chi in trang thai, hash so khop va gate dry-run cho tung bai.
Xoa file nay sau khi co evidence (cung pattern factory-diagnose1-9)."""
import csv, glob, hashlib, json, os, re, subprocess, sys

IDS = ['BLG-%05d' % n for n in range(635, 645)]

def matrix_rows():
    with open('data/content-matrix.csv', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))

def row_fingerprint(r):
    basis = {k: r[k] for k in ('title', 'intent', 'primary_keyword',
                               'expected_url', 'output_path', 'canonical_url')}
    return hashlib.sha256(json.dumps(basis, ensure_ascii=False,
                          sort_keys=True).encode('utf-8')).hexdigest()

def draft_for(r):
    s = r['output_path']
    if s.startswith('_posts/{date}-'):
        slug = s[len('_posts/{date}-'):-3]
    else:
        m = re.match(r'_posts/\d{4}-\d{2}-\d{2}-(.+)\.md$', s)
        if not m:
            return None, None
        slug = m.group(1)
    hits = sorted(glob.glob('_drafts/*-%s.md' % slug))
    return (hits[0] if hits else None), slug

rows = matrix_rows()
by_id = {r['id']: r for r in rows}
for aid in IDS:
    print()
    print('=== %s ===' % aid)
    row = by_id.get(aid)
    if row is None:
        print('MISSING IN MATRIX')
        continue
    print('row_status=%s' % row['status'])
    draft, slug = draft_for(row)
    print('slug=%s' % slug)
    print('find_draft=%s' % draft)
    qap = 'data/qa/%s.json' % aid
    if not os.path.exists(qap):
        print('QA_EVIDENCE_MISSING')
        continue
    qa = json.load(open(qap, encoding='utf-8'))
    print('qa_scored_at=%s' % qa.get('scored_at'))
    print('qa_content_sha256=%s' % qa.get('content_sha256'))
    print('qa_matrix_row_sha256=%s' % qa.get('matrix_row_sha256'))
    fp = row_fingerprint(row)
    print('matrix_row_sha256_now=%s' % fp)
    print('fp_match=%s' % (fp == qa.get('matrix_row_sha256')))
    if draft:
        dsha = hashlib.sha256(open(draft, 'rb').read()).hexdigest()
        print('draft_sha256_now=%s' % dsha)
        print('sha_match=%s' % (dsha == qa.get('content_sha256')))
        print('--- publish-gate dry-run ---')
        r = subprocess.run([sys.executable, 'scripts/factory/publish-gate.py',
                            '--draft', draft, '--id', aid, '--dry-run'],
                           capture_output=True, text=True)
        print(r.stdout)
        if r.stderr:
            print('STDERR: ' + r.stderr)
        print('gate_exit=%s' % r.returncode)
print()
print('DIAGNOSE DONE')
