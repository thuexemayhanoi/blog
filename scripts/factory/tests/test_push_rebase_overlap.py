#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm thử push/rebase + LỆNH CHỒNG NHAU với GIT THẬT (không mock).

Sandbox không có git -> test SKIP cục bộ; GitHub Actions runner có git
nên CI (Factory validate) luôn chạy đủ. Kịch bản dùng ĐÚNG khối
"Commit va push fast-forward" trích từ factory-operator.yml (không tự
viết lại logic), trên bare origin + clone làm việc:

 1. Lệnh chồng nhau: run A tiêu thụ C1 (xóa file lệnh) và tạo output
    deterministic; trong lúc đó coordinator đẩy C2 (SỬA file lệnh) lên
    origin. Push A bị từ chối -> rebase conflict modify/delete đúng
    operator-command.json -> khối hòa giải giữ C2 của origin (lệnh mới
    KHÔNG MẤT) -> verify lại -> push fast-forward. Run sau (bước Node
    đọc lệnh) đọc được C2 trên trạng thái mới nhất -> KHÔNG lặp: commit
    của run A xuất hiện đúng 1 lần trên origin/main.
 2. Conflict ở file KHÁC -> rebase --abort, STOP (exit 1), origin không
    nhận commit nào của run A (không push khi chưa sạch).
 3. Origin đổi file khác (không đụng file lệnh) -> rebase sạch, verify,
    push OK.

Không đụng production: mọi thứ trong temp dir, origin là bare repo cục bộ.

Chạy: python3 scripts/factory/tests/test_push_rebase_overlap.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_qa_modes import IGNORE
from test_workflow_syntax import extract_run_blocks

WF = os.path.join(ROOT, '.github', 'workflows', 'factory-operator.yml')

C1 = {'op': 'status', 'command_id': 'c1-old'}
C2 = {'op': 'status', 'command_id': 'c2-new', 'coordinator': 'coordinator-2'}
CMD_REL = 'data/factory/operator-command.json'


def _block(step_fragment):
    for name, script, _lineno in extract_run_blocks(WF):
        if step_fragment in name:
            return script
    raise AssertionError('không tìm thấy khối run: %r' % step_fragment)


COMMIT_BLOCK = _block('Commit va push fast-forward')
VALIDATE_BLOCK = _block('Doc gia lap lenh operator')

GIT = shutil.which('git')


def git(cwd, *args):
    r = subprocess.run(['git'] + list(args), cwd=cwd,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError('git %s FAIL:\n%s%s'
                             % (' '.join(args), r.stdout, r.stderr))
    return r


@unittest.skipUnless(GIT, 'cần git thật (chạy trên runner CI)')
class PushRebaseOverlapTest(unittest.TestCase):

    def setUp(self):
        base = tempfile.mkdtemp(prefix='push-rebase-')
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        self.origin = os.path.join(base, 'origin.git')
        git(self.origin, 'init', '--bare', '-b', 'main')
        self.fx = os.path.join(base, 'repo')
        shutil.copytree(ROOT, self.fx, ignore=IGNORE)
        git(self.fx, 'init', '-b', 'main')
        git(self.fx, 'config', 'user.name', 'e2e-push-rebase')
        git(self.fx, 'config', 'user.email', 'e2e@example.com')
        with open(os.path.join(self.fx, CMD_REL), 'w', encoding='utf-8') as f:
            json.dump(C1, f, ensure_ascii=False)
        git(self.fx, 'add', '-A')
        git(self.fx, 'commit', '-m', 'base: lenh C1 + repository')
        git(self.fx, 'remote', 'add', 'origin', self.origin)
        git(self.fx, 'push', '-u', 'origin', 'main')
        self.coordinator_pushes = os.path.join(base, 'coordinator')

    def _simulate_run_end_state(self):
        """Trạng thái sau op của run A: lệnh C1 đã tiêu thụ (file bị xóa,
        đúng bước 'Xoa lenh') + một output deterministic của engine."""
        os.remove(os.path.join(self.fx, CMD_REL))
        os.makedirs(os.path.join(self.fx, 'reports/factory'), exist_ok=True)
        with open(os.path.join(self.fx, 'reports/factory/e2e-marker.json'),
                  'w', encoding='utf-8') as f:
            json.dump({'run': 'A', 'note': 'deterministic output'}, f)

    def _verified_tree(self):
        git(self.fx, 'add', '-A')
        return git(self.fx, 'write-tree').stdout.strip()

    def _run_commit_block(self):
        env = dict(os.environ)
        env.update({'OP': 'status', 'COMMAND_ID': 'c1-old',
                    'SCOPE': 'fast',
                    'OPERATOR_VERIFIED_TREE': self._verified_tree(),
                    'GITHUB_ENV': os.path.join(self.fx, '.github-env'),
                    'PYTHONDONTWRITEBYTECODE': '1'})
        return subprocess.run(['bash', '-c', COMMIT_BLOCK], cwd=self.fx,
                              env=env, capture_output=True, text=True)

    def _coordinator_push(self, mutate):
        """Coordinator đẩy commit mới lên origin GIỮA run A."""
        git(self.fx, 'fetch', 'origin', 'main')
        os.makedirs(self.coordinator_pushes, exist_ok=True)
        clone = os.path.join(self.coordinator_pushes, 'clone')
        git(self.coordinator_pushes, 'clone', self.origin, 'clone')
        git(clone, 'config', 'user.name', 'coordinator')
        git(clone, 'config', 'user.email', 'coordinator@example.com')
        mutate(clone)
        git(clone, 'add', '-A')
        git(clone, 'commit', '-m', 'coordinator: lenh/file moi cho run sau')
        git(clone, 'push', 'origin', 'main')

    def _origin_log(self, pattern):
        r = git(self.fx, 'log', '--format=%s', 'origin/main')
        return [l for l in r.stdout.splitlines() if pattern in l]

    def test_overlap_command_reconciled_not_lost_not_duplicated(self):
        self._simulate_run_end_state()
        # giữa chặn: coordinator đẩy C2 (SỬA file lệnh C1 -> C2)
        self._coordinator_push(lambda clone: json.dump(
            C2, open(os.path.join(clone, CMD_REL), 'w', encoding='utf-8'),
            ensure_ascii=False))
        r = self._run_commit_block()
        self.assertEqual(r.returncode, 0, 'STDOUT:\n%s\nSTDERR:\n%s'
                         % (r.stdout, r.stderr))
        self.assertIn('FINAL_PUSHED_HEAD', r.stdout)
        # lệnh mới KHÔNG MẤT: file lệnh trên cây push == C2 của origin
        got = git(self.fx, 'show', 'origin/main:' + CMD_REL).stdout
        self.assertEqual(json.loads(got), C2)
        self.assertEqual(json.load(open(os.path.join(self.fx, CMD_REL),
                                        encoding='utf-8')), C2)
        # KHÔNG LẶP: commit của run A đúng 1 lần trên origin/main
        self.assertEqual(len(self._origin_log('factory-operator:')), 1)
        # commit của coordinator cũng còn (lệnh sẽ được run sau xử lý)
        self.assertEqual(len(self._origin_log('coordinator:')), 1)
        self.assertIn('(sau rebase, da verify lai)', r.stdout)
        # KHÔNG force push: push luôn là fast-forward sau rebase
        self.assertNotIn('--force', COMMIT_BLOCK)
        # run sau đọc được C2 trên trạng thái mới nhất
        env_file = os.path.join(self.fx, '.github-env-next')
        env = dict(os.environ, GITHUB_ENV=env_file)
        r2 = subprocess.run(['bash', '-c', VALIDATE_BLOCK], cwd=self.fx,
                            env=env, capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        exports = dict(l.split('=', 1) for l in
                      open(env_file, encoding='utf-8').read().splitlines())
        self.assertEqual(exports.get('COMMAND_ID'), C2['command_id'])

    def test_conflict_other_file_aborts_without_push(self):
        self._simulate_run_end_state()
        qa_rel = os.path.join('scripts', 'factory', 'qa.py')

        def mutate(clone):
            p = os.path.join(clone, qa_rel)
            with open(p, 'a', encoding='utf-8') as f:
                f.write('# coordinator edit\n')

        self._coordinator_push(mutate)
        # run A cũng sửa QA file khác dòng -> conflict content
        with open(os.path.join(self.fx, qa_rel), 'a', encoding='utf-8') as f:
            f.write('# run A edit (khac dong)\n')
        r = self._run_commit_block()
        self.assertEqual(r.returncode, 1)
        self.assertIn('rebase conflict', r.stdout)
        # origin KHÔNG nhận commit nào của run A
        self.assertEqual(len(self._origin_log('factory-operator:')), 0)
        # rebase đã abort: working tree không kẹt conflict nào
        st = git(self.fx, 'status', '--porcelain').stdout
        import re as _re
        self.assertIsNone(_re.search(r'^(UU|AA|DD|AU|UA|DU|UD) ', st, _re.M),
                          'còn trạng thái unmerged sau abort: %r' % st)

    def test_origin_moves_other_file_rebase_clean_push(self):
        self._simulate_run_end_state()

        def mutate(clone):
            with open(os.path.join(clone, 'assets', 'e2e-note.txt'),
                      'w', encoding='utf-8') as f:
                f.write('coordinator them file\n')

        self._coordinator_push(mutate)
        r = self._run_commit_block()
        self.assertEqual(r.returncode, 0, 'STDOUT:\n%s\nSTDERR:\n%s'
                         % (r.stdout, r.stderr))
        self.assertIn('FINAL_PUSHED_HEAD', r.stdout)
        self.assertEqual(len(self._origin_log('factory-operator:')), 1)
        self.assertEqual(len(self._origin_log('coordinator:')), 1)
        # lệnh C1 đã tiêu thụ, không còn file lệnh trên origin
        r2 = git(self.fx, 'cat-file', '-e', 'origin/main:' + CMD_REL,
                 check=False)
        self.assertNotEqual(r2.returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
