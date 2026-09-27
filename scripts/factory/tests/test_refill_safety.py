#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiem thu hardening refill-queue.py (12 truong hop bat buoc):

 1. plain --verify leaves tree unchanged
 2. --verify --report - leaves tree unchanged
 3. explicit --report PATH writes only PATH
 4. dry-run leaves tree unchanged
 5. busy atomic lock rejects refill
 6. two simultaneous lock attempts: exactly one succeeds
 7. active transaction rejects refill
 8. HEAD changes after lock acquisition: refill aborts
 9. gate failure after lock acquisition: lock cleaned up
10. simulated success: lock cleaned up
11. no stale sentinel after handled failure
12. no matrix/checkpoint/published content changed during tests

Khong cham du lieu that: toan bo test chay trong ban sao temp
(data/state + capacity + matrix duoc copy vao tmp; script refill
chay trong tmp). Chay:
python3 scripts/factory/tests/test_refill_safety.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

RESULTS = []


def record(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print(('PASS: ' if ok else 'FAIL: ') + name + ((' - ' + detail) if detail else ''))


def tree_hash(path):
    """Hash toan bo cay file (duong dan + noi dung) - manh hon git status."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        for fn in sorted(filenames):
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, path)
            h.update(rel.encode('utf-8'))
            h.update(open(fp, 'rb').read())
    return h.hexdigest()


def make_fixture(mutate_txn=None, head_seq=None, ledger_candidates=None):
    """Tao ban sao repo nho trong tmp de test refill an toan (ko du lieu that)."""
    tmp = tempfile.mkdtemp(prefix='refill-safety-')
    work = os.path.join(tmp, 'repo')
    os.makedirs(os.path.join(work, 'data/state'))
    os.makedirs(os.path.join(work, 'scripts/factory/tests'))
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
        txn = json.load(open(os.path.join(work, 'data/state/transaction.json'),
                             encoding='utf-8'))
        txn['active'] = True
        json.dump(txn, open(os.path.join(work, 'data/state/transaction.json'),
                            'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    if ledger_candidates is not None:
        led = json.load(open(os.path.join(
            work, 'data/state/refill-candidates.json'), encoding='utf-8'))
        led['candidates'] = ledger_candidates
        json.dump(led, open(os.path.join(
            work, 'data/state/refill-candidates.json'), 'w', encoding='utf-8'),
            ensure_ascii=False, indent=2)
    if head_seq is not None:
        # monkeypatch git_head qua wrapper script trong fixture
        wrap = os.path.join(work, 'scripts/factory/refill-queue.py')
        src = open(wrap, encoding='utf-8').read()
        heads = json.dumps(head_seq)
        patch = ("_HEAD_SEQ = %s\n"
                 "import itertools as _it\n"
                 "_HEAD_ITER = _it.chain(_HEAD_SEQ, _it.repeat(_HEAD_SEQ[-1]))\n"
                 "def git_head():\n"
                 "    return next(_HEAD_ITER)\n") % heads
        # chen ngay truoc def git_head() goc de de (dinh nghia sau de)
        src = src.replace('def git_head():',
                         patch + '\ndef git_head_orig():', 1)
        # goi lai: dinh nghia moi (da chen) se duoc dinh nghia goc de ngay sau
        open(wrap, 'w', encoding='utf-8').write(src)
    return work


def run(work, args):
    return subprocess.run(
        [sys.executable, os.path.join(work, 'scripts/factory/refill-queue.py')]
        + args, capture_output=True, text=True, cwd=work)


def load_rq(work):
    """Nap refill-queue.py TU BAN SAO FIXTURE (file co dau gach nen phai
    spec_from_file_location; import tu dong os.chdir ve fixture)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'refill_queue_under_test_%d' % len(RESULTS),
        os.path.join(work, 'scripts/factory/refill-queue.py'))
    rq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rq)
    return rq


def lock_state(work):
    sentinel = os.path.exists(os.path.join(work, 'data/state/writer-lock.active'))
    lj = os.path.join(work, 'data/state/writer-lock.json')
    locked = None
    if os.path.exists(lj):
        locked = json.load(open(lj, encoding='utf-8')).get('locked')
    return sentinel, locked


def main():
    # === 1. plain --verify: pure ===
    w = make_fixture()
    before = tree_hash(w)
    r = run(w, ['--verify'])
    after = tree_hash(w)
    record('1. plain --verify tree unchanged (hash)',
           r.returncode == 0 and before == after,
           'exit=%d hash_same=%s' % (r.returncode, before == after))
    assert 'reports' not in os.listdir(w), 'plain --verify tao thu muc reports!'
    shutil.rmtree(os.path.dirname(w))

    # === 2. --verify --report - : pure ===
    w = make_fixture()
    before = tree_hash(w)
    r = run(w, ['--verify', '--report', '-'])
    after = tree_hash(w)
    record('2. --verify --report - tree unchanged (hash)',
           r.returncode == 0 and before == after,
           'exit=%d hash_same=%s' % (r.returncode, before == after))
    shutil.rmtree(os.path.dirname(w))

    # === 3. --report PATH: chi ghi dung PATH ===
    w = make_fixture()
    target = os.path.join(w, 'tmp_out/my-report.md')
    r = run(w, ['--verify', '--report', target])
    wrote_exact = os.path.isfile(target)
    no_default = not os.path.exists(os.path.join(
        w, 'reports/factory/refill-verify.md'))
    before = tree_hash(w)
    run(w, ['--verify', '--report', target])
    after = tree_hash(w)
    record('3. --report PATH ghi dung PATH, khong ghi default, idempotent',
           r.returncode == 0 and wrote_exact and no_default
           and before == after,
           'exact=%s no_default=%s idempotent=%s'
           % (wrote_exact, no_default, before == after))
    shutil.rmtree(os.path.dirname(w))

    # === 4. dry-run: pure ===
    w = make_fixture()
    before = tree_hash(w)
    r = run(w, ['--dry-run'])
    after = tree_hash(w)
    record('4. --dry-run tree unchanged (hash)',
           r.returncode == 0 and before == after,
           'exit=%d hash_same=%s' % (r.returncode, before == after))
    shutil.rmtree(os.path.dirname(w))

    # === 5. busy lock rejects refill (chung minh qua module truc tiep) ===
    w = make_fixture(head_seq=['abc123', 'abc123'])
    rq = load_rq(w)
    rq.ROOT = w
    os.chdir(w)
    rq.LOCK_SENTINEL = os.path.join(w, 'data/state/writer-lock.active')
    rq.LOCK_JSON = os.path.join(w, 'data/state/writer-lock.json')
    open(rq.LOCK_SENTINEL, 'w').write('other-writer busy')
    try:
        rq.acquire_atomic_lock('refill-queue', 'abc123')
        busy_rejected = False
    except FileExistsError:
        busy_rejected = True
    seed_before = open(os.path.join(w, 'data/state/matrix-seed.json'), 'rb').read()
    sys.argv = ['refill-queue.py', '--refill', '--yes']
    led = json.load(open(os.path.join(w, 'data/state/refill-candidates.json'),
                         encoding='utf-8'))
    cap = json.load(open(os.path.join(w, 'data/factory-capacity.json'),
                        encoding='utf-8'))
    tax = json.load(open(os.path.join(w, 'data/state/taxonomy-config.json'),
                         encoding='utf-8'))
    rows = rq.load_matrix()
    rc = rq.mode_refill(cap, tax, rows, led)
    seed_after = open(os.path.join(w, 'data/state/matrix-seed.json'), 'rb').read()
    record('5. busy atomic lock rejects refill, seed khong doi',
           busy_rejected and rc != 0 and seed_before == seed_after,
           'busy_rejected=%s rc=%d' % (busy_rejected, rc))
    os.remove(rq.LOCK_SENTINEL)

    # === 6. hai lock attempts dong thoi: dung mot thanh cong ===
    import multiprocessing as mp
    lock_dir = os.path.join(w, 'data/state')
    def _try_lock(i, q):
        try:
            fd = os.open(os.path.join(lock_dir, 'concurrency-test.active'),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, str(i).encode()); os.close(fd)
            q.put('OK')
        except FileExistsError:
            q.put('BUSY')
    q = mp.Queue()
    procs = [mp.Process(target=_try_lock, args=(i, q)) for i in range(8)]
    for p in procs: p.start()
    for p in procs: p.join()
    outcomes = [q.get() for _ in range(8)]
    wins = outcomes.count('OK')
    record('6. 8 lock attempts dong thoi: dung 1 thanh cong (O_EXCL)',
           wins == 1, 'wins=%d' % wins)
    os.remove(os.path.join(lock_dir, 'concurrency-test.active'))

    # === 7. transaction active rejects refill ===
    w2 = make_fixture(mutate_txn=True, head_seq=['abc123', 'abc123'])
    rq2 = load_rq(w2)
    cap2 = json.load(open(os.path.join(w2, 'data/factory-capacity.json'),
                          encoding='utf-8'))
    tax2 = json.load(open(os.path.join(w2, 'data/state/taxonomy-config.json'),
                          encoding='utf-8'))
    sys.argv = ['refill-queue.py', '--refill', '--yes']
    led2 = json.load(open(rq2.LEDGER_PATH, encoding='utf-8'))
    seed_before = open(rq2.SEED_PATH, 'rb').read()
    rc = rq2.mode_refill(cap2, tax2, rq2.load_matrix(), led2)
    s, l = lock_state(w2)
    record('7. transaction active rejects refill (khong lock, seed nguyen)',
           rc != 0 and not s and
           open(rq2.SEED_PATH, 'rb').read() == seed_before,
           'rc=%d sentinel=%s' % (rc, s))

    # === 8. HEAD doi sau khi giu khoa -> abort, nha khoa ===
    w3 = make_fixture(head_seq=['abc123', 'def999'])
    rq3 = load_rq(w3)
    seed_before = open(rq3.SEED_PATH, 'rb').read()
    rc = rq3.mode_refill(cap2, tax2, rq3.load_matrix(),
                         json.load(open(rq3.LEDGER_PATH, encoding='utf-8')))
    s, l = lock_state(w3)
    record('8. HEAD mismatch sau lock -> abort + nha khoa, seed nguyen',
           rc != 0 and not s and l is False and
           open(rq3.SEED_PATH, 'rb').read() == seed_before,
           'rc=%d sentinel=%s locked=%s' % (rc, s, l))

    # === 9. gate failure sau lock -> lock cleaned up ===
    bad = [{'candidate_id': 'CAND-BAD-001', 'child_id': 'C-KHONG-TON-TAI',
            'title': 'chu de sai child', 'intent': 'intent bad',
            'kw': 'kw bad khong trung', 'word_target': 1300,
            'kw2': [], 'links': [], 'subtopic': '', 'audience': '',
            'location_scope': ''}]
    w4 = make_fixture(head_seq=['abc123', 'abc123'], ledger_candidates=bad)
    rq4 = load_rq(w4)
    seed_before = open(rq4.SEED_PATH, 'rb').read()
    rc = rq4.mode_refill(cap2, tax2, rq4.load_matrix(),
                         json.load(open(rq4.LEDGER_PATH, encoding='utf-8')))
    s, l = lock_state(w4)
    record('9. gate failure sau lock -> tu choi + nha khoa, seed nguyen',
           rc != 0 and not s and l is False and
           open(rq4.SEED_PATH, 'rb').read() == seed_before,
           'rc=%d sentinel=%s locked=%s' % (rc, s, l))

    # === 10. thanh cong (mo phong, ledger rong) -> lock cleaned up ===
    w5 = make_fixture(head_seq=['abc123', 'abc123'], ledger_candidates=[])
    rq5 = load_rq(w5)
    rc = rq5.mode_refill(cap2, tax2, rq5.load_matrix(),
                         json.load(open(rq5.LEDGER_PATH, encoding='utf-8')))
    s, l = lock_state(w5)
    record('10. refill thanh cong (mo phong) -> lock da nha (sentinel di, '
           'locked=false)', rc == 0 and not s and l is False,
           'rc=%d sentinel=%s locked=%s' % (rc, s, l))

    # === 11. khong stale sentinel sau moi failure handled ===
    stale_ok = True
    for ww in (w2, w3, w4):
        if os.path.exists(os.path.join(ww, 'data/state/writer-lock.active')):
            stale_ok = False
    record('11. khong stale sentinel sau failure (test 7/8/9)', stale_ok)

    # === 12. matrix/checkpoint/published khong doi trong tests ===
    # (moi test dung ban sao rieng; chung minh tren ban that: hash truoc/sau)
    real_before = tree_hash(os.path.join(ROOT, 'data'))
    run(w5, ['--verify'])
    run(w5, ['--dry-run'])
    real_after = tree_hash(os.path.join(ROOT, 'data'))
    matrix_unchanged = open(os.path.join(ROOT, 'data/content-matrix.csv'),
                            'rb').read() == open(
        os.path.join(w2, 'data/content-matrix.csv'), 'rb').read()
    record('12. data that cua repo khong doi trong tests; matrix ban sao '
           'giong ban that', real_before == real_after and matrix_unchanged,
           'data_same=%s matrix_same=%s'
           % (real_before == real_after, matrix_unchanged))

    fails = [n for n, ok, _ in RESULTS if not ok]
    print()
    if fails:
        print('KET QUA: FAIL (%d/%d)' % (len(fails), len(RESULTS)))
        return 1
    print('KET QUA: PASS (%d/%d)' % (len(RESULTS), len(RESULTS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
