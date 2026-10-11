#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Test CANONICAL queue processor — scripts/factory/factory-queue.py.

Phase 3 (migration multi-writer từ /vanchinh): khối consume inline
của factory-publish.yml được thay bằng script canonical. Bộ test chặt:

  14. queue 10 -> 5 pair (pair cuối queue lẻ được 1 ID);
  15. pair FAIL content KHÔNG rollback pair đã publish; pair PLANNED
      sau bị DEFERRED (engine resume-first); rc 0 (recoverable);
  16. transaction active TRƯỚC run -> refuse fail-closed (KHÔNG đổi gì);
  17. queue-level run-lock đã giữ -> refuse fail-closed;
  18. hot path KHÔNG full-site audit (static: mọi op --scope fast,
      không validate.py trong factory-queue.py);
  cộng: duplicate/unknown/PUBLISHED-EXISTING-BLOCKED/missing-draft/
  > 10 ID refuse trước mutation; engine writer-lock stale refuse;
  report deterministic rewrite sau từng pair; KHÔNG git push / KHÔNG
  AI / KHÔNG API / KHÔNG secrets trong processor.

BO TEST NAY KHÔNG viết bài thật: mọi mutation trên bản sao tạm
(FxTestCase của test_qa_modes.py); production state phải
BYTE-IDENTICAL trước/sau (hash guard setUpModule/tearDownModule).

Chạy: python3 scripts/factory/tests/test_factory_queue.py (từ repo)
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_qa_modes import (FxTestCase, borrow_planned_row, make_draft,
                            matrix_rows, save_matrix, write_json)
from test_push_selection import draft_rel, planned_rows

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
QUEUE_SRC = os.path.join(ROOT, 'scripts', 'factory', 'factory-queue.py')

REAL_GUARD_FILES = [
    'data/content-matrix.csv',
    'data/state/checkpoint.json',
    'data/state/transaction.json',
    'data/factory/production-control.json',
]
_GUARD = {}


def _file_hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def setUpModule():
    for rel in REAL_GUARD_FILES:
        _GUARD[rel] = _file_hash(os.path.join(ROOT, rel))


def tearDownModule():
    for rel, want in _GUARD.items():
        got = _file_hash(os.path.join(ROOT, rel))
        assert got == want, (
            'PRODUCTION STATE BỊ ĐỔI TRONG TEST: %s (%s != %s)'
            % (rel, got, want))
    for p in ('/tmp/queue-summary.json',):
        if os.path.exists(p):
            os.remove(p)


def load_queue_module(fx):
    spec = importlib.util.spec_from_file_location(
        'blog_factory_queue', os.path.join(fx, 'scripts/factory/factory-queue.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def queue_run(fx, ids, mode='new', rc_expect=None, env_extra=None):
    """Chạy factory-queue.py trên fixture; report/summary ghi VÀO fixture
    (env override) để KHÔNG đụng production /tmp/queue-summary.json."""
    env = dict(os.environ)
    env['FACTORY_QUEUE_REPORT'] = os.path.join(fx, 'tmp-queue-report.json')
    env['FACTORY_QUEUE_SUMMARY'] = os.path.join(fx, 'tmp-queue-summary.json')
    env.pop('GITHUB_OUTPUT', None)
    env.update(env_extra or {})
    r = subprocess.run(
        [sys.executable, 'scripts/factory/factory-queue.py', 'run',
         '--ids', ids, '--mode', mode],
        cwd=fx, capture_output=True, text=True, env=env)
    if rc_expect is not None:
        assert r.returncode == rc_expect, (
            'factory-queue rc=%d (kỳ vọng %d): %s%s'
            % (r.returncode, rc_expect, r.stdout, r.stderr))
    out = {'rc': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}
    for key, rel in (('report', 'tmp-queue-report.json'),
                     ('summary', 'tmp-queue-summary.json')):
        p = os.path.join(fx, rel)
        out[key] = (json.load(open(p, encoding='utf-8'))
                    if os.path.exists(p) else None)
    return out


def borrow_with_drafts(fx, count, starve_ids=()):
    """Mượn `count` hàng PLANNED (matrix order) + draft đạt gate; các ID
    trong starve_ids bị cắt ngắn body để QA chắc chắn FAIL -> REPAIR."""
    borrow_planned_row(fx, count=count)
    rows = planned_rows(fx)
    assert len(rows) >= count
    chosen = rows[:count]
    for row in chosen:
        make_draft(fx, row)
    for row in chosen:
        if row['id'] in set(starve_ids):
            p = os.path.join(fx, draft_rel(row))
            with open(p, encoding='utf-8') as f:
                text = f.read()
            fm_end = text.index('\n---\n') + len('\n---\n')
            body = text[fm_end:].split('\n\n')[0]  # ~30 từ — quá ngắn
            with open(p, 'w', encoding='utf-8') as f:
                f.write(text[:fm_end] + body)
    return chosen


class PairingUnitTest(unittest.TestCase):
    """Item 14 + static safety của processor (không cần fixture)."""

    def test_01_queue_10_splits_5_pairs(self):
        m = load_queue_module(ROOT)
        q = ['BLG-%05d' % i for i in range(1, 11)]
        pairs = m.split_pairs(q, 2)
        self.assertEqual(len(pairs), 5)
        for p in pairs:
            self.assertEqual(len(p), 2)
        self.assertEqual([i for pair in pairs for i in pair], q)

    def test_02_odd_queue_last_pair_single(self):
        m = load_queue_module(ROOT)
        pairs = m.split_pairs(['a', 'b', 'c', 'd', 'e'], 2)
        self.assertEqual(len(pairs), 3)
        self.assertEqual(pairs[-1], ['e'])

    def test_03_pair_size_invalid(self):
        m = load_queue_module(ROOT)
        with self.assertRaises(ValueError):
            m.split_pairs(['a', 'b'], 0)

    def test_04_hot_path_no_full_site_audit(self):
        """Item 18: mọi op gọi --scope fast; KHÔNG validate.py trong
        processor (light matrix smoke là step riêng của workflow)."""
        src = open(QUEUE_SRC, encoding='utf-8').read()
        self.assertIn("'--scope', 'fast'", src)
        self.assertNotIn("'full'", src)
        self.assertNotIn("'deep'", src)
        self.assertNotIn('validate.py', src)

    def test_05_no_git_no_secrets(self):
        """Item 19/20: processor KHÔNG git (commit/push thuộc workflow),
        KHÔNG force push, KHÔNG AI/API/secrets."""
        src = open(QUEUE_SRC, encoding='utf-8').read()
        self.assertNotIn("'git'", src)
        self.assertNotIn('--force', src)
        self.assertNotIn('-fFORCE', src)
        for tok in ('api_key', 'API_KEY', 'SECR', 'mistral',
                    'MISTRAL', 'openai', 'anthropic'):
            self.assertNotIn(tok, src)

    def test_06_engine_paths_canonical(self):
        src = open(QUEUE_SRC, encoding='utf-8').read()
        self.assertIn('factory-operator.py', src)
        self.assertIn('factory-queue.active', src)


class QueueRefuseTest(FxTestCase):
    """Fail-closed TRƯỚC mutation: refuse KHÔNG đổi gì, KHÔNG để lại
    lock/report tác dụng phụ lên production state của fixture."""

    def _assert_untouched(self):
        self.assertEqual(
            [r['id'] for r in matrix_rows(self.fx)
             if r['status'] == 'WRITING'], [],
            'refuse mà vẫn claim = fail-open BUG')
        for p in ('data/state/factory-queue.active',
                  'data/state/factory-queue.json'):
            self.assertFalse(
                os.path.exists(os.path.join(self.fx, p)),
                'refune KHÔNG được để lại lock: %s' % p)

    def test_07_transaction_active_fail_closed(self):
        """Item 16: transaction active -> refuse, KHÔNG claim."""
        rows = borrow_with_drafts(self.fx, 2)
        ids = ','.join(r['id'] for r in rows)
        write_json(self.fx, 'data/state/transaction.json',
                   {'active': True,
                    'pending': {'step': 'promote pair'}})
        out = queue_run(self.fx, ids, rc_expect=1)
        self.assertIn('transaction active', out['stdout'])
        self._assert_untouched()

    def test_08_engine_writer_lock_fail_closed(self):
        rows = borrow_with_drafts(self.fx, 2)
        ids = ','.join(r['id'] for r in rows)
        with open(os.path.join(self.fx, 'data/state/writer-lock.active'),
                  'w', encoding='utf-8') as f:
            f.write('stale-token')
        out = queue_run(self.fx, ids, rc_expect=1)
        self.assertIn('writer lock', out['stdout'])
        self._assert_untouched()

    def test_09_queue_lock_conflict_fail_closed(self):
        """Item 17: run-lock queue đã bị giữ -> refuse fail-closed."""
        rows = borrow_with_drafts(self.fx, 2)
        ids = ','.join(r['id'] for r in rows)
        with open(os.path.join(self.fx, 'data/state/factory-queue.active'),
                  'w', encoding='utf-8') as f:
            f.write('khac 123')
        with open(os.path.join(self.fx, 'data/state/factory-queue.json'),
                  'w', encoding='utf-8') as f:
            json.dump({'held_at': 'x', 'pid': 123}, f)
        out = queue_run(self.fx, ids, rc_expect=1)
        self.assertIn('run-lock', out['stdout'])
        # sentinel của tiến trình khác PHẢI còn nguyên
        with open(os.path.join(self.fx,
                               'data/state/factory-queue.active'),
                  encoding='utf-8') as f:
            self.assertEqual(f.read().strip(), 'khac 123')
        self.assertEqual(
            [r['id'] for r in matrix_rows(self.fx)
             if r['status'] == 'WRITING'], [])

    def test_10_duplicate_id_refused(self):
        rows = borrow_with_drafts(self.fx, 1)
        out = queue_run(self.fx, '%s,%s' % (rows[0]['id'], rows[0]['id']),
                        rc_expect=1)
        self.assertIn('id trung nhau', out['stdout'])
        self._assert_untouched()

    def test_11_unknown_id_refused(self):
        borrow_with_drafts(self.fx, 1)
        out = queue_run(self.fx, 'BLG-99999', rc_expect=1)
        self.assertIn('khong co trong matrix', out['stdout'])
        self._assert_untouched()

    def test_12_locked_status_refused(self):
        for status in ('PUBLISHED', 'EXISTING', 'BLOCKED'):
            rows = borrow_with_drafts(self.fx, 1)
            aid = rows[0]['id']
            allrows = matrix_rows(self.fx)
            for r in allrows:
                if r['id'] == aid:
                    r['status'] = status
            save_matrix(self.fx, allrows)
            out = queue_run(self.fx, aid, rc_expect=1)
            self.assertIn('khong duoc sua lai', out['stdout'])
            self._assert_untouched()

    def test_13_missing_draft_refused(self):
        rows = borrow_with_drafts(self.fx, 2)
        os.remove(os.path.join(self.fx, draft_rel(rows[1])))
        out = queue_run(self.fx,
                        ','.join(r['id'] for r in rows), rc_expect=1)
        self.assertIn('chua co draft', out['stdout'])
        self.assertIn(rows[1]['id'], out['stdout'])
        self._assert_untouched()

    def test_14_over_ten_ids_refused(self):
        borrow_with_drafts(self.fx, 11)
        rows = planned_rows(self.fx)[:11]
        out = queue_run(self.fx,
                        ','.join(r['id'] for r in rows), rc_expect=1)
        self.assertIn('> toi da 10', out['stdout'])
        self._assert_untouched()


class QueueConsumeTest(FxTestCase):
    """Item 15: chạy queue THẬT trên fixture (engine canonical)."""

    def test_15_pair_fail_keeps_published_pairs_and_defers_rest(self):
        # 6 hàng PLANNED = 3 pair: pair1 đạt gate; pair2 QA FAIL ->
        # REPAIR (recoverable); pair3 DEFERRED (engine resume-first).
        rows = borrow_with_drafts(self.fx, 6,
                                  starve_ids=())
        p1, p2, p3 = ([rows[0]['id'], rows[1]['id']],
                      [rows[2]['id'], rows[3]['id']],
                      [rows[4]['id'], rows[5]['id']])
        # cắt ngắn draft của pair2 SAU khi đã tạo đủ draft cho cả queue
        for r in rows[2:4]:
            p = os.path.join(self.fx, draft_rel(r))
            with open(p, encoding='utf-8') as f:
                text = f.read()
            fm_end = text.index('\n---\n') + len('\n---\n')
            body = text[fm_end:].split('\n\n')[0]
            with open(p, 'w', encoding='utf-8') as f:
                f.write(text[:fm_end] + body)
        ids = ','.join(r['id'] for r in rows)
        out = queue_run(self.fx, ids, mode='new', rc_expect=0)
        rep = out['report']
        self.assertEqual(rep['published'], p1,
                         'pair1 PHẢI publish và KHÔNG bị rollback')
        self.assertEqual(rep['recoverable'], p2)
        self.assertEqual(rep['deferred'], p3)
        self.assertEqual(rep['pairs'],
                         [{'pair_index': 1, 'ids': p1,
                           'status': 'published'},
                          {'pair_index': 2, 'ids': p2,
                           'status': 'recoverable'},
                          {'pair_index': 3, 'ids': p3,
                           'status': 'deferred'}])
        self.assertEqual(rep['queue'], [r['id'] for r in rows])
        self.assertEqual(rep['pair_size'], 2)
        self.assertIsNotNone(rep['finished'])
        # summary interface của workflow
        self.assertEqual(out['summary']['published'], p1)
        self.assertEqual(out['summary']['recoverable'], p2)
        self.assertEqual(out['summary']['deferred'], p3)
        self.assertIsNone(out['summary']['fatal'])
        # matrix truth: pair1 PUBLISHED, pair2 REPAIR, pair3 PLANNED
        st = {r['id']: r['status'] for r in matrix_rows(self.fx)}
        self.assertEqual({st[i] for i in p1}, {'PUBLISHED'})
        self.assertEqual({st[i] for i in p2}, {'REPAIR'})
        self.assertEqual({st[i] for i in p3}, {'PLANNED'})
        # bài thật đã lên _posts cho pair1
        by_id = {r['id']: r for r in matrix_rows(self.fx)}
        for aid in p1:
            self.assertTrue(os.path.exists(
                os.path.join(self.fx, by_id[aid]['output_path'])),
                'bai %s phai nam tai output_path' % aid)
        # lock sạch sau run; transaction đóng
        self.assertFalse(os.path.exists(
            os.path.join(self.fx, 'data/state/factory-queue.active')))
        self.assertFalse(os.path.exists(
            os.path.join(self.fx, 'data/state/writer-lock.active')))
        txn = json.load(open(os.path.join(self.fx,
                                          'data/state/transaction.json'),
                             encoding='utf-8'))
        self.assertFalse(txn.get('active'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
