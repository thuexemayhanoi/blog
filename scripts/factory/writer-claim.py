#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""writer-claim.py — MULTI-WRITER lease registry của /blog (schema v2).

Port từ thuexemayhanoi/vanchinh scripts/writer_claim.py (SOURCE OF TRUTH)
thích ứng engine /blog (matrix data/content-matrix.csv, cột id/status,
draft _drafts/, publisher scripts/factory/factory-operator.py), rồi
HARDEN cho 3 writer AI độc lập chạy đồng thời (provider-neutral: slot
W1/W2/W3 có thể do bất kỳ AI nào giữ, KHÔNG có tên nhà cung cấp nào
trong logic).

HỢP ĐỒNG (TURBO MULTI-WRITER):
  - tối đa 3 slot (W1,W2,W3 — MAX_WRITERS); MỘT slot thuộc ĐÚNG MỘT
    phiên (session) hợp lệ tại một thời điểm. Session id là định danh
    công khai ngẫu nhiên (s-xxxxxxxxxxxx): phiên mặc định của một working
    copy được lưu trong git-dir (KHÔNG commit), có thể truyền tường minh
    (--session / env FACTORY_WRITER_SESSION) để AI này bàn giao slot cho
    AI khác. Phiên KHÁC không thể renew/ghi đè/release slot còn hạn;
  - mỗi writer lease tối đa MAX_LEASE (10) ID theo THỨ TỰ MATRIX; tổng
    tối đa 30 ID in-flight (3 x 10);
  - ID được giữ cho tới khi PUBLISHED / EXISTING / BLOCKED: gồm cả hàng
    PLANNED và hàng in-flight (WRITING/QA/PASS/REPAIR) — chủ lease vẫn
    sở hữu hàng REPAIR của mình; lease hết hạn -> hàng in-flight thành
    "orphan" và có thể được writer khác nhận (--adopt);
  - lease sống tới expires_at = heartbeat_at + TTL (mặc định 48h, tùy
    chỉnh --ttl-hours 0.25..48). Hết hạn là CHẾT: slot + ID PLANNED
    được reclaim hợp lệ bởi phiên khác (epoch +1). KHÔNG BAO GIỜ chiếm
    lease còn hạn, kể cả khi vượt MAX_WRITERS (người đến sau thua);
  - registry SELF-HEAL qua prune_registry() trong mọi lệnh GHI:
      (a) lease hết hạn bị drop;
      (b) id không còn leasable (PUBLISHED/EXISTING/BLOCKED/REVIEW/lạ)
          bị drop;
      (c) lease không còn id (đã publish hết) bị xóa — KỂ CẢ lease có
          session: slot KHÔNG được đặt chỗ giữa hai batch (một lease rỗng
          không bảo vệ ID nào, mà khóa slot tới 48h nếu container của phiên
          bị tạo lại); phiên cũ chỉ cần `begin`/`claim` lại;
      (d) ID trùng giữa hai lease sống -> giữ lease claimed_at SỚM HƠN;
      (e) vượt MAX_WRITERS -> bỏ lease claim MUỚI NHẤT (không đụng
          lease cũ đang sống);
  - registry hỏng JSON/sai cấu trúc => FAIL-CLOSED (exit 1, code
    REGISTRY_CORRUPT), KHÔNG coi là rỗng. Phục hồi:
    `repair-registry --from-git` lấy bản hợp lệ gần nhất trong git
    history. Ghi file nguyên tử (tmp + fsync + replace);
  - thời gian luôn UTC (calendar.timegm) — KHÔNG phụ thuộc múi giờ máy;
  - registry sống ở data/state/writer-claims.json (env WRITER_CLAIMS).
    Path nằm NGOÀI paths filter của factory-publish.yml nên push registry
    KHÔNG BAO GIỜ kích hoạt production run;
  - đua push registry: dùng scripts/factory/writer-session.py (CAS client:
    fetch -> tính claim trên truth mới nhất -> push, non-FF thì LÀM LẠI
    transaction, KHÔNG force push);
  - v1 leases (không session/heartbeat_at) vẫn hợp lệ ("legacy"): renew
    bằng tên slot như cũ; phiên đầu tiên chạm vào sẽ nhận (adopt) lease.

QUAN TRỌNG (tách bạch ownership và production state):
  - lệnh này KHÔNG mutate matrix/checkpoint/production-control — lease
    registry CHỈ là ownership của WRITER;
  - claim PLANNED -> WRITING thật sự vẫn do publisher/engine canonical
    xử lý (factory-operator.py prepare-next qua factory-queue.py trong
    factory-publish.yml).

Lệnh:
  claim   --writer W [--count N|--ids A,B] [--session S] [--ttl-hours H]
          [--label L] [--adopt]     lease N hàng PLANNED còn tự do (hoặc
                                    đúng --ids); --adopt nhận cả hàng
                                    in-flight orphan; không --count thì
                                    bù cho đủ MAX_LEASE
  heartbeat --writer W [--session S] [--ttl-hours H]   gia hạn slot
  release --writer W [--ids A,B | --all] [--session S]  bỏ lease của CHÍNH
                                    phiên mình (--all = trả luôn slot)
  show                              in registry + hàng còn tự do (ĐỌC,
                                    không ghi)
  status  [--writer W] [--session S] trạng thái slot chi tiết (ĐỌC)
  prune                             rà hiệu lực lease NGAY BÂY GIỜ (ghi)
  merge   --file registry.json      gộp registry remote vào local
                                    (claimed_at SỚM HƠN thắng)
  check-registry                    kiểm tra bất biến registry (exit 1 nếu hỏng)
  repair-registry [--from-git [--ref R]]  sửa trùng lặp / lấy bản hợp lệ
                                    từ git history

Thoát: 0 ok, 1 lỗi (KHÔNG đổi gì khi lỗi).
"""
import argparse
import calendar
import csv
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
MATRIX = ROOT / 'data' / 'content-matrix.csv'
REGISTRY = pathlib.Path(os.environ.get('WRITER_CLAIMS')
                        or str(ROOT / 'data' / 'state' / 'writer-claims.json'))
SCHEMA_VERSION = '2'
SLOTS = ('W1', 'W2', 'W3')
SLOT_RE = re.compile(r'^W[1-3]$')
# token phiên: chỉ ký tự an toàn (được ghi nguyên văn vào frontmatter draft —
# KHÔNG cho dấu cách/xuống dòng/':' làm hỏng YAML hay chèn khóa lạ)
SESSION_RE = re.compile(r'^[A-Za-z0-9._-]{1,64}$')
ID_RE = re.compile(r'^BLG-\d+$')
MAX_LEASE = 10     # lease sống tối đa mỗi writer (write-ahead buffer)
MAX_WRITERS = 3    # registry từ chối writer thứ 4
TTL_HOURS = 48.0   # TTL mặc định; mỗi claim/heartbeat gia hạn
MIN_TTL_HOURS = 0.25
MAX_TTL_HOURS = 48.0
PLANNED = 'PLANNED'
INFLIGHT = ('WRITING', 'QA', 'PASS', 'REPAIR')   # đã claim bởi engine
LEASABLE = (PLANNED,) + INFLIGHT


class RegistryCorrupt(Exception):
    """Registry tồn tại nhưng hỏng — FAIL-CLOSED, KHÔNG coi là rỗng."""


# --------------------------------------------------------------- thời gian

def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _iso(epoch):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(epoch))


def _epoch_of(iso):
    """Epoch giây (UTC) của timestamp ISO 'YYYY-MM-DDTHH:MM:SSZ'; chịu
    phân số giây. Timestamp hỏng được coi là chết (0.0) để entry cũ không
    bao giờ sống lại. DÙNG calendar.timegm (UTC thuần): time.mktime diễn
    giải theo múi giờ MÁY — lệch ±7h giữa phiên ở múi giờ khác nhau, làm
    lease còn hạn bị coi là hết hạn (hoặc ngược lại)."""
    e = _parse_ts(iso)
    return 0.0 if e is None else e


_TS_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.\d+)?'
                    r'(Z|[+-]\d{2}:?\d{2})?$')


def _parse_ts(iso):
    """Epoch UTC của timestamp ISO-8601 (Z hoặc ±hh:mm, chịu phân số giây);
    None nếu không phân tích được (KHÔNG đoán)."""
    if not iso or not isinstance(iso, str):
        return None
    m = _TS_RE.match(iso.strip())
    if not m:
        return None
    try:
        base = float(calendar.timegm(time.strptime(
            '%sT%sZ' % (m.group(1), m.group(2)), '%Y-%m-%dT%H:%M:%SZ')))
    except Exception:
        return None
    tz = m.group(3)
    if tz and tz != 'Z':
        sign = 1 if tz[0] == '+' else -1
        digits = tz[1:].replace(':', '')
        base -= sign * (int(digits[:2]) * 3600 + int(digits[2:]) * 60)
    return base


def _clamp_ttl(ttl_hours=None):
    if ttl_hours is None:
        env = os.environ.get('FACTORY_LEASE_TTL_HOURS')
        try:
            ttl_hours = float(env) if env else TTL_HOURS
        except ValueError:
            ttl_hours = TTL_HOURS
    return max(MIN_TTL_HOURS, min(float(ttl_hours), MAX_TTL_HOURS))


def _expires_at(now=None, ttl_hours=None):
    now = now if now is not None else time.time()
    return _iso(now + _clamp_ttl(ttl_hours) * 3600)


# ------------------------------------------------------------- matrix/registry

def load_matrix_rows():
    with open(MATRIX, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def empty_registry():
    return {'schema_version': SCHEMA_VERSION, 'updated_at': None,
            'leases': {}}


def parse_registry(text):
    """Parse + kiểm cấu trúc; raise RegistryCorrupt (KHÔNG trả rỗng)."""
    try:
        d = json.loads(text)
    except Exception as e:
        raise RegistryCorrupt('registry khong doc duoc (%s: %s)'
                              % (e.__class__.__name__, e))
    if not isinstance(d, dict) or not isinstance(d.get('leases'), dict):
        raise RegistryCorrupt('registry sai cau truc: thieu object "leases"')
    for w, l in d['leases'].items():
        if not isinstance(l, dict):
            raise RegistryCorrupt('lease %s sai cau truc (khong phai object)'
                                  % w)
        if not isinstance(l.get('ids', []), list):
            raise RegistryCorrupt('lease %s: "ids" khong phai list' % w)
        bad = [a for a in l.get('ids', [])
               if not (isinstance(a, str) and ID_RE.match(a))]
        if bad:
            raise RegistryCorrupt('lease %s: ID khong hop le %r' % (w, bad[:3]))
        exp = l.get('expires_at')
        if exp not in (None, '') and _parse_ts(exp) is None:
            # timestamp hỏng KHÔNG được coi là "đã chết" (sẽ làm lease sống
            # bị chiếm): fail-closed, người vận hành sửa tay
            raise RegistryCorrupt('lease %s: expires_at khong phan tich duoc '
                                  '(%r)' % (w, exp))
    d.setdefault('schema_version', '1')
    return d


def load_registry(path=None):
    """File vắng -> registry rỗng (single-writer legacy do selector quyết
    định); file HỎNG -> RegistryCorrupt (fail-closed)."""
    p = pathlib.Path(path) if path else REGISTRY
    if not p.is_file():
        return empty_registry()
    return parse_registry(p.read_text(encoding='utf-8'))


def _write_atomic(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.wc-', suffix='.tmp',
                               dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def dump_registry(reg):
    reg['schema_version'] = SCHEMA_VERSION
    reg['updated_at'] = _now()
    reg['leases'] = {w: l for w, l in sorted(reg['leases'].items())}
    return json.dumps(reg, ensure_ascii=False, indent=2)


def save_registry(reg, path=None):
    _write_atomic(pathlib.Path(path) if path else REGISTRY, dump_registry(reg))


# ------------------------------------------------------------------ session

def _git_dir():
    try:
        r = subprocess.run(['git', 'rev-parse', '--absolute-git-dir'],
                           cwd=str(ROOT), capture_output=True, text=True,
                           timeout=10)
        d = r.stdout.strip()
        if r.returncode == 0 and d and os.path.isdir(d):
            return pathlib.Path(d)
    except Exception:
        pass
    return None


def _session_dir():
    env = os.environ.get('FACTORY_SESSION_DIR')
    if env:
        return pathlib.Path(env)
    gd = _git_dir()
    if gd is not None:
        return gd / 'factory-writer-sessions'
    return ROOT / '.factory-writer-sessions'


def new_session_id():
    return 's-' + uuid.uuid4().hex[:12]


class BadSession(ValueError):
    """Token phiên không hợp lệ (ký tự lạ / dài quá)."""


def valid_session(s):
    return isinstance(s, str) and bool(SESSION_RE.match(s))


def _session_file():
    return _session_dir() / 'session.json'


def default_session(slot=None, create=True):
    """Phiên của working copy này. Thứ tự:
      1. env FACTORY_WRITER_SESSION (token TƯỜNG MINH do AI/chủ xe đặt: nối
         việc sau khi container bị tạo lại, hoặc bàn giao AI -> AI);
      2. file phiên của working copy (git-dir, KHÔNG commit) — MỘT phiên cho
         cả working copy (một working copy = một AI = tối đa MỘT slot);
      3. ngẫu nhiên (lưu vào git-dir ở lần đầu).
    KHÔNG suy phiên từ danh tính git: nhiều AI cùng một nhà cung cấp dùng
    CHUNG một danh tính git, suy ra phiên sẽ coi chúng là MỘT phiên và hai AI
    sẽ cùng ghi một slot/ID. Muốn một "người viết" sống sót qua việc tạo lại
    container: đặt FACTORY_WRITER_SESSION=<token riêng của nó> (hoặc
    `--session`; `begin --session` lưu lại cho các lệnh sau). Token chỉ gồm
    [A-Za-z0-9._-], tối đa 64 ký tự (nó được ghi vào frontmatter draft).
    `slot` giữ lại cho tương thích chữ ký, không còn ảnh hưởng tên file."""
    env = os.environ.get('FACTORY_WRITER_SESSION', '').strip()
    if env:
        if not valid_session(env):
            raise BadSession('FACTORY_WRITER_SESSION khong hop le (chi '
                             '[A-Za-z0-9._-], toi da 64 ky tu): %r' % env[:80])
        return env
    f = _session_file()
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
        if isinstance(d, dict) and valid_session(d.get('session')):
            return d['session']
    except Exception:
        pass
    if not create:
        return None
    sid = new_session_id()
    save_session(sid)
    return sid


def save_session(sess):
    """Lưu phiên của working copy (sau `begin --session S` tường minh, để
    status/check/push/confirm nhận ra cùng phiên)."""
    if not valid_session(sess):
        raise BadSession('session khong hop le (chi [A-Za-z0-9._-], toi da '
                         '64 ky tu): %r' % str(sess)[:80])
    try:
        _write_atomic(_session_file(), json.dumps(
            {'session': sess, 'saved_at': _now()}))
    except OSError:
        pass   # không ghi được: phiên chỉ sống trong tiến trình này


# --------------------------------------------------------------- lõi thuần

def _live_leases(reg, now=None):
    """{article_id: (writer, lease)} của mọi lease CHƯA hết hạn."""
    now = now if now is not None else time.time()
    out = {}
    for w, l in reg['leases'].items():
        if not isinstance(l, dict):
            continue
        if _epoch_of(l.get('expires_at', '')) < now:
            continue
        for a in l.get('ids', []):
            out.setdefault(a, (w, l))
    return out


def live_conflicts(reg, now=None):
    """{article_id: [slot, ...]} cho ID bị GIỮ BỞI >= 2 lease còn sống. Registry
    như vậy mơ hồ về chủ sở hữu (merge git thô của hai writer): người gọi
    phải fail-closed, KHÔNG được chọn đại một slot."""
    now = now if now is not None else time.time()
    held = {}
    for w, l in reg['leases'].items():
        if not isinstance(l, dict) or _epoch_of(l.get('expires_at', '')) < now:
            continue
        for a in l.get('ids', []):
            held.setdefault(a, []).append(w)
    return {a: sorted(ws) for a, ws in held.items() if len(ws) > 1}


def _planned_ids(rows):
    """ID các hàng PLANNED, deterministic theo THỨ TỰ MATRIX."""
    return [r['id'] for r in rows if r['status'] == PLANNED]


def _claim_key(lease, slot):
    return (_epoch_of(lease.get('claimed_at') or ''), slot)


def prune_registry(reg, rows, now=None):
    """Ép hiệu lực lease TẠI CHỖ (xem docstring module). Trả report dict,
    KHÔNG bao giờ raise, KHÔNG đụng lease còn sống của người khác."""
    now = now if now is not None else time.time()
    report = {'expired': [], 'invalid_ids': {}, 'removed_writers': [],
              'duplicates': [], 'capped': [], 'kept': {}}
    for w in [w for w, l in reg['leases'].items()
              if _epoch_of(l.get('expires_at', '')) < now]:
        del reg['leases'][w]
        report['expired'].append(w)
    status = {r['id']: r['status'] for r in rows}
    for w in list(reg['leases'].keys()):
        lease = reg['leases'][w]
        ids = list(lease.get('ids', []))
        keep = [a for a in ids if status.get(a) in LEASABLE]
        dropped = [a for a in ids if a not in set(keep)]
        if dropped:
            report['invalid_ids'][w] = dropped
        lease['ids'] = keep
        if not keep:
            # lease không còn id: xóa (như semantics cũ của v1). Lease rỗng
            # không bảo vệ ID nào; giữ nó chỉ khóa slot (tới expires_at) với
            # phiên đã mất container.
            del reg['leases'][w]
            report['removed_writers'].append(w)
    # (d) ID trùng giữa hai lease sống: giữ lease claim SỚM HƠN
    owner = {}
    for w in sorted(reg['leases'],
                    key=lambda x: _claim_key(reg['leases'][x], x)):
        lease = reg['leases'][w]
        keep = []
        for a in lease.get('ids', []):
            if a in owner and owner[a] != w:
                report['duplicates'].append(
                    {'id': a, 'kept_by': owner[a], 'dropped_from': w})
            else:
                owner[a] = w
                keep.append(a)
        lease['ids'] = keep
        if not keep:
            del reg['leases'][w]
            report['removed_writers'].append(w)
    # (e) vượt MAX_WRITERS: bỏ lease claim MỚI NHẤT (người đến sau thua)
    if len(reg['leases']) > MAX_WRITERS:
        by_age = sorted(reg['leases'].items(),
                        key=lambda kv: _claim_key(kv[1], kv[0]))
        for w, _ in by_age[MAX_WRITERS:]:
            del reg['leases'][w]
            report['capped'].append(w)
    report['kept'] = {w: list(l['ids']) for w, l in reg['leases'].items()}
    return report


def _changed(report):
    return bool(report['expired'] or report['invalid_ids']
                or report['removed_writers'] or report['duplicates']
                or report['capped'])


def _err(code, msg, **extra):
    d = {'ok': False, 'code': code, 'error': msg}
    d.update(extra)
    return d


def apply_claim(reg, rows, writer, session, count=None, ids=None, now=None,
                ttl_hours=None, label=None, adopt=False,
                allow_empty_pool=False):
    """Claim THUẦN trên registry trong bộ nhớ (writer-session.py dùng lại
    cho CAS). Mutate `reg` CHỈ khi thành công; trả dict {ok: True, ...}
    hoặc {ok: False, code, error, ...}. KHÔNG I/O."""
    now = now if now is not None else time.time()
    if not SLOT_RE.match(writer or ''):
        return _err('BAD_SLOT', 'slot khong hop le %r (chi W1, W2, W3)'
                    % writer, writer=writer)
    if not session:
        return _err('NO_SESSION', 'thieu session id', writer=writer)
    if not valid_session(session):
        return _err('BAD_SESSION', 'session id khong hop le (chi '
                    '[A-Za-z0-9._-], toi da 64 ky tu)', writer=writer)
    work = json.loads(json.dumps(reg))      # sao chép: lỗi thì KHÔNG đổi reg
    prev = work['leases'].get(writer)       # trước prune: biết epoch cũ
    report = prune_registry(work, rows, now)
    status_of = {r['id']: r['status'] for r in rows}
    lease = work['leases'].get(writer)
    legacy_adopted = False
    takeover = None
    if lease is not None:
        cur = lease.get('session')
        if cur and cur != session:
            return _err('SLOT_HELD',
                        'slot %s dang duoc phien khac giu (lease song den '
                        '%s) — khong chiem lease con han'
                        % (writer, lease.get('expires_at')),
                        writer=writer, holder_session=cur,
                        expires_at=lease.get('expires_at'))
        legacy_adopted = not cur
    else:
        if len(work['leases']) >= MAX_WRITERS:
            return _err('NO_FREE_SLOT',
                        'registry da giu %d writer song' % MAX_WRITERS,
                        writer=writer, writers=sorted(work['leases']))
        if prev is not None and prev.get('session') \
                and prev.get('session') != session:
            takeover = {'previous_session': prev.get('session'),
                        'previous_expires_at': prev.get('expires_at')}
    live = _live_leases(work, now)
    already = list(lease['ids']) if lease else []
    resumed_after_lapse = []
    if lease is None and prev is not None and prev.get('session') == session:
        # CÙNG phiên quay lại sau khi lease hết hạn mà chưa ai nhận slot: nối
        # lại các ID của chính mình còn leasable (kể cả hàng REPAIR) — không
        # bỏ rơi chúng thành orphan rồi cấp ID mới.
        resumed_after_lapse = [
            a for a in prev.get('ids', [])
            if status_of.get(a) in LEASABLE
            and not (live.get(a) and live[a][0] != writer)]
        already = list(resumed_after_lapse)
    want_ids = [a for a in (ids or []) if a]
    for a in want_ids:
        st = status_of.get(a)
        holder = live.get(a)
        if holder and holder[0] != writer:
            return _err('ID_TAKEN', '%s: da bi lease boi writer %s'
                        % (a, holder[0]), writer=writer, id=a)
        if st == PLANNED:
            continue
        if st in INFLIGHT and (a in already or adopt):
            continue
        if st in INFLIGHT:
            return _err('NOT_PLANNED', '%s: hang %s dang in-flight khong co '
                        'lease song — dung --adopt de nhan' % (a, st),
                        writer=writer, id=a)
        return _err('NOT_PLANNED', '%s: khong phai hang PLANNED' % a,
                    writer=writer, id=a)
    room = MAX_LEASE - len(already)
    if want_ids:
        new_ids = [a for a in want_ids if a not in already]
        want_count = len(new_ids)
    else:
        want_count = (count if count is not None else max(room, 0))
        new_ids = None
    if want_count > MAX_LEASE or want_count > room:
        return _err('LEASE_FULL', 'muc lease toi da la %d moi writer'
                    % MAX_LEASE, writer=writer, already_leased=already,
                    requested=want_count)
    if new_ids is None:
        new_ids = []
        if adopt:
            orphans = [r['id'] for r in rows if r['status'] in INFLIGHT
                       and r['id'] not in live and r['id'] not in already]
            new_ids.extend(orphans[:want_count])
        free = [a for a in _planned_ids(rows)
                if (a not in live or live[a][0] == writer)
                and a not in already and a not in new_ids]
        new_ids.extend(free[:max(want_count - len(new_ids), 0)])
        if want_count > 0 and not new_ids and not (already
                                                   and allow_empty_pool):
            return _err('NO_FREE_ID', 'khong con hang PLANNED tu do de lease',
                        writer=writer, free_count=0)
    lease_ids = sorted(set(already + new_ids))
    if not lease_ids:
        return _err('EMPTY_CLAIM', 'khong co ID nao de giu (count=0 va slot '
                    '%s chua co lease song) — lease rong khong duoc tao'
                    % writer, writer=writer)
    ttl_eff = _clamp_ttl(ttl_hours if ttl_hours is not None
                         else (lease or {}).get('ttl_hours'))
    epoch = int((lease or prev or {}).get('epoch') or 0)
    if lease is None and (takeover or prev is None):
        epoch += 1
    elif lease is not None and legacy_adopted:
        epoch = max(epoch, 1)
    new_lease = {
        'ids': lease_ids,
        'session': session,
        'epoch': epoch or 1,
        'claimed_at': (lease or {}).get('claimed_at') or _iso(now),
        'heartbeat_at': _iso(now),
        'ttl_hours': ttl_eff,
        'expires_at': _expires_at(now, ttl_eff),
    }
    if label or (lease or {}).get('label'):
        new_lease['label'] = (label or lease.get('label'))[:80]
    work['leases'][writer] = new_lease
    reg.clear()
    reg.update(work)
    repair_first = [a for a in lease_ids if status_of.get(a) == 'REPAIR']
    return {'ok': True, 'writer': writer, 'session': session,
            'epoch': new_lease['epoch'], 'claimed': new_ids,
            'leased_total': lease_ids, 'count': len(lease_ids),
            'claimed_at': new_lease['claimed_at'],
            'heartbeat_at': new_lease['heartbeat_at'],
            'expires_at': new_lease['expires_at'],
            'repair_first': repair_first,
            'legacy_adopted': legacy_adopted, 'takeover': takeover,
            'resumed_after_lapse': resumed_after_lapse,
            'pruned': report['kept'] and {k: v for k, v in report.items()
                                          if k != 'kept' and v}}


def apply_heartbeat(reg, rows, writer, session, now=None, ttl_hours=None):
    """Gia hạn slot của CHÍNH phiên mình (không đổi ID). Thuần."""
    now = now if now is not None else time.time()
    if not SLOT_RE.match(writer or ''):
        return _err('BAD_SLOT', 'slot khong hop le %r' % writer, writer=writer)
    if not valid_session(session):
        return _err('BAD_SESSION', 'session id khong hop le', writer=writer)
    work = json.loads(json.dumps(reg))
    prune_registry(work, rows, now)
    lease = work['leases'].get(writer)
    if lease is None:
        return _err('NO_LEASE', 'slot %s khong con lease song (het han hoac '
                    'chua claim) — chay claim/begin lai' % writer,
                    writer=writer)
    cur = lease.get('session')
    if cur and cur != session:
        return _err('NOT_OWNER', 'slot %s thuoc phien khac' % writer,
                    writer=writer, holder_session=cur)
    ttl_eff = _clamp_ttl(ttl_hours if ttl_hours is not None
                         else lease.get('ttl_hours'))
    lease['session'] = session
    lease['epoch'] = max(int(lease.get('epoch') or 0), 1)
    lease['heartbeat_at'] = _iso(now)
    lease['ttl_hours'] = ttl_eff
    lease['expires_at'] = _expires_at(now, ttl_eff)
    reg.clear()
    reg.update(work)
    return {'ok': True, 'writer': writer, 'session': session,
            'epoch': lease['epoch'], 'leased_total': list(lease['ids']),
            'heartbeat_at': lease['heartbeat_at'],
            'expires_at': lease['expires_at']}


def apply_release(reg, rows, writer, session, ids=None, end=False, now=None):
    """Release ID (hoặc cả slot nếu end) — CHỈ chủ lease. Thuần."""
    now = now if now is not None else time.time()
    if not valid_session(session):
        return _err('BAD_SESSION', 'session id khong hop le', writer=writer)
    work = json.loads(json.dumps(reg))
    prune_registry(work, rows, now)
    mine = work['leases'].get(writer)
    if not mine:
        return {'ok': True, 'writer': writer, 'released': [],
                'leased_total': [], 'ended': False}
    cur = mine.get('session')
    if cur and cur != session:
        return _err('NOT_OWNER', 'slot %s thuoc phien khac — chi chu lease '
                    'moi release duoc' % writer, writer=writer,
                    holder_session=cur)
    drop = [a for a in (ids or []) if a in mine['ids']]
    if end:
        drop = list(mine['ids'])
    keep = [a for a in mine['ids'] if a not in set(drop)]
    ended = False
    if end or not keep:
        # release hết ID = trả luôn slot (như v1; phiên có thể begin lại
        # ngay).
        del work['leases'][writer]
        ended = True
    else:
        mine['ids'] = keep
        if not mine.get('session'):
            mine['session'] = session
    reg.clear()
    reg.update(work)
    return {'ok': True, 'writer': writer, 'released': sorted(drop),
            'leased_total': [] if ended else keep, 'ended': ended}


def check_invariants(reg, rows=None, now=None):
    """Bất biến registry. Trả list lỗi (rỗng = hợp lệ)."""
    now = now if now is not None else time.time()
    problems = []
    leases = reg.get('leases', {})
    if len(leases) > MAX_WRITERS:
        problems.append('co %d slot (> %d)' % (len(leases), MAX_WRITERS))
    seen = {}
    status = {r['id']: r['status'] for r in rows} if rows else None
    for w, l in leases.items():
        if not SLOT_RE.match(w):
            problems.append('slot %r khong hop le (chi W1..W3)' % w)
        ids = l.get('ids', [])
        if len(ids) > MAX_LEASE:
            problems.append('slot %s giu %d ID (> %d)' % (w, len(ids),
                                                          MAX_LEASE))
        if len(set(ids)) != len(ids):
            problems.append('slot %s co ID lap' % w)
        live = _epoch_of(l.get('expires_at', '')) >= now
        for a in ids:
            if live:
                if a in seen:
                    problems.append('ID %s bi giu boi hai lease song (%s, %s)'
                                    % (a, seen[a], w))
                seen[a] = w
            if status is not None and a not in status:
                problems.append('ID %s (slot %s) khong co trong matrix'
                                % (a, w))
    by_session = {}
    for w, l in leases.items():
        s = l.get('session')
        if s and _epoch_of(l.get('expires_at', '')) >= now:
            by_session.setdefault(s, []).append(w)
    for s, ws in sorted(by_session.items()):
        if len(ws) > 1:
            problems.append('phien %s giu %d slot song (%s) — moi phien chi '
                            'duoc MOT slot' % (s, len(ws), ','.join(sorted(ws))))
    return problems


def orphan_rows(reg, rows, now=None):
    """ID in-flight (WRITING/QA/PASS/REPAIR) KHÔNG thuộc lease sống nào —
    orphan, nhận bằng `begin --ids ... --adopt`. Thuần, không ghi."""
    now = now if now is not None else time.time()
    work = json.loads(json.dumps(reg))
    prune_registry(work, rows, now)
    held = set(_live_leases(work, now))
    return [r['id'] for r in rows
            if r['status'] in INFLIGHT and r['id'] not in held]


# --------------------------------------------------------------------- CLI

def _out_err(res):
    d = {k: v for k, v in res.items() if k != 'ok'}
    print(json.dumps(d, ensure_ascii=False))
    return 1


def _load_all():
    return load_registry(), load_matrix_rows()


def _persist_if_changed(reg, report):
    if _changed(report):
        save_registry(reg)


def cmd_claim(writer, count=None, ids=None, now=None, session=None,
              ttl_hours=None, label=None, adopt=False):
    reg, rows = _load_all()
    sess = session or default_session(writer)
    res = apply_claim(reg, rows, writer, sess, count=count, ids=ids, now=now,
                      ttl_hours=ttl_hours, label=label, adopt=adopt)
    if not res['ok']:
        return _out_err(res)
    save_registry(reg)
    res.pop('ok')
    res['registry'] = str(REGISTRY)
    print('BLOG_WRITER_CLAIM ' + json.dumps(res, ensure_ascii=False))
    return 0


def cmd_heartbeat(writer, session=None, ttl_hours=None):
    reg, rows = _load_all()
    sess = session or default_session(writer, create=False) \
        or default_session(writer)
    res = apply_heartbeat(reg, rows, writer, sess, ttl_hours=ttl_hours)
    if not res['ok']:
        return _out_err(res)
    save_registry(reg)
    res.pop('ok')
    print('BLOG_WRITER_HEARTBEAT ' + json.dumps(res, ensure_ascii=False))
    return 0


def cmd_release(writer, ids, session=None, end=False):
    reg, rows = _load_all()
    sess = session or default_session(writer, create=False) \
        or default_session(writer)
    res = apply_release(reg, rows, writer, sess, ids=ids, end=end)
    if not res['ok']:
        return _out_err(res)
    save_registry(reg)
    res.pop('ok')
    print(json.dumps(res, ensure_ascii=False))
    return 0


def _slot_view(w, l, status_of, now):
    exp = _epoch_of(l.get('expires_at', ''))
    ids = list(l.get('ids', []))
    return {'session': l.get('session'), 'epoch': l.get('epoch'),
            'label': l.get('label'), 'legacy': not l.get('session'),
            'claimed_at': l.get('claimed_at'),
            'heartbeat_at': l.get('heartbeat_at'),
            'expires_at': l.get('expires_at'), 'live': exp >= now,
            'remaining_s': int(exp - now) if exp >= now else 0,
            'ids': ids,
            'inflight': {a: status_of.get(a) for a in ids
                         if status_of.get(a) in INFLIGHT}}


def cmd_show():
    reg, rows = _load_all()
    now = time.time()
    prune_registry(reg, rows, now)           # chỉ trong bộ nhớ (đọc thuần)
    live = _live_leases(reg, now)
    planned = _planned_ids(rows)
    taken = set(live)
    status_of = {r['id']: r['status'] for r in rows}
    orphans = [r['id'] for r in rows if r['status'] in INFLIGHT
               and r['id'] not in taken]
    out = {'writers': {w: l['ids'] for w, l in reg['leases'].items()},
           'slots': {w: _slot_view(w, l, status_of, now)
                     for w, l in reg['leases'].items()},
           'free_slots': [s for s in SLOTS if s not in reg['leases']],
           'planned_total': len(planned),
           'planned_free': [a for a in planned
                            if a not in taken][:MAX_LEASE],
           'orphans': orphans,
           'registry': str(REGISTRY)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_status(writer=None, session=None):
    reg, rows = _load_all()
    now = time.time()
    prune_registry(reg, rows, now)
    status_of = {r['id']: r['status'] for r in rows}
    me = None
    if writer:
        sess = session or default_session(writer, create=False)
        lease = reg['leases'].get(writer)
        me = {'writer': writer, 'session': sess,
              'owns_slot': bool(lease and sess and lease.get('session') == sess),
              'slot_free': lease is None,
              'legacy_lease': bool(lease and not lease.get('session'))}
    out = {'me': me,
           'slots': {w: _slot_view(w, l, status_of, now)
                     for w, l in reg['leases'].items()},
           'free_slots': [s for s in SLOTS if s not in reg['leases']],
           'registry': str(REGISTRY)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_prune():
    reg, rows = _load_all()
    report = prune_registry(reg, rows)
    save_registry(reg)
    print('BLOG_WRITER_PRUNE ' + json.dumps(
        {'report': report, 'registry': str(REGISTRY)},
        ensure_ascii=False, indent=2))
    return 0


def merge_registries(local, other, rows):
    """Gộp registry `other` (remote) vào `local` (thuần, mutate local).
    Xung đột ID: claimed_at SỚM HƠN thắng (phụ: tên slot nhỏ hơn). KHÔNG
    bao giờ chiếm lease sống của slot khác bằng cách đá lease CŨ (vượt
    MAX_WRITERS thì bỏ lease MỚI NHẤT — xem prune_registry)."""
    prune_registry(local, rows)
    valid = set(r['id'] for r in rows if r['status'] in LEASABLE)
    conflicts, lost, invalid = [], [], []
    for w, l in (other.get('leases') or {}).items():
        if not isinstance(l, dict):
            continue
        if _epoch_of(l.get('expires_at', '')) < time.time():
            continue                          # lease hết hạn không vào local
        incoming = list(l.get('ids', []))
        keep = []
        for a in incoming:
            if a not in valid:
                invalid.append({'id': a, 'writer': w})
                continue
            holder = next(((ow, ol) for ow, ol in local['leases'].items()
                           if ow != w and a in ol['ids']), None)
            if holder is None:
                keep.append(a)
                continue
            ow, ol = holder
            if (_epoch_of(l.get('claimed_at') or ''), w) < \
               (_epoch_of(ol.get('claimed_at') or ''), ow):
                ol['ids'] = [x for x in ol['ids'] if x != a]
                if not ol['ids']:
                    del local['leases'][ow]
                conflicts.append({'id': a, 'winner': w, 'loser': ow})
                keep.append(a)
            else:
                lost.append({'id': a, 'winner': ow, 'loser': w})
        if keep:
            mine = local['leases'].get(w) or {}
            same = (not mine.get('session') or not l.get('session')
                    or mine.get('session') == l.get('session'))
            if mine and not same and \
                    _epoch_of(mine.get('claimed_at') or '') <= \
                    _epoch_of(l.get('claimed_at') or ''):
                continue                      # lease local của phiên khác cũ hơn: giữ
            lease = dict(l)
            lease['ids'] = sorted(set(list(mine.get('ids', [])) + keep))[:MAX_LEASE] \
                if same else sorted(keep)[:MAX_LEASE]
            local['leases'][w] = lease
    prune_registry(local, rows)
    return {'merged': True, 'conflicts': conflicts,
            'rejected_not_planned': invalid, 'lost_to_other_writer': lost,
            'writers': {w: l['ids'] for w, l in local['leases'].items()}}


def cmd_merge(path):
    other = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    reg, rows = _load_all()
    out = merge_registries(reg, other, rows)
    save_registry(reg)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_check_registry():
    reg = load_registry()
    rows = load_matrix_rows()
    problems = check_invariants(reg, rows)
    print(json.dumps({'ok': not problems, 'problems': problems,
                      'slots': sorted(reg['leases']),
                      'registry': str(REGISTRY)}, ensure_ascii=False))
    return 0 if not problems else 1


def _git_show(ref, path):
    r = subprocess.run(['git', 'show', '%s:%s' % (ref, path)],
                       cwd=str(ROOT), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def cmd_repair_registry(from_git=False, ref='HEAD'):
    """Khôi phục registry. KHÔNG tạo lease mới, KHÔNG xóa lease còn sống:
      - registry đọc được: chỉ dọn trùng lặp/hết hạn (prune);
      - registry HỎNG + --from-git: lấy bản hợp lệ GẦN NHẤT trong git
        history của file rồi prune (mất tối đa các thay đổi của commit
        hỏng)."""
    rows = load_matrix_rows()
    try:
        reg = load_registry()
        source = 'working-copy'
    except RegistryCorrupt as e:
        if not from_git:
            print(json.dumps({'ok': False, 'code': 'REGISTRY_CORRUPT',
                              'error': str(e),
                              'hint': 'chay repair-registry --from-git'},
                             ensure_ascii=False))
            return 1
        rel = os.path.relpath(str(REGISTRY), str(ROOT))
        log = subprocess.run(['git', 'log', '--format=%H', '-n', '50', ref,
                              '--', rel], cwd=str(ROOT), capture_output=True,
                             text=True).stdout.split()
        reg = None
        source = None
        for sha in log:
            txt = _git_show(sha, rel)
            if txt is None:
                continue
            try:
                reg = parse_registry(txt)
                source = 'git:%s' % sha[:10]
                break
            except RegistryCorrupt:
                continue
        if reg is None:
            print(json.dumps({'ok': False, 'code': 'NO_VALID_VERSION',
                              'error': 'khong tim thay ban hop le trong 50 '
                                       'commit gan nhat'}))
            return 1
    report = prune_registry(reg, rows)
    save_registry(reg)
    print(json.dumps({'ok': True, 'source': source, 'report': report,
                      'registry': str(REGISTRY)}, ensure_ascii=False,
                     indent=2))
    return 0


def _ids_arg(v):
    return [x.strip() for x in v.split(',') if x.strip()] if v else None


def main():
    ap = argparse.ArgumentParser(add_help=True)
    sub = ap.add_subparsers(dest='command', required=True)

    def common(p):
        p.add_argument('--session', default=None,
                       help='session id (mặc định: phiên của working copy)')

    c = sub.add_parser('claim')
    c.add_argument('--writer', required=True)
    g = c.add_mutually_exclusive_group()
    g.add_argument('--count', type=int, default=None)
    g.add_argument('--ids', default=None,
                   help='danh sách id phân tách dấu phẩy')
    c.add_argument('--ttl-hours', type=float, default=None)
    c.add_argument('--label', default=None)
    c.add_argument('--adopt', action='store_true',
                   help='nhận cả hàng in-flight orphan (REPAIR/PASS/...)')
    common(c)
    h = sub.add_parser('heartbeat')
    h.add_argument('--writer', required=True)
    h.add_argument('--ttl-hours', type=float, default=None)
    common(h)
    r = sub.add_parser('release')
    r.add_argument('--writer', required=True)
    rg = r.add_mutually_exclusive_group(required=True)
    rg.add_argument('--ids', default=None)
    rg.add_argument('--all', action='store_true',
                    help='release mọi ID và trả luôn slot')
    common(r)
    sub.add_parser('show')
    st = sub.add_parser('status')
    st.add_argument('--writer', default=None)
    common(st)
    sub.add_parser('prune')
    m = sub.add_parser('merge')
    m.add_argument('--file', required=True,
                   help='bản sao registry JSON từ remote')
    sub.add_parser('check-registry')
    rp = sub.add_parser('repair-registry')
    rp.add_argument('--from-git', action='store_true')
    rp.add_argument('--ref', default='HEAD')
    args = ap.parse_args()
    os.chdir(ROOT)
    try:
        if args.command == 'claim':
            return cmd_claim(args.writer, count=args.count,
                             ids=_ids_arg(args.ids), session=args.session,
                             ttl_hours=args.ttl_hours, label=args.label,
                             adopt=args.adopt)
        if args.command == 'heartbeat':
            return cmd_heartbeat(args.writer, session=args.session,
                                 ttl_hours=args.ttl_hours)
        if args.command == 'release':
            return cmd_release(args.writer, _ids_arg(args.ids) or [],
                               session=args.session, end=args.all)
        if args.command == 'show':
            return cmd_show()
        if args.command == 'status':
            return cmd_status(args.writer, args.session)
        if args.command == 'prune':
            return cmd_prune()
        if args.command == 'merge':
            return cmd_merge(args.file)
        if args.command == 'check-registry':
            return cmd_check_registry()
        if args.command == 'repair-registry':
            return cmd_repair_registry(args.from_git, args.ref)
    except RegistryCorrupt as e:
        print(json.dumps({'code': 'REGISTRY_CORRUPT', 'error': str(e),
                          'hint': 'chay: writer-claim.py repair-registry '
                                  '--from-git'}, ensure_ascii=False))
        return 1
    except BadSession as e:
        print(json.dumps({'code': 'BAD_SESSION', 'error': str(e)},
                         ensure_ascii=False))
        return 1
    return 2


if __name__ == '__main__':
    sys.exit(main())
