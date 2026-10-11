#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helper MÔ PHỎNG đa-writer OFFLINE (stdlib + git) — KHÔNG chạm main thật.

Dựng một "origin" bare repo cục bộ + các clone độc lập (mỗi clone = một
phiên AI writer khác nhau) để kiểm tra đồng thời: claim, push, race,
lỗi push (409/422/503), lease hết hạn... trên fixture NHẸ (matrix tối
thiểu) — nhanh, deterministic, không mạng.

KHÔNG phải test: file này chỉ chứa helper (import bởi các test_*.py).
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
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(TESTS_DIR)))
SCRIPTS_COPY = ['writer-claim.py', 'writer-session.py']

MATRIX_FIELDS = ['id', 'status', 'title', 'slug', 'output_path',
                 'canonical_url', 'expected_url']


def git(cwd, *args, check=True, env=None, input=None):
    e = dict(os.environ)
    e.update({'GIT_AUTHOR_NAME': 'sim', 'GIT_AUTHOR_EMAIL': 'sim@example.com',
              'GIT_COMMITTER_NAME': 'sim',
              'GIT_COMMITTER_EMAIL': 'sim@example.com'})
    if env:
        e.update(env)
    r = subprocess.run(['git'] + list(args), cwd=cwd, capture_output=True,
                       text=True, env=e, input=input)
    if check and r.returncode != 0:
        raise RuntimeError('git %s: %s' % (' '.join(args), r.stderr))
    return r


def make_matrix(n_planned=120, extra_rows=()):
    rows = []
    for i in range(1, n_planned + 1):
        aid = 'BLG-%05d' % i
        rows.append({'id': aid, 'status': 'PLANNED',
                     'title': 'Bai viet so %d' % i,
                     'slug': 'bai-viet-so-%d' % i,
                     'output_path': '_posts/{date}-bai-viet-so-%d.md' % i,
                     'canonical_url': '/c/{date}/bai-viet-so-%d/' % i,
                     'expected_url': '/c/{date}/bai-viet-so-%d/' % i})
    rows.extend(extra_rows)
    return rows


def matrix_text(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=MATRIX_FIELDS, lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


class Sim:
    """origin bare + seed + clones. Mọi thứ nằm trong một thư mục tạm."""

    def __init__(self, n_planned=120, rows=None):
        self.base = tempfile.mkdtemp(prefix='wsim-')
        self.origin = os.path.join(self.base, 'origin.git')
        git(self.base, 'init', '-q', '--bare', '--initial-branch=main',
            self.origin)
        seed = os.path.join(self.base, 'seed')
        git(self.base, 'clone', '-q', self.origin, seed, check=False)
        git(seed, 'checkout', '-q', '-B', 'main')
        os.makedirs(os.path.join(seed, 'scripts', 'factory'))
        for fn in SCRIPTS_COPY:
            shutil.copy(os.path.join(REPO_ROOT, 'scripts', 'factory', fn),
                        os.path.join(seed, 'scripts', 'factory', fn))
        os.makedirs(os.path.join(seed, 'data', 'state'))
        os.makedirs(os.path.join(seed, 'data', 'qa'))
        os.makedirs(os.path.join(seed, '_drafts'))
        self.rows = rows if rows is not None else make_matrix(n_planned)
        with open(os.path.join(seed, 'data', 'content-matrix.csv'), 'w',
                  encoding='utf-8', newline='') as f:
            f.write(matrix_text(self.rows))
        with open(os.path.join(seed, 'data', 'state', 'writer-claims.json'),
                  'w', encoding='utf-8') as f:
            json.dump({'schema_version': '2', 'updated_at': None,
                       'leases': {}}, f, indent=2)
        with open(os.path.join(seed, '_drafts', '.gitkeep'), 'w') as f:
            f.write('')
        git(seed, 'add', '-A')
        git(seed, 'commit', '-q', '-m', 'seed')
        git(seed, 'push', '-q', 'origin', 'HEAD:main')
        self.seed = seed
        self.clones = {}

    def cleanup(self):
        shutil.rmtree(self.base, ignore_errors=True)

    # ------------------------------------------------------------ clones
    def clone(self, name):
        path = os.path.join(self.base, 'clone-' + name)
        git(self.base, 'clone', '-q', self.origin, path)
        git(path, 'checkout', '-q', '-B', 'main', 'origin/main')
        self.clones[name] = path
        return path

    def session_cmd(self, clone, *args, env=None, timeout=120):
        """Chạy writer-session.py của chính clone đó (một phiên độc lập)."""
        path = self.clones[clone] if clone in self.clones else clone
        e = dict(os.environ)
        e['FACTORY_SESSION_BACKOFF'] = '0.01'
        e.pop('FACTORY_WRITER_SESSION', None)
        if env:
            e.update(env)
        return subprocess.run(
            [sys.executable,
             os.path.join(path, 'scripts', 'factory', 'writer-session.py')]
            + list(args), cwd=path, capture_output=True, text=True, env=e,
            timeout=timeout)

    def session_popen(self, clone, *args, env=None):
        path = self.clones[clone]
        e = dict(os.environ)
        e['FACTORY_SESSION_BACKOFF'] = '0.01'
        e.pop('FACTORY_WRITER_SESSION', None)
        if env:
            e.update(env)
        return subprocess.Popen(
            [sys.executable,
             os.path.join(path, 'scripts', 'factory', 'writer-session.py')]
            + list(args), cwd=path, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=e)

    # ---------------------------------------------------- origin helpers
    def origin_show(self, path):
        r = git(self.origin, 'show', 'main:%s' % path, check=False)
        return r.stdout if r.returncode == 0 else None

    def origin_registry(self):
        return json.loads(self.origin_show('data/state/writer-claims.json'))

    def origin_matrix(self):
        return list(csv.DictReader(io.StringIO(
            self.origin_show('data/content-matrix.csv'), newline='')))

    def origin_head(self):
        return git(self.origin, 'rev-parse', 'main').stdout.strip()

    def origin_files(self, prefix):
        out = git(self.origin, 'ls-tree', '-r', '--name-only', 'main',
                  '--', prefix).stdout.split()
        return out

    def origin_commit_count(self):
        return int(git(self.origin, 'rev-list', '--count', 'main'
                       ).stdout.strip())

    def commit_on_origin(self, files, message='external commit',
                         delete=()):
        """Một commit TRỰC TIẾP lên origin main (mô phỏng người/publisher
        khác đẩy). files: {path: text}."""
        wd = os.path.join(self.base, 'ext-%d' % int(time.time() * 1e6))
        git(self.base, 'clone', '-q', self.origin, wd)
        git(wd, 'checkout', '-q', '-B', 'main', 'origin/main')
        for p, txt in files.items():
            full = os.path.join(wd, p)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w', encoding='utf-8') as f:
                f.write(txt)
        for p in delete:
            os.remove(os.path.join(wd, p))
        git(wd, 'add', '-A')
        git(wd, 'commit', '-q', '-m', message)
        git(wd, 'push', '-q', 'origin', 'HEAD:main')
        shutil.rmtree(wd, ignore_errors=True)

    def set_status(self, statuses, message='set status'):
        rows = self.origin_matrix()
        for r in rows:
            if r['id'] in statuses:
                r['status'] = statuses[r['id']]
        self.commit_on_origin({'data/content-matrix.csv': matrix_text(rows)},
                              message)

    def edit_registry(self, fn, message='edit registry'):
        reg = self.origin_registry()
        fn(reg)
        self.commit_on_origin(
            {'data/state/writer-claims.json': json.dumps(reg, indent=2)},
            message)

    # ------------------------------------------------- fault injection
    def install_push_failures(self, count, message='remote: HTTP 503',
                              status_file='push-fail-count'):
        """pre-receive hook: từ chối `count` lần push kế tiếp bằng
        `message` (mô phỏng GitHub 409/422/503), sau đó nhận bình thường."""
        hook = os.path.join(self.origin, 'hooks', 'pre-receive')
        counter = os.path.join(self.origin, status_file)
        with open(counter, 'w') as f:
            f.write(str(count))
        with open(hook, 'w') as f:
            f.write('#!/bin/sh\n'
                    'c=$(cat "%s" 2>/dev/null || echo 0)\n'
                    'if [ "$c" -gt 0 ]; then\n'
                    '  echo $((c-1)) > "%s"\n'
                    '  echo "%s" >&2\n'
                    '  exit 1\n'
                    'fi\n'
                    'exit 0\n' % (counter, counter, message))
        os.chmod(hook, 0o755)

    def remove_push_hook(self):
        hook = os.path.join(self.origin, 'hooks', 'pre-receive')
        if os.path.exists(hook):
            os.remove(hook)


def parse_session_out(stdout):
    """Dòng cuối BLOG_WRITER_SESSION {json}."""
    last = None
    for ln in stdout.splitlines():
        if ln.startswith('BLOG_WRITER_SESSION '):
            last = json.loads(ln[len('BLOG_WRITER_SESSION '):])
    return last


def write_draft(clone, aid, title=None, slot='W1', extra=''):
    """Draft tối thiểu (đủ cho đường CAS; KHÔNG đạt QA thật)."""
    n = int(aid.split('-')[1])
    path = os.path.join(clone, '_drafts', '2026-10-11-bai-viet-so-%d.md' % n)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('---\ntitle: "%s"\narticle_id: %s\nwriter: %s\n---\n\nNoi dung '
                'bai %s.%s\n' % (title or 'Bai viet so %d' % n, aid, slot,
                                 aid, extra))
    return path


class LightRepo:
    """Cây làm việc NHẸ (không git) cho selector/queue: matrix tối thiểu +
    scripts cần thiết. Nhanh hơn FxTestCase (không copy cả repo)."""

    def __init__(self, n_planned=60, rows=None, scripts=None):
        self.root = tempfile.mkdtemp(prefix='lightrepo-')
        sd = os.path.join(self.root, 'scripts', 'factory')
        os.makedirs(sd)
        for fn in (scripts or ['writer-claim.py', 'push-selection.py']):
            shutil.copy(os.path.join(REPO_ROOT, 'scripts', 'factory', fn),
                        os.path.join(sd, fn))
        for d in ('data/state', 'data/qa', 'data/factory', '_drafts',
                  '_posts'):
            os.makedirs(os.path.join(self.root, d), exist_ok=True)
        self.rows = rows if rows is not None else make_matrix(n_planned)
        self.save_matrix()
        self.write_json('data/factory/production-control.json',
                        {'enabled': True, 'chunk_size': 2})

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def write_json(self, rel, obj):
        with open(self.path(rel), 'w', encoding='utf-8') as f:
            json.dump(obj, f)

    def save_matrix(self):
        with open(self.path('data/content-matrix.csv'), 'w',
                  encoding='utf-8', newline='') as f:
            f.write(matrix_text(self.rows))

    def set_status(self, statuses):
        for r in self.rows:
            if r['id'] in statuses:
                r['status'] = statuses[r['id']]
        self.save_matrix()

    def registry(self, leases):
        self.write_json('data/state/writer-claims.json',
                        {'schema_version': '2', 'updated_at': None,
                         'leases': leases})

    def draft(self, aid, writer=None, session=None, body='Noi dung.',
              name=None):
        n = int(aid.split('-')[1])
        fn = name or '2026-10-11-bai-viet-so-%d.md' % n
        fm = ['---', 'title: "Bai viet so %d"' % n, 'article_id: %s' % aid]
        if writer:
            fm.append('writer: %s' % writer)
        if session:
            fm.append('writer_session: %s' % session)
        fm.append('---')
        with open(self.path('_drafts/' + fn), 'w', encoding='utf-8') as f:
            f.write('\n'.join(fm) + '\n\n' + body + '\n')
        return '_drafts/' + fn

    def evidence(self, aid, rel_draft, same=True):
        """Bằng chứng QA: same=True -> content_sha256 khớp draft hiện tại."""
        import hashlib
        with open(self.path(rel_draft), 'rb') as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        self.write_json('data/qa/%s.json' % aid,
                        {'content_sha256': sha if same else 'x' * 64})

    def select(self, added=(), modified=(), backlog=False, changed=(),
               rc_expect=0, env=None):
        ap = self.path('tmp-added.txt')
        mp = self.path('tmp-modified.txt')
        cp = self.path('tmp-changed.txt')
        for p, lines in ((ap, added), (mp, modified), (cp, changed)):
            with open(p, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + ('\n' if lines else ''))
        args = [sys.executable,
                os.path.join(self.root, 'scripts', 'factory',
                             'push-selection.py'),
                '--added', ap, '--modified', mp]
        if changed:
            args += ['--changed', cp]
        if backlog:
            args.append('--backlog')
        e = dict(os.environ)
        e.pop('GITHUB_OUTPUT', None)
        e.pop('WRITER_CLAIMS', None)
        if env:
            e.update(env)
        r = subprocess.run(args, cwd=self.root, capture_output=True,
                           text=True, env=e)
        assert r.returncode == rc_expect, (
            'push-selection rc=%d (ky vong %d): %s%s'
            % (r.returncode, rc_expect, r.stdout, r.stderr))
        lines = [l for l in r.stdout.splitlines()
                 if l.strip().startswith('{')]
        return r.returncode, json.loads(lines[-1]), r
