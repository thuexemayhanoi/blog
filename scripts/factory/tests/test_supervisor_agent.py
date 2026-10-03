#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test AGENT #5 (supervisor-agent.py) — hợp đồng second-line recovery.

Hermetic: fixture dùng lại builder của test_repair_agent (fixture nhỏ,
KHÔNG đụng production state, KHÔNG sinh bài, KHÔNG chạy production
cycle). Chứng minh hợp đồng spec Agent #5:

  1. #4 và #5 KHÔNG mutate đồng thời (holder lock cưỡng chế);
  2. #5 KHÔNG start khi thiếu handoff #4 hợp lệ (lock + result #4);
  3. CÙNG incident_id được giữ nguyên xuyên suốt #4 -> #5;
  4. #5 tối đa MỘT repair attempt mỗi incident;
  5. #5 unresolved → production CÒN PAUSE (lock giữ, checkpoint giữ);
  6. verify HEALTHY → nhả maintenance_lock, incident recovered/resumable;
  7. checkpoint được bảo toàn khi #5 dừng;
  8. KHÔNG file bài viết nào bị đổi (sentinel byte-identical);
  9. KHÔNG production cycle nào được test start.

Chạy: python3 scripts/factory/tests/test_supervisor_agent.py
"""
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

NOW = T.NOW
LATER = T.FUTURE        # writer-lock "còn tươi" ở NOW đã hết hạn ở LATER
WORKFLOWS = ('factory-publish.yml', 'factory-liveness.yml',
            'factory-publish-verify.yml', 'factory-soak.yml',
            'quality-gate.yml')


def fixture5():
    """Fixture của Agent #4 + supervisor-agent + stub 5 workflow."""
    root, tmp = T.fixture()
    shutil.copy2(os.path.join(FACTORY, 'supervisor-agent.py'),
                 os.path.join(root, 'scripts/factory/supervisor-agent.py'))
    for w in WORKFLOWS:
        path = os.path.join(root, '.github/workflows', w)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('# stub workflow (chỉ để verify checklist đếm)\n')
    return root, tmp


def run5(root, *args, now=NOW):
    return subprocess.run(
        [PY, 'scripts/factory/supervisor-agent.py', '--root', root,
         '--now', now] + list(args),
        cwd=REPO, capture_output=True, text=True, timeout=60)


def rj(root, rel):
    return T.rj(root, rel)


def cp_bytes(root):
    with open(os.path.join(root, 'data/state/checkpoint.json'), 'rb') as f:
        return f.read()


class SupervisorContractTest(unittest.TestCase):

    def setUp(self):
        self.root, self.tmp = fixture5()
        self.before = T.make_sentinels(self.root)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    # ------------------------------------------------- handoff contract

    def test_take_requires_completed_agent4(self):
        T.start_ok(self.root, 'INC-20261003-h1')   # mới start, chưa repair
        r = run5(self.root, 'take', '--incident-id', 'INC-20261003-h1')
        self.assertEqual(r.returncode, 1)
        self.assertIn('handoff KHÔNG hợp lệ', r.stdout)

    def test_take_requires_active_lock(self):
        # chu kỳ #4 -> #5 đã đóng (lock đã nhả) -> take lại REFUSED
        T.set_writer_lock(self.root, True, expires_at=T.PAST)
        T.start_ok(self.root, 'INC-20261003-h2')
        T.repair(self.root, 'INC-20261003-h2', 'release-stale-writer-lock')
        self.assertEqual(run5(self.root, 'take', '--incident-id',
                              'INC-20261003-h2').returncode, 0)
        self.assertEqual(run5(self.root, 'verify', '--incident-id',
                              'INC-20261003-h2').returncode, 0)
        r = run5(self.root, 'take', '--incident-id', 'INC-20261003-h2')
        self.assertEqual(r.returncode, 1)
        self.assertIn('KHÔNG active', r.stdout)

    def test_take_unknown_incident_refused(self):
        r = run5(self.root, 'take', '--incident-id', 'INC-20261003-none')
        self.assertEqual(r.returncode, 1)
        self.assertIn('REFUSED', r.stdout)

    def test_no_simultaneous_mutation(self):
        # khi holder vẫn là agent-4: #5 không được mutate
        T.set_writer_lock(self.root, True, expires_at=T.PAST)
        T.start_ok(self.root, 'INC-20261003-sim')
        r = run5(self.root, 'repair', '--incident-id', 'INC-20261003-sim',
                 '--action', 'release-stale-writer-lock')
        self.assertEqual(r.returncode, 1)
        self.assertIn('holder=agent-4', r.stdout)
        # sau take (holder=agent-5): #4 không được mutate nữa
        T.repair(self.root, 'INC-20261003-sim',
                 'release-stale-writer-lock')   # #4 SUCCESS
        r2 = run5(self.root, 'take', '--incident-id', 'INC-20261003-sim')
        self.assertEqual(r2.returncode, 0)
        self.assertIn('AGENT5_TAKE', r2.stdout)
        r3 = T.run4(self.root, 'repair', '--incident-id',
                    'INC-20261003-sim', '--action',
                    'release-stale-writer-lock')
        self.assertEqual(r3.returncode, 1)
        self.assertIn('holder=agent-5', r3.stdout)
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertEqual(lk['holder'], 'agent-5')   # không có #4 đè #5

    # --------------------------------------------------- SUCCESS -> verify

    def test_verify_healthy_releases_lock(self):
        T.set_writer_lock(self.root, True, expires_at=T.PAST)
        T.start_ok(self.root, 'INC-20261003-v1')
        T.repair(self.root, 'INC-20261003-v1', 'release-stale-writer-lock')
        self.assertEqual(run5(self.root, 'take', '--incident-id',
                              'INC-20261003-v1').returncode, 0)
        r = run5(self.root, 'verify', '--incident-id', 'INC-20261003-v1')
        self.assertEqual(r.returncode, 0)
        self.assertIn('HEALTHY', r.stdout)
        self.assertIn('RELEASED', r.stdout)
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertFalse(lk['locked'])
        self.assertEqual(lk['last_released_by'], 'agent-5')
        self.assertEqual(lk['last_released_incident'], 'INC-20261003-v1')
        inc = rj(self.root, 'data/state/incidents/INC-20261003-v1.json')
        self.assertEqual(inc['status'], 'recovered')
        self.assertFalse(inc['production_paused'])
        self.assertEqual(inc['incident_id'], 'INC-20261003-v1')  # giữ id
        self.assertEqual(inc['agent4']['result'], 'SUCCESS')
        self.assertEqual(inc['agent5']['verify'][0]['check'],
                         'repo-state:data/state/writer-lock.json')
        self.assertTrue(all(c['ok'] for c in inc['agent5']['verify']))
        # content + checkpoint nguyên vẹn
        self.assertEqual(T.digests(self.root), self.before)
        # operator đã chạy lại được (pause đã nhả)
        op = subprocess.run([PY, 'scripts/factory/factory-operator.py',
                             'status'], cwd=self.root,
                            capture_output=True, text=True, timeout=60)
        self.assertEqual(op.returncode, 0)

    def test_verify_unhealthy_keeps_pause_attention(self):
        T.set_writer_lock(self.root, True, expires_at=T.PAST)
        T.start_ok(self.root, 'INC-20261003-v2')
        T.repair(self.root, 'INC-20261003-v2', 'release-stale-writer-lock')
        run5(self.root, 'take', '--incident-id', 'INC-20261003-v2')
        # trạng thái vẫn hỏng ở một nơi #4 không chạm: counts lệch
        cp = rj(self.root, 'data/state/checkpoint.json')
        cp['counts'] = dict(cp['counts'], planned=99)
        T.wj(self.root, 'data/state/checkpoint.json', cp)
        before_cp = cp_bytes(self.root)
        r = run5(self.root, 'verify', '--incident-id', 'INC-20261003-v2')
        self.assertEqual(r.returncode, 0)
        self.assertIn('UNHEALTHY', r.stdout)
        self.assertIn('attention', r.stdout)
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertTrue(lk['locked'])          # pause GIỮ
        self.assertEqual(lk['holder'], 'agent-5')
        inc = rj(self.root, 'data/state/incidents/INC-20261003-v2.json')
        self.assertEqual(inc['status'], 'attention')
        self.assertTrue(inc['production_paused'])
        # report người đọc được
        rp = os.path.join(self.root, 'reports/factory/incidents',
                          'INC-20261003-v2.md')
        self.assertTrue(os.path.exists(rp))
        with open(rp, encoding='utf-8') as f:
            text = f.read()
        self.assertIn('INC-20261003-v2', text)
        # checkpoint được GIỮ NGUYÊN (#5 verify không sửa gì)
        self.assertEqual(cp_bytes(self.root), before_cp)
        self.assertEqual(T.digests(self.root), self.before)
        # operator vẫn từ chối mutate (pause chưa nhả)
        op = subprocess.run([PY, 'scripts/factory/factory-operator.py',
                             'prepare-next'], cwd=self.root,
                            capture_output=True, text=True, timeout=60)
        self.assertEqual(op.returncode, 1)
        self.assertIn('maintenance-lock', op.stdout)

    # ------------------------------------------------- ESCALATE -> repair

    def test_escalate_repair_success_resumable(self):
        # #4 ESCALATE vì writer-lock còn tươi tại NOW
        T.set_writer_lock(self.root, True, expires_at=LATER)
        T.start_ok(self.root, 'INC-20261003-e1')
        r4 = T.repair(self.root, 'INC-20261003-e1',
                      'release-stale-writer-lock')
        self.assertIn('ESCALATE', r4.stdout)
        # #5 take + repair tại LATER (lock đã hết hạn -> sửa được)
        self.assertEqual(run5(self.root, 'take', '--incident-id',
                              'INC-20261003-e1').returncode, 0)
        r = run5(self.root, 'repair', '--incident-id', 'INC-20261003-e1',
                 '--action', 'release-stale-writer-lock', now=LATER)
        self.assertEqual(r.returncode, 0)
        self.assertIn('RESUMABLE', r.stdout)
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertFalse(lk['locked'])
        inc = rj(self.root, 'data/state/incidents/INC-20261003-e1.json')
        self.assertEqual(inc['status'], 'resumable')
        self.assertEqual(inc['agent4']['result'], 'ESCALATE')
        self.assertEqual(inc['agent5']['attempts'], 1)
        self.assertEqual(inc['agent5']['result'], 'RESUMABLE')
        self.assertEqual(inc['agent5']['actions'][0]['action'],
                         'release-stale-writer-lock')
        self.assertEqual(T.digests(self.root), self.before)

    def test_escalate_repair_refused_stops(self):
        # lock VẪN tươi tại NOW -> #5 action refuse -> STOP giữ pause
        T.set_writer_lock(self.root, True, expires_at=LATER)
        T.start_ok(self.root, 'INC-20261003-e2')
        r4 = T.repair(self.root, 'INC-20261003-e2',
                      'release-stale-writer-lock')
        self.assertIn('ESCALATE', r4.stdout)
        before_cp = cp_bytes(self.root)
        self.assertEqual(run5(self.root, 'take', '--incident-id',
                              'INC-20261003-e2').returncode, 0)
        r = run5(self.root, 'repair', '--incident-id', 'INC-20261003-e2',
                 '--action', 'release-stale-writer-lock')
        self.assertEqual(r.returncode, 0)
        self.assertIn('STOP', r.stdout)
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertTrue(lk['locked'])                 # pause GIỮ
        inc = rj(self.root, 'data/state/incidents/INC-20261003-e2.json')
        self.assertEqual(inc['status'], 'stopped')
        self.assertTrue(inc['production_paused'])
        self.assertEqual(inc['agent5']['attempts'], 1)
        self.assertEqual(inc['agent5']['result'], 'STOPPED')
        # checkpoint + kết quả recoverable của writer GIỮ NGUYÊN
        self.assertEqual(cp_bytes(self.root), before_cp)
        wl = rj(self.root, 'data/state/writer-lock.json')
        self.assertTrue(wl['locked'])   # không force unlock lock tươi
        rp = os.path.join(self.root, 'reports/factory/incidents',
                          'INC-20261003-e2.md')
        self.assertTrue(os.path.exists(rp))
        self.assertEqual(T.digests(self.root), self.before)

    def test_one_attempt_agent5(self):
        T.set_writer_lock(self.root, True, expires_at=LATER)
        T.start_ok(self.root, 'INC-20261003-e3')
        T.repair(self.root, 'INC-20261003-e3', 'release-stale-writer-lock')
        run5(self.root, 'take', '--incident-id', 'INC-20261003-e3')
        r1 = run5(self.root, 'repair', '--incident-id', 'INC-20261003-e3',
                  '--action', 'release-stale-writer-lock')
        self.assertIn('STOP', r1.stdout)
        # attempt 2 -> REFUSED (không retry tự trị)
        r2 = run5(self.root, 'repair', '--incident-id', 'INC-20261003-e3',
                  '--action', 'release-stale-writer-lock')
        self.assertEqual(r2.returncode, 1)
        self.assertIn('đã dùng hết MỘT attempt', r2.stdout)
        inc = rj(self.root, 'data/state/incidents/INC-20261003-e3.json')
        self.assertEqual(inc['agent5']['attempts'], 1)   # không tăng

    def test_repair_refused_when_agent4_success(self):
        # #4=SUCCESS -> #5 KHÔNG được repair thêm (chỉ verify)
        T.set_writer_lock(self.root, True, expires_at=T.PAST)
        T.start_ok(self.root, 'INC-20261003-e4')
        T.repair(self.root, 'INC-20261003-e4', 'release-stale-writer-lock')
        run5(self.root, 'take', '--incident-id', 'INC-20261003-e4')
        r = run5(self.root, 'repair', '--incident-id', 'INC-20261003-e4',
                 '--action', 'prune-writer-claims')
        self.assertEqual(r.returncode, 1)
        self.assertIn('chỉ dành cho incident #4=ESCALATE', r.stdout)
        inc = rj(self.root, 'data/state/incidents/INC-20261003-e4.json')
        self.assertEqual(inc['agent5']['attempts'], 0)   # không mutate

    def test_no_production_cycle_started(self):
        """Toàn bộ chu kỳ #4->#5 KHÔNG sinh bài, KHÔNG claim, KHÔNG txn."""
        T.set_writer_lock(self.root, True, expires_at=T.PAST)
        T.start_ok(self.root, 'INC-20261003-np')
        T.repair(self.root, 'INC-20261003-np', 'release-stale-writer-lock')
        run5(self.root, 'take', '--incident-id', 'INC-20261003-np')
        run5(self.root, 'verify', '--incident-id', 'INC-20261003-np')
        txn = rj(self.root, 'data/state/transaction.json')
        self.assertFalse(txn['active'])
        self.assertEqual(txn['history'], [])
        claims = rj(self.root, 'data/state/writer-claims.json')
        self.assertEqual(claims['leases'], {})
        drafts = os.listdir(os.path.join(self.root, '_drafts'))
        posts = os.listdir(os.path.join(self.root, '_posts'))
        self.assertEqual(sorted(drafts), ['sentinel-draft.md'])
        self.assertEqual(sorted(posts), ['sentinel-post.md'])
        self.assertEqual(T.digests(self.root), self.before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
