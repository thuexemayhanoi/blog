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
  S6  Push block của factory-publish.yml mô phỏng bằng fake git: commit
      rồi mới push; push non-fast-forward => bounded retry (fetch +
      rebase, tối đa 3 lần thử) rồi FAIL; rebase conflict => abort
      ngay; không thay đổi => không commit; KHÔNG bao giờ force push
      (static).
  S7  Static: hợp đồng CHÍNH XÁC 5 workflow hiện tại — quality-gate.yml
      dual-mode + READ-ONLY; factory-publish.yml production publisher
      DUY NHẤT (turbo queue 2..10 draft/push chia pair 2, chọn EXACT
      ID từ article_id, claim chỉ hàng PLANNED, QA 75/70, KHÔNG
      refill, không AI/API secrets); factory-liveness.yml READ-ONLY
      fail-closed (dispatch, KHÔNG cron — pattern /shop
      no-scheduled-runs); factory-publish-verify.yml FULL audit +
      READ-ONLY; factory-soak.yml hermetic on-demand; các workflow đã
      retire (publish-drafts, article-batch (gộp vào liveness/
      publish-verify),
      factory-production, factory-refill, ...) KHÔNG quay lại;
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
    with open(os.path.join(ROOT, '.github/workflows/factory-publish.yml'),
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
    """Mô phỏng run-block commit của factory-publish.yml bằng fake git:
    pipeline đơn giản — commit 1 lần rồi push; push non-FF => bounded
    retry (fetch + rebase, tối đa 3 lần thử rồi FAIL — KHÔNG bao giờ
    force push); rebase conflict => abort ngay; không thay đổi =>
    không commit."""

    def setUp(self):
        self.work, self.tmp = fresh_copy()
        self.bin = os.path.join(self.tmp, 'bin')
        os.makedirs(self.bin)
        self.scen_path = os.path.join(self.tmp, 'scenario.json')
        self.git_log = os.path.join(self.tmp, 'git.log')
        self.verify_log = os.path.join(self.tmp, 'verify.log')
        self.block = extract_run_block(
            read_workflow(), 'Commit publish results (single commit per queue run)')
        # GitHub Actions thay ${{ }} trước khi bash chạy; làm giống engine
        # để bash chạy đúng ở local
        self.block = self.block.replace(
            '${{ steps.select.outputs.mode }}', 'new')
        self.block = self.block.replace(
            '${{ steps.select.outputs.queue }}', 'TESTIDS')
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

    def test_s6a_non_ff_bounded_retry_then_fail(self):
        r = self._run_block([
            {'args': ['push'], 'exit': 1,
             'err': 'non-fast-forward\n'},
            {'args': ['fetch', 'origin'], 'exit': 0},
            {'args': ['rebase', 'origin/main'], 'exit': 0},
            {'args': ['push'], 'exit': 1,
             'err': 'non-fast-forward\n'},
            {'args': ['fetch', 'origin'], 'exit': 0},
            {'args': ['rebase', 'origin/main'], 'exit': 0},
            {'args': ['push'], 'exit': 1,
             'err': 'non-fast-forward\n'},
        ])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        calls = self._git_calls()
        self.assertEqual(calls.count('CALL push'), 3,
                         'non-FF: toi da 3 lan thu — khong treo mai, '
                         'khong force')
        self.assertEqual(
            sum(1 for c in calls if c.startswith('CALL fetch origin')), 2,
            'moi retry phai fetch truth tuoi truoc khi rebase')
        self.assertEqual(
            sum(1 for c in calls if c == 'CALL rebase origin/main'), 2,
            'moi retry phai rebase len truth tuoi')
        self.assertNotIn('--force', '\n'.join(calls))

    def test_s6b_retry_recovers_then_success(self):
        r = self._run_block([
            {'args': ['push'], 'exit': 1,
             'err': 'non-fast-forward\n'},
            {'args': ['fetch', 'origin'], 'exit': 0},
            {'args': ['rebase', 'origin/main'], 'exit': 0},
            {'args': ['push'], 'exit': 0},
        ])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self._git_calls()
        i_commit = next(i for i, c in enumerate(calls)
                        if c.startswith('CALL commit'))
        i_push = next(i for i, c in enumerate(calls)
                      if c == 'CALL push')
        self.assertLess(i_commit, i_push, 'commit phai TRUOC push')
        self.assertEqual(calls.count('CALL push'), 2,
                         'thua race mot lan -> fetch+rebase -> push lai')
        # thu tu: push FAIL -> fetch -> rebase -> push OK
        self.assertEqual(calls[i_push + 1], 'CALL fetch origin main')
        self.assertEqual(calls[i_push + 2], 'CALL rebase origin/main')

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

    def test_s6e_rebase_conflict_aborts_cleanly(self):
        """Rebase conflict: abort NGAY, KHÔNG thử push lại, KHÔNG force."""
        r = self._run_block([
            {'args': ['push'], 'exit': 1,
             'err': 'non-fast-forward\n'},
            {'args': ['fetch', 'origin'], 'exit': 0},
            {'args': ['rebase', 'origin/main'], 'exit': 1,
             'err': 'CONFLICT\n'},
            {'args': ['rebase', '--abort'], 'exit': 0},
        ])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        calls = self._git_calls()
        self.assertEqual(calls.count('CALL push'), 1,
                         'rebase conflict phai STOP ngay')
        self.assertIn('CALL rebase --abort', calls,
                      'rebase conflict phai abort, khong de rebase dang treo')
        self.assertNotIn('--force', '\n'.join(calls))


# ------------------------------------------------------------------ S7
def wf_text(name):
    with open(os.path.join(ROOT, '.github/workflows', name),
              encoding='utf-8') as f:
        return f.read()


def code_lines(text):
    """Các dòng chạy được (bỏ comment) của một workflow."""
    return [l for l in text.splitlines()
            if l.strip() and not l.strip().startswith('#')]


CURRENT_WORKFLOWS = [
    'factory-liveness.yml',
    'factory-publish-verify.yml',
    'factory-publish.yml',
    'factory-soak.yml',
    'production-watchdog.yml',
    'quality-gate.yml',
]

RETIRED_WORKFLOWS = [
    'article-batch.yml',
    'factory-production.yml',
    'factory-refill.yml',
    'publish-drafts.yml',
    'factory-operator.yml',
    'factory-validate.yml',
    'factory-capacity-validate.yml',
    'factory-watchdog.yml',
    'publish-queue.yml',
    'weekly-maintenance.yml',
    'diag-factory-tests.yml',
]


class StaticContract(unittest.TestCase):
    """Hợp đồng CHÍNH XÁC 6 workflow hiện tại (docs/factory-workflow-
    contract.md — kiến trúc port từ /vanchinh, gọn theo pattern /shop):
      quality-gate.yml            — cong dual-mode read-only (push/PR)
      factory-publish.yml         — production publisher DUY NHẤT
                                   (push main _drafts/**, turbo queue
                                   2..10 draft/push, pair 2)
      factory-liveness.yml       — watchdog read-only fail-closed
                                   (workflow_dispatch, KHÔNG cron)
      factory-publish-verify.yml  — FULL audit read-only (dispatch)
      factory-soak.yml            — reliability/soak hermetic on-demand
      production-watchdog.yml     — Agent #6 wake 2h (lightweight,
                                   cron 30p, dry-run mặc định)
    Các workflow legacy (publish-drafts.yml, factory-production.yml,
    factory-refill.yml, article-batch.yml — dry-run gộp vào
    factory-liveness/factory-publish-verify, ...) đã RETIRE theo lệnh
    chủ xe và KHÔNG được quay lại."""

    def test_s7_workflow_contract(self):
        wf = sorted(f for f in os.listdir(os.path.join(ROOT,
                                                       '.github/workflows'))
                   if f.endswith('.yml'))
        self.assertEqual(wf, CURRENT_WORKFLOWS,
                         'hop dong CHINH XAC 6 workflow — khong them, '
                         'khong bot workflow ngoai danh sach')
        # các workflow/test đã retire KHÔNG quay lại
        for name in RETIRED_WORKFLOWS:
            self.assertFalse(
                os.path.exists(os.path.join(ROOT, '.github/workflows',
                                            name)),
                'workflow da retire khong duoc quay lai: %s' % name)
        self.assertFalse(os.path.exists(os.path.join(
            ROOT, 'scripts/factory/tests/test_push_rebase_overlap.py')),
            'test da retire khong duoc quay lai')

    def test_s7_single_publisher_single_mutator(self):
        """CHỈ factory-publish.yml được contents: write và CHỈ nó
        commit/push: mọi workflow khác đều READ-ONLY — KHÔNG publisher
        song song, KHÔNG mutator ẩn."""
        for name in CURRENT_WORKFLOWS:
            y = wf_text(name)
            if name == 'factory-publish.yml':
                self.assertIn('contents: write', y)
                self.assertIn('git push', y)
                self.assertIn('git commit', y)
            else:
                self.assertIn('contents: read', y)
                self.assertNotIn('contents: write', y)
                self.assertNotIn('git push', y)
                self.assertNotIn('git commit', y)

    def test_s7_quality_gate_fast_readonly(self):
        """quality-gate.yml dual-mode (port pattern /shop article-quality
        + qa_scope): content push = CHỈ validate FAST chunk; engine push
        /dispatch = + build + built-links + draft-leak + sitemap sanity.
        KHÔNG còn build + quét link toàn site cho MỌI push nội dung —
        kết thúc lớp lỗi 404 transient khi batch chưa publish xong."""
        y = wf_text('quality-gate.yml')
        self.assertIn('contents: read', y)
        self.assertNotIn('contents: write', y)
        self.assertNotIn('git push', y)
        self.assertIn('validate.py --scope chunk', y)
        self.assertIn('jekyll-build-pages', y)
        self.assertIn('check-built-links.py', y)
        self.assertIn('push:', y)          # trigger push main
        self.assertIn('pull_request:', y)  # trigger PR
        self.assertIn('workflow_dispatch:', y)
        # dual-mode: selector CANONICAL gate-scope.py quyết định chế độ
        self.assertIn('scripts/factory/gate-scope.py', y)
        self.assertEqual(
            y.count("if: steps.mode.outputs.mode == 'full'"), 4,
            'build/links/draft-leak/sitemap CHỈ chạy ở mode full')

    def test_s7_publish_hotpath(self):
        """factory-publish.yml — production publisher DUY NHẤT (mô hình
        /vanchinh turbo queue): push main theo paths _drafts/**, gọi
        CANONICAL selector scripts/factory/push-selection.py (queue tối
        đa 10 draft/push, chia pair 2), claim chỉ hàng PLANNED, qa/publish
        --ids --scope fast ngưỡng 75/70, resume-first, một pair lỗi
        KHÔNG rollback pair đã publish, bounded retry non-FF, KHÔNG bao
        giờ force push."""
        y = wf_text('factory-publish.yml')
        # trigger: push main paths _drafts/** — KHÔNG PR, KHÔNG cron
        self.assertIn('push:', y)
        self.assertIn('branches: [main]', y)
        self.assertIn('_drafts/**', y)
        self.assertNotIn('pull_request:', y)
        for line in code_lines(y):
            self.assertNotIn('cron', line.lower(),
                             'cron trong phan chay duoc: %s' % line)
        # concurrency: publisher concurrency = 1, KHONG cancel run dang chay
        self.assertIn('group: factory-publish', y)
        self.assertIn('cancel-in-progress: false', y)
        self.assertIn('contents: write', y)
        self.assertIn("PYTHONDONTWRITEBYTECODE: '1'", y)
        # CANONICAL selector: workflow gọi push-selection.py; KHÔNG còn
        # selector Python inline trùng lặp trong YAML (một nguồn sự thật)
        self.assertIn('scripts/factory/push-selection.py', y)
        for line in code_lines(y):
            for stale in ('article_id', 'trung nhau trong cung mot push',
                          'toi da 10', 'khong co trong matrix',
                          'da xong/khoa', 'production-control paused',
                          'sorted(queue'):
                self.assertNotIn(
                    stale, line,
                    'selector inline TRÙNG LẶP trong YAML (business rule '
                    'phải sống trong push-selection.py): %s' % line)
        with open(os.path.join(ROOT, 'scripts/factory/push-selection.py'),
                  encoding='utf-8') as f:
            sel = f.read()
        # queue 2..10: chọn EXACT ID từ article_id, REFUSE fail-closed
        self.assertIn('MAX_QUEUE_PER_PUSH = 10', sel)
        self.assertIn('len(queue) > MAX_QUEUE_PER_PUSH', sel)
        self.assertIn('article_id', sel)
        self.assertIn('id trung nhau trong cung mot push', sel)
        self.assertIn('id khong co trong matrix', sel)
        self.assertIn("'PUBLISHED', 'EXISTING', 'BLOCKED'", sel)
        # template bài nhập mẫu bị loại khỏi selection (chuỗi GHÉP để
        # file test không chứa slug template nguyên vẹn — draft-leak
        # gate grep slug này trên cây build)
        self.assertIn("'mau' + '-nhap'", sel)
        # queue sắp theo thứ tự matrix (deterministic)
        self.assertIn('sorted(queue, key=lambda i: order[i])', sel)
        # production-control enabled=false: exit sạch TRƯỚC claim
        self.assertIn('production-control paused', sel)
        # mode: new (cần claim) / repair (KHÔNG claim lại từ đầu)
        self.assertIn("mode = 'new' if needs_claim else 'repair'", sel)
        self.assertIn("'PLANNED'", sel)
        # pair size = 2: pair count deterministic của canonical selector
        self.assertIn('PAIR_SIZE = 2', sel)
        self.assertIn('(len(queue) + 1) // 2', sel)
        # consume của workflow GỌI CANONICAL queue processor — KHÔNG còn
        # implementation queue inline thứ hai trong YAML (một nguồn sự
        # thật; port Phase 3 multi-writer từ /vanchinh)
        self.assertIn('scripts/factory/factory-queue.py run', y)
        self.assertIn('factory-operator.py', y)
        with open(os.path.join(ROOT, 'scripts/factory/factory-queue.py'),
                  encoding='utf-8') as f:
            fq = f.read()
        # consume của processor chia pair 2, tuần tự, deterministic
        self.assertIn('PAIR_SIZE = 2', fq)
        self.assertIn('[queue[i:i + pair_size]', fq)
        # claim CHỈ hàng PLANNED; qa/publish --ids fast
        self.assertIn("planned = [i for i in pair if st[i] == 'PLANNED']",
                      fq)
        self.assertIn("'prepare-next', '--ids', ','.join(planned)", fq)
        self.assertIn("'qa', '--ids', label, '--scope', 'fast'", fq)
        self.assertIn("'publish', '--ids', label, '--scope', 'fast'", fq)
        # resume-first: pair FAIL -> recoverable, KHÔNG claim pair mới
        self.assertIn('DEFERRED (engine resume-first', fq)
        self.assertIn('blocked and any(', fq)
        # một pair lỗi KHÔNG rollback pair đã publish (recoverable riêng)
        self.assertIn("state['recoverable'].extend(pair)", fq)
        self.assertIn("state['published'].extend(pair)", fq)
        self.assertIn('FATAL rc=%s', fq)
        # guard fail-closed: KHÔNG publish khi còn transaction/lock
        guard = extract_run_block(
            y, 'Guard no pending transaction and no lock (fail-closed)')
        self.assertIn('writer-lock.active', guard)
        self.assertIn('active', guard)
        # commit/push deterministic state; bounded retry non-FF, never force
        self.assertIn('git add -A', y)
        self.assertIn('[automated txn]', y)
        self.assertIn('until git push', y)
        self.assertIn('"$n" -ge 3', y)
        self.assertIn('git rebase origin/main', y)
        self.assertNotIn('--force', y.replace('force push', ''))
        # cuối run: state sạch (không lock, không txn active)
        clean = extract_run_block(y, 'Assert clean factory state')
        self.assertIn('writer-lock.active', clean)
        self.assertIn('active', clean)
        # hot path KHÔNG chay audit nang
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
                             'refill KHONG duoc chay trong hot publish: '
                             '%s' % refill_op)
        # ten step khong chua ": " (bug YAML startup)
        for line in y.splitlines():
            s = line.strip()
            if s.startswith('- name: ') and ': ' in s[len('- name: '):]:
                self.fail('tên step chứa ": ": %s' % s)

    def test_s7_consume_step_fail_closed(self):
        """Consume loop: qa/publish chạy với check=True — exit code
        KHÔNG được nuốt; lỗi hạ tầng là FATAL (dừng cả run), lỗi nội
        dung mới là recoverable."""
        y = wf_text('factory-publish.yml')
        block = extract_run_block(
            y, 'Consume write-ahead queue (pair claim QA publish sequential)')
        self.assertIn('scripts/factory/factory-queue.py run', block)
        self.assertNotIn('|| true', block)
        # fail-closed sống trong CANONICAL processor (KHÔNG còn inline)
        with open(os.path.join(ROOT, 'scripts/factory/factory-queue.py'),
                  encoding='utf-8') as f:
            fq = f.read()
        self.assertIn("'qa', '--ids', label, '--scope', 'fast'", fq)
        self.assertIn("'publish', '--ids', label, '--scope', 'fast'", fq)
        self.assertIn('check=True', fq)
        self.assertNotIn('|| true', fq)

    def test_s7_liveness_readonly_never_recovers(self):
        """factory-liveness.yml: CHỈ workflow_dispatch (KHÔNG cron —
        pattern /shop no-scheduled-runs), READ-ONLY thuần — watchdog +
        status + purity; unhealthy PHẢI FAIL run (fail-closed, KHÔNG
        chỉ warning rồi xanh); KHÔNG bao giờ recover/claim/qa/publish."""
        y = wf_text('factory-liveness.yml')
        self.assertIn('contents: read', y)
        self.assertNotIn('contents: write', y)
        self.assertNotIn('git push', y)
        self.assertNotIn('cron:', y)
        self.assertNotIn('schedule:', y)
        self.assertIn('workflow_dispatch:', y)
        self.assertIn('scripts/factory/watchdog.py', y)
        self.assertIn('factory-operator.py status', y)
        self.assertNotIn('continue-on-error', y)
        # watchdog step: set -eu, KHÔNG nuốt exit code (unhealthy = FAIL)
        wd = extract_run_block(y, 'Watchdog (unhealthy = FAIL run')
        self.assertIn('set -eu', wd)
        self.assertIn('watchdog.py', wd)
        self.assertNotIn('|| true', wd)
        code = '\n'.join(code_lines(y))
        for bad in ('prepare-next', 'recover', '--refill',
                    'release-chunk', 'requeue', 'qa --ids', 'publish --ids'):
            self.assertNotIn(bad, code,
                              'liveness KHONG duoc mutate: %s' % bad)

    def test_s7_soak_hermetic_readonly(self):
        """factory-soak.yml: CHỈ workflow_dispatch (không cron/push),
        contents: read, chạy test_soak_recovery.py trên fixture hermetic
        — KHÔNG đụng production state, KHÔNG commit/push."""
        y = wf_text('factory-soak.yml')
        self.assertIn('workflow_dispatch:', y)
        self.assertNotIn('cron:', y)
        code = '\n'.join(code_lines(y))
        self.assertNotIn('push:', code)
        self.assertIn('contents: read', y)
        self.assertNotIn('contents: write', y)
        self.assertIn('scripts/factory/tests/test_soak_recovery.py', y)
        for bad in ('prepare-next', 'requeue', 'release-chunk', '--refill',
                    'qa --ids', 'publish --ids', 'git commit', 'git push'):
            self.assertNotIn(bad, code,
                             'soak phai HERMETIC/READ-ONLY: %s' % bad)
        # purity: working tree sach (khong mutation production state)
        self.assertIn('git status --porcelain', y)

    def test_s7_production_watchdog_lightweight(self):
        """production-watchdog.yml (Agent #6): lightweight scheduled —
        cron 30 phút là KIỂM TRA periodic read-mostly (KHÔNG phải bản
        6h liveness full đã retire); contents: read; KHÔNG commit/push;
        chạy production-watchdog.py DRY-RUN — workflow KHÔNG BAO GIỜ
        kích hoạt production; KHÔNG build/link scan/full QA; KHÔNG
        repair; KHÔNG đụng queue/writer trực tiếp."""
        y = wf_text('production-watchdog.yml')
        self.assertIn('contents: read', y)
        self.assertNotIn('contents: write', y)
        self.assertNotIn('git push', y)
        self.assertNotIn('git commit', y)
        self.assertIn("cron: '*/30 * * * *'", y)
        self.assertIn('workflow_dispatch:', y)
        self.assertIn('scripts/factory/production-watchdog.py', y)
        self.assertIn('--dry-run', y)
        self.assertNotIn('--wake', y)   # ship dry-run: KHÔNG wake thật
        code = '\n'.join(code_lines(y))
        for bad in ('prepare-next', 'requeue', 'release-chunk', '--refill',
                    'qa --ids', 'publish --ids', 'writer-claim.py claim',
                    'jekyll', 'check-built-links', 'validate.py'):
            self.assertNotIn(bad, code,
                             'watchdog phai LIGHTWEIGHT/READ-ONLY: %s' % bad)

    def test_s7_publish_verify_full_audit_readonly(self):
        """factory-publish-verify.yml: FULL audit read-only, CHỈ
        workflow_dispatch (không cron): watchdog + verify full + refill
        gates + sitemap plan + generator drift/idempotency + Jekyll
        build + built-link deep + draft-leak + hub/pagination render;
        cuối run working tree sạch; KHÔNG commit/push."""
        y = wf_text('factory-publish-verify.yml')
        self.assertIn('contents: read', y)
        self.assertNotIn('contents: write', y)
        self.assertNotIn('git push', y)
        self.assertNotIn('git commit', y)
        self.assertNotIn('cron:', y)
        self.assertIn('workflow_dispatch:', y)
        self.assertIn('factory-operator.py verify --scope full', y)
        self.assertIn('scripts/factory/watchdog.py', y)
        self.assertIn('refill-queue.py --verify', y)
        self.assertIn('--selftest', y)
        self.assertIn('sitemap-plan.py', y)
        # generator drift/idempotency checks
        self.assertIn('restore-foundation.py', y)
        self.assertIn('generate-matrix.py', y)
        self.assertIn('expand-topic-universe.py', y)
        self.assertIn('generate-listing-pages.py', y)
        self.assertIn('git checkout --', y)
        # Jekyll build + built-link deep + draft-leak + hub/pagination
        self.assertIn('jekyll-build-pages', y)
        self.assertIn('check-built-links.py', y)
        tpl = 'mau' + '-nhap' + '-bai' + '-moi'
        self.assertIn(tpl, y)
        self.assertIn('trang/2', y)
        self.assertIn('post-card', y)
        # cuối run working tree phải sạch
        self.assertIn('git status --porcelain', y)

    def test_s7_legacy_publishers_retired(self):
        """publish-drafts.yml / factory-production.yml / factory-refill.yml
        đã RETIRE (legacy, theo lệnh chủ xe): file KHÔNG được quay lại —
        factory-publish.yml là production publisher DUY NHẤT."""
        for name in ('publish-drafts.yml', 'factory-production.yml',
                     'factory-refill.yml'):
            self.assertFalse(
                os.path.exists(os.path.join(ROOT, '.github/workflows',
                                            name)),
                '%s da retire - KHONG quay lai' % name)

    def test_s7_no_ai_no_secrets(self):
        for wf in CURRENT_WORKFLOWS:
            y = wf_text(wf)
            # 'secrets.' hoi thua: header factory-publish.yml ghi "NO
            # secrets." (claim, khong phai usage). Cấm thật là truy cập
            # secret cua GitHub Actions va key AI trong moi workflow.
            for bad in ('api_key', 'API_KEY', 'sk-', 'OPENAI', 'MISTRAL',
                        'anthropic', '${{ secrets.'):
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
