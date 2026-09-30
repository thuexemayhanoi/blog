#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QA CLI thủ công — 3 mức FAST / DEEP / FULL (docs/PROC-PUBLISH.md).

Sản xuất thủ công (manual production): KHÔNG có self-dispatch, KHÔNG có
vòng lặp Actions tự chạy tiếp. Người vận hành (chủ xe / agent theo lệnh
tay "CONTINUE BLOG") tự quyết định khi nào chạy mức nào:

  python3 scripts/factory/qa.py --mode fast [--ids BLG-xxx,...]
      MẶC ĐỊNH cho mỗi cặp 2 bài. QA deterministic từng bài (cấu
      trúc, SEO on-page, link nội bộ, business facts, cannibalization,
      legal/source) + validate.py --scope chunk (chỉ chunk hiện tại +
      nền bắt buộc). KHÔNG quét legacy 483 bài, KHÔNG sitemap live,
      KHÔNG audit toàn site. Ngưỡng KHÔNG đổi giữa các mức: quality >= 75,
      seo >= 70, business_fact/legal PASS-FAIL.

  python3 scripts/factory/qa.py --mode deep
      Sau ~50 bài hoặc khi cần soát rộng: everything của fast + hạng
      mục rộng (inventory/matrix/hub/URL legacy, không sitemap live)
      + bài test link integrity.

  python3 scripts/factory/qa.py --mode full
      Định kỳ / final verification: validate toàn repository + sitemap
      live + toàn bộ test + capacity-audit. KHÔNG phải điều kiện xuất
      bản mỗi chunk.

QA từng bài (bằng chứng data/qa/<ID>.json) và publish gate KHÔNG đổi
giữa các mức — chỉ phạm vi validate nền tảng thay đổi. Mức fast vẫn
bắt buộc quality >= 75, seo >= 70, legal/source gate, business facts.
"""
import argparse
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

MODES = ('fast', 'deep', 'full')


def run(cmd):
    print('$ python3 %s' % ' '.join(cmd))
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True)
    print(r.stdout[-3000:])
    if r.stderr.strip():
        print(r.stderr[-1000:], file=sys.stderr)
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description='QA thủ công 3 mức (fast/deep/full)')
    ap.add_argument('--mode', choices=MODES, default='fast')
    ap.add_argument('--ids', default='',
                    help='dành cho fast: danh sách ID chunk (mặc định: hàng '
                         'WRITING/QA/REPAIR hiện có)')
    ap.add_argument('--skip-article-qa', action='store_true',
                    help='chỉ chạy validate nền theo mức, bỏ QA từng bài '
                         '(dùng khi chưa có draft)')
    args = ap.parse_args()

    if args.mode == 'full':
        rc = run(['scripts/factory/validate.py', '--scope', 'full'])
        if rc != 0:
            print('qa full: validate full FAIL — KHÔNG khai PASS.')
            return 1
        for t in ('scripts/factory/capacity-audit.py',
                  'scripts/factory/tests/test_publish_gate.py',
                  'scripts/factory/tests/test_refill_safety.py',
                  'scripts/factory/tests/test_operator.py',
                  'scripts/factory/tests/test_link_integrity.py',
                  'scripts/factory/tests/test_qa_modes.py'):
            if run([t]) != 0:
                print('qa full: FAIL ở %s' % t)
                return 1
        print('qa full: PASS (toàn repository)')
        return 0

    # fast / deep: QA từng bài qua operator chuẩn (lock/transaction/evidence)
    op_cmd = ['scripts/factory/factory-operator.py', 'qa', '--scope', args.mode]
    if args.ids:
        op_cmd += ['--ids', args.ids]
    if args.skip_article_qa:
        print('qa %s: bỏ QA từng bài theo cờ --skip-article-qa' % args.mode)
    else:
        rc = run(op_cmd)
        if rc != 0:
            print('qa %s: operator qa FAIL — xem evidence data/qa/<ID>.json.' % args.mode)
            return 1
    # deep: thêm hạng mục rộng (batch scope + link integrity tests)
    if args.mode == 'deep':
        if run(['scripts/factory/validate.py', '--scope', 'batch']) != 0:
            print('qa deep: validate batch FAIL.')
            return 1
        if run(['scripts/factory/tests/test_link_integrity.py']) != 0:
            print('qa deep: link integrity FAIL.')
            return 1
        print('qa deep: PASS (chunk + hạng mục rộng, không sitemap live)')
        return 0
    print('qa fast: PASS (chỉ chunk hiện tại + nền bắt buộc)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
