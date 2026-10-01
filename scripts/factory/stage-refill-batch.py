#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# stage-refill-batch.py - writer-side topic-expansion STAGING (2026-10-01).
#
# Che do (Hop dong docs/ENGINE-RUNBOOK.md, docs/PROC-PUBLISH.md):
#   stage-refill-batch.py --all           stage moi batch trong
#                                        data/factory/refill-batches/*.json
#   stage-refill-batch.py --batch PATH    stage dung mot batch file
#   stage-refill-batch.py --selftest     kiem thu am, KHONG doi cay lam viec
#
# NGUYEN TAC (KHONG exception):
#   - Batch chi duoc STAGE vao ledger qua CUNG gate G1-G8
#     (scripts/factory/refill-queue.py --verify). Gate FAIL -> ROLLBACK
#     ledger nguyen ven, ::error + step summary, exit 1 (fail-closed).
#   - Idempotent theo candidate_id: da co trong candidates/materialized/
#     rejected -> SKIP (khong dup).
#   - KHONG gan ID bai, KHONG sua matrix/checkpoint, KHONG materialize
#     (materialize la viec cua refill-queue.py --refill --yes trong run).
#   - Bao cao verify chi in stdout (--report -): CI khong bao gio
#     commit bao cao (hop dong refill-queue.py).
import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
os.chdir(ROOT)

LEDGER_PATH = 'data/state/refill-candidates.json'
BATCH_DIR = 'data/factory/refill-batches'
MIN_WORD = 1200
REQUIRED = ('candidate_id', 'child_id', 'title', 'intent', 'kw', 'kw2',
            'links', 'subtopic', 'audience', 'location_scope', 'word_target')
VERIFY_CMD = [sys.executable, 'scripts/factory/refill-queue.py', '--verify',
              '--report', '-']


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def emit_summary(text):
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if not summary:
        return
    with open(summary, 'a', encoding='utf-8') as f:
        f.write(text)


def fail(msg):
    print('::error::stage-refill-batch: %s' % msg)
    emit_summary('\n## stage-refill-batch: FAIL\n\n- %s\n' % msg)
    sys.exit(1)


def check_schema(c, src):
    errs = []
    for k in REQUIRED:
        if k not in c:
            errs.append('%s: thieu truong %s' % (src, k))
    if errs:
        return errs
    if not isinstance(c['candidate_id'], str) or not c['candidate_id'].strip():
        errs.append('%s: candidate_id rong' % src)
    if not isinstance(c['child_id'], str) or not c['child_id'].strip():
        errs.append('%s: child_id rong' % src)
    for k in ('title', 'intent', 'kw', 'subtopic', 'audience',
              'location_scope'):
        if not isinstance(c[k], str) or not c[k].strip():
            errs.append('%s: truong %s rong' % (src, k))
    for k in ('kw2', 'links'):
        v = c[k]
        if not isinstance(v, list):
            errs.append('%s: truong %s phai la list' % (src, k))
            continue
        for x in v:
            if not isinstance(x, str) or not x.strip():
                errs.append('%s: %s co phan tu rong' % (src, k))
    wt = c['word_target']
    if isinstance(wt, bool) or not isinstance(wt, int) or wt < MIN_WORD:
        errs.append('%s: word_target phai la so nguyen >= %d (nhan %r)'
                    % (src, MIN_WORD, wt))
    if isinstance(c['links'], list):
        for ln in c['links']:
            if (not isinstance(ln, str) or not ln.startswith('/')
                    or not ln.endswith('/') or '..' in ln or ' ' in ln):
                errs.append('%s: link khong hop le: %r' % (src, ln))
    return errs


def stage(batch_files):
    with open(LEDGER_PATH, encoding='utf-8') as f:
        original = f.read()
    ledger = json.loads(original)
    known = set()
    for c in ledger.get('candidates', []):
        if isinstance(c, dict) and c.get('candidate_id'):
            known.add(c['candidate_id'])
    for m in ledger.get('materialized', []):
        if isinstance(m, dict) and m.get('candidate_id'):
            known.add(m['candidate_id'])
    for r in ledger.get('rejected', []):
        if isinstance(r, dict) and r.get('candidate_id'):
            known.add(r['candidate_id'])
    seen_local = set(known)
    staged_new, skipped, errors = [], 0, []
    for bf in batch_files:
        try:
            with open(bf, encoding='utf-8') as f:
                batch = json.load(f)
        except Exception as e:
            errors.append('%s: khong parse duoc JSON (%s)' % (bf, e))
            continue
        cands = batch.get('candidates') if isinstance(batch, dict) else None
        if not isinstance(cands, list) or not cands:
            errors.append('%s: batch khong co candidates[] hop le' % bf)
            continue
        for i, c in enumerate(cands, 1):
            src = '%s#%d' % (os.path.basename(bf), i)
            if not isinstance(c, dict):
                errors.append('%s: candidate khong phai object' % src)
                continue
            errors += check_schema(c, src)
            cid = c.get('candidate_id')
            if not isinstance(cid, str) or not cid.strip():
                continue
            if cid in seen_local:
                skipped += 1
                print('SKIP idempotent (da co trong ledger): %s' % cid)
                continue
            seen_local.add(cid)
            staged_new.append({k: c[k] for k in REQUIRED})
    if errors:
        for e in errors:
            print('::error::%s' % e)
        fail('batch loi schema - khong stage bat ky candidate nao')
    if not staged_new:
        print('KHONG co candidate moi (skip %d) - ledger giu nguyen.' % skipped)
        return 0
    ledger.setdefault('candidates', []).extend(staged_new)
    meta = ledger.setdefault('_meta', {})
    meta['status'] = 'STAGED'
    meta['staged_at'] = now_iso()
    meta['note'] = ('Staging tu data/factory/refill-batches/ boi '
                    'stage-refill-batch.py: candidate phai qua gate G1-G8 '
                    'cua refill-queue.py --verify; FAIL thi rollback nguyen '
                    'ven. Materialize boi refill-queue.py --refill --yes.')
    tmp = LEDGER_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, LEDGER_PATH)
    print('STAGED: +%d candidate vao ledger (skip %d) - chay gate G1-G8...' %
          (len(staged_new), skipped))
    proc = subprocess.run(VERIFY_CMD)
    if proc.returncode != 0:
        with open(LEDGER_PATH, 'w', encoding='utf-8') as f:
            f.write(original)
        fail('gate G1-G8 FAIL (rc=%d) - da ROLLBACK ledger nguyen ven; '
             'sua batch roi stage lai' % proc.returncode)
    emit_summary('\n## stage-refill-batch: OK\n\n- staged: %d candidate\n'
                 '- skipped (idempotent): %d\n- gate G1-G8: PASS (refill-queue.py --verify)\n'
                 % (len(staged_new), skipped))
    print('STAGE OK: %d candidate STAGED - cho op refill materialize.' %
          len(staged_new))
    return 0


def selftest():
    good = {'candidate_id': 'CAND-ST-SELFTEST-1', 'child_id': 'C-THUE-GIA',
            'title': 'Tieu de kiem thu hop le', 'intent': 'Y dinh kiem thu',
            'kw': 'tu khoa kiem thu', 'kw2': ['tu khoa phu'],
            'links': ['/bang-gia/'], 'subtopic': 'refill-selftest',
            'audience': 'nguoi kiem thu', 'location_scope': 'Ha Noi',
            'word_target': 1200}
    ok = True
    if check_schema(good, 'st1'):
        print('FAIL: candidate hop le bi bao loi')
        ok = False
    bad = dict(good, word_target=800)
    if not check_schema(bad, 'st2'):
        print('FAIL: word_target nong khong bi tu choi')
        ok = False
    bad = dict(good, links=['khong-co-slash'])
    if not check_schema(bad, 'st3'):
        print('FAIL: link sai khong bi tu choi')
        ok = False
    bad = {k: v for k, v in good.items() if k != 'kw2'}
    if not check_schema(bad, 'st4'):
        print('FAIL: thieu truong khong bi tu choi')
        ok = False
    bad = dict(good, word_target='1200')
    if not check_schema(bad, 'st5'):
        print('FAIL: word_target chuoi khong bi tu choi')
        ok = False
    print('SELFTEST stage-refill-batch: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main():
    args = sys.argv[1:]
    if '--selftest' in args:
        sys.exit(selftest())
    files = []
    if '--all' in args:
        files = sorted(glob.glob(os.path.join(BATCH_DIR, '*.json')))
    elif '--batch' in args and args.index('--batch') + 1 < len(args):
        files = [args[args.index('--batch') + 1]]
    else:
        print('cach dung: stage-refill-batch.py --all | --batch PATH | --selftest')
        sys.exit(2)
    if not files:
        print('KHONG co batch nao trong %s - khong co gi de stage.' % BATCH_DIR)
        sys.exit(0)
    sys.exit(stage(files))


if __name__ == '__main__':
    main()
