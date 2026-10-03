#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHỌN CHẾ ĐỘ QUALITY GATE (port pattern /shop scripts/qa_scope.py).

Hợp đồng dual-mode (docs/factory-workflow-contract.md), fail-closed:

  full    — push chạm thứ ảnh hưởng engine/toàn site: scripts/**,
            _layouts/**, _includes/**, _data/**, _config.yml,
            .github/workflows/**, docs/**, data/state/matrix-seed.json,
            data/factory/** (kill switch / refill control) → chạy ĐẦY ĐỦ
            gate: validate FAST scope chunk + Jekyll build + built-link
            integrity + draft-leak + sitemap/schema/hub sanity.
  content — push thuần nội dung production: _drafts/**, _posts/**,
            data/content-matrix.csv, data/qa/**, data/state/** (trừ
            matrix-seed.json), reports/factory/** → CHỈ validate FAST
            scope chunk. KHÔNG build + KHÔNG quét link toàn site mỗi
            cycle nữa (audit nặng thuộc factory-publish-verify.yml,
            theo đợt); link của từng bài mới vẫn bị QA scoped chấm
            qua links_routes_valid ở factory-publish.yml.

Lý do: chu kỳ sản xuất đẩy drafts nhiều lần trong một batch — build
toàn site + quét mọi link ở MỌI push nội dung là full-site QA lặp
lại và còn đỏ transient khi bài đã publish link tới bài cùng batch
chưa publish (route chưa tồn tại) — 3 run Quality gate failure
2026-10-03 đều do pattern này. /shop đã chứng minh pattern: gate
content scoped, gate FULL chỉ khi engine đổi.

Fail-closed: scope không xác định được (thiếu base/danh sách rỗng)
hoặc bất kỳ đường dẫn lạ nào → full.

Chạy:
  python3 scripts/factory/gate-scope.py --changed-files FILE --scope auto|full
  # in JSON {"mode": "content"|"full", "reason": "..."} ra stdout
"""
import argparse
import json
import sys

# Thứ ảnh hưởng engine/toàn site → FULL (một file là đủ).
ENGINE_PREFIXES = (
    'scripts/',
    '_layouts/',
    '_includes/',
    '_data/',
    '.github/workflows/',
    'docs/',
    'data/factory/',
)
ENGINE_FILES = (
    '_config.yml',
    'data/state/matrix-seed.json',
)

# Nội dung production lifecycle → content mode khi KHÔNG có gì khác.
CONTENT_PREFIXES = (
    '_drafts/',
    '_posts/',
    'data/qa/',
    'data/state/',
    'reports/factory/',
)
CONTENT_FILES = (
    'data/content-matrix.csv',
)


def classify(changed):
    """Trả về (mode, reason). Fail-closed: lạ/rỗng -> full."""
    if not changed:
        return 'full', 'danh sách changed rỗng/không đọc được — fail-closed'
    for p in changed:
        p = (p or '').strip()
        if not p:
            continue
        if p in ENGINE_FILES or p.startswith(ENGINE_PREFIXES):
            return 'full', 'đổi engine/toàn site: %s' % p
        known = (p in CONTENT_FILES or p.startswith(CONTENT_PREFIXES))
        if not known:
            return 'full', 'đường dẫn ngoài hợp đồng content: %s' % p
    return 'content', 'push thuần nội dung (drafts/posts/matrix/QA evidence)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--changed-files', required=True,
                    help='file danh sách path đổi (mỗi dòng một path)')
    ap.add_argument('--scope', default='auto',
                    choices=('auto', 'full'),
                    help='auto = phân loại từ changed files; full = ép FULL')
    args = ap.parse_args()
    if args.scope == 'full':
        mode, reason = 'full', 'scope=full (dispatch/base không rõ) — ép FULL'
    else:
        try:
            with open(args.changed_files, encoding='utf-8') as f:
                changed = f.read().splitlines()
        except OSError:
            changed = []
        mode, reason = classify(changed)
    json.dump({'mode': mode, 'reason': reason}, sys.stdout,
              ensure_ascii=False)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
