#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""factory-queue.py — CANONICAL write-ahead queue processor của /blog.

Port từ /vanchinh scripts/factory_queue.py (SOURCE OF TRUTH), thay thế
KHỚP khối consume Python inline của .github/workflows/factory-publish.yml
(một nguồn sự thật duy nhất — workflow chỉ orchestration, KHÔNG giữ
implementation queue thứ hai trong YAML).

Input (do CANONICAL selector scripts/factory/push-selection.py chọn từ
push — queue 2..10, exact article_id, matrix order, refuse fail-closed):
  python3 scripts/factory/factory-queue.py run \
      --ids BLG-001,BLG-002,... --mode new|repair [--pair-size 2]

Hợp đồng tiêu thụ (port NGUYÊN semantics inline cũ của factory-publish.yml):
  queue -> deterministic PAIRS of 2 (pair cuối 1 ID khi queue lẻ)
  -> pair: claim exact PLANNED subset (prepare-next --scope fast)
           -> scoped QA fast (threshold 75/70, KHÔNG hạ)
           -> transactional publish PASS only (publish --scope fast)
           -> checkpoint (report rewrite sau TỪNG pair — crash-resume)
  -> pair kế. Publisher concurrency = 1.

Safety:
  - fail-closed TRƯỚC mutation: transaction active / engine writer-lock
    còn tồn tại / queue trùng ID / ID lạ / hàng PUBLISHED-EXISTING-
    BLOCKED / > 10 ID / draft thiếu file trong _drafts/ -> refuse,
    KHÔNG đổi gì (exit 1);
  - MỘT queue-level run lock (data/state/factory-queue.active, O_EXCL)
    giữ xuyên suốt CẢ queue — lock đã bị giữ -> refuse (exit 1);
    engine writer-lock của từng op (prepare/qa/publish) tách bạch và vẫn
    transactional đúng engine canonical;
  - pair FAIL không BAO GIỜ rollback pair đã publish;
  - pair FAIL content (mọi trạng thái pair về REPAIR/PASS) = recoverable
    + engine resume-first: các pair PLANNED sau DEFERRED sang lần chạy
    kế (repair-first), KHÔNG nửa vời;
  - pair FAIL hạ tầng (claim/QA infra) = FATAL: dừng NGAY queue, báo
    rõ, exit 1 — pair đã publish GIỮ NGUYÊN (workflow fail trước commit
    step; draft còn xếp hàng trên main, lần push kế retry);
  - KHÔNG full-site audit trong hot path (mọi op gọi --scope fast;
    light matrix smoke là step riêng của workflow);
  - KHÔNG AI, KHÔNG API, KHÔNG secrets, KHÔNG git push (commit/push
    thuộc workflow), KHÔNG force push.

Report: reports/factory/factory-queue-last-run.json (env
FACTORY_QUEUE_REPORT) — deterministic, rewrite sau từng pair, đủ
checkpoint để crash-resume; summary {published, recoverable, deferred,
fatal} ghi /tmp/queue-summary.json (env FACTORY_QUEUE_SUMMARY) cho
step "Queue run summary" của workflow; step outputs GITHUB_OUTPUT
published_ids/recoverable_ids/deferred_ids giữ nguyên interface.

Thoát: 0 = queue đã xử lý (published hoặc recoverable); 1 = fatal /
refuse (KHÔNG đổi gì khi refuse).
"""
import argparse
import csv
import glob
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATRIX = 'data/content-matrix.csv'
TXN = 'data/state/transaction.json'
ENGINE_LOCK = 'data/state/writer-lock.active'
QUEUE_LOCK = 'data/state/factory-queue.active'
QUEUE_LOCK_META = 'data/state/factory-queue.json'
OP = 'scripts/factory/factory-operator.py'

PAIR_SIZE = 2          # hợp đồng turbo queue: pair 2 bài
MAX_QUEUE = 10         # tối đa 10 ID/queue run (lease limit mỗi writer)
LOCKED_STATUSES = ('PUBLISHED', 'EXISTING', 'BLOCKED')
RECOVERABLE = ('REPAIR', 'PASS')

REPORT = os.environ.get(
    'FACTORY_QUEUE_REPORT',
    os.path.join(ROOT, 'reports', 'factory', 'factory-queue-last-run.json'))
SUMMARY = os.environ.get('FACTORY_QUEUE_SUMMARY', '/tmp/queue-summary.json')


class QueueLockHeld(Exception):
    """Run-lock queue đã bị tiến trình khác giữ — fail-closed."""


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def load_rows():
    with open(os.path.join(ROOT, MATRIX), encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def status_map(rows):
    return {r['id']: r['status'] for r in rows}


def split_pairs(queue, pair_size=PAIR_SIZE):
    """Chia queue deterministic thành các pair `pair_size` (pair cuối
    có thể ngắn hơn khi queue lẻ) — KHÔNG đụng thứ tự matrix."""
    if pair_size < 1:
        raise ValueError('pair_size phai >= 1')
    return [queue[i:i + pair_size] for i in range(0, len(queue), pair_size)]


def draft_missing(rows):
    """ID hàng nào KHÔNG còn draft _drafts/<date>-<slug>.md (từ
    output_path _posts/{date}-<slug>.md) — KHÔNG thể QA/publish."""
    missing = []
    for r in rows:
        out = r['output_path'] or ''
        prefix = '_posts/{date}-'
        if not out.startswith(prefix) or not out.endswith('.md'):
            missing.append(r['id'])
            continue
        slug = out[len(prefix):-len('.md')]
        if not glob.glob(os.path.join(ROOT, '_drafts', '*-' + slug + '.md')):
            missing.append(r['id'])
    return missing


def validate_queue(ids):
    """Revalidate TRƯỚC mutation (fresh repository truth). Trả
    (queue, None) hoặc (None, lý do refuse). queue = matrix order."""
    rows = load_rows()
    by_id = {r['id']: r for r in rows}
    order = {r['id']: i for i, r in enumerate(rows)}
    seen = set()
    for a in ids:
        if a in seen:
            return None, 'id trung nhau trong queue: %s' % a
        seen.add(a)
    if len(ids) > MAX_QUEUE:
        return None, ('%d id > toi da %d cua mot queue run'
                      % (len(ids), MAX_QUEUE))
    for a in ids:
        r = by_id.get(a)
        if r is None:
            return None, '%s: khong co trong matrix' % a
        if r['status'] in LOCKED_STATUSES:
            return None, ('%s: trang thai %s — khong duoc sua lai'
                          % (a, r['status']))
    miss = draft_missing([by_id[a] for a in ids])
    if miss:
        return None, 'id chua co draft trong _drafts/: %s' % ','.join(miss)
    return sorted(ids, key=lambda a: order[a]), None


def acquire_queue_lock():
    """MỘT run-lock cho TOÀN queue run (O_EXCL — hai tiến trình không
    thể cùng tạo sentinel -> không race). Trả release()."""
    lock_path = os.path.join(ROOT, QUEUE_LOCK)
    meta_path = os.path.join(ROOT, QUEUE_LOCK_META)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        raise QueueLockHeld('factory-queue run-lock dang giu (%s) — '
                            'tu choi, KHONG chay song song' % QUEUE_LOCK)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write('%s %s\n' % (_now(), os.getpid()))
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump({'held_at': _now(), 'pid': os.getpid(),
                   'sentinel': QUEUE_LOCK}, f, ensure_ascii=False, indent=2)

    def release():
        for p in (meta_path, lock_path):
            try:
                os.remove(p)
            except OSError:
                pass
    return release


def write_state(state):
    """Rewrite report (canonical, đầy đủ) + summary (interface workflow)
    — deterministic sau TỪNG pair: đủ checkpoint để crash-resume."""
    for path, payload in ((REPORT, state),
                          (SUMMARY, {'published': state['published'],
                                     'recoverable': state['recoverable'],
                                     'deferred': state['deferred'],
                                     'fatal': state['fatal']})):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def github_output(state):
    gout = os.environ.get('GITHUB_OUTPUT')
    if not gout:
        return
    with open(gout, 'a', encoding='utf-8') as f:
        f.write('published_ids=%s\n' % ','.join(state['published']))
        f.write('recoverable_ids=%s\n' % ','.join(state['recoverable']))
        f.write('deferred_ids=%s\n' % ','.join(state['deferred']))


def _op(args):
    return subprocess.run([sys.executable, OP] + args, cwd=ROOT,
                          check=True)


def run_queue(mode, ids, pair_size=PAIR_SIZE):
    started = _now()
    # fail-closed TRƯỚC mutation: transaction active -> refuse
    with open(os.path.join(ROOT, TXN), encoding='utf-8') as f:
        txn = json.load(f) or {}
    if txn.get('active'):
        print(json.dumps({'error': 'transaction active con ton tai (%s) — '
                          'recover truoc khi chay queue' % txn.get('pending'),
                          'mode': mode}))
        return 1
    # fail-closed: engine writer-lock còn tồn tại (stale lock) -> refuse
    if os.path.exists(os.path.join(ROOT, ENGINE_LOCK)):
        print(json.dumps({'error': 'writer lock con ton tai (stale lock) — '
                          'recover truoc khi chay queue',
                          'mode': mode}))
        return 1
    queue, err = validate_queue(ids)
    if err is not None:
        print(json.dumps({'error': 'refusing queue: %s' % err,
                          'mode': mode}, ensure_ascii=False))
        return 1
    pairs = split_pairs(queue, pair_size)
    state = {'schema_version': '1', 'mode': mode, 'queue': queue,
             'pair_size': pair_size, 'started': started, 'finished': None,
             'pairs': [], 'published': [], 'recoverable': [],
             'deferred': [], 'fatal': None}
    write_state(state)
    try:
        release = acquire_queue_lock()
    except QueueLockHeld as e:
        state['fatal'] = str(e)
        write_state(state)
        print(json.dumps({'error': str(e)}, ensure_ascii=False))
        return 1
    blocked = False
    try:
        for idx, pair in enumerate(pairs, 1):
            label = ','.join(pair)
            entry = {'pair_index': idx, 'ids': pair, 'status': 'pending'}
            state['pairs'].append(entry)
            write_state(state)
            st = {i: s for i, s in status_map(load_rows()).items()
                  if i in pair}
            if blocked and any(v == 'PLANNED' for v in st.values()):
                # engine resume-first: sau pair FAIL content KHÔNG claim
                # thêm bài mới — pair PLANNED còn lại DEFERRED lần kế
                state['deferred'].extend(pair)
                entry['status'] = 'deferred'
                write_state(state)
                print('pair %s: DEFERRED (engine resume-first — hoan '
                      'tat repair truoc)' % label)
                continue
            try:
                planned = [i for i in pair if st[i] == 'PLANNED']
                if planned:
                    _op(['prepare-next', '--ids', ','.join(planned),
                         '--scope', 'fast'])
                _op(['qa', '--ids', label, '--scope', 'fast'])
                _op(['publish', '--ids', label, '--scope', 'fast'])
                state['published'].extend(pair)
                entry['status'] = 'published'
                print('pair %s: PUBLISHED' % label)
            except subprocess.CalledProcessError as e:
                st2 = {i: s for i, s in
                       status_map(load_rows()).items() if i in pair}
                content_fail = all(v in RECOVERABLE for v in st2.values())
                if content_fail:
                    state['recoverable'].extend(pair)
                    blocked = True
                    entry['status'] = 'recoverable'
                    print('pair %s: FAIL content (recoverable, can '
                          'repair push) rc=%s' % (label, e.returncode))
                else:
                    state['fatal'] = 'pair %s rc=%s' % (label, e.returncode)
                    entry['status'] = 'fatal'
                    write_state(state)
                    print('pair %s: FATAL rc=%s — dung ngay, khong tiep '
                          'tuc pair ke' % (label, e.returncode))
                    return 1
            write_state(state)
    finally:
        state['finished'] = _now()
        write_state(state)
        github_output(state)
        release()
    print('BLOG_FACTORY_QUEUE ' + json.dumps(
        {'mode': mode, 'queue': queue, 'pairs': len(pairs),
         'published': state['published'],
         'recoverable': state['recoverable'],
         'deferred': state['deferred'], 'fatal': state['fatal'],
         'report': REPORT}, ensure_ascii=False))
    print('queue done: published=%s recoverable=%s deferred=%s'
          % (state['published'], state['recoverable'], state['deferred']))
    return 0


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('command', choices=['run'])
    ap.add_argument('--ids', required=True,
                    help='danh sách id phân tách dấu phẩy (matrix order '
                         'revalidated trước mutation)')
    ap.add_argument('--mode', choices=['new', 'repair'], required=True)
    ap.add_argument('--pair-size', type=int, default=PAIR_SIZE)
    args = ap.parse_args()
    os.chdir(ROOT)
    ids = [v.strip() for v in args.ids.split(',') if v.strip()]
    if args.command == 'run':
        return run_queue(args.mode, ids, pair_size=args.pair_size)
    return 2


if __name__ == '__main__':
    sys.exit(main())
