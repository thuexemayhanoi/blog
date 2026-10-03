#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""maintenance.py — hợp đồng maintenance-lock + incident registry dùng chung.

Nền tảng cho Agent #4 (repair-agent.py — sửa chữa hạ tầng dòng đầu) và
Agent #5 (supervisor-agent.py — giám sát/second-line). Hợp đồng:

  - MỘT maintenance_lock toàn cục (data/state/maintenance-lock.json):
    trong khi lock active, MỌI op mutating của factory-operator.py
    (prepare-next/qa/publish/release-chunk/recover/requeue/refill) từ
    chối chạy — production mutation tạm dừng (pause thật, không tự khai).
  - Chỉ MỘT agent (#4 hoặc #5) được giữ lock tại một thời điểm — #4 và
    #5 KHÔNG BAO GIỜ mutate đồng thời.
  - Lock có TTL (mặc định 6h); lock hết hạn được takeover RÕ RÀNG và ghi
    dấu stale_takeover vào record (không âm thầm bypass).
  - Incident registry: data/state/incidents/<incident_id>.json — audit
    đầy đủ (trigger, timestamps, diagnosis, actions, tests, result).
  - Incident_id giữ nguyên xuyên suốt #4 -> #5 (SAME incident_id).
  - Giới hạn tự trị mỗi incident: #4 tối đa 1 repair attempt, #5 tối đa
    1 repair attempt (tổng 2) — cưỡng chế bằng counter trong record.
  - Mọi ghi trạng thái CHỈ được rơi vào data/state/** hoặc
    reports/factory/incidents/** — TUYỆT ĐỐI không đụng _posts/,
    _drafts/, data/content-matrix.csv, _data/, _layouts/, _includes/
    (agent không bao giờ sửa bài viết).

Không loop, không polling — mọi lệnh là one-shot, exit code rõ ràng.
"""
import datetime
import json
import os
import re

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

LOCK_REL = 'data/state/maintenance-lock.json'
INCIDENTS_REL = 'data/state/incidents'
REPORTS_REL = 'reports/factory/incidents'

LOCK_TTL_HOURS = 6.0          # lock hết hạn = takeover được (ghi dấu)
AGENT4 = 'agent-4'
AGENT5 = 'agent-5'
HOLDERS = (AGENT4, AGENT5)

INCIDENT_ID_RE = re.compile(r'^INC-[0-9]{8}-[a-z0-9][a-z0-9-]*$')

# paths agent được PHÉP ghi (prefix tương đối từ root)
WRITABLE_PREFIXES = ('data/state/', 'reports/factory/incidents/')
# prefix TUYỆT ĐỐI cấm — article/content của writer và publisher
FORBIDDEN_PREFIXES = ('_posts/', '_drafts/', '_queue/', 'data/content-matrix.csv',
                      '_data/', '_layouts/', '_includes/', 'assets/')


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%SZ')


def parse_iso(s):
    return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(
        tzinfo=datetime.timezone.utc)


def hours_between(a, b):
    return (b - a).total_seconds() / 3600.0


def as_dt(now):
    """Chuẩn hoá input thời gian: ISO string -> datetime UTC (giữ
    nguyên nếu đã là datetime). Cho phép caller truyền cả hai dạng."""
    if isinstance(now, datetime.datetime):
        return now
    return parse_iso(now)


def as_iso(now):
    if isinstance(now, datetime.datetime):
        return now.strftime('%Y-%m-%dT%H:%M:%SZ')
    return now


class MaintenanceError(Exception):
    """Lỗi hợp đồng (không đủ điều kiện / lock conflict)."""


# ------------------------------------------------------------------ io

def _abs(root, rel):
    return os.path.join(root, rel)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def assert_writable_rel(rel):
    """Guard ghi cứng: mọi path agent ghi phải nằm trong whitelist state
    và KHÔNG rơi vào vùng bài viết/nội dung của writer/publisher."""
    norm = rel.replace(os.sep, '/')
    for bad in FORBIDDEN_PREFIXES:
        if norm == bad or norm.startswith(bad):
            raise MaintenanceError(
                'TU CHOI ghi vung noi dung writer/publisher: %s (agent '
                'chi duoc sua ha tang data/state/**)' % rel)
    for ok in WRITABLE_PREFIXES:
        if norm == ok.rstrip('/') or norm.startswith(ok):
            return
    raise MaintenanceError('path ngoai whitelist ha tang: %s' % rel)


# ------------------------------------------------------------------ lock

def lock_path(root):
    return _abs(root, LOCK_REL)


def read_lock(root):
    lk = read_json(lock_path(root), None)
    if lk is None:
        return {'locked': False, 'holder': None, 'incident_id': None,
                'acquired_at': None, 'expires_at': None,
                'updated_at': now_iso(), 'note': 'chua tung lock'}
    return lk


def lock_is_fresh(lk, now):
    """lock đang giữ và chưa hết TTL."""
    if not lk.get('locked'):
        return False
    exp = lk.get('expires_at')
    if not exp:
        return False
    return parse_iso(exp) > as_dt(now)


def acquire_lock(root, holder, incident_id, now, force_stale=False,
                 note=''):
    """Giành maintenance lock cho holder/incident. Từ chối nếu:
    - holder lạ (chỉ agent-4/agent-5);
    - lock đang được giữ TUOI bởi incident khác;
    - lock stale của incident khác khi không force_stale.
    Lock hết hạn: takeover được nhưng phải RÕ RÀNG (force_stale=True),
    ghi dấu stale_takeover vào record."""
    if holder not in HOLDERS:
        raise MaintenanceError('holder la: %s' % holder)
    validate_incident_id(incident_id)
    now = as_iso(now)
    now_dt = as_dt(now)
    lk = read_lock(root)
    if lk.get('locked'):
        same_incident = lk.get('incident_id') == incident_id
        if lock_is_fresh(lk, now):
            if same_incident and lk.get('holder') == holder:
                return lk  # idempotent: đã giữ rồi
            raise MaintenanceError(
                'maintenance-lock dang active (holder=%s, incident=%s, '
                'het han %s) — khong gian lock chong lan'
                % (lk.get('holder'), lk.get('incident_id'),
                   lk.get('expires_at')))
        if not (same_incident or force_stale):
            raise MaintenanceError(
                'lock STALE (holder=%s, incident=%s, het han %s) — '
                'takeover can --force-stale RO RANG (khong am tham '
                'bypass)'
                % (lk.get('holder'), lk.get('incident_id'),
                   lk.get('expires_at')))
        stale_from = {'holder': lk.get('holder'),
                      'incident_id': lk.get('incident_id'),
                      'acquired_at': lk.get('acquired_at'),
                      'expires_at': lk.get('expires_at'),
                      'taken_over_at': now}
    else:
        stale_from = None
    new = {'locked': True, 'holder': holder, 'incident_id': incident_id,
           'acquired_at': now,
           'expires_at': (now_dt + datetime.timedelta(
               hours=LOCK_TTL_HOURS)).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'updated_at': now, 'note': note or 'maintenance active'}
    if stale_from:
        new['stale_takeover'] = stale_from
        new['note'] = ('takeover lock het han (stale) — truoc: holder=%s '
                       'incident=%s' % (stale_from['holder'],
                                        stale_from['incident_id']))
    assert_writable_rel(LOCK_REL)
    write_json_atomic(lock_path(root), new)
    return new


def release_lock(root, holder, incident_id, now, note=''):
    """Nhả lock — chỉ holder giữ lock cho DUNG incident mới được nhả."""
    lk = read_lock(root)
    now = as_iso(now)
    if not lk.get('locked'):
        return lk  # idempotent
    if (lk.get('holder') != holder or
            lk.get('incident_id') != incident_id):
        raise MaintenanceError(
            'khong nha duoc lock cua nguoi khac (holder=%s, incident=%s)'
            % (lk.get('holder'), lk.get('incident_id')))
    out = {'locked': False, 'holder': None, 'incident_id': None,
           'acquired_at': None, 'expires_at': None, 'updated_at': now,
           'note': note or ('released by %s' % holder),
           'last_released_by': holder,
           'last_released_incident': incident_id,
           'last_released_at': now}
    assert_writable_rel(LOCK_REL)
    write_json_atomic(lock_path(root), out)
    return out


def transfer_lock(root, new_holder, incident_id, now, note=''):
    """Chuyển ownership #4 -> #5 cho CUNG incident (lock KHÔNG nhả giữa
    chừng — tránh khoảng trống cho mutation song song)."""
    if new_holder not in HOLDERS:
        raise MaintenanceError('holder la: %s' % new_holder)
    now = as_iso(now)
    lk = read_lock(root)
    if not lk.get('locked') or lk.get('incident_id') != incident_id:
        raise MaintenanceError(
            'khong transfer duoc: lock khong active cho incident %s'
            % incident_id)
    if lk.get('holder') not in HOLDERS:
        raise MaintenanceError('holder hien tai la: %s' % lk.get('holder'))
    lk['holder'] = new_holder
    lk['updated_at'] = now
    lk['transferred_from'] = AGENT4 if new_holder == AGENT5 else AGENT4
    if note:
        lk['note'] = note
    assert_writable_rel(LOCK_REL)
    write_json_atomic(lock_path(root), lk)
    return lk


# ------------------------------------------------------------------ incident

def validate_incident_id(incident_id):
    if not incident_id or not INCIDENT_ID_RE.match(incident_id):
        raise MaintenanceError(
            'incident_id sai dinh dang INC-YYYYMMDD-slug: %r' % incident_id)


def incident_path(root, incident_id):
    validate_incident_id(incident_id)
    return _abs(root, '%s/%s.json' % (INCIDENTS_REL, incident_id))


def report_path(root, incident_id):
    validate_incident_id(incident_id)
    return _abs(root, '%s/%s.md' % (REPORTS_REL, incident_id))


def incident_exists(root, incident_id):
    return os.path.exists(incident_path(root, incident_id))


def load_incident(root, incident_id):
    p = incident_path(root, incident_id)
    if not os.path.exists(p):
        raise MaintenanceError('incident chua ton tai: %s' % incident_id)
    return read_json(p)


def save_incident(root, incident_id, data):
    assert_writable_rel('%s/%s.json' % (INCIDENTS_REL, incident_id))
    write_json_atomic(incident_path(root, incident_id), data)


def new_incident(incident_id, trigger, source, now):
    """Khung record incident mới — mọi trường audit bắt buộc có chỗ."""
    return {
        'incident_id': incident_id,
        'status': 'open',          # open -> repairing -> recovered |
                                   # resumable | attention | stopped
        'trigger': trigger,
        'source': source or '',
        'created_at': now,
        'updated_at': now,
        'production_paused': True,  # maintenance lock đang giữ
        'diagnosis': None,
        'agent4': {
            'attempts': 0,          # tối đa 1
            'started_at': None,
            'result': None,        # SUCCESS | ESCALATE
            'diagnosis': None,
            'actions': [],         # [{action, files, details, at}]
            'tests': [],           # [{command, exit, summary, at}]
            'finished_at': None,
        },
        'agent5': {
            'attempts': 0,          # tối đa 1
            'started_at': None,
            'verify': None,        # HEALTHY | UNHEALTHY
            'result': None,        # RECOVERED | RESUMABLE | STOPPED
            'diagnosis': None,
            'actions': [],
            'tests': [],
            'finished_at': None,
        },
    }


# ------------------------------------------------------------------ guard

def require_holder(root, holder, incident_id):
    """Bắt buộc caller đang giữ lock cho đúng incident — chặn mutate
    không lock / lock của incident khác / holder khác."""
    lk = read_lock(root)
    if not lk.get('locked'):
        raise MaintenanceError(
            'maintenance-lock KHONG active — tu choi mutate (khong bao '
            'gio sua ha tang khi chua gianh lock)')
    if lk.get('holder') != holder:
        raise MaintenanceError(
            'lock dang thuoc holder=%s (yeu cau %s) — #4/#5 khong '
            'mutate dong thoi' % (lk.get('holder'), holder))
    if lk.get('incident_id') != incident_id:
        raise MaintenanceError(
            'lock thuoc incident=%s (yeu cau %s)'
            % (lk.get('incident_id'), incident_id))
    return lk
