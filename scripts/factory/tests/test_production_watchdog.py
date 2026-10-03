#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test AGENT #6 (production-watchdog.py) — hợp đồng production watchdog.

Hermetic: fixture dùng lại builder của test_repair_agent + stub
factory-operator ghi lại lời gọi; KHÔNG đụng production state, KHÔNG
sinh bài, KHÔNG chạy production cycle thật. Chứng minh hợp đồng spec:

  - <2h inactivity → KHÔNG hành động; >=2h → đủ điều kiện wake;
  - heartbeat/log/status check/run FAIL KHÔNG reset đồng hồ progress;
  - progress THẬT (writer claim, publish, hoàn tất chu kỳ, QA) reset;
  - #4 active / #5 active / maintenance_lock (kể cả stale) / pause chủ
    động / blocked chủ động / incident mở / writer active (lock, sentinel,
    hàng WRITING/QA/PASS/REPAIR, lease tươi) / publisher active /
    build-deploy active → KHÔNG hành động;
  - dry-run mặc định KHÔNG BAO GIỜ kích hoạt;
  - wake idempotent: cooldown chống 2 lần chạy tạo duplicate cycle;
  - wake chọn ĐÚNG MỘT entrypoint (factory-operator prepare-next),
    KHÔNG trực tiếp khởi động Writer #1/#2/#3.

Chạy: python3 scripts/factory/tests/test_production_watchdog.py
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(FACTORY))
PY = sys.executable
sys.path.insert(0, HERE)
import test_repair_agent as T                    # noqa: E402

BASE = '2026-10-03T15:00:00Z'     # "bây giờ" của watchdog
T0 = '2026-10-03T12:00:00Z'       # progress mặc định của fixture (3h trước)
FRESH = '2026-10-03T14:30:00Z'    # 30 phút trước (progress tươi)
OLD = '2026-10-01T00:00:00Z'


def iso_at(base, **kw):
    dt = datetime.datetime.strptime(base, '%Y-%m-%dT%H:%M:%SZ')
    return (dt + datetime.timedelta(**kw)).strftime('%Y-%m-%dT%H:%M:%SZ')


STUB_OPERATOR = (
    'import json, sys\n'
    'log = "data/state/stub-calls.jsonl"\n'
    'with open(log, "a", encoding="utf-8") as f:\n'
    '    f.write(json.dumps({"argv": sys.argv[1:]}) + "\\n")\n'
    'print("STUB_OPERATOR ok")\n'
    'sys.exit(0)\n'
)


def fixture6():
    root, tmp = T.fixture()
    # stub operator: ghi lại MỌI lời gọi để chứng minh entrypoint duy nhất
    with open(os.path.join(root, 'scripts/factory/factory-operator.py'),
              'w', encoding='utf-8') as f:
        f.write(STUB_OPERATOR)
    with open(os.path.join(root, 'data/state/stub-calls.jsonl'), 'w',
              encoding='utf-8') as f:
        f.write('')
    return root, tmp


def run6(root, *args, now=BASE):
    return subprocess.run(
        [PY, 'scripts/factory/production-watchdog.py', '--root', root,
         '--now', now] + list(args),
        cwd=REPO, capture_output=True, text=True, timeout=60)


def wj(root, rel, obj):
    return T.wj(root, rel, obj)


def rj(root, rel):
    return T.rj(root, rel)


def state_of(r):
    line = [ln for ln in r.stdout.splitlines()
            if ln.startswith('WATCHDOG_JSON: ')]
    assert line, 'thiếu WATCHDOG_JSON: %r %r' % (r.stdout, r.stderr)
    return json.loads(line[0].split(': ', 1)[1])


def stub_calls(root):
    path = os.path.join(root, 'data/state/stub-calls.jsonl')
    with open(path, encoding='utf-8') as f:
        return [json.loads(ln) for ln in f if ln.strip()]


class WatchdogContractTest(unittest.TestCase):

    def setUp(self):
        self.root, self.tmp = fixture6()
        self.before = T.make_sentinels(self.root)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    # ------------------------------------------------ inactivity contract

    def test_under_2h_no_action(self):
        cp = rj(self.root, 'data/state/checkpoint.json')
        cp['updated_at'] = FRESH
        wj(self.root, 'data/state/checkpoint.json', cp)
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'none')
        self.assertFalse(st['eligible'])
        self.assertEqual(st['inactivity_hours'], 0.5)

    def test_exactly_2h_eligible(self):
        cp = rj(self.root, 'data/state/checkpoint.json')
        cp['updated_at'] = iso_at(BASE, hours=-2)   # đúng 2h
        wj(self.root, 'data/state/checkpoint.json', cp)
        r = run6(self.root)
        st = state_of(r)
        self.assertTrue(st['eligible'])
        self.assertEqual(st['action'], 'would-wake')
        self.assertEqual(st['inactivity_hours'], 2.0)

    def test_heartbeat_and_status_do_not_reset(self):
        # progress cũ 3h; các file "hoạt động" khác đều mới — KHÔNG tính
        wj(self.root, 'data/state/maintenance-lock.json', {
            'locked': False, 'updated_at': FRESH})
        wj(self.root, 'data/state/diagnostics.json', {
            'updated_at': FRESH, 'note': 'status check gần đây'})
        wj(self.root, 'reports/factory/status.md', 'status lúc %s' % FRESH)
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'would-wake')
        self.assertEqual(st['last_valid_progress_at'], T0)

    def test_failed_run_does_not_reset(self):
        txn = rj(self.root, 'data/state/transaction.json')
        txn['history'] = [{'article_id': 'BLG-00001',
                           'result': 'FAILED',
                           'finished_at': FRESH}]
        wj(self.root, 'data/state/transaction.json', txn)
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'would-wake')
        self.assertEqual(st['last_valid_progress_at'], T0)

    def test_watchdog_marker_is_not_progress(self):
        # marker wake 1.5h trước: KHÔNG reset đồng hồ (inactivity vẫn
        # tính từ progress thật T0 = 3h); chỉ wake_cooldown chặn.
        wj(self.root, 'data/state/watchdog-wake.json', {
            'last_wake_at': iso_at(BASE, minutes=-90), 'wake_count': 1})
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'none')
        self.assertIn('wake_cooldown', st['reason'])
        self.assertEqual(st['last_valid_progress_at'], T0)
        self.assertEqual(st['inactivity_hours'], 3.0)

    def test_writer_claim_progress_resets(self):
        wj(self.root, 'data/state/writer-claims.json', {
            'schema_version': '1', 'updated_at': FRESH,
            'leases': {'W1': {'ids': ['BLG-00001'],
                              'claimed_at': FRESH,
                              'expires_at': OLD}}})   # lease đã chết
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'none')

    def test_publish_progress_resets(self):
        txn = rj(self.root, 'data/state/transaction.json')
        txn['history'] = [{'article_id': 'BLG-00001',
                           'result': 'PUBLISHED',
                           'finished_at': FRESH}]
        wj(self.root, 'data/state/transaction.json', txn)
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'none')
        self.assertEqual(st['last_valid_progress_at'], FRESH)

    def test_completed_cycle_progress_resets(self):
        cp = rj(self.root, 'data/state/checkpoint.json')
        cp['updated_at'] = FRESH
        wj(self.root, 'data/state/checkpoint.json', cp)
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'none')

    def test_qa_evidence_progress_resets(self):
        wj(self.root, 'data/qa/BLG-00001.json', {
            'article_id': 'BLG-00001', 'scored_at': FRESH})
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'none')

    def test_no_progress_signals_no_wake(self):
        os.remove(os.path.join(self.root, 'data/state/checkpoint.json'))
        wj(self.root, 'data/state/writer-claims.json', {
            'schema_version': '1', 'leases': {}})
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'none')
        self.assertIsNone(st['last_valid_progress_at'])

    # ------------------------------------------------------ guard contract

    def assert_no_action(self, reason_key):
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'none', st['reason'])
        self.assertIn(reason_key, st['reason'])
        self.assertEqual(stub_calls(self.root), [])

    def test_agent4_active_no_action(self):
        wj(self.root, 'data/state/maintenance-lock.json', {
            'locked': True, 'holder': 'agent-4',
            'incident_id': 'INC-20261003-a',
            'expires_at': iso_at(BASE, hours=+6)})
        self.assert_no_action('agent4_active')

    def test_agent5_active_no_action(self):
        wj(self.root, 'data/state/maintenance-lock.json', {
            'locked': True, 'holder': 'agent-5',
            'incident_id': 'INC-20261003-a',
            'expires_at': iso_at(BASE, hours=+6)})
        self.assert_no_action('agent5_active')

    def test_stale_maintenance_lock_no_action(self):
        # lock hết hạn NHƯNG vẫn locked=true: watchdog KHÔNG bypass lock
        wj(self.root, 'data/state/maintenance-lock.json', {
            'locked': True, 'holder': 'agent-4',
            'incident_id': 'INC-20261003-a', 'expires_at': OLD})
        self.assert_no_action('maintenance_lock')

    def test_open_incident_no_action(self):
        os.makedirs(os.path.join(self.root, 'data/state/incidents'),
                    exist_ok=True)
        wj(self.root, 'data/state/incidents/INC-20261003-stopped.json', {
            'incident_id': 'INC-20261003-stopped', 'status': 'stopped'})
        self.assert_no_action('open_incident')

    def test_closed_incident_allows_wake(self):
        os.makedirs(os.path.join(self.root, 'data/state/incidents'),
                    exist_ok=True)
        wj(self.root, 'data/state/incidents/INC-20261003-ok.json', {
            'incident_id': 'INC-20261003-ok', 'status': 'recovered'})
        r = run6(self.root)
        st = state_of(r)
        self.assertEqual(st['action'], 'would-wake')

    def test_intentional_pause_no_action(self):
        wj(self.root, 'data/factory/production-control.json',
           {'enabled': False, 'chunk_size': 2})
        self.assert_no_action('intentional_pause')

    def test_intentional_blocked_no_action(self):
        cp = rj(self.root, 'data/state/checkpoint.json')
        cp['status'] = 'BLOCKED'
        cp['updated_at'] = T0
        wj(self.root, 'data/state/checkpoint.json', cp)
        self.assert_no_action('intentional_blocked')

    def test_active_writer_lock_no_action(self):
        T.set_writer_lock(self.root, True, expires_at=iso_at(BASE, hours=+1))
        self.assert_no_action('writer_lock_held')

    def test_writer_lock_sentinel_no_action(self):
        open(os.path.join(self.root, 'data/state/writer-lock.active'),
             'w').close()
        self.assert_no_action('writer_lock_sentinel')

    def test_active_matrix_rows_no_action(self):
        rows = T.MATRIX_CSV.strip().splitlines()
        rows[1] = rows[1].replace('PLANNED', 'WRITING')
        with open(os.path.join(self.root, 'data/content-matrix.csv'), 'w',
                  encoding='utf-8') as f:
            f.write('\n'.join(rows) + '\n')
        self.assert_no_action('active_matrix_rows')

    def test_fresh_writer_lease_no_action(self):
        wj(self.root, 'data/state/writer-claims.json', {
            'schema_version': '1', 'updated_at': T0,
            'leases': {'W3': {'ids': ['BLG-00001'], 'claimed_at': T0,
                              'expires_at': iso_at(BASE, hours=+24)}}})
        self.assert_no_action('fresh_writer_lease')

    def test_publisher_active_no_action(self):
        txn = rj(self.root, 'data/state/transaction.json')
        txn['active'] = True
        txn['pending'] = {'article_id': 'BLG-00001', 'step': 'promote'}
        wj(self.root, 'data/state/transaction.json', txn)
        self.assert_no_action('publisher_active')

    def test_build_deploy_active_no_action(self):
        wj(self.root, 'data/state/deploy-active.json', {'active': True})
        self.assert_no_action('build_deploy_active')

    # ------------------------------------------------ wake contract

    def test_dry_run_default_never_invokes(self):
        r = run6(self.root)          # KHÔNG --wake
        st = state_of(r)
        self.assertEqual(st['action'], 'would-wake')
        self.assertEqual(stub_calls(self.root), [])   # KHÔNG gọi entrypoint
        self.assertFalse(os.path.exists(
            os.path.join(self.root, 'data/state/watchdog-wake.json')))

    def test_wake_single_entrypoint_no_direct_writers(self):
        claims_before = rj(self.root, 'data/state/writer-claims.json')
        r = run6(self.root, '--wake')
        st = state_of(r)
        self.assertEqual(st['action'], 'wake')
        self.assertEqual(st['wake_exit'], 0)
        calls = stub_calls(self.root)
        self.assertEqual(len(calls), 1)              # ĐÚNG MỘT lần
        self.assertEqual(calls[0]['argv'], ['prepare-next'])  # entrypoint
        # KHÔNG đụng writer claims / queue trực tiếp
        self.assertEqual(rj(self.root, 'data/state/writer-claims.json'),
                         claims_before)
        self.assertEqual(T.digests(self.root), self.before)
        mk = rj(self.root, 'data/state/watchdog-wake.json')
        self.assertEqual(mk['wake_count'], 1)
        self.assertEqual(mk['entrypoint'],
                         'scripts/factory/factory-operator.py prepare-next')

    def test_wake_idempotent_no_duplicate_cycle(self):
        self.assertEqual(run6(self.root, '--wake').returncode, 0)
        # lần 2 ngay sau đó (progress KHÔNG đổi, wake không phải progress)
        # -> cooldown chặn duplicate
        r2 = run6(self.root, '--wake')
        st2 = state_of(r2)
        self.assertEqual(st2['action'], 'none')
        self.assertIn('wake_cooldown', st2['reason'])
        self.assertEqual(len(stub_calls(self.root)), 1)
        mk = rj(self.root, 'data/state/watchdog-wake.json')
        self.assertEqual(mk['wake_count'], 1)
        # sau khi cooldown hết (2h sau wake) MÀ VẪN không progress -> được
        # wake lại (đúng: cycle chưa tạo progress)
        later = iso_at(BASE, hours=+3)
        r3 = run6(self.root, '--wake', now=later)
        st3 = state_of(r3)
        self.assertEqual(st3['action'], 'wake')
        self.assertEqual(len(stub_calls(self.root)), 2)
        mk2 = rj(self.root, 'data/state/watchdog-wake.json')
        self.assertEqual(mk2['wake_count'], 2)

    def test_wake_blocked_when_guard_appears_between_runs(self):
        r = run6(self.root)          # dry-run: would-wake
        self.assertEqual(state_of(r)['action'], 'would-wake')
        # guard xuất hiện (maintenance-lock) -> wake thật bị chặn
        wj(self.root, 'data/state/maintenance-lock.json', {
            'locked': True, 'holder': 'agent-4',
            'incident_id': 'INC-20261003-z',
            'expires_at': iso_at(BASE, hours=+6)})
        r2 = run6(self.root, '--wake')
        st2 = state_of(r2)
        self.assertEqual(st2['action'], 'none')
        self.assertEqual(stub_calls(self.root), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
