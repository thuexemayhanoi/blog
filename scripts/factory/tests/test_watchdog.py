#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test LIVENESS WATCHDOG — tầng 1 (unit) cho scripts/factory/watchdog.py.

Hermetic: mọi test chạy trên bản sao repository trong thư mục tạm; KHÔNG
đụng production state của repository thật. Bằng chứng READ-ONLY: hash toàn
bộ cây state trước/sau khi chạy watchdog phải KHÔNG đổi.

Chạy: python3 scripts/factory/tests/test_watchdog.py
"""
import csv
import datetime
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
PY = sys.executable
IGNORE = shutil.ignore_patterns('__pycache__', '.git', '*.pyc')

NOW = '2026-09-30T12:00:00+00:00'


def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')


def hours_ago(h):
    base = datetime.datetime.fromisoformat(NOW)
    return iso(base - datetime.timedelta(hours=h))


def fresh_copy():
    tmp = tempfile.mkdtemp(prefix='watchdog-')
    work = os.path.join(tmp, 'work')
    shutil.copytree(ROOT, work, ignore=IGNORE)
    return work, tmp


def run_watchdog(work, *extra):
    return subprocess.run(
        [PY, 'scripts/factory/watchdog.py', '--now', NOW] + list(extra),
        cwd=work, capture_output=True, text=True)


def state_of(r):
    line = [ln for ln in r.stdout.splitlines()
            if ln.startswith('WATCHDOG_JSON: ')]
    assert line, 'thiếu WATCHDOG_JSON: %r' % r.stdout
    return json.loads(line[0].split(': ', 1)[1])


def read_json(work, rel):
    return json.load(open(os.path.join(work, rel), encoding='utf-8'))


def write_json(work, rel, obj):
    p = os.path.join(work, rel)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def set_txn(work, active, age_h=None, phase=None):
    txn = read_json(work, 'data/state/transaction.json')
    txn['active'] = active
    if active:
        txn['pending'] = {'article_id': 'BLG-00999',
                          'step': 'promote BLG-00999',
                          'destination': '_posts/2026-09-30-x.md',
                          'draft': '_drafts/2026-09-30-x.md'}
    else:
        txn['pending'] = None
    if phase:
        txn['phase'] = phase
    txn['updated_at'] = hours_ago(age_h) if age_h is not None else NOW
    write_json(work, 'data/state/transaction.json', txn)


def set_lock(work, locked, age_h=None):
    meta = {'locked': locked, 'holder': 'operator-test' if locked else None,
            'acquired_at': hours_ago(age_h) if locked and age_h is not None
            else None,
            'expires_at': None,
            'updated_at': hours_ago(age_h) if age_h is not None else NOW,
            'note': 'test fixture'}
    write_json(work, 'data/state/writer-lock.json', meta)
    sentinel = os.path.join(work, 'data/state/writer-lock.active')
    if locked:
        open(sentinel, 'w', encoding='utf-8').write('testtoken')
    elif os.path.exists(sentinel):
        os.remove(sentinel)


def set_checkpoint_age(work, age_h):
    cp = read_json(work, 'data/state/checkpoint.json')
    cp['updated_at'] = hours_ago(age_h)
    write_json(work, 'data/state/checkpoint.json', cp)


def release_all_work(work):
    """Fixture: trả mọi hàng đang dở về PLANNED — queue rỗng cho test idle."""
    p = os.path.join(work, 'data/content-matrix.csv')
    rows = list(csv.DictReader(open(p, encoding='utf-8')))
    for r in rows:
        if r['status'] in ('WRITING', 'QA', 'REPAIR', 'PASS'):
            r['status'] = 'PLANNED'
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()),
                           lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    cp = read_json(work, 'data/state/checkpoint.json')
    cp['in_progress_chunk'] = None
    cp['updated_at'] = NOW
    write_json(work, 'data/state/checkpoint.json', cp)


def tree_digest(work):
    """Hash mọi file state + matrix — bằng chứng READ-ONLY."""
    h = hashlib.sha256()
    for rel in ('data/state/transaction.json',
                'data/state/checkpoint.json',
                'data/state/writer-lock.json',
                'data/content-matrix.csv'):
        h.update(open(os.path.join(work, rel), 'rb').read())
    return h.hexdigest()


class WatchdogStateTest(unittest.TestCase):
    """13 trạng thái/ngưỡng theo hợp đồng watchdog (ENGINE-RUNBOOK mục 10)."""

    def setUp(self):
        self.work, self.tmp = fresh_copy()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_01_healthy_idle_when_clean_and_queue_empty(self):
        release_all_work(self.work)
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'HEALTHY_IDLE')

    def test_02_healthy_idle_with_claimed_rows_but_fresh_state(self):
        # hàng WRITING còn (giữa 2 lệnh operator) nhưng checkpoint tươi
        # -> không kết tội stall: đây là nhịp nghỉ bình thường của writer.
        set_checkpoint_age(self.work, 0)
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = state_of(r)
        self.assertEqual(st['state'], 'HEALTHY_IDLE')
        self.assertGreaterEqual(st['unfinished_work'], 1)

    def test_03_healthy_active_fresh_txn(self):
        set_txn(self.work, True, age_h=1)
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'HEALTHY_ACTIVE')

    def test_04_healthy_active_fresh_lock(self):
        set_lock(self.work, True, age_h=1)
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'HEALTHY_ACTIVE')

    def test_05_stale_txn_at_threshold(self):
        set_txn(self.work, True, age_h=3)          # đúng ngưỡng 3h
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'STALE_TXN')

    def test_06_txn_below_threshold_not_stale(self):
        set_txn(self.work, True, age_h=2.9)
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'HEALTHY_ACTIVE')

    def test_07_stale_lock_with_unfinished_work(self):
        set_lock(self.work, True, age_h=3)         # ngưỡng 2h + còn WRITING
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'STALE_LOCK')

    def test_08_stale_orphan_lock_without_work_is_stale_lock(self):
        # Lock mồ côi stale + 0 việc dở: operator preflight vẫn coi lock
        # đang giữ là held -> chặn mọi mutation -> KHÔNG THỂ là HEALTHY_IDLE.
        release_all_work(self.work)
        set_lock(self.work, True, age_h=3)         # lock mồ côi, queue rỗng
        before = tree_digest(self.work)
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        st = state_of(r)
        self.assertEqual(st['state'], 'STALE_LOCK')
        self.assertIn('mồ côi', r.stdout)
        # READ-ONLY: watchdog KHÔNG tự xoá / force-unlock lock mồ côi
        self.assertEqual(tree_digest(self.work), before,
                         'watchdog ĐÃ WRITE — vi phạm hợp đồng READ-ONLY')

    def test_09_stalled_active_chunk_abandoned(self):
        # còn WRITING, không lock/txn, checkpoint im lặng 7h (ngưỡng 6h)
        set_checkpoint_age(self.work, 7)
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'STALLED_ACTIVE')

    def test_10_stale_checkpoint_with_work(self):
        set_checkpoint_age(self.work, 25)          # ngưỡng 24h
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'STALE_CHECKPOINT')

    def test_11_txn_priority_over_lock(self):
        set_txn(self.work, True, age_h=4)
        set_lock(self.work, True, age_h=3)
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'STALE_TXN')

    def test_12_degraded_state_files_exit_2(self):
        p = os.path.join(self.work, 'data/state/transaction.json')
        open(p, 'w', encoding='utf-8').write('{KHÔNG PHẢI JSON')
        r = run_watchdog(self.work)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'DEGRADED_STATE_FILES')

    def test_13_thresholds_overridable(self):
        # --txn-stale-hours 1: txn 2h cũ giờ là STALE (ngưỡng là tham số)
        set_txn(self.work, True, age_h=2)
        r = run_watchdog(self.work, '--txn-stale-hours', '1')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(state_of(r)['state'], 'STALE_TXN')


class WatchdogReadOnlyTest(unittest.TestCase):

    def test_watchdog_never_writes_anything(self):
        work, tmp = fresh_copy()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        before = tree_digest(work)
        for setup in (lambda: set_txn(work, True, age_h=4),
                      lambda: set_lock(work, True, age_h=3),
                      lambda: set_checkpoint_age(work, 30)):
            setup()
            dirty = tree_digest(work)
            r = run_watchdog(work)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertEqual(tree_digest(work), dirty,
                             'watchdog ĐÃ WRITE — vi phạm hợp đồng READ-ONLY')
        self.assertNotEqual(tree_digest(work), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
