#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run-tests.py — chạy bộ test engine OFFLINE (stdlib + git), song song.

  python3 scripts/factory/run-tests.py --suites ci [--jobs 3] [--only test_x,test_y]

Nhóm suite:
  ci    suite phải XANH trên mọi thay đổi engine (quality-gate.yml, job
        engine-tests): unit + hợp đồng workflow + đa-writer + mô phỏng
        đồng thời ĐẦU-CUỐI với engine thật (test_multiwriter_sim);
  data  suite kiểm DỮ LIỆU production (đỏ nếu dữ liệu lệch — không phải lỗi
        engine): link nội bộ của matrix, bằng chứng QA của bài đã publish...;
  heavy suite rất chậm (soak);
  all   ci + data + heavy.

Mỗi suite là một script unittest độc lập; chạy trong tiến trình riêng
(cwd = gốc repo), KHÔNG mạng, KHÔNG đụng production state (fixture sao
chép/clone cục bộ). Thoát 0 chỉ khi mọi suite được chọn đều PASS.
"""
import os
import sys

# scripts/factory/queue.py (script legacy) che module `queue` của stdlib khi
# chạy `python3 scripts/factory/run-tests.py` (sys.path[0] = thư mục script) →
# `concurrent.futures` import hỏng. Bỏ thư mục script khỏi sys.path TRƯỚC mọi
# import khác (các suite con chạy ở tiến trình riêng nên không bị ảnh hưởng).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path
               if os.path.abspath(p or os.getcwd()) != _HERE]

import argparse  # noqa: E402
import concurrent.futures  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TESTS = os.path.join(ROOT, 'scripts', 'factory', 'tests')

CI = [
    # hợp đồng workflow / gate (rất nhanh)
    'test_gate_scope', 'test_workflow_syntax', 'test_agent_integration',
    'test_operator', 'test_publish_gate', 'test_production_watchdog',
    'test_reports_resume', 'test_repair_agent', 'test_supervisor_agent',
    'test_topic_universe', 'test_legacy_qa_audit', 'test_reattest_legacy_qa',
    'test_faq',
    # refill / publish flow
    'test_refill_safety', 'test_refill_semantics', 'test_refill_drift',
    'test_slugify_vi',
    'test_publish_flow',
    # đa-writer: registry, selector, queue, push an toàn, CAS client
    'test_writer_claim', 'test_selector_ownership', 'test_selector_drain',
    'test_push_selection', 'test_factory_queue', 'test_publisher_push',
    'test_writer_session', 'test_writer_loop',
    # hợp đồng tĩnh/hardening + watchdog
    'test_hardening', 'test_watchdog',
    # mô phỏng đồng thời đầu-cuối (engine thật, origin bare cục bộ)
    'test_multiwriter_sim',
]
DATA = ['test_built_links', 'test_link_integrity', 'test_qa_modes']
HEAVY = ['test_soak_recovery']
GROUPS = {'ci': CI, 'data': DATA, 'heavy': HEAVY,
          'all': CI + DATA + HEAVY}
# chạy trước (chậm nhất) để cân bằng song song
SLOW_FIRST = ['test_multiwriter_sim', 'test_soak_recovery',
              'test_push_selection', 'test_factory_queue', 'test_hardening',
              'test_qa_modes', 'test_watchdog', 'test_writer_claim',
              'test_writer_session']


def run_suite(name, timeout):
    path = os.path.join(TESTS, name + '.py')
    t0 = time.time()
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        r = subprocess.run([sys.executable, '-W', 'ignore', path], cwd=ROOT,
                           capture_output=True, text=True, timeout=timeout,
                           env=env)
        rc, out = r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        rc, out = 124, 'TIMEOUT sau %ss\n%s' % (timeout, (e.stdout or '')[-2000:]
                                               if isinstance(e.stdout, str)
                                               else '')
    return name, rc, time.time() - t0, out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--suites', choices=sorted(GROUPS), default='ci')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--only', default='')
    ap.add_argument('--timeout', type=int, default=1500)
    a = ap.parse_args()
    names = list(GROUPS[a.suites])
    if a.only:
        want = [x.strip() for x in a.only.split(',') if x.strip()]
        unknown = [w for w in want if w not in GROUPS['all']]
        if unknown:
            print('suite khong ton tai: %s' % ', '.join(unknown))
            return 2
        names = [n for n in names if n in want]
    if not names:
        print('khong co suite nao duoc chon (nhom %s, --only %r)'
              % (a.suites, a.only))
        return 2
    names.sort(key=lambda n: (SLOW_FIRST.index(n) if n in SLOW_FIRST
                              else len(SLOW_FIRST)))
    missing = [n for n in names
               if not os.path.exists(os.path.join(TESTS, n + '.py'))]
    if missing:
        print('THIEU suite: %s' % ', '.join(missing))
        return 2
    t0 = time.time()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(run_suite, n, a.timeout) for n in names]
        for f in concurrent.futures.as_completed(futs):
            name, rc, dt, out = f.result()
            results.append((name, rc, dt, out))
            print('%-28s %s  %6.1fs' % (name, 'PASS' if rc == 0 else
                                        'FAIL(rc=%d)' % rc, dt), flush=True)
    failed = [r for r in results if r[1] != 0]
    for name, rc, dt, out in failed:
        print('\n===== %s (rc=%d) — duoi output =====' % (name, rc))
        print('\n'.join(out.splitlines()[-60:]))
    print('\nTONG: %d suite, %d PASS, %d FAIL, %.0fs'
          % (len(results), len(results) - len(failed), len(failed),
             time.time() - t0))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
