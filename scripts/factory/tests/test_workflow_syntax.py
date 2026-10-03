#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra cú pháp shell của MỌI khối run: trong .github/workflows/*.yml.

Bài học bug đã sửa (2026-09-28, PR #1): bước "op publish" trong
workflow operator cũ có dấu " thừa cuối dòng
(`... ${SCOPE:+--scope $SCOPE}"`) — bash -n từ chối ngay từ đầu nhưng
workflow chỉ phát hiện khi chạy TỚI bước đó trong sản xuất, làm mất
nguyên run operator. Từ đây mọi khối run: phải được kiểm bash -n
trong factory-publish-verify.yml (verify của factory-operator.py)
và trong test tĩnh này, KHÔNG đợi đến lúc bước đó thực sự chạy.

Không cần pyyaml: trích khối run: theo indent (block scalar `|`/`>`
hoặc inline), giống YAML engine của Actions xuất script. Mỗi khối
được ghi ra file .sh rồi `bash -n` — bắt lỗi thiếu/thừa dấu ngoặc,
error lambẹp vùng else/for, expansion sót công... (lỗi cú pháp, không
phải lỗi logic runtime).

Chạy: python3 scripts/factory/tests/test_workflow_syntax.py
"""
import glob
import os
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

WORKFLOWS = os.path.join(ROOT, '.github', 'workflows')
RUN_RE = re.compile(r'^([ \t]*)(?:- )?run:(.*)$')
NAME_RE = re.compile(r'^\s*- name:\s*(.*)$')
BLOCK_STYLES = ('|', '|-', '|+', '>', '>-', '>+')

# Bug thực tế đã xảy ra: phải vẫn FAIL nếu ai đó biến lại dòng này.
BROKEN_PUBLISH_LINE = (
    'python3 scripts/factory/factory-operator.py '
    'publish --ids "$IDS" ${SCOPE:+--scope $SCOPE}"')
FIXED_PUBLISH_LINE = (
    'python3 scripts/factory/factory-operator.py '
    'publish --ids "$IDS" ${SCOPE:+--scope $SCOPE}')


def extract_run_blocks(path):
    """Trả về [(tên step, script, số dòng)] theo đúng indent YAML."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        m = RUN_RE.match(lines[i])
        if not m:
            i += 1
            continue
        indent, rest = m.group(1), m.group(2).strip()
        name = None
        for j in range(i - 1, -1, -1):
            nm = NAME_RE.match(lines[j])
            if nm:
                name = nm.group(1).strip()
                break
        if rest in BLOCK_STYLES + ('',):
            j = i + 1
            body = []
            while j < len(lines):
                ln = lines[j]
                if ln.strip() == '':
                    body.append('')
                    j += 1
                    continue
                ind = len(ln) - len(ln.lstrip())
                if ind <= len(indent):
                    break
                body.append(ln)
                j += 1
            nonblank = [b for b in body if b.strip()]
            if nonblank:
                strip = min(len(b) - len(b.lstrip()) for b in nonblank)
                body = [b[strip:] if b.strip() else '' for b in body]
            while body and body[-1] == '':
                body.pop()
            blocks.append((name, '\n'.join(body), i + 1))
            i = j
        else:
            blocks.append((name, rest, i + 1))
            i += 1
    return blocks


def bash_n(script):
    """bash -n trả về returncode (0 = cú pháp đúng, !=0 = SAI)."""
    fd, tmp = tempfile.mkstemp(suffix='.sh')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(script + '\n')
        return subprocess.run(['bash', '-n', tmp],
                              capture_output=True, text=True).returncode
    finally:
        os.unlink(tmp)


class WorkflowShellSyntaxTest(unittest.TestCase):

    def test_all_workflows_exist(self):
        found = glob.glob(os.path.join(WORKFLOWS, '*.yml'))
        self.assertEqual(len(found), 6,
                          'thiếu workflow trong .github/workflows')
        names = sorted(os.path.basename(f) for f in found)
        self.assertEqual(
            names, ['factory-liveness.yml',
                    'factory-publish-verify.yml', 'factory-publish.yml',
                    'factory-soak.yml', 'production-watchdog.yml',
                    'quality-gate.yml'],
            'hop dong CHINH XAC 6 workflow hien tai (factory-publish.yml '
            'la production publisher duy nhat; cac workflow legacy da '
            'retire KHONG quay lai): khong them workflow moi ngoai danh '
            'sach hop dong')

    def test_every_run_block_passes_bash_n(self):
        paths = sorted(glob.glob(os.path.join(WORKFLOWS, '*.yml')))
        self.assertTrue(paths, 'không tìm thấy workflow nào')
        checked = 0
        for path in paths:
            for name, script, lineno in extract_run_blocks(path):
                checked += 1
                rc = bash_n(script)
                self.assertEqual(
                    rc, 0,
                    'CÚ PHÁP SHELL SAI: %s dòng %d (step %r)\n%s'
                    % (os.path.basename(path), lineno, name, script))
        # đầy đủ: phải có ít nhất khối run của operator workflow
        self.assertGreaterEqual(checked, 15,
                                'số khối run phát hiện bất thường '
                                '(%d) — extractor có thể hỏng' % checked)

    def test_regression_broken_publish_line_fails(self):
        """Đúng bug dấu " thừa: bash -n PHẢI bắt. Nếu test này FAIL
        nghĩa là bảo vệ (bash -n) không còn bắt được lớp lỗi này."""
        self.assertNotEqual(bash_n(BROKEN_PUBLISH_LINE), 0,
                            'bash -n không bắt được dòng publish lỗi')

    def test_regression_fixed_publish_line_passes(self):
        self.assertEqual(bash_n(FIXED_PUBLISH_LINE), 0,
                         'dòng publish đã sửa vẫn sai cú pháp')

    def test_scope_expansion_argv_matches_expected(self):
        """THỰC THI dòng lệnh của bước op (python3 được thay bằng stub ghi
        argv) với SCOPE rỗng/fast/deep/full — đối chiếu argv THẬT, không
        chỉ cú pháp: SCOPE rỗng thì KHÔNG có --scope, SCOPE có giá trị
        thì đúng cặp --scope <giá trị>."""
        verify_line = ('python3 scripts/factory/factory-operator.py '
                       'verify ${SCOPE:+--scope $SCOPE}')
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, 'argv.log')
            stub = os.path.join(td, 'python3')
            with open(stub, 'w', encoding='utf-8') as f:
                f.write('#!/bin/sh\n'
                        'printf %s "$@" >> %s\n'
                        'exit 0\n'
                        % (shlex.quote('%s\\n'), shlex.quote(log)))
            os.chmod(stub, 0o755)
            env = dict(os.environ,
                       PATH=td + os.pathsep + os.environ.get('PATH', ''))
            cases = [
                ('', FIXED_PUBLISH_LINE, {'IDS': 'BLG-001,BLG-002'},
                 ['scripts/factory/factory-operator.py', 'publish',
                  '--ids', 'BLG-001,BLG-002']),
                ('fast', FIXED_PUBLISH_LINE, {'IDS': 'BLG-001,BLG-002'},
                 ['scripts/factory/factory-operator.py', 'publish',
                  '--ids', 'BLG-001,BLG-002', '--scope', 'fast']),
                ('deep', FIXED_PUBLISH_LINE, {'IDS': 'BLG-001'},
                 ['scripts/factory/factory-operator.py', 'publish',
                  '--ids', 'BLG-001', '--scope', 'deep']),
                ('', verify_line, {},
                 ['scripts/factory/factory-operator.py', 'verify']),
                ('full', verify_line, {},
                 ['scripts/factory/factory-operator.py', 'verify',
                  '--scope', 'full']),
            ]
            for scope, line, extra, _want in cases:
                env2 = dict(env, SCOPE=scope)
                env2.update(extra)
                r = subprocess.run(['bash', '-c', line], env=env2, cwd=td,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0,
                                 'SCOPE=%r: %s' % (scope, r.stderr))
            with open(log, encoding='utf-8') as f:
                got = f.read().splitlines()
            i = 0
            for _scope, _line, _extra, want in cases:
                argv = got[i:i + len(want)]
                i += len(want)
                self.assertEqual(argv, want,
                                 'argv lệch (kỳ vọng %r, nhận %r)'
                                 % (want, argv))
if __name__ == '__main__':
    unittest.main(verbosity=2)
