#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm thử publish gate: bài thiếu bằng chứng / điểm dưới ngưỡng / trạng thái
chưa PASS phải BỊ TỪ CHỐI promote; bài đủ điều kiện chỉ được promote khi mọi
cổng đều đúng (chạy --dry-run để không đổi dữ liệu thật).

Chạy: python3 scripts/factory/tests/test_publish_gate.py
"""
import csv, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
tmp = tempfile.mkdtemp(prefix='factory-gate-test-')
work = os.path.join(tmp, 'repo')
os.makedirs(os.path.join(work, 'data/state'))
os.makedirs(os.path.join(work, 'data/qa'))
os.makedirs(os.path.join(work, '_drafts'))

for p in ('data/content-taxonomy.json',):
    shutil.copy(os.path.join(ROOT, p), os.path.join(work, p))
os.makedirs(os.path.join(work, 'scripts/factory'))
shutil.copy(os.path.join(ROOT, 'scripts/factory/publish-gate.py'),
            os.path.join(work, 'scripts/factory/publish-gate.py'))
GATE = os.path.join(work, 'scripts/factory/publish-gate.py')

fields = ['id','status','title','intent','primary_keyword','secondary_keywords',
          'parent_id','child_id','group','expected_url','output_path','canonical_url',
          'internal_links','source_required','legal_risk','batch','source']
rows = []
def mrow(aid, st):
    return {'id':aid,'status':st,'title':'T','intent':'I','primary_keyword':'kw',
            'secondary_keywords':'','parent_id':'P-THUE-XE','child_id':'C-THUE-GIA','group':'',
            'expected_url':'/blog/thue-xe/{date}/sim-%s/'%aid,
            'output_path':'_posts/{date}-sim-%s.md'%aid.lower(),
            'canonical_url':'/blog/thue-xe/{date}/sim-%s/'%aid,
            'internal_links':'/bang-gia/','source_required':'false','legal_risk':'none',
            'batch':'','source':'planned:test'}
for aid, st in (('BLG-91001','PASS'), ('BLG-91002','QA'), ('BLG-91003','WRITING')):
    rows.append(mrow(aid, st))
with open(os.path.join(work,'data/content-matrix.csv'),'w',encoding='utf-8',newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

json.dump({'locked': False, 'holder': None}, open(os.path.join(work,'data/state/writer-lock.json'),'w'))
json.dump({'active': False, 'pending': None}, open(os.path.join(work,'data/state/transaction.json'),'w'))
cp = {'factory_version':2,'capacity':10000,'updated_at':'2026-09-27T00:00:00+00:00',
      'status':'RUNNING','matrix_status':'PRESENT_CREATED_NEW',
      'last_completed_article_id':None,'last_batch_id':None,'next_claimable_id':'BLG-91001',
      'in_progress_chunk':None,'counts':{},'resume_point':'','rules':{}}
json.dump(cp, open(os.path.join(work,'data/state/checkpoint.json'),'w'), ensure_ascii=False, indent=2)

draft = os.path.join(work, '_drafts', '2026-09-27-sim-blg-91001.md')
open(draft,'w',encoding='utf-8').write(
    '---\ntitle: Bài kiểm thử gate\ndate: 2026-09-27 09:00:00 +0700\ncategories: [Thuê xe]\n'
    'description: Mô tả kiểm thử.\n---\n\nNội dung kiểm thử đầy đủ, không placeholder.\n')

def run(args):
    return subprocess.run([sys.executable, GATE] + args, cwd=work, capture_output=True, text=True)

# 1. hàng PASS nhưng THIẾU bằng chứng QA -> từ chối
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 1, r.stdout
assert 'bằng chứng' in r.stdout, r.stdout

# 2. bằng chứng có quality < 90 -> từ chối
json.dump({'quality':85,'seo':95,'business_fact':'PASS','legal':'NOT_REQUIRED','critical_failure':False},
          open(os.path.join(work,'data/qa/BLG-91001.json'),'w',encoding='utf-8'))
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 1 and 'quality' in r.stdout, r.stdout

# 3. bằng chứng đủ nhưng trạng thái QA/WRITING -> từ chối
for aid in ('BLG-91002','BLG-91003'):
    r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id',aid,'--dry-run'])
    assert r.returncode == 1 and 'PASS' in r.stdout, r.stdout

# 4. đủ mọi điều kiện -> dry-run PASS, draft vẫn còn nguyên
json.dump({'quality':92,'seo':95,'business_fact':'PASS','legal':'NOT_REQUIRED','critical_failure':False},
          open(os.path.join(work,'data/qa/BLG-91001.json'),'w',encoding='utf-8'))
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 0, r.stdout
assert os.path.exists(draft), 'draft bị di chuyển dù chỉ dry-run'

# 5. business_fact FAIL -> từ chối kể cả điểm cao
json.dump({'quality':95,'seo':95,'business_fact':'FAIL','legal':'NOT_REQUIRED','critical_failure':False},
          open(os.path.join(work,'data/qa/BLG-91001.json'),'w',encoding='utf-8'))
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 1 and 'business_fact' in r.stdout, r.stdout

shutil.rmtree(tmp)
print('PASS: gate từ chối thiếu bằng chứng / điểm thấp / trạng thái chưa PASS / business FAIL; '
      'dry-run không đổi dữ liệu.')
