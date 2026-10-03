#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration test hợp đồng chéo Agent #4 / #5 / #6 (STEP 4).

Chứng minh TOÀN BỘ hợp đồng cross-agent trên MỘT fixture:

  - #4 -> #5 là path escalation repair DUY NHẤT; sau #5 không còn
    lượt tự trị nào (tổng tối đa 2 attempts/incident);
  - #6 KHÔNG BAO GIỜ repair; KHÔNG wake khi #4/#5 active;
  - cùng một thời điểm chỉ MỘT agent mutate hạ tầng;
  - maintenance lock KHÔNG bị bypass (kể cả khi stale);
  - stale-lock handling an toàn + tường minh (--force-stale);
  - wake idempotent: hai lần watchdog KHÔNG tạo duplicate cycle;
  - writer vẫn content-only, factory-publish.yml vẫn publisher DUY NHẤT;
  - KHÔNG test nào sinh/publish bài thật.

Chạy: python3 scripts/factory/tests/test_agent_integration.py
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
import test_supervisor_agent as S5               # noqa: E402
import test_production_watchdog as S6            # noqa: E402

NOW = T.NOW
LATER = T.FUTURE
WAKE_NOW = S6.BASE            # 15:00Z — progress fixture T0=12:00 (3h)


def fixtureI():
    """Fixture đầy đủ: engine thật + stub operator ghi lời gọi."""
    root, tmp = S5.fixture5()          # + supervisor + 5 workflow stub
    with open(os.path.join(root, 'scripts/factory/factory-operator.py'),
              'w', encoding='utf-8') as f:
        f.write(S6.STUB_OPERATOR)
    with open(os.path.join(root, 'data/state/stub-calls.jsonl'), 'w',
              encoding='utf-8') as f:
        f.write('')
    return root, tmp


def rj(root, rel):
    return T.rj(root, rel)


def escalation_fixture(root):
    """Incident đã chạy hết chuỗi: #4 ESCALATE -> #5 STOP (1 attempt mỗi
    agent). Trả (incident_id, incident)."""
    T.set_writer_lock(root, True, expires_at=LATER)
    inc = 'INC-20261003-full'
    T.start_ok(root, inc)
    r4 = T.repair(root, inc, 'release-stale-writer-lock')
    assert 'ESCALATE' in r4.stdout
    assert S5.run5(root, 'take', '--incident-id', inc).returncode == 0
    r5 = S5.run5(root, 'repair', '--incident-id', inc, '--action',
                 'release-stale-writer-lock')
    assert 'STOP' in r5.stdout
    return inc, rj(root, 'data/state/incidents/%s.json' % inc)


class AgentIntegrationContractTest(unittest.TestCase):

    def setUp(self):
        self.root, self.tmp = fixtureI()
        self.before = T.make_sentinels(self.root)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    # ------------------------------------------- escalation path duy nhất

    def test_4_to_5_only_escalation_total_two_attempts(self):
        inc, data = escalation_fixture(self.root)
        a4, a5 = data['agent4'], data['agent5']
        self.assertEqual(a4['attempts'], 1)
        self.assertEqual(a5['attempts'], 1)
        self.assertEqual(a4['attempts'] + a5['attempts'], 2)   # TỔNG = 2
        # KHÔNG còn lượt nào: #4 repair REFUSED, #5 repair REFUSED
        r4b = T.repair(self.root, inc, 'release-stale-writer-lock')
        self.assertEqual(r4b.returncode, 1)
        r5b = S5.run5(self.root, 'repair', '--incident-id', inc, '--action',
                      'release-stale-writer-lock')
        self.assertEqual(r5b.returncode, 1)
        r5c = S5.run5(self.root, 'repair', '--incident-id', inc, '--action',
                      'prune-writer-claims')
        self.assertEqual(r5c.returncode, 1)
        data2 = rj(self.root, 'data/state/incidents/%s.json' % inc)
        self.assertEqual(data2['agent4']['attempts'], 1)
        self.assertEqual(data2['agent5']['attempts'], 1)
        # incident vẫn pause (chưa giải quyết xong)
        self.assertTrue(rj(self.root,
                           'data/state/maintenance-lock.json')['locked'])
        self.assertEqual(T.digests(self.root), self.before)

    def test_only_one_agent_mutates_at_a_time(self):
        T.set_writer_lock(self.root, True, expires_at=T.PAST)
        inc = 'INC-20261003-mutex'
        T.start_ok(self.root, inc)
        # holder=agent-4: #5 bị từ chối mutate
        r5 = S5.run5(self.root, 'repair', '--incident-id', inc, '--action',
                     'release-stale-writer-lock')
        self.assertEqual(r5.returncode, 1)
        self.assertIn('holder=agent-4', r5.stdout)
        T.repair(self.root, inc, 'release-stale-writer-lock')   # #4 SUCCESS
        # handoff: trong SUỐT quá trình holder chỉ là agent-4 rồi agent-5
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertEqual(lk['holder'], 'agent-4')
        S5.run5(self.root, 'take', '--incident-id', inc)
        lk2 = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertEqual(lk2['holder'], 'agent-5')
        self.assertEqual(lk2['incident_id'], inc)   # CÙNG incident_id
        # holder=agent-5: #4 bị từ chối mutate
        r4 = T.repair(self.root, inc, 'release-stale-writer-lock')
        self.assertEqual(r4.returncode, 1)
        self.assertIn('holder=agent-5', r4.stdout)

    def test_lock_not_bypassed_even_after_stop(self):
        inc, _ = escalation_fixture(self.root)
        # trả lại operator THẬT để chứng minh pause có hiệu lực
        shutil.copy2(os.path.join(FACTORY, 'factory-operator.py'),
                     os.path.join(self.root, 'scripts/factory',
                                  'factory-operator.py'))
        # incident STOP: lock vẫn giữ -> operator từ chối mutate thật
        op = subprocess.run([PY, 'scripts/factory/factory-operator.py',
                             'prepare-next'], cwd=self.root,
                            capture_output=True, text=True, timeout=60)
        self.assertEqual(op.returncode, 1)
        self.assertIn('maintenance-lock', op.stdout)
        # watchdog cũng KHÔNG wake khi lock còn (kể cả paused Incident)
        r = S6.run6(self.root, '--wake', now=WAKE_NOW)
        st = S6.state_of(r)
        self.assertEqual(st['action'], 'none')
        self.assertEqual(S6.stub_calls(self.root), [])

    def test_stale_lock_takeover_explicit(self):
        T.start_ok(self.root, 'INC-20261003-old')
        # lock hết TTL nhưng vẫn locked: KHÔNG ai được giành lại âm thầm
        r4 = T.run4(self.root, 'start', '--incident-id', 'INC-20261003-new',
                    '--trigger', 'sự cố mới', now=LATER)
        self.assertEqual(r4.returncode, 1)
        self.assertIn('force-stale', r4.stdout)
        # watchdog cũng KHÔNG coi stale lock là idle
        r6 = S6.run6(self.root, now=WAKE_NOW)
        st = S6.state_of(r6)
        self.assertEqual(st['action'], 'none')
        self.assertIn('maintenance_lock', st['reason'])
        # takeover tường minh -> ghi dấu stale_takeover
        r4b = T.run4(self.root, 'start', '--incident-id', 'INC-20261003-new',
                     '--trigger', 'sự cố mới', '--force-stale', now=LATER)
        self.assertEqual(r4b.returncode, 0)
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertEqual(lk['incident_id'], 'INC-20261003-new')
        self.assertEqual(lk['stale_takeover']['incident_id'], 'INC-20261003-old')

    # ------------------------------------------------------ #6 contract

    def test_watchdog_never_repairs_only_wakes(self):
        # #6 KHÔNG repair: wake chỉ gọi entrypoint; TOÀN BỘ state khác
        # byte-identical (riêng writer-lock treo thì #6 DO NOTHING —
        # guard active writer, repair là việc của #4/#5)
        before_state = self._state_bytes()
        r = S6.run6(self.root, '--wake', now=WAKE_NOW)
        st = S6.state_of(r)
        self.assertEqual(st['action'], 'wake')
        calls = S6.stub_calls(self.root)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['argv'], ['prepare-next'])  # chỉ entrypoint
        # không incident nào được #6 tạo ra
        inc_dir = os.path.join(self.root, 'data/state/incidents')
        self.assertFalse(os.path.isdir(inc_dir)
                         and os.listdir(inc_dir))  # không incident
        self.assertEqual(T.digests(self.root), self.before)
        # KHÔNG file state nào khác bị #6 đụng (chỉ wake marker)
        self.assertEqual(self._state_bytes(exclude_wake=True),
                         before_state)
        # riêng writer-lock treo: #6 DO NOTHING (guard), không repair
        T.set_writer_lock(self.root, True, expires_at=T.PAST)
        T.wj(self.root, 'data/state/stub-calls.jsonl', None)  # noqa
        with open(os.path.join(self.root, 'data/state/stub-calls.jsonl'),
                  'w', encoding='utf-8') as f:
            f.write('')
        r2 = S6.run6(self.root, '--wake', now=WAKE_NOW)
        st2 = S6.state_of(r2)
        self.assertEqual(st2['action'], 'none')
        self.assertIn('writer_lock_held', st2['reason'])
        self.assertEqual(S6.stub_calls(self.root), [])
        wl2 = rj(self.root, 'data/state/writer-lock.json')
        self.assertTrue(wl2['locked'])   # KHÔNG repair — việc của #4

    def _state_bytes(self, exclude_wake=False):
        out = {}
        state_dir = os.path.join(self.root, 'data/state')
        for name in sorted(os.listdir(state_dir)):
            # wake marker là output chủ đích của #6; stub-calls.jsonl là
            # log operator của fixture (lời gọi wake đã assert riêng ở
            # trên) — cả hai không phải state factory bị #6 đụng
            if name == 'watchdog-wake.json' and exclude_wake:
                continue
            if name == 'stub-calls.jsonl':
                continue
            path = os.path.join(state_dir, name)
            if os.path.isfile(path):
                with open(path, 'rb') as f:
                    out[name] = f.read()
        return out

    def test_watchdog_wakes_only_after_everything_idle(self):
        inc, _ = escalation_fixture(self.root)   # lock còn giữ
        r1 = S6.run6(self.root, '--wake', now=WAKE_NOW)
        self.assertEqual(S6.state_of(r1)['action'], 'none')
        self.assertEqual(S6.stub_calls(self.root), [])
        # operator (người vận hành) xử lý xong: #5 nhả lock, incident đóng
        subprocess.run([PY, '-c',
                       'import sys; sys.path.insert(0, %r); '
                       'import maintenance as M; '
                       'M.release_lock(%r, M.AGENT5, %r, M.parse_iso(%r))'
                       % (os.path.join(self.root, 'scripts/factory'),
                          self.root, inc, T.PAST)], cwd=REPO)
        inc_data = rj(self.root, 'data/state/incidents/%s.json' % inc)
        inc_data['status'] = 'recovered'
        T.wj(self.root, 'data/state/incidents/%s.json' % inc, inc_data)
        # người vận hành xử lý dứt điểm: nhả writer-lock còn treo
        T.set_writer_lock(self.root, False)
        r2 = S6.run6(self.root, '--wake', now=WAKE_NOW)
        st2 = S6.state_of(r2)
        self.assertEqual(st2['action'], 'wake')   # giờ mới đủ điều kiện
        self.assertEqual(len(S6.stub_calls(self.root)), 1)

    def test_two_watchdog_invocations_no_duplicate(self):
        self.assertEqual(S6.run6(self.root, '--wake', now=WAKE_NOW).returncode, 0)
        self.assertEqual(S6.run6(self.root, '--wake', now=WAKE_NOW).returncode, 0)
        calls = S6.stub_calls(self.root)
        self.assertEqual(len(calls), 1)              # KHÔNG duplicate cycle
        self.assertEqual(calls[0]['argv'], ['prepare-next'])

    # ------------------------------------------ writer/coordinator contracts

    def test_writers_content_only_agents_never_publish(self):
        # whitelist action của #4/#5 KHÔNG bao giờ chạm nội dung
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'ra', os.path.join(FACTORY, 'repair-agent.py'))
        ra = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ra)
        for action in ra.ACTIONS:
            self.assertNotIn('publish', action)
            self.assertNotIn('qa', action)
            self.assertNotIn('promote', action)
            self.assertNotIn('post', action)
        self.assertNotIn('_posts', ra.ACTIONS)
        # entrypoint của #6 là op claim của operator, KHÔNG phải op
        # publisher (qa/publish chỉ chạy trong factory-publish.yml)
        self.assertEqual(S6_ENTRY(),
                         ['scripts/factory/factory-operator.py',
                          'prepare-next'])
        # factory-publish.yml vẫn là workflow DUY NHẤT được write
        wf_dir = os.path.join(REPO, '.github/workflows')
        writers = []
        for name in sorted(os.listdir(wf_dir)):
            with open(os.path.join(wf_dir, name), encoding='utf-8') as f:
                text = f.read()
            if 'contents: write' in text:
                writers.append(name)
        self.assertEqual(writers, ['factory-publish.yml'])

    def test_no_real_article_generated_anywhere(self):
        # toàn bộ chuỗi 3 agent + wake: KHÔNG sinh bài, KHÔNG claim,
        # KHÔNG publish, matrix nguyên vẹn
        inc, _ = escalation_fixture(self.root)
        S6.run6(self.root, '--wake', now=WAKE_NOW)   # bị chặn (lock) — an toàn
        S6.run6(self.root, now=WAKE_NOW)             # dry-run cũng bị chặn
        drafts = sorted(os.listdir(os.path.join(self.root, '_drafts')))
        posts = sorted(os.listdir(os.path.join(self.root, '_posts')))
        self.assertEqual(drafts, ['sentinel-draft.md'])
        self.assertEqual(posts, ['sentinel-post.md'])
        self.assertEqual(T.digests(self.root), self.before)
        txn = rj(self.root, 'data/state/transaction.json')
        self.assertFalse(txn['active'])
        self.assertEqual(txn['history'], [])


def S6_ENTRY():
    """Đọc ENTRYPOINT của production-watchdog từ repo thật (không import
    trực tiếp vì tên file có gạch nối)."""
    import ast
    path = os.path.join(FACTORY, 'production-watchdog.py')
    with open(path, encoding='utf-8') as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and getattr(node.targets[0], 'id', '') == 'ENTRYPOINT'):
            return [el.value for el in node.value.elts]
    raise AssertionError('thiếu ENTRYPOINT trong production-watchdog.py')


if __name__ == '__main__':
    unittest.main(verbosity=2)
