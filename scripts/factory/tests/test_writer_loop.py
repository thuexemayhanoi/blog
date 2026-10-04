#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test writer-loop.py — driver single-writer liên tục.

Chạy: python3 scripts/factory/tests/test_writer_loop.py (từ gốc repository)

Chứng minh (docs/WRITER-LOOP.md):
  - status: read-only — JSON hợp lệ, đồng bộ checkpoint/matrix, KHÔNG
    đụng file trạng thái nào.
  - qa: fail-closed khi draft chưa tồn tại (NO_DRAFT, exit 1) và
    KHÔNG mutate matrix/checkpoint (pre-check, không ghi evidence).
  - verify: phát hiện hàng chưa PUBLISHED (exit 1); PASS với hàng đã
    PUBLISHED khi transaction inactive + writer-lock free.
  - next/release: claim lease 2 hàng PLANNED đầu (deterministic, đúng
    thứ tự matrix) rồi nhả sạch; cả hai lệnh KHÔNG đụng
    matrix/checkpoint (lease CHỈ sống trong writer-claims.json).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

IGNORE = shutil.ignore_patterns('.git', '_site', '.jekyll-cache', '__pycache__',
                                'node_modules', 'vendor', '*.pyc')


def run_py(args, cwd):
    return subprocess.run([sys.executable] + args, capture_output=True,
                          text=True, cwd=cwd)


def sha(fx, rel):
    with open(os.path.join(fx, rel), 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def matrix_rows(fx):
    import csv
    with open(os.path.join(fx, 'data/content-matrix.csv'), encoding='utf-8',
              newline='') as f:
        return list(csv.DictReader(f))


def write_json(fx, rel, obj):
    p = os.path.join(fx, rel)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


class WriterLoopTestCase(unittest.TestCase):
    """Sao chép repository thật vào thư mục tạm cho MỖI test — mọi
    mutation xảy ra trên bản sao riêng. Fixture hermetic: registry lease
    reset về rỗng (repo thật có thể đang giữ lease thật)."""

    def setUp(self):
        base = tempfile.mkdtemp(prefix='writer-loop-')
        self.fx = os.path.join(base, 'repo')
        shutil.copytree(ROOT, self.fx, ignore=IGNORE)
        write_json(self.fx, 'data/state/writer-claims.json',
                   {'schema_version': '1', 'updated_at': None, 'leases': {}})
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)

    def loop(self, *args):
        return run_py(['scripts/factory/writer-loop.py'] + list(args), self.fx)

    def first_planned(self):
        return next(r['id'] for r in matrix_rows(self.fx)
                    if r['status'] == 'PLANNED')

    def first_published_planned(self):
        return next(r['id'] for r in matrix_rows(self.fx)
                    if r['status'] == 'PUBLISHED'
                    and r['source'].startswith('planned:'))

    def test_status_json_readonly(self):
        guards = {rel: sha(self.fx, rel) for rel in (
            'data/content-matrix.csv', 'data/state/checkpoint.json',
            'data/state/writer-claims.json', 'data/state/transaction.json')}
        r = self.loop('status')
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        cp = json.load(open(os.path.join(
            self.fx, 'data/state/checkpoint.json'), encoding='utf-8'))
        for key in ('head_checkpoint', 'next_claimable_id', 'counts',
                    'claimable_planned', 'needs_refill', 'min_ready_queue',
                    'unfinished_ids', 'leases', 'next_pairs'):
            self.assertIn(key, out)
        self.assertEqual(out['head_checkpoint'],
                         cp.get('last_completed_article_id'))
        self.assertEqual(out['claimable_planned'],
                         sum(1 for x in matrix_rows(self.fx)
                             if x['status'] == 'PLANNED'))
        for rel, h in guards.items():
            self.assertEqual(sha(self.fx, rel), h,
                             'status phải read-only, đụng %s' % rel)

    def test_qa_fail_closed_missing_draft(self):
        aid = self.first_planned()
        guards = {rel: sha(self.fx, rel) for rel in (
            'data/content-matrix.csv', 'data/state/checkpoint.json')}
        r = self.loop('qa', '--ids', aid)
        self.assertNotEqual(r.returncode, 0, 'qa thiếu draft phải FAIL')
        self.assertIn('NO_DRAFT', r.stdout)
        self.assertIn('WRITER_QA FAIL', r.stdout)
        self.assertFalse(os.path.exists(
            os.path.join(self.fx, 'data/qa', aid + '.json')),
            'qa pre-check KHÔNG được ghi evidence')
        for rel, h in guards.items():
            self.assertEqual(sha(self.fx, rel), h)

    def test_verify_fail_on_planned_pass_on_published(self):
        planned = self.first_planned()
        published = self.first_published_planned()
        r = self.loop('verify', '--ids', planned)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('WRITER_VERIFY FAIL', r.stdout)
        r = self.loop('verify', '--ids', published)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout[:r.stdout.rfind('WRITER_VERIFY')])
        self.assertEqual(out['problems'], [])
        self.assertFalse(out['checkpoint']['published'] is None)

    def test_next_claim_then_release(self):
        rows = matrix_rows(self.fx)
        expected = [r['id'] for r in rows if r['status'] == 'PLANNED'][:2]
        guards = {rel: sha(self.fx, rel) for rel in (
            'data/content-matrix.csv', 'data/state/checkpoint.json')}
        r = self.loop('next', '--writer', 'W1', '--count', '2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out['claimed'], expected)
        self.assertEqual(len(out['rows']), 2)
        for row in out['rows']:
            for key in ('title', 'slug', 'output_path', 'canonical_url',
                        'primary_keyword', 'internal_links', 'word_target'):
                self.assertIn(key, row)
        reg = json.load(open(os.path.join(
            self.fx, 'data/state/writer-claims.json'), encoding='utf-8'))
        self.assertEqual(reg['leases']['W1']['ids'], sorted(expected))
        r = self.loop('release', '--writer', 'W1',
                      '--ids', ','.join(expected))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        reg = json.load(open(os.path.join(
            self.fx, 'data/state/writer-claims.json'), encoding='utf-8'))
        self.assertNotIn('W1', reg['leases'], 'release phải nhả sạch lease')
        for rel, h in guards.items():
            self.assertEqual(sha(self.fx, rel), h,
                             'next/release KHÔNG đụng %s' % rel)


if __name__ == '__main__':
    unittest.main(verbosity=2)
