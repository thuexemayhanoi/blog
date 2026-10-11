#!/usr/bin/env python3
"""Negative provenance/QA tests. All bytes and rows are hermetic fixtures."""
import copy
import importlib.util
import json
import os
import pathlib
import sys
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
