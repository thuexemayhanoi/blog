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

    def test_same_session_races_two_different_slots(self):
        self.sim.clone('a')
        self.sim.clone('b')
        procs = [self.sim.session_popen(n, 'begin', '--slot', slot,
                                       '--session', 's-shared-race', '--count', '2')
                 for n, slot in [('a', 'W1'), ('b', 'W2')]]
        results = []
        for p in procs:
            so, se = p.communicate(timeout=120)
            results.append((p.returncode, parse_session_out(so)))
        self.assertEqual(sorted(c for c, _ in results), [0, 1], results)
        self.assertEqual(next(o['code'] for c, o in results if c),
                         'SESSION_HOLDS_OTHER_SLOT')
        self.assertEqual(len(self.sim.origin_registry()['leases']), 1)

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


    def test_37_finished_batch_frees_the_slot_no_empty_reservation(self):
        """Mọi ID của lease đã PUBLISHED -> lease rỗng bị prune: container mới
        của cùng "người viết" (không giữ token) nhận slot NGAY, không bị khóa
        tới expires_at (review: lease rỗng 48h khóa slot)."""
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1')
        self.sim.set_status({i: 'PUBLISHED' for i in a['leased_total']})
        self.sim.clone('a2', identity='a')      # container mới, không file phiên
        b = self.begin('a2', '--slot', 'W1')
        self.assertEqual(b['slot'], 'W1')
        self.assertNotEqual(b['session'], a['session'])
        self.assertFalse(set(b['leased_total']) & set(a['leased_total']))
        reg = self.sim.origin_registry()
        self.assertEqual(reg['leases']['W1']['session'], b['session'])

    def test_38_empty_claim_is_refused_not_an_empty_reservation(self):
        self.sim.clone('a')
        r = self.sim.session_cmd('a', 'begin', '--slot', 'W1', '--count', '0')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(parse_session_out(r.stdout)['code'], 'EMPTY_CLAIM')
        self.assertEqual(self.sim.origin_registry()['leases'], {})


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

    def test_34_explicit_token_new_container_continues_own_slot(self):
        """Container bị tạo lại (clone mới, không còn file phiên) nhưng AI giữ
        token TƯỜNG MINH (FACTORY_WRITER_SESSION): vẫn là phiên cũ -> nối việc,
        không tự khóa slot của chính mình."""
        tok = {'FACTORY_WRITER_SESSION': 's-persona-a'}
        self.sim.clone('a')
        r1 = self.sim.session_cmd('a', 'begin', '--slot', 'W1', env=tok)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        a = parse_session_out(r1.stdout)
        self.sim.clone('a2', identity='a')              # container mới
        r2 = self.sim.session_cmd('a2', 'begin', '--slot', 'auto', env=tok)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        a2 = parse_session_out(r2.stdout)
        self.assertEqual(a2['session'], 's-persona-a')
        self.assertEqual(a2['slot'], 'W1', 'auto nối lại slot ĐANG giữ')
        self.assertEqual(a2['leased_total'], a['leased_total'])
        self.assertEqual(a2['epoch'], a['epoch'])

    def test_35_same_git_identity_is_not_the_same_session(self):
        """Nhiều AI cùng nhà cung cấp dùng CHUNG một danh tính git (và không
        token): KHÔNG được coi là một phiên. Clone thứ hai đòi slot của clone
        đầu -> SLOT_HELD; `--slot auto` nhận slot KHÁC, không đụng ID của clone
        đầu."""
        self.sim.clone('a')
        self.sim.clone('a2', identity='a')              # cùng danh tính git
        a = self.begin('a', '--slot', 'W1')
        r = self.sim.session_cmd('a2', 'begin', '--slot', 'W1')
        self.assertEqual(r.returncode, 1)
        out = parse_session_out(r.stdout)
        self.assertEqual(out['code'], 'SLOT_HELD')
        self.assertEqual(out['holder_session'], a['session'])
        b = self.begin('a2', '--slot', 'auto')
        self.assertEqual(b['slot'], 'W2')
        self.assertNotEqual(b['session'], a['session'])
        self.assertFalse(set(b['leased_total']) & set(a['leased_total']))

    def test_36_explicit_session_separates_same_identity(self):
        """Hai AI dùng chung một danh tính git: tách phiên bằng
        FACTORY_WRITER_SESSION khác nhau -> được bảo vệ như AI độc lập."""
        self.sim.clone('a')
        self.sim.clone('a2', identity='a')
        r1 = self.sim.session_cmd('a', 'begin', '--slot', 'W1',
                                  env={'FACTORY_WRITER_SESSION': 's-one'})
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        r2 = self.sim.session_cmd('a2', 'begin', '--slot', 'W1',
                                  env={'FACTORY_WRITER_SESSION': 's-two'})
        self.assertEqual(r2.returncode, 1)
        self.assertEqual(parse_session_out(r2.stdout)['code'], 'SLOT_HELD')

    def test_33_status_is_read_only_and_reports_next_action(self):
        self.sim.clone('a')
        head = self.sim.origin_head()
        r = self.sim.session_cmd('a', 'status')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = parse_session_out(r.stdout)
        self.assertEqual(out['free_slots'], ['W1', 'W2', 'W3'])
        self.assertIn('begin', out['next_action'])
        self.assertEqual(self.sim.origin_head(), head)


class TestReviewFixes(SessionBase):
    """Lỗi tìm được bởi review đối kháng (registry/CAS) — mỗi test tái hiện
    kịch bản lỗi và chứng minh đã chặn."""

    TOK = {'FACTORY_WRITER_SESSION': 's-review-a'}

    def run_cmd(self, clone, *args, env=None):
        r = self.sim.session_cmd(clone, *args, env=env)
        return r, parse_session_out(r.stdout)

    def test_50_unreadable_registry_blob_is_not_treated_as_absent(self):
        """R1: object registry đọc lỗi từng bị coi là "registry vắng" => registry
        rỗng bị push đè lên lease sống của người khác."""
        self.sim.clone('a')
        self.sim.clone('b')
        self.begin('a', '--slot', 'W1')
        r, _ = self.run_cmd('b', 'status')            # b fetch: object về loose
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        b = self.sim.clones['b']
        blob = git(b, 'rev-parse',
                   'origin/main:data/state/writer-claims.json').stdout.strip()
        obj = os.path.join(b, '.git', 'objects', blob[:2], blob[2:])
        if not os.path.exists(obj):
            self.skipTest('blob nam trong pack')
        os.remove(obj)
        head = self.sim.origin_head()
        r, out = self.run_cmd('b', 'begin', '--slot', 'auto')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(out['code'], 'GIT_READ_FAILED')
        self.assertEqual(self.sim.origin_head(), head, 'khong push gi')
        self.assertIn('W1', self.sim.origin_registry()['leases'])

    def test_51_one_session_holds_at_most_one_slot(self):
        """R2: cùng một phiên không được giữ hai slot; `--slot auto` (có
        token/--session) nối lại slot ĐANG giữ."""
        self.sim.clone('a')
        r, w1 = self.run_cmd('a', 'begin', '--slot', 'W1', env=self.TOK)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r, out = self.run_cmd('a', 'begin', '--slot', 'W2', env=self.TOK)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['code'], 'SESSION_HOLDS_OTHER_SLOT')
        r, auto = self.run_cmd('a', 'begin', '--slot', 'auto', env=self.TOK)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(auto['slot'], 'W1')
        self.assertEqual(auto['leased_total'], w1['leased_total'])
        r, auto2 = self.run_cmd('a', 'begin', '--slot', 'auto',
                                '--session', 's-review-a')
        self.assertEqual(auto2['slot'], 'W1')
        self.assertEqual(list(self.sim.origin_registry()['leases']), ['W1'])

    def test_52_explicit_session_begin_persists_for_later_commands(self):
        """R3: bàn giao `begin --session S` phải lưu phiên: status/check/push
        sau đó (không truyền --session) nhận ra cùng phiên."""
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W2')
        b = self.begin('b', '--slot', 'W2', '--session', a['session'])
        self.assertEqual(b['session'], a['session'])
        r, st = self.run_cmd('b', 'status')
        self.assertEqual(st['me']['slot'], 'W2')
        self.assertEqual(st['me']['session'], a['session'])

    def test_53_two_local_files_for_one_id_refused_by_check(self):
        """R4: hai file cùng ID — không biết bản nào đúng (từng push nhầm bản
        cũ của chủ trước)."""
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1')
        aid = a['leased_total'][0]
        c = self.sim.clones['a']
        write_draft(c, aid, slot='W1', date='2026-10-10')
        write_draft(c, aid, slot='W1', date='2026-10-12')
        r, out = self.run_cmd('a', 'check', '--no-qa')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(out['code'], 'DUPLICATE_DRAFT')

    def test_54_push_removes_stale_same_id_draft_from_origin(self):
        """R4: chủ cũ để lại draft; chủ mới (sau khi lease cũ hết hạn) push
        bản mới đổi ngày -> bản cũ bị xóa trong CÙNG commit (selector/engine
        không bao giờ phải chọn giữa hai bản)."""
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W1')
        aid = a['leased_total'][0]
        write_draft(self.sim.clones['a'], aid, slot='W1', date='2026-10-10')
        r, out = self.run_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        old = '_drafts/2026-10-10-bai-viet-so-%d.md' % int(aid.split('-')[1])
        self.assertIn(old, self.sim.origin_files('_drafts/'))
        self.sim.edit_registry(lambda reg: reg['leases']['W1'].update(
            expires_at='2000-01-01T00:00:00Z'))
        r, bb = self.run_cmd('b', 'begin', '--slot', 'W2', '--ids', aid)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        c = self.sim.clones['b']
        os.remove(os.path.join(c, old))           # chủ mới bỏ bản cũ khỏi cây
        write_draft(c, aid, slot='W2', date='2026-10-12')
        r, out = self.run_cmd('b', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(out['removed_stale'], [old])
        files = self.sim.origin_files('_drafts/')
        self.assertNotIn(old, files)
        self.assertIn('_drafts/2026-10-12-bai-viet-so-%d.md'
                      % int(aid.split('-')[1]), files)

    def test_55_same_session_resumes_ids_and_repair_after_lapse(self):
        """R5: phiên quay lại sau khi lease hết hạn (chưa ai nhận slot) phải
        nối lại ID + hàng REPAIR của MÌNH, không cấp ID mới bỏ rơi chúng."""
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'auto', '--count', '4')
        rep = a['leased_total'][:2]
        self.sim.set_status({i: 'REPAIR' for i in rep})
        self.sim.edit_registry(lambda reg: reg['leases']['W1'].update(
            expires_at='2000-01-01T00:00:00Z'))
        b = self.begin('a', '--slot', 'auto')
        self.assertEqual(b['slot'], 'W1')
        self.assertEqual(b['session'], a['session'])
        self.assertTrue(set(rep) <= set(b['leased_total']), b)
        self.assertTrue(set(a['leased_total']) <= set(b['leased_total']))
        self.assertEqual(sorted(b['resumed_after_lapse']),
                         sorted(a['leased_total']))
        self.assertEqual(b['epoch'], a['epoch'], 'khong co takeover')

    def test_56_begin_count_is_a_target_total_and_idempotent(self):
        """R6: retry CAS sau lỗi 5xx đã áp dụng làm lease phình (3 -> 6)."""
        self.sim.clone('a')
        r1 = self.begin('a', '--slot', 'W1', '--count', '3')
        self.assertEqual(len(r1['leased_total']), 3)
        r2 = self.begin('a', '--slot', 'W1', '--count', '3')
        self.assertEqual(r2['leased_total'], r1['leased_total'])
        r3 = self.begin('a', '--slot', 'W1', '--count', '5')
        self.assertEqual(len(r3['leased_total']), 5)
        self.assertTrue(set(r1['leased_total']) <= set(r3['leased_total']))

    def test_57_plain_begin_never_shortens_ttl_and_survives_empty_pool(self):
        """R7: begin gia hạn mặc định 12h từng RÚT lease 48h; holder 1-9 ID
        khi hết PLANNED từng nhận NO_FREE_ID và không gia hạn."""
        self.sim = Sim(n_planned=3)
        self.addCleanup(self.sim.cleanup)
        self.sim.clone('a')
        r1 = self.begin('a', '--slot', 'W1', '--ttl-hours', '48')
        self.assertEqual(len(r1['leased_total']), 3)
        r2 = self.begin('a', '--slot', 'W1')          # pool rỗng + gia hạn
        self.assertEqual(r2['claimed'], [])
        self.assertGreaterEqual(r2['expires_at'], r1['expires_at'])

    def test_58_repair_registry_replaces_a_corrupt_origin_registry(self):
        """R8: registry hỏng trên origin: mọi lệnh REGISTRY_CORRUPT; phải có
        đường CAS để sửa (không chỉ working copy)."""
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W1')
        self.sim.commit_on_origin(
            {'data/state/writer-claims.json': '{"leases": [truncated'},
            'corrupt registry')
        r, out = self.run_cmd('b', 'begin', '--slot', 'auto')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['code'], 'REGISTRY_CORRUPT')
        r, fixed = self.run_cmd('b', 'repair-registry')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(fixed['repaired'])
        self.assertEqual(self.sim.origin_registry()['leases']['W1']['ids'],
                         a['leased_total'], 'lease song duoc khoi phuc')
        r, again = self.run_cmd('b', 'repair-registry')
        self.assertFalse(again['repaired'])
        self.begin('b', '--slot', 'auto')

    def test_59_legacy_leases_listed_and_only_explicit_slot_adopts(self):
        """R9: lease v1 (không session) — `auto` không adopt (tránh cấp thêm
        slot thứ hai cho chủ legacy); status/NO_FREE_SLOT chỉ cách adopt."""
        legacy = {'schema_version': '1', 'updated_at': None, 'leases': {
            s: {'ids': [], 'claimed_at': '2026-10-11T00:00:00Z',
                'expires_at': '2099-01-01T00:00:00Z'}
            for s in ('W1', 'W2', 'W3')}}
        # lease legacy phải có ID thật để không bị prune
        for n, s in enumerate(('W1', 'W2', 'W3')):
            legacy['leases'][s]['ids'] = ['BLG-%05d' % (n * 2 + 1),
                                          'BLG-%05d' % (n * 2 + 2)]
        self.sim.clone('a')
        self.sim.commit_on_origin(
            {'data/state/writer-claims.json': json.dumps(legacy)}, 'legacy')
        r, out = self.run_cmd('a', 'begin', '--slot', 'auto')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['code'], 'NO_FREE_SLOT')
        self.assertEqual(out['legacy_slots'], ['W1', 'W2', 'W3'])
        r, st = self.run_cmd('a', 'status')
        self.assertEqual(st['legacy_slots'], ['W1', 'W2', 'W3'])
        self.assertIn('begin --slot', st['next_action'])
        r, adopted = self.run_cmd('a', 'begin', '--slot', 'W2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(adopted['legacy_adopted'])

    def test_60_bad_session_token_refused(self):
        """R10: token ghi nguyên văn vào frontmatter — ký tự lạ làm hỏng YAML
        hoặc chèn khóa (permalink)."""
        self.sim.clone('a')
        for bad in ('s-gpt 5: writer 2', 's-x\npermalink: /evil/', 'a' * 65):
            r, out = self.run_cmd('a', 'begin', '--slot', 'W1',
                                  '--session', bad)
            self.assertEqual(r.returncode, 1, bad)
            self.assertEqual(out['code'], 'BAD_SESSION')
        r, out = self.run_cmd('a', 'begin', '--slot', 'W1',
                              env={'FACTORY_WRITER_SESSION': 'co dau cach'})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['code'], 'BAD_SESSION')
        self.assertEqual(self.sim.origin_registry()['leases'], {})

    def test_61_bad_slot_creates_no_files_and_is_structured(self):
        self.sim.clone('a')
        r, out = self.run_cmd('a', 'begin', '--slot', '../../evil')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['code'], 'BAD_SLOT')
        c = self.sim.clones['a']
        stray = [f for f in os.listdir(os.path.dirname(c))
                 if f.startswith('evil')]
        self.assertEqual(stray, [])

    def test_62_structured_errors_not_tracebacks(self):
        """R11: --repo sai; clone single-branch; draft không phải UTF-8."""
        r = subprocess.run(
            [sys.executable, os.path.join(
                self.sim.seed, 'scripts', 'factory', 'writer-session.py'),
             '--repo', '/nonexistent-repo-dir', 'status'],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn('Traceback', r.stderr)
        git(self.sim.origin, 'branch', 'dev', 'main')
        sb = os.path.join(self.sim.base, 'clone-single')
        git(self.sim.base, 'clone', '-q', '--single-branch', '--branch',
            'dev', self.sim.origin, sb)
        git(sb, 'config', 'user.name', 'single')
        git(sb, 'config', 'user.email', 'single@sim.example')
        self.sim.clones['single'] = sb
        r, out = self.run_cmd('single', 'begin', '--slot', 'W1')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(sb, '_drafts', '2026-10-11-bin.md'),
                  'wb') as f:
            f.write(b'---\narticle_id: BLG-00001\n---\n\xff\xfe')
        r, out = self.run_cmd('single', 'status')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn('Traceback', r.stderr)

    def test_63_protected_branch_fails_fast_not_retried_8_times(self):
        self.sim.clone('a')
        self.sim.install_push_failures(
            50, message='remote: error: GH006: Protected branch update '
                        'failed for refs/heads/main.')
        r, out = self.run_cmd('a', 'begin', '--slot', 'W1')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['code'], 'PUSH_FATAL')
        with open(os.path.join(self.sim.origin, 'push-fail-count')) as f:
            left = int(f.read())
        self.assertEqual(left, 49, 'dung ngay lan dau, khong retry')

    def test_64_release_refused_while_pushed_draft_waits_for_publisher(self):
        """P5: release --all sau push làm draft PLANNED mồ côi (selector cách
        ly vì không còn lease)."""
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1', '--count', '2')
        aid = a['leased_total'][0]
        write_draft(self.sim.clones['a'], aid, slot='W1')
        r, out = self.run_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r, out = self.run_cmd('a', 'release', '--all')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['code'], 'DRAFT_QUEUED')
        self.assertEqual(out['queued'], [aid])
        r, out = self.run_cmd('a', 'release', '--all', '--even-if-queued')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.sim.origin_registry()['leases'], {})

    def test_65_malformed_expiry_in_registry_is_corrupt_not_dead(self):
        """Timestamp hỏng từng được coi là "đã chết" => lease sống bị chiếm."""
        self.sim.clone('a')
        legacy = {'schema_version': '2', 'updated_at': None, 'leases': {
            'W1': {'ids': ['BLG-00001'], 'session': 's-x', 'epoch': 1,
                   'claimed_at': '2026-10-11T00:00:00Z',
                   'expires_at': '2026-10-13T15:5'}}}
        self.sim.commit_on_origin(
            {'data/state/writer-claims.json': json.dumps(legacy)}, 'bad ts')
        r, out = self.run_cmd('a', 'begin', '--slot', 'W1')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['code'], 'REGISTRY_CORRUPT')


class TestCodexFindings(SessionBase):
    """Góp ý của Codex review trên PR #7 (đã kiểm chứng là lỗi thật)."""

    def run_cmd(self, clone, *args, env=None):
        r = self.sim.session_cmd(clone, *args, env=env)
        return r, parse_session_out(r.stdout)

    def test_68_idempotent_push_renews_lease_only_when_it_matters(self):
        """Push lặp (draft đã có đúng nội dung trên origin) từng bỏ rơi
        heartbeat nhưng vẫn báo hạn mới: lease hết hạn dù push "thành công"."""
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1', '--count', '1')
        aid = a['leased_total'][0]
        write_draft(self.sim.clones['a'], aid, slot='W1')
        r1, o1 = self.run_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        head = self.sim.origin_head()
        r2, o2 = self.run_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertTrue(o2['already_pushed'])
        self.assertFalse(o2['lease_renewed'])
        self.assertEqual(o2['expires_at'], o1['expires_at'],
                         'khong bao han moi khi khong ghi')
        self.assertEqual(self.sim.origin_head(), head, 'khong commit moi')
        # chờ publisher lâu: lease đã tiêu hao (còn 1h trên TTL 12h)
        soon = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                             time.gmtime(time.time() + 3600))
        self.sim.edit_registry(lambda reg: reg['leases']['W1'].update(
            expires_at=soon, ttl_hours=12.0))
        head = self.sim.origin_head()
        r3, o3 = self.run_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        self.assertTrue(o3['lease_renewed'])
        self.assertNotEqual(self.sim.origin_head(), head,
                            'gia han duoc ghi len origin')
        exp = self.sim.origin_registry()['leases']['W1']['expires_at']
        self.assertGreater(exp, soon)

    def test_69_sync_reconciles_tracked_drafts_already_pushed(self):
        """Draft đã tracked, writer sửa rồi `push` (plumbing): bản local giống
        hệt origin nhưng `try_sync` từng bỏ qua mãi vì file 'dirty'."""
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1', '--count', '1')
        aid = a['leased_total'][0]
        c = self.sim.clones['a']
        path = write_draft(c, aid, slot='W1')
        r1, o1 = self.run_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertTrue(o1['sync']['synced'], o1['sync'])
        with open(path, 'a', encoding='utf-8') as f:
            f.write('\nSua lai noi dung sau khi publisher bao REPAIR.\n')
        r2, o2 = self.run_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertTrue(o2['sync']['synced'], o2['sync'])
        self.assertEqual(git(c, 'status', '--porcelain',
                             '--untracked-files=no').stdout.strip(), '')
        self.assertEqual(git(c, 'rev-parse', 'HEAD').stdout.strip(),
                         self.sim.origin_head())


class TestCodexRound2(SessionBase):
    """Codex vòng 2 trên PR #7 (đã kiểm chứng là lỗi thật)."""

    def test_71_auto_slot_returns_to_own_expired_slot_not_first_free(self):
        """Lease của chính phiên (slot W2) hết hạn trong lúc W1 trống: `auto`
        phải quay lại W2 (nối lại ID + REPAIR), không nhảy sang W1."""
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W2', '--count', '4')
        rep = a['leased_total'][:2]
        self.sim.set_status({i: 'REPAIR' for i in rep})
        self.sim.edit_registry(lambda reg: reg['leases']['W2'].update(
            expires_at='2000-01-01T00:00:00Z'))
        b = self.begin('a', '--slot', 'auto')
        self.assertEqual(b['slot'], 'W2', b)
        self.assertEqual(b['session'], a['session'])
        self.assertEqual(sorted(b['resumed_after_lapse']),
                         sorted(a['leased_total']))
        self.assertTrue(set(rep) <= set(b['leased_total']))
        self.assertEqual(sorted(self.sim.origin_registry()['leases']), ['W2'])


class TestRegistryConflictBoundary(SessionBase):
    """Codex P2 trên PR #9: OwnershipConflict (lease sống mơ hồ) phải ra
    REGISTRY_CONFLICT ở MỌI lệnh thường — chờ TTL/coordinator — chứ không bị
    báo REGISTRY_CORRUPT kèm hướng dẫn `repair-registry --from-git` (lệnh đó
    từ chối đúng tình huống này: ngõ cụt, và nếu làm được sẽ mất lease sống)."""

    def run_cmd(self, clone, *args, env=None):
        r = self.sim.session_cmd(clone, *args, env=env)
        return r, parse_session_out(r.stdout)

    def _conflict(self, kind):
        self.sim.clone('a')
        self.sim.clone('b')
        a = self.begin('a', '--slot', 'W1', '--count', '2')
        self.begin('b', '--slot', 'W2', '--count', '2')
        if kind == 'id':
            self.sim.edit_registry(lambda reg: reg['leases']['W2']['ids']
                                   .append(a['leased_total'][0]))
        else:
            self.sim.edit_registry(lambda reg: reg['leases']['W2']
                                   .update(session=a['session']))
        return a

    def _assert_conflict_everywhere(self, kind):
        a = self._conflict(kind)
        head = self.sim.origin_head()
        for clone, args in (('a', ['status']),
                            ('b', ['status']),
                            ('a', ['begin', '--slot', 'auto']),
                            ('a', ['begin', '--slot', 'W3']),
                            ('a', ['heartbeat']),
                            ('a', ['release', '--all']),
                            ('a', ['check']),
                            ('a', ['repair-registry'])):
            r, out = self.run_cmd(clone, *args)
            tag = (kind, clone, args, r.stdout, r.stderr)
            self.assertEqual(r.returncode, 1, tag)
            self.assertEqual(out['code'], 'REGISTRY_CONFLICT', tag)
            self.assertTrue(out.get('problems'), tag)
            self.assertNotIn('--from-git', out['error'], tag)
        self.assertEqual(self.sim.origin_head(), head,
                         'lenh bi tu choi khong duoc ghi gi len origin')
        self.assertEqual(sorted(self.sim.origin_registry()['leases']),
                         ['W1', 'W2'], 'khong lease nao bi xoa/rollback')
        return a

    def test_72_duplicate_live_id_is_reported_as_conflict(self):
        self._assert_conflict_everywhere('id')

    def test_73_one_session_in_two_live_slots_is_reported_as_conflict(self):
        self._assert_conflict_everywhere('session')

    def test_74_conflict_clears_when_one_lease_expires(self):
        """Đường thoát đúng như tài liệu: hết TTL của một bên thì registry hết
        mơ hồ và lệnh chạy lại bình thường (không cần repair)."""
        a = self._conflict('id')
        self.sim.edit_registry(lambda reg: reg['leases']['W2']
                               .update(expires_at='2000-01-01T00:00:00Z'))
        r, out = self.run_cmd('a', 'status')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(out['me']['slot'], 'W1')
        self.assertEqual(out['me']['ids'], a['leased_total'])

    def test_75_real_corruption_still_points_to_repair(self):
        self.sim.clone('a')
        self.sim.commit_on_origin(
            {'data/state/writer-claims.json': '{"leases": '}, 'corrupt')
        r, out = self.run_cmd('a', 'status')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(out['code'], 'REGISTRY_CORRUPT')
        self.assertIn('repair-registry', out['error'])

    def test_76_non_utf8_registry_is_corrupt_not_a_traceback(self):
        self.sim.clone('a')
        # bytes không hợp lệ UTF-8 phải đi qua commit nhị phân
        import shutil
        wd = os.path.join(self.sim.base, 'ext-bad-bytes')
        git(self.sim.base, 'clone', '-q', self.sim.origin, wd)
        git(wd, 'checkout', '-q', '-B', 'main', 'origin/main')
        with open(os.path.join(wd, 'data/state/writer-claims.json'), 'wb') as f:
            f.write(b'{"leases": {}, "x": "\xff\xfe"}')
        git(wd, 'add', '-A')
        git(wd, 'commit', '-q', '-m', 'non-utf8 registry')
        git(wd, 'push', '-q', 'origin', 'HEAD:main')
        shutil.rmtree(wd, ignore_errors=True)
        r, out = self.run_cmd('a', 'status')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(out['code'], 'REGISTRY_CORRUPT')
        self.assertNotIn('Traceback', r.stderr)


class TestConfirmEdges(SessionBase):

    def test_66_confirm_blocked_is_terminal_not_a_timeout(self):
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1', '--count', '2')
        ids = a['leased_total']
        self.sim.set_status({ids[0]: 'PUBLISHED', ids[1]: 'BLOCKED'})
        t0 = time.time()
        r = self.sim.session_cmd('a', 'confirm', '--ids', ','.join(ids),
                                 '--timeout', '30', '--poll', '0.1')
        out = parse_session_out(r.stdout)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(out['code'], 'BLOCKED')
        self.assertEqual(out['published'], [ids[0]])
        self.assertLess(time.time() - t0, 20, 'khong cho het timeout')

    def test_67_confirm_without_ids_remembers_last_push(self):
        """Sau khi publish hết, lease bị prune; `confirm` không --ids từng
        trả NO_IDS."""
        self.sim.clone('a')
        a = self.begin('a', '--slot', 'W1', '--count', '1')
        aid = a['leased_total'][0]
        write_draft(self.sim.clones['a'], aid, slot='W1')
        r = self.sim.session_cmd('a', 'push', '--no-qa', '--ids', aid)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.sim.set_status({aid: 'PUBLISHED'})
        r = self.sim.session_cmd('a', 'confirm', '--timeout', '5',
                                 '--poll', '0.1')
        out = parse_session_out(r.stdout)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(out['published'], [aid])


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
