#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIVENESS WATCHDOG — kiểm tra "sức sống" của factory (READ-ONLY THUẦN).

Hợp đồng (docs/ENGINE-RUNBOOK.md mục 10):
  - CHỈ ĐỌC state (transaction/checkpoint/writer-lock/matrix). Không ghi,
    không mutate, không lock, không nhận việc, không tự recover — watchdog
    là hệ thống báo cáo, mọi can thiệp qua operator chuẩn (RECOVERY.md).
  - Chạy định kỳ trong .github/workflows/factory-liveness.yml
    (cron tuần, contents: read) — cùng purity check bắt buộc sau đó.
  - Sau watchdog bước purity bắt buộc: working tree phải sạch (bằng chứng
    READ-ONLY, không tự khai).

Trạng thái (ưu tiên từ trên xuống):
  DEGRADED_STATE_FILES  — state file thiếu/hỏng JSON (exit 2).
  STALE_TXN             — transaction active quá ngưỡng (mặc định 3h) (exit 1).
  STALE_LOCK            — BẤT KỲ lock đang giữ quá ngưỡng (2h) đều exit 1,
                          CẢ hai trường hợp: còn việc dở hay 0 việc dở.
                          Lý do: factory-operator preflight coi mọi lock
                          đang giữ (locked=true / writer-lock.active) là
                          "đang chặn" và từ chối mutation — lock mồ côi
                          stale KHÔNG phải HEALTHY_IDLE. Watchdog vẫn
                          READ-ONLY: KHÔNG tự xoá, KHÔNG force-unlock.
  STALE_CHECKPOINT      — còn việc dở nhưng checkpoint không cập nhật quá 24h.
  STALLED_ACTIVE        — còn việc dở, không lock, không txn, checkpoint im
                          lặng quá 6h (chunk claim rồi bỏ mặc).
  HEALTHY_ACTIVE        — txn/lock còn tươi (engine đang làm).
  HEALTHY_IDLE          — không việc dở, không txn/lock (engine nghỉ).

Exit: 0 = HEALTHY_*; 1 = cần can thiệp (STALE_*/STALLED_*); 2 = lỗi dữ liệu.

Chạy: python3 scripts/factory/watchdog.py [--root PATH] [--now ISO]
      [--lock-stale-hours H] [--txn-stale-hours H]
      [--checkpoint-stale-hours H] [--active-stale-hours H]
"""
import argparse
import csv
import datetime
import json
import os
import sys

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

TXN = 'data/state/transaction.json'
CP = 'data/state/checkpoint.json'
LOCK = 'data/state/writer-lock.json'
LOCK_FILE = 'data/state/writer-lock.active'
MATRIX = 'data/content-matrix.csv'

UNFINISHED_STATUS = ('WRITING', 'QA', 'REPAIR', 'PASS')

DEFAULT_LOCK_STALE_H = 2.0
DEFAULT_TXN_STALE_H = 3.0
DEFAULT_CHECKPOINT_STALE_H = 24.0
DEFAULT_ACTIVE_STALE_H = 6.0

E_OK, E_ATTENTION, E_DATA = 0, 1, 2


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_ts(value):
    """ISO -> datetime (timezone-aware). Thiếu timezone -> coi là UTC."""
    if not value:
        return None
    try:
        ts = datetime.datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    return ts


def age_hours(ts, now):
    if ts is None:
        return None            # không suy đoán — gọi là "không rõ"
    return (now - ts).total_seconds() / 3600.0


def read_json(root, rel):
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def unfinished_work(root):
    """Số hàng đang dở (WRITING/QA/REPAIR/PASS) + chunk in-progress.
    READ-ONLY: chỉ đọc matrix/checkpoint; matrix hỏng không crash watchdog."""
    ids = set()
    matrix_note = None
    mpath = os.path.join(root, MATRIX)
    if os.path.exists(mpath):
        try:
            with open(mpath, encoding='utf-8', newline='') as f:
                for r in csv.DictReader(f):
                    if r.get('status') in UNFINISHED_STATUS:
                        ids.add(r['id'])
        except (OSError, csv.Error):
            matrix_note = 'matrix không đọc được — đếm theo checkpoint chunk'
    try:
        cp = read_json(root, CP)
    except (OSError, ValueError):
        cp = {}
    for aid in cp.get('in_progress_chunk') or []:
        if aid:
            ids.add(aid)
    return sorted(ids), matrix_note


def lock_held(root, meta):
    if os.path.exists(os.path.join(root, LOCK_FILE)):
        return True
    return bool(meta.get('locked'))


def check(root, now, lock_stale_h, txn_stale_h, checkpoint_stale_h,
          active_stale_h):
    """Trả về dict trạng thái. KHÔNG ghi bất cứ file nào."""
    out = {
        'checked_at': now.strftime('%Y-%m-%dT%H:%M:%S+00:00'),
        'root': root,
        'thresholds': {
            'lock_stale_hours': lock_stale_h,
            'txn_stale_hours': txn_stale_h,
            'checkpoint_stale_hours': checkpoint_stale_h,
            'active_stale_hours': active_stale_h,
        },
    }
    # ---- đọc state (bước đầu: DEGRADED khi state hỏng)
    try:
        txn = read_json(root, TXN)
        lock_meta = read_json(root, LOCK)
        cp = read_json(root, CP)
    except (OSError, ValueError) as e:
        out.update({
            'state': 'DEGRADED_STATE_FILES',
            'detail': 'state file thiếu/hỏng: %s' % e,
            'exit': E_DATA,
        })
        return out
    txn_active = bool(txn.get('active'))
    txn_age = age_hours(parse_ts(txn.get('updated_at')), now)
    held = lock_held(root, lock_meta)
    lock_age = age_hours(parse_ts(lock_meta.get('updated_at')), now)
    cp_age = age_hours(parse_ts(cp.get('updated_at')), now)
    unfinished, matrix_note = unfinished_work(root)

    out.update({
        'txn_active': txn_active,
        'txn_phase': txn.get('phase'),
        'txn_age_hours': txn_age,
        'lock_held': held,
        'lock_holder': lock_meta.get('holder'),
        'lock_age_hours': lock_age,
        'checkpoint_age_hours': cp_age,
        'last_completed_article_id': cp.get('last_completed_article_id'),
        'next_claimable_id': cp.get('next_claimable_id'),
        'unfinished_work': len(unfinished),
        'unfinished_ids': unfinished[:5],
    })
    if matrix_note:
        out['matrix_note'] = matrix_note

    def stale(age, hours):
        # None (không rõ mốc) -> coi là treo: không suy đoán an toàn
        return age is None or age >= hours

    # ---- ưu tiên theo hợp đồng
    if txn_active and stale(txn_age, txn_stale_h):
        out.update({
            'state': 'STALE_TXN',
            'detail': 'transaction active %.1fh (ngưỡng %.1fh) — chạy '
                      'operator recover (docs/RECOVERY.md).'
                      % (txn_age if txn_age is not None else -1, txn_stale_h),
            'exit': E_ATTENTION,
        })
        return out
    if held and stale(lock_age, lock_stale_h):
        if unfinished:
            out.update({
                'state': 'STALE_LOCK',
                'detail': 'writer-lock treo %.1fh (ngưỡng %.1fh) VÀ còn %d '
                          'việc dở — can thiệp theo docs/RECOVERY.md '
                          '(KHÔNG force-unlock ownership không rõ).'
                          % (lock_age if lock_age is not None else -1,
                             lock_stale_h, len(unfinished)),
                'exit': E_ATTENTION,
            })
            return out
        # Lock mồ côi stale (0 việc dở): mutation preflight của
        # factory-operator vẫn coi mọi lock đang giữ là held và chặn
        # mutation -> KHÔNG THỂ là HEALTHY_IDLE. Watchdog READ-ONLY:
        # KHÔNG tự xoá, KHÔNG force-unlock — dọn qua operator chuẩn.
        out.update({
            'state': 'STALE_LOCK',
            'detail': 'writer-lock mồ côi treo %.1fh (ngưỡng %.1fh), 0 việc dở '
                      '— preflight vẫn chặn mọi mutation vì lock còn held; '
                      'dọn theo docs/RECOVERY.md (KHÔNG force-unlock '
                      'ownership không rõ).'
                      % (lock_age if lock_age is not None else -1,
                         lock_stale_h),
            'exit': E_ATTENTION,
        })
        return out
    if unfinished and stale(cp_age, checkpoint_stale_h):
        out.update({
            'state': 'STALE_CHECKPOINT',
            'detail': 'còn %d việc dở nhưng checkpoint im lặng %.1fh '
                      '(ngưỡng %.1fh).' % (len(unfinished),
                                           cp_age if cp_age is not None
                                           else -1, checkpoint_stale_h),
            'exit': E_ATTENTION,
        })
        return out
    if (unfinished and not txn_active and not held
            and stale(cp_age, active_stale_h)):
        out.update({
            'state': 'STALLED_ACTIVE',
            'detail': 'chunk claim rồi bỏ mặc: %d việc dở, không lock, '
                      'không transaction, checkpoint im lặng %.1fh '
                      '(ngưỡng %.1fh). Resume: hoàn tất hoặc release-chunk.'
                      % (len(unfinished),
                         cp_age if cp_age is not None else -1, active_stale_h),
            'exit': E_ATTENTION,
        })
        return out
    if txn_active or held:
        out.update({
            'state': 'HEALTHY_ACTIVE',
            'detail': 'engine đang làm việc (txn_active=%s, lock=%s).'
                      % (txn_active, held),
            'exit': E_OK,
        })
        return out
    out.update({
        'state': 'HEALTHY_IDLE',
        'detail': 'engine nghỉ: không transaction, không lock%s.'
                  % ('' if not unfinished
                     else ' (%d việc dở chờ writer — checkpoint còn tươi)'
                     % len(unfinished)),
        'exit': E_OK,
    })
    return out


def main():
    ap = argparse.ArgumentParser(
        description='Liveness watchdog READ-ONLY cho blog factory')
    ap.add_argument('--root', default=DEFAULT_ROOT,
                    help='gốc repository (mặc định: repository của script)')
    ap.add_argument('--now', default=None,
                    help='(test) thời điểm hiện tại ISO — không dùng khi chạy thật')
    ap.add_argument('--lock-stale-hours', type=float,
                    default=DEFAULT_LOCK_STALE_H)
    ap.add_argument('--txn-stale-hours', type=float,
                    default=DEFAULT_TXN_STALE_H)
    ap.add_argument('--checkpoint-stale-hours', type=float,
                    default=DEFAULT_CHECKPOINT_STALE_H)
    ap.add_argument('--active-stale-hours', type=float,
                    default=DEFAULT_ACTIVE_STALE_H)
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    now = parse_ts(args.now) if args.now else now_utc()
    if now is None:
        print('=== WATCHDOG ===')
        print('FAIL: --now không đọc được ISO timestamp')
        return E_DATA
    out = check(root, now, args.lock_stale_hours, args.txn_stale_hours,
                args.checkpoint_stale_hours, args.active_stale_hours)
    print('=== WATCHDOG (READ-ONLY) ===')
    print('Trạng thái: %s' % out['state'])
    for key in ('detail', 'note'):
        if out.get(key):
            print('%s: %s' % (key.capitalize(), out[key]))
    print('Việc dở: %d %s | txn_active=%s | lock=%s' % (
        out.get('unfinished_work', 0), out.get('unfinished_ids') or [],
        out.get('txn_active'), out.get('lock_held')))
    print('WATCHDOG_JSON: %s' % json.dumps(out, ensure_ascii=False))
    return out['exit']


if __name__ == '__main__':
    sys.exit(main())
