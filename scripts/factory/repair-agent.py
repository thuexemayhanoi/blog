#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repair-agent.py — AGENT #4: first-line INFRASTRUCTURE repair.

Hợp đồng (docs/factory-workflow-contract.md mục Agent #4/#5/#6):

  - KHÔNG BAO GIỜ viết/sửa bài viết (_posts/, _drafts/, matrix content,
    taxonomy, pricing, business facts). Chỉ sửa hạ tầng data/state/**.
  - Trigger từ một sự cố hạ tầng THẬT (watchdog STALE_*, incident từ
    operator): `start` tạo/reuse incident_id + giành maintenance_lock
    toàn cục — mọi op mutating của factory-operator từ chối trong lúc
    maintenance active (pause production thật).
  - Tối đa MỘT repair attempt mỗi incident (cưỡng chế bằng counter).
  - Mỗi action trong whitelist là sửa chữa deterministic, tối thiểu,
    an toàn — chỉ đọc đúng bằng chứng liên quan đến lỗi.
  - Sau repair chạy regression test focused (validate.py scope chunk)
    và ghi vào record: incident_id, timestamps, trigger, diagnosis,
    files/actions, tests, result.
  - Trả về đúng: SUCCESS (hold lock chờ #5 verify) hoặc ESCALATE
    (bàn giao #5 — lock giữ nguyên, cùng incident_id).
  - One-shot: không loop, không polling, không tự retry.

Lệnh (chạy từ gốc repo hoặc --root):
  start  --incident-id INC-YYYYMMDD-slug --trigger TEXT [--source TEXT]
          [--force-stale]
  repair --incident-id INC-... --action NAME [--diagnosis TEXT]
          [--skip-tests]   (chỉ dùng khi fixture không có validate.py)
  status --incident-id INC-...

Exit: 0 = SUCCESS/ESCALATE (protocol hoàn tất, đã ghi record);
      1 = REFUSED (vi phạm hợp đồng — KHÔNG mutate gì).
"""
import argparse
import csv
import datetime
import importlib.util
import json
import os
import subprocess
import sys

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maintenance as M                                    # noqa: E402

STATE = 'data/state'
WL = 'data/state/writer-lock.json'
TXN = 'data/state/transaction.json'
CP = 'data/state/checkpoint.json'
CLAIMS = 'data/state/writer-claims.json'
MATRIX = 'data/content-matrix.csv'

# whitelist action: mỗi action sửa đúng 1 loại hỏng hạ tầng,
# deterministic, không đụng vùng nội dung.
ACTIONS = ('release-stale-writer-lock', 'clear-inactive-transaction',
           'recompute-checkpoint-counts', 'prune-writer-claims')


# ------------------------------------------------------------------ helpers

def p(root, rel):
    return os.path.join(root, rel)


def out_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _load(root, rel, default=None):
    path = p(root, rel)
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _save_json(root, rel, data):
    M.assert_writable_rel(rel)
    M.write_json_atomic(p(root, rel), data)


def _matrix_rows(root):
    path = p(root, MATRIX)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ actions

def act_release_stale_writer_lock(root, now):
    """writer-lock locked=true nhưng hết hạn (expires_at đã qua) hoặc
    thiếu holder/token → nhả về unlocked. Lock còn tươi = KHÔNG đụng
    (đó là ownership đang hoạt động, không phải hỏng hạ tầng)."""
    lk = _load(root, WL, None)
    if not lk or not lk.get('locked'):
        return {'ok': True, 'diagnosis': 'writer-lock không bị giữ — không có gì để sửa',
                'files': [], 'details': 'locked=false hoặc thiếu file'}
    exp = lk.get('expires_at')
    broken = (not exp or not lk.get('holder') or
              M.parse_iso(exp) <= M.parse_iso(now))
    if not broken:
        return {'ok': False,
                'diagnosis': 'writer-lock còn TƯƠI (holder=%s, hết hạn %s) — '
                             'không phải hỏng hạ tầng, không force-unlock '
                             'ownership đang hoạt động' % (lk.get('holder'), exp),
                'files': [], 'details': 'refused-fresh-lock'}
    before = dict(lk)
    lk['locked'] = False
    lk['holder'] = None
    lk['token'] = None
    lk['acquired_at'] = None
    lk['expires_at'] = None
    lk['updated_at'] = now
    lk['note'] = ('nhả bởi Agent #4 repair (release-stale-writer-lock): '
                  'lock hết hạn/thiếu metadata; trước: %s'
                  % json.dumps({k: before.get(k) for k in
                                ('holder', 'acquired_at', 'expires_at')},
                               ensure_ascii=False))
    _save_json(root, WL, lk)
    return {'ok': True,
            'diagnosis': 'writer-lock stale (holder=%s, hết hạn %s) đã được nhả'
                         % (before.get('holder'), before.get('expires_at')),
            'files': [WL],
            'details': 'stale writer-lock released'}


def act_clear_inactive_transaction(root, now):
    """transaction active=true nhưng không có pending payload (mâu thuẫn
    dữ liệu — txn treo chặn preflight) → đưa về inactive giữ nguyên
    history. active=true CÙNG pending hợp lệ = không phải hỏng — ESCALATE."""
    txn = _load(root, TXN, None)
    if not txn or not txn.get('active'):
        return {'ok': True,
                'diagnosis': 'transaction không active — không có gì để sửa',
                'files': [], 'details': 'active=false hoặc thiếu file'}
    if txn.get('pending'):
        return {'ok': False,
                'diagnosis': 'transaction active CÙNG pending (%s) — không '
                             'phải dữ liệu mâu thuẫn; cần operator xử lý '
                             'thủ công, vượt mức Agent #4'
                             % json.dumps(txn['pending'], ensure_ascii=False),
                'files': [], 'details': 'refused-active-with-pending'}
    txn['active'] = False
    txn['updated_at'] = now
    note = ('sửa bởi Agent #4 repair (clear-inactive-transaction): active=true '
            'nhưng pending=null — mâu thuẫn dữ liệu đã được đưa về inactive')
    txn['note'] = note
    _save_json(root, TXN, txn)
    return {'ok': True, 'diagnosis': note, 'files': [TXN],
            'details': 'inactive-but-active transaction cleared'}


def act_recompute_checkpoint_counts(root, now):
    """counts của checkpoint lệch số đếm thật từ matrix → tính lại đúng
    (deterministic). Không đổi trạng thái/mức độ, chỉ đồng bộ số."""
    cp = _load(root, CP, None)
    rows = _matrix_rows(root)
    if cp is None:
        return {'ok': False,
                'diagnosis': 'checkpoint.json thiếu — vượt mức Agent #4 '
                             '(không tự tạo checkpoint từ đầu)',
                'files': [], 'details': 'missing-checkpoint'}
    before = dict(cp.get('counts', {}))
    counts = {}
    for st in ('planned', 'writing', 'qa', 'pass', 'published', 'repair',
               'blocked', 'fail', 'review', 'existing'):
        counts[st] = sum(1 for r in rows if r.get('status', '').upper() == st.upper())
    if before == counts and rows:
        return {'ok': True,
                'diagnosis': 'checkpoint counts đã khớp matrix — không có gì để sửa',
                'files': [], 'details': 'counts consistent'}
    cp['counts'] = counts
    cp['updated_at'] = now
    cp['note'] = ('đồng bộ lại counts từ matrix bởi Agent #4 repair '
                  '(recompute-checkpoint-counts); trước: %s'
                  % json.dumps(before, ensure_ascii=False))
    _save_json(root, CP, cp)
    return {'ok': True,
            'diagnosis': 'checkpoint counts lệch matrix đã được tính lại '
                         '(%s -> %s)' % (json.dumps(before, ensure_ascii=False),
                                         json.dumps(counts, ensure_ascii=False)),
            'files': [CP], 'details': 'checkpoint counts recomputed'}


def act_prune_writer_claims(root, now):
    """lease của writer hết hạn TTL (48h) hoặc id không còn PLANNED →
    prune qua writer-claim.py prune (self-heal registry có sẵn, giữ
    nguyên kết quả recoverable của writer còn hợp lệ)."""
    claims_path = p(root, CLAIMS)
    wc = p(root, 'scripts/factory/writer-claim.py')
    if not os.path.exists(wc):
        return {'ok': False,
                'diagnosis': 'scripts/factory/writer-claim.py không tồn tại — '
                             'không prune được', 'files': [],
                'details': 'missing-writer-claim-script'}
    before = _load(root, CLAIMS, {})
    r = subprocess.run([sys.executable, wc, 'prune'],
                       capture_output=True, text=True, cwd=root)
    after = _load(root, CLAIMS, {})
    if r.returncode != 0:
        return {'ok': False,
                'diagnosis': 'writer-claim prune exit %d: %s'
                             % (r.returncode, (r.stdout + r.stderr)[-300:]),
                'files': [CLAIMS], 'details': 'prune-failed'}
    changed = before != after
    return {'ok': True,
            'diagnosis': 'writer-claims registry đã prune%s'
                         % (' (có lease hết hạn bị thu hồi)' if changed
                            else ' — registry đã sạch'),
            'files': [CLAIMS],
            'details': 'prune ok; registry thay đổi: %s' % changed}


ACTION_FUNCS = {
    'release-stale-writer-lock': act_release_stale_writer_lock,
    'clear-inactive-transaction': act_clear_inactive_transaction,
    'recompute-checkpoint-counts': act_recompute_checkpoint_counts,
    'prune-writer-claims': act_prune_writer_claims,
}


# ------------------------------------------------------------------ regression

def run_regression(root):
    """Focused regression sau repair: validate.py scope chunk (cùng ngưỡng
    publisher dùng trên đường nóng — không full-site audit)."""
    vp = p(root, 'scripts/factory/validate.py')
    if not os.path.exists(vp):
        return {'command': 'validate.py --scope chunk', 'exit': None,
                'summary': 'validate.py không tồn tại trong root', 'ok': False}
    r = subprocess.run([sys.executable, vp, '--scope', 'chunk'],
                       capture_output=True, text=True, cwd=root)
    tail = (r.stdout or '').strip().splitlines()
    summary = tail[-1] if tail else (r.stderr or '').strip()[-200:]
    return {'command': 'validate.py --scope chunk', 'exit': r.returncode,
            'summary': summary, 'ok': r.returncode == 0}


# ------------------------------------------------------------------ commands

def cmd_start(args, root):
    now = args.now or M.now_iso()
    if args.incident_id and M.incident_exists(root, args.incident_id):
        inc = M.load_incident(root, args.incident_id)
        if inc['agent4'].get('attempts', 0) >= 1 or inc['agent4'].get('result'):
            print('REFUSED: incident %s đã dùng hết lượt Agent #4 (mỗi '
                  'incident tối đa 1 repair attempt)' % args.incident_id)
            return 1
        trigger, source = inc.get('trigger'), inc.get('source')
    else:
        trigger, source = args.trigger, args.source
    if not trigger:
        print('REFUSED: thiếu --trigger (incident phải xuất phát từ sự cố '
              'thật, không tự bịa)')
        return 1
    try:
        lk = M.acquire_lock(root, M.AGENT4, args.incident_id, now,
                            force_stale=args.force_stale,
                            note='Agent #4 first-line repair')
    except M.MaintenanceError as e:
        print('REFUSED: %s' % e)
        return 1
    if M.incident_exists(root, args.incident_id):
        inc = M.load_incident(root, args.incident_id)
        inc['status'] = 'repairing'
    else:
        inc = M.new_incident(args.incident_id, trigger, source, now)
        inc['status'] = 'repairing'
    inc['agent4']['started_at'] = inc['agent4']['started_at'] or now
    inc['updated_at'] = now
    inc['maintenance_lock'] = lk
    M.save_incident(root, args.incident_id, inc)
    print('AGENT4_START: %s (holder=%s, expires %s)'
          % (args.incident_id, lk['holder'], lk['expires_at']))
    return 0


def cmd_repair(args, root):
    now = args.now or M.now_iso()
    try:
        M.validate_incident_id(args.incident_id)
        inc = M.load_incident(root, args.incident_id)
        M.require_holder(root, M.AGENT4, args.incident_id)
    except M.MaintenanceError as e:
        print('REFUSED: %s' % e)
        return 1
    a4 = inc['agent4']
    if a4.get('attempts', 0) >= 1:
        print('REFUSED: incident %s đã có MỘT attempt Agent #4 — không '
              'bao giờ retry tự trị; bàn giao Agent #5' % args.incident_id)
        return 1
    if args.action not in ACTIONS:
        print('REFUSED: action %r ngoài whitelist %s' % (args.action, ACTIONS))
        return 1

    action = ACTION_FUNCS[args.action]
    res = action(root, now)
    a4['attempts'] = 1
    a4['result'] = None
    a4['diagnosis'] = args.diagnosis or res['diagnosis']
    a4['actions'].append({
        'action': args.action,
        'ok': res['ok'],
        'diagnosis': res['diagnosis'],
        'files': res['files'],
        'details': res['details'],
        'at': now,
    })

    tests = None
    if res['ok'] and not args.skip_tests:
        tests = run_regression(root)
        a4['tests'].append({**tests, 'at': now})

    success = bool(res['ok']) and (tests is None or tests['ok'])
    a4['result'] = 'SUCCESS' if success else 'ESCALATE'
    a4['finished_at'] = now
    inc['updated_at'] = now
    inc['diagnosis'] = a4['diagnosis']
    # SUCCESS: lock GIỮ NGUYÊN chờ Agent #5 verify rồi nhả;
    # ESCALATE: lock cũng giữ nguyên — #5 nhận đúng incident_id này.
    inc['status'] = 'agent4-' + a4['result'].lower()
    M.save_incident(root, args.incident_id, inc)
    print('AGENT4_RESULT: %s' % a4['result'])
    if not success:
        print('  reason: %s' % res['diagnosis'])
        if tests and not tests['ok']:
            print('  regression: exit=%s (%s)' % (tests['exit'],
                                                  tests['summary']))
    return 0


def cmd_status(args, root):
    try:
        inc = M.load_incident(root, args.incident_id)
    except M.MaintenanceError as e:
        print('REFUSED: %s' % e)
        return 1
    out_json(inc)
    return 0


def main():
    ap = argparse.ArgumentParser(description='Agent #4 first-line repair')
    ap.add_argument('--root', default=DEFAULT_ROOT)
    ap.add_argument('--now', default=None,
                    help='ISO timestamp override (test deterministic)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('start')
    s.add_argument('--incident-id', required=True)
    s.add_argument('--trigger')
    s.add_argument('--source')
    s.add_argument('--force-stale', action='store_true')
    s.set_defaults(fn=cmd_start)
    r = sub.add_parser('repair')
    r.add_argument('--incident-id', required=True)
    r.add_argument('--action', required=True, choices=list(ACTIONS))
    r.add_argument('--diagnosis')
    r.add_argument('--skip-tests', action='store_true')
    r.set_defaults(fn=cmd_repair)
    t = sub.add_parser('status')
    t.add_argument('--incident-id', required=True)
    t.set_defaults(fn=cmd_status)
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    return args.fn(args, root)


if __name__ == '__main__':
    sys.exit(main())
