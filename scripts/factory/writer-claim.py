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
    phiên (session) hợp lệ tại một thời điểm; MỘT phiên chỉ được giữ MỘT
    slot sống. Quy tắc được thực thi ở lõi claim/heartbeat và CAS client.
    Session id là định danh
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
      (d) registry đọc từ đĩa có ID/session trùng giữa lease sống ->
          FAIL-CLOSED trước prune; không chọn chủ bằng claimed_at;
      (e) vượt MAX_WRITERS -> bỏ lease claim MUỚI NHẤT (không đụng
          lease cũ đang sống);
  - registry hỏng JSON/sai cấu trúc => FAIL-CLOSED (exit 1, code
    REGISTRY_CORRUPT), KHÔNG coi là rỗng. Phục hồi:
    `repair-registry --from-git` lấy bản hợp lệ gần nhất trong git
    history. Ghi file nguyên tử (tmp + fsync + replace);
  - registry ĐỌC ĐƯỢC nhưng mơ hồ chủ (một ID bị >= 2 lease sống giữ, một
    phiên giữ >= 2 slot sống) => exit 1, code REGISTRY_CONFLICT (KHÔNG phải
    REGISTRY_CORRUPT): mọi lệnh từ chối, không ghi gì, và KHÔNG được
    rollback/repair từ git (sẽ làm mất lease sống). Lối ra: chờ lease hết
    TTL hoặc coordinator hóa giải có bằng chứng (docs/RECOVERY.md);
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
  merge   --file registry.json      gộp phần không tranh chấp; không chuyển
                                    chủ slot/ID local đang sống. Cùng slot:
                                    lease v1 (chưa session) + bản đã nhận
                                    = CÙNG chủ (giữ session đã nhận, không
                                    hạ cấp); chỉ hai session cùng có mặt mà
                                    khác nhau mới là REGISTRY_CONFLICT
  check-registry                    kiểm tra bất biến registry (exit 1 nếu hỏng)
  repair-registry [--from-git [--ref R]]  sửa trùng lặp / lấy bản hợp lệ
                                    từ git history

Thoát: 0 ok, 1 lỗi (KHÔNG đổi gì khi lỗi).
"""
import argparse
import calendar
import csv
import json
import math
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
# \Z, KHONG phai $: '$' khop truoc mot '\n' cuoi nen 'W1\n' / 's-a\n' lot qua
# (hai 'slot' W1 va W1\n, phien khong bao gio khop token trong draft)
SLOT_RE = re.compile(r'^W[1-3]\Z')
# token phiên: chỉ ký tự an toàn (được ghi nguyên văn vào frontmatter draft —
# KHÔNG cho dấu cách/xuống dòng/':' làm hỏng YAML hay chèn khóa lạ)
SESSION_RE = re.compile(r'^[A-Za-z0-9._-]{1,64}\Z')
ID_RE = re.compile(r'^BLG-\d+\Z')
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


class OwnershipConflict(RegistryCorrupt):
    """Lease sống mơ hồ: không tự rollback registry để chọn một chủ.
    Là con của RegistryCorrupt để code cũ vẫn fail-closed, nhưng MỌI ranh
    giới công cụ phải bắt riêng và báo REGISTRY_CONFLICT (conflict_payload),
    không báo REGISTRY_CORRUPT + hướng dẫn khôi phục từ git."""

    def __init__(self, msg, problems=None):
        super().__init__(msg)
        self.problems = list(problems or [])


CONFLICT_HINT = ('KHONG rollback/khoi phuc registry tu git (se mat lease '
                 'song): cho lease het TTL hoac coordinator hoa giai co '
                 'bang chung (docs/RECOVERY.md)')


def conflict_payload(e):
    """Payload JSON THỐNG NHẤT cho REGISTRY_CONFLICT (CLI + writer-session)."""
    return {'code': 'REGISTRY_CONFLICT', 'error': str(e),
            'problems': list(getattr(e, 'problems', []) or []),
            'hint': CONFLICT_HINT}


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
    """Parse + kiểm cấu trúc; raise RegistryCorrupt (KHÔNG trả rỗng).

    HAI PHA, để phân loại không bao giờ rollback nhầm lease SỐNG đang tranh chấp:
      1. hình dạng TỐI THIỂU đủ để phát hiện tranh chấp chủ (lease là object,
         `ids` là list ID hợp lệ, `expires_at` đọc được, session của lease sống là
         chuỗi) rồi `require_live_ownership` -> OwnershipConflict (REGISTRY_CONFLICT:
         chờ TTL/coordinator, KHÔNG repair/rollback);
      2. lỗi cấu trúc SỬA ĐƯỢC (khóa slot lạ, vượt MAX_LEASE, kiểu trường, token
         session hỏng) -> RegistryCorrupt (`repair-registry --from-git`).
    Registry vừa tranh chấp vừa có lỗi pha 2 là REGISTRY_CONFLICT: repair khôi phục
    bản cũ sẽ âm thầm làm mất lease đang tranh chấp."""
    try:
        d = json.loads(text)
    except Exception as e:
        raise RegistryCorrupt('registry khong doc duoc (%s: %s)'
                              % (e.__class__.__name__, e))
    if not isinstance(d, dict) or not isinstance(d.get('leases'), dict):
        raise RegistryCorrupt('registry sai cau truc: thieu object "leases"')
    now = time.time()
    live_of = {}
    # ---- pha 1: hinh dang toi thieu de phat hien tranh chap chu ----
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
        live_of[w] = _epoch_of(exp or '') >= now
        sess = l.get('session')
        if live_of[w] and sess is not None and not isinstance(sess, str):
            raise RegistryCorrupt('lease %s: session khong phai chuoi (%r)'
                                  % (w, str(sess)[:40]))
    d.setdefault('schema_version', '1')
    require_live_ownership(d)
    # ---- pha 2: loi cau truc SUA DUOC (repair-registry --from-git) ----
    for w, l in d['leases'].items():
        live = live_of[w]
        # kieu cac truong con lai: sai kieu (sua tay) lam claim/heartbeat crash
        # (int()/float()/[:80]) va repair khong don duoc -> corrupt, co cau truc
        ep = l.get('epoch')
        if ep is not None and (isinstance(ep, bool)
                               or not isinstance(ep, int)):
            raise RegistryCorrupt('lease %s: epoch khong phai so nguyen (%r)'
                                  % (w, str(ep)[:20]))
        tt = l.get('ttl_hours')
        if tt is not None:
            try:
                tt_ok = (not isinstance(tt, bool)
                         and isinstance(tt, (int, float))
                         and math.isfinite(tt))
            except OverflowError:      # so nguyen JSON qua lon cho double
                tt_ok = False
            if not tt_ok:
                raise RegistryCorrupt('lease %s: ttl_hours khong phai so huu '
                                      'han (%r)' % (w, str(tt)[:20]))
        for key in ('label', 'claimed_at', 'heartbeat_at'):
            v = l.get(key)
            if v is not None and not isinstance(v, str):
                raise RegistryCorrupt('lease %s: %s khong phai chuoi' % (w, key))
        if live and not (isinstance(w, str) and SLOT_RE.match(w)):
            # khoa slot la khoa GAN NGUOI (typo W4 / w1 / 'W1 ' / 'W1\n'): nhan
            # lease SONG voi khoa la thi prune (vuot MAX_WRITERS: "nguoi den sau
            # thua") se bo lease SONG hop le claim moi nhat de giu lease "ma" ->
            # fail-closed. Lease HET HAN voi khoa la vo hai (bi prune truoc buoc
            # cat), nen duoc bo qua nhu moi lease het han khac.
            raise RegistryCorrupt('slot %r khong hop le (chi W1..W3)'
                                  % str(w)[:20])
        distinct = len(set(l.get('ids', [])))
        if live and distinct > MAX_LEASE:
            # lease SONG vuot MAX_LEASE ID KHAC NHAU: chu lease bi LEASE_FULL ke
            # ca count=0, prune khong cat -> corrupt (sua tu git history), khong
            # ket toi TTL. Dem ID PHAN BIET: ID lap trong lease la mot chu, prune
            # tu don (self_duplicates) nen khong bi coi la vuot tran.
            raise RegistryCorrupt('lease %s: %d ID (> %d)'
                                  % (w, distinct, MAX_LEASE))
        l.setdefault('ids', [])         # khong co khoa ids = lease rong (se bi prune)
        sess = l.get('session')
        if sess is not None and not valid_session(sess) and live:
            # token hong KHONG phai hai chu tranh nhau: la REGISTRY_CORRUPT
            # (de `repair-registry --from-git` con dung duoc). Lease het han
            # se bi prune nen bo qua.
            raise RegistryCorrupt('lease %s: session khong hop le (%r)'
                                  % (w, str(sess)[:40]))
    return d


def load_registry(path=None):
    """File vắng -> registry rỗng (single-writer legacy do selector quyết
    định); file HỎNG -> RegistryCorrupt (fail-closed)."""
    p = pathlib.Path(path) if path else REGISTRY
    if not p.is_file():
        return empty_registry()
    return parse_registry(_read_registry_text(p))


def _read_registry_text(p):
    """Doc registry; byte khong phai UTF-8 la REGISTRY_CORRUPT co cau truc
    (khong phai UnicodeDecodeError traceback)."""
    try:
        return pathlib.Path(p).read_text(encoding='utf-8')
    except UnicodeDecodeError as e:
        raise RegistryCorrupt('registry khong phai UTF-8 hop le (%s)' % e)


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
    phải fail-closed, KHÔNG được chọn đại một slot. Mỗi slot đếm MỘT lần cho
    mỗi ID: `ids: [A, A]` trong MỘT lease vẫn chỉ có một chủ (hỏng cấu trúc
    nhẹ do check_invariants báo và prune dọn), không phải tranh chấp."""
    now = now if now is not None else time.time()
    held = {}
    for w, l in reg['leases'].items():
        if not isinstance(l, dict) or _epoch_of(l.get('expires_at', '')) < now:
            continue
        for a in dict.fromkeys(l.get('ids', [])):
            held.setdefault(a, []).append(w)
    return {a: sorted(ws) for a, ws in held.items() if len(ws) > 1}


def live_ownership_problems(reg, now=None):
    """Không chọn chủ tùy ý khi registry có ID/session sống mơ hồ."""
    now = now if now is not None else time.time()
    problems = ['ID %s giu boi %s' % (a, ','.join(ws))
                for a, ws in sorted(live_conflicts(reg, now).items())]
    sessions = {}
    for w, lease in reg['leases'].items():
        # lease het han / RONG khong giu viec gi (se bi prune): khong tinh vao
        # "mot phien giu nhieu slot". Token session hong la REGISTRY_CORRUPT
        # (parse_registry), khong phai tranh chap chu.
        if _epoch_of(lease.get('expires_at', '')) < now or not lease.get('ids'):
            continue
        s = lease.get('session')
        if s:
            sessions.setdefault(s, []).append(w)
    problems.extend('session %s giu nhieu slot %s' % (s, ','.join(sorted(ws)))
                    for s, ws in sorted(sessions.items()) if len(ws) > 1)
    return problems


def require_live_ownership(reg, now=None):
    problems = live_ownership_problems(reg, now)
    if problems:
        raise OwnershipConflict('registry ownership khong nhat quan: ' +
                                '; '.join(problems), problems)


def _session_slot_error(reg, writer, session, now):
    others = sorted(w for w, l in reg['leases'].items()
                    if w != writer and l.get('session') == session
                    and l.get('ids')
                    and _epoch_of(l.get('expires_at', '')) >= now)
    if others:
        return _err('SESSION_HOLDS_OTHER_SLOT',
                    'phien %s dang giu %s — release truoc khi doi slot'
                    % (session, ','.join(others)), holder_slots=others)
    return None


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
              'duplicates': [], 'self_duplicates': {}, 'capped': [],
              'kept': {}}
    for w in [w for w, l in reg['leases'].items()
              if _epoch_of(l.get('expires_at', '')) < now]:
        del reg['leases'][w]
        report['expired'].append(w)
    status = {r['id']: r['status'] for r in rows}
    for w in list(reg['leases'].keys()):
        lease = reg['leases'][w]
        ids = list(lease.get('ids', []))
        keep = [a for a in ids if status.get(a) in LEASABLE]
        keep_set = set(keep)
        dropped = [a for a in ids if a not in keep_set]
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
        keep, in_keep = [], set()
        for a in lease.get('ids', []):
            if a in owner and owner[a] != w:
                report['duplicates'].append(
                    {'id': a, 'kept_by': owner[a], 'dropped_from': w})
            elif a in in_keep:
                # ID lặp TRONG CHÍNH lease này: vẫn một chủ, chỉ bỏ bản lặp
                # (giữ thứ tự lần xuất hiện đầu) — không đổi chủ, không đổi ID.
                report['self_duplicates'].setdefault(w, []).append(a)
            else:
                owner[a] = w
                keep.append(a)
                in_keep.add(a)
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
                or report['self_duplicates'] or report['capped'])


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
    problems = live_ownership_problems(reg, now)
    if problems:
        return _err('REGISTRY_CONFLICT', '; '.join(problems),
                    problems=problems, hint=CONFLICT_HINT)
    work = json.loads(json.dumps(reg))      # sao chép: lỗi thì KHÔNG đổi reg
    prev = work['leases'].get(writer)       # trước prune: biết epoch cũ
    report = prune_registry(work, rows, now)
    session_error = _session_slot_error(work, writer, session, now)
    if session_error:
        return session_error
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
    problems = live_ownership_problems(reg, now)
    if problems:
        return _err('REGISTRY_CONFLICT', '; '.join(problems),
                    problems=problems, hint=CONFLICT_HINT)
    work = json.loads(json.dumps(reg))
    prune_registry(work, rows, now)
    session_error = _session_slot_error(work, writer, session, now)
    if session_error:
        return session_error
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
    problems = live_ownership_problems(reg, now)
    if problems:
        return _err('REGISTRY_CONFLICT', '; '.join(problems),
                    problems=problems, hint=CONFLICT_HINT)
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
        if not mine.get('session'):
            # Release MỘT PHẦN lease legacy = phiên này nhận lease (như
            # heartbeat/claim): phải qua cùng guard "một phiên một slot", nếu
            # không phiên đã giữ slot khác sẽ giữ HAI slot sống và mọi lệnh sau
            # đó là REGISTRY_CONFLICT. (Trả hết lease không nhận ai nên không
            # cần guard: chỉ giảm phần đang giữ.)
            session_error = _session_slot_error(work, writer, session, now)
            if session_error:
                return session_error
            mine['session'] = session
        mine['ids'] = keep
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
                if a in seen and seen[a] != w:
                    # ID lặp trong CHÍNH một lease đã báo ở 'co ID lap' (một
                    # chủ); chỉ hai slot KHÁC nhau mới là "hai lease sống".
                    problems.append('ID %s bi giu boi hai lease song (%s, %s)'
                                    % (a, seen[a], w))
                seen[a] = w
            if status is not None and a not in status:
                problems.append('ID %s (slot %s) khong co trong matrix'
                                % (a, w))
    by_session = {}
    for w, l in leases.items():
        s = l.get('session')
        if s and l.get('ids') and _epoch_of(l.get('expires_at', '')) >= now:
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
    """Merge nguyên tử; không chuyển chủ lease local còn sống bằng timestamp.

    Cùng slot hai bên chỉ XUNG ĐỘT (OwnershipConflict) khi CẢ HAI cùng có
    session và hai session KHÁC nhau. Lease v1 (chưa session) đối diện bản
    đã được nhận (v2) là MỘT chủ ở hai thời điểm: giữ session đã nhận, KHÔNG
    hạ cấp v2 -> v1. Một phiên không được giữ hai slot sống."""
    now = time.time()
    for reg_in in (local, other):
        for w, lease in (reg_in.get('leases') or {}).items():
            if _epoch_of((lease or {}).get('expires_at', '')) >= now \
                    and not (isinstance(w, str) and SLOT_RE.match(w)):
                # slot la khoa gan nguoi: nhap "ma" W4 SONG se day lease SONG
                # hop le (claim moi nhat) ra khoi registry o buoc cat MAX_WRITERS
                raise RegistryCorrupt('slot %r khong hop le (chi W1..W3)'
                                      % str(w)[:20])
    require_live_ownership(local, now)
    require_live_ownership(other, now)
    work = json.loads(json.dumps(local))
    prune_registry(work, rows, now)
    incoming = json.loads(json.dumps(other))
    prune_registry(incoming, rows, now)
    for w, lease in incoming['leases'].items():
        mine = work['leases'].get(w) or {}
        mine_s = mine.get('session')
        s = lease.get('session')
        if mine_s and s and mine_s != s:
            msg = ('slot %s dang co lease song cua phien %s; ban remote '
                   'thuoc phien khac %s' % (w, mine_s, s))
            raise OwnershipConflict(msg, [msg])
        if mine and bool(mine_s) != bool(s) \
                and not (set(mine.get('ids', [])) & set(lease.get('ids', []))):
            # v1 <-> da nhan chi la MOT chu khi ban da nhan con GIU it nhat mot
            # ID cua lease v1 (nhan lease khong doi ID); khong chung ID thi la
            # hai working copy claim doc lap: mo ho chu => fail-closed.
            msg = ('slot %s: lease v1 va lease da nhan session khong chung ID '
                   'song nao — khong chung minh duoc cung chu' % w)
            raise OwnershipConflict(msg, [msg])
        if s and _session_slot_error(work, w, s, now):
            msg = 'session %s khong duoc giu hai slot' % s
            raise OwnershipConflict(msg, [msg])
    out = _merge_uncontested(work, incoming, rows)
    require_live_ownership(work, now)
    local.clear()
    local.update(work)
    return out


def _lease_stamp(lease):
    """Thứ tự "mới hơn" của hai bản CÙNG MỘT lease: heartbeat/claim, rồi hạn."""
    return (_epoch_of(lease.get('heartbeat_at') or lease.get('claimed_at')
                      or ''), _epoch_of(lease.get('expires_at') or ''))


def _merge_same_slot(mine, theirs, keep):
    """Hai bản của CÙNG lease (sessions không xung đột — đã kiểm). Bản ĐÃ NHẬN
    (có session) mới hơn bản v1 nên làm gốc; cùng loại thì bản có heartbeat/
    hạn mới hơn (hòa: local). ID: ID local trước (đã commit/CAS, không bị đá
    ra bởi ID incoming), rồi ID incoming mới, tối đa MAX_LEASE. Hạn = muộn
    hơn trong hai bản (cùng chủ); epoch = lớn hơn."""
    if bool(mine.get('session')) != bool(theirs.get('session')):
        base = theirs if theirs.get('session') else mine
    else:
        base = theirs if _lease_stamp(theirs) > _lease_stamp(mine) else mine
    lease = dict(base)
    ids = list(mine.get('ids', []))
    ids += [a for a in keep if a not in ids]
    lease['ids'] = sorted(ids[:MAX_LEASE])
    latest = max((mine, theirs),
                 key=lambda x: _epoch_of(x.get('expires_at') or ''))
    if latest.get('expires_at'):
        lease['expires_at'] = latest['expires_at']
    epochs = [e for e in (mine.get('epoch'), theirs.get('epoch'))
              if isinstance(e, int)]
    if epochs:
        lease['epoch'] = max(epochs)
    return lease


def _merge_uncontested(local, other, rows):
    """Gộp vào scratch registry đã kiểm ownership; ID local sống luôn giữ chủ."""
    prune_registry(local, rows)
    valid = set(r['id'] for r in rows if r['status'] in LEASABLE)
    conflicts, lost, invalid = [], [], []
    for w, l in (other.get('leases') or {}).items():
        if not isinstance(l, dict):
            continue
        if _epoch_of(l.get('expires_at', '')) < time.time():
            continue                          # lease hết hạn không vào local
        incoming = list(dict.fromkeys(l.get('ids', [])))   # ID lặp trong một lease: một chủ
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
            # Local đã được commit/CAS: claimed_at từ file ngoài không phải
            # quyền chuyển chủ ID đang sống. Writer phải fetch và claim lại.
            lost.append({'id': a, 'winner': ow, 'loser': w})
        if keep:
            mine = local['leases'].get(w)
            if mine:
                lease = _merge_same_slot(mine, l, keep)
            else:
                lease = dict(l)
                lease['ids'] = sorted(keep)[:MAX_LEASE]
            local['leases'][w] = lease
    prune_registry(local, rows)
    return {'merged': True, 'conflicts': conflicts,
            'rejected_not_planned': invalid, 'lost_to_other_writer': lost,
            'writers': {w: l['ids'] for w, l in local['leases'].items()}}


def cmd_merge(path):
    other = parse_registry(_read_registry_text(path))
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
    """Noi dung `path` o `ref`, hoac None neu khong doc duoc/khong phai UTF-8
    (mot ban lich su byte-hong chi la ung vien khong dung duoc: repair di tiep
    sang ban cu hon, khong crash)."""
    r = subprocess.run(['git', 'show', '%s:%s' % (ref, path)],
                       cwd=str(ROOT), capture_output=True)
    if r.returncode != 0:
        return None
    try:
        return r.stdout.decode('utf-8')
    except UnicodeDecodeError:
        return None


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
    except OwnershipConflict as e:
        print(json.dumps(conflict_payload(e), ensure_ascii=False))
        return 1
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
            except OwnershipConflict as e:
                # ban gan nhat con mo ho chu SONG: nhay qua no ve ban cu hon
                # se lang le mat cac lease dang tranh chap
                print(json.dumps(conflict_payload(e), ensure_ascii=False))
                return 1
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
    except OwnershipConflict as e:
        print(json.dumps(conflict_payload(e), ensure_ascii=False))
        return 1
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
