#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gỡ trang chuyển hướng (stub meta refresh) của URL cũ đã di trú slug đ -> d (Issue #77) CÓ KIỂM SOÁT, theo lô, có hoàn tác.

Quyết định chủ repo 2026-10-27 (sau khi di trú xong): không cần giữ chuyển hướng lịch sử. URL cũ được GỠ (trả 404 — đúng kỳ vọng),
bài vẫn ở URL mới. Registry giữ nguyên ánh xạ cũ -> mới, chỉ đổi status MIGRATED -> RETIRED, để gate chặn mọi liên kết mới vào URL đã gỡ.
Công cụ KHÔNG đụng bài viết, evidence QA, matrix hay sitemap: chỉ xóa `redirects/slug-d/<ID>.html` và đổi status dòng registry.

Một mục chỉ được gỡ khi thỏa MỌI điều kiện (tool tự kiểm từ byte hiện tại, không có cờ ép):
  1. Nguồn di trú sạch (`slug_redirects.source_errors` rỗng): registry <-> matrix <-> bài <-> evidence <-> trang chuyển hướng khớp.
  2. Dòng registry status MIGRATED; trang chuyển hướng tồn tại và KHỚP BYTE `stub_source()` (sinh bằng công cụ, không sửa tay).
  3. Bài ở URL mới tồn tại, permalink == new_url (đã có ở 1).
  4. KHÔNG còn liên kết nào trong nguồn site VÀ trong _drafts/ trỏ URL cũ (mọi dạng, có/không '/' cuối): gỡ khi còn liên kết
     = tạo 404 nội bộ (draft đang xếp hàng sẽ thành bài).
     Mục còn liên kết bị từ chối (BLOCKED_STILL_LINKED) — trỏ thẳng URL mới bằng `migrate-slug-urls.py links-apply` trước.
  5. `--approval-ref` (chủ duyệt) và `--live-ref` (lần audit live factory-liveness stub_check xác nhận URL mới HTTP 200, canonical tự
     trỏ, có trong sitemap) bắt buộc, ghi vào sao lưu. Môi trường agent không gọi được production nên bằng chứng live đến từ workflow.

Lệnh:
  plan     [--ids A,B] [--out FILE]                                        đề xuất (không ghi gì)
  apply    --approval-ref TEXT --live-ref TEXT (--ids A,B | --all-eligible) [--batch-id ID] [--dry-run]
  verify   --backup FILE                                                   kiểm trạng thái đã ghi so với sao lưu
  rollback --backup FILE [--dry-run]                                       khôi phục byte-exact (chỉ khi còn đúng bản đã ghi)

Sao lưu `reports/qa-audit/retire/<batch>.json` (dòng registry cũ + nguyên văn trang chuyển hướng) được ghi và đọc lại TRƯỚC khi sửa gì;
apply lỗi giữa chừng tự trả mọi thứ về byte cũ. Lô <= 700 ID (không đổi nội dung bài nên không chấm lại; mỗi lô một commit/PR).
Sau apply: hạ ratchet bằng `check-slug-redirects.py --from-source --write-ratchet`.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.append(str(HERE))
import slug_redirects as SR  # noqa: E402

BACKUP_SCHEMA = 'retire-backup/1'
BACKUP_DIR = 'reports/qa-audit/retire'
ELIGIBLE = 'ELIGIBLE_PROPOSAL_AWAITING_OWNER_APPROVAL'
MAX_BATCH = 700
AID_RE = re.compile(r'^BLG-\d{5,}\Z')
BATCH_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,80}\Z')


class Refuse(Exception):
    def __init__(self, code, msg, **extra):
        super().__init__(msg)
        self.code, self.msg, self.extra = code, msg, extra


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')


def doc_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def atomic_write(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.retire.tmp')
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise


def git_out(root, *args):
    r = subprocess.run(['git'] + list(args), cwd=str(root), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def require_clean_tree(root):
    dirty = git_out(root, 'status', '--porcelain', '--untracked-files=no')
    if dirty is None:
        raise Refuse('NOT_A_REPO', 'khong doc duoc git status')
    if dirty:
        raise Refuse('DIRTY_TREE', 'cay lam viec khac HEAD; commit/hoan tac truoc', dirty=dirty.splitlines()[:20])


def front_permalink(path):
    with open(path, encoding='utf-8') as f:
        head = f.read(3000)
    m = re.search(r'^permalink:\s*(\S+)\s*$', head, re.M)
    return m.group(1) if m else None


def decide(root, rows, linked):
    """{aid: (quyết định, lý do)} cho các dòng registry được hỏi; `linked` = {old_url: [tệp nguồn]} đã quét sẵn."""
    out = {}
    for r in rows:
        aid = r['article_id']
        if r.get('status') != SR.MIGRATED:
            out[aid] = ('NOT_MIGRATED', 'status %r (chi go dong MIGRATED)' % r.get('status'))
            continue
        stub = root / SR.stub_relpath(aid)
        if not stub.is_file() or stub.read_text(encoding='utf-8') != SR.stub_source(r):
            out[aid] = ('STUB_MISMATCH', 'trang chuyen huong thieu/khac stub_source()')
            continue
        post = root / r['new_output_path']
        if not post.is_file() or front_permalink(post) != r['new_url']:
            out[aid] = ('NEW_POST_MISSING', 'bai o URL moi thieu hoac permalink khac new_url')
            continue
        srcs = linked.get(r['old_url'])
        if srcs:
            out[aid] = ('BLOCKED_STILL_LINKED', 'con lien ket toi URL cu tu: %s' % ', '.join(srcs[:5]))
            continue
        out[aid] = (ELIGIBLE, '')
    return out


def linked_sources(root, old_urls):
    """{old_url: [tệp nguồn còn liên kết]} — quét MỘT lần cho cả lô (mỗi URL một lượt là quá chậm với ~1.400 URL)."""
    hits = {}
    for u in old_urls:
        hits[u] = []
    if not old_urls:
        return hits
    forms = {}
    for u in old_urls:
        forms[u] = u
        forms[u.rstrip('/')] = u
    pat = re.compile('|'.join(re.escape(f) for f in sorted(forms, key=len, reverse=True)))
    for rel in sorted(SR.source_link_hits(old_urls, str(root), include_drafts=True)):
        with open(root / rel, encoding='utf-8', errors='replace') as f:
            text = f.read()
        for m in pat.finditer(text):
            if m.group(0).endswith('/') or not re.match(r'[\w\-/]', text[m.end():m.end() + 1]):
                src = hits[forms[m.group(0)]]
                if rel not in src:
                    src.append(rel)
    return hits


def select_rows(root, ids):
    reg = SR.load_registry(str(root))
    by_id = {r['article_id']: r for r in reg}
    if ids is None:
        return [r for r in reg if r.get('status') == SR.MIGRATED]
    unknown = sorted(set(ids) - set(by_id))
    if unknown:
        raise Refuse('UNKNOWN_IDS', 'ID khong co trong registry: %s' % unknown[:5])
    return [by_id[a] for a in sorted(set(ids))]


def make_plan(root, ids=None):
    root = pathlib.Path(root)
    errs = SR.source_errors(str(root))
    rows = select_rows(root, ids)
    dec = decide(root, rows, linked_sources(root, [r['old_url'] for r in rows]))
    counts = {}
    for d, _ in dec.values():
        counts[d] = counts.get(d, 0) + 1
    return {'schema': 'retire-plan/1', 'authority': 'PROPOSAL ONLY — apply kiem lai moi dieu kien tu byte hien tai',
            'head': git_out(root, 'rev-parse', 'HEAD'), 'source_errors': errs[:50], 'source_error_count': len(errs),
            'counts': dict(sorted(counts.items())),
            'eligible': sorted(a for a, (d, _) in dec.items() if d == ELIGIBLE),
            'excluded': {a: {'decision': d, 'reason': why} for a, (d, why) in sorted(dec.items()) if d != ELIGIBLE}}


def apply_batch(root, ids, approval_ref, live_ref, batch_id=None, dry_run=False):
    root = pathlib.Path(root)
    if len((approval_ref or '').strip()) < 10:
        raise Refuse('NO_APPROVAL', '--approval-ref (chu duyet) bat buoc')
    if len((live_ref or '').strip()) < 10:
        raise Refuse('NO_LIVE_EVIDENCE', '--live-ref (audit live xac nhan URL moi HTTP 200) bat buoc')
    batch_id = batch_id or 'retire-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
    if not BATCH_RE.match(batch_id):
        raise Refuse('BAD_BATCH_ID', 'batch-id sai dang: %r' % batch_id)
    errs = SR.source_errors(str(root))
    if errs:
        raise Refuse('SOURCE_NOT_CLEAN', 'nguon di tru chua sach (%d loi) — sua truoc khi go' % len(errs), errors=errs[:10])
    rows = select_rows(root, ids)
    if not rows:
        raise Refuse('NO_IDS', 'khong co dong nao de go')
    if len(rows) > MAX_BATCH:
        raise Refuse('BATCH_TOO_LARGE', 'lo %d > %d ID' % (len(rows), MAX_BATCH))
    dec = decide(root, rows, linked_sources(root, [r['old_url'] for r in rows]))
    bad = {a: d for a, d in dec.items() if d[0] != ELIGIBLE}
    if bad:
        raise Refuse('NOT_ELIGIBLE', '%d ID khong du dieu kien (chua ghi gi)' % len(bad),
                     ineligible={a: '%s: %s' % d for a, d in sorted(bad.items())[:20]})
    reg_path = root / SR.REGISTRY_REL
    reg_old = reg_path.read_bytes()
    entries = {}
    for r in rows:
        rel = SR.stub_relpath(r['article_id'])
        text = (root / rel).read_text(encoding='utf-8')
        entries[r['article_id']] = {'registry_row': dict(r), 'stub_path': rel, 'stub_text': text,
                                    'stub_sha256': sha(text.encode('utf-8'))}
    want = {a for a in entries}
    new_rows = []
    for r in SR.load_registry(str(root)):
        r = dict(r)
        if r['article_id'] in want:
            r['status'] = SR.RETIRED
        new_rows.append(r)
    reg_new = SR.registry_text(new_rows).encode('utf-8')
    backup = {'schema': BACKUP_SCHEMA, 'batch_id': batch_id, 'created_at': now_iso(),
              'head_at_apply': git_out(root, 'rev-parse', 'HEAD'), 'tool_sha256': sha(pathlib.Path(__file__).read_bytes()),
              'approval_ref': approval_ref.strip(), 'live_ref': live_ref.strip(),
              'purpose': 'Go trang chuyen huong URL cu da di tru (quyet dinh chu 2026-10-27): URL cu tra 404, bai giu nguyen o URL moi',
              'registry_old_sha256': sha(reg_old), 'registry_new_sha256': sha(reg_new), 'entries': entries}
    out = {'batch_id': batch_id, 'dry_run': dry_run, 'retired': sorted(entries),
           'backup': '%s/%s.json' % (BACKUP_DIR, batch_id)}
    if dry_run:
        return out
    bpath = root / BACKUP_DIR / (batch_id + '.json')
    if bpath.exists():
        raise Refuse('BACKUP_EXISTS', 'sao luu %s da ton tai — dung batch-id khac' % bpath.relative_to(root))
    btext = doc_text(backup).encode('utf-8')
    atomic_write(bpath, btext)
    if bpath.read_bytes() != btext:
        raise Refuse('BACKUP_READBACK', 'doc lai sao luu khong khop (chua sua gi)')
    removed = []
    try:
        for aid, e in sorted(entries.items()):
            (root / e['stub_path']).unlink()
            removed.append(aid)
        atomic_write(reg_path, reg_new)
    except BaseException:
        for aid in removed:
            atomic_write(root / entries[aid]['stub_path'], entries[aid]['stub_text'].encode('utf-8'))
        atomic_write(reg_path, reg_old)
        raise
    problems = verify_backup(root, backup)
    if problems:
        rollback_backup(root, backup)
        raise Refuse('VERIFY_AFTER_APPLY', 'kiem lai sau khi ghi khong dat — da hoan tac', problems=problems[:10])
    out['ok'] = True
    return out


def check_backup_shape(backup):
    if backup.get('schema') != BACKUP_SCHEMA:
        raise Refuse('BAD_BACKUP', 'schema sao luu khong dung')
    if not isinstance(backup.get('entries'), dict) or not backup['entries']:
        raise Refuse('BAD_BACKUP', 'sao luu khong co entries')
    for k in ('approval_ref', 'live_ref', 'batch_id'):
        if not (isinstance(backup.get(k), str) and backup[k].strip()):
            raise Refuse('BAD_BACKUP', 'sao luu thieu %s' % k)
    for aid, e in backup['entries'].items():
        if not AID_RE.match(aid) or not isinstance(e, dict) or not isinstance(e.get('registry_row'), dict):
            raise Refuse('BAD_BACKUP', 'muc %r khong hop le' % (aid,))
        if e.get('stub_path') != SR.stub_relpath(aid) or not isinstance(e.get('stub_text'), str):
            raise Refuse('BAD_BACKUP', '%s: stub_path/stub_text sai' % aid)
        if sha(e['stub_text'].encode('utf-8')) != e.get('stub_sha256'):
            raise Refuse('BACKUP_CORRUPT', '%s: stub_text khong khop sha256' % aid)
        row = e['registry_row']
        if row.get('article_id') != aid or row.get('status') != SR.MIGRATED or e['stub_text'] != SR.stub_source(row):
            raise Refuse('BAD_BACKUP', '%s: dong registry cu khong phai MIGRATED/khong sinh ra dung trang chuyen huong' % aid)


def verify_backup(root, backup):
    """Kiểm trạng thái ĐÃ GHI: dòng registry = dòng cũ với status RETIRED, trang chuyển hướng đã gỡ, bài URL mới còn nguyên,
    không còn liên kết nào trong nguồn trỏ URL cũ. Trả danh sách lỗi."""
    check_backup_shape(backup)
    root = pathlib.Path(root)
    reg = {r['article_id']: r for r in SR.load_registry(str(root))}
    problems = []
    olds = []
    for aid, e in sorted(backup['entries'].items()):
        want = dict(e['registry_row'], status=SR.RETIRED)
        cur = reg.get(aid)
        if cur is None or {k: cur.get(k, '') for k in SR.REGISTRY_COLUMNS} != {k: want.get(k, '') for k in SR.REGISTRY_COLUMNS}:
            problems.append('%s: dong registry khac dong cu + status RETIRED' % aid)
        if (root / e['stub_path']).exists():
            problems.append('%s: trang chuyen huong %s van ton tai' % (aid, e['stub_path']))
        post = root / want['new_output_path']
        if not post.is_file() or front_permalink(post) != want['new_url']:
            problems.append('%s: bai o URL moi thieu hoac permalink khac new_url' % aid)
        olds.append(want['old_url'])
    for old, srcs in sorted(linked_sources(root, olds).items()):
        if srcs:
            problems.append('%s: con lien ket toi URL cu da go tu %s' % (old, ', '.join(srcs[:5])))
    return problems


def rollback_backup(root, backup, dry_run=False):
    """Khôi phục trang chuyển hướng + status MIGRATED cho mục còn ĐÚNG bản đã ghi (không đè thay đổi sau đó)."""
    check_backup_shape(backup)
    root = pathlib.Path(root)
    rows = [dict(r) for r in SR.load_registry(str(root))]
    by_id = {r['article_id']: r for r in rows}
    out = {'restored': [], 'skipped_changed_since_apply': [], 'dry_run': dry_run}
    for aid, e in sorted(backup['entries'].items()):
        want = dict(e['registry_row'], status=SR.RETIRED)
        cur = by_id.get(aid)
        same = cur is not None and all(cur.get(k, '') == want.get(k, '') for k in SR.REGISTRY_COLUMNS)
        if not same or (root / e['stub_path']).exists():
            out['skipped_changed_since_apply'].append(aid)
            continue
        out['restored'].append(aid)
    if dry_run or not out['restored']:
        return out
    for aid in out['restored']:
        e = backup['entries'][aid]
        atomic_write(root / e['stub_path'], e['stub_text'].encode('utf-8'))
        by_id[aid]['status'] = SR.MIGRATED
    atomic_write(root / SR.REGISTRY_REL, SR.registry_text(rows).encode('utf-8'))
    return out


def _ids(v):
    return [x.strip() for x in (v or '').split(',') if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--ids', default='')
    p.add_argument('--out')
    a_ = sub.add_parser('apply')
    a_.add_argument('--approval-ref', default='')
    a_.add_argument('--live-ref', default='')
    a_.add_argument('--ids', default='')
    a_.add_argument('--all-eligible', action='store_true', help='moi dong MIGRATED du dieu kien (toi da %d)' % MAX_BATCH)
    a_.add_argument('--batch-id', default=None)
    a_.add_argument('--dry-run', action='store_true')
    v = sub.add_parser('verify')
    v.add_argument('--backup', required=True)
    r = sub.add_parser('rollback')
    r.add_argument('--backup', required=True)
    r.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'plan':
            plan = make_plan(ROOT, _ids(a.ids) or None)
            if a.out:
                atomic_write(os.path.abspath(a.out), doc_text(plan).encode('utf-8'))
            print(json.dumps({'ok': True, 'head': plan['head'], 'counts': plan['counts'],
                              'source_error_count': plan['source_error_count'], 'out': a.out or None},
                             ensure_ascii=False, indent=2))
            return 0
        if a.cmd == 'apply':
            require_clean_tree(ROOT)
            ids = _ids(a.ids)
            if bool(ids) == bool(a.all_eligible):
                raise Refuse('NO_IDS', 'can dung MOT trong --ids A,B hoac --all-eligible')
            if a.all_eligible:
                ids = make_plan(ROOT)['eligible']
            print(json.dumps(apply_batch(ROOT, ids, a.approval_ref, a.live_ref, a.batch_id, a.dry_run),
                             ensure_ascii=False, indent=2))
            return 0
        backup = json.loads(pathlib.Path(a.backup).read_text(encoding='utf-8'))
        if a.cmd == 'verify':
            problems = verify_backup(ROOT, backup)
            print(json.dumps({'ok': not problems, 'checked': len(backup['entries']), 'problems': problems[:200]},
                             ensure_ascii=False, indent=2))
            return 0 if not problems else 1
        out = rollback_backup(ROOT, backup, a.dry_run)
        out['ok'] = not out['skipped_changed_since_apply']
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out['ok'] else 1
    except Refuse as e:
        d = {'ok': False, 'code': e.code, 'error': e.msg}
        d.update(e.extra)
        print(json.dumps(d, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
