#!/usr/bin/env python3
"""Negative provenance/QA tests. All bytes and rows are hermetic fixtures."""
import copy
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'audit-legacy-qa.py'
spec = importlib.util.spec_from_file_location('legacy_audit_test', SCRIPT)
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_qa_modes import FxTestCase, matrix_rows


class LegacyEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.old = b'---\ntitle: Safe rental guide\n---\nRead [price](/blog/bang-gia/).'
        self.current = A.migrated(self.old)
        self.old_row = dict(zip(A.FP_FIELDS, ['Safe rental guide', 'price comparison',
                            'rental price', '/blog/price/', '_posts/price.md', '/blog/price/']))
        self.row = {k: A.migrated(v.encode()).decode() for k, v in self.old_row.items()}
        self.row['id'] = 'BLG-90001'
        self.ev = {'content_sha256': A.sha(self.old),
                   'matrix_row_sha256': A.fingerprint(self.old_row)}
        self.fresh = dict(article_id=self.row['id'], result='PASS', quality=100,
                          seo=100, business_fact='PASS', legal='NOT_REQUIRED',
                          critical_failure=False, content_sha256=A.sha(self.current),
                          matrix_row_sha256=A.fingerprint(self.row))

    def classification(self, current=None, ev=None):
        return A.classify(self.row, self.current if current is None else current,
                          ev or self.ev, self.old_row, self.old, self.ev)['classification']

    def decision(self, fresh):
        return A.proposal_decision('DOMAIN_ONLY_PROVEN', fresh, self.current,
                                   self.row, 75, 70)

    def test_domain_only_is_proposal_not_attestation(self):
        self.assertEqual(self.classification(), 'DOMAIN_ONLY_PROVEN')
        self.assertEqual(self.decision(self.fresh),
                         'ELIGIBLE_PROPOSAL_AWAITING_OWNER_APPROVAL')

    def test_prose_or_whitespace_change_cannot_be_hidden_by_domain_normalization(self):
        for extra in [b'\n', b' Guaranteed free rental.']:
            self.assertEqual(self.classification(self.current + extra), 'CONTENT_OR_MATRIX_CHANGE')

    def test_forged_old_hash_is_not_provenance(self):
        bad = dict(self.ev, content_sha256='0' * 64, result='PASS', quality=100, seo=100)
        self.assertEqual(self.classification(ev=bad), 'BASELINE_EVIDENCE_UNBOUND')

    def test_matrix_intent_change_is_not_domain_only(self):
        self.row['intent'] = 'different search intent'
        self.assertEqual(self.classification(), 'CONTENT_OR_MATRIX_CHANGE')

    def test_pass_label_cannot_override_bad_actual_qa(self):
        for bad in [dict(self.fresh, quality=74), dict(self.fresh, seo=69),
                    dict(self.fresh, business_fact='FAIL'), dict(self.fresh, legal='FAIL'),
                    dict(self.fresh, critical_failure=True), dict(self.fresh, result='REPAIR')]:
            self.assertEqual(self.decision(bad), 'FRESH_QA_FAILED')

    def test_pass_for_other_bytes_row_or_article_is_refused(self):
        for key in ('content_sha256', 'matrix_row_sha256', 'article_id'):
            self.assertEqual(self.decision(dict(self.fresh, **{key: 'forged'})), 'FRESH_QA_UNBOUND')

    def test_real_change_cannot_be_eligible_even_if_new_qa_passes(self):
        self.assertEqual(A.proposal_decision('CONTENT_OR_MATRIX_CHANGE', self.fresh,
                         self.current, self.row, 75, 70), 'MANUAL_REVIEW_REQUIRED')

    def test_no_evidence_mutation(self):
        before = copy.deepcopy((self.ev, self.fresh, self.row))
        self.classification()
        self.decision(self.fresh)
        self.assertEqual((self.ev, self.fresh, self.row), before)


def _git(cwd, *args):
    r = subprocess.run(['git', '-c', 'commit.gpgsign=false', '-c', 'user.name=t',
                        '-c', 'user.email=t@t'] + list(args), cwd=cwd,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


class DirtyTreeTest(unittest.TestCase):
    """Codex P2 (vòng 7): `head` chỉ gắn được với kết quả khi các đầu vào (matrix, bài,
    evidence, scorer, business facts, taxonomy) đọc từ cây làm việc KHỚP HEAD."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='audit-dirty-')
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        os.makedirs(os.path.join(self.d, 'scripts/factory'))
        shutil.copy(SCRIPT, os.path.join(self.d, 'scripts/factory/audit-legacy-qa.py'))
        os.makedirs(os.path.join(self.d, 'data'))
        with open(os.path.join(self.d, 'data/x.txt'), 'w') as f:
            f.write('v1\n')
        _git(self.d, 'init', '-q')
        _git(self.d, 'add', '-A')
        _git(self.d, 'commit', '-q', '-m', 'base')

    def test_dirty_inputs_reports_tracked_changes_and_untracked_inputs_only(self):
        self.assertEqual(A.dirty_inputs(self.d), [])
        with open(os.path.join(self.d, 'data/x.txt'), 'w') as f:
            f.write('v2\n')
        self.assertTrue(any('data/x.txt' in line for line in A.dirty_inputs(self.d)))
        _git(self.d, 'checkout', '-q', '--', 'data/x.txt')
        self.assertEqual(A.dirty_inputs(self.d), [])
        os.makedirs(os.path.join(self.d, '_posts'))
        with open(os.path.join(self.d, '_posts/new.md'), 'w') as f:
            f.write('x')
        with open(os.path.join(self.d, 'notes.txt'), 'w') as f:
            f.write('outside the input directories')
        listed = A.dirty_inputs(self.d)
        self.assertTrue(any('_posts/new.md' in line for line in listed), listed)
        self.assertFalse(any('notes.txt' in line for line in listed), listed)

    def test_guard_mirrors_what_the_scorer_reads(self):
        """Review độc lập: canonical_routes() đọc `permalink:` của MỌI .md/.html ngoài
        các thư mục bị loại — một trang untracked ở ngoài INPUT_DIRS lật được
        `links_routes_valid`/`critical_failure` mà guard cũ không thấy; ngược lại
        `_drafts/` không bao giờ được đọc nên draft untracked của writer không được
        làm audit từ chối."""
        def touch(rel, text='x'):
            full = os.path.join(self.d, rel)
            os.makedirs(os.path.dirname(full) or self.d, exist_ok=True)
            with open(full, 'w', encoding='utf-8') as f:
                f.write(text)
        flagged = ['zz-untracked-page.md', 'listing/new.md', 'thue-xe/x.html',
                   'trang-đẹp.md', 'data/anything.json', 'scripts/helper.py',
                   '_posts/2026-10-12-x.md']
        ignored = ['_drafts/2026-10-12-wip.md', 'docs/note.md', 'reports/r.md',
                   'assets/page.html', 'en/page.md', 'notes.txt', 'out.json']
        for rel in flagged + ignored:
            touch(rel)
        listed = A.dirty_inputs(self.d)
        for rel in flagged:
            self.assertTrue(any(line.endswith(' ' + rel) for line in listed), (rel, listed))
        for rel in ignored:
            self.assertFalse(any(line.endswith(' ' + rel) for line in listed), (rel, listed))

    def test_cli_refuses_a_dirty_tree_before_reading_any_input(self):
        with open(os.path.join(self.d, 'data/x.txt'), 'w') as f:
            f.write('edited after the checkout\n')
        r = subprocess.run([sys.executable, os.path.join(self.d, 'scripts/factory/audit-legacy-qa.py'),
                            '--baseline', 'HEAD', '--rescore-stale'],
                           cwd=self.d, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out['code'], 'DIRTY_TREE')
        self.assertTrue(out['dirty'])
        self.assertNotIn('Traceback', r.stderr)
        # --allow-dirty is the explicit opt-out: it is not refused as DIRTY_TREE (it then
        # fails on the missing matrix of this toy repo, which proves nothing was read before)
        r = subprocess.run([sys.executable, os.path.join(self.d, 'scripts/factory/audit-legacy-qa.py'),
                            '--baseline', 'HEAD', '--allow-dirty'],
                           cwd=self.d, capture_output=True, text=True)
        self.assertNotIn('DIRTY_TREE', r.stdout)


class RealScorerTest(FxTestCase):
    def test_forged_pass_and_matching_hashes_cannot_sanitize_bad_business_fact(self):
        rows = matrix_rows(self.fx)
        row = next(r for r in rows if r['status'] == 'PUBLISHED')
        path = pathlib.Path(self.fx) / row['output_path']
        # Dangerous data only in the disposable fixture, never production.
        current = path.read_bytes() + '\nGiá thuê được cam kết là 9.876.543đ.\n'.encode()
        path.write_bytes(current)
        old = current.replace(b'](/', b'](/blog/')
        old_row = dict(row)
        for key in ('expected_url', 'canonical_url'):
            old_row[key] = '/blog' + row[key]
        forged = {'article_id': row['id'], 'result': 'PASS', 'quality': 100,
                  'seo': 100, 'business_fact': 'PASS', 'legal': 'NOT_REQUIRED',
                  'critical_failure': False, 'content_sha256': A.sha(old),
                  'matrix_row_sha256': A.fingerprint(old_row)}
        classified = A.classify(row, current, forged, old_row, old, forged)
        self.assertEqual(classified['classification'], 'DOMAIN_ONLY_PROVEN')
        cwd = os.getcwd()
        try:
            spec = importlib.util.spec_from_file_location('fixture_legacy_scorer',
                pathlib.Path(self.fx) / 'scripts/factory/factory-operator.py')
            op = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(op)
            biz = json.loads((pathlib.Path(self.fx) / 'data/business-facts.json').read_text())
            tax = json.loads((pathlib.Path(self.fx) / 'data/content-taxonomy.json').read_text())
            fresh = A.rescore_published(op, row, rows, biz, tax)
        finally:
            os.chdir(cwd)
        self.assertEqual(fresh['business_fact'], 'FAIL')
        self.assertEqual(A.proposal_decision(classified['classification'], fresh,
                         current, row, op.QUALITY_MIN, op.SEO_MIN), 'FRESH_QA_FAILED')
        self.assertEqual(path.read_bytes(), current, 'read-only rescore changed the post')

    def _fixture_scorer(self):
        spec = importlib.util.spec_from_file_location('fixture_legacy_scorer2',
            pathlib.Path(self.fx) / 'scripts/factory/factory-operator.py')
        op = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(op)
        biz = json.loads((pathlib.Path(self.fx) / 'data/business-facts.json').read_text())
        tax = json.loads((pathlib.Path(self.fx) / 'data/content-taxonomy.json').read_text())
        return op, biz, tax

    def test_rescore_uses_the_approved_amount_whitelist(self):
        """Codex P1: qa_check_one dựa vào APPROVED_AMOUNTS (build_amount_whitelist
        điền, như operator.main/writer-loop). Rescore từng bỏ bước đó nên MỌI số
        tiền bị coi chưa duyệt (87 FAIL giả). Số đã duyệt phải PASS; số lạ vẫn FAIL."""
        rows = matrix_rows(self.fx)
        cwd = os.getcwd()
        try:
            op, biz, tax = self._fixture_scorer()
            self.assertEqual(len(op.APPROVED_AMOUNTS), 0, 'module moi: chua khoi tao')
            row = None
            for cand in rows:
                if cand['status'] != 'PUBLISHED':
                    continue
                if A.rescore_published(op, cand, rows, biz, tax).get('business_fact') == 'PASS':
                    row = cand
                    break
            self.assertIsNotNone(row, 'fixture phai co mot bai PUBLISHED dat business_fact')
            path = pathlib.Path(self.fx) / row['output_path']
            base = path.read_bytes()
            approved = next(v for r in biz['approved_pricing'].values()
                            if isinstance(r, dict) and isinstance(r.get('day'), int)
                            for v in [r['day']])
            shown = '{:,}'.format(approved).replace(',', '.')
            path.write_bytes(base + ('\nGiá thuê tham khảo %s đồng một ngày.\n' % shown).encode())
            op2, _, _ = self._fixture_scorer()
            fresh = A.rescore_published(op2, row, rows, biz, tax)
            self.assertEqual(fresh['non_approved_amounts'], [], fresh['non_approved_amounts'])
            self.assertEqual(fresh['business_fact'], 'PASS')
            path.write_bytes(base + '\nGiá thuê được cam kết là 9.876.543 đồng.\n'.encode())
            op3, _, _ = self._fixture_scorer()
            fresh = A.rescore_published(op3, row, rows, biz, tax)
            self.assertEqual(fresh['business_fact'], 'FAIL')
            self.assertIn(9876543, fresh['non_approved_amounts'])
        finally:
            os.chdir(cwd)

    def test_rescore_does_not_depend_on_the_callers_working_directory(self):
        """Codex P2 (vòng 3): qa_check_one mở `output_path` TƯƠNG ĐỐI theo cwd của
        người gọi. CLI chạy được từ nơi khác chỉ nhờ operator `chdir` lúc import;
        `rescore_published` là hàm thư viện (tool re-attest, test) nên phải tự giải
        đường dẫn từ gốc repo của scorer và TRẢ cwd lại như cũ."""
        rows = matrix_rows(self.fx)
        row = next(r for r in rows if r['status'] == 'PUBLISHED')
        cwd = os.getcwd()
        try:
            op, biz, tax = self._fixture_scorer()
            here = A.rescore_published(op, row, rows, biz, tax)
            self.assertNotEqual(here.get('result'), 'NO_DRAFT', here)
            with tempfile.TemporaryDirectory() as elsewhere:
                os.chdir(elsewhere)
                there = A.rescore_published(op, row, rows, biz, tax)
                self.assertEqual(os.path.realpath(os.getcwd()),
                                 os.path.realpath(elsewhere),
                                 'rescore khong duoc doi cwd cua nguoi goi')
        finally:
            os.chdir(cwd)
        drop = lambda ev: {k: v for k, v in ev.items() if k != 'scored_at'}
        self.assertEqual(drop(there), drop(here))


if __name__ == '__main__':
    unittest.main(verbosity=2)
