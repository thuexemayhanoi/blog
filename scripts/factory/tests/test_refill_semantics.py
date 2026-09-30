#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiem thu SEMANTIC refill (op refill phai tao work that).

Bug da sua (2026-09-30): factory-operator.py op_refill chi chay
'refill-queue.py' (khong doi so -> --plan, read-only) roi tra 0 —
workflow bao SUCCESS nhung queue KHONG BAO GIO co hang PLANNED moi
(planned=0, next_claimable_id=null). Hop dong moi (docs/PROC-PUBLISH.md):
  SUCCESS bat buoc: planned tang, matrix tang, seed tang,
  next_claimable_id != null, transaction inactive, lock sach.
  Het candidate STAGED -> NEEDS_TOPIC_EXPANSION (exit 1), KHONG filler.

Cac nhom test (temp fixture, KHONG cham production state):
  T1  happy path: candidate STAGED (tu sinh hermetic) -> op refill
      rc=0, seed/matrix/
      planned tang, next_claimable_id != null, txn inactive, lock sach,
      ledger STAGED -> MATERIALIZED
  T1b chong duplicate: id/slug/canonical/keyword/intent moi KHONG trung
      bat ky hang cu nao
  T2  ledger khong con candidate moi -> NEEDS_TOPIC_EXPANSION (rc=1),
      KHONG SUCCESS gia, state khong doi
  T3  refill lan hai tren cung fixture -> tu choi an toan, KHONG
      duplicate seed/matrix (idempotent)
  T4  HEAD doi giua critical section -> STOP, khong partial mutation,
      lock sach, candidate van STAGED (chua materialize)
  T5  gate G1-G8 fail -> STOP, seed/matrix/checkpoint/ledger nguyen ven,
      lock sach
  T6  writer-lock dang bi writer khac giu -> tu choi an toan, khong
      mutate, khong force-unlock
  T7  (regression chinh, ngam trong T1): neu operator quay lai chi chay
      'refill-queue.py' --plan roi bao thanh cong, planned se khong tang
      -> semantic postcondition FAIL -> op tra rc=1 -> T1 FAIL
  P   purity: toan bo suite KHONG lam ban production data/

Chay: python3 scripts/factory/tests/test_refill_semantics.py
"""
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

RESULTS = []
_COUNTER = [0]
_TMP_ROOTS = []
_CONST_HEADS = ['f1xTUREhEAD0001', 'f1xTUREhEAD0001']


def record(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print(('PASS: ' if ok else 'FAIL: ') + name
          + ((' - ' + detail) if detail else ''))


def tree_hash(path):
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        for fn in sorted(filenames):
            fp = os.path.join(dirpath, fn)
            h.update(os.path.relpath(fp, path).encode('utf-8'))
            h.update(open(fp, 'rb').read())
    return h.hexdigest()


def file_hash(path):
    if not os.path.exists(path):
        return None
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def _norm(s):
    s = unicodedata.normalize('NFD', s or '')
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def synth_candidates(work, n=3):
    """Candidate hop le G1-G8 tu sinh (hermetic): T1 khong phu thuoc
    production ledger (sau refill that ledger rong — operator verify
    full chay tren state moi phai van PASS)."""
    cap = json.load(open(os.path.join(
        work, 'data/factory-capacity.json'), encoding='utf-8'))
    tax = json.load(open(os.path.join(
        work, 'data/state/taxonomy-config.json'), encoding='utf-8'))
    tax2p = os.path.join(work, 'data/content-taxonomy.json')
    tax2 = json.load(open(tax2p, encoding='utf-8')) \
        if os.path.exists(tax2p) else {'children': []}
    rows = list(csv.DictReader(open(
        os.path.join(work, 'data/content-matrix.csv'),
        encoding='utf-8', newline='')))
    used = {}
    for r in rows:
        used[r['child_id']] = used.get(r['child_id'], 0) + 1
    kids2 = set(c['child_id'] for c in tax2['children'])
    cec = cap['child_editorial_capacity']
    kids = ([c[0] for c in tax['children'] if c[0] in kids2]
            if kids2 else [c[0] for c in tax['children']])
    kid = max(kids, key=lambda k: cec.get(k, 0) - used.get(k, 0))
    kw = set((r['child_id'], _norm(r['primary_keyword']))
             for r in rows if r['primary_keyword'])
    it = set((r['child_id'], _norm(r['intent']))
             for r in rows if r['intent'])
    titles = set(_norm(r['title']) for r in rows)
    outs = set(r['output_path'] for r in rows)
    cands = []
    i = 0
    while len(cands) < n:
        i += 1
        c = {'candidate_id': 'CAND-HERMETIC-%03d' % i,
             'child_id': kid,
             'title': 'Kiem thu hermetic refill lan %d' % i,
             'intent': 'y dang kiem thu hermetic %d' % i,
             'kw': 'hermetic refill kw %d' % i,
             'kw2': [], 'links': [], 'subtopic': 'hermetic-test',
             'audience': 'kiem thu tu dong', 'location_scope': 'Ha Noi',
             'word_target': 1200}
        if (_norm(c['title']) in titles
                or (kid, _norm(c['kw'])) in kw
                or (kid, _norm(c['intent'])) in it
                or ('_posts/{date}-%s.md'
                    % _norm(c['title']).replace(' ', '-')) in outs):
            continue
        cands.append(c)
    return cands


def make_fixture(ledger_candidates=None, head_seq=None):
    """Ban sao temp hoan chinh: op + engine + du lieu + _posts that.

    head_seq: monkeypatch git_head trong ban sao refill-queue.py (fixture
    khong can git) — co che giong test_refill_safety.py."""
    tmp = tempfile.mkdtemp(prefix='refill-semantics-')
    _TMP_ROOTS.append(tmp)
    work = os.path.join(tmp, 'repo')
    os.makedirs(os.path.join(work, 'data/state'))
    os.makedirs(os.path.join(work, 'scripts/factory'))
    for p in ('data/factory-capacity.json',
              'data/state/taxonomy-config.json',
              'data/state/refill-candidates.json',
              'data/state/matrix-seed.json',
              'data/state/transaction.json',
              'data/state/checkpoint.json',
              'data/content-matrix.csv',
              'data/content-taxonomy.json',
              'data/content-inventory.csv',
              'scripts/factory/refill-queue.py',
              'scripts/factory/factory-operator.py',
              'scripts/factory/publish-gate.py',
              'scripts/factory/queue.py',
              'scripts/factory/generate-matrix.py'):
        shutil.copy(os.path.join(ROOT, p), os.path.join(work, p))
    # generate-matrix.py liet ke _posts/ va ghi reports/factory/
    shutil.copytree(os.path.join(ROOT, '_posts'), os.path.join(work, '_posts'))
    os.makedirs(os.path.join(work, 'reports/factory'))
    if ledger_candidates is None:
        ledger_candidates = synth_candidates(work)
    p = os.path.join(work, 'data/state/refill-candidates.json')
    led = json.load(open(p, encoding='utf-8'))
    led['candidates'] = ledger_candidates
    json.dump(led, open(p, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    if head_seq is None:
        head_seq = _CONST_HEADS
    p = os.path.join(work, 'scripts/factory/refill-queue.py')
    src = open(p, encoding='utf-8').read()
    heads = json.dumps(list(head_seq))
    marker = "def git_head():"
    assert marker in src
    patch = ("import itertools as _it\n"
             "_HEAD_SEQ = %s\n"
             "_HEAD_ITER = _it.chain(_HEAD_SEQ, _it.repeat(_HEAD_SEQ[-1]))\n"
             "\n"
             "def git_head_orig():\n" % heads)
    src = src.replace(marker, patch, 1)
    # wrapper moi phai nam TRUOC block `if __name__ == '__main__'` —
    # subprocess chay file nay nhu __main__, main() goi git_head ngay.
    main_guard = "if __name__ == '__main__':"
    assert main_guard in src
    wrapper = ("def git_head():\n"
               "    return next(_HEAD_ITER)\n"
               "\n\n")
    idx = src.index(main_guard)
    src = src[:idx] + wrapper + src[idx:]
    open(p, 'w', encoding='utf-8').write(src)
    return work


def load_module(work, rel):
    _COUNTER[0] += 1
    spec = importlib.util.spec_from_file_location(
        'mod_under_test_%d' % _COUNTER[0], os.path.join(work, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # tu os.chdir(ROOT cua ban sao fixture
    return mod


def arm_hermetic(op):
    """Bypass validate.py / generate-reports.py (subprocess nang, ngoai
    pham vi semantic cua op refill); lock + checkpoint + refill-queue
    subprocess van CHAY THAT trong fixture."""
    def fake_preflight(require_clean_txn=True, scope='chunk'):
        txn = json.load(open('data/state/transaction.json',
                             encoding='utf-8'))
        assert not txn.get('active'), 'fixture txn phai inactive'
        cp = json.load(open('data/state/checkpoint.json',
                            encoding='utf-8'))
        return txn, cp, op.load_matrix()

    op.preflight = fake_preflight
    op.run_reports_checked = lambda ctx: 0
    op.validate_or_stop = lambda ctx, scope='chunk': 0


def snapshot(work):
    matrix = list(__import__('csv').DictReader(
        open(os.path.join(work, 'data/content-matrix.csv'),
             encoding='utf-8', newline='')))
    planned = [r['id'] for r in matrix if r['status'] == 'PLANNED']
    seed = json.load(open(os.path.join(work, 'data/state/matrix-seed.json'),
                          encoding='utf-8'))
    seed_rows = sum(len((s or {}).get('rows', []))
                    for s in (seed.get('children') or {}).values())
    led = json.load(open(
        os.path.join(work, 'data/state/refill-candidates.json'),
        encoding='utf-8'))
    cp = json.load(open(os.path.join(work, 'data/state/checkpoint.json'),
                        encoding='utf-8'))
    txn = json.load(open(os.path.join(work, 'data/state/transaction.json'),
                         encoding='utf-8'))
    return {
        'rows': len(matrix),
        'planned': planned,
        'ids': set(r['id'] for r in matrix),
        'slugs': set(r['slug'] for r in matrix),
        'canon': set(r['canonical_url'] for r in matrix),
        'kwkeys': set((r['child_id'], r['primary_keyword'].lower())
                      for r in matrix if r['primary_keyword']),
        'intents': set((r['child_id'], r['intent'].lower())
                       for r in matrix if r['intent']),
        'seed_rows': seed_rows,
        'staged': led.get('candidates') or [],
        'materialized': led.get('materialized') or [],
        'next_id': cp.get('next_claimable_id'),
        'cp_counts': dict(cp.get('counts') or {}),
        'txn_active': bool(txn.get('active')),
        'h_matrix': file_hash(os.path.join(work, 'data/content-matrix.csv')),
        'h_seed': file_hash(os.path.join(work, 'data/state/matrix-seed.json')),
        'h_ledger': file_hash(
            os.path.join(work, 'data/state/refill-candidates.json')),
        'h_cp': file_hash(os.path.join(work, 'data/state/checkpoint.json')),
    }


def lock_clean(work):
    sentinel = os.path.exists(
        os.path.join(work, 'data/state/writer-lock.active'))
    lj = os.path.join(work, 'data/state/writer-lock.json')
    meta = json.load(open(lj, encoding='utf-8')) if os.path.exists(lj) else {}
    return (not sentinel) and meta.get('locked') is not True


def run_op(work):
    op = load_module(work, 'scripts/factory/factory-operator.py')
    arm_hermetic(op)
    buf = io.StringIO()
    old_argv = sys.argv
    sys.argv = ['factory-operator.py', 'refill']
    try:
        with redirect_stdout(buf):
            rc = op.op_refill(None)
    finally:
        sys.argv = old_argv
    return rc, op, buf.getvalue()


def main():
    data_before = tree_hash(os.path.join(ROOT, 'data'))

    # ============ T1 + T7. HAPPY PATH: REFILL TAO WORK THAT ============
    # (T7 ngam: neu op chi chay --plan roi bao SUCCESS, planned se khong
    #  tang -> semantic postcondition FAIL -> rc=1 -> test nay FAIL)
    w1 = make_fixture()
    before1 = snapshot(w1)
    rc1, _op1, out1 = run_op(w1)
    after1 = snapshot(w1)
    new_planned = sorted(set(after1['planned']) - set(before1['planned']))
    record('T1a. op refill rc=0, planned 0 -> %d, matrix %d -> %d, '
           'seed %d -> %d' % (len(after1['planned']), after1['rows'],
                              before1['rows'], after1['seed_rows'],
                              before1['seed_rows']),
           rc1 == 0
           and len(after1['planned']) > len(before1['planned'])
           and after1['rows'] > before1['rows']
           and after1['seed_rows'] > before1['seed_rows'],
           'rc=%d planned=%d matrix=%d->%d seed=%d->%d'
           % (rc1, len(after1['planned']), before1['rows'], after1['rows'],
              before1['seed_rows'], after1['seed_rows']))
    record('T1b. next_claimable_id != null (%s), txn inactive, lock sach'
           % after1['next_id'],
           after1['next_id'] is not None
           and after1['next_id'] == (after1['planned'] or [None])[0]
           and after1['txn_active'] is False
           and lock_clean(w1),
           'next=%s txn_active=%s' % (after1['next_id'],
                                       after1['txn_active']))
    record('T1c. ledger STAGED %d -> %d, MATERIALIZED %d -> %d'
           % (len(before1['staged']), len(after1['staged']),
              len(before1['materialized']), len(after1['materialized'])),
           len(before1['staged']) > 0
           and len(after1['staged']) == 0
           and len(after1['materialized']) == len(before1['materialized'])
           + len(before1['staged']),
           'staged=%d->%d materialized=%d->%d'
           % (len(before1['staged']), len(after1['staged']),
              len(before1['materialized']), len(after1['materialized'])))
    record('T1d. checkpoint counts planned=%d, output co REFILL '
           'MATERIALIZED + materialize OK'
           % after1['cp_counts'].get('planned'),
           after1['cp_counts'].get('planned') == len(after1['planned'])
           and 'REFILL MATERIALIZED' in out1
           and 'materialize OK' in out1,
           'cp_planned=%r' % after1['cp_counts'].get('planned'))

    # T1e: chong duplicate — moi id/slug/canonical/kw/intent deu MOI
    new_ids = set(after1['ids']) - set(before1['ids'])
    matrix_after1 = list(__import__('csv').DictReader(
        open(os.path.join(w1, 'data/content-matrix.csv'),
             encoding='utf-8', newline='')))
    new_rows = [r for r in matrix_after1 if r['id'] in new_ids]
    dup_slug = [r['id'] for r in new_rows
                if r['slug'] in before1['slugs']]
    dup_canon = [r['id'] for r in new_rows
                 if r['canonical_url'] in before1['canon']]
    dup_kw = [r['id'] for r in new_rows
              if r['primary_keyword']
              and (r['child_id'], r['primary_keyword'].lower())
              in before1['kwkeys']]
    dup_it = [r['id'] for r in new_rows
              if r['intent']
              and (r['child_id'], r['intent'].lower())
              in before1['intents']]
    record('T1e. khong duplicate id/slug/canonical/keyword/intent '
           '(+%d hang moi)' % len(new_ids),
           len(new_ids) == len(before1['staged'])
           and not dup_slug and not dup_canon
           and not dup_kw and not dup_it,
           'new=%d dup(slug=%d canon=%d kw=%d intent=%d)'
           % (len(new_ids), len(dup_slug), len(dup_canon),
              len(dup_kw), len(dup_it)))

    # T1f: regression bug trượt id (2026-09-30): tái sinh sau khi chèn
    # candidate KHÔNG được đổi (id, title, status) của bat ky hàng cũ nào.
    # (fixture copy data/content-matrix.csv tu ROOT truoc khi chay.)
    matrix_before1 = list(__import__('csv').DictReader(
        open(os.path.join(ROOT, 'data/content-matrix.csv'),
             encoding='utf-8', newline='')))
    before_by_id = {r['id']: (r['title'], r['status'])
                    for r in matrix_before1}
    after_by_id1 = {r['id']: (r['title'], r['status'])
                    for r in matrix_after1}
    drift = [i for i, (t, s) in before_by_id.items()
             if i in after_by_id1 and after_by_id1[i] != (t, s)]
    record('T1f. moi hang cu giu nguyen (id, title, status) — '
           'regression truot id khi tai sinh',
           not drift, 'drift=%d %s' % (len(drift), drift[:5]))

    # ============ T3. REFILL LAN HAI: IDEMPOTENT, KHONG DUPLICATE ========
    rc3, _op3, out3 = run_op(w1)
    after3 = snapshot(w1)
    record('T3. refill lan hai: TU CHOI NEEDS_TOPIC_EXPANSION (rc=1), '
           'state giong het (khong duplicate)',
           rc3 == 1 and 'NEEDS_TOPIC_EXPANSION' in out3
           and after3['h_matrix'] == after1['h_matrix']
           and after3['h_seed'] == after1['h_seed']
           and after3['h_ledger'] == after1['h_ledger']
           and after3['h_cp'] == after1['h_cp']
           and len(after3['planned']) == len(after1['planned'])
           and lock_clean(w1),
           'rc=%d planned=%d' % (rc3, len(after3['planned'])))

    # ============ T2. HET CANDIDATE -> KHONG SUCCESS GIA ============
    w2 = make_fixture(ledger_candidates=[])
    before2 = snapshot(w2)
    rc2, _op2, out2 = run_op(w2)
    after2 = snapshot(w2)
    record('T2. ledger rong: NEEDS_TOPIC_EXPANSION (rc=1), khong mutate, '
           'lock sach',
           rc2 == 1 and 'NEEDS_TOPIC_EXPANSION' in out2
           and after2['h_matrix'] == before2['h_matrix']
           and after2['h_seed'] == before2['h_seed']
           and after2['h_ledger'] == before2['h_ledger']
           and after2['h_cp'] == before2['h_cp']
           and lock_clean(w2),
           'rc=%d' % rc2)

    # ============ T4. HEAD DOI GIUA CRITICAL SECTION ============
    w4 = make_fixture(head_seq=['AAA111', 'BBB222'])
    before4 = snapshot(w4)
    rq4 = load_module(w4, 'scripts/factory/refill-queue.py')
    cap4 = json.load(open(os.path.join(
        w4, 'data/factory-capacity.json'), encoding='utf-8'))
    tax4 = json.load(open(os.path.join(
        w4, 'data/state/taxonomy-config.json'), encoding='utf-8'))
    old_argv = sys.argv
    sys.argv = ['refill-queue.py', '--refill', '--yes']
    try:
        with redirect_stdout(io.StringIO()):
            rc4 = rq4.mode_refill(
                cap4, tax4, rq4.load_matrix(),
                json.load(open(rq4.LEDGER_PATH, encoding='utf-8')))
    finally:
        sys.argv = old_argv
    after4 = snapshot(w4)
    record('T4. HEAD doi giua refill: STOP (rc!=0), seed/matrix/ledger/'
           'checkpoint nguyen ven, candidate van STAGED, lock sach',
           rc4 != 0
           and after4['h_seed'] == before4['h_seed']
           and after4['h_matrix'] == before4['h_matrix']
           and after4['h_ledger'] == before4['h_ledger']
           and after4['h_cp'] == before4['h_cp']
           and len(after4['staged']) == len(before4['staged'])
           and len(after4['materialized'])
           == len(before4['materialized'])
           and lock_clean(w4),
           'rc=%d staged=%d materialized=%d'
           % (rc4, len(after4['staged']), len(after4['materialized'])))

    # ============ T5. GATE G1-G8 FAIL -> STOP, KHONG CORRUPT ============
    bad = [{'candidate_id': 'CAND-BAD-SEM-001',
            'child_id': 'C-KHONG-TON-TAI',
            'title': 'chu de sai child khong trung',
            'intent': 'intent bad khong trung',
            'kw': 'kw bad khong trung', 'word_target': 1300,
            'kw2': [], 'links': [], 'subtopic': '', 'audience': '',
            'location_scope': ''}]
    w5 = make_fixture(ledger_candidates=bad)
    before5 = snapshot(w5)
    rc5, _op5, out5 = run_op(w5)
    after5 = snapshot(w5)
    record('T5. gate fail: op rc=1, khong qua gate, seed/matrix/ledger/'
           'checkpoint nguyen ven, lock sach',
           rc5 == 1 and 'khong qua gate' in out5
           and after5['h_seed'] == before5['h_seed']
           and after5['h_matrix'] == before5['h_matrix']
           and after5['h_ledger'] == before5['h_ledger']
           and after5['h_cp'] == before5['h_cp']
           and lock_clean(w5),
           'rc=%d' % rc5)

    # ============ T6. CONCURRENT: WRITER KHAC DANG GIU KHOA ============
    w6 = make_fixture()
    before6 = snapshot(w6)
    os.makedirs(os.path.join(w6, 'data/state'), exist_ok=True)
    with open(os.path.join(w6, 'data/state/writer-lock.active'), 'w',
              encoding='utf-8') as f:
        f.write('t0k3n-cua-writer-khac')
    with open(os.path.join(w6, 'data/state/writer-lock.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'locked': True, 'holder': 'other-writer',
                   'action': 'write-chunk',
                   'token': 't0k3n-cua-writer-khac'}, f,
                  ensure_ascii=False, indent=2)
    r6 = subprocess.run(
        [sys.executable, 'scripts/factory/refill-queue.py',
         '--refill', '--yes'],
        capture_output=True, text=True, cwd=w6)
    after6 = snapshot(w6)
    sentinel6 = os.path.exists(
        os.path.join(w6, 'data/state/writer-lock.active'))
    record('T6. writer khac giu khoa: tu choi an toan (rc=1), khong '
           'mutate, khong force-unlock',
           r6.returncode == 1 and 'TU CHOI' in r6.stdout
           and after6['h_seed'] == before6['h_seed']
           and after6['h_matrix'] == before6['h_matrix']
           and after6['h_ledger'] == before6['h_ledger']
           and sentinel6,
           'rc=%d sentinel_cua_writer_khac_con=%s'
           % (r6.returncode, sentinel6))

    # ============ P. PURITY: PRODUCTION STATE KHONG DOI ============
    os.chdir(ROOT)
    data_after = tree_hash(os.path.join(ROOT, 'data'))
    record('P. production data/ nguyen ven sau toan bo suite',
           data_before == data_after)

    # cleanup temp fixtures
    for tmp in _TMP_ROOTS:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [r for r in RESULTS if not r[1]]
    print('\n%d/%d PASS' % (len(RESULTS) - len(failed), len(RESULTS)))
    if failed:
        print('SEMANTIC REFILL SUITE: FAIL')
        sys.exit(1)
    print('SEMANTIC REFILL SUITE: PASS')


if __name__ == '__main__':
    main()
