#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test gate dual-mode: scripts/factory/gate-scope.py + wiring workflow.

Port pattern /shop (scripts/qa_scope.py + test_scoped_qa_workflow.py),
adapter /blog. Chứng minh hợp đồng dual-mode của Quality gate:

  - content push (drafts/posts/matrix/QA evidence/state/reports)
    → CHỈ validate FAST scope chunk; KHÔNG build + KHÔNG quét link
    toàn site mỗi cycle (nguồn 3 Quality gate failure transient
    2026-10-03: bài đã publish link bài cùng batch chưa publish).
  - engine push (scripts/layouts/includes/data/config/workflow/docs/
    matrix-seed/production-control) hoặc dispatch/base không rõ
    → FULL: validate chunk + build + built-links + draft-leak +
    sitemap/schema/hub sanity.
  - fail-closed: danh sách rỗng, file mất, path lạ → full.

Chạy: python3 scripts/factory/tests/test_gate_scope.py (từ gốc repository)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

GATE = os.path.join(ROOT, 'scripts', 'factory', 'gate-scope.py')
WF = os.path.join(ROOT, '.github', 'workflows', 'quality-gate.yml')


def gate_mod():
    spec = importlib.util.spec_from_file_location('gate_scope_test', GATE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_cli(paths, scope='auto'):
    """Chạy gate-scope.py CLI đúng như workflow gọi."""
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False,
                                     encoding='utf-8') as f:
        f.write('\n'.join(paths) + ('\n' if paths else ''))
        changed = f.name
    try:
        r = subprocess.run(
            [sys.executable, GATE, '--changed-files', changed,
             '--scope', scope],
            capture_output=True, text=True, cwd=ROOT)
        return r.returncode, json.loads(r.stdout)
    finally:
        os.unlink(changed)


class TestGateScopeClassify(unittest.TestCase):

    def setUp(self):
        self.m = gate_mod()

    def test_content_push_drafts_matrix_state(self):
        # push sản xuất điển hình: drafts + writer-claims + QA evidence
        mode, _ = self.m.classify([
            '_drafts/2026-10-03-xe-a.md',
            '_drafts/2026-10-03-xe-b.md',
            'data/state/writer-claims.json',
            'data/state/checkpoint.json',
            'data/qa/BLG-01160.json',
            'data/content-matrix.csv',
        ])
        self.assertEqual(mode, 'content')

    def test_content_push_publish_results(self):
        # commit kết quả publish của factory-publish.yml
        mode, _ = self.m.classify([
            '_posts/2026-10-03-xe-a.md',
            '_posts/2026-10-03-xe-b.md',
            'data/content-matrix.csv',
            'data/qa/BLG-01161.json',
            'data/state/checkpoint.json',
            'data/state/transaction.json',
            'reports/factory/factory-queue-last-run.json',
        ])
        self.assertEqual(mode, 'content')

    def test_engine_files_force_full(self):
        for engine in (
            ['scripts/factory/factory-operator.py'],
            ['_config.yml'],
            ['_layouts/post.html'],
            ['_includes/header.html'],
            ['_data/navigation.yml'],
            ['.github/workflows/quality-gate.yml'],
            ['docs/PROC-PUBLISH.md'],
            ['data/state/matrix-seed.json'],
            ['data/factory/production-control.json'],
        ):
            mode, reason = self.m.classify(engine)
            self.assertEqual(mode, 'full', '%s phải là full (%s)'
                             % (engine, reason))

    def test_mixed_content_engine_is_full(self):
        mode, _ = self.m.classify([
            '_posts/2026-10-03-xe-a.md',
            'scripts/factory/validate.py',
        ])
        self.assertEqual(mode, 'full')

    def test_empty_or_unknown_fail_closed(self):
        self.assertEqual(self.m.classify([])[0], 'full')
        self.assertEqual(self.m.classify(None)[0], 'full')
        # path ngoài hợp đồng content (ví dụ README) → full
        self.assertEqual(self.m.classify(['README.md'])[0], 'full')
        self.assertEqual(self.m.classify(['assets/css/x.css'])[0], 'full')

    def test_cli_forced_full_dispatch(self):
        rc, out = run_cli(['_drafts/x.md'], scope='full')
        self.assertEqual(rc, 0)
        self.assertEqual(out['mode'], 'full')

    def test_cli_content_and_missing_file_fail_closed(self):
        rc, out = run_cli(['_drafts/x.md', 'data/content-matrix.csv'])
        self.assertEqual(rc, 0)
        self.assertEqual(out['mode'], 'content')
        # file changed không tồn tại → rỗng → full (fail-closed)
        r = subprocess.run(
            [sys.executable, GATE, '--changed-files', '/no/such/file',
             '--scope', 'auto'],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)['mode'], 'full')


class TestQualityGateWiring(unittest.TestCase):
    """Workflow phải gọi gate-scope.py và điều kiện các step nặng
    theo mode — không còn build+quét link toàn site cho mọi push."""

    def test_workflow_wires_dual_mode(self):
        y = open(WF, encoding='utf-8').read()
        # selector CANONICAL, không phải logic inline trong YAML
        self.assertIn('scripts/factory/gate-scope.py', y)
        self.assertIn("echo \"mode=$MODE\" >> \"$GITHUB_OUTPUT\"", y)
        # 4 step nặng phải điều kiện theo mode == full
        self.assertEqual(
            y.count("if: steps.mode.outputs.mode == 'full'"), 4,
            'build/links/draft-leak/sitemap phải chạy CHỈ ở mode full')
        for step in ('Build site', 'Built-site link integrity',
                     'Drafts must not be deployed', 'Sitemap + schema'):
            self.assertIn(step, y)
        # validate FAST luôn chạy (cả hai mode)
        self.assertIn('validate.py --scope chunk', y)
        # read-only gate luôn chạy
        self.assertIn('git status --porcelain', y)
        self.assertIn('contents: read', y)
        self.assertNotIn('contents: write', y)
        self.assertNotIn('git push', y)

    def test_gate_scope_script_is_pure_selector(self):
        """gate-scope.py KHÔNG mutate state — chỉ in JSON ra stdout."""
        s = open(GATE, encoding='utf-8').read()
        for bad in ("'w'", 'os.remove', 'shutil', 'subprocess',
                    'csv.writer', 'csv.reader'):
            self.assertNotIn(bad, s,
                             'gate-scope phải pure selector: %s' % bad)


if __name__ == '__main__':
    unittest.main(verbosity=2)
