#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test CAS client writer-session.py + registry v2 (writer-claim.py) —
MÔ PHỎNG OFFLINE nhiều phiên AI writer độc lập trên origin bare cục bộ.

Bao phủ các kịch bản đồng thời bắt buộc:
  1. 3 writer W1/W2/W3 claim cùng lúc -> 3 slot khác nhau, ID rời nhau;
  2. 3 writer push gần như cùng lúc -> đủ 30 draft, không đè nhau,
     registry giữ đủ 3 lease;
  3. 2 writer claim CÙNG một ID -> chỉ MỘT thắng;
  4. 2 phiên dùng CHUNG một slot -> phiên sau bị từ chối, registry nguyên;
  5. writer hết quota giữa batch (push dở) -> ID đã push còn nguyên,
     ID chưa push reclaim được sau khi lease hết hạn;
  6. writer mất kết nối giữ lease -> không chiếm khi còn hạn; hết hạn
     thì phiên khác reclaim hợp lệ (epoch +1) và phiên cũ bị chặn push;
  7. push bị từ chối 409/422/503 -> retry có giới hạn, rồi thành công,
     KHÔNG force push;
  8. mất lease giữa chừng -> push dừng (exit 5), KHÔNG push gì;
  9. resume-first theo từng writer khi có REPAIR; --adopt nhận orphan;
 10. bàn giao slot bằng --session (AI này -> AI khác);
 11. múi giờ máy KHÔNG ảnh hưởng hạn lease (UTC);
 12. registry hỏng -> fail-closed (không coi là rỗng).

Chạy: python3 scripts/factory/tests/test_writer_session.py
"""
import json
import os
import re
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_helpers import (Sim, git, make_matrix, matrix_text,
                         parse_session_out, write_draft, REPO_ROOT)


def ok_out(r):
    out = parse_session_out(r.stdout)
    assert out is not None, 'khong co BLOG_WRITER_SESSION: %s%s' % (
        r.stdout, r.stderr)
    return out


class SessionBase(unittest.TestCase):
    def setUp(self):
        self.sim = Sim(n_planned=120)
        self.addCleanup(self.sim.cleanup)

    def begin(self, clone, *extra, expect=0):
        r = self.sim.session_cmd(clone, 'begin', *extra)
        out = parse_session_out(r.stdout)
        self.assertEqual(r.returncode, expect, r.stdout + r.stderr)
        return out

    def ids(self, out):
        return out['leased_total']


class TestConcurrentClaims(SessionBase):

    def test_01_three_writers_begin_concurrently(self):
        for n in ('a', 'b', 'c'):
            self.sim.clone(n)
        procs = [self.sim.session_popen(n, 'begin', '--slot', 'auto')
                 for n in ('a', 'b', 'c')]
        outs = []
        for p in procs:
            so, se = p.communicate(timeout=120)
            self.assertEqual(p.returncode, 0, so + se)
            outs.append(parse_session_out(so))
        slots = sorted(o['slot'] for o in outs)
        self.assertEqual(slots, ['W1', 'W2', 'W3'])
        all_ids = [i for o in outs for i in o['leased_total']]
        self.assertEqual(len(all_ids), 30)
        self.assertEqual(len(set(all_ids)), 30, 'khong ID nao bi giu 2 lan')
        reg = self.sim.origin_registry()
        self.assertEqual(sorted(reg['leases']), ['W1', 'W2', 'W3'])
        sessions = {l['session'] for l in reg['leases'].values()}
        self.assertEqual(len(sessions), 3, 'moi slot mot phien rieng')
        for l in reg['leases'].values():
            self.assertEqual(len(l['ids']), 10)

    def test_02_two_writers_race_same_explicit_id(self):
        self.sim.clone('a')
        self.sim.clone('b')
        pa = self.sim.session_popen('a', 'begin', '--slot', 'W1',
                                    '--ids', 'BLG-00005')
        pb = self.sim.session_popen('b', 'begin', '--slot', 'W2',
                                    '--ids', 'BLG-00005')
        res = []
        for p in (pa, pb):
            so, se = p.communicate(timeout=120)
            res.append((p.returncode, parse_session_out(so)))
        codes = sorted(c for c, _ in res)
        self.assertEqual(codes, [0, 1], 'dung MOT writer thang ID: %s' % res)
        reg = self.sim.origin_registry()
        holders = [w for w, l in reg['leases'].items()
                   if 'BLG-00005' in l['ids']]
        self.assertEqual(len(holders), 1)
        loser = [o for c, o in res if c == 1][0]
        self.assertIn(loser['code'], ('ID_TAKEN', 'NOT_PLANNED'))

    def test_03_two_sessions_same_slot_second_refused(self):
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W1')
        before = self.sim.origin_head()
        r = self.sim.session_cmd('b', 'begin', '--slot', 'W1')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        out = parse_session_out(r.stdout)
        self.assertEqual(out['code'], 'SLOT_HELD')
        self.assertEqual(self.sim.origin_head(), before,
                         'tu choi KHONG duoc doi gi tren origin')
        reg = self.sim.origin_registry()
        self.assertEqual(reg['leases']['W1']['session'], a['session'])
        # phiên đầu vẫn renew được (resume idempotent)
        a2 = self.begin('a', '--slot', 'W1')
        self.assertEqual(a2['session'], a['session'])
        self.assertEqual(a2['leased_total'], a['leased_total'])

    def test_04_fourth_session_gets_no_free_slot(self):
        for n in ('a', 'b', 'c', 'd'):
            self.sim.clone(n)
        for n in ('a', 'b', 'c'):
            self.begin(n, '--slot', 'auto')
        r = self.sim.session_cmd('d', 'begin', '--slot', 'auto')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(parse_session_out(r.stdout)['code'], 'NO_FREE_SLOT')
        self.assertEqual(sorted(self.sim.origin_registry()['leases']),
                         ['W1', 'W2', 'W3'])

    def test_05_slot_auto_resumes_own_slot(self):
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'auto')
        a2 = self.begin('a', '--slot', 'auto')
        self.assertEqual(a['slot'], a2['slot'])
        self.assertEqual(a['leased_total'], a2['leased_total'])
        self.assertEqual(len(self.sim.origin_registry()['leases']), 1)


class TestPushes(SessionBase):

    def _begin_all(self):
        names = ('a', 'b', 'c')
        for n in names:
            self.sim.clone(n)
        outs = {}
        for n in names:
            outs[n] = self.begin(n, '--slot', 'auto')
        return outs

    def test_10_three_writers_push_near_simultaneously(self):
        outs = self._begin_all()
        for n, o in outs.items():
            for aid in o['leased_total']:
                write_draft(self.sim.clones[n], aid, slot=o['slot'])
        procs = {n: self.sim.session_popen(n, 'push', '--no-qa')
                 for n in outs}
        for n, p in procs.items():
            so, se = p.communicate(timeout=180)
            self.assertEqual(p.returncode, 0, so + se)
            res = parse_session_out(so)
            self.assertEqual(len(res['pushed']), 10)
        files = [f for f in self.sim.origin_files('_drafts/')
                 if f.endswith('.md')]
        self.assertEqual(len(files), 30, 'du 30 draft, khong cai nao bi de')
        reg = self.sim.origin_registry()
        self.assertEqual(sorted(reg['leases']), ['W1', 'W2', 'W3'],
                         'heartbeat cua 3 writer khong de nhau')
        sess = {n: o['session'] for n, o in outs.items()}
        for n, o in outs.items():
            self.assertEqual(reg['leases'][o['slot']]['session'], sess[n])
        # mỗi draft mang đúng identity của chủ lease
        for n, o in outs.items():
            for aid in o['leased_total']:
                num = int(aid.split('-')[1])
                txt = self.sim.origin_show(
                    '_drafts/2026-10-11-bai-viet-so-%d.md' % num)
                self.assertIn('writer: %s' % o['slot'], txt)
                self.assertIn('writer_session: %s' % o['session'], txt)

    def test_11_push_retries_on_503_409_422_without_force(self):
        self.sim.clone('a')
        o = self.begin('a', '--slot', 'W1')
        for aid in o['leased_total'][:3]:
            write_draft(self.sim.clones['a'], aid, slot='W1')
        for msg in ('remote: HTTP 503 Service Unavailable',
                    'remote: error: HTTP 409 Conflict',
                    'remote: error: HTTP 422 Unprocessable Entity'):
            self.sim.install_push_failures(2, msg)
            r = self.sim.session_cmd('a', 'push', '--no-qa',
                                     '--ids', o['leased_total'][0])
            self.assertEqual(r.returncode, 0, msg + r.stdout + r.stderr)
            res = parse_session_out(r.stdout)
            self.sim.remove_push_hook()
            # lần đầu: đã đẩy sau >= 3 lần thử; các lần sau idempotent
            self.assertTrue(res.get('attempts', 1) >= 1)
        files = [f for f in self.sim.origin_files('_drafts/')
                 if f.endswith('.md')]
        self.assertEqual(len(files), 1)
        with open(os.path.join(REPO_ROOT, 'scripts', 'factory',
                               'writer-session.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIsNone(re.search(r'--force(?!-remove)', src),
                          'tuyet doi khong force push')
        self.assertNotIn('--force-with-lease', src)
        self.assertNotIn("'+refs", src)

    def test_12_push_gives_up_after_bounded_attempts(self):
        self.sim.clone('a')
        o = self.begin('a', '--slot', 'W1')
        aid = o['leased_total'][0]
        write_draft(self.sim.clones['a'], aid, slot='W1')
        self.sim.install_push_failures(50, 'remote: HTTP 503')
        head = self.sim.origin_head()
        r = self.sim.session_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(parse_session_out(r.stdout)['code'], 'CAS_EXHAUSTED')
        self.assertEqual(self.sim.origin_head(), head)
        # draft vẫn còn nguyên ở working copy (không mất việc)
        self.assertTrue(os.path.exists(os.path.join(
            self.sim.clones['a'], '_drafts', '2026-10-11-bai-viet-so-%d.md'
            % int(aid.split('-')[1]))))

    def test_13_push_survives_concurrent_external_commits(self):
        self.sim.clone('a')
        o = self.begin('a', '--slot', 'W1')
        for aid in o['leased_total']:
            write_draft(self.sim.clones['a'], aid, slot='W1')
        # origin đã tiến lên (publisher/người khác đẩy) sau lần fetch cuối
        self.sim.commit_on_origin({'reports/x.txt': 'factory moved\n'},
                                  'factory: publish (simulated)')
        r = self.sim.session_cmd('a', 'push', '--no-qa')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('reports/x.txt',
                      git(self.sim.origin, 'ls-tree', '-r', '--name-only',
                          'main').stdout)
        self.assertEqual(len(parse_session_out(r.stdout)['pushed']), 10)

    def test_14_push_is_idempotent(self):
        self.sim.clone('a')
        o = self.begin('a', '--slot', 'W1')
        aid = o['leased_total'][0]
        write_draft(self.sim.clones['a'], aid, slot='W1')
        r1 = self.sim.session_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        head = self.sim.origin_head()
        r2 = self.sim.session_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(self.sim.origin_head(), head,
                         'push lap lai KHONG tao commit moi')

    def test_15_cannot_push_ids_not_in_lease(self):
        self.sim.clone('a')
        self.begin('a', '--slot', 'W1')
        write_draft(self.sim.clones['a'], 'BLG-00100', slot='W1')
        r = self.sim.session_cmd('a', 'push', '--no-qa', '--ids',
                                 'BLG-00100')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(parse_session_out(r.stdout)['code'], 'NOT_MY_IDS')
        self.assertEqual([f for f in self.sim.origin_files('_drafts/')
                          if f.endswith('.md')], [])


class TestLeaseLifecycle(SessionBase):

    def test_20_out_of_quota_partial_batch_then_reclaim(self):
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W1')
        ids = a['leased_total']
        for aid in ids[:4]:
            write_draft(self.sim.clones['a'], aid, slot='W1')
        r = self.sim.session_cmd('a', 'push', '--no-qa',
                                 '--ids', ','.join(ids[:4]))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # A hết quota / biến mất; B cố chiếm slot khi lease còn hạn -> bị chặn
        rb = self.sim.session_cmd('b', 'begin', '--slot', 'W1')
        self.assertEqual(rb.returncode, 1)
        self.assertEqual(parse_session_out(rb.stdout)['code'], 'SLOT_HELD')
        # B dùng slot khác: chỉ nhận ID KHÔNG thuộc lease sống của A
        b = self.begin('b', '--slot', 'W2')
        self.assertFalse(set(b['leased_total']) & set(ids))
        # lease của A hết hạn -> B reclaim slot W1 hợp lệ; 4 draft đã push
        # của A vẫn còn trên origin (không mất việc)
        self.sim.edit_registry(
            lambda reg: reg['leases']['W1'].update(
                expires_at='2000-01-01T00:00:00Z'))
        c_ids = [f for f in self.sim.origin_files('_drafts/')
                 if f.endswith('.md')]
        self.assertEqual(len(c_ids), 4)

    def test_21_disconnect_expiry_takeover_blocks_old_session(self):
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W1')
        aid = a['leased_total'][0]
        write_draft(self.sim.clones['a'], aid, slot='W1')
        self.sim.edit_registry(
            lambda reg: reg['leases']['W1'].update(
                expires_at='2000-01-01T00:00:00Z'))
        b = self.begin('b', '--slot', 'W1')
        self.assertEqual(b['epoch'], a['epoch'] + 1, 'epoch tang khi doi chu')
        self.assertIsNotNone(b.get('takeover'))
        self.assertEqual(b['takeover']['previous_session'], a['session'])
        self.assertIn(aid, b['leased_total'],
                      'ID PLANNED cua lease het han duoc reclaim')
        # A tỉnh lại, push -> bị chặn: KHÔNG push gì
        head = self.sim.origin_head()
        r = self.sim.session_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertEqual(parse_session_out(r.stdout)['code'], 'LEASE_LOST')
        self.assertEqual(self.sim.origin_head(), head)

    def test_22_never_seize_live_lease(self):
        self.sim.clone('a')
        self.sim.clone('b')
        self.begin('a', '--slot', 'W1', '--ttl-hours', '1')
        reg = self.sim.origin_registry()
        before = json.dumps(reg['leases']['W1'], sort_keys=True)
        r = self.sim.session_cmd('b', 'begin', '--slot', 'W1')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.dumps(
            self.sim.origin_registry()['leases']['W1'], sort_keys=True),
            before)

    def test_23_lease_lost_midway_pushes_nothing(self):
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1')
        aid = a['leased_total'][0]
        write_draft(self.sim.clones['a'], aid, slot='W1')
        self.sim.edit_registry(
            lambda reg: reg['leases']['W1'].update(session='s-someoneelse'))
        head = self.sim.origin_head()
        r = self.sim.session_cmd('a', 'push', '--no-qa')
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertEqual(self.sim.origin_head(), head)

    def test_24_handoff_between_ais_with_session_id(self):
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W2', '--label', 'ai-one')
        # AI một hết quota, đưa session id cho AI hai (clone/container khác)
        b = self.begin('b', '--slot', 'W2', '--session', a['session'],
                       '--label', 'ai-two')
        self.assertEqual(b['session'], a['session'])
        self.assertEqual(b['leased_total'], a['leased_total'])
        self.assertEqual(b['epoch'], a['epoch'], 'bàn giao KHÔNG đổi chủ')

    def test_25_release_all_frees_slot(self):
        self.sim.clone('a')
        self.sim.clone('b')
        self.begin('a', '--slot', 'W1')
        r = self.sim.session_cmd('a', 'release', '--all')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn('W1', self.sim.origin_registry()['leases'])
        b = self.begin('b', '--slot', 'W1')
        self.assertEqual(b['slot'], 'W1')

    def test_26_other_session_cannot_release_or_heartbeat(self):
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W1')
        r = self.sim.session_cmd('b', 'release', '--slot', 'W1', '--all')
        # b không có session khớp -> không tìm thấy lease của mình: no-op
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.sim.origin_registry()['leases']['W1']
                         ['session'], a['session'])

    def test_27_resume_first_when_repair_rows(self):
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1')
        ids = a['leased_total']
        self.sim.set_status({ids[0]: 'REPAIR', ids[1]: 'REPAIR'})
        # còn REPAIR: begin KHÔNG claim thêm ID mới (resume-first của chính
        # writer này, KHÔNG chặn writer khác)
        a2 = self.begin('a', '--slot', 'W1')
        self.assertEqual(sorted(a2['repair_first']), sorted(ids[:2]))
        self.assertEqual(a2['leased_total'], ids)
        self.assertTrue(a2['resume_only_repair_first'])
        a3 = self.begin('a', '--slot', 'W1', '--allow-new-with-repair')
        self.assertEqual(a3['leased_total'], ids, 'lease da day 10')

    def test_28_orphan_repair_can_be_adopted_after_expiry(self):
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W1')
        rid = a['leased_total'][0]
        self.sim.set_status({rid: 'REPAIR'})
        self.sim.edit_registry(
            lambda reg: reg['leases']['W1'].update(
                expires_at='2000-01-01T00:00:00Z'))
        # không có --adopt: từ chối (hàng in-flight orphan)
        r = self.sim.session_cmd('b', 'begin', '--slot', 'W2', '--ids', rid)
        self.assertEqual(r.returncode, 1, r.stdout)
        r = self.sim.session_cmd('b', 'begin', '--slot', 'W2', '--ids', rid,
                                 '--adopt')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(rid, parse_session_out(r.stdout)['leased_total'])


class TestRegistryRobustness(SessionBase):

    def test_30_corrupt_registry_fails_closed(self):
        self.sim.clone('a')
        self.sim.commit_on_origin(
            {'data/state/writer-claims.json': '{"leases": '},
            'corrupt registry')
        r = self.sim.session_cmd('a', 'begin', '--slot', 'W1')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(parse_session_out(r.stdout)['code'],
                         'REGISTRY_CORRUPT')
        self.assertEqual(self.sim.origin_show(
            'data/state/writer-claims.json'), '{"leases": ',
            'khong ghi de registry hong')

    def test_31_timezone_does_not_change_lease_expiry(self):
        sys.path.insert(0, os.path.join(REPO_ROOT, 'scripts', 'factory'))
        code = ('import importlib.util, time, calendar, os\n'
                'spec = importlib.util.spec_from_file_location("wc", %r)\n'
                'm = importlib.util.module_from_spec(spec); '
                'spec.loader.exec_module(m)\n'
                'iso = "2026-10-11T15:05:00Z"\n'
                'want = calendar.timegm(time.strptime(iso, "%%Y-%%m-%%dT%%H:%%M:%%SZ"))\n'
                'print(int(m._epoch_of(iso) - want))\n'
                % os.path.join(REPO_ROOT, 'scripts', 'factory',
                               'writer-claim.py'))
        for tz in ('UTC', 'Asia/Ho_Chi_Minh', 'America/Los_Angeles'):
            r = subprocess.run([sys.executable, '-c', code],
                               capture_output=True, text=True,
                               env=dict(os.environ, TZ=tz))
            self.assertEqual(r.stdout.strip(), '0',
                             'lech gio theo TZ=%s: %s%s' % (tz, r.stdout,
                                                            r.stderr))

    def test_32_legacy_v1_lease_is_adopted_not_dropped(self):
        self.sim.clone('a')
        legacy = {'schema_version': '1', 'updated_at': None, 'leases': {
            'W1': {'ids': ['BLG-00001', 'BLG-00002'],
                   'claimed_at': '2026-10-11T00:00:00Z',
                   'expires_at': '2099-01-01T00:00:00Z'}}}
        self.sim.commit_on_origin(
            {'data/state/writer-claims.json': json.dumps(legacy)},
            'legacy v1 lease')
        a = self.begin('a', '--slot', 'W1')
        self.assertTrue(a['legacy_adopted'])
        self.assertEqual(a['leased_total'][:2], ['BLG-00001', 'BLG-00002'])
        self.assertEqual(a['claimed_at'], '2026-10-11T00:00:00Z',
                         'claimed_at goc khong bi reset khi renew')

    def test_33_status_is_read_only_and_reports_next_action(self):
        self.sim.clone('a')
        head = self.sim.origin_head()
        r = self.sim.session_cmd('a', 'status')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = parse_session_out(r.stdout)
        self.assertEqual(out['free_slots'], ['W1', 'W2', 'W3'])
        self.assertIn('begin', out['next_action'])
        self.assertEqual(self.sim.origin_head(), head)


class TestConfirm(SessionBase):

    def test_40_confirm_reports_published(self):
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1')
        ids = a['leased_total'][:2]
        self.sim.set_status({i: 'PUBLISHED' for i in ids})
        r = self.sim.session_cmd('a', 'confirm', '--ids', ','.join(ids),
                                 '--timeout', '5', '--poll', '0.2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(parse_session_out(r.stdout)['published']),
                         sorted(ids))

    def test_41_confirm_reports_repair_with_failed_checks(self):
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1')
        rid = a['leased_total'][0]
        self.sim.set_status({rid: 'REPAIR'})
        self.sim.commit_on_origin({'data/qa/%s.json' % rid: json.dumps(
            {'checks': {'word_count': False, 'h2_min': True},
             'quality': 60, 'seo': 80, 'business_fact': 'PASS',
             'legal': 'NOT_REQUIRED', 'bad_routes': ['/khong-co/']})},
            'qa evidence')
        r = self.sim.session_cmd('a', 'confirm', '--ids', rid,
                                 '--timeout', '5', '--poll', '0.2')
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        rep = parse_session_out(r.stdout)['repair'][rid]
        self.assertEqual(rep['failed_checks'], ['word_count'])
        self.assertEqual(rep['bad_routes'], ['/khong-co/'])

    def test_42_confirm_pending_nudges_publisher_trigger(self):
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1')
        aid = a['leased_total'][0]
        r = self.sim.session_cmd('a', 'confirm', '--ids', aid,
                                 '--timeout', '3', '--poll', '0.3',
                                 '--nudge-after', '0.5', '--max-nudges', '2')
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        out = parse_session_out(r.stdout)
        self.assertGreaterEqual(out['nudged'], 1)
        self.assertIn('_drafts/.nudge-W1', self.sim.origin_files('_drafts/'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
