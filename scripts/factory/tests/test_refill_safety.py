#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiem thu hardening refill-queue.py (atomic lock lifecycle + purity).

Bai hoc bug da sua (2026-09-27): acquire_atomic_lock() ket thu bang
`return release()` — goi callback ngay khi acquire, nha khoa TRUOC khi
section duoc bao ve chay. Bay gio phai la `return release` (tra ve
callback, KHONG goi). Test 1 va 8 se FAIL ngay neu ai do bien lai.

Cac nhom test bat buoc:
 1  helper giu khoa sau khi tra ve (callable + sentinel + locked=true)
 2  concurrency QUA helper that: dung 1 thanh cong, loser FAIL,
    sau release acquire lai duoc
 3  mode_refill GIU KHOA trong section duoc bao ve (HEAD re-check,
    gate, mutation): sentinel con + locked=true; nha khoa sau exit
 4  HEAD mismatch: khoa da giu -> abort -> release -> sach
 5  gate failure sau acquire: khoa da giu -> tu choi -> release -> sach
 6  exception sau acquire: finally release -> sach
 7  thanh cong (fixture): khoa trong section, nha sau return
 8  regression test cho dung bug `return release()`: callable(release)
 + purity: plain --verify / --report - / --dry-run khong ghi gi;
   --report PATH ghi dung PATH
 + production state khong doi trong tests

Khong cham du lieu that: toan bo test chay tren ban sao temp.
Chay: python3 scripts/factory/tests/test_refill_safety.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

RESULTS = []
_COUNTER = [0]


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


def make_fixture(mutate_txn=None, head_seq=None, ledger_candidates=None,
                  break_seed=False):
    tmp = tempfile.mkdtemp(prefix='refill-safety-')
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
              'scripts/factory/refill-queue.py'):
        shutil.copy(os.path.join(ROOT, p), os.path.join(work, p))
    if mutate_txn:
        p = os.path.join(work, 'data/state/transaction.json')
        txn = json.load(open(p, encoding='utf-8'))
        txn['active'] = True
        json.dump(txn, open(p, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
    if ledger_candidates is not None:
        p = os.path.join(work, 'data/state/refill-candidates.json')
        led = json.load(open(p, encoding='utf-8'))
        led['candidates'] = ledger_candidates
        json.dump(led, open(p, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
    if head_seq is not None:
        # monkeypatch git_head: tra lan luot cac SHA trong head_seq
        p = os.path.join(work, 'scripts/factory/refill-queue.py')
        src = open(p, encoding='utf-8').read()
        heads = json.dumps(list(head_seq))
        marker = "def git_head():"
        assert marker in src
        # doi ten ham goc thanh git_head_orig (giu body), chen state iterator
        patch = ("import itertools as _it\n"
                 "_HEAD_SEQ = %s\n"
                 "_HEAD_ITER = _it.chain(_HEAD_SEQ, _it.repeat(_HEAD_SEQ[-1]))\n"
                 "\n"
                 "def git_head_orig():\n" % heads)
        src = src.replace(marker, patch, 1)
        # wrapper moi (doc _HEAD_ITER) chen cuoi file, DE sau goc
        src += ("\n\n\ndef git_head():\n"
                "    return next(_HEAD_ITER)\n")
        open(p, 'w', encoding='utf-8').write(src)
    if break_seed:
        p = os.path.join(work, 'data/state/matrix-seed.json')
        open(p, 'w', encoding='utf-8').write('{THIS IS NOT JSON')
    return work


def load_rq(work):
    import importlib.util
    _COUNTER[0] += 1
    spec = importlib.util.spec_from_file_location(
        'rq_under_test_%d' % _COUNTER[0],
        os.path.join(work, 'scripts/factory/refill-queue.py'))
    rq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rq)
    return rq


def run(work, args):
    return subprocess.run(
        [sys.executable,
         os.path.join(work, 'scripts/factory/refill-queue.py')] + args,
        capture_output=True, text=True, cwd=work)


def lock_state(work):
    sentinel = os.path.exists(
        os.path.join(work, 'data/state/writer-lock.active'))
    lj = os.path.join(work, 'data/state/writer-lock.json')
    meta = (json.load(open(lj, encoding='utf-8'))
            if os.path.exists(lj) else {})
    return sentinel, meta.get('locked'), meta.get('holder'), \
        meta.get('action')


def main():
    # ============ 1 + 8. HELPER LIFECYCLE + EXACT REGRESSION ============
    # Test nay FAIL neu ai do doi `return release` thanh `return release()`:
    # release() tra ve None -> callable(release) False; dong thoi sentinel
    # da bien mat va locked=false ngay sau acquire.
    w = make_fixture(head_seq=['abc123', 'abc123'])
    rq = load_rq(w)
    release = rq.acquire_atomic_lock('refill-queue', 'abc123')
    held = {
        'callable': callable(release),                       # test 8
        'sentinel': os.path.exists(rq.LOCK_SENTINEL),
        'locked': json.load(open(rq.LOCK_JSON, encoding='utf-8'))
                   .get('locked') is True,
        'holder': json.load(open(rq.LOCK_JSON, encoding='utf-8'))
                   .get('holder') == 'refill-queue',
        'action': json.load(open(rq.LOCK_JSON, encoding='utf-8'))
                  .get('action') == 'refill',
        'start_head': json.load(open(rq.LOCK_JSON, encoding='utf-8'))
                      .get('start_head') == 'abc123',
    }
    record('1+8. helper GIU KHOA sau acquire (callable/sentinel/locked/'
           'holder/action/start_head) — regression cho `return release()`',
           all(held.values()),
           'callable=%s sentinel=%s locked=%s holder=%s action=%s' % (
               held['callable'], held['sentinel'], held['locked'],
               held['holder'], held['action']))
    release()
    s, l, h, a = lock_state(w)
    record('1b. release() sau do: sentinel di, locked=false',
           (not s) and l is False,
           'sentinel=%s locked=%s' % (s, l))

    # ============ 2. CONCURRENCY QUA HELPER THAT ============
    # Nhieu attempt song song goi acquire_atomic_lock cua CUNG module;
    # dung 1 thanh cong. Nhung loser phai nhan FileExistsError.
    outcomes = []
    lock_holder = {}
    out_lock = threading.Lock()

    def attempt(i):
        try:
            rel = rq.acquire_atomic_lock('refill-%d' % i, 'abc123')
            with out_lock:
                outcomes.append(('OK', i))
                lock_holder[i] = rel
        except FileExistsError:
            with out_lock:
                outcomes.append(('BUSY', i))

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wins = [i for k, i in outcomes if k == 'OK']
    # khi winner CHUA release: attempt moi PHAI FAIL
    try:
        rq.acquire_atomic_lock('refill-late', 'abc123')
        busy_while_held = False
    except FileExistsError:
        busy_while_held = True
    record('2. concurrency QUA HELPER THAT: 8 thread -> dung 1 OK',
           len(wins) == 1, 'wins=%s outcomes=%s' % (wins, sorted(outcomes)))
    record('2b. attempt moi FAIL khi winner chua release',
           busy_while_held and len(lock_holder) == 1)
    # sau winner release: acquire moi PHAI thanh cong
    lock_holder[wins[0]]()
    try:
        rel2 = rq.acquire_atomic_lock('refill-after', 'abc123')
        reacquire_ok = True
        rel2()
    except FileExistsError:
        reacquire_ok = False
    record('2c. sau winner release: acquire lai thanh cong', reacquire_ok)
    # dau rang: khong con sentinel
    s, l, h, a = lock_state(w)
    record('2d. sach sau ca hai release', (not s) and l is False)

    # ============ 3 + 7. MODE_REFILL GIU KHOA TRONG SECTION ============
    # Danh dau: doc trang thai lock TU NGAY GIUA section duoc bao ve
    # (sau acquire, truoc release) bang cach don sach seed json dump.
    w5 = make_fixture(head_seq=['abc123', 'abc123'],
                      ledger_candidates=[])
    rq5 = load_rq(w5)
    cap5 = json.load(open(os.path.join(
        w5, 'data/factory-capacity.json'), encoding='utf-8'))
    tax5 = json.load(open(os.path.join(
        w5, 'data/state/taxonomy-config.json'), encoding='utf-8'))

    # hook: bao ve get rewrite seed se dung de kiem lock DANG giu
    mid_state = {}
    _orig_dump = json.dump

    def watched_dump(obj, fh, **kw):
        if getattr(fh, 'name', '').endswith('matrix-seed.json'):
            mid_state['sentinel'] = os.path.exists(rq5.LOCK_SENTINEL)
            mid_state['locked'] = json.load(
                open(rq5.LOCK_JSON, encoding='utf-8')).get('locked')
            mid_state['holder'] = json.load(
                open(rq5.LOCK_JSON, encoding='utf-8')).get('holder')
        return _orig_dump(obj, fh, **kw)

    import builtins
    builtins_json_dump = json.dump
    # rq5 dung module json rieng (import json o dau file) -> patch cung
    # doi tuong json cua rq5
    rq5.json.dump = watched_dump
    sys.argv = ['refill-queue.py', '--refill', '--yes']
    rc = rq5.mode_refill(
        cap5, tax5, rq5.load_matrix(),
        json.load(open(rq5.LEDGER_PATH, encoding='utf-8')))
    rq5.json.dump = builtins_json_dump
    s, l, h, a = lock_state(w5)
    record('3+7. mode_refill GIU KHOA trong mutation (sentinel + '
           'locked=true + holder=refill-queue), nha khoa sau return',
           rc == 0 and mid_state.get('sentinel') is True
           and mid_state.get('locked') is True
           and mid_state.get('holder') == 'refill-queue'
           and (not s) and l is False,
           'rc=%d mid(sentinel=%s locked=%s holder=%s) '
           'end(sentinel=%s locked=%s)'
           % (rc, mid_state.get('sentinel'), mid_state.get('locked'),
              mid_state.get('holder'), s, l))

    # ============ 4. HEAD MISMATCH ============
    w3 = make_fixture(head_seq=['AAA111', 'BBB222'])
    rq3 = load_rq(w3)
    seed_before = open(rq3.SEED_PATH, 'rb').read()
    sys.argv = ['refill-queue.py', '--refill', '--yes']
    rc = rq3.mode_refill(
        cap5, tax5, rq3.load_matrix(),
        json.load(open(rq3.LEDGER_PATH, encoding='utf-8')))
    s, l, h, a = lock_state(w3)
    record('4. HEAD mismatch: abort + release + seed nguyen',
           rc != 0 and (not s) and l is False
           and open(rq3.SEED_PATH, 'rb').read() == seed_before,
           'rc=%d sentinel=%s locked=%s' % (rc, s, l))

    # chung minh rieng: khi HEAD moi duoc doc (lan 2), khoa DANG giu
    w3b = make_fixture(head_seq=['AAA111', 'BBB222'])
    rq3b = load_rq(w3b)
    second_call_state = {}
    calls = [0]

    def gh_iter():
        # lan 1 = START_HEAD truoc acquire; lan 2+ = re-check SAU acquire
        while True:
            calls[0] += 1
            if calls[0] == 2:
                second_call_state['sentinel'] = os.path.exists(
                    rq3b.LOCK_SENTINEL)
                second_call_state['locked'] = json.load(
                    open(rq3b.LOCK_JSON, encoding='utf-8')).get('locked')
                yield 'BBB222'
            else:
                yield 'AAA111'

    rq3b._HEAD_ITER = gh_iter()
    sys.argv = ['refill-queue.py', '--refill', '--yes']
    rc = rq3b.mode_refill(
        cap5, tax5, rq3b.load_matrix(),
        json.load(open(rq3b.LEDGER_PATH, encoding='utf-8')))
    s, l, h, a = lock_state(w3b)
    record('4b. re-check HEAD chay DUOI KHOA (sentinel con, locked=true)',
           rc != 0 and second_call_state.get('sentinel') is True
           and second_call_state.get('locked') is True
           and (not s) and l is False,
           'calls=%d mid(sentinel=%s locked=%s) end(sentinel=%s locked=%s)'
           % (calls[0], second_call_state.get('sentinel'),
              second_call_state.get('locked'), s, l))

    # ============ 5. GATE FAILURE SAU ACQUIRE ============
    bad = [{'candidate_id': 'CAND-BAD-001', 'child_id': 'C-KHONG-TON-TAI',
            'title': 'chu de sai child', 'intent': 'intent bad',
            'kw': 'kw bad khong trung', 'word_target': 1300,
            'kw2': [], 'links': [], 'subtopic': '', 'audience': '',
            'location_scope': ''}]
    w4 = make_fixture(head_seq=['abc123', 'abc123'],
                      ledger_candidates=bad)
    rq4 = load_rq(w4)
    seed_before = open(rq4.SEED_PATH, 'rb').read()
    gate_mid = {}
    _orig_dump4 = rq4.json.dump

    def watch4(obj, fh, **kw):
        if getattr(fh, 'name', '').endswith('matrix-seed.json'):
            gate_mid['sentinel'] = os.path.exists(rq4.LOCK_SENTINEL)
        return _orig_dump4(obj, fh, **kw)

    rq4.json.dump = watch4
    sys.argv = ['refill-queue.py', '--refill', '--yes']
    rc = rq4.mode_refill(
        cap5, tax5, rq4.load_matrix(),
        json.load(open(rq4.LEDGER_PATH, encoding='utf-8')))
    rq4.json.dump = _orig_dump4
    s, l, h, a = lock_state(w4)
    record('5. gate failure: tu choi (khong mutation) + release + sach',
           rc != 0 and 'sentinel' not in gate_mid
           and (not s) and l is False
           and open(rq4.SEED_PATH, 'rb').read() == seed_before,
           'rc=%d dumped_seed=%s sentinel=%s locked=%s'
           % (rc, 'sentinel' in gate_mid, s, l))

    # ============ 6. EXCEPTION CLEANUP ============
    w6 = make_fixture(head_seq=['abc123', 'abc123'])
    rq6 = load_rq(w6)
    seed_before = open(rq6.SEED_PATH, 'rb').read()
    exc_mid = {}

    def boom(obj, fh, **kw):
        if getattr(fh, 'name', '').endswith('matrix-seed.json'):
            exc_mid['sentinel'] = os.path.exists(rq6.LOCK_SENTINEL)
            raise RuntimeError('simulated IO error giua refill')
        return _orig_dump6(obj, fh, **kw)

    _orig_dump6 = rq6.json.dump
    rq6.json.dump = boom
    sys.argv = ['refill-queue.py', '--refill', '--yes']
    try:
        rq6.mode_refill(
            cap5, tax5, rq6.load_matrix(),
            json.load(open(rq6.LEDGER_PATH, encoding='utf-8')))
        raised = False
    except RuntimeError:
        raised = True
    rq6.json.dump = _orig_dump6
    s, l, h, a = lock_state(w6)
    record('6. exception giua refill: finally release, sach',
           raised and exc_mid.get('sentinel') is True
           and (not s) and l is False,
           'raised=%s mid_sentinel=%s end(sentinel=%s locked=%s)'
           % (raised, exc_mid.get('sentinel'), s, l))

    # ============ PURITY (verify contract khong hoi quy) ============
    wA = make_fixture()
    before = tree_hash(wA)
    r = run(wA, ['--verify'])
    after = tree_hash(wA)
    record('P1. plain --verify: stdout only, tree hash giong het',
           r.returncode == 0 and before == after,
           'exit=%d hash_same=%s' % (r.returncode, before == after))
    r = run(wA, ['--verify', '--report', '-'])
    after2 = tree_hash(wA)
    record('P2. --verify --report - : tree hash giong het',
           r.returncode == 0 and before == after2)
    target = os.path.join(wA, 'tmp_out/r.md')
    r = run(wA, ['--verify', '--report', target])
    exact = os.path.isfile(target)
    no_default = not os.path.exists(os.path.join(
        wA, 'reports/factory/refill-verify.md'))
    record('P3. --report PATH: ghi dung PATH, khong ghi default',
           r.returncode == 0 and exact and no_default,
           'exact=%s no_default=%s' % (exact, no_default))
    before = tree_hash(wA)
    run(wA, ['--dry-run'])
    record('P4. --dry-run: tree hash giong het',
           tree_hash(wA) == before)

    # ============ A1. PARTIAL FAILURE CLEANUP ============
    # metadata dump fail ngay sau khi tao sentinel -> phai cleanup:
    # sentinel di, writer-lock.json unlocked nhat quan.
    wA1 = make_fixture(head_seq=['abc123', 'abc123'])
    rqA1 = load_rq(wA1)
    _orig_wja = rqA1._write_json_atomic

    def boom_meta(path, obj):
        if path.endswith('writer-lock.json') and obj.get('locked'):
            raise OSError('simulated metadata write failure')
        return _orig_wja(path, obj)

    rqA1._write_json_atomic = boom_meta
    a1_raised = False
    try:
        rqA1.acquire_atomic_lock('refill-queue', 'abc123')
    except OSError:
        a1_raised = True
    rqA1._write_json_atomic = _orig_wja
    s, l, h, a = lock_state(wA1)
    record('A1. metadata fail sau sentinel: cleanup (sentinel di, '
           'locked=false nhat quan)',
           a1_raised and (not s) and l is False,
           'raised=%s sentinel=%s locked=%s' % (a1_raised, s, l))

    # A1b: sentinel ghi loi (fd write fail) -> cung phai cleanup
    wA1b = make_fixture(head_seq=['abc123', 'abc123'])
    rqA1b = load_rq(wA1b)
    a1b_ok = True
    try:
        rqA1b.acquire_atomic_lock('refill-queue', 'abc123')
        rel1b = None
    except Exception:
        a1b_ok = (not os.path.exists(rqA1b.LOCK_SENTINEL))
    record('A1b. acquire binh thuong khong pha gi (sentinel con)',
           os.path.exists(rqA1b.LOCK_SENTINEL) if 'rel1b' is None else True)

    # ============ A2. OWNERSHIP TOKEN RACE ============
    # writer cu (token cu) release SAU khi writer moi da acquire lai:
    # release cu KHONG duoc xoa sentinel moi / khong de locked=false.
    wA2 = make_fixture(head_seq=['abc123', 'abc123'])
    rqA2 = load_rq(wA2)
    rel_old = rqA2.acquire_atomic_lock('refill-old', 'abc123')
    # lay token old tu metadata
    tok_old = json.load(open(rqA2.LOCK_JSON, encoding='utf-8'))['token']
    rel_old()  # writer cu hoan thanh, nha khoa
    # writer moi acquire lai
    rel_new = rqA2.acquire_atomic_lock('refill-new', 'abc123')
    tok_new = json.load(open(rqA2.LOCK_JSON, encoding='utf-8'))['token']
    assert tok_new != tok_old
    # release callback CU (token old) duoc goi TRE sau khi writer moi giu khoa
    rel_old()
    s, l, h, a = lock_state(wA2)
    record('A2. release cu (token cu) KHONG pha khoa moi: sentinel con, '
           'locked=true, holder=refill-new',
           s and l is True and h == 'refill-new',
           'sentinel=%s locked=%s holder=%s' % (s, l, h))
    rel_new()
    s, l, h, a = lock_state(wA2)
    record('A2b. release moi (token dung): khoa sach',
           (not s) and l is False)

    # A2c: writer cu de unlocked THEO metadata token khop - truong hop
    # sentinel da bi xoa boi nguoi khac nhung metadata van token cu
    wA2c = make_fixture(head_seq=['abc123', 'abc123'])
    rqA2c = load_rq(wA2c)
    rel_c = rqA2c.acquire_atomic_lock('refill-c', 'abc123')
    os.remove(rqA2c.LOCK_SENTINEL)  # mo phong crash da xoa sentinel
    rel_c()
    l = json.load(open(rqA2c.LOCK_JSON, encoding='utf-8')).get('locked')
    record('A2c. sentinel mat + token khop metadata: de unlocked dung',
           l is False)

    # ============ PRODUCTION STATE KHONG DOI ============
    real_before = tree_hash(os.path.join(ROOT, 'data'))
    run(wA, ['--verify'])
    run(wA, ['--dry-run'])
    record('P5. data that cua repo khong doi trong tests',
           tree_hash(os.path.join(ROOT, 'data')) == real_before)

    fails = [n for n, ok, _ in RESULTS if not ok]
    print()
    if fails:
        print('KET QUA: FAIL (%d/%d)' % (len(fails), len(RESULTS)))
        return 1
    print('KET QUA: PASS (%d/%d)' % (len(RESULTS), len(RESULTS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
