#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""writer-claim.py — MULTI-WRITER lease registry của /blog.

Port từ thuexemayhanoi/vanchinh scripts/writer_claim.py (SOURCE OF TRUTH)
thích ứng engine /blog (matrix data/content-matrix.csv, cột id/status,
draft _drafts/, publisher scripts/factory/factory-operator.py).

HỢP ĐỒNG (TURBO MULTI-WRITER — port nguyên semantics của /vanchinh):
  - tối đa 3 writer (MAX_WRITERS) chuẩn bị bài song song và KHÔNG BAO GIỜ
    trùng article_id;
  - một writer lease tối đa MAX_LEASE (10) hàng PLANNED của matrix,
    theo THỨ TỰ MATRIX (deterministic);
  - lease hết hạn sau TTL_HOURS (48h) và tự bị thu hồi (reclaim);
  - registry SELF-HEAL qua prune_registry() trong MỌI lệnh:
      (a) lease hết TTL bị drop;
      (b) id không còn là hàng PLANNED (đã publish / blocked / trạng
          thái khác / id lạ) bị drop;
      (c) writer còn lại không id hợp lệ nào bị xóa;
      (d) registry vượt MAX_WRITERS -> giữ MAX_WRITERS claim MỚI NHẤT;
  - registry sống ở data/state/writer-claims.json (env WRITER_CLAIMS).
    Path nằm NGOÀI paths filter của factory-publish.yml nên push registry
    KHÔNG BAO GIỜ kích hoạt production run;
  - push registry thua race (non-fast-forward): fetch fresh main, chạy
    merge với registry remote, claim lại phần còn tự do, push lại —
    KHÔNG BAO GIỜ force push.

QUAN TRỌNG (tách bạch ownership và production state):
  - lệnh này KHÔNG mutate matrix/checkpoint/production-control — lease
    registry CHỈ là ownership của WRITER;
  - claim PLANNED -> WRITING thật sự vẫn do publisher/engine canonical
    xử lý (factory-operator.py prepare-next qua factory-queue.py trong
    factory-publish.yml).

Lệnh:
  claim   --writer W [--count N|--ids A,B]  lease N hàng PLANNED còn tự do
                                          (hoặc đúng --ids khi còn tự do)
  release --writer W --ids A,B             bỏ lease (sau khi factory
                                          publish xong ID, hoặc bỏ bài)
  show                                      in registry + hàng còn tự do
                                            (tự prune trước khi báo cáo)
  prune                                     rà hiệu lực lease NGAY BÂY GIỜ
  merge   --file registry.json              gộp registry remote vào local
                                            (claimed_at SỚM HƠN thắng)

Thoát: 0 ok, 1 lỗi (KHÔNG đổi gì khi lỗi).
"""
import argparse
import csv
import json
import os
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
MATRIX = ROOT / 'data' / 'content-matrix.csv'
REGISTRY = pathlib.Path(os.environ.get(
    'WRITER_CLAIMS', str(ROOT / 'data' / 'state' / 'writer-claims.json')))
MAX_LEASE = 10     # lease sống tối đa mỗi writer (write-ahead buffer)
TTL_HOURS = 48.0   # lease cũ hơn TTL là chết và có thể reclaim
MAX_WRITERS = 3    # registry từ chối writer thứ 4


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _epoch_of(iso):
    """Epoch giây của timestamp ISO; chịu phân số giây. Timestamp hỏng
    được coi là chết (0.0) để entry cũ không bao giờ sống lại."""
    if not iso:
        return 0.0
    base = re.sub(r'\.\d+Z$', 'Z', iso)
    try:
        return time.mktime(time.strptime(base, '%Y-%m-%dT%H:%M:%SZ'))
    except Exception:
        return 0.0


def load_matrix_rows():
    with open(MATRIX, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def load_registry():
    if not REGISTRY.is_file():
        return {'schema_version': '1', 'updated_at': None, 'leases': {}}
    try:
        d = json.loads(REGISTRY.read_text(encoding='utf-8'))
    except Exception:
        return {'schema_version': '1', 'updated_at': None, 'leases': {}}
    if not isinstance(d, dict) or not isinstance(d.get('leases'), dict):
        return {'schema_version': '1', 'updated_at': None, 'leases': {}}
    d.setdefault('schema_version', '1')
    d.setdefault('leases', {})
    return d


def save_registry(reg):
    reg['schema_version'] = '1'
    reg['updated_at'] = _now()
    reg['leases'] = {w: l for w, l in sorted(reg['leases'].items())}
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2),
                        encoding='utf-8')


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


def _planned_ids(rows):
    """ID các hàng PLANNED, deterministic theo THỨ TỰ MATRIX."""
    return [r['id'] for r in rows if r['status'] == 'PLANNED']


def prune_registry(reg, rows, now=None):
    """Ép hiệu lực lease TẠI CHỖ. Thứ tự (quy tắc ownership):
    (a) lease hết TTL bị drop; (b) id không còn PLANNED bị drop;
    (c) writer không còn id hợp lệ bị xóa (ẩn trong (b));
    (d) vượt MAX_WRITERS -> giữ MAX_WRITERS claim mới nhất.
    Trả report dict, KHÔNG bao giờ raise."""
    now = now if now is not None else time.time()
    report = {'expired': [], 'invalid_ids': {}, 'removed_writers': [],
              'capped': [], 'kept': {}}
    for w in [w for w, l in reg['leases'].items()
              if _epoch_of(l.get('expires_at', '')) < now]:
        del reg['leases'][w]
        report['expired'].append(w)
    valid = set(_planned_ids(rows))
    for w in list(reg['leases'].keys()):
        lease = reg['leases'][w]
        keep = [a for a in lease.get('ids', []) if a in valid]
        dropped = [a for a in lease.get('ids', []) if a not in set(keep)]
        if dropped:
            report['invalid_ids'][w] = dropped
        if keep:
            lease['ids'] = keep
        else:
            del reg['leases'][w]
            report['removed_writers'].append(w)
    if len(reg['leases']) > MAX_WRITERS:
        by_age = sorted(reg['leases'].items(),
                        key=lambda kv: (_epoch_of(kv[1].get('claimed_at') or ''),
                                        kv[0]))
        for w, _ in by_age[:-MAX_WRITERS]:
            del reg['leases'][w]
            report['capped'].append(w)
    report['kept'] = {w: list(l['ids']) for w, l in reg['leases'].items()}
    return report


def _selfheal(reg, rows, now=None):
    """prune_registry + PERSIST khi có gì bị drop (self-heal trong mọi
    lệnh; prune no-op KHÔNG ghi file)."""
    report = prune_registry(reg, rows, now)
    if (report['expired'] or report['invalid_ids']
            or report['removed_writers'] or report['capped']):
        save_registry(reg)
    return report


def _expires_at(now=None):
    now = now if now is not None else time.time()
    return time.strftime('%Y-%m-%dT%H:%M:%SZ',
                         time.gmtime(now + TTL_HOURS * 3600))


def cmd_claim(writer, count=None, ids=None, now=None):
    reg = load_registry()
    rows = load_matrix_rows()
    _selfheal(reg, rows, now)
    live = _live_leases(reg, now)
    mine = reg['leases'].get(writer)
    already = list(mine['ids']) if mine else []
    want_ids = [a for a in (ids or []) if a]
    want_count = len(want_ids) if want_ids else (count or MAX_LEASE)
    if want_count > MAX_LEASE or len(already) + want_count > MAX_LEASE:
        print(json.dumps({'error': 'muc lease toi da la %d moi writer'
                          % MAX_LEASE, 'writer': writer,
                         'already_leased': already,
                         'requested': want_count}))
        return 1
    planned = _planned_ids(rows)
    status_of = {r['id']: r['status'] for r in rows}
    for a in want_ids:
        if status_of.get(a) != 'PLANNED':
            print(json.dumps({'error': '%s: khong phai hang PLANNED' % a,
                              'writer': writer}))
            return 1
        holder = live.get(a)
        if holder and holder[0] != writer:
            print(json.dumps({'error': '%s: da bi lease boi writer %s'
                              % (a, holder[0]), 'writer': writer}))
            return 1
    if writer not in reg['leases'] and len(reg['leases']) >= MAX_WRITERS:
        print(json.dumps({'error': 'registry da giu %d writer'
                          % MAX_WRITERS,
                          'writers': sorted(reg['leases'])[:5],
                          'writer': writer}))
        return 1
    free = [a for a in planned if a not in live or live[a][0] == writer]
    if want_ids:
        new_ids = [a for a in want_ids if a not in already]
        missing = [a for a in new_ids if a not in free]
        if missing:
            print(json.dumps({'error': 'id khong con tu do: %s'
                              % ','.join(missing), 'writer': writer}))
            return 1
    else:
        new_ids = [a for a in free if a not in already][:want_count]
    if not new_ids:
        print(json.dumps({'error': 'khong con hang PLANNED tu do de lease',
                          'writer': writer, 'free_count': 0}))
        return 1
    lease_ids = sorted(set(already + new_ids))
    reg['leases'][writer] = {'ids': lease_ids, 'claimed_at': _now(),
                             'expires_at': _expires_at(now)}
    save_registry(reg)
    out = {'writer': writer, 'claimed': new_ids,
           'leased_total': lease_ids, 'count': len(lease_ids),
           'expires_at': reg['leases'][writer]['expires_at'],
           'registry': str(REGISTRY)}
    print('BLOG_WRITER_CLAIM ' + json.dumps(out, ensure_ascii=False))
    return 0


def cmd_release(writer, ids):
    reg = load_registry()
    rows = load_matrix_rows()
    _selfheal(reg, rows)
    mine = reg['leases'].get(writer)
    if not mine:
        print(json.dumps({'writer': writer, 'released': [],
                          'leased_total': []}))
        return 0
    drop = [a for a in ids if a in mine['ids']]
    keep = [a for a in mine['ids'] if a not in set(drop)]
    if keep:
        mine['ids'] = keep
    else:
        del reg['leases'][writer]
    save_registry(reg)
    print(json.dumps({'writer': writer, 'released': drop,
                      'leased_total': keep}))
    return 0


def cmd_show():
    reg = load_registry()
    rows = load_matrix_rows()
    _selfheal(reg, rows)
    live = _live_leases(reg)
    planned = _planned_ids(rows)
    taken = set(live)
    out = {'writers': {w: l['ids'] for w, l in reg['leases'].items()},
           'planned_total': len(planned),
           'planned_free': [a for a in planned
                            if a not in taken][:MAX_LEASE],
           'registry': str(REGISTRY)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_prune():
    reg = load_registry()
    rows = load_matrix_rows()
    report = prune_registry(reg, rows)
    save_registry(reg)
    print('BLOG_WRITER_PRUNE ' + json.dumps(
        {'report': report, 'registry': str(REGISTRY)},
        ensure_ascii=False, indent=2))
    return 0


def cmd_merge(path):
    """Gộp registry remote vào local. Mọi id incoming được đối chiếu với
    MỌI lease local; xung đột: claimed_at SỚM HƠN thắng (thứ bậc phụ:
    tên writer nhỏ hơn). Writer thua giữ các id còn lại và được báo
    rõ để claim bù. KHÔNG force-override; kết quả được lưu."""
    other = json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    reg = load_registry()
    rows = load_matrix_rows()
    prune_registry(reg, rows)
    valid = set(_planned_ids(rows))
    conflicts, lost, invalid = [], [], []
    for w, l in (other.get('leases') or {}).items():
        incoming = list(l.get('ids', []))
        keep = []
        for a in incoming:
            if a not in valid:
                # id không còn PLANNED KHÔNG BAO GIỜ vào local qua merge
                invalid.append({'id': a, 'writer': w})
                continue
            holder = next(((ow, ol) for ow, ol in reg['leases'].items()
                           if ow != w and a in ol['ids']), None)
            if holder is None:
                keep.append(a)
                continue
            ow, ol = holder
            if (_epoch_of(l.get('claimed_at') or ''), w) < \
               (_epoch_of(ol.get('claimed_at') or ''), ow):
                ol['ids'] = [x for x in ol['ids'] if x != a]
                if not ol['ids']:
                    del reg['leases'][ow]
                conflicts.append({'id': a, 'winner': w, 'loser': ow})
                keep.append(a)
            else:
                lost.append({'id': a, 'winner': ow, 'loser': w})
        if keep:
            lease = reg['leases'].get(w) or {}
            lease['ids'] = sorted(set(list(lease.get('ids', [])) + keep))[:MAX_LEASE]
            lease['claimed_at'] = l.get('claimed_at')
            lease['expires_at'] = l.get('expires_at')
            reg['leases'][w] = lease
    prune_registry(reg, rows)
    save_registry(reg)
    print(json.dumps({'merged': True, 'conflicts': conflicts,
                      'rejected_not_planned': invalid,
                      'lost_to_other_writer': lost,
                      'writers': {w: l['ids']
                                  for w, l in reg['leases'].items()}},
                     ensure_ascii=False, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(add_help=True)
    sub = ap.add_subparsers(dest='command', required=True)
    c = sub.add_parser('claim')
    c.add_argument('--writer', required=True)
    g = c.add_mutually_exclusive_group()
    g.add_argument('--count', type=int, default=None)
    g.add_argument('--ids', default=None,
                   help='danh sách id phân tách dấu phẩy')
    r = sub.add_parser('release')
    r.add_argument('--writer', required=True)
    r.add_argument('--ids', required=True)
    sub.add_parser('show')
    sub.add_parser('prune')
    m = sub.add_parser('merge')
    m.add_argument('--file', required=True,
                   help='bản sao registry JSON từ remote')
    args = ap.parse_args()
    os.chdir(ROOT)
    if args.command == 'claim':
        ids = ([v.strip() for v in args.ids.split(',') if v.strip()]
               if args.ids else None)
        return cmd_claim(args.writer, count=args.count, ids=ids)
    if args.command == 'release':
        return cmd_release(args.writer,
                           [v.strip() for v in args.ids.split(',')
                            if v.strip()])
    if args.command == 'show':
        return cmd_show()
    if args.command == 'prune':
        return cmd_prune()
    if args.command == 'merge':
        return cmd_merge(args.file)
    return 2


if __name__ == '__main__':
    sys.exit(main())
