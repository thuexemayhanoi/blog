#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm thử mở rộng vũ trụ chủ đề (topic universe):

1. expand-topic-universe.py idempotent: chạy 2 lần cho kết quả giống hệt
   (taxonomy-config, matrix-seed, topic-universe.md).
2. KHÔNG đụng state runtime: checkpoint, writer-lock, transaction byte-identical.
3. Bảo toàn neo: 483 hàng legacy giữ nguyên id/URL/trạng thái, REVIEW đúng 10,
   PUBLISHED giữ nguyên, không đổi REVIEW -> PASS.
4. generate-matrix idempotent sau mở rộng (byte-identical khi chạy lại).
5. Chống trùng toàn matrix: id, slug, output_path, canonical, expected_url;
   trong child: intent + primary_keyword chuẩn hoá duy nhất.
6. Chống spam: không có hai hàng mở rộng trùng tiêu đề chuẩn hoá.
7. Kế hoạch lô: batch_id nhóm đúng 50 hàng PLANNED theo thứ tự id.
8. Schema v2: hàng PLANNED có slug/search_intent/parent_hub/child_cluster/
   cannibalization_key/word_target/batch_id hợp lệ.

Chạy: python3 scripts/factory/tests/test_topic_universe.py
"""
import csv, hashlib, json, os, re, shutil, subprocess, sys, tempfile, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
tmp = tempfile.mkdtemp(prefix='factory-topic-universe-test-')
work = os.path.join(tmp, 'repo')
os.makedirs(work)

# sao chép tối thiểu: data + scripts + _posts (legacy_rows cần đủ 483 bài)
shutil.copytree(os.path.join(ROOT, 'data'), os.path.join(work, 'data'))
shutil.copytree(os.path.join(ROOT, 'scripts'), os.path.join(work, 'scripts'))
os.makedirs(os.path.join(work, '_posts'))
for fn in os.listdir(os.path.join(ROOT, '_posts')):
    if fn.endswith('.md'):
        shutil.copy(os.path.join(ROOT, '_posts', fn), os.path.join(work, '_posts', fn))
os.makedirs(os.path.join(work, 'reports/factory'))
for fn in os.listdir(os.path.join(ROOT, 'reports/factory')):
    src = os.path.join(ROOT, 'reports/factory', fn)
    if os.path.isdir(src):
        # reports/factory/rows/ (manifest writer export) không thuộc fixture test
        continue
    shutil.copy(src, os.path.join(work, 'reports/factory', fn))
# restore-foundation ghi vào _data/
os.makedirs(os.path.join(work, '_data'))


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def norm(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def run(cmd):
    r = subprocess.run(cmd, cwd=work, capture_output=True, text=True)
    if r.returncode != 0:
        print('FAIL chạy %s:\n%s' % (' '.join(cmd), r.stdout + r.stderr))
        sys.exit(1)
    return r.stdout


FAILS = []


def check(cond, msg):
    print(('PASS: ' if cond else 'FAIL: ') + msg)
    if not cond:
        FAILS.append(msg)


# --- snapshot state runtime + neo legacy/REVIEW trước mở rộng
state_files = ['data/state/checkpoint.json', 'data/state/writer-lock.json',
               'data/state/transaction.json']
before_state = {f: sha(os.path.join(work, f)) for f in state_files}
matrix0 = list(csv.DictReader(open(os.path.join(work, 'data/content-matrix.csv'),
                                   encoding='utf-8', newline='')))
legacy0 = {r['id']: (r['status'], r['expected_url'], r['canonical_url'],
                     r['output_path'])
           for r in matrix0 if r['source'].startswith('legacy:')}
review0 = sorted(r['id'] for r in matrix0 if r['status'] == 'REVIEW')
pub0 = sorted(r['id'] for r in matrix0 if r['status'] == 'PUBLISHED')

# --- 1. chạy expand lần 1 rồi lần 2: kết quả giống hệt
run([sys.executable, 'scripts/factory/expand-topic-universe.py'])
snap1 = {f: sha(os.path.join(work, f)) for f in (
    'data/state/taxonomy-config.json', 'data/state/matrix-seed.json',
    'reports/factory/topic-universe.md')}
run([sys.executable, 'scripts/factory/expand-topic-universe.py'])
snap2 = {f: sha(os.path.join(work, f)) for f in snap1}
check(snap1 == snap2, 'expand-topic-universe.py idempotent (chạy lại không đổi gì)')

# --- 2. state runtime không bị đụng
after_state = {f: sha(os.path.join(work, f)) for f in state_files}
check(before_state == after_state,
      'checkpoint/writer-lock/transaction byte-identical sau mở rộng')

# --- 3. tái sinh taxonomy + matrix, kiểm neo
run([sys.executable, 'scripts/factory/restore-foundation.py'])
run([sys.executable, 'scripts/factory/generate-matrix.py'])
m1 = sha(os.path.join(work, 'data/content-matrix.csv'))
run([sys.executable, 'scripts/factory/generate-matrix.py'])
m2 = sha(os.path.join(work, 'data/content-matrix.csv'))
check(m1 == m2, 'generate-matrix.py idempotent sau mở rộng (byte-identical)')

matrix1 = list(csv.DictReader(open(os.path.join(work, 'data/content-matrix.csv'),
                                   encoding='utf-8', newline='')))
legacy1 = {r['id']: (r['status'], r['expected_url'], r['canonical_url'],
                     r['output_path'])
           for r in matrix1 if r['source'].startswith('legacy:')}
check(legacy0 == legacy1,
      '483 hàng legacy giữ nguyên id/URL/trạng thái (không đổi)')
review1 = sorted(r['id'] for r in matrix1 if r['status'] == 'REVIEW')
pub1 = sorted(r['id'] for r in matrix1 if r['status'] == 'PUBLISHED')
check(review0 == review1 and len(review1) == 10,
      'REVIEW giữ đúng 10 hàng, không tự PASS')
check(pub0 == pub1, 'PUBLISHED giữ nguyên, không reshuffle')

# --- 4. chống trùng toàn matrix (từng cột riêng; legacy expected_url == canonical
# là đúng theo thiết kế — không tính là trùng)
def slug_of(r):
    op = r['output_path']
    if '{date}' in op:
        return op.split('-', 1)[1][:-3]   # '{date}-slug.md'
    return os.path.basename(op)[11:-3]     # 'YYYY-MM-DD-slug.md'


seen = {'id': {}, 'slug': {}, 'output_path': {}, 'canonical_url': {}, 'expected_url': {}}
errs = []
for r in matrix1:
    for c in seen:
        v = r[c]
        if c == 'slug':
            v = slug_of(r)
            if r['status'] == 'BLOCKED':
                continue   # hàng BLOCKED đã bị chặn sản xuất vì trùng slug
        if not v:
            continue
        if r['source'].startswith('legacy:') and c == 'expected_url':
            continue  # legacy: expected_url == canonical_url (không phải trùng thật)
        if v in seen[c]:
            errs.append('%s trùng %s: %s' % (r['id'], c, v))
        seen[c][v] = r['id']
    kw_key = (r['child_id'], norm(r['primary_keyword']))
    it_key = (r['child_id'], norm(r['intent']))
    if r['status'] in ('PLANNED', 'WRITING', 'QA', 'PASS'):
        if norm(r['primary_keyword']) and kw_key in seen['id']:
            errs.append('primary_keyword trùng child %s' % r['id'])
        if norm(r['primary_keyword']):
            seen['id'][kw_key] = r['id']
        if it_key in seen['id']:
            errs.append('intent trùng child %s' % r['id'])
        seen['id'][it_key] = r['id']
check(not errs, 'chống trùng id/slug/URL/canonical/intent/keyword toàn matrix (%s)'
      % ('; '.join(errs[:3]) or 'PASS'))

# --- 5. chống spam: không hai hàng mở rộng trùng tiêu đề chuẩn hoá
exp_titles = set()
dup_titles = []
seed = json.load(open(os.path.join(work, 'data/state/matrix-seed.json'),
                     encoding='utf-8'))
n_exp = 0
for cid, spec in seed['children'].items():
    for r in spec.get('rows', []):
        if 'scores' in r:
            n_exp += 1
            t = norm(r['title'])
            if t in exp_titles:
                dup_titles.append(r['title'])
            exp_titles.add(t)
check(not dup_titles, 'không hai hàng mở rộng trùng tiêu đề chuẩn hoá (chống spam)')
check(n_exp > 0, 'seed có hàng mở rộng được ghi nhận: %d' % n_exp)

# --- 6. kế hoạch lô + schema v2
planned = [r for r in matrix1 if r['status'] == 'PLANNED']
ok_batch = all(r['batch_id'] == 'B%03d' % (i // 50 + 1)
               for i, r in enumerate(planned))
check(ok_batch, 'batch_id nhóm đúng 50 hàng PLANNED theo thứ tự id')
missing = [r['id'] for r in planned
           if not all(r[c].strip() for c in ('slug', 'search_intent', 'parent_hub',
                                             'child_cluster', 'cannibalization_key',
                                             'word_target', 'batch_id'))]
check(not missing, 'mọi hàng PLANNED có đủ cột schema v2 (%s)'
      % (missing[:3] or 'PASS'))
check(all(r['search_intent'] == r['intent'] for r in planned),
      'search_intent khớp intent trên mọi hàng PLANNED')
try:
    check(all(int(r['word_target']) >= 800 for r in planned),
          'word_target >= 800 trên mọi hàng PLANNED')
except ValueError:
    check(False, 'word_target phải là số')

# --- 7. expand KHÔNG hủy hàng seed cũ: mọi hàng cũ (không scores) vẫn còn
old_titles = set()
for cid, spec in seed['children'].items():
    for r in spec.get('rows', []):
        if 'scores' not in r:
            old_titles.add(norm(r['title']))
matrix_titles = {norm(r['title']) for r in matrix1
                  if r['status'] in ('PLANNED', 'WRITING', 'QA', 'PASS',
                                     'REPAIR', 'PUBLISHED', 'BLOCKED')}
lost = [t for t in old_titles if t not in matrix_titles]
check(not lost, 'hàng seed cũ không bị mất sau mở rộng (%s)' % (lost[:2] or 'PASS'))

print()
if FAILS:
    print('KẾT QUẢ: FAIL (%d)' % len(FAILS))
    sys.exit(1)
print('KẾT QUẢ: PASS (mở rộng idempotent, neo nguyên, chống trùng + chống spam PASS)')
