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
  S6  Push block của publish-drafts.yml mô phỏng bằng fake git: push
      FAIL => STOP ngay (không rebase, không retry); commit rồi mới
      push; không thay đổi => không commit; KHÔNG bao giờ force push
      (static).
  S7  Static: hợp đồng 4 workflow hiện tại — quality-gate.yml FAST +
      READ-ONLY; factory-liveness.yml 6h; factory-publish-verify.yml
      FULL audit + READ-ONLY; publish-drafts.yml đường nóng đơn giản
      push _drafts (QA 75/70, KHÔNG refill, không AI/API secrets);
      publish-gate.py là người xuất bản duy nhất; các workflow đã
      retire (factory-production, factory-refill, ...) KHÔNG quay lại;
      _data/publishing.yml enabled: false.
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
    with open(os.path.join(ROOT, '.github/workflows/publish-drafts.yml'),
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


FAKE_GIT = '#!%s\n' % PY + r'''import json, os, sys
# (shebang trinh thuc that - tranh de quy qua PATH khi bin/ chua
# stub python3)
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

# STUB_PY = python3 gia: ghi argv vao verify log VA git log (de chung minh
# thu tu goi), exit theo VERIFY_EXIT. Shebang dung trinh thuc that
# (sys.executable) de tranh de quy qua PATH.
STUB_PY = '#!%s\n' % PY + r"""import os, sys
argv = sys.argv[1:]
log = os.environ.get('FAKE_GIT_LOG')
if log:
    with open(log, 'a') as f:
        f.write('CALL python3 ' + ' '.join(argv) + '\n')
vlog = os.environ.get('VERIFY_LOG')
if vlog:
    with open(vlog, 'a') as f:
        f.write(' '.join(argv) + '\n')
sys.exit(int(os.environ.get('VERIFY_EXIT', '0')))
"""


class PushBlockSim(unittest.TestCase):
    """Mô phỏng run-block commit của publish-drafts.yml bằng fake git:
    pipeline đơn giản — commit 1 lần rồi push; push FAIL => run FAIL
    ngay (KHÔNG rebase, KHÔNG retry); không thay đổi => không commit;
    không bao giờ force push (static)."""

    def setUp(self):
        self.work, self.tmp = fresh_copy()
        self.bin = os.path.join(self.tmp, 'bin')
        os.makedirs(self.bin)
        self.scen_path = os.path.join(self.tmp, 'scenario.json')
        self.git_log = os.path.join(self.tmp, 'git.log')
        self.verify_log = os.path.join(self.tmp, 'verify.log')
        self.block = extract_run_block(
            read_workflow(), 'Commit ket qua publish (1 commit)')
        # GitHub Actions thay ${{ }} trước khi bash chạy; làm giống engine
        # để bash chạy đúng ở local
        self.block = self.block.replace(
            '${{ steps.select.outputs.ids }}', 'TESTIDS')
        # kịch bản chung: config ×2, add -A, diff --cached (có thay đổi),
        # commit
        self.common = [
            {'args': ['config'], 'exit': 0},
            {'args': ['config'], 'exit': 0},
            {'args': ['add'], 'exit': 0},
            {'args': ['diff', '--cached', '--quiet'], 'exit': 1},
            {'args': ['commit'], 'exit': 0},
        ]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _git_shim(self):
        p = os.path.join(self.bin, 'git')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(FAKE_GIT)
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
        p = os.path.join(self.bin, 'python3')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(STUB_PY)
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
            'ACTION': 'qa',
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

    def test_s6a_push_fail_stops_no_retry(self):
        r = self._run_block([
            {'args': ['push'], 'exit': 1,
             'err': 'non-fast-forward\n'},
            # nếu pipeline retry thì bước này sẽ khớp và run exit 0 — FAIL
            {'args': ['push'], 'exit': 0},
        ])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        calls = self._git_calls()
        self.assertEqual(calls.count('CALL push'), 1,
                         'push FAIL phai STOP ngay — khong rebase, '
                         'khong retry')
        self.assertNotIn('--force', '\n'.join(calls))
        self.assertNotIn('rebase', '\n'.join(calls))

    def test_s6b_clean_push_success(self):
        r = self._run_block([{'args': ['push'], 'exit': 0}])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self._git_calls()
        i_commit = next(i for i, c in enumerate(calls)
                        if c.startswith('CALL commit'))
        i_push = next(i for i, c in enumerate(calls)
                      if c == 'CALL push')
        self.assertLess(i_commit, i_push, 'commit phai TRUOC push')
        self.assertEqual(calls.count('CALL push'), 1)

    def test_s6c_nothing_to_commit_skips_push(self):
        self.common[3] = {'args': ['diff', '--cached', '--quiet'],
                          'exit': 0}
        r = self._run_block([])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self._git_calls()
        self.assertFalse(any(c.startswith('CALL commit') for c in calls),
                         'khong thay doi thi KHONG commit')
        self.assertFalse(any(c == 'CALL push' for c in calls),
                         'khong thay doi thi KHONG push')

    def test_s6d_no_force_push_static(self):
        y = read_workflow()
        self.assertNotIn('push -f', y)
        self.assertNotIn('git push --force', y)
        self.assertNotIn('--force', y.replace('force push', ''))


# ------------------------------------------------------------------ S7
class StaticContract(unittest.TestCase):
    """Hợp đồng 4 workflow hiện tại (publish-drafts.yml thay thế
    factory-production.yml + factory-refill.yml đã retire theo lệnh
    chủ xe): quality-gate (FAST, read-only, mọi push/PR), publish-drafts
    (đường nóng đơn giản push main _drafts/** — chọn EXACT ID từ
    article_id, tối đa 2 draft/push, claim chỉ PLANNED, qa/publish
    --ids --scope fast ngưỡng 75/70, contents: write), factory-liveness
    (read-only, cron 6 giờ, KHÔNG bao giờ recover), factory-publish-verify
    (FULL audit, read-only, CHỈ workflow_dispatch)."""

    def test_s7_workflow_contract(self):
        wf = sorted(f for f in os.listdir(os.path.join(ROOT,
                                                       '.github/workflows'))
                   if f.endswith('.yml'))
        self.assertEqual(wf, ['factory-liveness.yml',
                              'factory-publish-verify.yml',
                              'publish-drafts.yml',
                              'quality-gate.yml'])
        # các workflow/test đã retire KHÔNG quay lại
        retired = ['factory-operator.yml', 'factory-validate.yml',
                   'factory-capacity-validate.yml', 'factory-watchdog.yml',
                   'publish-queue.yml', 'weekly-maintenance.yml',
                   'factory-production.yml', 'factory-refill.yml',
                   'diag-factory-tests.yml']
        for name in retired:
            self.assertFalse(
                os.path.exists(os.path.join(ROOT, '.github/workflows', name)),
                'workflow da retire khong duoc quay lai: %s' % name)
        self.assertFalse(os.path.exists(os.path.join(
            ROOT, 'scripts/factory/tests/test_push_rebase_overlap.py')),
            'test da retire khong duoc quay lai')

    def test_s7_quality_gate_fast_readonly(self):
        with open(os.path.join(ROOT, '.github/workflows/quality-gate.yml'),
                  encoding='utf-8') as f:
            y = f.read()
        self.assertIn('contents: read', y)
        self.assertNotIn('contents: write', y)
        self.assertNotIn('git push', y)
        self.assertIn('validate.py --scope chunk', y)
        self.assertIn('jekyll-build-pages', y)
        self.assertIn('check-built-links.py', y)
        self.assertIn('push:', y)          # trigger push main
        self.assertIn('pull_request:', y)  # trigger PR
        self.assertIn('workflow_dispatch:', y)

    def test_s7_publish_verify_full_audit_readonly(self):
        """factory-publish-verify.yml: FULL audit read-only, CHỈ
        workflow_dispatch (không cron), cùng nội dung audit của
        weekly-maintenance.yml đã retire."""
        with open(os.path.join(ROOT,
                               '.github/workflows/factory-publish-verify.yml'),
                  encoding='utf-8') as f:
            y = f.read()
        self.assertIn('contents: read', y)
        self.assertNotIn('contents: write', y)
        self.assertNotIn('git push', y)
        self.assertNotIn('cron:', y)
        self.assertIn('workflow_dispatch:', y)
        self.assertIn('factory-operator.py verify --scope full', y)
        self.assertIn('scripts/factory/watchdog.py', y)
        self.assertIn('refill-queue.py --verify', y)
        self.assertIn('--selftest', y)
        self.assertIn('sitemap-plan.py', y)
        self.assertIn('jekyll-build-pages', y)
        self.assertIn('check-built-links.py', y)

    def test_s7_liveness_readonly_never_recovers(self):
        """factory-liveness.yml: cron moi 6 gio, READ-ONLY thuần —
        watchdog + status + purity; KHÔNG bao giờ recover/claim/publish."""
        with open(os.path.join(ROOT,
                               '.github/workflows/factory-liveness.yml'),
                  encoding='utf-8') as f:
            y = f.read()
        self.assertIn('contents: read', y)
        self.assertNotIn('contents: write', y)
        self.assertNotIn('git push', y)
        self.assertIn('cron: "0 */6 * * *"', y)
        self.assertIn('workflow_dispatch:', y)
        self.assertIn('scripts/factory/watchdog.py', y)
        self.assertIn('factory-operator.py status', y)
        code = '\n'.join(l for l in y.splitlines()
                       if not l.strip().startswith('#'))
        for bad in ('prepare-next', 'recover', '--refill',
                    'release-chunk', 'requeue', 'publish --ids'):
            self.assertNotIn(bad, code,
                              'liveness KHONG duoc mutate: %s' % bad)

    def test_s7_production_push_hotpath(self):
        """publish-drafts.yml (mô hình /vanchinh đơn giản): đường nóng
        PUSH main theo paths _drafts/** — chọn EXACT ID từ article_id
        frontmatter, tối đa 2 draft/push, claim prepare-next --ids (chỉ
        hàng PLANNED), qa --ids --scope fast (ngưỡng 75/70), publish
        --ids (chỉ hàng PASS), 1 commit publish; repair push: hàng
        WRITING/QA/REPAIR/PASS bỏ qua claim, qa chấm lại thẳng."""
        with open(os.path.join(ROOT, '.github/workflows/publish-drafts.yml'),
                  encoding='utf-8') as f:
            y = f.read()
        # trigger: push main paths _drafts/** + dispatch
        self.assertIn('workflow_dispatch:', y)
        self.assertIn('push:', y)
        self.assertIn('branches: [main]', y)
        self.assertIn('_drafts/**', y)
        self.assertNotIn('pull_request:', y)
        for line in y.splitlines():
            s = line.strip()
            if s.startswith('#') or not s:
                continue
            self.assertNotIn('cron', s.lower(),
                             'cron trong phan chay duoc: %s' % s)
        self.assertIn('group: publish-drafts', y)
        self.assertIn('cancel-in-progress: false', y)
        self.assertIn('contents: write', y)
        # hot path: chon EXACT ID tu article_id, toi da 2 draft/push,
        # template mau-nhap-bai-moi bi loai
        self.assertIn('article_id', y)
        self.assertIn('toi da 2 draft', y)
        self.assertIn('mau-nhap-bai-moi', y)
        # claim chi hang PLANNED; qa/publish --ids fast
        self.assertIn('prepare-next --ids', y)
        self.assertIn('qa --ids', y)
        self.assertIn('publish --ids', y)
        self.assertIn('--scope fast', y)
        self.assertIn('factory-operator.py', y)
        # hot path KHONG chay audit nang
        for heavy in ('verify --scope full', 'test_soak', 'test_hardening',
                      'capacity-audit', 'check-built-links'):
            self.assertNotIn(heavy, y,
                             'hot path KHONG chay audit nang: %s' % heavy)
        # REFILL DA RETIRE: KHONG stage batch, KHONG refill canonical,
        # KHONG trigger qua refill-request.json
        for refill_op in ('factory-operator.py refill', '--refill',
                          'stage-refill-batch',
                          'data/factory/refill-request.json'):
            self.assertNotIn(refill_op, y,
                             'refill KHONG duoc chay trong publish-drafts: '
                             '%s' % refill_op)
        # ten step khong chua ": " (bug YAML startup)
        for line in y.splitlines():
            s = line.strip()
            if s.startswith('- name: ') and ': ' in s[len('- name: '):]:
                self.fail('tên step chứa ": ": %s' % s)
        self.assertIn("PYTHONDONTWRITEBYTECODE: '1'", y)

    def test_s7_refill_workflow_retired(self):
        """factory-refill.yml đã retire theo lệnh chủ xe (KHÔNG refill
        tự động): file KHÔNG được quay lại; refill-request.json và
        refill-batches/ KHÔNG còn workflow trigger nào."""
        self.assertFalse(os.path.exists(os.path.join(
            ROOT, '.github/workflows/factory-refill.yml')),
            'factory-refill.yml da retire - KHONG quay lai')

    def test_s7_qa_step_fatal_crash(self):
        y = read_workflow()
        i = y.index('- name: QA cham diem')
        seg = y[i:y.index('- name: Publish (chi hang PASS')]
        self.assertIn('set -e', seg)
        self.assertNotIn('|| code=$?', seg)

    def test_s7_no_ai_no_secrets(self):
        for wf in ('quality-gate.yml', 'publish-drafts.yml',
                   'factory-liveness.yml', 'factory-publish-verify.yml'):
            with open(os.path.join(ROOT, '.github/workflows', wf),
                      encoding='utf-8') as f:
                y = f.read()
            for bad in ('api_key', 'API_KEY', 'sk-', 'OPENAI', 'MISTRAL',
                        'anthropic', 'secrets.'):
                self.assertNotIn(bad, y, '%s chua %s' % (wf, bad))

    def test_s7_publish_gate_canonical(self):
        """publish-gate.py vẫn là người xuất bản duy nhất (tham chiếu
        canonical từ factory-operator.py)."""
        with open(os.path.join(ROOT, 'scripts/factory/factory-operator.py'),
                  encoding='utf-8') as f:
            opsrc = f.read()
        self.assertIn("'scripts/factory/publish-gate.py'", opsrc)

    def test_s7_publishing_config_disabled(self):
        with open(os.path.join(ROOT, '_data/publishing.yml'),
                  encoding='utf-8') as f:
            pub = f.read()
        self.assertRegex(pub, r'(?m)^enabled:\s*false\s*$')


if __name__ == '__main__':
    unittest.main(verbosity=2)
