#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""writer-session.py — CLIENT CAS cho AI writer (provider-neutral, chỉ git).

MỘT lệnh cho mỗi bước của vòng đời writer; thay cho việc mỗi AI tự viết
git thủ công (nguồn của lost-update / ghi đè registry / push đè nhau).
Chỉ dùng git + Python stdlib: KHÔNG API ngoài, KHÔNG AI, KHÔNG secret.
Provider-neutral: slot W1/W2/W3 do BẤT KỲ AI nào giữ.

NGUYÊN TẮC CAS (compare-and-swap trên ref origin/main — không force push):
  mọi thay đổi dùng chung (registry lease, push draft) là một TRANSACTION:
    fetch origin/main -> đọc registry/matrix từ commit đó -> TÍNH lại
    claim/ownership trên truth mới nhất -> tạo commit (plumbing, index
    tạm, KHÔNG đụng working tree/branch của bạn) -> push commit đó lên
    main. Push bị từ chối (non-fast-forward / 409 / 422 / 5xx) = có người
    đẩy trước: LÀM LẠI TỪ fetch (không rebase commit cũ) với backoff có
    giới hạn. Hai writer không bao giờ ghi đè nhau và không bao giờ giữ
    cùng một ID.

LỆNH:
  begin   --slot W1|W2|W3|auto   nhận slot + lease (resume-first: giữ ID
          [--count N|--ids ..]   đang dở, bù cho đủ 10). In slot/session/
          [--label L] [--ttl-hours H] [--adopt] [--session S]
          [--allow-new-with-repair]
  status  [--slot W]             đọc: slot, ai giữ, hạn, ID của tôi,
                                 draft chưa push, việc tiếp theo
  sync                           ff-only working copy theo origin/main
                                 (để QA cục bộ thấy bài mới nhất)
  check   [--ids ..] [--no-qa]   gắn `writer:`/`writer_session:` vào draft
                                 của tôi, xác minh ownership, QA cục bộ
                                 (cùng scorer với publisher)
  push    [--ids ..] [--no-qa]   push CHỈ draft đã QA PASS của ID mình
                                 giữ (+ heartbeat) trong MỘT commit CAS
  confirm [--ids ..]             chờ factory publish: PUBLISHED / REPAIR /
          [--timeout S] [--poll S] [--nudge-after S]
  heartbeat | release [--ids ..|--all]

Thoát: 0 ok; 1 từ chối/lỗi; 2 dùng sai; 3 có REPAIR cần sửa; 4 còn chờ
(hết timeout, chưa publish); 5 mất lease (không push gì).

Biến môi trường: FACTORY_WRITER_SESSION (bàn giao slot giữa các AI),
FACTORY_SESSION_BACKOFF (hệ số thời gian chờ, test dùng 0).
"""
import argparse
import csv
import importlib.util
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_REL = 'data/state/writer-claims.json'
MATRIX_REL = 'data/content-matrix.csv'
QA_DIR = 'data/qa'
DRAFTS_DIR = '_drafts'
FRONT_ID_RE = re.compile(r'^article_id:\s*(BLG-\d+)', re.M)
MAX_PUSH_IDS = 10
CAS_ATTEMPTS = 8
NET_ATTEMPTS = 4
TRANSIENT_RE = re.compile(
    r'(rejected|non-fast-forward|fetch first|stale info|cannot lock ref|'
    r'reference update failed|\b409\b|\b422\b|\b50[0-4]\b|timed out|'
    r'timeout|connection (reset|refused)|could not resolve|rpc failed|'
    r'early eof|unexpected disconnect|remote end hung up|'
    r'temporarily unavailable|try again|hook declined)', re.I)
FATAL_RE = re.compile(r'(permission denied|authentication failed|'
                      r'protected branch|\b40[13]\b|\b404\b|'
                      r'repository not found|not allowed)', re.I)

E_OK, E_REFUSED, E_USAGE, E_REPAIR, E_PENDING, E_LEASE_LOST = 0, 1, 2, 3, 4, 5


class Refuse(Exception):
    def __init__(self, code, msg, **extra):
        super().__init__(msg)
        self.code, self.msg, self.extra = code, msg, extra


def _load_claim_module():
    spec = importlib.util.spec_from_file_location(
        'blog_writer_claim', os.path.join(HERE, 'writer-claim.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


WC = _load_claim_module()


def _scale():
    try:
        return float(os.environ.get('FACTORY_SESSION_BACKOFF', '1'))
    except ValueError:
        return 1.0


def _sleep(seconds):
    s = seconds * _scale()
    if s > 0:
        time.sleep(s)


# ------------------------------------------------------------------- git

class Git:
    def __init__(self, repo, remote='origin', branch='main'):
        self.repo = repo
        self.remote = remote
        self.branch = branch
        self.ref = '%s/%s' % (remote, branch)

    def run(self, args, check=True, input=None, env=None, text=True):
        e = dict(os.environ)
        if env:
            e.update(env)
        r = subprocess.run(['git'] + list(args), cwd=self.repo,
                           capture_output=True, input=input, env=e,
                           text=text)
        if check and r.returncode != 0:
            err = r.stderr if text else r.stderr.decode('utf-8', 'replace')
            raise RuntimeError('git %s -> rc=%d: %s'
                               % (' '.join(args), r.returncode, err.strip()))
        return r

    def fetch(self):
        last = ''
        for attempt in range(1, NET_ATTEMPTS + 1):
            r = self.run(['fetch', '-q', self.remote, self.branch],
                         check=False)
            if r.returncode == 0:
                return
            last = r.stderr.strip()
            if FATAL_RE.search(last):
                break
            _sleep(2 ** attempt)
        raise Refuse('FETCH_FAILED', 'git fetch that bai: %s' % last[-300:])

    def rev(self, ref):
        return self.run(['rev-parse', '--verify', '-q', ref]).stdout.strip()

    def show(self, rev, path):
        r = self.run(['show', '%s:%s' % (rev, path)], check=False,
                     text=False)
        return r.stdout if r.returncode == 0 else None

    def make_commit(self, base, changes, message, ident):
        """Commit bằng plumbing (index tạm): KHÔNG đụng working tree."""
        fd, idx = tempfile.mkstemp(prefix='ws-index-')
        os.close(fd)
        os.remove(idx)
        env = {'GIT_INDEX_FILE': idx}
        env.update(ident)
        try:
            self.run(['read-tree', base], env=env)
            for path, data in sorted(changes.items()):
                if data is None:
                    self.run(['update-index', '--force-remove', path],
                             env=env)
                    continue
                blob = self.run(['hash-object', '-w', '--stdin'],
                                input=data, env=env, text=False
                                ).stdout.decode().strip()
                self.run(['update-index', '--add', '--cacheinfo',
                          '100644,%s,%s' % (blob, path)], env=env)
            tree = self.run(['write-tree'], env=env).stdout.strip()
            return self.run(['commit-tree', tree, '-p', base, '-m', message],
                            env=env).stdout.strip()
        finally:
            try:
                os.remove(idx)
            except OSError:
                pass

    def push_commit(self, sha):
        """Push commit lên origin/main — KHÔNG force. Trả (ok, kind, err)
        với kind in {'ok','rejected','transient','fatal'}."""
        r = self.run(['push', '-q', self.remote,
                      '%s:refs/heads/%s' % (sha, self.branch)], check=False)
        if r.returncode == 0:
            return True, 'ok', ''
        err = (r.stderr + r.stdout).strip()
        if FATAL_RE.search(err) and not re.search(r'rejected', err, re.I):
            return False, 'fatal', err
        if re.search(r'(rejected|non-fast-forward|fetch first|stale info|'
                     r'cannot lock ref|reference update failed)', err, re.I):
            return False, 'rejected', err
        if TRANSIENT_RE.search(err):
            return False, 'transient', err
        return False, 'fatal', err

    def ident(self, slot):
        r = self.run(['var', 'GIT_AUTHOR_IDENT'], check=False)
        if r.returncode == 0:
            return {}
        name = os.environ.get('FACTORY_WRITER_GIT_NAME', 'writer-%s' % slot)
        mail = os.environ.get('FACTORY_WRITER_GIT_EMAIL',
                              'noreply@users.noreply.github.com')
        return {'GIT_AUTHOR_NAME': name, 'GIT_AUTHOR_EMAIL': mail,
                'GIT_COMMITTER_NAME': name, 'GIT_COMMITTER_EMAIL': mail}

    def cas(self, build, slot, max_attempts=CAS_ATTEMPTS):
        """Transaction CAS. build(base_sha, read) -> (changes, message,
        result). Làm lại từ fetch khi push bị từ chối; build có thể raise
        Refuse (dừng ngay, không push). Trả (result, commit|None)."""
        last = ''
        for attempt in range(1, max_attempts + 1):
            self.fetch()
            base = self.rev(self.ref)

            def read(path, _base=base):
                return self.show(_base, path)
            changes, message, result = build(base, read)
            if not changes:
                result['attempts'] = attempt
                return result, None
            commit = self.make_commit(base, changes, message,
                                      self.ident(slot))
            ok, kind, err = self.push_commit(commit)
            if ok:
                result['attempts'] = attempt
                result['commit'] = commit
                return result, commit
            last = err
            if kind == 'fatal':
                raise Refuse('PUSH_FATAL', 'push bi tu choi: %s' % err[-300:])
            # rejected = có người đẩy trước -> làm lại ngay (backoff ngắn);
            # transient (5xx/mạng) -> backoff dài hơn. KHÔNG force push.
            wait = (0.3 if kind == 'rejected' else 2.0) * (2 ** min(attempt - 1, 4))
            _sleep(wait + random.random() * 0.5)
        raise Refuse('CAS_EXHAUSTED', 'het %d lan thu CAS (push lien tuc bi '
                     'tu choi): %s' % (max_attempts, last[-200:]))


# -------------------------------------------------------- tiện ích dữ liệu

def parse_matrix(data):
    if data is None:
        raise Refuse('NO_MATRIX', 'khong doc duoc %s tren origin/main'
                     % MATRIX_REL)
    return list(csv.DictReader(io.StringIO(data.decode('utf-8'),
                                           newline='')))


def parse_registry_bytes(data):
    if data is None:
        return WC.empty_registry()
    try:
        return WC.parse_registry(data.decode('utf-8'))
    except WC.RegistryCorrupt as e:
        raise Refuse('REGISTRY_CORRUPT', '%s — chay: writer-claim.py '
                     'repair-registry --from-git' % e)


def local_drafts(repo):
    """{article_id: path_rel} của draft trong working copy."""
    out = {}
    d = os.path.join(repo, DRAFTS_DIR)
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.md'):
            continue
        try:
            with open(os.path.join(d, fn), encoding='utf-8') as f:
                head = f.read(2500)
        except OSError:
            continue
        m = FRONT_ID_RE.search(head)
        if m:
            out.setdefault(m.group(1), '%s/%s' % (DRAFTS_DIR, fn))
    return out


def set_identity(path_abs, slot, session):
    """Ghi `writer:` + `writer_session:` vào frontmatter (idempotent)."""
    with open(path_abs, encoding='utf-8') as f:
        s = f.read()
    m = re.match(r'(---\n)(.*?)(\n---\n)', s, re.S)
    if not m:
        raise Refuse('NO_FRONTMATTER', '%s thieu frontmatter'
                     % os.path.basename(path_abs))
    fm = m.group(2)

    def put(fm, key, val):
        line = '%s: %s' % (key, val)
        if re.search(r'^%s:\s*\S*.*$' % key, fm, re.M):
            return re.sub(r'^%s:.*$' % key, line, fm, flags=re.M)
        return fm + '\n' + line
    new = put(put(fm, 'writer', slot), 'writer_session', session)
    if new != fm:
        s = m.group(1) + new + s[m.end(2):]
        with open(path_abs, 'w', encoding='utf-8') as f:
            f.write(s)
        return True
    return False


def emit(code, payload):
    payload = dict(payload)
    payload['exit'] = code
    print('BLOG_WRITER_SESSION ' + json.dumps(payload, ensure_ascii=False))
    return code


def refuse_out(e):
    d = {'ok': False, 'code': e.code, 'error': e.msg}
    d.update(e.extra)
    print('LOI [%s]: %s' % (e.code, e.msg), file=sys.stderr)
    return emit(E_LEASE_LOST if e.code in ('LEASE_LOST', 'NOT_OWNER')
                else E_REFUSED, d)


# ------------------------------------------------------------------ lệnh

def pick_slot(reg, rows, want, now):
    """auto -> slot đang là của TÔI (session mặc định khớp), nếu không thì
    slot trống đầu tiên; slot hết hạn coi như trống."""
    work = json.loads(json.dumps(reg))
    WC.prune_registry(work, rows, now)
    if want != 'auto':
        return want
    for s in WC.SLOTS:
        lease = work['leases'].get(s)
        mine = WC.default_session(s, create=False)
        if lease and mine and lease.get('session') == mine:
            return s
    for s in WC.SLOTS:
        if s not in work['leases']:
            return s
    raise Refuse('NO_FREE_SLOT', 'ca %d slot deu dang duoc phien khac giu; '
                 'xem `writer-session.py status` de biet gio het han'
                 % WC.MAX_WRITERS,
                 slots={w: l.get('expires_at')
                        for w, l in work['leases'].items()})


def cmd_begin(g, a):
    session = a.session or None
    result_holder = {}

    def build(base, read):
        reg = parse_registry_bytes(read(REGISTRY_REL))
        rows = parse_matrix(read(MATRIX_REL))
        now = time.time()
        slot = pick_slot(reg, rows, a.slot, now)
        sess = session or WC.default_session(slot)
        status_of = {r['id']: r['status'] for r in rows}
        lease = reg['leases'].get(slot)
        mine_ids = list(lease['ids']) if lease and \
            lease.get('session') in (sess, None) and \
            WC._epoch_of(lease.get('expires_at', '')) >= now else []
        repair = [i for i in mine_ids if status_of.get(i) == 'REPAIR']
        count, ids = a.count, _split(a.ids)
        resumed_only = False
        if repair and not a.allow_new_with_repair and not ids:
            count = 0          # resume-first của CHÍNH writer này
            resumed_only = True
        if count == 0 and not ids:
            res = WC.apply_heartbeat(reg, rows, slot, sess, now=now,
                                     ttl_hours=a.ttl_hours)
            if not res['ok'] and res.get('code') == 'NO_LEASE':
                res = WC.apply_claim(reg, rows, slot, sess, count=0,
                                     now=now, ttl_hours=a.ttl_hours,
                                     label=a.label, adopt=a.adopt)
                if not res['ok']:
                    raise Refuse(res['code'], res['error'], **{
                        k: v for k, v in res.items()
                        if k not in ('ok', 'code', 'error')})
            elif not res['ok']:
                raise Refuse(res['code'], res['error'])
        else:
            res = WC.apply_claim(reg, rows, slot, sess, count=count, ids=ids,
                                 now=now, ttl_hours=a.ttl_hours,
                                 label=a.label, adopt=a.adopt)
            if not res['ok']:
                raise Refuse(res['code'], res['error'], **{
                    k: v for k, v in res.items()
                    if k not in ('ok', 'code', 'error')})
        res['slot'] = slot
        res['session'] = sess
        res['repair_first'] = [i for i in res.get('leased_total', [])
                               if status_of.get(i) == 'REPAIR']
        res['resume_only_repair_first'] = resumed_only
        res['planned_left'] = sum(1 for r in rows if r['status'] == 'PLANNED')
        res['rows'] = {i: status_of.get(i) for i in res.get('leased_total',
                                                            [])}
        res['titles'] = {r['id']: r['title'][:100] for r in rows
                         if r['id'] in set(res.get('leased_total', []))}
        text = WC.dump_registry(reg)
        old = read(REGISTRY_REL)
        changes = {} if old is not None and _same_registry(old, text) \
            else {REGISTRY_REL: text.encode('utf-8')}
        first = res.get('claimed') or res.get('leased_total') or ['-']
        msg = ('writer-claim(%s): lease %s\n\nWriter-Session: %s'
               % (slot, ','.join(first[:1] + first[-1:]), sess))
        result_holder.update(slot=slot)
        return changes, msg, res

    res, commit = g.cas(build, a.slot if a.slot != 'auto' else 'W?')
    res.pop('ok', None)
    sync = try_sync(g)
    res['sync'] = sync
    print('SLOT %s | session %s | epoch %s | han %s | ID: %s'
          % (res['slot'], res['session'], res.get('epoch'),
             res.get('expires_at'), ','.join(res.get('leased_total', []))),
          file=sys.stderr)
    return emit(E_OK, dict(res, ok=True))


def _same_registry(old_bytes, new_text):
    """So sánh bỏ qua updated_at (không tạo commit rỗng chỉ vì thời gian)."""
    try:
        a = json.loads(old_bytes.decode('utf-8'))
        b = json.loads(new_text)
        a.pop('updated_at', None)
        b.pop('updated_at', None)
        return a == b
    except Exception:
        return False


def _split(v):
    return [x.strip() for x in v.split(',') if x.strip()] if v else None


def try_sync(g):
    """ff-only working copy theo origin/main khi an toàn; không bao giờ
    mất việc: file untracked trùng nội dung với bản đã push thì thay bằng
    bản tracked."""
    try:
        cur = g.run(['rev-parse', '--abbrev-ref', 'HEAD']).stdout.strip()
        if cur != g.branch:
            return {'synced': False, 'reason': 'khong o nhanh %s' % g.branch}
        dirty = g.run(['status', '--porcelain', '--untracked-files=no']
                      ).stdout.strip()
        if dirty:
            return {'synced': False, 'reason': 'co thay doi tracked cuc bo'}
        for attempt in range(2):
            r = g.run(['merge', '--ff-only', '-q', g.ref], check=False)
            if r.returncode == 0:
                return {'synced': True, 'head': g.rev('HEAD')[:10]}
            err = r.stderr
            paths = re.findall(r'^\s+(\S.*)$', err, re.M)
            moved = []
            for p in paths:
                p = p.strip()
                if not p.startswith(DRAFTS_DIR + '/'):
                    continue
                up = g.show(g.ref, p)
                loc = os.path.join(g.repo, p)
                try:
                    cur_bytes = open(loc, 'rb').read()
                except OSError:
                    continue
                if up is not None and up == cur_bytes:
                    os.remove(loc)      # trùng bản đã push: tracked sẽ khôi phục
                    moved.append(p)
            if not moved:
                return {'synced': False,
                        'reason': 'ff-only that bai: %s' % err.strip()[-200:]}
        return {'synced': False, 'reason': 'ff-only that bai'}
    except Exception as e:      # sync không bao giờ làm hỏng lệnh chính
        return {'synced': False, 'reason': str(e)[:200]}


def cmd_sync(g, a):
    g.fetch()
    return emit(E_OK, {'ok': True, 'sync': try_sync(g)})


def my_slot_and_session(g, a, reg, rows):
    """Slot/session hiện tại của tôi: --slot hoặc suy ra từ session mặc định."""
    now = time.time()
    work = json.loads(json.dumps(reg))
    WC.prune_registry(work, rows, now)
    slots = [a.slot] if getattr(a, 'slot', None) and a.slot != 'auto' \
        else list(WC.SLOTS)
    sess_arg = getattr(a, 'session', None)
    for s in slots:
        sess = sess_arg or WC.default_session(s, create=False)
        lease = work['leases'].get(s)
        if lease and sess and lease.get('session') == sess:
            return s, sess, lease
    return None, None, None


def cmd_status(g, a):
    g.fetch()
    base = g.rev(g.ref)
    reg = parse_registry_bytes(g.show(base, REGISTRY_REL))
    rows = parse_matrix(g.show(base, MATRIX_REL))
    now = time.time()
    status_of = {r['id']: r['status'] for r in rows}
    work = json.loads(json.dumps(reg))
    WC.prune_registry(work, rows, now)
    slot, sess, lease = my_slot_and_session(g, a, reg, rows)
    slots = {w: WC._slot_view(w, l, status_of, now)
             for w, l in work['leases'].items()}
    out = {'ok': True, 'head': base[:10], 'slots': slots,
           'free_slots': [s for s in WC.SLOTS if s not in work['leases']],
           'planned_left': sum(1 for r in rows if r['status'] == 'PLANNED'),
           'me': None}
    if slot:
        ids = list(lease['ids'])
        drafts = local_drafts(g.repo)
        up = {i: (g.show(base, p) is not None) for i, p in drafts.items()
              if i in set(ids)}
        out['me'] = {'slot': slot, 'session': sess, 'ids': ids,
                     'rows': {i: status_of.get(i) for i in ids},
                     'expires_at': lease.get('expires_at'),
                     'remaining_s': slots[slot]['remaining_s'],
                     'local_drafts': sorted(i for i in ids if i in drafts),
                     'drafts_already_on_origin': sorted(
                         i for i, v in up.items() if v)}
        repair = [i for i in ids if status_of.get(i) == 'REPAIR']
        todo = [i for i in ids if status_of.get(i) == 'PLANNED'
                and i not in drafts]
        if repair:
            out['next_action'] = 'sua REPAIR roi push: %s' % ','.join(repair)
        elif todo:
            out['next_action'] = 'viet draft cho: %s' % ','.join(todo)
        else:
            out['next_action'] = 'begin de nhan batch ke tiep'
    else:
        out['next_action'] = ('begin --slot auto de nhan slot'
                              if out['free_slots'] else
                              'ca 3 slot dang bi giu — cho het han hoac '
                              'dung slot cua minh voi --session')
    return emit(E_OK, out)


def _resolve_ids(g, a, slot, lease):
    ids = _split(getattr(a, 'ids', None))
    if ids:
        extra = [i for i in ids if i not in set(lease['ids'])]
        if extra:
            raise Refuse('NOT_MY_IDS', 'ID khong thuoc lease cua %s: %s'
                         % (slot, ','.join(extra)))
        return ids
    drafts = local_drafts(g.repo)
    return [i for i in lease['ids'] if i in drafts]


def run_local_qa(g, ids):
    r = subprocess.run([sys.executable,
                        os.path.join(HERE, 'writer-loop.py'), 'qa',
                        '--ids', ','.join(ids)],
                       cwd=g.repo, capture_output=True, text=True)
    res = {}
    for line in (r.stdout + r.stderr).splitlines():
        m = re.match(r'^(BLG-\d+)\s+result=(\w+)(.*)$', line)
        if m:
            res[m.group(1)] = (m.group(2), line.strip())
    return res


def cmd_check(g, a, then_push=False):
    g.fetch()
    sync = try_sync(g)      # QA cục bộ phải thấy bài/matrix mới nhất
    base = g.rev(g.ref)
    reg = parse_registry_bytes(g.show(base, REGISTRY_REL))
    rows = parse_matrix(g.show(base, MATRIX_REL))
    slot, sess, lease = my_slot_and_session(g, a, reg, rows)
    if not slot:
        raise Refuse('LEASE_LOST', 'khong con slot song cho phien nay — '
                     'chay begin')
    ids = _resolve_ids(g, a, slot, lease)
    drafts = local_drafts(g.repo)
    missing = [i for i in ids if i not in drafts]
    have = [i for i in ids if i in drafts]
    status_of = {r['id']: r['status'] for r in rows}
    skipped = {i: status_of.get(i) for i in have
               if status_of.get(i) not in ('PLANNED', 'WRITING', 'QA', 'PASS',
                                            'REPAIR')}
    have = [i for i in have if i not in skipped]
    fixed = []
    for i in have:
        if set_identity(os.path.join(g.repo, drafts[i]), slot, sess):
            fixed.append(i)
    qa = {}
    if have and not getattr(a, 'no_qa', False):
        qa = run_local_qa(g, have)
    passed = [i for i in have if getattr(a, 'no_qa', False)
              or qa.get(i, ('', ''))[0] == 'PASS']
    failed = {i: qa.get(i, ('NOQA', ''))[1][:240] for i in have
              if i not in passed}
    out = {'ok': True, 'slot': slot, 'session': sess, 'ids': ids,
           'sync': sync,
           'with_draft': have, 'missing_drafts': missing,
           'skipped_not_pushable': skipped, 'identity_fixed': fixed,
           'qa_pass': passed, 'qa_failed': failed}
    if then_push:
        return out, passed, drafts
    return emit(E_OK, out)


def cmd_push(g, a):
    out, passed, drafts = cmd_check(g, a, then_push=True)
    slot, sess = out['slot'], out['session']
    if not passed:
        return emit(E_REFUSED, dict(out, ok=False, code='NOTHING_TO_PUSH',
                                    error='khong co draft nao QA PASS de push'))
    if len(passed) > MAX_PUSH_IDS:
        return emit(E_REFUSED, dict(out, ok=False, code='TOO_MANY',
                                    error='toi da %d ID moi push'
                                    % MAX_PUSH_IDS))
    blobs = {}
    for i in passed:
        with open(os.path.join(g.repo, drafts[i]), 'rb') as f:
            blobs[drafts[i]] = f.read()

    def build(base, read):
        reg = parse_registry_bytes(read(REGISTRY_REL))
        rows = parse_matrix(read(MATRIX_REL))
        status_of = {r['id']: r['status'] for r in rows}
        now = time.time()
        res = WC.apply_heartbeat(reg, rows, slot, sess, now=now,
                                 ttl_hours=a.ttl_hours)
        if not res['ok']:
            raise Refuse('LEASE_LOST', '%s — khong push gi (draft van con '
                         'o working copy)' % res['error'])
        leased = set(res['leased_total'])
        bad = [i for i in passed if i not in leased]
        if bad:
            raise Refuse('LEASE_LOST', 'mat lease tren ID: %s — khong push '
                         'gi' % ','.join(bad))
        for i in passed:
            st = status_of.get(i)
            if st not in ('PLANNED', 'WRITING', 'QA', 'PASS', 'REPAIR'):
                raise Refuse('ALREADY_DONE', '%s da o trang thai %s — khong '
                             'push lai' % (i, st))
        changes = dict(blobs)
        for path in blobs:
            cur = read(path)
            if cur is not None and cur == blobs[path]:
                changes.pop(path)           # đã có đúng nội dung: idempotent
        if not changes:
            res['already_pushed'] = True
            return {}, '', dict(res, pushed=[], ids=passed)
        changes[REGISTRY_REL] = WC.dump_registry(reg).encode('utf-8')
        msg = ('draft(%s..%s): push batch %d draft cho factory publish '
               '(writer %s)\n\nWriter-Session: %s'
               % (passed[0], passed[-1], len(passed), slot, sess))
        return changes, msg, dict(res, pushed=passed,
                                  files=sorted(blobs))
    try:
        res, commit = g.cas(build, slot)
    except Refuse as e:
        return emit(E_LEASE_LOST if e.code == 'LEASE_LOST' else E_REFUSED,
                    dict(out, ok=False, code=e.code, error=e.msg))
    res.pop('ok', None)
    res['sync'] = try_sync(g)
    payload = dict(out, **{k: v for k, v in res.items()
                           if k in ('commit', 'attempts', 'pushed',
                                    'already_pushed', 'expires_at', 'sync')})
    payload['ok'] = True
    print('PUSH OK: %d draft (%s) commit %s' % (
        len(passed), ','.join(passed), (commit or '-')[:10]),
        file=sys.stderr)
    return emit(E_OK, payload)


def read_qa_failures(g, base, i):
    data = g.show(base, '%s/%s.json' % (QA_DIR, i))
    if not data:
        return {}
    try:
        ev = json.loads(data.decode('utf-8'))
    except ValueError:
        return {}
    failed = sorted(k for k, v in (ev.get('checks') or {}).items() if not v)
    d = {'failed_checks': failed, 'quality': ev.get('quality'),
         'seo': ev.get('seo'), 'business_fact': ev.get('business_fact'),
         'legal': ev.get('legal')}
    for k in ('bad_routes', 'non_approved_amounts', 'forbidden_hits',
              'cannibalization_clash', 'duplicate_title_clash',
              'duplicate_slug_clash', 'intent_unique_clash'):
        if ev.get(k):
            d[k] = ev[k]
    return d


def cmd_confirm(g, a):
    g.fetch()
    base = g.rev(g.ref)
    reg = parse_registry_bytes(g.show(base, REGISTRY_REL))
    rows = parse_matrix(g.show(base, MATRIX_REL))
    slot, sess, lease = my_slot_and_session(g, a, reg, rows)
    ids = _split(a.ids) or (list(lease['ids']) if lease else [])
    if not ids:
        raise Refuse('NO_IDS', 'khong co ID de xac nhan (truyen --ids)')
    t0 = time.time()
    nudged = 0
    last_nudge = t0
    last = {}
    while True:
        g.fetch()
        base = g.rev(g.ref)
        rows = parse_matrix(g.show(base, MATRIX_REL))
        st = {r['id']: r['status'] for r in rows}
        last = {i: st.get(i, '?') for i in ids}
        published = [i for i in ids if last[i] == 'PUBLISHED']
        repair = [i for i in ids if last[i] == 'REPAIR']
        waiting = [i for i in ids if last[i] in ('PLANNED', 'WRITING', 'QA',
                                                'PASS')]
        if len(published) == len(ids):
            return emit(E_OK, {'ok': True, 'published': published,
                               'waited_s': int(time.time() - t0),
                               'planned_left': sum(
                                   1 for r in rows
                                   if r['status'] == 'PLANNED')})
        if repair and not waiting:
            return emit(E_REPAIR, {
                'ok': False, 'code': 'REPAIR', 'published': published,
                'repair': {i: read_qa_failures(g, base, i) for i in repair},
                'hint': 'sua draft theo failed_checks roi push lai (cung '
                        'ID); KHONG ha nguong QA'})
        elapsed = time.time() - t0
        if elapsed >= a.timeout:
            return emit(E_PENDING, {
                'ok': False, 'code': 'PENDING', 'status': last,
                'waited_s': int(elapsed), 'nudged': nudged,
                'hint': 'chua publish: factory dang xep hang. Chay lai '
                        'confirm sau; neu qua lau co the nudge: '
                        'writer-session.py confirm --nudge-after 0'})
        if waiting and elapsed >= a.nudge_after and nudged < a.max_nudges \
                and time.time() - last_nudge >= a.nudge_after:
            if slot and nudge(g, slot):
                nudged += 1
                last_nudge = time.time()
        _sleep_real(min(a.poll, max(a.timeout - elapsed, 0)))


def _sleep_real(seconds):
    if seconds > 0:
        time.sleep(seconds)


def nudge(g, slot):
    """Kích lại publisher khi run trước bị GitHub hủy (concurrency chỉ giữ
    1 run chờ): ghi _drafts/.nudge-<slot> (không phải .md -> selector bỏ
    qua; chỉ để push đổi _drafts/** khởi chạy lại workflow, nó drain backlog
    trong repo). Idempotent, tối đa vài lần."""
    path = '%s/.nudge-%s' % (DRAFTS_DIR, slot)

    def build(base, read):
        data = ('%s\n' % WC._now()).encode('utf-8')
        return {path: data}, 'draft-nudge(%s): kich lai factory publish' % slot, {}
    try:
        g.cas(build, slot, max_attempts=3)
        return True
    except Refuse:
        return False


def cmd_heartbeat(g, a):
    sess_holder = {}

    def build(base, read):
        reg = parse_registry_bytes(read(REGISTRY_REL))
        rows = parse_matrix(read(MATRIX_REL))
        slot, sess, lease = my_slot_and_session(g, a, reg, rows)
        if not slot:
            raise Refuse('LEASE_LOST', 'khong con slot song cho phien nay')
        res = WC.apply_heartbeat(reg, rows, slot, sess, ttl_hours=a.ttl_hours)
        if not res['ok']:
            raise Refuse('LEASE_LOST', res['error'])
        return ({REGISTRY_REL: WC.dump_registry(reg).encode('utf-8')},
                'writer-claim(%s): heartbeat\n\nWriter-Session: %s'
                % (slot, sess), res)
    res, _ = g.cas(build, getattr(a, 'slot', None) or 'W?')
    res.pop('ok', None)
    return emit(E_OK, dict(res, ok=True))


def cmd_release(g, a):
    ids = _split(a.ids)

    def build(base, read):
        reg = parse_registry_bytes(read(REGISTRY_REL))
        rows = parse_matrix(read(MATRIX_REL))
        slot, sess, lease = my_slot_and_session(g, a, reg, rows)
        if not slot:
            return {}, '', {'released': [], 'ended': False,
                            'note': 'khong co lease song de release'}
        res = WC.apply_release(reg, rows, slot, sess, ids=ids or [],
                               end=a.all)
        if not res['ok']:
            raise Refuse(res['code'], res['error'])
        return ({REGISTRY_REL: WC.dump_registry(reg).encode('utf-8')},
                'writer-claim(%s): release%s\n\nWriter-Session: %s'
                % (slot, ' (end)' if a.all else '', sess), res)
    res, _ = g.cas(build, getattr(a, 'slot', None) or 'W?')
    res.pop('ok', None)
    return emit(E_OK, dict(res, ok=True))


# -------------------------------------------------------------------- main

def toplevel(repo):
    if repo:
        return os.path.abspath(repo)
    r = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print('LOI: khong o trong git repo (dung --repo)', file=sys.stderr)
        sys.exit(E_USAGE)
    return r.stdout.strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description='CAS client cho AI writer')
    ap.add_argument('--repo', default=None)
    ap.add_argument('--remote', default='origin')
    ap.add_argument('--branch', default='main')
    sub = ap.add_subparsers(dest='cmd', required=True)

    def ids_opt(p):
        p.add_argument('--ids', default=None)
        p.add_argument('--slot', default=None)
        p.add_argument('--session', default=None)
        p.add_argument('--ttl-hours', type=float, default=None)

    b = sub.add_parser('begin')
    b.add_argument('--slot', default='auto')
    b.add_argument('--count', type=int, default=None)
    b.add_argument('--ids', default=None)
    b.add_argument('--label', default=None)
    b.add_argument('--ttl-hours', type=float, default=12.0)
    b.add_argument('--adopt', action='store_true')
    b.add_argument('--allow-new-with-repair', action='store_true')
    b.add_argument('--session', default=None)
    s = sub.add_parser('status')
    s.add_argument('--slot', default=None)
    s.add_argument('--session', default=None)
    sub.add_parser('sync')
    c = sub.add_parser('check')
    ids_opt(c)
    c.add_argument('--no-qa', action='store_true')
    p = sub.add_parser('push')
    ids_opt(p)
    p.add_argument('--no-qa', action='store_true')
    cf = sub.add_parser('confirm')
    ids_opt(cf)
    cf.add_argument('--timeout', type=float, default=900)
    cf.add_argument('--poll', type=float, default=20)
    cf.add_argument('--nudge-after', type=float, default=360)
    cf.add_argument('--max-nudges', type=int, default=3)
    h = sub.add_parser('heartbeat')
    ids_opt(h)
    r = sub.add_parser('release')
    ids_opt(r)
    r.add_argument('--all', action='store_true')
    a = ap.parse_args(argv)
    repo = toplevel(a.repo)
    g = Git(repo, a.remote, a.branch)
    try:
        fn = {'begin': cmd_begin, 'status': cmd_status, 'sync': cmd_sync,
              'check': cmd_check, 'push': cmd_push, 'confirm': cmd_confirm,
              'heartbeat': cmd_heartbeat, 'release': cmd_release}[a.cmd]
        return fn(g, a)
    except Refuse as e:
        return refuse_out(e)


if __name__ == '__main__':
    sys.exit(main())
