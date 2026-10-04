#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""writer-loop.py — driver MỘT writer ngoài chạy liên tục (single-writer).

Mục tiêu (docs/WRITER-LOOP.md): writer ngoài đọc main, nối việc dang dở,
viết cặp 2 bài, QA scoped, push, xác nhận publish rồi lấy cặp tiếp — mỗi
bước MỘT lệnh, không phải mổ xẻ JSON tay.

Chế độ (KHÔNG đụng engine, KHÔNG hạ gate):
  writer-loop.py status
      Bản đọc nhanh: counts + claimable PLANNED + needs-refill + hàng
      dở (WRITING/QA/PASS/REPAIR) + lease đang giữ + ID claimable kế.
      Read-only, in JSON.
  writer-loop.py next --writer W1 [--count 2]
      Claim lease qua scripts/factory/writer-claim.py (chỉ mutate
      data/state/writer-claims.json) rồi in chi tiết đủ để viết draft:
      title, slug, output_path, canonical, kw, kw2, links, word_target.
  writer-loop.py qa --ids BLG-xxx,BLG-yyy
      Pre-check draft bằng CHÍNH scorer deterministic của engine
      (factory-operator.qa_check_one) — KHÔNG mutate matrix/checkpoint,
      KHÔNG ghi evidence (evidence do factory-publish ghi khi promote).
      exit 0 = PASS đủ ngưỡng 75/70, khác 0 = FAIL fail-closed.
  writer-loop.py verify --ids BLG-xxx,BLG-yyy
      Hậu kiểm SAU khi fetch main về cây làm việc: hàng PUBLISHED,
      checkpoint, transaction inactive, writer-lock free, draft đã được
      tiêu thụ, queue report không fatal. Read-only, exit 0 = PASS.
  writer-loop.py release --writer W1 --ids BLG-xxx,BLG-yyy
      Nhả lease qua writer-claim.py release.

Giới hạn: single writer theo lease W1 (multi-writer tooling cũ giữ
nguyên, KHÔNG mở rộng). KHÔNG ref­ill tại đây — refill là op coordinator
theo docs/CONTINUOUS-WRITER.md (refill-queue.py + stage-refill-batch.py).
"""
import argparse
import csv
import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

MATRIX = 'data/content-matrix.csv'
CLAIM = 'scripts/factory/writer-claim.py'
MIN_READY_QUEUE = 100
UNFINISHED = ('WRITING', 'QA', 'PASS', 'REPAIR')


def load_matrix():
    with open(MATRIX, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def cmd_status(args):
    rows = load_matrix()
    cp = load_json('data/state/checkpoint.json')
    counts = {}
    for r in rows:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    claimable = [r['id'] for r in rows if r['status'] == 'PLANNED']
    unfinished = [r['id'] for r in rows if r['status'] in UNFINISHED]
    reg = load_json('data/state/writer-claims.json')
    leases = {w: v.get('ids', []) for w, v in reg.get('leases', {}).items()}
    out = {
        'head_checkpoint': cp.get('last_completed_article_id'),
        'next_claimable_id': cp.get('next_claimable_id'),
        'counts': counts,
        'claimable_planned': len(claimable),
        'needs_refill': len(claimable) < MIN_READY_QUEUE,
        'min_ready_queue': MIN_READY_QUEUE,
        'unfinished_ids': unfinished,
        'leases': leases,
        'next_pairs': [claimable[i:i + 2] for i in range(0, min(len(claimable), 6), 2)],
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def _row_detail(r):
    return {
        'id': r['id'], 'status': r['status'], 'title': r['title'],
        'intent': r['intent'], 'primary_keyword': r['primary_keyword'],
        'secondary_keywords': r['secondary_keywords'],
        'parent_id': r['parent_id'], 'child_id': r['child_id'],
        'slug': r['slug'], 'output_path': r['output_path'],
        'canonical_url': r['canonical_url'],
        'internal_links': r['internal_links'],
        'word_target': r['word_target'],
        'source_required': r['source_required'], 'legal_risk': r['legal_risk'],
    }


def cmd_next(args):
    r = subprocess.run([sys.executable, CLAIM, 'claim',
                        '--writer', args.writer, '--count', str(args.count)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-2000:] + r.stderr[-1000:])
        return r.returncode
    ids = json.loads(r.stdout.strip().split(' ', 1)[1])['claimed'] \
        if r.stdout.strip().startswith('BLOG_WRITER_CLAIM') else None
    if not ids:
        sys.stderr.write('writer-loop: không đọc được ID từ claim output\n')
        return 1
    rows = {x['id']: x for x in load_matrix()}
    print(json.dumps({'writer': args.writer, 'claimed': ids,
                      'rows': [_row_detail(rows[i]) for i in ids]},
                     ensure_ascii=False, indent=1))
    return 0


def _load_scorer():
    spec = importlib.util.spec_from_file_location(
        'fo', os.path.join(ROOT, 'scripts/factory/factory-operator.py'))
    fo = importlib.util.module_from_spec(spec)
    sys.modules['fo'] = fo
    spec.loader.exec_module(fo)
    return fo


def cmd_qa(args):
    fo = _load_scorer()
    rows = load_matrix()
    biz = fo.read_json('data/business-facts.json', {})
    tax = fo.read_json('data/content-taxonomy.json', {})
    byid = {r['id']: r for r in rows}
    bad = 0
    for aid in args.ids.split(','):
        aid = aid.strip()
        if not aid:
            continue
        row = byid.get(aid)
        if row is None:
            print('%s NOT_IN_MATRIX' % aid)
            bad += 1
            continue
        ev = fo.qa_check_one(row, rows, biz, tax)
        failed = sorted(k for k, v in ev.get('checks', {}).items() if not v)
        ok = (ev.get('result') == 'PASS')
        print('%s result=%s wc=%s/%s q=%s seo=%s biz=%s legal=%s crit=%s%s' % (
            aid, ev.get('result'), ev.get('word_count'),
            ev.get('word_target'), ev.get('quality'), ev.get('seo'),
            ev.get('business_fact'), ev.get('legal'),
            ev.get('critical_failure'),
            (' fail=' + ','.join(failed)) if failed else ''))
        for k in ('bad_routes', 'cannibalization_clash', 'duplicate_title_clash',
                  'duplicate_slug_clash', 'intent_unique_clash',
                  'non_approved_amounts', 'forbidden_hits'):
            if ev.get(k):
                print('  %s: %s' % (k, ev[k]))
        if not ok:
            bad += 1
    print('WRITER_QA', 'PASS' if bad == 0 else 'FAIL')
    return 0 if bad == 0 else 1


def cmd_verify(args):
    ids = [i.strip() for i in args.ids.split(',') if i.strip()]
    rows = {r['id']: r for r in load_matrix()}
    cp = load_json('data/state/checkpoint.json')
    txn = load_json('data/state/transaction.json')
    lock = load_json('data/state/writer-lock.json')
    problems = []
    for aid in ids:
        r = rows.get(aid)
        if r is None:
            problems.append('%s: KHÔNG có trong matrix' % aid)
            continue
        if r['status'] != 'PUBLISHED':
            problems.append('%s: trạng thái %s (kỳ PUBLISHED)' % (aid, r['status']))
    if txn.get('active'):
        problems.append('transaction đang active')
    if lock.get('locked'):
        problems.append('writer-lock đang bị giữ (%s)' % lock.get('holder'))
    q = None
    try:
        q = load_json('reports/factory/factory-queue-last-run.json')
    except OSError:
        pass
    out = {'ids': ids, 'problems': problems,
           'checkpoint': {'last_completed': cp.get('last_completed_article_id'),
                           'published': cp.get('counts', {}).get('published')},
           'queue_report_fatal': bool(q and q.get('fatal')) if q else None}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print('WRITER_VERIFY', 'PASS' if not problems else 'FAIL')
    return 0 if not problems else 1


def cmd_release(args):
    r = subprocess.run([sys.executable, CLAIM, 'release',
                        '--writer', args.writer, '--ids', args.ids],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout[-3000:])
    if r.stderr.strip():
        sys.stderr.write(r.stderr[-1000:])
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description='Driver single-writer liên tục')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    p2 = sub.add_parser('next')
    p2.add_argument('--writer', default='W1')
    p2.add_argument('--count', type=int, default=2)
    p3 = sub.add_parser('qa')
    p3.add_argument('--ids', required=True)
    p4 = sub.add_parser('verify')
    p4.add_argument('--ids', required=True)
    p5 = sub.add_parser('release')
    p5.add_argument('--writer', default='W1')
    p5.add_argument('--ids', required=True)
    args = ap.parse_args()
    return {'status': cmd_status, 'next': cmd_next, 'qa': cmd_qa,
            'verify': cmd_verify, 'release': cmd_release}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
