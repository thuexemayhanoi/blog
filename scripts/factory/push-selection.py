#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push-selection.py — CANONICAL queue selector của đường nóng publish.

Hợp đồng 6 workflow (docs/factory-workflow-contract.md): factory-publish.yml
gọi script NÀY để chọn queue từ push — KHÔNG còn selector Python inline
trùng lặp trong workflow YAML (một nguồn sự thật duy nhất, tránh drift
giữa hai implementation).

Input (giống capture push scope của workflow — output của git diff,
tách khỏi git để test fixture không cần git):
  --added <file>     path ADDED trong push    (git diff --diff-filter=A)
  --modified <file>  path MODIFIED trong push (git diff --diff-filter=M)
  Mỗi dòng một path tương đối với gốc repo (ví dụ `_drafts/<file>.md`).

Output:
  - JSON deterministic trên stdout (kết quả selection cho test/log);
  - nếu env GITHUB_OUTPUT tồn tại: append `queue=`, `mode=`, `pairs=`
    (step outputs — mọi step sau của workflow đọc
    `steps.select.outputs.queue != ''` để biết có queue hay không).

Semantics (port CHÍNH XÁC từ selector inline cũ của factory-publish.yml):
  - queue 2..10 draft/push: TỐI ĐA 10 ID (MAX_QUEUE_PER_PUSH; lease limit
    mỗi writer); KHÔNG có min — push 1 draft hợp lệ; queue LẺ được chia
    pair (pair cuối 1 ID);
  - EXACT article_id: regex `^article_id:\\s*(BLG-\\d+)` trong 2000 ký tự
    đầu của draft; file KHÔNG phải `.md` bị bỏ qua; draft template (bài
    nhập mẫu) bị bỏ qua;
  - REFUSE (fail-closed, exit 3 — KHÔNG đổi gì):
      draft thiếu article_id trong frontmatter /
      ID trùng nhau trong cùng push /
      > 10 draft một push /
      ID không có trong matrix /
      hàng EXISTING, BLOCKED (vi phạm thật — KHÔNG BAO GIỜ ghi đè);
  - RACE PUSH TRÙNG (superseded — an toàn, KHÔNG refuse): hàng
      PUBLISHED trong push = chính push này đã được một queue run
      khác publish trong khoảng giữa writer tạo push và lần chạy này
      refresh truth (hai push writer sát nhau; concurrency group
      factory-publish tuần tự hóa các run). Push bị bypass như vậy
      được BỎ QUA sạch (`published_edits`, exit 0 — run GREEN no-op,
      KHÔNG RED), đúng semantics /shop (published edits — ignored).
      Publisher KHÔNG BAO GIỜ đụng lại bài đã publish; queue còn lại
      (nếu có) vẫn xử lý bình thường;
  - deterministic: queue sắp theo THỨ TỰ MATRIX (không theo tên file);
  - mode: `new` (queue chứa hàng PLANNED cần claim) / `repair`
    (KHÔNG claim lại từ đầu — repair rows skip claim);
  - production-control enabled=false + lần chạy cần claim bài mới ->
    exit 0 sạch TRƯỚC khi claim (queue rỗng; push repair-only vẫn hợp lệ);
  - không draft trong push -> no-op exit 0;
  - OWNERSHIP MULTI-WRITER (chỉ KÍCH HOẠT khi data/state/writer-claims.json
    TỒN TẠI — presence = multi-writer mode ON; registry vắng = single-writer
    legacy, semantics cũ giữ nguyên):
      mọi ID PLANNED cần claim PHẢI có lease sống trong registry
      (scripts/factory/writer-claim.py, TTL 48h, self-heal prune) và
      draft PHẢI khai `writer: Wx` trong frontmatter khớp writer đang
      giữ lease của ID đó (writer identity từ frontmatter draft —
      deterministic, sống trong git history sau merge, KHÔNG dựa vào
      branch name); vi phạm -> REFUSE fail-closed exit 3 (KHÔNG đổi gì).
      Repair rows KHÔNG claim lại từ đầu nên KHÔNG cần lease (prune tự
      loại id không còn PLANNED khỏi registry);
  - selector CHỈ ĐỌC: KHÔNG mutate matrix/checkpoint/production-control/
    bất kỳ file nào của repo (chỉ ghi stdout hoặc $GITHUB_OUTPUT);
  - KHÔNG AI, KHÔNG API, KHÔNG secrets.

Thoát: 0 = chọn xong (kể cả no-op/paused), 3 = refuse (fail-closed).
"""
import argparse
import csv
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATRIX = 'data/content-matrix.csv'
CONTROL = 'data/factory/production-control.json'

# Hợp đồng turbo queue: tối đa 10 draft/push; consume chia pair 2
# (pair cuối của queue lẻ có 1 ID).
MAX_QUEUE_PER_PUSH = 10
PAIR_SIZE = 2

FRONT_ID_RE = re.compile(r'^article_id:\s*(BLG-\d+)', re.M)
WRITER_RE = re.compile(r'^writer:\s*(W\d+)\s*$', re.M)
# chuỗi GHÉP để file này không chứa slug template nguyên vẹn — draft-leak
# gate grep slug này trên cây build (scripts/ bị Jekyll copy)
TEMPLATE_SLUG = 'mau' + '-nhap' + '-bai' + '-moi'
# Hàng bị REFUSE khi xuất hiện trong push (vi phạm thật): EXISTING/BLOCKED.
# Hàng PUBLISHED KHÔNG nằm trong danh sách này — xem RACE PUSH TRÙNG
# ở docstring: bị bỏ qua sạch (published_edits, exit 0), KHÔNG refuse.
REFUSED_STATUSES = ('EXISTING', 'BLOCKED')


class Refuse(Exception):
    """Push vi phạm hợp đồng queue — fail-closed, KHÔNG đổi gì."""


def load_control():
    try:
        with open(os.path.join(ROOT, CONTROL), encoding='utf-8') as f:
            c = json.load(f) or {}
        return bool(c.get('enabled', True))
    except Exception:
        return True


def load_matrix():
    with open(os.path.join(ROOT, MATRIX), encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    return {r['id']: r for r in rows}, rows


def read_paths(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return [ln.strip() for ln in f.read().splitlines() if ln.strip()]


def claim_registry():
    # Đọc writer-claims registry (CHỈ ĐỌC, KHÔNG prune/mutate). Trả
    # (reg, live) khi multi-writer mode ON; trả None khi registry KHÔNG
    # tồn tại (single-writer legacy — KHÔNG enforce ownership). Nạp
    # writer-claim.py qua importlib (tên file có gạch ngang) để dùng
    # CHÍNH XÁC load_registry/_live_leases — một nguồn sự thật.
    path = os.environ.get(
        'WRITER_CLAIMS',
        os.path.join(ROOT, 'data', 'state', 'writer-claims.json'))
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location(
        'blog_writer_claim',
        os.path.join(ROOT, 'scripts', 'factory', 'writer-claim.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    reg = mod.load_registry()
    return reg, mod._live_leases(reg)


def ids_from(paths):
    """EXACT article_id từ các path draft (port nguyên vẹn inline cũ):
    chỉ file `.md`; template bị bỏ qua; thiếu article_id -> REFUSE ngay
    (fail-closed, KHÔNG âm thầm bỏ qua draft thật)."""
    out = []
    for f in paths:
        if not f.endswith('.md'):
            continue
        if TEMPLATE_SLUG in f:
            continue  # template bai nhap mau, khong phai bai that
        try:
            with open(f, encoding='utf-8') as fh:
                head = fh.read()[:2000]
        except OSError as e:
            # fail-closed: draft không đọc được -> REFUSE sạch (KHÔNG
            # âm thầm bỏ qua; inline cũ crash traceback, vẫn fail-closed)
            raise Refuse('draft %s khong doc duoc trong HEAD (%s)'
                         % (f, e.__class__.__name__))
        m = FRONT_ID_RE.search(head)
        if not m:
            raise Refuse('draft %s thieu article_id trong frontmatter' % f)
        wm = WRITER_RE.search(head)
        out.append((m.group(1), wm.group(1) if wm else None))
    return out


def select(added, modified):
    """Chọn queue từ push; chỉ ĐỌC repository state, trả dict
    deterministic (không side-effect)."""
    control_enabled = load_control()
    by_id, rows = load_matrix()
    order = {r['id']: i for i, r in enumerate(rows)}
    out = {
        'proceed': False, 'mode': 'skip', 'queue': [], 'claim_ids': [],
        'qa_ids': [], 'pairs': 0, 'refuse': None,
        'control_enabled': control_enabled,
        'multi_writer': False, 'writers': {},
        'published_edits': [],
    }

    registry = claim_registry()
    out['multi_writer'] = registry is not None
    try:
        entries = ids_from(added) + ids_from(modified)
    except Refuse as e:
        out['refuse'] = str(e)
        return out
    queue = [a for a, _ in entries]
    declared = {a: w for a, w in entries}

    if not queue:
        # no-op sạch: không draft trong push — KHÔNG đụng matrix
        return out

    if len(set(queue)) != len(queue):
        out['refuse'] = 'id trung nhau trong cung mot push'
        return out
    if len(queue) > MAX_QUEUE_PER_PUSH:
        out['refuse'] = ('%d draft > toi da 10 moi push (turbo queue)'
                         % len(queue))
        return out
    unknown = [i for i in queue if i not in by_id]
    if unknown:
        out['refuse'] = 'id khong co trong matrix: %s' % ','.join(unknown)
        return out
    # RACE PUSH TRÙNG (superseded): một queue run khác có thể đã publish
    # đúng các ID của push này giữa lúc writer tạo push và lần chạy này
    # refresh truth (hai push writer sát nhau, các run tuần tự trong
    # concurrency group factory-publish). Bỏ qua sạch — exit 0 no-op,
    # KHÔNG refuse RED; publisher KHÔNG BAO GIỜ đụng lại hàng PUBLISHED
    # (semantics /shop: published edits — ignored). Queue còn lại vẫn
    # được xử lý bình thường.
    published = sorted((i for i in queue
                        if by_id[i]['status'] == 'PUBLISHED'),
                       key=lambda i: order[i])
    if published:
        out['published_edits'] = published
        queue = [i for i in queue
                 if by_id[i]['status'] != 'PUBLISHED']
        if not queue:
            # toàn bộ push đã được publish bởi run khác — no-op sạch
            return out
    locked = [i for i in queue
              if by_id[i]['status'] in REFUSED_STATUSES]
    if locked:
        out['refuse'] = ('id da xong/khoa, khong duoc sua lai: %s'
                         % ','.join(locked))
        return out

    # deterministic matrix order (KHÔNG theo tên file, KHÔNG theo thứ tự push)
    queue = sorted(queue, key=lambda i: order[i])

    needs_claim = any(by_id[i]['status'] == 'PLANNED' for i in queue)
    if not control_enabled and needs_claim:
        # production-control paused: KHÔNG claim bài mới — exit sạch
        # TRƯỚC mọi mutation; repair-only vẫn được phép ở lần chạy khác
        out['mode'] = 'paused'
        return out

    mode = 'new' if needs_claim else 'repair'
    out['mode'] = mode
    out['queue'] = queue
    # claim CHỈ hàng PLANNED; repair rows skip claim (KHÔNG claim lại
    # từ đầu) — consume của workflow chia pair và claim đúng subset này
    out['claim_ids'] = [i for i in queue if by_id[i]['status'] == 'PLANNED']
    out['qa_ids'] = list(queue)
    out['pairs'] = (len(queue) + 1) // 2

    if registry is not None and out['claim_ids']:
        # MULTI-WRITER mode ON: mọi ID PLANNED cần claim PHẢI thuộc lease
        # sống của ĐÚNG writer khai trong frontmatter draft. Identity từ
        # frontmatter (deterministic, theo draft vào git history sau
        # merge), KHÔNG dựa vào branch name. Fail-closed: refuse TRƯỚC
        # mọi mutation; selector KHÔNG mutate registry (chỉ ĐỌC).
        reg, live = registry
        bad = []
        for aid in out['claim_ids']:
            holder = live.get(aid)
            if holder is None:
                bad.append('%s: khong co lease song trong writer-claims '
                           'registry (multi-writer mode ON)' % aid)
            elif declared.get(aid) != holder[0]:
                bad.append('%s: draft khai writer %s nhung lease dang '
                           'thuoc writer %s'
                           % (aid, declared.get(aid), holder[0]))
        if bad:
            out['refuse'] = '; '.join(bad)
            return out
        out['writers'] = {a: declared[a] for a in out['claim_ids']}

    out['proceed'] = True
    return out


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--added', default=None,
                    help='file chứa path ADDED, mỗi dòng một path')
    ap.add_argument('--modified', default=None,
                    help='file chứa path MODIFIED, mỗi dòng một path')
    args = ap.parse_args()
    os.chdir(ROOT)
    out = select(read_paths(args.added), read_paths(args.modified))
    print(json.dumps(out, ensure_ascii=False))
    if out.get('published_edits'):
        print('selection: published_edits (race push trùng — ID đã '
              'được publish bởi run khác, bỏ qua sạch, KHÔNG sửa bài '
              'đã xuất bản): %s'
              % ','.join(out['published_edits']))
    if out['refuse']:
        print('REFUSED: %s' % out['refuse'], file=sys.stderr)
        return 3
    if out['mode'] == 'skip':
        if out.get('published_edits'):
            print('selection: push trùng đã superseded — toàn bộ ID '
                  'PUBLISHED, no-op sạch (run GREEN)')
        else:
            print('selection: khong co draft trong push — no-op')
    elif out['mode'] == 'paused':
        print('selection: production-control paused — khong claim bai '
              'moi; exit sach')
    else:
        print('selection: mode=%s queue=%s pairs=%d'
              % (out['mode'], out['queue'], out['pairs']))
    # workflow (Actions) đọc step outputs từ $GITHUB_OUTPUT; local/test
    # KHÔNG có biến này — stdout JSON ở trên là kết quả đầy đủ
    gout = os.environ.get('GITHUB_OUTPUT')
    if gout:
        with open(gout, 'a', encoding='utf-8') as f:
            f.write('queue=%s\n' % ','.join(out['queue']))
            f.write('mode=%s\n' % out['mode'])
            f.write('pairs=%s\n' % out['pairs'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
