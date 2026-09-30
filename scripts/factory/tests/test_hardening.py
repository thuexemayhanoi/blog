#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test hardening sản xuất 10K — FINAL HEAD VERIFICATION contract.

Phủ các kịch bản yêu cầu:
  S1  REPAIR outcome bình thường KHÔNG gây fail operator (nonfatal).
  S2  generate-reports.py FAIL => op qa DỪNG (rc=1), không khai "qa: xong".
  S3  generate-listing-pages.py FAIL => op requeue DỪNG sau state mutation.
  S4  Draft hỏng UTF-8 => qa crash là FATAL; workflow qa step `set -eu`,
      không nuốt exit code.
  S5  generate-reports.py FAIL => prepare-next DỪNG, không claim.
  S6  Push block (tách từ factory-operator.yml) mô phỏng bằng fake git:
      rebase conflict => STOP; rebase sạch => verify lại TRƯỚC push;
      verify FAIL sau rebase => STOP; tree khác tree đã verify => STOP.
  S7  Static: workflow không force push, verify trước commit, không cron,
      concurrency/permissions giữ nguyên, publish-queue.yml vẫn gated
      enabled=false, _data/publishing.yml enabled: false. Thêm: publish-queue
      legacy không cron, cổng factory-validate chạy hardening/watchdog,
      watchdog workflow READ-ONLY.
  S8  recover FAIL-CLOSED (docs/RECOVERY.md): reports hỏng => DỪNG rc=1
      (S8), transaction CHƯA đóng; sửa reports => recover lại đóng đúng
      (S8a); validate --expect-txn-phase chặt active+phase (S8b); trạng
      thái vật lý không suy luận được => STOP không mutate (S8c).

Chạy: python3 scripts/factory/tests/test_hardening.py (không đổi ROOT).
"""
import csv
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
PY = sys.executable

IGNORE = shutil.ignore_patterns('__pycache__', '.git', '*.pyc')


def fresh_copy():
    """Bản sao repo sạch trong tmp; trả về (work, tmp)."""
    tmp = tempfile.mkdtemp(prefix='harden-')
    work = os.path.join(tmp, 'work')
    shutil.copytree(ROOT, work, ignore=IGNORE)
    return work, tmp


def run(work, *args, **kw):
    return subprocess.run([PY] + list(args), cwd=work,
                          capture_output=True, text=True, **kw)


def load_rows(work):
    with open(os.path.join(work, 'data/content-matrix.csv'),
              encoding='utf-8') as f:
        return list(csv.DictReader(f))


def save_rows(work, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    with open(os.path.join(work, 'data/content-matrix.csv'), 'w',
              encoding='utf-8', newline='') as f:
        f.write(buf.getvalue())


def set_status(work, aid, status, repair_count=None):
    rows = load_rows(work)
    for r in rows:
        if r['id'] == aid:
            r['status'] = status
            if repair_count is not None:
                r['repair_count'] = str(repair_count)
    save_rows(work, rows)
    # đồng bộ checkpoint + outputs deterministic để preflight validate PASS
    cp_path = os.path.join(work, 'data/state/checkpoint.json')
    with open(cp_path, encoding='utf-8') as f:
        cp = json.load(f)
    counts = {}
    for r in rows:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    cp['counts'] = {'legacy_total': cp['counts'].get('legacy_total', 483),
                     'existing': counts.get('EXISTING', 0),
                     'review': counts.get('REVIEW', 0),
                     'planned': counts.get('PLANNED', 0),
                     'writing': counts.get('WRITING', 0),
                     'qa': counts.get('QA', 0),
                     'pass': counts.get('PASS', 0),
                     'published': counts.get('PUBLISHED', 0),
                     'repair': counts.get('REPAIR', 0),
                     'blocked': counts.get('BLOCKED', 0),
                     'fail': counts.get('FAIL', 0)}
    with open(cp_path, 'w', encoding='utf-8') as f:
        json.dump(cp, f, ensure_ascii=False, indent=2)
    for script in ('generate-reports.py', 'generate-matrix.py',
                   'generate-listing-pages.py'):
        rr = run(work, 'scripts/factory/' + script)
        assert rr.returncode == 0, script + ': ' + rr.stdout + rr.stderr


def get_row(work, aid):
    for r in load_rows(work):
        if r['id'] == aid:
            return r
    raise AssertionError(aid)


def first_planned(work, skip=0):
    n = -1
    for r in load_rows(work):
        if r['status'] == 'PLANNED':
            n += 1
            if n == skip:
                return r
    raise AssertionError('không còn hàng PLANNED')


def write_garbage_draft(work, row, raw=None):
    slug = row['output_path']
    slug = slug[len('_posts/{date}-'):-3]
    d = '2026-09-27'
    path = os.path.join(work, '_drafts', '%s-%s.md' % (d, slug))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = 'wb' if isinstance(raw, bytes) else 'w'
    with open(path, mode, encoding=None if mode == 'wb' else 'utf-8') as f:
        f.write(raw if raw is not None else 'nội dung rác không frontmatter\n')
    return path


def break_script(work, name):
    """Chèn lệnh exit(1) vào cuối script để mô phỏng tool crash/failure."""
    p = os.path.join(work, 'scripts/factory', name)
    with open(p, 'a', encoding='utf-8') as f:
        f.write('\nimport sys as _s\n_s.exit(1)\n')


# ------------------------------------------------------------------ S1/S2/S4
class QaHardening(unittest.TestCase):
    def test_s1_repair_outcome_nonfatal(self):
        work, tmp = fresh_copy()
        try:
            row = first_planned(work)
            set_status(work, row['id'], 'WRITING')
            write_garbage_draft(work, row)
            r = run(work, 'scripts/factory/factory-operator.py',
                    'qa', '--ids', row['id'])
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('REPAIR', r.stdout)
            self.assertIn('qa: xong', r.stdout)
            self.assertEqual(get_row(work, row['id'])['status'], 'REPAIR')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_s2_report_generator_failure_stops_qa(self):
        work, tmp = fresh_copy()
        try:
            row = first_planned(work)
            set_status(work, row['id'], 'WRITING')
            write_garbage_draft(work, row)
            break_script(work, 'generate-reports.py')
            r = run(work, 'scripts/factory/factory-operator.py',
                    'qa', '--ids', row['id'])
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn('run_reports FAIL', r.stdout)
            self.assertNotIn('qa: xong', r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_s4_qa_crash_is_fatal(self):
        work, tmp = fresh_copy()
        try:
            row = first_planned(work)
            set_status(work, row['id'], 'WRITING')
            # byte UTF-8 không hợp lệ => open(..., encoding='utf-8') crash
            write_garbage_draft(
                work, row,
                raw=b'\xff\xfe n\xf3i dung kha nang \x80\x81\n')
            r = run(work, 'scripts/factory/factory-operator.py',
                    'qa', '--ids', row['id'])
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn('qa: xong', r.stdout)
            self.assertTrue('UnicodeDecodeError' in r.stderr
                            or 'Traceback' in r.stderr,
                            'phải là crash thật, không phải outcome thường')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ S3
class RequeueHardening(unittest.TestCase):
    def test_s3_listing_generator_failure_stops_requeue(self):
        work, tmp = fresh_copy()
        try:
            row = first_planned(work)
            set_status(work, row['id'], 'REPAIR', repair_count=0)
            break_script(work, 'generate-listing-pages.py')
            r = run(work, 'scripts/factory/factory-operator.py',
                    'requeue', '--ids', row['id'])
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn('run_reports FAIL', r.stdout)
            # state đã đổi trên đĩa nhưng op DỪNG — workflow không commit
            self.assertEqual(get_row(work, row['id'])['status'], 'WRITING')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ S5
class PrepareNextHardening(unittest.TestCase):
    def test_s5_report_failure_stops_prepare_next(self):
        work, tmp = fresh_copy()
        try:
            # hermetic: repo thật có thể đang giữ in_progress_chunk
            # WRITING với draft đã push (BLG-00625..00634) — release-chunk
            # bảo vệ hàng có draft nên phải bỏ draft trong bản sao fixture
            # trước, nếu không prepare-next từ chối ở bước "còn hàng dở"
            # (đúng engine, nhưng không phải thứ test này kiểm).
            drafts_dir = os.path.join(work, '_drafts')
            for fn in os.listdir(drafts_dir):
                os.remove(os.path.join(drafts_dir, fn))
            r0 = run(work, 'scripts/factory/factory-operator.py',
                     'release-chunk')
            self.assertIn(r0.returncode, (0, 1), r0.stdout)
            break_script(work, 'generate-reports.py')
            r = run(work, 'scripts/factory/factory-operator.py',
                    'prepare-next', '--count', '3')
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertNotIn('prepare-next: claim', r.stdout)
            self.assertIn('run_reports FAIL', r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ S8
class RecoverHardening(unittest.TestCase):
    def test_s8_recover_reports_failure_stops(self):
        work, tmp = fresh_copy()
        try:
            row = first_planned(work)
            set_status(work, row['id'], 'QA')
            dest = '_posts/2026-09-27-recover-sim.md'
            with open(os.path.join(work, dest), 'w',
                      encoding='utf-8') as f:
                f.write('---\narticle_id: %s\ntitle: x\n---\nnội dung\n'
                        % row['id'])
            txn = {
                'active': True,
                'pending': {'article_id': row['id'], 'step':
                            'promote %s' % row['id'], 'destination': dest,
                            'draft': '_drafts/x.md'},
                'history': [{'destination': dest,
                             'source': '_drafts/x.md'}],
            }
            with open(os.path.join(work, 'data/state/transaction.json'),
                      'w', encoding='utf-8') as f:
                json.dump(txn, f, ensure_ascii=False, indent=2)
            break_script(work, 'generate-reports.py')
            r = run(work, 'scripts/factory/factory-operator.py', 'recover')
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn('run_reports FAIL', r.stdout)
            self.assertNotIn('recover: transaction hoàn tất', r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


    def test_s8a_recover_resume_closes_txn_only_after_postcheck(self):
        """FAIL-CLOSED: hậu kiểm FAIL -> transaction GIỮ NGUYÊN active +
        phase RECOVERY_VERIFYING; chạy recover lại sau khi sửa reports
        (idempotent) -> CHỈ KHI ĐÓ transaction mới được đóng."""
        work, tmp = fresh_copy()
        try:
            row = first_planned(work)
            set_status(work, row['id'], 'QA')
            draft = '_drafts/2026-09-27-recover-s8a.md'
            with open(os.path.join(work, draft), 'w',
                      encoding='utf-8') as f:
                f.write('---\narticle_id: %s\ntitle: x\n---\nnội dung\n'
                        % row['id'])
            txn = {
                'active': True,
                'pending': {'article_id': row['id'],
                            'step': 'promote %s' % row['id'],
                            'destination': '_posts/2026-09-27-recover-s8a.md',
                            'draft': draft},
                'history': [{'destination':
                             '_posts/2026-09-27-recover-s8a.md',
                             'source': draft}],
                'updated_at': '2026-09-30T00:00:00+00:00',
            }
            with open(os.path.join(work, 'data/state/transaction.json'),
                      'w', encoding='utf-8') as f:
                json.dump(txn, f, ensure_ascii=False, indent=2)
            break_script(work, 'generate-reports.py')
            r = run(work, 'scripts/factory/factory-operator.py', 'recover')
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn('run_reports FAIL', r.stdout)
            self.assertNotIn('transaction đã đóng', r.stdout)
            with open(os.path.join(work, 'data/state/transaction.json'),
                      encoding='utf-8') as f:
                txn1 = json.load(f)
            self.assertTrue(txn1.get('active'),
                            'FAIL-CLOSED bị phá: txn đóng trước hậu kiểm')
            self.assertEqual(txn1.get('phase'), 'RECOVERY_VERIFYING')
            self.assertEqual(txn1.get('recover_result'),
                             'RECOVERED_ROLLED_BACK')
            # sửa reports -> recover lại (resume idempotent) -> đóng txn
            shutil.copy(os.path.join(ROOT, 'scripts/factory/',
                                     'generate-reports.py'),
                        os.path.join(work, 'scripts/factory/',
                                     'generate-reports.py'))
            r = run(work, 'scripts/factory/factory-operator.py', 'recover')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('RECOVERED_ROLLED_BACK', r.stdout)
            self.assertIn('transaction đã đóng', r.stdout)
            with open(os.path.join(work, 'data/state/transaction.json'),
                      encoding='utf-8') as f:
                txn2 = json.load(f)
            self.assertFalse(txn2.get('active'))
            self.assertNotIn('phase', txn2)
            self.assertEqual(txn2['history'][-1]['result'],
                             'RECOVERED_ROLLED_BACK')
            # idempotent: note recover không bị ghi hai lần
            self.assertEqual(get_row(work, row['id'])['notes'].count('recover '), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_s8b_expect_txn_phase_strict_contract(self):
        """validate.py --expect-txn-phase: CHẶT — active=true VÀ phase khớp;
        inactive/mismatch đều FAIL; không có flag thì active vẫn FAIL."""
        work, tmp = fresh_copy()
        try:
            v = 'scripts/factory/validate.py'
            # txn sạch + expect -> FAIL (không lỏng cho inactive)
            r = run(work, v, '--scope', 'chunk',
                    '--expect-txn-phase', 'RECOVERY_VERIFYING')
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn('transaction inactive', r.stdout)
            # active + phase khớp -> PASS, SUMMARY_JSON mang expect_txn_phase
            txn = {'active': True, 'pending': None, 'history': [],
                   'phase': 'RECOVERY_VERIFYING',
                   'updated_at': '2026-09-30T00:00:00+00:00',
                   'note': 'hậu kiểm recover (fixture)'}
            with open(os.path.join(work, 'data/state/transaction.json'),
                      'w', encoding='utf-8') as f:
                json.dump(txn, f, ensure_ascii=False, indent=2)
            r = run(work, v, '--scope', 'chunk',
                    '--expect-txn-phase', 'RECOVERY_VERIFYING')
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn('"expect_txn_phase": "RECOVERY_VERIFYING"', r.stdout)
            # active + phase lệch -> FAIL
            txn['phase'] = 'OTHER_PHASE'
            with open(os.path.join(work, 'data/state/transaction.json'),
                      'w', encoding='utf-8') as f:
                json.dump(txn, f, ensure_ascii=False, indent=2)
            r = run(work, v, '--scope', 'chunk',
                    '--expect-txn-phase', 'RECOVERY_VERIFYING')
            self.assertEqual(r.returncode, 1)
            self.assertIn('!= --expect-txn-phase', r.stdout)
            # active KHÔNG flag -> FAIL như hợp đồng cũ
            r = run(work, v, '--scope', 'chunk')
            self.assertEqual(r.returncode, 1)
            self.assertIn('transaction đang treo', r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_s8c_recover_unknown_physical_state_stops(self):
        """Không suy luận được trạng thái vật lý -> STOP rc=1, KHÔNG mutate
        matrix/transaction (không bịa phục hồi)."""
        work, tmp = fresh_copy()
        try:
            row = first_planned(work)
            before = get_row(work, row['id'])
            txn = {
                'active': True,
                'pending': {'article_id': row['id'],
                            'destination': '_posts/2026-09-27-mat-tich.md',
                            'draft': '_drafts/mat-tich.md'},
                'history': [{'destination': '_posts/2026-09-27-mat-tich.md',
                             'source': '_drafts/mat-tich.md'}],
                'updated_at': '2026-09-30T00:00:00+00:00',
            }
            with open(os.path.join(work, 'data/state/transaction.json'),
                      'w', encoding='utf-8') as f:
                json.dump(txn, f, ensure_ascii=False, indent=2)
            r = run(work, 'scripts/factory/factory-operator.py', 'recover')
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn('không suy luận được', r.stdout)
            with open(os.path.join(work, 'data/state/transaction.json'),
                      encoding='utf-8') as f:
                txn2 = json.load(f)
            self.assertTrue(txn2.get('active'), 'txn bị đóng oan')
            after = get_row(work, row['id'])
            self.assertEqual(after['status'], before['status'])
            self.assertEqual(after['notes'], before['notes'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

# ------------------------------------------------------------------ S6
def read_workflow():
    with open(os.path.join(ROOT, '.github/workflows/factory-operator.yml'),
              encoding='utf-8') as f:
        return f.read()


def extract_run_block(text, step_marker):
    """Tách run-block của step (mọt dòng `run: |`, body thụt 10 space)."""
    i = text.index(step_marker)
    j = text.index('run: |', i)
    lines = text[j:].splitlines()
    body = []
    for ln in lines[1:]:
        if ln.strip() == '' :
            body.append('')
            continue
        if not ln.startswith(' ' * 10):
            break
        body.append(ln[10:])
    return '\n'.join(body) + '\n'


FAKE_GIT = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
scen = json.load(open(os.environ['FAKE_GIT_SCENARIO']))
log = os.environ.get('FAKE_GIT_LOG')
with open(log, 'a') as f:
    f.write('CALL ' + ' '.join(argv) + '\n')
steps = scen['steps']
i = scen.get('_pos', 0)
while i < len(steps):
    st = steps[i]
    a = st.get('args') or []
    if argv[:len(a)] == a:
        scen['_pos'] = i + 1
        json.dump(scen, open(os.environ['FAKE_GIT_SCENARIO'], 'w'))
        if st.get('err'):
            sys.stderr.write(st['err'])
        sys.stdout.write(st.get('out') or '')
        sys.exit(st.get('exit', 0))
    i += 1
sys.stderr.write('FAKE GIT: KHÔNG KỊCH BẢN CHO: %s\n' % argv)
sys.exit(128)
'''

STUB_VERIFY = r'''#!/usr/bin/env python3
import os, subprocess, sys
log = os.environ['VERIFY_LOG']
head = subprocess.run(['git', 'rev-parse', 'HEAD'],
                      capture_output=True, text=True).stdout.strip()
with open(log, 'a') as f:
    f.write('VERIFY_HEAD=' + head + '\n')
sys.exit(int(os.environ.get('VERIFY_EXIT', '0')))
'''


class PushBlockSim(unittest.TestCase):
    """Mô phỏng run-block commit/push bằng fake git (script theo kịch bản)."""

    def setUp(self):
        self.work, self.tmp = fresh_copy()
        self.bin = os.path.join(self.tmp, 'bin')
        os.makedirs(self.bin)
        self.scen_path = os.path.join(self.tmp, 'scenario.json')
        self.git_log = os.path.join(self.tmp, 'git.log')
        self.verify_log = os.path.join(self.tmp, 'verify.log')
        # thay factory-operator.py bằng stub verify (chỉ block push dùng nó)
        stub = os.path.join(self.work, 'scripts/factory/factory-operator.py')
        with open(stub, 'w', encoding='utf-8') as f:
            f.write(STUB_VERIFY)
        self.block = extract_run_block(read_workflow(),
                                       'Commit va push fast-forward')
        # kịch bản chung: config ×2, add, write-tree, diff --cached,
        # commit, rev-parse HEAD^{tree} == VERIFIED_TREE
        self.common = [
            {'args': ['config'], 'exit': 0},
            {'args': ['config'], 'exit': 0},
            {'args': ['add'], 'exit': 0},
            {'args': ['write-tree'], 'out': 'TREETREE\n', 'exit': 0},
            {'args': ['diff', '--cached', '--quiet'], 'exit': 1},
            {'args': ['commit'], 'exit': 0},
            {'args': ['rev-parse'], 'out': 'TREETREE\n', 'exit': 0},
        ]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _git_shim(self):
        p = os.path.join(self.bin, 'git')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(FAKE_GIT)
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)

    def _run_block(self, extra_steps, env_extra=None):
        scenario = {'steps': self.common + extra_steps}
        with open(self.scen_path, 'w') as f:
            json.dump(scenario, f)
        self._git_shim()
        env = dict(os.environ)
        env.update({
            'PATH': self.bin + os.pathsep + env['PATH'],
            'FAKE_GIT_SCENARIO': self.scen_path,
            'FAKE_GIT_LOG': self.git_log,
            'VERIFY_LOG': self.verify_log,
            'VERIFY_EXIT': '0',
            'GITHUB_ENV': '/dev/null',
            'OP': 'qa',
            'OPERATOR_VERIFIED_TREE': 'TREETREE',
        })
        env.update(env_extra or {})
        script = os.path.join(self.tmp, 'push_block.sh')
        with open(script, 'w', encoding='utf-8') as f:
            f.write(self.block)
        return subprocess.run(['bash', script], cwd=self.work, env=env,
                              capture_output=True, text=True)

    def _git_calls(self):
        with open(self.git_log) as f:
            return f.read().splitlines()

    def test_s6a_rebase_conflict_stops(self):
        r = self._run_block([
            {'args': ['push'], 'exit': 1,
             'err': 'non-fast-forward\n'},
            {'args': ['fetch'], 'exit': 0},
            {'args': ['rebase', 'origin/main'], 'exit': 1,
             'err': 'rebase conflict trong tệp production\n'},
            {'args': ['rebase', '--abort'], 'exit': 0},
        ])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('rebase conflict', r.stdout)
        self.assertNotIn('FINAL_PUSHED_HEAD', r.stdout)
        self.assertNotIn('--force', '\n'.join(self._git_calls()))

    def test_s6b_clean_rebase_verifies_before_push(self):
        r = self._run_block([
            {'args': ['push'], 'exit': 1, 'err': 'non-fast-forward\n'},
            {'args': ['fetch'], 'exit': 0},
            {'args': ['rebase', 'origin/main'], 'exit': 0,
             'out': 'Successfully rebased\n'},
            {'args': ['rev-parse', 'HEAD'], 'out': 'REBASED1\n', 'exit': 0},
            # git rev-parse HEAD do STUB VERIFY gọi:
            {'args': ['rev-parse', 'HEAD'], 'out': 'REBASED2\n', 'exit': 0},
            {'args': ['diff', '--quiet'], 'exit': 0},
            {'args': ['diff', '--cached', '--quiet'], 'exit': 0},
            {'args': ['push'], 'exit': 0},
            {'args': ['fetch'], 'exit': 0},
            {'args': ['merge-base'], 'exit': 0},
            {'args': ['rev-parse'], 'out': 'REBASED1\n', 'exit': 0},
            {'args': ['rev-parse'], 'out': 'ORIGINB\n', 'exit': 0},
        ])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('FINAL_PUSHED_HEAD=REBASED1', r.stdout)
        self.assertIn('ORIGIN_HEAD_AFTER=ORIGINB', r.stdout)
        # verify phải chạy SAU rebase, TRƯỚC push — chứng minh qua log
        with open(self.verify_log) as f:
            heads = [l for l in f.read().splitlines() if l]
        self.assertEqual(len(heads), 1, 'verify đúng 1 lần sau rebase')
        self.assertEqual(heads[0], 'VERIFY_HEAD=REBASED2')
        calls = self._git_calls()
        i_rebase = next(i for i, c in enumerate(calls)
                        if 'rebase origin/main' in c)
        i_push = next(i for i, c in enumerate(calls)
                      if c == 'CALL push' and i > i_rebase)
        # giữa rebase và push phải có rev-parse HEAD do verify gọi
        self.assertTrue(any('rev-parse HEAD' in c for c in
                            calls[i_rebase + 1:i_push]))

    def test_s6c_verify_fail_after_rebase_stops(self):
        r = self._run_block([
            {'args': ['push'], 'exit': 1, 'err': 'non-fast-forward\n'},
            {'args': ['fetch'], 'exit': 0},
            {'args': ['rebase', 'origin/main'], 'exit': 0},
            {'args': ['rev-parse', 'HEAD'], 'out': 'REBASED1\n', 'exit': 0},
            {'args': ['rev-parse', 'HEAD'], 'out': 'REBASED1\n', 'exit': 0},
        ], env_extra={'VERIFY_EXIT': '1'})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        calls = self._git_calls()
        # KHÔNG có push nào sau rebase
        i_rebase = next(i for i, c in enumerate(calls)
                        if 'rebase origin/main' in c)
        self.assertFalse(any(c == 'CALL push' for c in calls[i_rebase:]))

    def test_s6d_tree_mismatch_stops_before_commit(self):
        r = self._run_block([], env_extra={'OPERATOR_VERIFIED_TREE': 'WRONG'})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('cay index khac cay da verified', r.stdout)
        calls = self._git_calls()
        self.assertFalse(any(c == 'CALL commit' for c in calls))

    def test_s6e_first_push_success(self):
        r = self._run_block([
            {'args': ['push'], 'exit': 0},
            {'args': ['fetch'], 'exit': 0},
            {'args': ['merge-base'], 'exit': 0},
            {'args': ['rev-parse'], 'out': 'PUSHED1\n', 'exit': 0},
            {'args': ['rev-parse'], 'out': 'ORIGINA\n', 'exit': 0},
        ])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('FINAL_PUSHED_HEAD=PUSHED1', r.stdout)
        self.assertIn('ORIGIN_HEAD_AFTER=ORIGINA', r.stdout)


# ------------------------------------------------------------------ S7
class StaticContract(unittest.TestCase):
    def test_s7_workflow_invariants(self):
        y = read_workflow()
        # không force push
        self.assertNotIn('--force', y.replace('force push', ''))
        self.assertNotIn('push -f', y)
        self.assertNotIn('git push --force', y)
        # cây đã verify so khớp ở verify step VÀ commit step
        self.assertGreaterEqual(y.count('$OPERATOR_VERIFIED_TREE'), 2)
        self.assertIn('$OPERATOR_VERIFIED_TREE',
                      y[y.index('Commit va push fast-forward'):])
        self.assertIn('OPERATOR_VERIFIED_TREE=',
                      y[y.index('Verify chuan'):y.index(
                          'Commit va push fast-forward')])
        # verify TRƯỚC commit
        i_verify = y.index('Verify chuan tren dung trang thai se commit')
        i_commit = y.index('Commit va push fast-forward')
        self.assertLess(i_verify, i_commit)
        # bước xóa command file TRƯỚC verify (cây verify == cây commit)
        i_rm = y.index('Xoa lenh da xu ly')
        self.assertLess(i_rm, i_verify)
        # không cron / schedule (không bật sản xuất hàng giờ)
        for line in y.splitlines():
            s = line.strip()
            if s.startswith('#') or not s:
                continue
            self.assertNotIn('cron', s.lower(),
                             'cron trong phần chạy được: %s' % s)
            self.assertNotIn('schedule', s.lower(),
                             'schedule trong phần chạy được: %s' % s)
        # concurrency + permissions
        self.assertIn('group: blog-factory-production', y)
        self.assertIn('cancel-in-progress: false', y)
        self.assertIn('contents: write', y)
        # trigger chỉ theo command file
        self.assertIn("paths: ['data/factory/operator-command.json']", y)
        # tên step không chứa ": " (bug YAML startup)
        for line in y.splitlines():
            s = line.strip()
            if s.startswith('- name: ') and ': ' in s[len('- name: '):]:
                self.fail('tên step chứa ": ": %s' % s)
        # PYTHONDONTWRITEBYTECODE để cây verify ổn định
        self.assertIn("PYTHONDONTWRITEBYTECODE: '1'", y)

    def test_s7_qa_step_fatal_crash(self):
        y = read_workflow()
        i = y.index('- name: op qa')
        seg = y[i:y.index('- name: op publish')]
        self.assertIn('set -eu', seg)
        self.assertNotIn('|| code=$?', seg)

    def test_s7_publish_queue_disabled(self):
        with open(os.path.join(ROOT, '.github/workflows/publish-queue.yml'),
                  encoding='utf-8') as f:
            pq = f.read()
        self.assertIn("config.get(\"enabled\", False)", pq)
        with open(os.path.join(ROOT, '_data/publishing.yml'),
                  encoding='utf-8') as f:
            pub = f.read()
        self.assertRegex(pub, r'(?m)^enabled:\s*false\s*$')

    def test_s7_no_ai_no_second_publisher(self):
        y = read_workflow()
        for bad in ('api_key', 'API_KEY', 'sk-', 'OPENAI', 'MISTRAL',
                    'anthropic', 'secrets.'):
            self.assertNotIn(bad, y)
        # publish-gate.py vẫn là người xuất bản duy nhất (tham chiếu canonical)
        with open(os.path.join(ROOT, 'scripts/factory/factory-operator.py'),
                  encoding='utf-8') as f:
            opsrc = f.read()
        self.assertIn("'scripts/factory/publish-gate.py'", opsrc)


    def test_s7_publish_queue_legacy_no_cron(self):
        """publish-queue.yml là legacy diagnostics-only: cron ĐÃ BỎ (hợp
        đồng hardening), chỉ còn workflow_dispatch chạy tay."""
        with open(os.path.join(ROOT, '.github/workflows/publish-queue.yml'),
                  encoding='utf-8') as f:
            pq = f.read()
        self.assertNotIn('cron', pq)
        self.assertNotIn('schedule:', pq)
        self.assertIn('workflow_dispatch:', pq)
        self.assertIn('LEGACY', pq)

    def test_s7_factory_validate_gates_hardening(self):
        """Cổng CI Factory validate PHẢI chạy tầng 1/2: test_hardening.py
        + test_watchdog.py — không được tự ý tháo khỏi gate."""
        with open(os.path.join(ROOT, '.github/workflows/factory-validate.yml'),
                  encoding='utf-8') as f:
            y = f.read()
        self.assertIn('tests/test_hardening.py', y)
        self.assertIn('tests/test_watchdog.py', y)

    def test_s7_watchdog_workflow_readonly_contract(self):
        """factory-watchdog.yml: workflow định kỳ duy nhất của factory,
        READ-ONLY: contents: read, không write/push, purity bắt buộc."""
        with open(os.path.join(ROOT, '.github/workflows/factory-watchdog.yml'),
                  encoding='utf-8') as f:
            w = f.read()
        self.assertIn('contents: read', w)
        self.assertNotIn('contents: write', w)
        self.assertIn('cron: "*/30 * * * *"', w)
        self.assertIn('workflow_dispatch', w)
        self.assertIn('scripts/factory/watchdog.py', w)
        self.assertIn('git status --porcelain', w)
        self.assertNotIn('git push', w)


if __name__ == '__main__':
    unittest.main(verbosity=2)
