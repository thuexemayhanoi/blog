#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""supervisor-agent.py — AGENT #5: supervisor / second-line recovery.

Hợp đồng (docs/factory-workflow-contract.md mục Agent #4/#5/#6):

  - KHÔNG BAO GIỜ viết/sửa bài viết. Chỉ hạ tầng data/state/**.
  - Tái dùng CÙNG incident_id của Agent #4 và CÙNG maintenance_lock —
    handoff qua `take`: lock được CHUYỂN ownership #4 -> #5 cho cùng
    incident (không nhả giữa chừng → không có khoảng trống cho
    mutation song song). #4 và #5 KHÔNG BAO GIỜ mutate đồng thời.
  - Khi #4 = SUCCESS: `verify` kiểm định ĐỘC LẬP toàn diện trạng thái
    (repo state, workflow, writer staging, publisher/txn, queue/claim,
    checkpoint, tests). HEALTHY → nhả maintenance_lock, đánh incident
    recovered — production resume qua entrypoint SINH THƯỜNG hiện có
    (không spawn cycle trong agent). UNHEALTHY → giữ pause, giữ lock,
    đánh attention, VIẾT REPORT, STOP (không sửa thêm).
  - Khi #4 = ESCALATE: `repair` được ĐÚNG MỘT attempt tối thiểu an toàn
    (cùng whitelist action của #4) → verify lại: HEALTHY → nhả lock,
    đánh resumable. Vẫn hỏng → giữ pause, GIỮ NGUYÊN checkpoint + kết
    quả recoverable của writer, VIẾT REPORT người đọc được, STOP.
    KHÔNG escalation lên Agent #6 — #6 chỉ có trách nhiệm wake.
  - Tối đa MỘT repair attempt #5 mỗi incident (cưỡng chế counter).
  - One-shot: không loop, không polling, không retry tự trị.

Lệnh (chạy từ gốc repo hoặc --root):
  take   --incident-id INC-...              (handoff #4 -> #5)
  verify --incident-id INC-... [--skip-tests]
  repair --incident-id INC-... --action NAME [--diagnosis] [--skip-tests]
  status --incident-id INC-...

Exit: 0 = protocol hoàn tất (đã ghi recovered/resumable/attention/
      stopped vào record);
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
_spec = importlib.util.spec_from_file_location(
    'repair_agent', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'repair-agent.py'))
R4 = importlib.util.module_from_spec(_spec)                 # noqa: E402
_spec.loader.exec_module(R4)                               # noqa: E402

STATE = 'data/state'
WL = 'data/state/writer-lock.json'
TXN = 'data/state/transaction.json'
CP = 'data/state/checkpoint.json'
CLAIMS = 'data/state/writer-claims.json'
CTRL = 'data/factory/production-control.json'
MATRIX = 'data/content-matrix.csv'
WORKFLOWS = ('factory-publish.yml', 'factory-liveness.yml',
             'factory-publish-verify.yml', 'factory-soak.yml',
             'quality-gate.yml')


def p(root, rel):
    return os.path.join(root, rel)


def _load(root, rel, default=None):
    path = p(root, rel)
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _matrix_rows(root):
    path = p(root, MATRIX)
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ verify

def verify_state(root, now=None, skip_tests=False):
    """Kiểm định ĐỘC LẬP sau repair. Trả (healthy, checks, tests)."""
    checks = []

    def chk(name, ok, detail):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})
        return bool(ok)

    # 1. repository state: các file state parse được
    for rel in (WL, TXN, CP, CLAIMS, 'data/state/maintenance-lock.json'):
        data = _load(root, rel, None)
        chk('repo-state:' + rel, data is not None,
            'parse OK' if data is not None else 'thiếu/hỏng JSON')

    # 2. workflow state: 5 workflow hợp đồng tồn tại
    missing = [w for w in WORKFLOWS
               if not os.path.exists(p(root, '.github/workflows/' + w))]
    chk('workflow-contract', not missing,
        'đủ 5 workflow' if not missing else 'thiếu: %s' % missing)

    # 3. writer staging state: writer-lock không bị giữ, không sentinel
    wl = _load(root, WL, {})
    chk('writer-lock-unlocked', not wl.get('locked'),
        'locked=%s holder=%s' % (wl.get('locked'), wl.get('holder')))

    # 4. publisher/integration state: transaction không active
    txn = _load(root, TXN, {})
    chk('transaction-inactive', not txn.get('active'),
        'active=%s pending=%s' % (txn.get('active'),
                                  bool(txn.get('pending'))))

    # 5. queue/assignment state: lease còn sống đều trỏ id PLANNED
    rows = _matrix_rows(root)
    planned = {r['id'] for r in rows if r.get('status') == 'PLANNED'}
    claims = _load(root, CLAIMS, {'leases': {}})
    bad = []
    now = M.as_dt(now) if now is not None else M.as_dt(M.now_iso())
    for w, lease in (claims.get('leases') or {}).items():
        exp = (lease or {}).get('expires_at')
        try:
            fresh = M.parse_iso(exp) > now
        except Exception:
            fresh = False
        if fresh:
            for aid in lease.get('ids', []):
                if aid not in planned:
                    bad.append('%s:%s' % (w, aid))
    chk('claims-valid', not bad,
        'lease tươi đều PLANNED' if not bad else 'lease lệch: %s' % bad)

    # 6. checkpoint integrity: counts khớp matrix + next_claimable tồn tại
    cp = _load(root, CP, {})
    counts = {}
    for r in rows:
        counts[r.get('status', '').upper()] = \
            counts.get(r.get('status', '').upper(), 0) + 1
    cp_counts = {k.upper(): v for k, v in (cp.get('counts') or {}).items()}
    mismatch = {k: (cp_counts.get(k, 0), counts.get(k, 0))
                for k in set(cp_counts) | set(counts)
                if cp_counts.get(k, 0) != counts.get(k, 0)}
    chk('checkpoint-counts', not mismatch,
        'khớp matrix' if not mismatch else 'lệch: %s' % mismatch)
    nxt = cp.get('next_claimable_id')
    chk('checkpoint-next-claimable',
        nxt is None or nxt in {r['id'] for r in rows},
        'next_claimable_id=%s' % nxt)

    # 7. production-control nguyên vẹn
    ctrl = _load(root, CTRL, None)
    chk('production-control',
        isinstance(ctrl, dict) and isinstance(ctrl.get('enabled'), bool)
        and isinstance(ctrl.get('chunk_size'), int),
        'enabled=%s chunk_size=%s' % (None if ctrl is None
                                      else ctrl.get('enabled'),
                                      None if ctrl is None
                                      else ctrl.get('chunk_size')))

    # 8. tests/CI evidence (nếu có thể): regression focused
    tests = None
    if not skip_tests:
        tests = R4.run_regression(root)
        chk('regression-chunk', tests.get('ok'),
            'exit=%s (%s)' % (tests.get('exit'), tests.get('summary')))
    return (all(c['ok'] for c in checks), checks, tests)


# ------------------------------------------------------------------ report

def write_report(root, inc, now):
    """Report người đọc được cho incident DỪNG (stopped/attention)."""
    a4, a5 = inc['agent4'], inc['agent5']
    lines = [
        '# Incident %s — báo cáo dừng của Agent #5' % inc['incident_id'],
        '',
        '- Trạng thái: **%s** (production còn PAUSE)' % inc['status'],
        '- Trigger: %s' % inc.get('trigger'),
        '- Bắt đầu: %s — cập nhật: %s' % (inc.get('created_at'), now),
        '- Agent #4: result=%s, attempts=%s' % (a4.get('result'),
                                                a4.get('attempts')),
        '  - diagnosis: %s' % (a4.get('diagnosis') or '(không có)'),
        '  - actions: %s' % json.dumps(
            a4.get('actions') or [], ensure_ascii=False),
        '- Agent #5: result=%s, attempts=%s' % (a5.get('result'),
                                                a5.get('attempts')),
        '  - diagnosis: %s' % (a5.get('diagnosis') or '(không có)'),
        '  - verify: %s' % json.dumps(
            a5.get('verify') or [], ensure_ascii=False, indent=2),
        '',
        '## Việc cần làm (người vận hành)',
        '',
        '1. Đọc verify checklist ở trên, mục `ok: false` là lỗi còn tồn tại.',
        '2. Checkpoint và kết quả recoverable của writer được GIỮ NGUYÊN '
        '(agent không rollback).',
        '3. maintenance-lock còn active — sau khi xử lý xong, nhả lock',
        '   bằng `maintenance.release_lock` cho holder agent-5 cùng '
        'incident_id này (không force, không tự xóa file lock).',
        '4. KHÔNG tự sửa bài viết; mọi sửa hạ tầng tiếp theo là incident '
        'MỚI với incident_id MỚI.',
    ]
    rel = '%s/%s.md' % (M.REPORTS_REL, inc['incident_id'])
    M.assert_writable_rel(rel)
    os.makedirs(os.path.dirname(p(root, rel)), exist_ok=True)
    with open(p(root, rel), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return rel


# ------------------------------------------------------------------ commands

def _require_handoff(root, incident_id):
    """#5 KHÔNG start được khi thiếu handoff #4 hợp lệ."""
    inc = M.load_incident(root, incident_id)
    a4 = inc['agent4']
    if a4.get('attempts', 0) < 1 or a4.get('result') not in ('SUCCESS',
                                                             'ESCALATE'):
        raise M.MaintenanceError(
            'handoff KHÔNG hợp lệ: Agent #4 chưa hoàn tất cho incident %s '
            '(attempts=%s, result=%s) — #5 chỉ nhận incident sau khi #4 '
            'đã trả SUCCESS/ESCALATE' % (incident_id,
                                         a4.get('attempts'),
                                         a4.get('result')))
    return inc


def cmd_take(args, root):
    now = args.now or M.now_iso()
    try:
        M.validate_incident_id(args.incident_id)
        _require_handoff(root, args.incident_id)
        lk = M.read_lock(root)
        if not lk.get('locked') or lk.get('incident_id') != args.incident_id:
            raise M.MaintenanceError(
                'maintenance-lock KHÔNG active cho incident %s — không '
                'take được (lock phải do Agent #4 giành và giữ nguyên)'
                % args.incident_id)
        if lk.get('holder') != M.AGENT4:
            raise M.MaintenanceError(
                'lock holder=%s (kỳ vọng agent-4) — #5 chỉ nhận handoff '
                'trực tiếp từ #4, không qua trung gian' % lk.get('holder'))
        M.transfer_lock(root, M.AGENT5, args.incident_id, now,
                        note='Agent #5 supervisor nhận handoff từ #4')
    except M.MaintenanceError as e:
        print('REFUSED: %s' % e)
        return 1
    inc = M.load_incident(root, args.incident_id)
    inc['agent5']['started_at'] = inc['agent5']['started_at'] or now
    inc['updated_at'] = now
    M.save_incident(root, args.incident_id, inc)
    print('AGENT5_TAKE: %s (holder=agent-5, expires %s)'
          % (args.incident_id, lk['expires_at']))
    return 0


def cmd_verify(args, root):
    now = args.now or M.now_iso()
    try:
        M.validate_incident_id(args.incident_id)
        M.require_holder(root, M.AGENT5, args.incident_id)
        inc = M.load_incident(root, args.incident_id)
    except M.MaintenanceError as e:
        print('REFUSED: %s' % e)
        return 1
    a5 = inc['agent5']
    healthy, checks, tests = verify_state(root, now=now,
                                      skip_tests=args.skip_tests)
    a5['verify'] = checks
    a5['result'] = 'HEALTHY' if healthy else 'UNHEALTHY'
    a5['tests'] = ([{**tests, 'at': now}] if tests else a5['tests'])
    a5['finished_at'] = now
    inc['updated_at'] = now
    if healthy:
        # nhả lock -> production resume qua entrypoint sinh thường
        M.release_lock(root, M.AGENT5, args.incident_id, now,
                       note='Agent #5 verify HEALTHY — incident đóng, '
                            'production resume bình thường')
        inc['status'] = 'recovered'
        inc['production_paused'] = False
        M.save_incident(root, args.incident_id, inc)
        print('AGENT5_VERIFY: HEALTHY — maintenance-lock RELEASED, incident '
              'recovered (production resume qua entrypoint bình thường)')
        return 0
    # #4=SUCCESS nhưng verify hỏng: KHÔNG sửa thêm — attention + report
    inc['status'] = 'attention'
    M.save_incident(root, args.incident_id, inc)
    rel = write_report(root, inc, now)
    print('AGENT5_VERIFY: UNHEALTHY — pause GIỮ, lock GIỮ, incident '
          'attention, report: %s' % rel)
    return 0


def cmd_repair(args, root):
    now = args.now or M.now_iso()
    try:
        M.validate_incident_id(args.incident_id)
        M.require_holder(root, M.AGENT5, args.incident_id)
        inc = M.load_incident(root, args.incident_id)
    except M.MaintenanceError as e:
        print('REFUSED: %s' % e)
        return 1
    a4, a5 = inc['agent4'], inc['agent5']
    if a4.get('result') != 'ESCALATE':
        print('REFUSED: #5 repair chỉ dành cho incident #4=ESCALATE '
              '(hiện %s) — #4 SUCCESS đi đường verify'
              % a4.get('result'))
        return 1
    if a5.get('attempts', 0) >= 1:
        print('REFUSED: incident %s đã dùng hết MỘT attempt Agent #5 — '
              'không retry tự trị' % args.incident_id)
        return 1
    if args.action not in R4.ACTIONS:
        print('REFUSED: action %r ngoài whitelist %s'
              % (args.action, R4.ACTIONS))
        return 1

    res = R4.ACTION_FUNCS[args.action](root, now)
    a5['attempts'] = 1
    a5['diagnosis'] = args.diagnosis or res['diagnosis']
    a5['actions'].append({
        'action': args.action, 'ok': res['ok'],
        'diagnosis': res['diagnosis'], 'files': res['files'],
        'details': res['details'], 'at': now,
    })
    inc['updated_at'] = now
    if not res['ok']:
        # action từ chối trạng thái không an toàn -> STOP, giữ pause
        a5['result'] = 'STOPPED'
        a5['finished_at'] = now
        inc['status'] = 'stopped'
        M.save_incident(root, args.incident_id, inc)
        rel = write_report(root, inc, now)
        print('AGENT5_RESULT: STOP — pause GIỮ, checkpoint GIỮ, report: %s'
              % rel)
        return 0

    # repair xong -> verify lại độc lập
    healthy, checks, tests = verify_state(root, now=now,
                                          skip_tests=args.skip_tests)
    a5['verify'] = checks
    a5['tests'] = ([{**tests, 'at': now}] if tests else a5['tests'])
    a5['finished_at'] = now
    if healthy:
        M.release_lock(root, M.AGENT5, args.incident_id, now,
                       note='Agent #5 repair + verify HEALTHY — resume '
                            'được qua entrypoint bình thường')
        a5['result'] = 'RESUMABLE'
        inc['status'] = 'resumable'
        inc['production_paused'] = False
        M.save_incident(root, args.incident_id, inc)
        print('AGENT5_RESULT: RESUMABLE — maintenance-lock RELEASED, '
              'incident resumable')
        return 0
    a5['result'] = 'STOPPED'
    inc['status'] = 'stopped'
    M.save_incident(root, args.incident_id, inc)
    rel = write_report(root, inc, now)
    print('AGENT5_RESULT: STOP — pause GIỮ, checkpoint GIỮ, report: %s'
          % rel)
    return 0


def cmd_status(args, root):
    try:
        inc = M.load_incident(root, args.incident_id)
    except M.MaintenanceError as e:
        print('REFUSED: %s' % e)
        return 1
    print(json.dumps(inc, ensure_ascii=False, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(description='Agent #5 supervisor/second-line')
    ap.add_argument('--root', default=DEFAULT_ROOT)
    ap.add_argument('--now', default=None,
                    help='ISO timestamp override (test deterministic)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('take')
    t.add_argument('--incident-id', required=True)
    t.set_defaults(fn=cmd_take)
    v = sub.add_parser('verify')
    v.add_argument('--incident-id', required=True)
    v.add_argument('--skip-tests', action='store_true')
    v.set_defaults(fn=cmd_verify)
    r = sub.add_parser('repair')
    r.add_argument('--incident-id', required=True)
    r.add_argument('--action', required=True, choices=list(R4.ACTIONS))
    r.add_argument('--diagnosis')
    r.add_argument('--skip-tests', action='store_true')
    r.set_defaults(fn=cmd_repair)
    s = sub.add_parser('status')
    s.add_argument('--incident-id', required=True)
    s.set_defaults(fn=cmd_status)
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    return args.fn(args, root)


if __name__ == '__main__':
    sys.exit(main())
