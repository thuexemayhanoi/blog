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
import importlib.util
import io
import json
import os
import re
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


class PublisherPushStatic(unittest.TestCase):
    """Commit/push của factory-publish.yml nay là script CANONICAL
    scripts/factory/publisher-push.py (hành vi động được kiểm bằng
    test_publisher_push.py trên origin bare thật: nothing-to-commit,
    non-FF bounded retry, KHÔNG force, guard giao-path chống rebase ghép
    sửa đổi vào bài đã publish, integrity sha256 == QA evidence). Ở đây
    chốt hợp đồng TĨNH của workflow + script."""

    def _src(self):
        with open(os.path.join(ROOT, 'scripts/factory/publisher-push.py'),
                  encoding='utf-8') as f:
            return f.read()

    def test_s6a_workflow_commit_step_uses_canonical_script(self):
        y = read_workflow()
        block = extract_run_block(
            y, 'Commit publish results (single commit per queue run)')
        self.assertIn('scripts/factory/publisher-push.py', block)
        self.assertIn('[automated txn]', block)
        # KHÔNG còn vòng push/rebase inline trong YAML
        for inline in ('until git push', 'git rebase', 'git push'):
            self.assertNotIn(inline, block)

    def test_s6b_script_bounded_retries_and_overlap_guard(self):
        src = self._src()
        self.assertIn('MAX_REBASES = 3', src)
        self.assertIn('upstream_overlap', src)
        self.assertIn('integrity_after_rebase', src)
        self.assertIn('integrity_before_push', src)
        self.assertIn('merge.directoryRenames=false', src)
        self.assertIn("'diff', '--name-only', '--no-renames'", src)

    def test_s6c_script_only_runs_in_actions_or_local_remotes(self):
        src = self._src()
        self.assertIn("GITHUB_ACTIONS", src)
        self.assertIn('FACTORY_PUSH_ALLOW_LOCAL', src)

    def test_s6d_no_force_push_static(self):
        y = read_workflow()
        self.assertNotIn('push -f', y)
        self.assertNotIn('git push --force', y)
        self.assertNotIn('--force', y.replace('force push', ''))
        src = self._src()
        self.assertNotIn('--force', src.replace('force push', ''))
        self.assertNotIn('+HEAD', src)
        self.assertNotIn('--force-with-lease', src)


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
    'factory-extract-rows.yml',
    'factory-liveness.yml',
    'factory-publish-verify.yml',
    'factory-publish.yml',
    'factory-refill.yml',
    'factory-soak.yml',
    'production-watchdog.yml',
    'quality-gate.yml',
]

RETIRED_WORKFLOWS = [
    'article-batch.yml',
    'factory-production.yml',
    'publish-drafts.yml',
    'factory-operator.yml',
    'factory-validate.yml',
    'factory-capacity-validate.yml',
    'factory-watchdog.yml',
    'publish-queue.yml',
    'weekly-maintenance.yml',
    'diag-factory-tests.yml',
    'custom-domain-migration.yml',
]


class StaticContract(unittest.TestCase):
    """Hợp đồng CHÍNH XÁC 8 workflow hiện tại (7 hợp đồng + helper
    factory-extract-rows; docs/factory-workflow-contract.md — kiến trúc port
    từ /vanchinh, gọn theo pattern /shop):
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
    article-batch.yml, custom-domain-migration.yml, ... — xem
    RETIRED_WORKFLOWS) đã RETIRE theo lệnh chủ xe và KHÔNG được quay lại.
    factory-refill.yml là workflow HIỆN TẠI (refill push-driven)."""

    def test_s7_workflow_contract(self):
        wf = sorted(f for f in os.listdir(os.path.join(ROOT,
                                                       '.github/workflows'))
                   if f.endswith('.yml'))
        self.assertEqual(wf, CURRENT_WORKFLOWS,
                         'hop dong CHINH XAC 8 workflow (7 hop dong + helper '
                         'factory-extract-rows) — khong them, '
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
        # Mutator được duyệt (2026-10-05): factory-publish.yml (publisher
        # bài — DUY NHẤT đi vào _posts/) và factory-refill.yml (phục hồi
        # theo lệnh chủ xe — chỉ mutate state refill: ledger/seed/matrix/
        # checkpoint/reports; KHÔNG bao giờ publish bài).
        for name in CURRENT_WORKFLOWS:
            y = wf_text(name)
            if name == 'factory-publish.yml':
                self.assertIn('contents: write', y)
                # commit/push của publisher sống trong CANONICAL
                # scripts/factory/publisher-push.py (testable, có guard
                # giao-path chống rebase ghép sửa đổi vào bài đã publish)
                self.assertIn('scripts/factory/publisher-push.py', y)
                self.assertNotIn('git push', y)
            elif name == 'factory-extract-rows.yml':
                # helper chỉ đọc matrix + commit các file báo cáo extracted-rows*
                self.assertIn('contents: write', y)
                self.assertIn("'data/factory/extract-request.json'", y)
                self.assertIn("'data/factory/extract-request-W*.json'", y)
                self.assertIn(
                    "git add -- 'reports/factory/extracted-rows*.json'", y)
                self.assertNotIn('git add -A', y)
                self.assertNotIn('publish-gate', y)
                self.assertNotIn('--force', y)
            elif name == 'factory-refill.yml':
                self.assertIn('contents: write', y)
                self.assertIn('git push', y)
                self.assertIn('git commit', y)
                # refill KHÔNG publish bài — publisher vẫn là DUY NHẤT
                self.assertNotIn('publish-gate', y)
                self.assertNotIn("op_publish", y)
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
            y.count("if: steps.mode.outputs.mode == 'full'"), 7,
            'build/links/canonical/draft-leak/sitemap/crawler CHỈ chạy ở '
            'mode full')

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
        # race push trùng: hàng PUBLISHED bị bỏ qua sạch (published_edits,
        # exit 0 GREEN no-op) — chỉ EXISTING/BLOCKED còn refuse fail-closed
        self.assertIn('published_edits', sel)
        self.assertIn("REFUSED_STATUSES = ('EXISTING', 'BLOCKED', 'REVIEW')",
                      sel)
        # template bài nhập mẫu bị loại khỏi selection (chuỗi GHÉP để
        # file test không chứa slug template nguyên vẹn — draft-leak
        # gate grep slug này trên cây build)
        self.assertIn("'mau' + '-nhap'", sel)
        # queue sắp theo thứ tự matrix (deterministic)
        self.assertIn('sorted(set(queue), key=lambda i: order[i])', sel)
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
        # chỉ publish các hàng PASS của pair (QA vẫn là cổng cứng)
        self.assertIn("'publish', '--ids', ','.join(passing)", fq)
        # pair đồng nhất: hàng in-flight trước, PLANNED sau
        self.assertIn('ordered_pairs(queue', fq)
        # resume-first là PER-WRITER (ở bước claim, writer-session.py): pair
        # FAIL -> recoverable, KHÔNG chặn pair/writer khác
        self.assertNotIn('blocked and any(', fq)
        self.assertNotIn('DEFERRED (engine resume-first', fq)
        # một pair lỗi KHÔNG rollback pair đã publish (recoverable riêng)
        self.assertIn("state['recoverable'].extend(failing)", fq)
        self.assertIn("state['published'].extend(passing)", fq)
        self.assertIn('FATAL rc=%s', fq)
        # guard fail-closed: KHÔNG publish khi còn transaction/lock
        guard = extract_run_block(
            y, 'Guard no pending transaction and no lock (fail-closed)')
        self.assertIn('writer-lock.active', guard)
        self.assertIn('active', guard)
        # commit/push deterministic state qua publisher-push.py; bounded
        # retry non-FF, never force (chi tiet: PublisherPushStatic)
        self.assertIn('[automated txn]', y)
        self.assertIn('scripts/factory/publisher-push.py', y)
        self.assertIn('push-selection.py', y)
        self.assertIn('--backlog', y)
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
        self.assertIn("'publish', '--ids', ','.join(passing)", fq)
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
        """publish-drafts.yml / factory-production.yml
        đã RETIRE (legacy, theo lệnh chủ xe): file KHÔNG được quay lại —
        factory-publish.yml là production publisher DUY NHẤT.
        (factory-refill.yml được chủ xe PHỤC HỒI 2026-10-05 — 55598ac1 —
        refill đẩy lên CI, commit đồng bộ một lần; KHÔNG phải legacy
        publisher.)"""
        for name in ('publish-drafts.yml', 'factory-production.yml'):
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
            # quy tac "workflow khong goi API ngoai, khong dung AI ma
            # nguon mo": khong ten nha cung cap AI / thu vien ML / cong cu
            # mang trong BAT KY workflow nao (khong phan biet hoa thuong)
            low = y.lower()
            for bad in ('mistral', 'openai', 'anthropic', 'chatgpt',
                        'gemini', 'llama', 'ollama', 'huggingface',
                        'transformers', 'sentence-transformers', 'torch',
                        'curl ', 'wget ', 'pip install', 'npm install',
                        'urllib.request', 'requests.get', 'requests.post',
                        'http.client'):
                self.assertNotIn(bad, low, '%s chua %s' % (wf, bad))
            # moi `uses:` chi la action cua GitHub (actions/*)
            for line in y.splitlines():
                st = line.strip()
                if st.startswith('- uses:') or st.startswith('uses:'):
                    self.assertRegex(st, r'uses:\s*actions/[\w-]+@',
                                     '%s: action ngoai GitHub: %s'
                                     % (wf, st))

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


class WorkflowTriggerContract(unittest.TestCase):
    """Hợp đồng trigger (review compat): publisher không có workflow_dispatch;
    chỉ production-watchdog có cron; gate chạy cho MỌI thay đổi workflow; mọi
    run gate độc lập (không run nào hủy run khác); engine-tests không bị che
    bởi job gate đỏ; push REFUSED làm đỏ run sau khi drain."""

    def test_publisher_has_no_dispatch_and_only_watchdog_has_cron(self):
        pub = '\n'.join(code_lines(wf_text('factory-publish.yml')))
        self.assertNotIn('workflow_dispatch', pub)
        for name in CURRENT_WORKFLOWS:
            code = '\n'.join(code_lines(wf_text(name)))
            has_cron = bool(re.search(
                r'^\s*(schedule|cron)\s*:|^\s*-\s*cron\s*:', code, re.M))
            self.assertEqual(has_cron, name == 'production-watchdog.yml',
                             '%s: cron chi duoc o production-watchdog' % name)

    def test_quality_gate_triggers_on_any_workflow_change(self):
        y = wf_text('quality-gate.yml')
        self.assertEqual(y.count("'.github/workflows/**'"), 2,
                         'push + pull_request deu phai co .github/workflows/**')

    def test_quality_gate_runs_are_independent(self):
        y = wf_text('quality-gate.yml')
        self.assertRegex(y, r'group:\s*quality-gate-\$\{\{[^}]*github\.sha')
        self.assertNotRegex(y, r'(?m)^\s+group:\s*quality-gate\s*$')
        self.assertIn('cancel-in-progress: false', y)

    def test_engine_tests_not_masked_by_a_red_gate_job(self):
        self.assertIn('!cancelled()', wf_text('quality-gate.yml'))

    def test_refused_push_fails_the_run_after_drain(self):
        y = wf_text('factory-publish.yml')
        self.assertIn("steps.select.outputs.refused == 'true'", y)
        self.assertIn('always()', y)


class EngineTestRunner(unittest.TestCase):
    """CI (quality-gate.yml, job engine-tests) chạy
    `python3 scripts/factory/run-tests.py --suites ci`. scripts/factory/queue.py
    (script legacy) che `queue` của stdlib nếu thư mục script còn trên sys.path:
    runner phải khởi động được ĐÚNG như CI, và mọi test_*.py phải thuộc một
    nhóm (không suite mồ côi bị bỏ qua âm thầm)."""

    def _runner(self):
        spec = importlib.util.spec_from_file_location(
            'run_tests_mod', os.path.join(ROOT, 'scripts/factory/run-tests.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_runner_starts_like_ci(self):
        r = subprocess.run(
            [sys.executable, 'scripts/factory/run-tests.py', '--suites', 'ci',
             '--only', 'test_gate_scope', '--jobs', '1'],
            cwd=ROOT, capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('1 suite, 1 PASS, 0 FAIL', r.stdout)

    def test_only_with_unknown_or_empty_selection_fails(self):
        for only in ('test_typo', 'test_built_links'):   # lạ / không thuộc ci
            r = subprocess.run(
                [sys.executable, 'scripts/factory/run-tests.py', '--suites',
                 'ci', '--only', only], cwd=ROOT, capture_output=True,
                text=True, timeout=60)
            self.assertEqual(r.returncode, 2, only + r.stdout)

    def test_every_suite_belongs_to_a_group(self):
        rt = self._runner()
        files = sorted(f[:-3] for f in os.listdir(os.path.join(
            ROOT, 'scripts/factory/tests'))
            if f.startswith('test_') and f.endswith('.py'))
        grouped = set(rt.CI) | set(rt.DATA) | set(rt.HEAVY)
        self.assertEqual([f for f in files if f not in grouped], [],
                         'suite mo coi: them vao CI/DATA/HEAVY trong run-tests.py')
        self.assertEqual([g for g in grouped if g not in files], [],
                         'nhom tro toi suite khong ton tai')
        self.assertEqual(len(rt.CI), len(set(rt.CI)), 'suite trung trong CI')

    def test_ci_workflow_runs_the_ci_group(self):
        y = wf_text('quality-gate.yml')
        self.assertIn('python3 scripts/factory/run-tests.py --suites ci', y)


if __name__ == '__main__':
    unittest.main(verbosity=2)
