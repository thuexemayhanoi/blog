#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DIAGNOSE v3 read-only-at-repo-level: SIMULATE the exact post-promote state
of op publish BLG-00635..00644 locally, then run the same follow-up steps
(generate-reports, validate --scope chunk, capacity-audit, queue, tests).
Mutations happen only in the throwaway runner workspace; the committed file
is the evidence output only. Xoa file nay sau khi co evidence."""

import csv, hashlib, json, os, re, shutil, subprocess, sys, glob

IDS = ['BLG-%05d' % n for n in range(635, 645)]
MATRIX = 'data/content-matrix.csv'
QA_DIR = 'data/qa'
CP = 'data/state/checkpoint.json'
TXN = 'data/state/transaction.json'

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    print('$ ' + ' '.join(cmd) + ' -> exit %d' % r.returncode)
    print(r.stdout[-3000:])
    if r.stderr:
        print('STDERR: ' + r.stderr[-3000:])
    return r.returncode

def now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')

def matrix_row_sha256(r):
    basis = {k: r[k] for k in ('title', 'intent', 'primary_keyword',
                               'expected_url', 'output_path', 'canonical_url')}
    return hashlib.sha256(json.dumps(basis, ensure_ascii=False,
                          sort_keys=True).encode('utf-8')).hexdigest()

with open(MATRIX, encoding='utf-8', newline='') as f:
    rows = list(csv.DictReader(f))
by_id = {r['id']: r for r in rows}

# --- simulate promote cua 10 bai (theo dung publish-gate.py) ---
for aid in IDS:
    row = by_id[aid]
    s = row['output_path']
    slug = s[len('_posts/{date}-'):-3] if s.startswith('_posts/{date}-') else re.match(r'_posts/\d{4}-\d{2}-\d{2}-(.+)\.md$', s).group(1)
    hits = sorted(glob.glob('_drafts/*-%s.md' % slug))
    draft = hits[0]
    m = re.match(r'(\d{4}-\d{2}-\d{2})-', os.path.basename(draft))
    date_part = m.group(1)
    dest = '_posts/%s-%s.md' % (date_part, slug)
    print('SIM promote %s: %s -> %s' % (aid, draft, dest))
    shutil.move(draft, dest)
    row['status'] = 'PUBLISHED'
    row['output_path'] = dest
    row['expected_url'] = row['expected_url'].replace('{date}', '%s/%s/%s' % (date_part[:4], date_part[5:7], date_part[8:]))
    row['canonical_url'] = row['expected_url']
    qap = os.path.join(QA_DIR, aid + '.json')
    if os.path.exists(qap):
        qev = json.load(open(qap, encoding='utf-8'))
        qev['source_path'] = dest
        qev['matrix_row_sha256'] = matrix_row_sha256(row)
        qev['published_at'] = now_iso()
        json.dump(qev, open(qap, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

fields = list(rows[0].keys())
with open(MATRIX, 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)

cp = json.load(open(CP, encoding='utf-8'))
planned_left = [r['id'] for r in rows if r['status'] == 'PLANNED']
cp['last_completed_article_id'] = IDS[-1]
cp['next_claimable_id'] = planned_left[0] if planned_left else None
cp['updated_at'] = now_iso()
cp['last_run_id'] = 'publish-gate-' + IDS[-1]
cp['in_progress_chunk'] = None
for st in ('planned', 'writing', 'qa', 'pass', 'published', 'repair', 'blocked', 'fail'):
    cp.setdefault('counts', {})[st] = sum(1 for r in rows if r['status'] == st.upper())
json.dump(cp, open(CP, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

print()
print('=== POST-PROMOTE CHECKS (theo dung thu tu op_publish + verify) ===')
rc = run([sys.executable, 'scripts/factory/generate-reports.py'])
print('generate-reports exit=%d' % rc)
rc = run([sys.executable, 'scripts/factory/validate.py', '--scope', 'chunk'])
print('validate chunk exit=%d' % rc)
rc = run([sys.executable, 'scripts/factory/capacity-audit.py'])
print('capacity-audit exit=%d' % rc)
rc = run([sys.executable, 'scripts/factory/queue.py', '--stats'])
print('queue stats exit=%d' % rc)
for t in sorted(glob.glob('scripts/factory/tests/test_*.py')):
    rc = run([sys.executable, t])
    print('%s exit=%d' % (t, rc))
print()
print('DIAGNOSE V3 DONE')
