#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publisher-push.py — commit + push AN TOÀN cho factory-publish.yml.

Thay khối shell `git add -A / commit / until git push; do rebase` cũ.
Lý do (audit P0-3, tái hiện được): khi push của publisher bị từ chối
(non-fast-forward vì writer vừa đẩy commit mới) quy trình cũ chạy
`git rebase origin/main`. Nếu writer đồng thời đẩy bản SỬA của một draft
mà publisher vừa chuyển `_drafts/x.md -> _posts/x.md`, git phát hiện
rename và ÂM THẦM áp bản sửa chưa QA lên bài đã publish: rebase "thành
công", nội dung bài khác nội dung đã chấm QA (đi vòng content_sha256).
`merge.renames=false` / `-X no-renames` KHÔNG ngăn được với git 2.43 (ort).

Hợp đồng mới (KHÔNG force push, KHÔNG sửa nội dung writer):
  1. `git add -A`; không có thay đổi -> thoát 0;
  2. INTEGRITY trước push: mọi `_posts/*.md` thêm/sửa trong commit phải có
     sha256 == data/qa/<article_id>.json.content_sha256 (nội dung đã
     publish == nội dung đã chấm QA);
  3. push; nếu bị từ chối non-FF:
       - fetch origin/main;
       - GUARD ĐỘC LẬP: tập path upstream đổi (merge-base..origin/main) giao
         tập path commit này đụng (add/modify/DELETE, KHÔNG dò rename) =
         rỗng. Giao khác rỗng (ví dụ writer sửa draft vừa bị chuyển) ->
         DỪNG, KHÔNG rebase, KHÔNG push, exit 1: main không đổi, run kế
         drain lại từ truth mới (không mất draft, không lọt nội dung);
       - rebase origin/main (không giao nhau nên sạch); xung đột -> abort;
       - INTEGRITY lần nữa SAU rebase; lệch -> DỪNG;
       - push lại (giới hạn MAX_REBASES lần, backoff);
  4. lỗi mạng/5xx/429 tạm thời: backoff 2,4,8,16s (tối đa 4 lần);
  5. in JSON một dòng `BLOG_PUBLISHER_PUSH {...}`; $GITHUB_OUTPUT nhận
     `pushed=true|false`.

Chỉ git + stdlib; KHÔNG API ngoài, KHÔNG AI, KHÔNG secret.

Thoát: 0 = đã push (hoặc không có gì để push); 1 = dừng an toàn (main KHÔNG
đổi, commit còn ở runner — run kế drain lại).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QA_DIR = 'data/qa'
MAX_REBASES = 3
NET_RETRIES = 4
FRONT_ID_RE = re.compile(r'^article_id:\s*(BLG-\d+)', re.M)
REJECT_RE = re.compile(r'(rejected|non-fast-forward|fetch first|stale info)',
                       re.I)
TRANSIENT_RE = re.compile(
    r'(\b50[0-4]\b|\b429\b|timed out|timeout|connection (reset|refused)|'
    r'could not resolve|rpc failed|early eof|unexpected disconnect|'
    r'remote end hung up|temporarily unavailable|try again|'
    r'cannot lock ref|reference update failed|\b409\b|\b422\b)', re.I)


def sh(args, check=False, cwd=None):
    r = subprocess.run(['git'] + list(args), cwd=cwd or ROOT,
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError('git %s: %s' % (' '.join(args),
                                           (r.stderr or r.stdout).strip()))
    return r


def _scale():
    try:
        return float(os.environ.get('FACTORY_PUSH_BACKOFF', '1'))
    except ValueError:
        return 1.0


def _sleep(sec):
    s = sec * _scale()
    if s > 0:
        time.sleep(s)


def changed_paths(a, b, cwd=None):
    """Path đổi giữa a..b, KHÔNG dò rename (rename = delete + add: cả hai
    path đều tính) -> guard giao nhau không bị rename heuristic đánh lừa."""
    r = sh(['diff', '--name-only', '--no-renames', '-z', a, b], cwd=cwd)
    return {p for p in r.stdout.split('\0') if p}


def integrity_problems(cwd=None):
    """Mọi _posts/*.md thay đổi trong commit HEAD (so với HEAD~1 nếu có)
    phải khớp bằng chứng QA. Trả list lỗi."""
    cwd = cwd or ROOT
    base = sh(['rev-parse', '--verify', '-q', 'HEAD~1'], cwd=cwd)
    if base.returncode != 0:
        return []
    out = sh(['diff', '--name-status', '--no-renames', '-z', 'HEAD~1',
              'HEAD', '--', '_posts/'], cwd=cwd).stdout.split('\0')
    problems = []
    i = 0
    while i + 1 < len(out):
        status, path = out[i], out[i + 1]
        i += 2
        if not status or status.startswith('D') or not path.endswith('.md'):
            continue
        full = os.path.join(cwd, path)
        try:
            with open(full, 'rb') as f:
                data = f.read()
        except OSError:
            problems.append('%s: khong doc duoc' % path)
            continue
        m = FRONT_ID_RE.search(data[:3000].decode('utf-8', 'replace'))
        if not m:
            continue            # bài legacy không có article_id: không áp
        aid = m.group(1)
        ev = os.path.join(cwd, QA_DIR, aid + '.json')
        try:
            with open(ev, encoding='utf-8') as f:
                want = (json.load(f) or {}).get('content_sha256')
        except (OSError, ValueError):
            problems.append('%s: thieu bang chung QA %s' % (path, ev))
            continue
        got = hashlib.sha256(data).hexdigest()
        if want != got:
            problems.append('%s: sha256 noi dung %s != QA content_sha256 %s '
                            '(noi dung khac noi dung da cham QA)'
                            % (path, got[:12], (want or '-')[:12]))
    return problems


def emit(code, **kw):
    kw['exit'] = code
    print('BLOG_PUBLISHER_PUSH ' + json.dumps(kw, ensure_ascii=False))
    gout = os.environ.get('GITHUB_OUTPUT')
    if gout:
        try:
            with open(gout, 'a', encoding='utf-8') as f:
                f.write('pushed=%s\n' % ('true' if kw.get('pushed') else
                                         'false'))
        except OSError:
            pass
    return code


def run(message, remote='origin', branch='main', max_rebases=MAX_REBASES,
        cwd=None):
    global ROOT
    if cwd:
        ROOT = cwd
    sh(['add', '-A'], check=True)
    if sh(['diff', '--cached', '--quiet']).returncode == 0:
        print('no state changes to commit')
        return emit(0, pushed=False, reason='no_changes')
    sh(['commit', '-q', '-m', message], check=True)
    probs = integrity_problems()
    if probs:
        for p in probs:
            print('INTEGRITY: %s' % p, file=sys.stderr)
        return emit(1, pushed=False, reason='integrity_before_push',
                    problems=probs)
    rebases = 0
    net = 0
    while True:
        r = sh(['push', '-q', remote, 'HEAD:refs/heads/%s' % branch])
        if r.returncode == 0:
            head = sh(['rev-parse', 'HEAD']).stdout.strip()
            print('push ok (%s)' % head[:10])
            return emit(0, pushed=True, head=head, rebases=rebases)
        err = (r.stderr + r.stdout).strip()
        if REJECT_RE.search(err):
            if rebases >= max_rebases:
                print('push failed after %d rebases (non-FF races); '
                      'leaving committed state for the next run' % rebases,
                      file=sys.stderr)
                return emit(1, pushed=False, reason='rebases_exhausted')
            rebases += 1
            f = sh(['fetch', '-q', remote, branch])
            if f.returncode != 0:
                _sleep(2 ** rebases)
                continue
            up = '%s/%s' % (remote, branch)
            base = sh(['merge-base', 'HEAD', up]).stdout.strip()
            if not base:
                return emit(1, pushed=False, reason='no_merge_base')
            theirs = changed_paths(base, up)
            mine = changed_paths(base, 'HEAD')
            overlap = sorted(theirs & mine)
            if overlap:
                print('UPSTREAM_TOUCHED_PUBLISHER_PATHS: %s — KHONG rebase '
                      '(tranh git ghep sua doi cua writer vao bai da '
                      'publish); main khong doi, run ke drain lai'
                      % ', '.join(overlap[:10]), file=sys.stderr)
                return emit(1, pushed=False, reason='upstream_overlap',
                            overlap=overlap[:20])
            rb = sh(['rebase', up])
            if rb.returncode != 0:
                sh(['rebase', '--abort'])
                print('rebase conflict; aborting (no force push)',
                      file=sys.stderr)
                return emit(1, pushed=False, reason='rebase_conflict')
            probs = integrity_problems()
            if probs:
                for p in probs:
                    print('INTEGRITY(after rebase): %s' % p, file=sys.stderr)
                return emit(1, pushed=False, reason='integrity_after_rebase',
                            problems=probs)
            print('push race lost; rebased onto %s (khong giao path), '
                  'thu lai (lan %d)' % (up, rebases))
            continue
        if TRANSIENT_RE.search(err) and net < NET_RETRIES:
            net += 1
            print('push loi tam thoi (%s) — thu lai sau backoff'
                  % err.splitlines()[-1][:120], file=sys.stderr)
            _sleep(2 ** net)
            continue
        print('push failed: %s' % err[-300:], file=sys.stderr)
        return emit(1, pushed=False, reason='push_failed', error=err[-300:])


def main(argv=None):
    ap = argparse.ArgumentParser(description='Safe publisher commit/push')
    ap.add_argument('--message', required=True)
    ap.add_argument('--remote', default='origin')
    ap.add_argument('--branch', default='main')
    ap.add_argument('--max-rebases', type=int, default=MAX_REBASES)
    ap.add_argument('--cwd', default=None)
    a = ap.parse_args(argv)
    return run(a.message, a.remote, a.branch, a.max_rebases, a.cwd)


if __name__ == '__main__':
    sys.exit(main())
