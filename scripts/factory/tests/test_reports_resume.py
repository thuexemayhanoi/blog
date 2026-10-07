#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm thử resume: sinh report KHÔNG được mất tiến độ.

Kịch bản: tạo bản sao repo thu gọn, mô phỏng matrix có hàng WRITING/QA/REPAIR/
PUBLISHED, checkpoint có last_completed_article_id/in_progress_chunk/updated_at
của lượt chạy trước. Chạy generate-reports.py hai lần. Kỳ vọng:
  - counts phản ánh đúng trạng thái matrix thật (không ép 0),
  - các trường tiến độ được bảo toàn nguyên vẹn,
  - chạy lại (idempotent) cho checkpoint byte-đối-byte giống hệt,
  - updated_at không bị kéo lùi về ngày bài cũ.

Chạy: python3 scripts/factory/tests/test_reports_resume.py
"""
import csv, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


tmp = tempfile.mkdtemp(prefix='factory-resume-test-')
work = os.path.join(tmp, 'repo')
os.makedirs(work)
for d in ('data/state', 'reports/factory', '_posts', 'data/qa'):
    os.makedirs(os.path.join(work, d), exist_ok=True)

# copy script vào bản sao để ROOT của script trỏ vào bản sao, không phải repo thật
os.makedirs(os.path.join(work, 'scripts/factory'))
shutil.copy(os.path.join(ROOT, 'scripts/factory/generate-reports.py'),
            os.path.join(work, 'scripts/factory/generate-reports.py'))
SRC = os.path.join(work, 'scripts/factory/generate-reports.py')

# dữ liệu thật (đã kiểm chứng) + đã thu gọn cho đủ chạy script
for p in ('data/content-taxonomy.json', 'data/content-inventory.csv',
          'data/state/taxonomy-config.json', 'data/state/existing-map.json',
          'data/business-facts.json'):
    shutil.copy(os.path.join(ROOT, p), os.path.join(work, p))
for f in os.listdir(os.path.join(ROOT, '_posts')):
    shutil.copy(os.path.join(ROOT, '_posts', f), os.path.join(work, '_posts', f))
# giữ nguyên inventory thật (không thu gọn)
kept = list(csv.DictReader(open(os.path.join(work, 'data/content-inventory.csv'), encoding='utf-8')))

# matrix mô phỏng có TIẾN ĐỘ: WRITING/QA/REPAIR/PASS/PUBLISHED
fields = ['id','status','title','intent','primary_keyword','secondary_keywords',
          'parent_id','child_id','group','expected_url','output_path','canonical_url',
          'internal_links','source_required','legal_risk','batch','source']
rows = []
for i, r in enumerate(kept, 1):
    rows.append({'id':'BLG-%05d'%i,'status':'EXISTING','title':r['title'],'intent':'(legacy) '+r['title'],
                 'primary_keyword':'','secondary_keywords':'','parent_id':r['likely_parent'],
                 'child_id':r['likely_child'],'group':'','expected_url':r['current_url'],
                 'output_path':r['source_path'],'canonical_url':r['current_url'],'internal_links':'',
                 'source_required':'','legal_risk':'','batch':'','source':'legacy:_posts/x'})
sim = [
    ('BLG-90001','WRITING'), ('BLG-90002','QA'), ('BLG-90003','REPAIR'),
    ('BLG-90004','PASS'), ('BLG-90005','PUBLISHED'), ('BLG-90006','PLANNED'),
    ('BLG-90007','FAIL'), ('BLG-90008','BLOCKED'),
]
for aid, st in sim:
    rows.append({'id':aid,'status':st,'title':'T '+aid,'intent':'I '+aid,'primary_keyword':'kw '+aid,
                 'secondary_keywords':'','parent_id':kept[0]['likely_parent'],'child_id':kept[0]['likely_child'],
                 'group':'','expected_url':'/kinh nghiệm/{date}/sim-%s/'%aid,
                 'output_path':'_posts/{date}-sim-%s.md'%aid,
                 'canonical_url':'/kinh nghiệm/{date}/sim-%s/'%aid,
                 'internal_links':'/bang-gia/','source_required':'false','legal_risk':'none',
                 'batch':'','source':'planned:test'})
with open(os.path.join(work,'data/content-matrix.csv'),'w',encoding='utf-8',newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

# checkpoint lượt chạy TRƯỚC có tiến độ thật
prev_cp = {
    'factory_version': 2, 'capacity': 10000,
    'updated_at': '2026-09-27T09:00:00+00:00',
    'last_run_id': 'publish-gate-BLG-90005',
    'status': 'RUNNING',
    'matrix_status': 'PRESENT_CREATED_NEW',
    'last_completed_article_id': 'BLG-90005',
    'last_batch_id': 'BATCH-042',
    'next_claimable_id': 'BLG-90006',
    'in_progress_chunk': {'batch_id': 'BATCH-042', 'ids': ['BLG-90001','BLG-90002'], 'started_at': '2026-09-27T08:00:00+00:00'},
    'counts': {},
    'resume_point': 'x', 'rules': {},
}
json.dump(prev_cp, open(os.path.join(work,'data/state/checkpoint.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=2)

def run():
    r = subprocess.run([sys.executable, SRC], cwd=work, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.load(open(os.path.join(work,'data/state/checkpoint.json'), encoding='utf-8'))

# lock + transaction KHÔNG bị report generation đụng tới
json.dump({'locked': False, 'holder': None}, open(os.path.join(work,'data/state/writer-lock.json'),'w',encoding='utf-8'))
json.dump({'active': False, 'pending': None, 'history': [{'article_id':'BLG-90005','result':'PUBLISHED'}]},
          open(os.path.join(work,'data/state/transaction.json'),'w',encoding='utf-8'))
lock_before = open(os.path.join(work,'data/state/writer-lock.json'), encoding='utf-8').read()
txn_before = open(os.path.join(work,'data/state/transaction.json'), encoding='utf-8').read()

cp1 = run()
cp_before = open(os.path.join(work,'data/state/checkpoint.json'), encoding='utf-8').read()
prog1 = json.load(open(os.path.join(work,'reports/factory/progress.json'), encoding='utf-8'))
import time as _t; _t.sleep(1.1)
cp2 = run()
cp2_raw = open(os.path.join(work,'data/state/checkpoint.json'), encoding='utf-8').read()
prog2 = json.load(open(os.path.join(work,'reports/factory/progress.json'), encoding='utf-8'))

# 1. counts từ matrix THẬT (không ép 0)
exp = {'WRITING':1,'QA':1,'REPAIR':1,'PASS':1,'PUBLISHED':1,'PLANNED':1,'FAIL':1,'BLOCKED':1}
for k, v in exp.items():
    assert cp1['counts'][k.lower()] == v, ('counts %s: %s' % (k, cp1['counts']))
assert cp1['counts']['existing'] == len(kept), cp1['counts']

# 2. tiến độ bảo toàn
assert cp1['last_completed_article_id'] == 'BLG-90005'
assert cp1['last_batch_id'] == 'BATCH-042'
assert cp1['next_claimable_id'] == 'BLG-90006'
assert cp1['in_progress_chunk'] == prev_cp['in_progress_chunk']
assert cp1['status'] == 'RUNNING'
assert cp1['last_run_id'] == 'publish-gate-BLG-90005'

# 3. updated_at không bị kéo lùi về ngày bài cũ (data_through của 40 bài cũ < 09:00 ngày 27)
assert cp1['updated_at'] == '2026-09-27T09:00:00+00:00', cp1['updated_at']

# 4. idempotent về STATE: chạy lại cho checkpoint byte-đối-byte giống
assert cp2_raw == cp_before, 'chạy lại generate-reports.py làm thay đổi checkpoint'

# 5. BA mốc thời gian: generated_at = giờ chạy thật (đổi giữa 2 lần chạy),
#    data_through = mốc dữ liệu (không đổi khi nội dung không đổi),
#    checkpoint.updated_at = mốc state (report KHÔNG nâng)
assert prog2['generated_at'] > prog1['generated_at'], (
    'generated_at phải là giờ chạy thật — phải đổi giữa hai lần chạy (%s vs %s)' % (
        prog1['generated_at'], prog2['generated_at']))
assert prog1['data_through'] == prog2['data_through'], 'data_through đổi dù nội dung không đổi'
assert prog2['data_fingerprint'] == prog1['data_fingerprint'], 'vân tay dữ liệu đổi dù dữ liệu không đổi'
assert prog2['checkpoint_progress']['last_completed_article_id'] == 'BLG-90005'
assert cp2['updated_at'] == '2026-09-27T09:00:00+00:00', (
    'report generation không được nâng checkpoint.updated_at: %s' % cp2['updated_at'])

# 6. lock/transaction untouched bởi report generation
assert open(os.path.join(work,'data/state/writer-lock.json'), encoding='utf-8').read() == lock_before
assert open(os.path.join(work,'data/state/transaction.json'), encoding='utf-8').read() == txn_before

shutil.rmtree(tmp)
print('PASS: chạy lại generate-reports.py không mất tiến độ; counts từ matrix thật; '
      'generated_at đổi theo giờ chạy thật, data_through/vân tay ổn định khi dữ liệu không đổi; '
      'checkpoint.updated_at + lock + transaction không bị report đụng.')
