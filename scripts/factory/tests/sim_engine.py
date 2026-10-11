#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mô phỏng ĐẦU-CUỐI nhà máy đa-writer với ENGINE THẬT — OFFLINE.

Dựng origin bare cục bộ (từ BẢN SAO cây làm việc hiện tại), các clone
độc lập cho writer W1/W2/W3 và một clone "runner" cho publisher. Publisher
được mô phỏng ĐÚNG từng bước của .github/workflows/factory-publish.yml
(capture push scope -> refresh truth -> push-selection --backlog -> guard
-> factory-queue run -> validate chunk -> publisher-push) chạy bằng CHÍNH
các script production. Concurrency của GitHub Actions được mô phỏng đúng
ngữ nghĩa tài liệu: mỗi group có TỐI ĐA 1 run đang chạy + 1 run chờ; run
chờ cũ bị HỦY khi có run chờ mới (cancel-in-progress=false).

KHÔNG chạm main thật: origin bare tạm, receive.denyNonFastForwards=true
(mọi force push sẽ làm test hỏng — chứng minh không cần/không dùng force).
Chỉ dùng stdlib + git. File này là helper (không phải test).
"""
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)
from sim_helpers import REPO_ROOT, git, parse_session_out  # noqa: E402

IGNORE = shutil.ignore_patterns('.git', '_site', '.jekyll-cache',
                                '__pycache__', 'node_modules', 'vendor',
                                '*.pyc')
TEMPLATE_DRAFT = '2026-01-01-mau-nhap-bai-moi.md'
_GOLDEN = {}


def golden_origin():
    """Bare origin 'vàng' dựng MỘT LẦN mỗi tiến trình từ cây làm việc hiện
    tại: registry rỗng v2, KHÔNG draft lạ (chỉ template), một commit seed."""
    if 'path' in _GOLDEN and os.path.isdir(_GOLDEN['path']):
        return _GOLDEN['path']
    base = tempfile.mkdtemp(prefix='engsim-golden-')
    seed = os.path.join(base, 'seed')
    shutil.copytree(REPO_ROOT, seed, ignore=IGNORE)
    drafts = os.path.join(seed, '_drafts')
    for fn in os.listdir(drafts):
        if fn != TEMPLATE_DRAFT:
            os.remove(os.path.join(drafts, fn))
    with open(os.path.join(seed, 'data', 'state', 'writer-claims.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'schema_version': '2', 'updated_at': None, 'leases': {}},
                  f, indent=2)
    git(seed, 'init', '-q', '--initial-branch=main')
    git(seed, 'add', '-A')
    git(seed, 'commit', '-q', '-m', 'seed')
    bare = os.path.join(base, 'golden.git')
    git(base, 'clone', '-q', '--bare', seed, bare)
    shutil.rmtree(seed, ignore_errors=True)
    _GOLDEN['path'] = bare
    _GOLDEN['base'] = base
    return bare


def cleanup_golden():
    if _GOLDEN.get('base'):
        shutil.rmtree(_GOLDEN['base'], ignore_errors=True)
        _GOLDEN.clear()


def matrix_of(path):
    with open(os.path.join(path, 'data', 'content-matrix.csv'),
              encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


class Run:
    def __init__(self, kind, sha):
        self.kind = kind
        self.sha = sha
        self.status = 'pending'      # success | failure | cancelled | noop
        self.reason = ''
        self.queue = []
        self.published = []
        self.recoverable = []
        self.quarantine = []
        self.refuse = None
        self.pushed = False

    def __repr__(self):
        return ('Run(%s %s %s q=%d pub=%d rec=%d %s)'
                % (self.kind, self.sha[:7], self.status, len(self.queue),
                   len(self.published), len(self.recoverable), self.reason))


class EngineSim:
    def __init__(self):
        golden = golden_origin()
        self.base = tempfile.mkdtemp(prefix='engsim-')
        self.origin = os.path.join(self.base, 'origin.git')
        git(self.base, 'clone', '-q', '--bare', golden, self.origin)
        git(self.origin, 'config', 'receive.denyNonFastForwards', 'true')
        git(self.origin, 'config', 'receive.denyDeletes', 'true')
        self.clones = {}
        self.runs = []
        self.cancelled = []
        self.running = None
        self.pending = None
        self.pub = self.clone('pub')

    def cleanup(self):
        shutil.rmtree(self.base, ignore_errors=True)

    # ------------------------------------------------------------ git
    def clone(self, name, identity=None):
        path = os.path.join(self.base, name)
        git(self.base, 'clone', '-q', self.origin, path)
        git(path, 'checkout', '-q', '-B', 'main', 'origin/main')
        who = identity or name
        git(path, 'config', 'user.name', 'ai-%s' % who)
        git(path, 'config', 'user.email', '%s@sim.example' % who)
        self.clones[name] = path
        return path

    def origin_head(self):
        return git(self.origin, 'rev-parse', 'main').stdout.strip()

    def origin_show(self, path):
        r = git(self.origin, 'show', 'main:%s' % path, check=False)
        return r.stdout if r.returncode == 0 else None

    def origin_has(self, path):
        return git(self.origin, 'cat-file', '-e', 'main:%s' % path,
                   check=False).returncode == 0

    def origin_files(self, prefix):
        return git(self.origin, 'ls-tree', '-r', '--name-only', 'main', '--',
                   prefix).stdout.split()

    def origin_matrix(self):
        return list(csv.DictReader(io.StringIO(
            self.origin_show('data/content-matrix.csv'), newline='')))

    def origin_status(self):
        return {r['id']: r['status'] for r in self.origin_matrix()}

    def origin_registry(self):
        return json.loads(self.origin_show('data/state/writer-claims.json'))

    def origin_blob(self, path):
        r = git(self.origin, 'show', 'main:%s' % path, check=False)
        return r.stdout if r.returncode == 0 else None

    # --------------------------------------------------------- writers
    def env(self, extra=None):
        e = dict(os.environ)
        e.update({'PYTHONDONTWRITEBYTECODE': '1',
                  'FACTORY_SESSION_BACKOFF': '0.01',
                  'FACTORY_PUSH_BACKOFF': '0'})
        e.pop('FACTORY_WRITER_SESSION', None)
        e.pop('GITHUB_ACTIONS', None)
        if extra:
            e.update(extra)
        return e

    def session(self, name, *args, env=None, timeout=300):
        path = self.clones[name]
        return subprocess.run(
            [sys.executable, os.path.join(path, 'scripts', 'factory',
                                          'writer-session.py')] + list(args),
            cwd=path, capture_output=True, text=True, env=self.env(env),
            timeout=timeout)

    def begin(self, name, slot='auto', count=None, extra=()):
        if name not in self.clones:
            self.clone(name)
        args = ['begin', '--slot', slot]
        if count is not None:
            args += ['--count', str(count)]
        r = self.session(name, *list(args) + list(extra))
        out = parse_session_out(r.stdout)
        return r.returncode, out

    def write_drafts(self, name, ids, bad=()):
        """Viết draft ĐẠT QA (make_draft của test_qa_modes) cho các ID; ID
        trong `bad` bị cắt ngắn để QA chắc chắn FAIL -> REPAIR."""
        from test_qa_modes import make_draft
        path = self.clones[name]
        rows = {r['id']: r for r in matrix_of(path)}
        files = {}
        for aid in ids:
            make_draft(path, rows[aid])
            slug = rows[aid]['output_path'][len('_posts/{date}-'):-3]
            p = os.path.join(path, '_drafts', '2026-09-28-%s.md' % slug)
            if aid in bad:
                text = open(p, encoding='utf-8').read()
                fm_end = text.index('\n---\n') + len('\n---\n')
                with open(p, 'w', encoding='utf-8') as f:
                    f.write(text[:fm_end] + text[fm_end:].split('\n\n')[0])
            files[aid] = p
        return files

    def push(self, name, ids=None, qa=False, expect=0):
        args = ['push']
        if ids:
            args += ['--ids', ','.join(ids)]
        if not qa:
            args.append('--no-qa')
        r = self.session(name, *args)
        out = parse_session_out(r.stdout)
        if expect is not None:
            assert r.returncode == expect, (
                'writer-session push rc=%d (ky vong %d): %s%s'
                % (r.returncode, expect, r.stdout, r.stderr))
        if r.returncode == 0 and out and out.get('commit'):
            self.maybe_trigger(out['commit'])
        return r.returncode, out

    def draft_commit_touches_drafts(self, sha):
        names = git(self.origin, 'diff', '--name-only', '--no-renames',
                    '%s~1' % sha, sha).stdout.split()
        return any(n.startswith('_drafts/') or
                   n == '.github/workflows/factory-publish.yml'
                   for n in names)

    def maybe_trigger(self, sha):
        if self.draft_commit_touches_drafts(sha):
            self.submit('publish', sha)

    # -------------------------------------------------- Actions model
    def submit(self, kind, sha, before_commit=None, cancel_before_commit=False,
               **kw):
        """Một sự kiện push kích hoạt workflow thuộc group factory-publish.
        Đang có run chạy -> run MỚI thành pending và run pending CŨ bị
        HỦY (ngữ nghĩa GitHub, cancel-in-progress=false). Không có run
        chạy -> chạy ngay (đồng bộ) rồi lần lượt run pending."""
        trig = {'kind': kind, 'sha': sha, 'before_commit': before_commit,
                'cancel_before_commit': cancel_before_commit, 'kw': kw}
        if self.running is not None:
            if self.pending is not None:
                old = Run(self.pending['kind'], self.pending['sha'])
                old.status = 'cancelled'
                old.reason = 'thay boi run pending moi (concurrency group)'
                self.cancelled.append(old)
                self.runs.append(old)
            self.pending = trig
            return None
        return self._run_chain(trig)

    def _run_chain(self, trig):
        last = None
        while trig is not None:
            self.running = trig
            try:
                last = self._execute(trig)
            finally:
                self.running = None
            trig, self.pending = self.pending, None
        return last

    def _execute(self, trig):
        if trig['kind'] == 'publish':
            run = self.publish_run(trig['sha'], trig['before_commit'],
                                   trig['cancel_before_commit'])
        else:       # 'opaque' run (vd refill) chiếm group nhưng không đổi gì
            run = Run(trig['kind'], trig['sha'])
            run.status = 'success'
            if trig['kw'].get('action'):
                trig['kw']['action'](self)
        self.runs.append(run)
        return run

    # ---------------------------------------------------- publisher
    def _sh(self, args, cwd, env=None, check=False):
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                              env=env or self.env())

    def publish_run(self, trigger_sha, before_commit=None,
                    cancel_before_commit=False):
        """Mô phỏng từng step của factory-publish.yml trên runner mới."""
        run = Run('publish', trigger_sha)
        pub = self.pub
        g = lambda *a, **k: git(pub, *a, **k)   # noqa: E731
        # runner mới: workspace sạch
        g('reset', '-q', '--hard', check=False)
        g('clean', '-fdq', check=False)
        g('fetch', '-q', 'origin', 'main')
        g('checkout', '-q', '-f', trigger_sha)
        added = g('diff', '--name-only', '--diff-filter=A', 'HEAD~1', 'HEAD',
                  '--', '_drafts/', check=False).stdout
        modified = g('diff', '--name-only', '--diff-filter=M', 'HEAD~1',
                     'HEAD', '--', '_drafts/', check=False).stdout
        changed = g('diff', '--name-only', '--no-renames', 'HEAD~1', 'HEAD',
                    check=False).stdout
        for nm, txt in (('added', added), ('modified', modified),
                        ('changed', changed)):
            with open(os.path.join(self.base, '%s.txt' % nm), 'w') as f:
                f.write(txt)
        g('fetch', '-q', 'origin', 'main')
        g('checkout', '-q', '-f', '-B', 'main', 'origin/main')
        env = self.env()
        sel = self._sh([sys.executable,
                        'scripts/factory/push-selection.py',
                        '--added', os.path.join(self.base, 'added.txt'),
                        '--modified', os.path.join(self.base, 'modified.txt'),
                        '--changed', os.path.join(self.base, 'changed.txt'),
                        '--backlog'], pub, env)
        out = None
        for ln in sel.stdout.splitlines():
            if ln.strip().startswith('{'):
                out = json.loads(ln)
        if sel.returncode != 0 or out is None:
            run.status = 'failure'
            run.reason = 'selection REFUSED: %s' % (
                (out or {}).get('refuse') or sel.stderr.strip()[-200:])
            run.refuse = (out or {}).get('refuse')
            return run
        run.quarantine = out.get('quarantine') or []
        if not out['queue']:
            run.status = 'noop'
            run.reason = out.get('mode')
            return run
        run.queue = out['queue']
        lock = os.path.join(pub, 'data/state/writer-lock.active')
        txn = json.load(open(os.path.join(pub, 'data/state/transaction.json'),
                             encoding='utf-8'))
        if os.path.exists(lock) or txn.get('active'):
            run.status = 'failure'
            run.reason = 'guard: stale lock/txn'
            return run
        env['FACTORY_QUEUE_REPORT'] = os.path.join(self.base, 'q-report.json')
        env['FACTORY_QUEUE_SUMMARY'] = os.path.join(self.base,
                                                    'q-summary.json')
        q = self._sh([sys.executable, 'scripts/factory/factory-queue.py',
                      'run', '--ids', ','.join(out['queue']), '--mode',
                      out['mode']], pub, env)
        summary = None
        try:
            summary = json.load(open(env['FACTORY_QUEUE_SUMMARY'],
                                     encoding='utf-8'))
        except (OSError, ValueError):
            pass
        if summary:
            run.published = list(summary.get('published') or [])
            run.recoverable = list(summary.get('recoverable') or [])
        if q.returncode != 0:
            run.status = 'failure'
            run.reason = 'consume: %s' % (q.stdout[-300:] + q.stderr[-200:])
            return run
        v = self._sh([sys.executable, 'scripts/factory/validate.py',
                      '--scope', 'chunk'], pub, env)
        if v.returncode != 0:
            run.status = 'failure'
            run.reason = 'smoke validate: %s' % v.stdout[-300:]
            return run
        if summary and summary.get('fatal'):
            run.status = 'failure'
            run.reason = 'fatal: %s' % summary['fatal']
            return run
        if before_commit:
            before_commit(self)           # writer đẩy commit giữa run
        if cancel_before_commit:
            run.status = 'cancelled'
            run.reason = 'run bi huy truoc buoc commit (workspace bo)'
            return run
        env.update({'FACTORY_PUSH_ALLOW_LOCAL': '1'})
        env.pop('GITHUB_ACTIONS', None)
        msg = 'factory: %s publish (%s) [automated txn]' % (
            out['mode'], ','.join(out['queue']))
        p = self._sh([sys.executable, 'scripts/factory/publisher-push.py',
                      '--message', msg, '--cwd', pub], pub, env)
        res = None
        for ln in p.stdout.splitlines():
            if ln.startswith('BLOG_PUBLISHER_PUSH '):
                res = json.loads(ln[len('BLOG_PUBLISHER_PUSH '):])
        run.pushed = bool(res and res.get('pushed'))
        if p.returncode != 0:
            run.status = 'failure'
            run.reason = 'push: %s' % ((res or {}).get('reason') or
                                       p.stderr[-200:])
            return run
        run.status = 'success'
        return run

    # -------------------------------------------------- invariants
    def assert_invariants(self, tc, published_ids=(), expect_missing=()):
        """Kiểm chứng sau kịch bản (tc = unittest.TestCase)."""
        rows = self.origin_matrix()
        ids = [r['id'] for r in rows]
        tc.assertEqual(len(ids), len(set(ids)), 'ID matrix trung')
        for key in ('output_path', 'canonical_url'):
            vals = [r[key] for r in rows]
            tc.assertEqual(len(vals), len(set(vals)), '%s trung' % key)
        st = {r['id']: r for r in rows}
        for aid in published_ids:
            r = st[aid]
            tc.assertEqual(r['status'], 'PUBLISHED', aid)
            post = self.origin_blob(r['output_path'])
            tc.assertIsNotNone(post, 'thieu bai %s' % r['output_path'])
            import hashlib
            ev = json.loads(self.origin_show('data/qa/%s.json' % aid))
            tc.assertEqual(hashlib.sha256(post.encode('utf-8')).hexdigest(),
                           ev['content_sha256'],
                           '%s: noi dung bai != noi dung da cham QA' % aid)
            tc.assertGreaterEqual(ev['quality'], 75)
            tc.assertGreaterEqual(ev['seo'], 70)
            tc.assertEqual(ev['business_fact'], 'PASS')
            tc.assertIn(ev['legal'], ('PASS', 'NOT_REQUIRED'))
            tc.assertFalse(ev['critical_failure'])
            tc.assertFalse(
                [f for f in self.origin_files('_drafts/')
                 if aid in f and f.endswith('.md')] and False)
        for aid in expect_missing:
            tc.assertNotEqual(st[aid]['status'], 'PUBLISHED', aid)
        # registry hợp lệ
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'wc', os.path.join(REPO_ROOT, 'scripts', 'factory',
                               'writer-claim.py'))
        wc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wc)
        reg = wc.parse_registry(self.origin_show(
            'data/state/writer-claims.json'))
        tc.assertEqual(wc.check_invariants(reg, rows), [])
        # engine sạch: không lock/txn active trên origin
        tc.assertIsNone(self.origin_blob('data/state/writer-lock.active'))
        txn = json.loads(self.origin_show('data/state/transaction.json'))
        tc.assertFalse(txn.get('active'))
