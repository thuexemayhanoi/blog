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
import hashlib


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def row_fp(r):
    import json as _j
    basis = {k: r[k] for k in ('title','intent','primary_keyword','expected_url','output_path','canonical_url')}
    return hashlib.sha256(_j.dumps(basis, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()

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

# 4. bằng chứng thiếu content_sha256 (gate v3) -> từ chối
json.dump({'quality':92,'seo':95,'business_fact':'PASS','legal':'NOT_REQUIRED','critical_failure':False},
          open(os.path.join(work,'data/qa/BLG-91001.json'),'w',encoding='utf-8'))
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 1 and 'content_sha256' in r.stdout, r.stdout

# 5. đủ mọi điều kiện (kèm hash đúng) -> dry-run PASS, draft vẫn còn nguyên
def full_qa(row):
    return {'quality':92,'seo':95,'business_fact':'PASS','legal':'NOT_REQUIRED',
            'critical_failure':False,
            'content_sha256': sha(draft), 'matrix_row_sha256': row_fp(row)}
rows_csv = list(csv.DictReader(open(os.path.join(work,'data/content-matrix.csv'),encoding='utf-8')))
row1 = next(r for r in rows_csv if r['id']=='BLG-91001')
json.dump(full_qa(row1), open(os.path.join(work,'data/qa/BLG-91001.json'),'w',encoding='utf-8'))
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 0, r.stdout
assert os.path.exists(draft), 'draft bị di chuyển dù chỉ dry-run'

# 6. STALE_QA_EVIDENCE: đổi nội dung draft sau QA -> từ chối
open(draft,'a',encoding='utf-8').write('\n\nĐoạn thêm sau khi QA chấm.')
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 1 and 'STALE_QA_EVIDENCE' in r.stdout, r.stdout

# 7. MATRIX_ROW_MISMATCH: đổi title hàng matrix sau QA -> từ chối
open(draft,'r+',encoding='utf-8')
open(draft,'w',encoding='utf-8').write(
    '---\ntitle: Bài kiểm thử gate\ndate: 2026-09-27 09:00:00 +0700\ncategories: [Thuê xe]\n'
    'description: Mô tả kiểm thử.\n---\n\nNội dung kiểm thử đầy đủ, không placeholder.\n')
rows_csv = list(csv.DictReader(open(os.path.join(work,'data/content-matrix.csv'),encoding='utf-8')))
row1 = next(r for r in rows_csv if r['id']=='BLG-91001')
json.dump(full_qa(row1), open(os.path.join(work,'data/qa/BLG-91001.json'),'w',encoding='utf-8'))
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 0, r.stdout  # chuẩn lại -> PASS
row1['title'] = 'Tiêu đề đổi sau QA'
rows_csv[0] = row1 if rows_csv[0]['id']=='BLG-91001' else rows_csv[0]
for i,rr in enumerate(rows_csv):
    if rr['id']=='BLG-91001': rows_csv[i]=row1
with open(os.path.join(work,'data/content-matrix.csv'),'w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows_csv[0].keys())); w.writeheader(); w.writerows(rows_csv)
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 1 and 'MATRIX_ROW_MISMATCH' in r.stdout, r.stdout

# 8. LOCK: sentinel tồn tại -> từ chối kể cả khi mọi điều kiện khác đúng
open(os.path.join(work,'data/state/writer-lock.active'),'w').write('writer khác')
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 1 and 'writer-lock' in r.stdout, r.stdout
os.remove(os.path.join(work,'data/state/writer-lock.active'))

# 9. business_fact FAIL -> từ chối kể cả điểm cao và hash đúng
bad = full_qa(row1); bad['business_fact'] = 'FAIL'
json.dump(bad, open(os.path.join(work,'data/qa/BLG-91001.json'),'w',encoding='utf-8'))
r = run(['--draft','_drafts/2026-09-27-sim-blg-91001.md','--id','BLG-91001','--dry-run'])
assert r.returncode == 1 and 'business_fact' in r.stdout, r.stdout

shutil.rmtree(tmp)
print('PASS: gate từ chối thiếu bằng chứng / điểm thấp / trạng thái chưa PASS / business FAIL; '
      'dry-run không đổi dữ liệu; STALE_QA_EVIDENCE khi nội dung đổi sau QA; '
      'MATRIX_ROW_MISMATCH khi hàng đổi sau QA; writer-lock bị giữ thì từ chối.')
