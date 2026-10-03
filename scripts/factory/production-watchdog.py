#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""production-watchdog.py — AGENT #6: director / production watchdog.

TRÁCH NHIỆM DUY NHẤT (docs/factory-workflow-contract.md mục Agent #6):
đánh thức production bình thường khi KHÔNG có valid progress liên tục
2 giờ.

  - last_valid_progress_at = timestamp mới nhất của MỘT trong các tín
    hiệu TIẾN TRÌNH THẬT: checkpoint.updated_at, transaction history
    (result=PUBLISHED) finished_at, writer-claims claimed_at/updated_at,
    QA evidence (data/qa/*.json) scored_at/published_at.
  - KHÔNG phải progress (KHÔNG reset đồng hồ): log, heartbeat, status
    check, polling, run FAIL, lần chạy watchdog, thông điệp thông tin.
  - Khi inactivity >= 2h, kiểm tra TRƯỚC khi hành động: #4 idle, #5
    idle, không maintenance-lock, production KHÔNG pause chủ động
    (production-control.enabled=false), KHÔNG blocked chủ động
    (checkpoint.status=BLOCKED), không writer cycle active (writer-lock
    locked / hàng WRITING/QA/PASS/REPAIR / lease còn tươi), không
    publisher active (transaction.active), không build/deploy active
    (data/state/deploy-active.json active). MỘT điều kiện còn hoạt
    động → KHÔNG làm gì cả (DO NOTHING là hành vi an toàn).
  - Hành động: kích hoạt ĐÚNG MỘT entrypoint production bình thường
    hiện có — `factory-operator.py prepare-next` (claim PLANNED →
    fan-out writer; chính operator refuse khi maintenance-lock/pause —
    double safety). KHÔNG trực tiếp khởi động Writer #1/#2/#3, KHÔNG
    repair, KHÔNG sửa bài, KHÔNG sửa queue/manifest/SQLite, KHÔNG
    cancel run đang chạy.
  - Idempotent: mỗi lần wake ghi marker data/state/watchdog-wake.json;
    cooldown 2h chống 2 lần chạy watchdog tạo duplicate cycle. Bản
    thân watchdog KHÔNG bao giờ reset đồng hồ inactivity.
  - Lightweight: READ-ONLY gần như hoàn toàn (chỉ ghi marker khi wake),
    KHÔNG build, KHÔNG quét link, KHÔNG full-site QA.
  - Dry-run mặc định: KHÔNG có --wake thì KHÔNG BAO GIỜ kích hoạt
    production — chỉ in WOULD_WAKE. --wake là quyết định của người
    vận hành (workflow ship mặc định --dry-run).

Exit: 0 = hoàn tất (kể cả DO NOTHING); 1 = lỗi dữ liệu.
"""
import argparse
import datetime
import glob
import json
import os
import subprocess
import sys

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

INACTIVITY_HOURS = 2.0    # ngưỡng wake: 2h KHÔNG valid progress
WAKE_COOLDOWN_HOURS = 2.0

LOCK = 'data/state/maintenance-lock.json'
INCIDENTS = 'data/state/incidents'
CTRL = 'data/factory/production-control.json'
CP = 'data/state/checkpoint.json'
TXN = 'data/state/transaction.json'
WL = 'data/state/writer-lock.json'
WL_SENTINEL = 'data/state/writer-lock.active'
CLAIMS = 'data/state/writer-claims.json'
QA_DIR = 'data/qa'
DEPLOY = 'data/state/deploy-active.json'
WAKE_MARKER = 'data/state/watchdog-wake.json'
MATRIX = 'data/content-matrix.csv'

CLOSED_INCIDENT = ('recovered', 'resumable')
ACTIVE_ROWS = ('WRITING', 'QA', 'PASS', 'REPAIR')

ENTRYPOINT = ['scripts/factory/factory-operator.py', 'prepare-next']


def p(root, rel):
    return os.path.join(root, rel)


def read_json(root, rel, default=None):
    path = p(root, rel)
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def parse_any_iso(s):
    """Timestamp ISO dạng Z hoặc +00:00 → datetime UTC; hỏng → None."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        dt = datetime.datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def now_dt(now=None):
    if isinstance(now, datetime.datetime):
        return now
    if now:
        return parse_any_iso(now)
    return datetime.datetime.now(datetime.timezone.utc)


def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------------------------------------------------------------- progress

def last_valid_progress(root, now):
    """Timestamp tiến trình THẬT mới nhất (KHÔNG tính log/heartbeat)."""
    stamps = []

    # 1. checkpoint: chu kỳ production hoàn tất/đầu ra mới
    cp = read_json(root, CP, {})
    t = parse_any_iso(cp.get('updated_at'))
    if t:
        stamps.append(('checkpoint.updated_at', t))

    # 2. publisher/integration: transaction history result PUBLISHED
    txn = read_json(root, TXN, {})
    for h in txn.get('history') or []:
        if isinstance(h, dict) and h.get('result') == 'PUBLISHED':
            t = parse_any_iso(h.get('finished_at') or h.get('started_at'))
            if t:
                stamps.append(('txn.PUBLISHED:' + str(h.get('article_id')), t))

    # 3. writer staging progress: writer-claims (claim mới = writer
    #    nhận bài và đang soạn)
    claims = read_json(root, CLAIMS, {})
    t = parse_any_iso(claims.get('updated_at'))
    if t:
        stamps.append(('writer-claims.updated_at', t))
    for w, lease in (claims.get('leases') or {}).items():
        if isinstance(lease, dict):
            t = parse_any_iso(lease.get('claimed_at'))
            if t:
                stamps.append(('writer-claims:' + str(w), t))

    # 4. QA evidence mới (publish/xếp hạng bài)
    for path in glob.glob(p(root, QA_DIR + '/*.json')):
        try:
            with open(path, encoding='utf-8') as f:
                ev = json.load(f)
        except (OSError, ValueError):
            continue
        for k in ('scored_at', 'published_at'):
            t = parse_any_iso(ev.get(k))
            if t:
                stamps.append(('qa:%s:%s' % (ev.get('article_id'), k), t))
                break

    if not stamps:
        return None, []
    newest = max(stamps, key=lambda kv: kv[1])
    return newest[1], sorted(stamps, key=lambda kv: kv[1])


# ---------------------------------------------------------------- guards

def collect_guards(root, now):
    g = {}

    # Agent #4/#5 idle + maintenance lock: MỌI lock active (kể cả stale)
    # đều là ngữ cảnh maintenance — watchdog KHÔNG bao giờ bypass lock.
    lk = read_json(root, LOCK, {})
    g['maintenance_lock'] = bool(lk.get('locked'))
    g['agent4_active'] = bool(lk.get('locked') and lk.get('holder') == 'agent-4')
    g['agent5_active'] = bool(lk.get('locked') and lk.get('holder') == 'agent-5')

    # incident còn mở (dừng/chưa xác nhận xong) → chưa phải lúc wake
    g['open_incident'] = False
    for path in glob.glob(p(root, INCIDENTS + '/*.json')):
        try:
            with open(path, encoding='utf-8') as f:
                inc = json.load(f)
        except (OSError, ValueError):
            continue
        if inc.get('status') not in CLOSED_INCIDENT:
            g['open_incident'] = True

    # pause chủ động của chủ xe
    ctrl = read_json(root, CTRL, {})
    g['intentional_pause'] = ctrl.get('enabled') is False
    cp = read_json(root, CP, {})
    g['intentional_blocked'] = cp.get('status') == 'BLOCKED'

    # writer cycle active: writer-lock + sentinel + hàng đang chạy + lease tươi
    wl = read_json(root, WL, {})
    g['writer_lock_held'] = bool(wl.get('locked'))
    g['writer_lock_sentinel'] = os.path.exists(p(root, WL_SENTINEL))
    g['active_matrix_rows'] = 0
    matrix = p(root, MATRIX)
    if os.path.exists(matrix):
        with open(matrix, encoding='utf-8', newline='') as f:
            import csv as _csv
            for row in _csv.DictReader(f):
                if (row.get('status') or '').upper() in ACTIVE_ROWS:
                    g['active_matrix_rows'] += 1
    g['active_matrix_rows_bool'] = g['active_matrix_rows'] > 0
    claims = read_json(root, CLAIMS, {})
    fresh = False
    for w, lease in (claims.get('leases') or {}).items():
        if isinstance(lease, dict):
            t = parse_any_iso(lease.get('expires_at'))
            if t and t > now:
                fresh = True
    g['fresh_writer_lease'] = fresh

    # publisher/integration active
    txn = read_json(root, TXN, {})
    g['publisher_active'] = bool(txn.get('active'))

    # build/deploy active (marker do integration ghi khi triển khai)
    dep = read_json(root, DEPLOY, {})
    g['build_deploy_active'] = bool(dep.get('active'))
    return g


def wake_cooldown(root, now):
    mk = read_json(root, WAKE_MARKER, {})
    t = parse_any_iso(mk.get('last_wake_at'))
    if not t:
        return False, mk
    return (now - t).total_seconds() / 3600.0 < WAKE_COOLDOWN_HOURS, mk


def main():
    ap = argparse.ArgumentParser(
        description='Agent #6 production watchdog (wake after 2h no valid '
                    'progress; dry-run mặc định)')
    ap.add_argument('--root', default=DEFAULT_ROOT)
    ap.add_argument('--now', default=None,
                    help='ISO timestamp override (test deterministic)')
    ap.add_argument('--wake', action='store_true',
                    help='KÍCH HOẠT THẬT entrypoint khi đủ điều kiện '
                         '(mặc định dry-run — KHÔNG bao giờ kích hoạt)')
    ap.add_argument('--dry-run', action='store_true',
                    help='minh bạch: KHÔNG kích hoạt production (mặc định)')
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    now = now_dt(args.now)
    if now is None:
        print('DATA ERROR: --now không parse được: %r' % args.now)
        return 1

    progress_at, stamps = last_valid_progress(root, now)
    if progress_at is None:
        inactivity = None
    else:
        inactivity = (now - progress_at).total_seconds() / 3600.0

    out = {
        'now': iso(now),
        'last_valid_progress_at': iso(progress_at) if progress_at else None,
        'inactivity_hours': round(inactivity, 3) if inactivity is not None
        else None,
        'eligible': False,
        'action': 'none',
        'reason': '',
        'entrypoint': ' '.join(ENTRYPOINT),
        'guards': {},
        'wake_marker': None,
    }

    if inactivity is None:
        out['reason'] = 'không có tín hiệu progress nào để so (chưa từng ' \
                        'chạy production) — KHÔNG wake'
        print('WATCHDOG_JSON: ' + json.dumps(out, ensure_ascii=False))
        print('WATCHDOG: NO ACTION (%s)' % out['reason'])
        return 0

    if inactivity < INACTIVITY_HOURS:
        out['reason'] = ('progress còn tươi (%.2fh < %.1fh)'
                         % (inactivity, INACTIVITY_HOURS))
        print('WATCHDOG_JSON: ' + json.dumps(out, ensure_ascii=False))
        print('WATCHDOG: NO ACTION (%s)' % out['reason'])
        return 0

    guards = collect_guards(root, now)
    out['guards'] = guards
    blockers = [k for k, v in sorted(guards.items())
                if v is True and not k.endswith('_count')]
    cooldown, marker = wake_cooldown(root, now)
    out['wake_marker'] = marker.get('last_wake_at')
    if cooldown:
        blockers.append('wake_cooldown')
    if blockers:
        out['reason'] = 'điều kiện hoạt động/bảo trì còn: %s' % blockers
        print('WATCHDOG_JSON: ' + json.dumps(out, ensure_ascii=False))
        print('WATCHDOG: NO ACTION (%s)' % out['reason'])
        return 0

    out['eligible'] = True
    if not args.wake:
        out['action'] = 'would-wake'
        out['reason'] = ('inactivity %.2fh >= %.1fh, mọi guard idle — '
                         'DRY-RUN (truyền --wake để kích hoạt thật)'
                         % (inactivity, INACTIVITY_HOURS))
        print('WATCHDOG_JSON: ' + json.dumps(out, ensure_ascii=False))
        print('WATCHDOG: WOULD WAKE — entrypoint: %s (%s)'
              % (out['entrypoint'], out['reason']))
        return 0

    # wake THẬT: đúng MỘT entrypoint production bình thường hiện có;
    # hệ thống production tự allocate/fan-out (watchdog KHÔNG đụng
    # queue/writer trực tiếp).
    out['action'] = 'wake'
    res = subprocess.run([sys.executable] + ENTRYPOINT, cwd=root,
                         capture_output=True, text=True, timeout=600)
    out['wake_exit'] = res.returncode
    out['wake_output_tail'] = (res.stdout or '')[-400:]
    marker = {
        'last_wake_at': iso(now),
        'last_progress_at': out['last_valid_progress_at'],
        'inactivity_hours': out['inactivity_hours'],
        'entrypoint': out['entrypoint'],
        'wake_exit': res.returncode,
        'wake_count': int((read_json(root, WAKE_MARKER, {})
                           or {}).get('wake_count', 0)) + 1,
        'note': 'Agent #6 wake — bản thân watchdog KHÔNG reset đồng hồ '
                'progress (log/heartbeat không phải progress)',
    }
    path = p(root, WAKE_MARKER)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(marker, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, path)
    out['reason'] = ('inactivity %.2fh — đã kích hoạt entrypoint '
                     '(exit %d)' % (inactivity, res.returncode))
    print('WATCHDOG_JSON: ' + json.dumps(out, ensure_ascii=False))
    print('WATCHDOG: WAKE — entrypoint: %s (exit %d)'
          % (out['entrypoint'], res.returncode))
    return 0


if __name__ == '__main__':
    sys.exit(main())
