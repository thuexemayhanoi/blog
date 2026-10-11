#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test publisher-push.py — commit/push an toàn của factory-publish.yml.

Tái hiện + chặn P0-3 (audit): rebase của publisher ÂM THẦM áp bản sửa
draft của writer lên bài vừa publish (git ghép theo rename) => nội dung
bài != nội dung đã chấm QA. Bộ test dựng origin bare + clone publisher +
clone writer cục bộ (KHÔNG mạng, KHÔNG đụng main thật).

Chạy: python3 scripts/factory/tests/test_publisher_push.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_helpers import REPO_ROOT, git

PUSHER = os.path.join(REPO_ROOT, 'scripts', 'factory', 'publisher-push.py')
DRAFT = '_drafts/2026-10-11-x.md'
POST = '_posts/2026-10-11-x.md'


def body():
    return ('---\ntitle: X\narticle_id: BLG-00001\nwriter: W1\n---\n' +
            '\n'.join('Dong noi dung so %d cua bai viet nay.' % i
                      for i in range(60)) + '\n')


class PushBase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix='ppush-')
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.origin = os.path.join(self.base, 'origin.git')
        git(self.base, 'init', '-q', '--bare', '--initial-branch=main',
            self.origin)
        seed = os.path.join(self.base, 'seed')
        git(self.base, 'clone', '-q', self.origin, seed, check=False)
        git(seed, 'checkout', '-q', '-B', 'main')
        os.makedirs(os.path.join(seed, '_drafts'))
        os.makedirs(os.path.join(seed, '_posts'))
        os.makedirs(os.path.join(seed, 'data', 'qa'))
        with open(os.path.join(seed, DRAFT), 'w', encoding='utf-8') as f:
            f.write(body())
        git(seed, 'add', '-A')
        git(seed, 'commit', '-q', '-m', 'base')
        git(seed, 'push', '-q', 'origin', 'HEAD:main')
        self.pub = self.clone('pub')
        self.writer = self.clone('writer')

    def clone(self, name):
        p = os.path.join(self.base, name)
        git(self.base, 'clone', '-q', self.origin, p)
        git(p, 'checkout', '-q', '-B', 'main', 'origin/main')
        return p

    def publish_locally(self, text=None):
        """Mô phỏng publish-gate: chuyển draft -> post + ghi bằng chứng QA."""
        git(self.pub, 'mv', DRAFT, POST)
        data = (text or body()).encode('utf-8')
        with open(os.path.join(self.pub, POST), 'wb') as f:
            f.write(data)
        with open(os.path.join(self.pub, 'data', 'qa', 'BLG-00001.json'),
                  'w') as f:
            json.dump({'content_sha256': hashlib.sha256(
                body().encode('utf-8')).hexdigest()}, f)

    def writer_edits_draft(self):
        p = os.path.join(self.writer, DRAFT)
        with open(p, encoding='utf-8') as f:
            s = f.read()
        s = s.replace('Dong noi dung so 10 ',
                      'Dong noi dung so 10 DA BI SUA SAU QA ')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(s)
        git(self.writer, 'commit', '-q', '-am', 'writer: sua draft')
        git(self.writer, 'push', '-q', 'origin', 'HEAD:main')

    def push(self, env=None):
        e = dict(os.environ)
        e['FACTORY_PUSH_BACKOFF'] = '0'
        e['GIT_AUTHOR_NAME'] = e['GIT_COMMITTER_NAME'] = 'bot'
        e['GIT_AUTHOR_EMAIL'] = e['GIT_COMMITTER_EMAIL'] = 'bot@example.com'
        if env:
            e.update(env)
        r = subprocess.run([sys.executable, PUSHER, '--message',
                            'factory: new publish (BLG-00001) [automated txn]'],
                           cwd=self.pub, capture_output=True, text=True,
                           env=e)
        out = None
        for ln in r.stdout.splitlines():
            if ln.startswith('BLOG_PUBLISHER_PUSH '):
                out = json.loads(ln[len('BLOG_PUBLISHER_PUSH '):])
        return r, out

    def origin_head(self):
        return git(self.origin, 'rev-parse', 'main').stdout.strip()

    def origin_has(self, path):
        return git(self.origin, 'cat-file', '-e', 'main:%s' % path,
                   check=False).returncode == 0


class TestPublisherPush(PushBase):

    def test_01_clean_push(self):
        self.publish_locally()
        r, out = self.push()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(out['pushed'])
        self.assertTrue(self.origin_has(POST))
        self.assertFalse(self.origin_has(DRAFT))

    def test_02_no_changes_is_noop(self):
        r, out = self.push()
        self.assertEqual(r.returncode, 0)
        self.assertFalse(out['pushed'])
        self.assertEqual(out['reason'], 'no_changes')

    def test_03_writer_edit_of_published_draft_is_NOT_merged_into_post(self):
        """P0-3: writer sửa draft SAU khi publisher chốt nội dung. Rebase
        cũ ghép bản sửa vào bài đã publish. Guard mới: dừng, main không
        đổi, KHÔNG bài nào lọt nội dung chưa QA."""
        self.publish_locally()
        self.writer_edits_draft()
        head = self.origin_head()
        r, out = self.push()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(out['reason'], 'upstream_overlap')
        self.assertIn(DRAFT, out['overlap'])
        self.assertEqual(self.origin_head(), head, 'main KHONG duoc doi')
        self.assertFalse(self.origin_has(POST))
        # draft của writer (bản sửa) vẫn nằm đó để run kế QA đúng nội dung
        txt = git(self.origin, 'show', 'main:%s' % DRAFT).stdout
        self.assertIn('DA BI SUA SAU QA', txt)

    def test_04_vanilla_rebase_hazard_is_caught_by_integrity_check(self):
        """Bằng chứng nguy cơ: nếu git rebase ghép bản sửa vào bài, kiểm
        integrity (sha256 bài == QA content_sha256) PHẢI bắt được."""
        self.publish_locally()
        git(self.pub, 'add', '-A')
        git(self.pub, 'commit', '-q', '-m', 'factory: publish')
        self.writer_edits_draft()
        git(self.pub, 'fetch', '-q', 'origin', 'main')
        rb = git(self.pub, 'rebase', 'origin/main', check=False)
        if rb.returncode != 0:
            git(self.pub, 'rebase', '--abort', check=False)
            self.skipTest('git nay xung dot (an toan) thay vi ghep ngam')
        with open(os.path.join(self.pub, POST), encoding='utf-8') as f:
            merged = 'DA BI SUA SAU QA' in f.read()
        if not merged:
            self.skipTest('git nay khong ghep sua doi vao bai')
        sys.path.insert(0, os.path.join(REPO_ROOT, 'scripts', 'factory'))
        import importlib.util
        spec = importlib.util.spec_from_file_location('pp', PUSHER)
        pp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pp)
        probs = pp.integrity_problems(cwd=self.pub)
        self.assertTrue(probs, 'integrity check phai bat sha lech')
        self.assertIn('QA content_sha256', probs[0])

    def test_05_disjoint_upstream_commit_rebases_and_pushes(self):
        self.publish_locally()
        # writer đẩy draft MỚI (path khác) trong lúc publisher chạy
        p = os.path.join(self.writer, '_drafts', '2026-10-11-y.md')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('---\ntitle: Y\narticle_id: BLG-00002\n---\nnoi dung\n')
        git(self.writer, 'add', '-A')
        git(self.writer, 'commit', '-q', '-m', 'writer: draft moi')
        git(self.writer, 'push', '-q', 'origin', 'HEAD:main')
        r, out = self.push()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(out['pushed'])
        self.assertEqual(out['rebases'], 1)
        self.assertTrue(self.origin_has(POST))
        self.assertTrue(self.origin_has('_drafts/2026-10-11-y.md'),
                        'draft moi cua writer khong bi mat')
        self.assertFalse(self.origin_has(DRAFT))

    def test_06_integrity_failure_before_push_blocks(self):
        self.publish_locally(text=body() + 'dong chen vao sau QA\n')
        head = self.origin_head()
        r, out = self.push()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['reason'], 'integrity_before_push')
        self.assertEqual(self.origin_head(), head)

    def test_07_transient_errors_retry_then_succeed(self):
        self.publish_locally()
        hook = os.path.join(self.origin, 'hooks', 'pre-receive')
        counter = os.path.join(self.origin, 'fail-count')
        with open(counter, 'w') as f:
            f.write('2')
        with open(hook, 'w') as f:
            f.write('#!/bin/sh\nc=$(cat "%s")\nif [ "$c" -gt 0 ]; then\n'
                    '  echo $((c-1)) > "%s"\n  echo "remote: HTTP 503" >&2\n'
                    '  exit 1\nfi\nexit 0\n' % (counter, counter))
        os.chmod(hook, 0o755)
        r, out = self.push()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(out['pushed'])
        self.assertTrue(self.origin_has(POST))

    def test_08_persistent_rejection_gives_up_without_force(self):
        self.publish_locally()
        hook = os.path.join(self.origin, 'hooks', 'pre-receive')
        with open(hook, 'w') as f:
            f.write('#!/bin/sh\necho "! [rejected] fetch first" >&2\n'
                    'exit 1\n')
        os.chmod(hook, 0o755)
        head = self.origin_head()
        r, out = self.push()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['reason'], 'rebases_exhausted')
        self.assertEqual(self.origin_head(), head)
        with open(PUSHER, encoding='utf-8') as f:
            src = f.read()
        self.assertNotIn('--force', src)
        self.assertNotIn('+HEAD', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
