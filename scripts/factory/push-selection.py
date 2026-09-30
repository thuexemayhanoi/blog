#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""push-selection.py — bộ chọn phạm vi push deterministic cho đường
nóng factory-production.yml (mô hình /vanchinh thích ứng cho /blog).

Writer ngoài (Mistral) CHỈ commit/push file draft trong `_drafts/`;
workflow lấy danh sách file ADDED/MODIFIED từ `git diff HEAD~1..HEAD`
rồi gọi script này để suy ra EXACT các article ID cần claim/QA/publish —
KHÔNG BAO GIỜ claim hàng PLANNED ngẫu nhiên, KHÔNG đụng bài PUBLISHED.

Input (danh sách path, mỗi dòng một path — như factory_push_selection.py
của /vanchinh, tách khỏi git để test fixture được không cần git):
  --added <file>     path ADDED trong push    (git diff --diff-filter=A)
  --modified <file>  path MODIFIED trong push (git diff --diff-filter=M)

Output: JSON trên stdout:
  {
    "proceed": bool,          # false => workflow không chạy op nào
    "mode": "new"|"repair"|"paused"|"skip",
    "claim_ids": [...],       # PLANNED -> WRITING (prepare-next --ids)
    "qa_ids": [...],          # mục tiêu QA/publish tường minh
    "refuse": null|"lý do",   # non-null => push vi phạm hợp đồng
    "control_enabled": bool,  # data/factory/production-control.json
    "chunk_size": int,
    "planned_claimable": int, # số hàng PLANNED còn claim được
    "refill_advised": bool    # claimable PLANNED < chunk_size
  }

Quy tắc chọn (fail-closed, matrix là nguồn sự thật):
  NEW:     draft của hàng PLANNED (file vừa push) -> claim EXACT ID đó.
  REPAIR:  draft của hàng WRITING/QA/REPAIR/PASS -> QA/publish EXACT ID,
           KHÔNG claim hàng PLANNED mới.
  PAUSED:  production-control enabled=false và push là bài mới ->
           workflow exit sạch TRƯỚC KHI claim (qa/publish việc dở
           vẫn được phép theo hợp đồng engine).
  SKIP:    không có draft nào trong push (no-op — vd commit tooling).

Từ chối (refuse, exit 3 — không đổi gì):
  - draft thiếu/không đọc được frontmatter hoặc thiếu article_id hợp lệ
  - article_id trùng nhau trong cùng push
  - ID không có trong matrix
  - hàng PUBLISHED/EXISTING bị push lại (KHÔNG BAO GIỜ ghi đè bài đã
    xuất bản), hàng REVIEW/BLOCKED/FAIL được bảo vệ
  - draft sai tên file YYYY-MM-DD-<slug>.md so với slug hàng matrix
  - push chứa CẢ bài mới lẫn repair (engine yêu cầu hoàn tất việc dở
    trước khi claim mới)
  - quá chunk_size article ID trong một push (mặc định 2 theo
    data/factory/production-control.json)

Thoát: 0 = chọn xong (kể cả skip/paused), 3 = refuse (fail-closed).
"""
import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MATRIX = 'data/content-matrix.csv'
CONTROL = 'data/factory/production-control.json'

ID_RE = re.compile(r'^BLG-\d{5}$')
DRAFT_RE = re.compile(r'^_drafts/[^/]+\.md$')
DRAFT_NAMED_RE = re.compile(r'^_drafts/(\d{4}-\d{2}-\d{2})-(.+)\.md$')
FRONT_ID_RE = re.compile(r'^article_id:\s*(\S+)\s*$', re.M)
REPAIRABLE = ('WRITING', 'QA', 'REPAIR', 'PASS')


def load_control():
    try:
        with open(os.path.join(ROOT, CONTROL), encoding='utf-8') as f:
            c = json.load(f) or {}
        return {'enabled': bool(c.get('enabled', True)),
                'chunk_size': int(c.get('chunk_size', 2))}
    except Exception:
        return {'enabled': True, 'chunk_size': 2}


def load_matrix():
    with open(os.path.join(ROOT, MATRIX), encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    return {r['id']: r for r in rows}, rows


def row_slug(row):
    op = row['output_path']
    if op.startswith('_posts/{date}-'):
        return op[len('_posts/{date}-'):-3]
    m = re.match(r'_posts/\d{4}-\d{2}-\d{2}-(.+)\.md$', op)
    return m.group(1) if m else None


def read_paths(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return [ln.strip() for ln in f.read().splitlines() if ln.strip()]


def draft_article_id(draft_path):
    """Đọc article_id từ frontmatter draft (đường dẫn tương đối ROOT)."""
    fp = os.path.join(ROOT, draft_path)
    if not os.path.isfile(fp):
        return None
    with open(fp, encoding='utf-8') as f:
        text = f.read()
    fm = re.match(r'^---\n(.*?)\n---', text, re.S)
    if not fm:
        return None
    m = FRONT_ID_RE.search(fm.group(1))
    return m.group(1) if m else None


def select(added, modified):
    control = load_control()
    by_id, rows = load_matrix()
    out = {
        'proceed': False, 'mode': 'skip', 'claim_ids': [], 'qa_ids': [],
        'refuse': None, 'control_enabled': control['enabled'],
        'chunk_size': control['chunk_size'],
        'planned_claimable': sum(1 for r in rows if r['status'] == 'PLANNED'),
        'refill_advised': False,
    }
    out['refill_advised'] = out['planned_claimable'] < control['chunk_size']

    def refuse(reason):
        out['refuse'] = reason
        return out

    touched = [(p, 'added') for p in added] + [(p, 'modified') for p in modified]

    # chỉ quan tâm file trong _drafts/; phần khác của push là no-op
    drafts = [(p, kind) for p, kind in touched if p.startswith('_drafts/')]
    if not drafts:
        return out

    seen_paths = set()
    ids = {}  # article_id -> (path, kind)
    for p, kind in drafts:
        if p in seen_paths:
            continue  # cùng file xuất hiện ở cả hai danh sách
        seen_paths.add(p)
        if not DRAFT_RE.match(p):
            return refuse('draft phải nằm ngay dưới _drafts/ (<date>-<slug>.md), '
                          'không trong thư mục con: %s' % p)
        if not os.path.isfile(os.path.join(ROOT, p)):
            return refuse('file push không tồn tại trong HEAD: %s' % p)
        aid = draft_article_id(p)
        if not aid or not ID_RE.match(aid):
            return refuse('draft thiếu article_id hợp lệ (BLG-xxxxx) trong '
                          'frontmatter: %s' % p)
        if aid in ids:
            return refuse('article_id trùng trong cùng push: %s (%s, %s)'
                          % (aid, ids[aid][0], p))
        ids[aid] = (p, kind)

    new_ids, repair_ids = [], []
    for aid in sorted(ids):
        p, _kind = ids[aid]
        row = by_id.get(aid)
        if row is None:
            return refuse('%s không có trong matrix — không claim ID lạ' % aid)
        if row['status'] in ('PUBLISHED', 'EXISTING'):
            return refuse('%s đã %s — KHÔNG BAO GIỜ ghi đè bài đã xuất bản'
                          % (aid, row['status']))
        if row['status'] in ('REVIEW', 'BLOCKED', 'FAIL'):
            return refuse('%s trạng thái %s được bảo vệ — không claim/QA'
                          % (aid, row['status']))
        slug = row_slug(row)
        m = DRAFT_NAMED_RE.match(p)
        if not m or not slug or m.group(2) != slug:
            return refuse('tên draft (%s) không khớp hàng matrix %s '
                          '(cần _drafts/<YYYY-MM-DD>-%s.md)'
                          % (p, aid, slug))
        if row['status'] == 'PLANNED':
            new_ids.append(aid)
        elif row['status'] in REPAIRABLE:
            repair_ids.append(aid)
        else:
            return refuse('%s trạng thái %s không thể xử lý qua push'
                          % (aid, row['status']))

    if new_ids and repair_ids:
        return refuse('push chứa cả bài mới (%s) lẫn repair (%s) — hoàn tất '
                      'việc dở (qa/publish repair) trước khi claim bài mới'
                      % (','.join(new_ids), ','.join(repair_ids)))
    total = len(new_ids) + len(repair_ids)
    if total > control['chunk_size']:
        return refuse('push chứa %d article ID > chunk_size %d — tối đa '
                      '%d bài mỗi push, tách push deterministic'
                      % (total, control['chunk_size'], control['chunk_size']))

    if new_ids:
        if not control['enabled']:
            # enabled=false: DỪNG SẠCH trước khi claim — không refuse
            # (đường nóng exit 0, không claim, không QA/publish lần này).
            out['mode'] = 'paused'
            return out
        out['mode'] = 'new'
        out['claim_ids'] = new_ids
        out['qa_ids'] = list(new_ids)
        out['proceed'] = True
        return out
    if repair_ids:
        out['mode'] = 'repair'
        out['qa_ids'] = repair_ids
        # qa/publish việc đang dở vẫn hợp lệ khi production-control tắt
        out['proceed'] = True
        return out
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
    if out['refuse']:
        print('REFUSED: %s' % out['refuse'], file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
