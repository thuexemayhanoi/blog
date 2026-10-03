#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test AGENT #4 (repair-agent.py + maintenance.py) — hợp đồng dòng đầu.

Hermetic: mọi test chạy trên fixture nhỏ trong thư mục tạm; KHÔNG đụng
production state của repository thật; KHÔNG sinh/sửa bài viết; KHÔNG
chạy production cycle. Chứng minh hợp đồng spec Agent #4:

  1. không mutate được khi chưa giữ maintenance_lock;
  2. không giành lock chồng lấn (incident khác / lock tươi);
  3. một incident chỉ được MỘT repair attempt #4 (không retry tự trị);
  4. file writer/content KHÔNG BAO GIỜ bị #4 sửa (sentinel byte-identical);
  5. SUCCESS/ESCALATE được persist đầy đủ vào incident JSON (audit);
  6. factory-operator từ chối op mutating khi maintenance-lock active;
  7. action gặp trạng thái không an toàn -> ESCALATE (không force);
  8. stale takeover phải --force-stale rõ ràng (không âm thầm bypass);
  9. mọi action whitelist là deterministic + chỉ đụng data/state/**.

Chạy: python3 scripts/factory/tests/test_repair_agent.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(FACTORY))
PY = sys.executable

NOW = '2026-10-03T12:00:00Z'
T_PLUS = '2026-10-03T18:00:00Z'   # > TTL 6h: lock cũ đã stale
PAST = '2026-10-01T00:00:00Z'     # writer-lock đã hết hạn từ lâu
FUTURE = '2026-10-04T00:00:00Z'   # writer-lock còn tươi

MATRIX_CSV = (
    'id,status,title,intent,primary_keyword,expected_url,slug,'
    'repair_count,notes\n'
    'BLG-00001,PLANNED,Tiêu đề 1,informative,từ khóa 1,/blog/a/,a,0,\n'
    'BLG-00002,PLANNED,Tiêu đề 2,informative,từ khóa 2,/blog/b/,b,0,\n'
    'BLG-00003,PUBLISHED,Tiêu đề 3,informative,từ khóa 3,/blog/c/,c,0,\n'
)


def fixture():
    """Root fixture tối tiểu: engine chuẩn + state hỏng có kiểm soát."""
    tmp = tempfile.mkdtemp(prefix='agent4-')
    root = os.path.join(tmp, 'repo')
    for rel in ('scripts/factory', 'scripts/factory/tests',
                'data/state', 'data/factory', 'data/qa',
                '_drafts', '_posts', 'reports/factory/incidents'):
        os.makedirs(os.path.join(root, rel), exist_ok=True)
    for name in ('maintenance.py', 'repair-agent.py',
                 'factory-operator.py', 'writer-claim.py',
                 'publish-gate.py'):
        shutil.copy2(os.path.join(FACTORY, name),
                     os.path.join(root, 'scripts/factory', name))
    # validate.py stub: exit 1 khi marker tồn tại (điều khiển test ESCALATE)
    with open(os.path.join(root, 'scripts/factory/validate.py'), 'w',
              encoding='utf-8') as f:
        f.write('import os, sys\n'
                'sys.exit(1 if os.path.exists("data/state/validate-fail")'
                ' else 0)\n')
    with open(os.path.join(root, 'data/content-matrix.csv'), 'w',
              encoding='utf-8') as f:
        f.write(MATRIX_CSV)
    wj(root, 'data/factory/production-control.json',
       {'enabled': True, 'chunk_size': 2})
    # business-facts tối tiểu để factory-operator load được whitelist giá
    wj(root, 'data/business-facts.json', {
        'approved_pricing': {'Xe fixture': {'day': 100000}},
        'forbidden_claims': [], 'content_rules': []})
    wj(root, 'data/state/maintenance-lock.json', {
        'locked': False, 'holder': None, 'incident_id': None,
        'acquired_at': None, 'expires_at': None, 'updated_at': NOW,
        'note': 'chua tung lock'})
    wj(root, 'data/state/transaction.json', {
        'active': False, 'updated_at': NOW, 'pending': None, 'history': []})
    wj(root, 'data/state/checkpoint.json', {
        'factory_version': 2, 'updated_at': NOW,
        'next_claimable_id': 'BLG-00001',
        'last_completed_article_id': None, 'in_progress_chunk': None,
        'counts': {'planned': 2, 'published': 1, 'writing': 0, 'qa': 0,
                   'pass': 0, 'repair': 0, 'blocked': 0, 'fail': 0}})
    wj(root, 'data/state/writer-claims.json', {
        'schema_version': '1', 'updated_at': NOW, 'leases': {}})
    set_writer_lock(root, False)
    return root, tmp


def wj(root, rel, obj):
    path = os.path.join(root, rel)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def rj(root, rel):
    with open(os.path.join(root, rel), encoding='utf-8') as f:
        return json.load(f)


def set_writer_lock(root, locked, expires_at=None, holder='W1'):
    wj(root, 'data/state/writer-lock.json', {
        'locked': locked,
        'holder': holder if locked else None,
        'token': 'tok-1' if locked else None,
        'acquired_at': NOW if locked else None,
        'expires_at': expires_at,
        'updated_at': NOW,
        'note': ''})


def run4(root, *args, now=NOW):
    return subprocess.run(
        [PY, 'scripts/factory/repair-agent.py', '--root', root,
         '--now', now] + list(args),
        cwd=REPO, capture_output=True, text=True, timeout=60)


def start_ok(root, inc, trigger='watchdog STALE_WRITER_LOCK'):
    r = run4(root, 'start', '--incident-id', inc, '--trigger', trigger)
    assert r.returncode == 0 and 'AGENT4_START' in r.stdout, \
        'start phải thành công: %s %s' % (r.stdout, r.stderr)
    return r


def repair(root, inc, action, **kw):
    args = ['repair', '--incident-id', inc, '--action', action]
    if kw.get('skip_tests'):
        args.append('--skip-tests')
    return run4(root, *args, now=kw.get('now', NOW))


def digests(root):
    """Hash vùng writer/content — #4 KHÔNG BAO GIỜ được làm đổi."""
    out = {}
    for rel in ('_drafts/sentinel-draft.md', '_posts/sentinel-post.md',
                'data/content-matrix.csv'):
        path = os.path.join(root, rel)
        with open(path, 'rb') as f:
            out[rel] = f.read()
    return out


def make_sentinels(root):
    with open(os.path.join(root, '_drafts/sentinel-draft.md'), 'w',
              encoding='utf-8') as f:
        f.write('---\ntitle: Sentinel draft\n---\nNội dung draft gốc.\n')
    with open(os.path.join(root, '_posts/sentinel-post.md'), 'w',
              encoding='utf-8') as f:
        f.write('---\ntitle: Sentinel post\n---\nNội dung post gốc.\n')
    return digests(root)


class RepairAgentContractTest(unittest.TestCase):

    def setUp(self):
        self.root, self.tmp = fixture()
        self.before = make_sentinels(self.root)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    # ---------------------------------------------------------- 1. lock

    def test_repair_requires_maintenance_lock(self):
        r = repair(self.root, 'INC-20261003-writer-lock',
                   'release-stale-writer-lock')
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn('REFUSED', r.stdout)
        # KHÔNG mutate gì: writer-lock file phải nguyên vẹn
        wl = rj(self.root, 'data/state/writer-lock.json')
        self.assertFalse(wl['locked'])

    def test_start_requires_real_trigger(self):
        r = run4(self.root, 'start', '--incident-id', 'INC-20261003-x')
        self.assertEqual(r.returncode, 1)
        self.assertIn('REFUSED', r.stdout)
        self.assertIn('--trigger', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(
            self.root, 'data/state/incidents/INC-20261003-x.json')))

    def test_no_overlapping_ownership(self):
        start_ok(self.root, 'INC-20261003-a')
        r = run4(self.root, 'start', '--incident-id', 'INC-20261003-b',
                 '--trigger', 'sự cố khác')
        self.assertEqual(r.returncode, 1)
        self.assertIn('REFUSED', r.stdout)
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertTrue(lk['locked'])
        self.assertEqual(lk['incident_id'], 'INC-20261003-a')

    def test_agent5_cannot_take_fresh_lock(self):
        start_ok(self.root, 'INC-20261003-a')
        r = subprocess.run(
            [PY, '-c',
             'import sys; sys.path.insert(0, %r); import maintenance as M; '
             'M.acquire_lock(%r, M.AGENT5, %r, M.parse_iso(%r))'
             % (os.path.join(self.root, 'scripts/factory'), self.root,
                'INC-20261003-a', NOW)],
            cwd=REPO, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('MaintenanceError', r.stderr)

    # --------------------------------------------- 2. one attempt / incident

    def test_one_repair_attempt_per_incident(self):
        set_writer_lock(self.root, True, expires_at=PAST)
        start_ok(self.root, 'INC-20261003-lock')
        r = repair(self.root, 'INC-20261003-lock', 'release-stale-writer-lock')
        self.assertEqual(r.returncode, 0)
        self.assertIn('AGENT4_RESULT: SUCCESS', r.stdout)
        # attempt 2 -> REFUSED (không bao giờ retry tự trị)
        r2 = repair(self.root, 'INC-20261003-lock',
                    'release-stale-writer-lock')
        self.assertEqual(r2.returncode, 1)
        self.assertIn('REFUSED', r2.stdout)
        # start lại cũng REFUSED (incident đã dùng lượt #4)
        r3 = run4(self.root, 'start', '--incident-id', 'INC-20261003-lock')
        self.assertEqual(r3.returncode, 1)
        self.assertIn('REFUSED', r3.stdout)
        inc = rj(self.root, 'data/state/incidents/INC-20261003-lock.json')
        self.assertEqual(inc['agent4']['attempts'], 1)

    # ------------------------------------------------ 3. content immutable

    def test_success_cycle_and_audit_record(self):
        set_writer_lock(self.root, True, expires_at=PAST)
        start_ok(self.root, 'INC-20261003-lock2')
        r = repair(self.root, 'INC-20261003-lock2',
                   'release-stale-writer-lock')
        self.assertEqual(r.returncode, 0)
        self.assertIn('AGENT4_RESULT: SUCCESS', r.stdout)
        wl = rj(self.root, 'data/state/writer-lock.json')
        self.assertFalse(wl['locked'])   # hạ tầng đã sửa
        self.assertEqual(digests(self.root), self.before)  # content nguyên
        inc = rj(self.root, 'data/state/incidents/INC-20261003-lock2.json')
        a4 = inc['agent4']
        self.assertEqual(a4['attempts'], 1)
        self.assertEqual(a4['result'], 'SUCCESS')
        self.assertEqual(a4['started_at'], NOW)
        self.assertEqual(a4['finished_at'], NOW)
        self.assertTrue(a4['actions'])
        self.assertEqual(a4['actions'][0]['action'],
                         'release-stale-writer-lock')
        self.assertEqual(a4['actions'][0]['files'],
                        ['data/state/writer-lock.json'])
        self.assertEqual(a4['tests'][0]['exit'], 0)
        self.assertEqual(inc['status'], 'agent4-success')
        self.assertEqual(inc['trigger'], 'watchdog STALE_WRITER_LOCK')
        self.assertTrue(inc['created_at'])
        self.assertEqual(inc['diagnosis'], a4['diagnosis'])
        # SUCCESS: lock giữ nguyên chờ Agent #5 verify
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertTrue(lk['locked'])
        self.assertEqual(lk['holder'], 'agent-4')

    def test_forbidden_paths_raise(self):
        sys.path.insert(0, os.path.join(self.root, 'scripts/factory'))
        try:
            import maintenance as M
            for bad in ('_posts/x.md', '_drafts/x.md', '_queue/x.md',
                        'data/content-matrix.csv', '_data/x.yml',
                        '_layouts/x.html', '_includes/x.html',
                        'assets/x.js'):
                with self.assertRaises(M.MaintenanceError, msg=bad):
                    M.assert_writable_rel(bad)
            for ok in ('data/state/x.json',
                       'data/state/incidents/INC-20261003-a.json',
                       'reports/factory/incidents/INC-20261003-a.md'):
                M.assert_writable_rel(ok)
        finally:
            sys.path.remove(os.path.join(self.root, 'scripts/factory'))

    # --------------------------------------------------- 4. ESCALATE paths

    def test_escalate_on_fresh_writer_lock(self):
        set_writer_lock(self.root, True, expires_at=FUTURE)
        start_ok(self.root, 'INC-20261003-fresh')
        r = repair(self.root, 'INC-20261003-fresh',
                   'release-stale-writer-lock')
        self.assertEqual(r.returncode, 0)
        self.assertIn('AGENT4_RESULT: ESCALATE', r.stdout)
        wl = rj(self.root, 'data/state/writer-lock.json')
        self.assertTrue(wl['locked'])   # KHÔNG force-unlock lock tươi
        self.assertEqual(digests(self.root), self.before)
        inc = rj(self.root, 'data/state/incidents/INC-20261003-fresh.json')
        self.assertEqual(inc['agent4']['result'], 'ESCALATE')
        self.assertEqual(inc['status'], 'agent4-escalate')
        self.assertFalse(inc['agent4']['tests'])  # không chạy test khi refuse
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertTrue(lk['locked'])   # lock giữ nguyên bàn giao #5

    def test_escalate_on_regression_failure(self):
        set_writer_lock(self.root, True, expires_at=PAST)
        start_ok(self.root, 'INC-20261003-reg')
        wj(self.root, 'data/state/validate-fail', {'stub': True})
        r = repair(self.root, 'INC-20261003-reg',
                   'release-stale-writer-lock')
        self.assertEqual(r.returncode, 0)
        self.assertIn('AGENT4_RESULT: ESCALATE', r.stdout)
        inc = rj(self.root, 'data/state/incidents/INC-20261003-reg.json')
        self.assertEqual(inc['agent4']['result'], 'ESCALATE')
        self.assertEqual(inc['agent4']['tests'][0]['exit'], 1)
        self.assertEqual(digests(self.root), self.before)

    def test_escalate_txn_active_with_pending(self):
        wj(self.root, 'data/state/transaction.json', {
            'active': True, 'updated_at': NOW,
            'pending': {'article_id': 'BLG-00009', 'step': 'promote'},
            'history': []})
        start_ok(self.root, 'INC-20261003-txn',
                 trigger='operator: transaction treo')
        r = repair(self.root, 'INC-20261003-txn',
                   'clear-inactive-transaction')
        self.assertIn('AGENT4_RESULT: ESCALATE', r.stdout)
        txn = rj(self.root, 'data/state/transaction.json')
        self.assertTrue(txn['active'])   # KHÔNG đụng txn có pending hợp lệ

    def test_clear_inactive_transaction_success(self):
        wj(self.root, 'data/state/transaction.json', {
            'active': True, 'updated_at': NOW, 'pending': None,
            'history': []})
        start_ok(self.root, 'INC-20261003-txn2',
                 trigger='operator: txn active pending=null')
        r = repair(self.root, 'INC-20261003-txn2',
                   'clear-inactive-transaction')
        self.assertIn('AGENT4_RESULT: SUCCESS', r.stdout)
        txn = rj(self.root, 'data/state/transaction.json')
        self.assertFalse(txn['active'])
        self.assertEqual(digests(self.root), self.before)

    def test_recompute_checkpoint_counts(self):
        cp = rj(self.root, 'data/state/checkpoint.json')
        cp['counts'] = {'planned': 99, 'published': 0, 'writing': 0,
                        'qa': 0, 'pass': 0, 'repair': 0, 'blocked': 0,
                        'fail': 0}
        wj(self.root, 'data/state/checkpoint.json', cp)
        start_ok(self.root, 'INC-20261003-cp',
                 trigger='watchdog CHECKPOINT_COUNT_MISMATCH')
        r = repair(self.root, 'INC-20261003-cp',
                   'recompute-checkpoint-counts')
        self.assertIn('AGENT4_RESULT: SUCCESS', r.stdout)
        cp2 = rj(self.root, 'data/state/checkpoint.json')
        self.assertEqual(cp2['counts']['planned'], 2)
        self.assertEqual(cp2['counts']['published'], 1)

    def test_prune_writer_claims(self):
        wj(self.root, 'data/state/writer-claims.json', {
            'schema_version': '1', 'updated_at': PAST,
            'leases': {'W9': {'ids': ['BLG-00001'], 'claimed_at': PAST,
                              'expires_at': PAST}}})
        start_ok(self.root, 'INC-20261003-claims',
                 trigger='operator: lease hết hạn không tự thu hồi')
        r = repair(self.root, 'INC-20261003-claims', 'prune-writer-claims')
        self.assertIn('AGENT4_RESULT: SUCCESS', r.stdout)
        reg = rj(self.root, 'data/state/writer-claims.json')
        self.assertNotIn('W9', reg['leases'])
        self.assertEqual(digests(self.root), self.before)

    # --------------------------------------- 5. operator pause + stale lock

    def test_operator_refuses_mutating_while_maintenance(self):
        start_ok(self.root, 'INC-20261003-ops')
        r = subprocess.run([PY, 'scripts/factory/factory-operator.py',
                            'prepare-next'],
                           cwd=self.root, capture_output=True, text=True,
                           timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn('maintenance-lock', r.stdout)
        self.assertIn('TỪ CHỐI', r.stdout)
        # op read-only vẫn cho chạy (status không cần lock)
        s = subprocess.run([PY, 'scripts/factory/factory-operator.py',
                            'status'],
                           cwd=self.root, capture_output=True, text=True,
                           timeout=60)
        self.assertEqual(s.returncode, 0)

    def test_stale_takeover_requires_force(self):
        start_ok(self.root, 'INC-20261003-old')
        # lock cũ đã hết TTL (> 6h)
        r = run4(self.root, 'start', '--incident-id', 'INC-20261003-new',
                 '--trigger', 'sự cố mới', now=T_PLUS)
        self.assertEqual(r.returncode, 1)
        self.assertIn('REFUSED', r.stdout)
        self.assertIn('force-stale', r.stdout)
        # takeover rõ ràng
        r2 = run4(self.root, 'start', '--incident-id', 'INC-20261003-new',
                  '--trigger', 'sự cố mới', '--force-stale', now=T_PLUS)
        self.assertEqual(r2.returncode, 0)
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertEqual(lk['incident_id'], 'INC-20261003-new')
        self.assertIn('stale_takeover', lk)
        self.assertEqual(lk['stale_takeover']['incident_id'],
                         'INC-20261003-old')
        inc = rj(self.root, 'data/state/incidents/INC-20261003-new.json')
        self.assertEqual(inc['trigger'], 'sự cố mới')

    def test_release_lock_wrong_holder_refused(self):
        start_ok(self.root, 'INC-20261003-lk')
        r = subprocess.run(
            [PY, '-c',
             'import sys; sys.path.insert(0, %r); import maintenance as M; '
             'M.release_lock(%r, M.AGENT5, %r, M.parse_iso(%r))'
             % (os.path.join(self.root, 'scripts/factory'), self.root,
                'INC-20261003-lk', NOW)],
            cwd=REPO, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)  # #5 không cướp lock của #4
        lk = rj(self.root, 'data/state/maintenance-lock.json')
        self.assertTrue(lk['locked'])
        self.assertEqual(lk['holder'], 'agent-4')

    def test_status_op_is_read_only_audit(self):
        set_writer_lock(self.root, True, expires_at=PAST)
        start_ok(self.root, 'INC-20261003-st')
        repair(self.root, 'INC-20261003-st', 'release-stale-writer-lock')
        r = run4(self.root, 'status', '--incident-id', 'INC-20261003-st')
        self.assertEqual(r.returncode, 0)
        inc = json.loads(r.stdout)
        self.assertEqual(inc['incident_id'], 'INC-20261003-st')
        self.assertEqual(inc['agent4']['result'], 'SUCCESS')


if __name__ == '__main__':
    unittest.main(verbosity=2)
