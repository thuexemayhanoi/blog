#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiem thu hoi quy su co drift checkpoint/matrix (BLG-01364, 2026-10-05)
+ refill bi ngat giua chung + concurrency workflow.

Bai hoc su co 2026-10-05: checkpoint planned=48, next_claimable=BLG-01364
trong khi matrix planned=0 (phan duoi push cua writer khong len kip).
validate.py FAIL-CLOSED chan tai 'Refill canonical'; nhung duong sua
lai la tay (sua truc tiep data/state/checkpoint.json) — de tai dien.

Cac nhom test (hermetic, toan bo chay tren ban sao temp — production
data/ KHONG BAO GIO bi thay doi):
 D1 checkpoint counts planned lech matrix (+2 va -3) -> validate
    FAIL-CLOSED 'lech matrix', khong mutate gi.
 D2 op `factory-operator.py repair-checkpoint` (canonical, 2026-10-05):
    hoi phuc counts + next_claimable_id tu matrix truth; matrix/seed/
    ledger nguyen ven; validate PASS; chay lan hai idempotent.
 D3 refill BI NGAT giua chung (matrix/seed da materialize nhung
    checkpoint chua duoc cap nhat — crash truoc phan duoi op):
    validate FAIL-CLOSED; op refill TU CHOI; repair-checkpoint hoi
    phuc; validate PASS; planned/seed DUNG nhu refill-queue da ghi
    (khong mat work that, khong materialize duplicate); refill lai ->
    NEEDS_TOPIC_EXPANSION (khong SUCCESS gia).
 D4 hop dong concurrency: factory-refill.yml va factory-publish.yml
    CUNG group `factory-publish`, cancel-in-progress: false (mot run
    xep hang cho run kia, khong huy nhau); refill trigger tren
    data/factory/refill-batches/** va refill-request.json.

Chay: python3 scripts/factory/tests/test_refill_drift.py
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_refill_semantics as base  # noqa: E402  (tai dung ROOT)

ROOT = base.ROOT
PY = sys.executable
RESULTS = []


def record(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print(('PASS: ' if ok else 'FAIL: ') + name
          + ((' - ' + detail) if detail else ''))


def file_hash(path):
    if not os.path.exists(path):
        return None
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def deaccent(s):
    s = unicodedata.normalize('NFD', s or '')
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def make_fixture():
    """Ban sao temp toan repo (tru .git/assets/anh) — du de chay validate
    + factory-operator + refill-queue THAT trong fixture."""
    tmp = tempfile.mkdtemp(prefix='refill-drift-')
    work = os.path.join(tmp, 'repo')
    shutil.copytree(ROOT, work,
                    ignore=shutil.ignore_patterns('.git', 'assets',
                                                  '*.jpeg', '*.png',
                                                  '*.jpg', '*.webp'))
    # git_head co dinh (fixture khong can git — dung co che giong
    # test_refill_safety/test_refill_semantics).
    p = os.path.join(work, 'scripts/factory/refill-queue.py')
    src = open(p, encoding='utf-8').read()
    marker = "def git_head():"
    assert marker in src
    patch = ("import itertools as _it\n"
             "_HEAD_SEQ = ['f1xTUREhEAD0001', 'f1xTUREhEAD0001']\n"
             "_HEAD_ITER = _it.chain(_HEAD_SEQ, _it.repeat(_HEAD_SEQ[-1]))\n"
             "\n"
             "def git_head_orig():\n")
    src = src.replace(marker, patch, 1)
    guard = "if __name__ == '__main__':"
    idx = src.index(guard)
    src = (src[:idx] + "def git_head():\n"
           "    return next(_HEAD_ITER)\n\n\n" + src[idx:])
    open(p, 'w', encoding='utf-8').write(src)
    return work


def pristine_snapshot(work):
    """Sao luu trang thai goc de restore giua cac test."""
    keep = {}
    for rel in ('data/state/checkpoint.json',
                'data/state/matrix-seed.json',
                'data/state/refill-candidates.json',
                'data/state/transaction.json',
                'data/state/writer-lock.json',
                'data/content-matrix.csv'):
        keep[rel] = open(os.path.join(work, rel), 'rb').read()
    return keep


def restore(work, keep):
    for rel, blob in keep.items():
        open(os.path.join(work, rel), 'wb').write(blob)


def run(work, *cmd):
    return subprocess.run([PY] + list(cmd), cwd=work,
                          capture_output=True, text=True)


def validate(work):
    return run(work, 'scripts/factory/validate.py', '--scope', 'chunk')


def matrix_planned(work):
    import csv
    rows = list(csv.DictReader(open(os.path.join(
        work, 'data/content-matrix.csv'), encoding='utf-8', newline='')))
    return sorted(r['id'] for r in rows if r['status'] == 'PLANNED')


def main():
    data_before = hashlib.sha256(
        open(os.path.join(ROOT, 'data/content-matrix.csv'), 'rb')
        .read()).hexdigest()
    work = make_fixture()
    keep = pristine_snapshot(work)
    cp_path = os.path.join(work, 'data/state/checkpoint.json')

    # ======== D1. DRIFT CAC HUONG -> validate FAIL-CLOSED ========
    for delta, tag in ((2, 'len'), (-3, 'xuong')):
        restore(work, keep)
        cp = json.load(open(cp_path, encoding='utf-8'))
        before_h = {p: file_hash(os.path.join(work, p)) for p in (
            'data/content-matrix.csv', 'data/state/matrix-seed.json',
            'data/state/refill-candidates.json')}
        cp['counts']['planned'] += delta
        json.dump(cp, open(cp_path, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        r = validate(work)
        after_h = {p: file_hash(os.path.join(work, p)) for p in before_h}
        leaked = [p for p in before_h if before_h[p] != after_h[p]]
        record('D1%s. counts.planned %+d -> validate FAIL-CLOSED '
               "'lech matrix', khong mutate matrix/seed/ledger"
               % (tag[0].upper(), delta),
               r.returncode != 0
               and 'lech matrix' in deaccent(r.stdout + r.stderr)
               and not leaked,
               'rc=%d leaked=%s' % (r.returncode, leaked or 'khong'))

    # ======== D2. repair-checkpoint HOI PHUC (canonical) ========
    restore(work, keep)
    cp = json.load(open(cp_path, encoding='utf-8'))
    planned_true = matrix_planned(work)
    cp['counts']['planned'] += 5          # drift
    cp['next_claimable_id'] = 'BLG-99999'  # drift
    json.dump(cp, open(cp_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    before_h = {p: file_hash(os.path.join(work, p)) for p in (
        'data/content-matrix.csv', 'data/state/matrix-seed.json',
        'data/state/refill-candidates.json')}
    r = run(work, 'scripts/factory/factory-operator.py',
            'repair-checkpoint')
    after_h = {p: file_hash(os.path.join(work, p)) for p in before_h}
    leaked = [p for p in before_h if before_h[p] != after_h[p]]
    cp2 = json.load(open(cp_path, encoding='utf-8'))
    rv = validate(work)
    record('D2a. repair-checkpoint hoi phuc counts+next_claimable theo '
           'matrix truth, matrix/seed/ledger nguyen ven',
           r.returncode == 0 and not leaked
           and cp2['counts']['planned'] == len(planned_true)
           and cp2['next_claimable_id'] == planned_true[0],
           'rc=%d planned=%d next=%s leaked=%s'
           % (r.returncode, cp2['counts']['planned'],
              cp2['next_claimable_id'], leaked or 'khong'))
    record('D2b. sau repair: validate chunk PASS', rv.returncode == 0,
           'rc=%d' % rv.returncode)
    r2 = run(work, 'scripts/factory/factory-operator.py',
             'repair-checkpoint')
    cp3 = json.load(open(cp_path, encoding='utf-8'))
    record('D2c. repair lan hai idempotent (counts + next_claimable '
           'khong doi them; chi updated_at di dong)',
           r2.returncode == 0
           and cp3['counts'] == cp2['counts']
           and cp3['next_claimable_id'] == cp2['next_claimable_id'],
           'rc=%d' % r2.returncode)

    # ======== D3. REFILL BI NGAT GIUA CHUNG ========
    restore(work, keep)
    # Inject candidate hop le (hermetic) vao ledger nhu stage da xong.
    cands = base.synth_candidates(work, n=2)
    for c in cands:  # validate yeu cau lien ket noi bo khac rong
        c['links'] = ['/thue-xe/']
    led_path = os.path.join(work, 'data/state/refill-candidates.json')
    led = json.load(open(led_path, encoding='utf-8'))
    led['candidates'] = cands
    json.dump(led, open(led_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    planned_before = matrix_planned(work)
    # Chay refill-queue THAT nhung bo qua phan duoi op (checkpoint) —
    # mo phong crash giua chung, dung nhu op_refill goi.
    rr = run(work, 'scripts/factory/refill-queue.py', '--refill', '--yes')
    planned_after = matrix_planned(work)
    record('D3a. refill-queue materialize work that (planned %d -> %d)'
           % (len(planned_before), len(planned_after)),
           rr.returncode == 0
           and len(planned_after) == len(planned_before) + 2,
           'rc=%d' % rr.returncode)
    # Checkpoint CHUA duoc cap nhat (crash sim) -> validate FAIL-CLOSED.
    rv = validate(work)
    record('D3b. checkpoint treo sau refill ngat -> validate '
           "FAIL-CLOSED 'lech matrix' (khong that lo work da tao)",
           rv.returncode != 0
           and 'lech matrix' in deaccent(rv.stdout + rv.stderr),
           'rc=%d' % rv.returncode)
    # op refill TU CHOI khi engine lech (preflight validate fail-closed).
    rop = run(work, 'scripts/factory/factory-operator.py', 'refill')
    record('D3c. op refill TU CHOI khi checkpoint lech matrix '
           '(fail-closed, khong khai thanh cong)',
           rop.returncode != 0
           and len(matrix_planned(work)) == len(planned_after),
           'rc=%d' % rop.returncode)
    # repair-checkpoint hoi phuc; validate PASS; work that khong mat.
    rrp = run(work, 'scripts/factory/factory-operator.py',
              'repair-checkpoint')
    cp4 = json.load(open(cp_path, encoding='utf-8'))
    rv2 = validate(work)
    led2 = json.load(open(led_path, encoding='utf-8'))
    record('D3d. repair-checkpoint hoi phuc sau refill ngat: counts '
           'dung matrix, next_claimable = ID moi, khong materialize '
           'duplicate',
           rrp.returncode == 0
           and cp4['counts']['planned'] == len(planned_after)
           and cp4['next_claimable_id'] in planned_after
           and not (led2.get('candidates') or [])
           and len(led2.get('materialized') or []) >= 2,
           'rc=%d next=%s' % (rrp.returncode, cp4['next_claimable_id']))
    record('D3e. sau repair: validate chunk PASS (engine lai chay '
           'duoc)', rv2.returncode == 0, 'rc=%d' % rv2.returncode)
    # Refill chay lai sau repair: ledger het candidate STAGED ->
    # NEEDS_TOPIC_EXPANSION (rc=1, khong filler) — khong bao SUCCESS gia.
    rre = run(work, 'scripts/factory/factory-operator.py', 'refill')
    record('D3f. refill lai sau repair: NEEDS_TOPIC_EXPANSION '
           '(het candidate staged, KHONG filler, KHONG SUCCESS gia)',
           rre.returncode != 0
           and 'NEEDS_TOPIC_EXPANSION' in rre.stdout,
           'rc=%d' % rre.returncode)

    # ======== D4. CONCURRENCY + TRIGGER HOP DONG WORKFLOW ========
    def yml(name):
        return open(os.path.join(ROOT, '.github/workflows', name),
                    encoding='utf-8').read()
    ref, pub = yml('factory-refill.yml'), yml('factory-publish.yml')
    grp = re.compile(r'group:\s*(\S+)').search(ref)
    grp_pub = re.compile(r'group:\s*(\S+)').search(pub)
    record('D4a. factory-refill va factory-publish CUNG concurrency '
           "group 'factory-publish'",
           grp and grp.group(1) == 'factory-publish'
           and grp_pub and grp_pub.group(1) == 'factory-publish',
           'refill=%s publish=%s'
           % (grp.group(1) if grp else None,
              grp_pub.group(1) if grp_pub else None))
    record('D4b. ca hai cancel-in-progress: false (run xep hang, khong '
           'huy nhau)',
           'cancel-in-progress: false' in ref
           and 'cancel-in-progress: false' in pub, '')
    record('D4c. refill trigger push refill-batches/** + '
           'refill-request.json (writer chi push batch + request, '
           'KHONG cham state)',
           "refill-batches/**" in ref.replace(' ', '')
           and 'refill-request.json' in ref, '')

    # ======== PU: production data nguyen ven ========
    data_after = hashlib.sha256(
        open(os.path.join(ROOT, 'data/content-matrix.csv'), 'rb')
        .read()).hexdigest()
    record('PU. production data/ khong doi sau toan bo suite',
           data_before == data_after, '')

    failed = [n for n, ok, _ in RESULTS if not ok]
    print('')
    print('TONG: %d/%d PASS' % (len(RESULTS) - len(failed), len(RESULTS)))
    for n, ok, d in RESULTS:
        if not ok:
            print('FAIL: %s %s' % (n, d))
    shutil.rmtree(os.path.dirname(work), ignore_errors=True)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
