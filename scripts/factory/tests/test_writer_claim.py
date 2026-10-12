#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test MULTI-WRITER lease registry — scripts/factory/writer-claim.py.

Port hợp đồng TURBO MULTI-WRITER từ /vanchinh (scripts/writer_claim.py),
thích ứng engine /blog. Chốt đúng semantics bắt buộc:
  1. W1 claim 10 ID (matrix order, deterministic);
  2. W2 KHÔNG claim được ID của W1 (duplicate ownership refuse);
  3. W2 claim 10 ID kế tiếp;
  4. W3 claim tiếp (đủ 3 writer);
  5. writer thứ 4 bị REFUSE;
  6. release trả đúng ID của đúng writer;
  7. TTL 48h hết hạn -> reclaim được;
  8. lease trên ID không còn PLANNED (PUBLISHED) tự bị prune;
  9. lease trên ID EXISTING/BLOCKED tự bị prune;
  10. merge race deterministic (claimed_at sớm hơn thắng);
  11. xung đột cùng ID chỉ MỘT owner thắng;
  12. mọi lệnh registry KHÔNG mutate matrix (hash guard).

Bộ test KHÔNG đụng production: mọi mutation trên bản sao tạm
(FxTestCase của test_qa_modes.py).

Chạy: python3 scripts/factory/tests/test_writer_claim.py (từ repo)
"""
import calendar
import datetime
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import copy
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_qa_modes import FxTestCase, borrow_planned_row, matrix_rows, save_matrix

REG = 'data/state/writer-claims.json'
MATRIX = 'data/content-matrix.csv'


def _hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def wc(fx, *args):
    """Mỗi writer mô phỏng là một phiên độc lập; cho phép override rõ ràng."""
    args = list(args)
    if '--writer' in args and '--session' not in args:
        args += ['--session', 's-test-' + args[args.index('--writer') + 1]]
    r = subprocess.run(
        [sys.executable, 'scripts/factory/writer-claim.py'] + args,
        cwd=fx, capture_output=True, text=True)
    out = _parse_out(r.stdout)
    return r.returncode, out, r.stdout, r.stderr


def _parse_out(stdout):
    """Chấp nhận JSON một dòng (claim/release) và JSON pretty nhiều dòng
    (show/prune/merge) — parse từ dấu ngoặc mở tới ngoặc khớp cuối."""
    out = {}
    # 1) JSON một dòng sau prefix / nguyên dòng
    for ln in stdout.splitlines():
        ln = ln.strip()
        for prefix in ('BLOG_WRITER_CLAIM ', 'BLOG_WRITER_PRUNE '):
            if ln.startswith(prefix):
                try:
                    out = json.loads(ln[len(prefix):])
                except ValueError:
                    pass
        if ln.startswith('{'):
            try:
                out = json.loads(ln)
            except ValueError:
                pass
    if out:
        return out
    # 2) JSON pretty nhiều dòng: gộp từ ngoặc mở đầu tiên đến ngoặc
    # khớp cuối của stdout (merge/show/prune chỉ in MỘT tài liệu JSON)
    text = stdout.strip()
    start = text.find('{')
    if start >= 0:
        depth, end = 0, -1
        in_str = False
        esc = False
        for i, ch in enumerate(text[start:], start):
            if esc:
                esc = False
                continue
            if ch == chr(92):
                if in_str:
                    esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end > start:
            try:
                return json.loads(text[start:end + 1])
            except ValueError:
                pass
    return out


_spec = importlib.util.spec_from_file_location(
    'claim_unit', os.path.join(ROOT, 'scripts/factory/writer-claim.py'))
WC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(WC)


class SessionOwnershipTest(unittest.TestCase):
    """Pure registry fixtures: no production reads or writes."""

    def setUp(self):
        self.now = time.time()
        self.rows = [{'id': 'BLG-%05d' % n, 'status': 'PLANNED'}
                     for n in range(1, 41)]
        self.reg = WC.empty_registry()

    def claim(self, slot, session, **kw):
        return WC.apply_claim(self.reg, self.rows, slot, session,
                              now=self.now, count=2, **kw)

    def test_same_session_cannot_claim_second_slot(self):
        self.assertTrue(self.claim('W1', 's-one')['ok'])
        before = copy.deepcopy(self.reg)
        r = self.claim('W2', 's-one')
        self.assertEqual(r.get('code'), 'SESSION_HOLDS_OTHER_SLOT', r)
        self.assertEqual(self.reg, before)

    def test_legacy_adoption_cannot_give_session_second_slot(self):
        self.claim('W1', 's-one')
        self.claim('W2', 's-two')
        self.reg['leases']['W2'].pop('session')
        before = copy.deepcopy(self.reg)
        r = WC.apply_heartbeat(self.reg, self.rows, 'W2', 's-one', now=self.now)
        self.assertEqual(r.get('code'), 'SESSION_HOLDS_OTHER_SLOT', r)
        self.assertEqual(self.reg, before)

    def test_ambiguous_live_session_fails_closed(self):
        self.claim('W1', 's-one')
        self.claim('W2', 's-two')
        self.reg['leases']['W2']['session'] = 's-one'
        before = copy.deepcopy(self.reg)
        for operation in (
                lambda: self.claim('W3', 's-three'),
                lambda: WC.apply_heartbeat(self.reg, self.rows, 'W1', 's-one', now=self.now),
                lambda: WC.apply_release(self.reg, self.rows, 'W1', 's-one', end=True, now=self.now)):
            self.assertEqual(operation().get('code'), 'REGISTRY_CONFLICT')
            self.assertEqual(self.reg, before)
        with self.assertRaises(WC.OwnershipConflict):
            WC.parse_registry(json.dumps(self.reg))

    def test_ambiguous_live_id_fails_closed(self):
        self.claim('W1', 's-one')
        self.claim('W2', 's-two')
        self.reg['leases']['W2']['ids'].append('BLG-00001')
        before = copy.deepcopy(self.reg)
        r = self.claim('W3', 's-three')
        self.assertEqual(r.get('code'), 'REGISTRY_CONFLICT', r)
        self.assertEqual(self.reg, before)

    def test_release_then_switch_slot(self):
        self.claim('W1', 's-one')
        self.assertTrue(WC.apply_release(self.reg, self.rows, 'W1', 's-one',
                                        end=True, now=self.now)['ok'])
        self.assertTrue(self.claim('W2', 's-one')['ok'])
        self.assertEqual(WC.check_invariants(self.reg, self.rows, self.now), [])

    def test_expired_slot_does_not_reserve_session(self):
        self.claim('W1', 's-one')
        self.reg['leases']['W1']['expires_at'] = WC._iso(self.now - 10)
        self.assertTrue(self.claim('W2', 's-one')['ok'])
        self.assertNotIn('W1', self.reg['leases'])

    def test_merge_cannot_replace_live_session_with_earlier_timestamp(self):
        self.claim('W1', 's-one')
        other = WC.empty_registry()
        other['leases']['W1'] = dict(self.reg['leases']['W1'],
                                    session='s-two', claimed_at='2000-01-01T00:00:00Z')
        before = copy.deepcopy(self.reg)
        with self.assertRaises(WC.RegistryCorrupt):
            WC.merge_registries(self.reg, other, self.rows)
        self.assertEqual(self.reg, before)

    def test_merge_cannot_put_same_session_in_two_slots(self):
        self.claim('W1', 's-one')
        other = WC.empty_registry()
        other['leases']['W2'] = dict(self.reg['leases']['W1'], ids=['BLG-00003'])
        before = copy.deepcopy(self.reg)
        with self.assertRaises(WC.RegistryCorrupt):
            WC.merge_registries(self.reg, other, self.rows)
        self.assertEqual(self.reg, before)

    # ---- Codex P2 (PR #9): lease v1 -> v2 qua merge, và REGISTRY_CONFLICT ----

    def test_merge_adopts_legacy_local_lease_from_incoming_session(self):
        """Local còn lease v1 (chưa session), remote là CHÍNH lease đó sau lần
        nhận hợp lệ đầu tiên: không phải hai chủ tranh nhau — giữ session đã nhận."""
        self.claim('W1', 's-one')
        other = copy.deepcopy(self.reg)
        self.reg['leases']['W1'].pop('session')
        out = WC.merge_registries(self.reg, other, self.rows)
        self.assertEqual(self.reg['leases']['W1']['session'], 's-one')
        self.assertEqual(self.reg['leases']['W1']['ids'],
                         other['leases']['W1']['ids'])
        self.assertEqual(out['lost_to_other_writer'], [])
        self.assertEqual(WC.check_invariants(self.reg, self.rows, self.now), [])

    def test_merge_never_downgrades_local_session_to_legacy(self):
        """Remote là bản cũ (v1) của lease local đã nhận: giữ session local."""
        self.claim('W1', 's-one')
        local = copy.deepcopy(self.reg['leases']['W1'])
        other = copy.deepcopy(self.reg)
        other['leases']['W1'].pop('session')
        WC.merge_registries(self.reg, other, self.rows)
        self.assertEqual(self.reg['leases']['W1']['session'], 's-one')
        self.assertEqual(self.reg['leases']['W1']['ids'], local['ids'])

    def test_merge_two_legacy_leases_of_one_slot_merge(self):
        self.claim('W1', 's-one')
        self.reg['leases']['W1'].pop('session')
        other = copy.deepcopy(self.reg)
        WC.merge_registries(self.reg, other, self.rows)
        self.assertNotIn('session', self.reg['leases']['W1'])

    def test_merge_unequal_present_sessions_is_an_ownership_conflict(self):
        """Chỉ HAI session cùng có mặt mà khác nhau mới là tranh chủ — và đó là
        REGISTRY_CONFLICT (chờ TTL/coordinator), không phải "registry hỏng"."""
        self.claim('W1', 's-one')
        other = WC.empty_registry()
        other['leases']['W1'] = dict(self.reg['leases']['W1'],
                                    session='s-two')
        before = copy.deepcopy(self.reg)
        with self.assertRaises(WC.OwnershipConflict) as cm:
            WC.merge_registries(self.reg, other, self.rows)
        self.assertTrue(cm.exception.problems, cm.exception)
        self.assertEqual(self.reg, before)

    def test_merge_legacy_adoption_cannot_give_session_a_second_slot(self):
        self.claim('W1', 's-one')
        self.claim('W2', 's-two')
        self.reg['leases']['W2'].pop('session')
        other = WC.empty_registry()
        other['leases']['W2'] = dict(self.reg['leases']['W2'],
                                    session='s-one')
        before = copy.deepcopy(self.reg)
        with self.assertRaises(WC.OwnershipConflict):
            WC.merge_registries(self.reg, other, self.rows)
        self.assertEqual(self.reg, before)

    def test_merge_union_keeps_every_local_id_first_up_to_max_lease(self):
        """ID local đã được CAS/commit không bị đá ra bởi ID incoming nhỏ hơn."""
        local_ids = ['BLG-%05d' % n for n in range(10, 19)]
        self.assertTrue(WC.apply_claim(self.reg, self.rows, 'W1', 's-one',
                                       ids=local_ids, now=self.now)['ok'])
        other = copy.deepcopy(self.reg)
        other['leases']['W1']['ids'] = ['BLG-00001', 'BLG-00002'] + local_ids[:2]
        WC.merge_registries(self.reg, other, self.rows)
        got = self.reg['leases']['W1']['ids']
        self.assertLessEqual(len(got), WC.MAX_LEASE)
        self.assertTrue(set(local_ids) <= set(got), got)

    def test_ownership_conflict_exposes_the_problem_list(self):
        self.claim('W1', 's-one')
        self.claim('W2', 's-two')
        self.reg['leases']['W2']['ids'].append(
            self.reg['leases']['W1']['ids'][0])
        with self.assertRaises(WC.OwnershipConflict) as cm:
            WC.parse_registry(json.dumps(self.reg))
        self.assertTrue(any('giu boi' in p for p in cm.exception.problems),
                        cm.exception.problems)

    # ---- Codex P2 round 2 (PR #9) ----

    def test_merge_legacy_adoption_requires_lineage(self):
        """Lease v1 local (ID A) + lease CÓ session ở incoming (ID B, rời A) KHÔNG
        chứng minh được là cùng một chủ (hai working copy tự claim độc lập):
        fail-closed, không gộp A+B dưới session của incoming."""
        self.claim('W1', 's-one')
        local_ids = list(self.reg['leases']['W1']['ids'])
        self.reg['leases']['W1'].pop('session')
        other = WC.empty_registry()
        other['leases']['W1'] = dict(self.reg['leases']['W1'], session='s-two',
                                    ids=['BLG-00031', 'BLG-00032'])
        before = copy.deepcopy(self.reg)
        with self.assertRaises(WC.OwnershipConflict) as cm:
            WC.merge_registries(self.reg, other, self.rows)
        self.assertTrue(cm.exception.problems)
        self.assertEqual(self.reg, before)
        self.assertEqual(self.reg['leases']['W1']['ids'], local_ids)

    def test_merge_session_local_vs_legacy_incoming_requires_lineage_too(self):
        self.claim('W1', 's-one')
        other = WC.empty_registry()
        other['leases']['W1'] = {'ids': ['BLG-00031', 'BLG-00032'],
                                 'claimed_at': WC._iso(self.now),
                                 'expires_at': WC._iso(self.now + 3600)}
        before = copy.deepcopy(self.reg)
        with self.assertRaises(WC.OwnershipConflict):
            WC.merge_registries(self.reg, other, self.rows)
        self.assertEqual(self.reg, before)

    def test_merge_adoption_that_released_some_ids_still_has_lineage(self):
        """Phiên đã nhận có thể đã release bớt ID: còn GIỮ ít nhất một ID của
        lease v1 local là đủ chứng minh dòng dõi."""
        self.claim('W1', 's-one')
        ids = list(self.reg['leases']['W1']['ids'])
        other = copy.deepcopy(self.reg)
        other['leases']['W1']['ids'] = ids[:1]
        self.reg['leases']['W1'].pop('session')
        WC.merge_registries(self.reg, other, self.rows)
        self.assertEqual(self.reg['leases']['W1']['session'], 's-one')
        self.assertEqual(sorted(self.reg['leases']['W1']['ids']), sorted(ids))

    def test_malformed_live_session_is_corruption_not_a_conflict(self):
        """Token session hỏng KHÔNG phải hai chủ tranh nhau: là REGISTRY_CORRUPT
        để `repair-registry --from-git` còn dùng được."""
        self.claim('W1', 's-one')
        self.reg['leases']['W1']['session'] = 'bad session!'
        with self.assertRaises(WC.RegistryCorrupt) as cm:
            WC.parse_registry(json.dumps(self.reg))
        self.assertNotIsInstance(cm.exception, WC.OwnershipConflict)

    def test_expired_malformed_session_is_ignored(self):
        self.claim('W1', 's-one')
        self.reg['leases']['W1']['session'] = 'bad session!'
        self.reg['leases']['W1']['expires_at'] = WC._iso(self.now - 10)
        WC.parse_registry(json.dumps(self.reg))

    def test_empty_lease_does_not_count_for_session_conflict(self):
        """Lease rỗng không giữ việc gì (sẽ bị prune): không được làm cả registry
        REGISTRY_CONFLICT chỉ vì cùng session với một lease còn việc."""
        self.claim('W1', 's-one')
        self.claim('W2', 's-two')
        self.reg['leases']['W2']['session'] = 's-one'
        self.reg['leases']['W1']['ids'] = []
        WC.parse_registry(json.dumps(self.reg))
        self.assertEqual(WC.live_ownership_problems(self.reg, self.now), [])
        self.assertEqual([p for p in WC.check_invariants(self.reg, self.rows, self.now)
                          if 'phien' in p], [])
        report = WC.prune_registry(self.reg, self.rows, self.now)
        self.assertNotIn('W1', self.reg['leases'])
        self.assertEqual(self.reg['leases']['W2']['session'], 's-one')

    def test_same_lease_duplicate_id_is_one_owner_not_a_conflict(self):
        """Codex P2 (vòng 3): `ids: [A, A]` trong MỘT lease chỉ có MỘT chủ — không
        phải tranh chấp. REGISTRY_CONFLICT dành cho >= 2 slot KHÁC NHAU; ID lặp là
        hỏng cấu trúc nhẹ: check_invariants vẫn báo, prune tự dọn (không đổi chủ)."""
        self.claim('W1', 's-one')
        lease = self.reg['leases']['W1']
        first = lease['ids'][0]
        lease['ids'].append(first)
        self.assertEqual(WC.live_conflicts(self.reg, self.now), {})
        self.assertEqual(WC.live_ownership_problems(self.reg, self.now), [])
        WC.parse_registry(json.dumps(self.reg))     # KHÔNG raise OwnershipConflict
        problems = WC.check_invariants(self.reg, self.rows, self.now)
        self.assertTrue(any('ID lap' in p for p in problems), problems)
        self.assertFalse(any('hai lease song' in p for p in problems), problems)
        report = WC.prune_registry(self.reg, self.rows, self.now)
        self.assertTrue(WC._changed(report))
        ids = self.reg['leases']['W1']['ids']
        self.assertEqual(ids, list(dict.fromkeys(ids)))
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[0], first)                 # thứ tự lần xuất hiện đầu giữ nguyên
        self.assertEqual(self.reg['leases']['W1']['session'], 's-one')
        self.assertEqual(WC.check_invariants(self.reg, self.rows, self.now), [])

    def test_conflict_lists_each_slot_once_even_with_ids_repeated_inside_a_lease(self):
        self.claim('W1', 's-one')
        self.claim('W2', 's-two')
        shared = self.reg['leases']['W1']['ids'][0]
        self.reg['leases']['W1']['ids'].append(shared)      # lặp trong chính W1
        self.reg['leases']['W2']['ids'].append(shared)      # và W2 giữ cùng ID: tranh chấp thật
        self.assertEqual(WC.live_conflicts(self.reg, self.now), {shared: ['W1', 'W2']})
        with self.assertRaises(WC.OwnershipConflict):
            WC.parse_registry(json.dumps(self.reg))

    def test_merge_never_writes_an_id_twice_into_one_lease(self):
        self.claim('W1', 's-one')
        other = WC.empty_registry()
        a, b = self.rows[20]['id'], self.rows[21]['id']
        other['leases']['W2'] = {'ids': [a, a, b], 'session': 's-two', 'epoch': 1,
                                 'claimed_at': WC._iso(self.now),
                                 'expires_at': WC._iso(self.now + 3600)}
        WC.merge_registries(self.reg, other, self.rows)
        ids = self.reg['leases']['W2']['ids']
        self.assertEqual(sorted(ids), sorted({a, b}))
        self.assertEqual(WC.check_invariants(self.reg, self.rows, self.now), [])

    # ---- review độc lập (fuzz) trên c2ef32f: registry sửa tay / merge thô ----

    def _three_live(self):
        reg = WC.empty_registry()
        for slot, sess in (('W1', 's-one'), ('W2', 's-two'), ('W3', 's-three')):
            res = WC.apply_claim(reg, self.rows, slot, sess, now=self.now, count=2)
            self.assertTrue(res['ok'], res)
        return reg

    def test_slot_key_outside_w1_w3_is_corruption_never_an_eviction(self):
        """Parse từng nhận khóa lạ ('W4', 'w1', 'W1 ', 'W1\\n'): một heartbeat bình thường
        rồi cắt MAX_WRITERS và ĐÁ lease SỐNG hợp lệ claim mới nhất (W3), giữ lease 'ma'.
        Khóa slot lạ phải là REGISTRY_CORRUPT (repair từ git còn dùng được)."""
        for w in ('W4', 'w1', 'W1 ', 'W1\n', 'W0', ''):
            with self.subTest(slot=repr(w)):
                reg = self._three_live()
                reg['leases'][w] = dict(reg['leases']['W1'], session='s-four',
                                        ids=[self.rows[30]['id']])
                with self.assertRaises(WC.RegistryCorrupt) as cm:
                    WC.parse_registry(json.dumps(reg))
                self.assertNotIsInstance(cm.exception, WC.OwnershipConflict)

    def test_expired_lease_under_an_unknown_slot_key_is_just_pruned(self):
        """Lease HẾT HẠN với khóa lạ vô hại (prune xóa nó trước bước cắt
        MAX_WRITERS) nên được bỏ qua như mọi lease hết hạn — repair-agent
        `prune-writer-claims` dựa vào đó."""
        reg = self._three_live()
        reg['leases']['W9'] = dict(reg['leases']['W1'], session='s-old',
                                   ids=[self.rows[30]['id']],
                                   expires_at=WC._iso(self.now - 10))
        parsed = WC.parse_registry(json.dumps(reg))
        WC.prune_registry(parsed, self.rows, self.now)
        self.assertEqual(sorted(parsed['leases']), ['W1', 'W2', 'W3'])

    def test_merge_refuses_a_slot_outside_w1_w3_and_keeps_every_local_lease(self):
        local = self._three_live()
        other = WC.empty_registry()
        other['leases']['W4'] = {'ids': [self.rows[30]['id']], 'session': 's-four',
                                 'epoch': 1, 'claimed_at': WC._iso(self.now - 4000),
                                 'expires_at': WC._iso(self.now + 3600)}
        before = copy.deepcopy(local)
        with self.assertRaises(WC.RegistryCorrupt):
            WC.merge_registries(local, other, self.rows)
        self.assertEqual(local, before, 'W3 (live) không được bị đá khỏi registry')
        other['leases']['W4']['expires_at'] = WC._iso(self.now - 10)   # hết hạn: bỏ qua
        WC.merge_registries(local, other, self.rows)
        self.assertEqual(sorted(local['leases']), ['W1', 'W2', 'W3'])

    def test_live_lease_over_max_lease_is_corruption_but_an_expired_one_is_ignored(self):
        reg = self._three_live()
        # ID KHÔNG trùng W2/W3 (nếu trùng thì parse raise OwnershipConflict vì lý do khác)
        reg['leases']['W1']['ids'] = [r['id'] for r in
                                      self.rows[10:10 + WC.MAX_LEASE + 1]]
        with self.assertRaises(WC.RegistryCorrupt) as cm:
            WC.parse_registry(json.dumps(reg))
        self.assertNotIsInstance(cm.exception, WC.OwnershipConflict)
        reg['leases']['W1']['expires_at'] = WC._iso(self.now - 10)
        WC.parse_registry(json.dumps(reg))          # hết hạn: bị prune, không chặn

    def test_live_lease_cap_counts_distinct_ids_so_prune_can_normalize_a_duplicate(self):
        """Codex P2 (vòng 5): 10 ID khác nhau + một ID lặp là MỘT chủ giữ 10 ID, không
        vượt MAX_LEASE: parse phải nhận để prune dọn bản lặp (self_duplicates) thay vì
        bắt khôi phục từ git history."""
        reg = self._three_live()
        ids = [r['id'] for r in self.rows[10:10 + WC.MAX_LEASE]]
        reg['leases']['W1']['ids'] = ids + [ids[0]]
        parsed = WC.parse_registry(json.dumps(reg))
        report = WC.prune_registry(parsed, self.rows, self.now)
        self.assertEqual(parsed['leases']['W1']['ids'], ids)
        self.assertEqual(report['self_duplicates'], {'W1': [ids[0]]})

    def test_ownership_conflict_wins_over_repairable_corruption(self):
        """Codex P2 (vòng 6): registry vừa tranh chấp chủ SỐNG vừa có lỗi cấu trúc sửa
        được phải là REGISTRY_CONFLICT (chờ TTL/coordinator, KHÔNG rollback); nếu báo
        REGISTRY_CORRUPT thì repair-registry khôi phục bản cũ và âm thầm mất lease
        đang tranh chấp."""
        ids = [r['id'] for r in self.rows[10:10 + WC.MAX_LEASE + 1]]
        cases = {
            'lease vuot MAX_LEASE + ID dung chung':
                lambda reg: (reg['leases']['W1'].update(ids=ids),
                             reg['leases']['W2'].update(ids=[ids[0]])),
            'epoch sai kieu + ID dung chung':
                lambda reg: (reg['leases']['W1'].update(epoch='abc'),
                             reg['leases']['W2']['ids'].append(
                                 reg['leases']['W1']['ids'][0])),
            'ttl_hours sai kieu + session dung chung':
                lambda reg: (reg['leases']['W1'].update(ttl_hours='abc'),
                             reg['leases']['W2'].update(
                                 session=reg['leases']['W1']['session'])),
            'khoa slot la + ID dung chung':
                lambda reg: reg['leases'].update(
                    W4=dict(reg['leases']['W1'], session='s-four')),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                reg = self._three_live()
                mutate(reg)
                with self.assertRaises(WC.OwnershipConflict):
                    WC.parse_registry(json.dumps(reg))

    def test_classification_matrix_conflict_beats_every_repairable_error(self):
        """Codex P2 (vòng 6-7): MỌI cặp (tranh chấp chủ SỐNG chứng minh được) x (lỗi cấu
        trúc sửa được) là REGISTRY_CONFLICT. Phân tích tranh chấp chạy trên dữ liệu NHẬN
        DIỆN ĐƯỢC nên một thành viên hỏng (ID sai dạng, token session hỏng...) không che
        được nó, và repair không bao giờ khôi phục bản cũ làm mất lease đang tranh chấp."""
        first = lambda reg: reg['leases']['W1']['ids'][0]
        conflicts = {
            'ID dung chung': lambda reg: reg['leases']['W2']['ids'].append(first(reg)),
            'session dung chung': lambda reg: reg['leases']['W2'].update(
                session=reg['leases']['W1']['session']),
        }
        anomalies = {
            'ID anh em sai dinh dang': lambda reg: reg['leases']['W1']['ids'].append('bad-id'),
            'ID anh em khong phai chuoi': lambda reg: reg['leases']['W1']['ids'].append(['x']),
            'epoch sai kieu': lambda reg: reg['leases']['W1'].update(epoch='abc'),
            'ttl khong huu han': lambda reg: reg['leases']['W1'].update(ttl_hours=10 ** 1000),
            'label sai kieu': lambda reg: reg['leases']['W2'].update(label=5),
            'vuot MAX_LEASE': lambda reg: reg['leases']['W3']['ids'].extend(
                r['id'] for r in self.rows[10:10 + WC.MAX_LEASE]),
            'khoa slot la': lambda reg: reg['leases'].update(
                W4=dict(reg['leases']['W3'], session='s-four', ids=[self.rows[35]['id']])),
            'token session hong o lease thu ba': lambda reg: reg['leases']['W3'].update(
                session='bad session!'),
            'session khong phai chuoi o lease thu ba': lambda reg: reg['leases']['W3'].update(
                session=5),
            'lease khac khong phai object': lambda reg: reg['leases'].update(W4=5),
            'han (expires_at) cua lease khac khong doc duoc': lambda reg: reg['leases']['W3'].update(
                expires_at='garbage'),
            'han (expires_at) cua lease khac sai kieu': lambda reg: reg['leases']['W3'].update(
                expires_at=[1]),
        }
        for c_label, conflict in conflicts.items():
            for a_label, anomaly in anomalies.items():
                with self.subTest(conflict=c_label, anomaly=a_label):
                    reg = self._three_live()
                    conflict(reg)
                    anomaly(reg)
                    with self.assertRaises(WC.OwnershipConflict):
                        WC.parse_registry(json.dumps(reg))

    def test_shape_errors_alone_are_still_corruption(self):
        """Lease sai hình dạng / hạn không đọc được, KHÔNG có tranh chấp: vẫn REGISTRY_CORRUPT."""
        for label, mutate in {
                'lease khong phai object': lambda reg: reg['leases'].update(W4=5),
                'expires_at khong doc duoc': lambda reg: reg['leases']['W3'].update(
                    expires_at='garbage'),
                'expires_at sai kieu': lambda reg: reg['leases']['W3'].update(expires_at=[1])}.items():
            with self.subTest(label):
                reg = self._three_live()
                mutate(reg)
                with self.assertRaises(WC.RegistryCorrupt) as cm:
                    WC.parse_registry(json.dumps(reg))
                self.assertNotIsInstance(cm.exception, WC.OwnershipConflict)

    def test_shared_malformed_session_is_corruption_not_a_conflict(self):
        """Codex P2 (vòng 7): hai lease sống cùng một token HỎNG không có chủ hợp lệ nào
        tranh nhau: REGISTRY_CORRUPT (repair --from-git dùng được); một tranh chấp ID hợp
        lệ độc lập vẫn thắng."""
        reg = self._three_live()
        for w in ('W1', 'W2'):
            reg['leases'][w]['session'] = 'bad session!'
        with self.assertRaises(WC.RegistryCorrupt) as cm:
            WC.parse_registry(json.dumps(reg))
        self.assertNotIsInstance(cm.exception, WC.OwnershipConflict)
        reg['leases']['W3']['ids'].append(reg['leases']['W1']['ids'][0])
        with self.assertRaises(WC.OwnershipConflict):
            WC.parse_registry(json.dumps(reg))

    def test_expired_lease_members_are_sanitized_not_validated(self):
        """Codex P2 (vòng 7): lease HẾT HẠN là vật bỏ: trường hỏng trong đó không được
        chặn cả registry (ép khôi phục từ git history có thể làm mất lease SỐNG mới hơn).
        Parse chuẩn hóa kiểu rồi prune xóa; claim/takeover slot đó không crash."""
        reg = self._three_live()
        dead = reg['leases']['W1']
        dead.update(expires_at=WC._iso(self.now - 10), epoch='abc', ttl_hours='abc',
                    label=5, claimed_at=5, heartbeat_at=[], session=5)
        dead['ids'] = dead['ids'] + ['bad-id', ['x']]
        parsed = WC.parse_registry(json.dumps(reg))
        WC.check_invariants(parsed, self.rows, self.now)      # không crash
        res = WC.apply_claim(parsed, self.rows, 'W1', 's-new', count=1, now=self.now)
        self.assertTrue(res['ok'], res)
        self.assertEqual(parsed['leases']['W1']['session'], 's-new')
        self.assertEqual(sorted(parsed['leases']), ['W1', 'W2', 'W3'])

    def test_oversized_integer_ttl_is_corruption_not_an_overflow(self):
        """Codex P2 (vòng 5): số nguyên JSON quá lớn cho double làm math.isfinite raise
        OverflowError (traceback, repair --from-git cũng chết) thay vì RegistryCorrupt."""
        for bad in (10 ** 1000, -10 ** 1000):
            with self.subTest(ttl_hours_digits=len(str(abs(bad)))):
                reg = self._three_live()
                reg['leases']['W1']['ttl_hours'] = bad
                with self.assertRaises(WC.RegistryCorrupt):
                    WC.parse_registry(json.dumps(reg))
        # số nguyên lớn nhưng HỮU HẠN (vừa double): hợp lệ, heartbeat kẹp về MAX_TTL
        reg = self._three_live()
        reg['leases']['W1']['ttl_hours'] = 10 ** 300
        parsed = WC.parse_registry(json.dumps(reg))
        res = WC.apply_heartbeat(parsed, self.rows, 'W1', 's-one', now=self.now)
        self.assertTrue(res['ok'], res)
        self.assertEqual(parsed['leases']['W1']['ttl_hours'], WC.MAX_TTL_HOURS)

    def test_odd_typed_lease_fields_are_corruption_not_a_traceback(self):
        for key, bad in (('epoch', 'abc'), ('epoch', [1]), ('epoch', True),
                         ('epoch', 1.5), ('ttl_hours', 'abc'), ('ttl_hours', []),
                         ('ttl_hours', True), ('ttl_hours', float('nan')),
                         ('ttl_hours', float('inf')), ('label', 5),
                         ('label', {}), ('claimed_at', 5), ('heartbeat_at', [])):
            with self.subTest(field=key, value=repr(bad)):
                reg = self._three_live()
                reg['leases']['W1'][key] = bad
                with self.assertRaises(WC.RegistryCorrupt):
                    WC.parse_registry(json.dumps(reg))

    def test_lease_without_an_ids_key_is_an_empty_lease_not_a_keyerror(self):
        reg = self._three_live()
        reg['leases']['W1'].pop('ids')
        parsed = WC.parse_registry(json.dumps(reg))
        self.assertEqual(parsed['leases']['W1']['ids'], [])

    def test_slot_session_and_id_tokens_reject_a_trailing_newline(self):
        """'$' khớp trước '\\n' cuối: 'W1\\n' lọt qua thành slot thứ hai, 's-a\\n' thành
        phiên không bao giờ khớp token trong draft (chủ lease bị kẹt)."""
        self.assertIsNone(WC.SLOT_RE.match('W1\n'))
        self.assertFalse(WC.valid_session('s-a\n'))
        self.assertIsNone(WC.ID_RE.match('BLG-00001\n'))
        reg = WC.empty_registry()
        res = WC.apply_claim(reg, self.rows, 'W1\n', 's-a', now=self.now, count=1)
        self.assertEqual(res.get('code'), 'BAD_SLOT', res)
        res = WC.apply_claim(reg, self.rows, 'W1', 's-a\n', now=self.now, count=1)
        self.assertEqual(res.get('code'), 'BAD_SESSION', res)
        self.assertEqual(reg['leases'], {})
        reg = self._three_live()
        reg['leases']['W1']['ids'][0] = 'BLG-00001\n'
        with self.assertRaises(WC.RegistryCorrupt):
            WC.parse_registry(json.dumps(reg))

    def test_prune_is_linear_in_the_number_of_ids(self):
        """`a not in set(keep)` dựng lại set cho TỪNG phần tử: 10k ID ~4s, 20k ~26s."""
        n = 20000
        rows = [{'id': 'BLG-%05d' % i, 'status': 'PLANNED'} for i in range(1, n + 1)]
        reg = WC.empty_registry()
        reg['leases']['W1'] = {'ids': [r['id'] for r in rows], 'session': 's-one',
                               'epoch': 1, 'claimed_at': WC._iso(self.now),
                               'expires_at': WC._iso(self.now + 3600)}
        t0 = time.time()
        WC.prune_registry(reg, rows, self.now)
        self.assertLess(time.time() - t0, 3.0, 'prune phải tuyến tính theo số ID')

    def _legacy_w2_with_session_on_w1(self):
        """s-one giữ W1; W2 là lease legacy (không session) có >= 2 ID."""
        self.claim('W1', 's-one')
        self.claim('W2', 's-two')
        self.reg['leases']['W2'].pop('session')
        ids = list(self.reg['leases']['W2']['ids'])
        self.assertGreaterEqual(len(ids), 2)
        return ids

    def test_release_cannot_adopt_a_legacy_lease_for_a_session_with_another_slot(self):
        """Codex P2 (vòng 3): release một phần lease legacy từng GẮN session của
        người gọi vào slot đó (nhận lease) mà không kiểm 'một phiên một slot' ->
        s-one giữ hai slot sống, mọi lệnh sau đó REGISTRY_CONFLICT."""
        ids = self._legacy_w2_with_session_on_w1()
        before = copy.deepcopy(self.reg)
        res = WC.apply_release(self.reg, self.rows, 'W2', 's-one',
                               ids=[ids[0]], now=self.now)
        self.assertFalse(res['ok'], res)
        self.assertEqual(res['code'], 'SESSION_HOLDS_OTHER_SLOT')
        self.assertEqual(res['holder_slots'], ['W1'])
        self.assertEqual(self.reg, before, 'lệnh bị từ chối không được đổi registry')
        self.assertEqual(WC.live_ownership_problems(self.reg, self.now), [])

    def test_release_still_adopts_a_legacy_lease_for_a_session_without_a_slot(self):
        ids = self._legacy_w2_with_session_on_w1()
        res = WC.apply_release(self.reg, self.rows, 'W2', 's-new',
                               ids=[ids[0]], now=self.now)
        self.assertTrue(res['ok'], res)
        self.assertEqual(self.reg['leases']['W2']['session'], 's-new')
        self.assertEqual(self.reg['leases']['W2']['ids'], ids[1:])
        self.assertEqual(WC.live_ownership_problems(self.reg, self.now), [])

    def test_release_of_a_whole_legacy_lease_only_reduces_holdings(self):
        """Trả HẾT lease legacy không gắn session mới cho ai: vẫn được phép (chỉ
        giảm phần đang giữ) và không đụng slot khác của phiên."""
        ids = self._legacy_w2_with_session_on_w1()
        w1 = copy.deepcopy(self.reg['leases']['W1'])
        res = WC.apply_release(self.reg, self.rows, 'W2', 's-one',
                               ids=ids, now=self.now)
        self.assertTrue(res['ok'], res)
        self.assertTrue(res['ended'])
        self.assertNotIn('W2', self.reg['leases'])
        self.assertEqual(self.reg['leases']['W1'], w1)


class WriterClaimTest(FxTestCase):
    """Mọi test chạy trên bản sao repo riêng (self.fx)."""

    def planned(self, n):
        """Đảm bảo fixture có >= n hàng PLANNED (top-up hermetic)."""
        borrow_planned_row(self.fx, count=n)
        return [r['id'] for r in matrix_rows(self.fx)
                if r['status'] == 'PLANNED']

    def reg(self):
        p = os.path.join(self.fx, REG)
        if not os.path.exists(p):
            return {'leases': {}}
        with open(p, encoding='utf-8') as f:
            return json.load(f)

    def matrix_guard(self):
        return _hash(os.path.join(self.fx, MATRIX))

    def test_repair_never_rolls_back_ambiguous_live_ownership(self):
        self.planned(4)
        wc(self.fx, 'claim', '--writer', 'W1', '--count', '2')
        reg = self.reg()
        reg['leases']['W2'] = dict(reg['leases']['W1'], ids=['BLG-99999'])
        path = os.path.join(self.fx, REG)
        with open(path, 'w') as f:
            json.dump(reg, f)
        before = _hash(path)
        rc, out, _, _ = wc(self.fx, 'repair-registry', '--from-git')
        self.assertEqual(rc, 1, out)
        self.assertEqual(out['code'], 'REGISTRY_CONFLICT')
        self.assertEqual(_hash(path), before)

    def _conflicted_registry(self, kind='id'):
        """W1 và W2 (hai phiên) hợp lệ, rồi ép tranh chấp chủ: một ID bị hai
        lease sống giữ ('id') hoặc một phiên giữ hai slot sống ('session')."""
        self.planned(8)
        path = os.path.join(self.fx, REG)
        if os.path.exists(path):
            os.remove(path)
        wc(self.fx, 'claim', '--writer', 'W1', '--count', '2')
        wc(self.fx, 'claim', '--writer', 'W2', '--count', '2')
        reg = self.reg()
        if kind == 'id':
            reg['leases']['W2']['ids'].append(reg['leases']['W1']['ids'][0])
        else:
            reg['leases']['W2']['session'] = reg['leases']['W1']['session']
        with open(path, 'w') as f:
            json.dump(reg, f)
        return path

    def test_registry_conflict_is_reported_as_conflict_by_every_command(self):
        """Codex P2: OwnershipConflict là con của RegistryCorrupt nhưng KHÔNG
        được báo REGISTRY_CORRUPT kèm hướng dẫn khôi phục từ git (repair-registry
        từ chối đúng tình huống đó): mọi lệnh thường phải báo REGISTRY_CONFLICT
        (chờ TTL/coordinator), có danh sách problems, không ghi gì."""
        for kind in ('id', 'session'):
            with self.subTest(kind=kind):
                path = self._conflicted_registry(kind)
                before = _hash(path)
                incoming = os.path.join(self.fx, 'incoming-registry.json')
                with open(incoming, 'w') as f:
                    json.dump({'schema_version': '2', 'leases': {}}, f)
                for args in (['claim', '--writer', 'W3', '--count', '2'],
                             ['heartbeat', '--writer', 'W1'],
                             ['release', '--writer', 'W1', '--all'],
                             ['show'], ['status'], ['prune'],
                             ['check-registry'],
                             ['merge', '--file', incoming],
                             ['repair-registry']):
                    rc, out, so, se = wc(self.fx, *args)
                    self.assertEqual(rc, 1, (kind, args, so, se))
                    self.assertEqual(out.get('code'), 'REGISTRY_CONFLICT',
                                     (kind, args, so, se))
                    self.assertTrue(out.get('problems'), (kind, args, out))
                    self.assertNotIn('--from-git', so, (kind, args, so))
                    self.assertEqual(_hash(path), before,
                                     'lenh %s da ghi registry' % args)

    def test_corrupt_registry_still_points_to_repair(self):
        """Hỏng thật (JSON/cấu trúc) vẫn là REGISTRY_CORRUPT + repair-registry."""
        self.planned(2)
        path = os.path.join(self.fx, REG)
        with open(path, 'w') as f:
            f.write('{"leases": ')
        rc, out, so, se = wc(self.fx, 'check-registry')
        self.assertEqual(rc, 1, (so, se))
        self.assertEqual(out.get('code'), 'REGISTRY_CORRUPT')
        self.assertIn('repair-registry', so)

    def test_merge_cli_adopts_a_legacy_lease_without_conflict(self):
        """Lease v1 ở local + bản remote đã được nhận (session): merge hợp lệ,
        giữ session đã nhận, ID không đổi."""
        self.planned(6)
        wc(self.fx, 'claim', '--writer', 'W1', '--count', '2')
        path = os.path.join(self.fx, REG)
        reg = self.reg()
        remote = copy.deepcopy(reg)
        reg['leases']['W1'].pop('session')
        with open(path, 'w') as f:
            json.dump(reg, f)
        incoming = os.path.join(self.fx, 'incoming-registry.json')
        with open(incoming, 'w') as f:
            json.dump(remote, f)
        rc, out, so, se = wc(self.fx, 'merge', '--file', incoming)
        self.assertEqual(rc, 0, (so, se))
        merged = self.reg()
        self.assertEqual(merged['leases']['W1']['session'], 's-test-W1')
        self.assertEqual(merged['leases']['W1']['ids'],
                         remote['leases']['W1']['ids'])

    def _git(self, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
                   GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
        r = subprocess.run(['git'] + list(args), cwd=self.fx, env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_repair_from_git_never_rolls_back_past_a_conflicted_version(self):
        """Codex P2: registry hiện tại hỏng cú pháp, bản git mới nhất còn tranh
        chấp chủ SỐNG: KHÔNG được nhảy về bản cũ hơn (làm mất lease tranh chấp)."""
        self.planned(8)
        path = os.path.join(self.fx, REG)
        if os.path.exists(path):
            os.remove(path)
        wc(self.fx, 'claim', '--writer', 'W1', '--count', '2')
        self._git('init', '-q')
        self._git('add', REG)
        self._git('commit', '-q', '-m', 'v0 valid')
        wc(self.fx, 'claim', '--writer', 'W2', '--count', '2')
        reg = self.reg()
        reg['leases']['W2']['ids'].append(reg['leases']['W1']['ids'][0])
        with open(path, 'w') as f:
            json.dump(reg, f)
        self._git('add', REG)
        self._git('commit', '-q', '-m', 'v1 conflicted')
        with open(path, 'w') as f:
            f.write('{"leases": ')
        before = _hash(path)
        rc, out, so, se = wc(self.fx, 'repair-registry', '--from-git')
        self.assertEqual(rc, 1, (so, se))
        self.assertEqual(out.get('code'), 'REGISTRY_CONFLICT', (so, se))
        self.assertEqual(_hash(path), before, 'khong duoc ghi registry')

    def test_prune_cleans_an_empty_lease_that_shares_a_session(self):
        self.planned(8)
        path = os.path.join(self.fx, REG)
        if os.path.exists(path):
            os.remove(path)
        wc(self.fx, 'claim', '--writer', 'W1', '--count', '2')
        wc(self.fx, 'claim', '--writer', 'W2', '--count', '2')
        reg = self.reg()
        reg['leases']['W2']['session'] = reg['leases']['W1']['session']
        reg['leases']['W1']['ids'] = []
        with open(path, 'w') as f:
            json.dump(reg, f)
        rc, out, so, se = wc(self.fx, 'prune')
        self.assertEqual(rc, 0, (so, se))
        after = self.reg()
        self.assertNotIn('W1', after['leases'])
        self.assertIn('W2', after['leases'])

    def test_same_lease_duplicate_id_is_reported_then_pruned_not_a_conflict(self):
        """Codex P2 (vòng 3): ID lặp trong MỘT lease không được thành
        REGISTRY_CONFLICT (không có chủ thứ hai) — `check-registry` báo đúng lỗi
        cấu trúc, các lệnh khác vẫn chạy, `prune` tự dọn không đổi chủ."""
        self.planned(8)
        path = os.path.join(self.fx, REG)
        if os.path.exists(path):
            os.remove(path)
        wc(self.fx, 'claim', '--writer', 'W1', '--count', '2')
        reg = self.reg()
        ids = list(reg['leases']['W1']['ids'])
        reg['leases']['W1']['ids'] = ids + [ids[0]]
        with open(path, 'w') as f:
            json.dump(reg, f)
        rc, out, so, se = wc(self.fx, 'check-registry')
        self.assertEqual(rc, 1, (so, se))
        self.assertNotIn(out.get('code'), ('REGISTRY_CONFLICT', 'REGISTRY_CORRUPT'), out)
        self.assertTrue(any('ID lap' in p for p in out['problems']), out)
        for args in (['show'], ['status']):
            rc, out, so, se = wc(self.fx, *args)
            self.assertEqual(rc, 0, (args, so, se))
        rc, out, so, se = wc(self.fx, 'prune')
        self.assertEqual(rc, 0, (so, se))
        after = self.reg()['leases']['W1']
        self.assertEqual(after['ids'], ids)
        self.assertEqual(after['session'], reg['leases']['W1']['session'])
        rc, out, so, se = wc(self.fx, 'check-registry')
        self.assertEqual(rc, 0, (so, se))

    def test_non_utf8_registry_is_corrupt_for_every_command(self):
        """Review độc lập: registry byte không phải UTF-8 là UnicodeDecodeError
        traceback ở CLI/validate/selector (docs hứa REGISTRY_CORRUPT có cấu trúc)."""
        self.planned(4)
        path = os.path.join(self.fx, REG)
        with open(path, 'wb') as f:
            f.write(b'{"schema_version": "2", "leases": {"W1": {"ids": [], '
                    b'"label": "caf\xe9"}}}')
        before = _hash(path)
        for args in (['check-registry'], ['show'], ['status'], ['prune'],
                     ['claim', '--writer', 'W1', '--count', '1'],
                     ['heartbeat', '--writer', 'W1'],
                     ['release', '--writer', 'W1', '--all'],
                     ['repair-registry']):
            rc, out, so, se = wc(self.fx, *args)
            self.assertEqual(rc, 1, (args, so, se))
            self.assertEqual(out.get('code'), 'REGISTRY_CORRUPT', (args, so, se))
            self.assertNotIn('Traceback', se, (args, se))
        self.assertEqual(_hash(path), before, 'lệnh bị từ chối không được ghi registry')

    def test_oversized_integer_ttl_is_a_structured_corruption_in_the_cli(self):
        self.planned(4)
        path = os.path.join(self.fx, REG)
        if os.path.exists(path):
            os.remove(path)
        wc(self.fx, 'claim', '--writer', 'W1', '--count', '2')
        reg = self.reg()
        reg['leases']['W1']['ttl_hours'] = 10 ** 1000
        with open(path, 'w') as f:
            json.dump(reg, f)
        for args in (['check-registry'], ['heartbeat', '--writer', 'W1'], ['prune']):
            rc, out, so, se = wc(self.fx, *args)
            self.assertEqual(rc, 1, (args, so, se))
            self.assertEqual(out.get('code'), 'REGISTRY_CORRUPT', (args, so, se))
            self.assertNotIn('Traceback', se, (args, se))

    def test_conflict_plus_repairable_error_is_still_a_conflict_everywhere(self):
        """Codex P2 (vòng 6): registry tranh chấp chủ + lỗi kiểu trường: mọi lệnh,
        kể cả repair-registry [--from-git], báo REGISTRY_CONFLICT và không ghi gì."""
        path = self._conflicted_registry('id')
        reg = self.reg()
        reg['leases']['W1']['epoch'] = 'abc'
        with open(path, 'w') as f:
            json.dump(reg, f)
        before = _hash(path)
        for args in (['repair-registry'], ['repair-registry', '--from-git'],
                     ['check-registry'], ['prune'], ['status']):
            rc, out, so, se = wc(self.fx, *args)
            self.assertEqual(rc, 1, (args, so, se))
            self.assertEqual(out.get('code'), 'REGISTRY_CONFLICT', (args, so, se))
            self.assertNotIn('--from-git', so, (args, so))
        self.assertEqual(_hash(path), before)

    def test_conflict_masked_by_a_shape_error_elsewhere_is_never_repaired(self):
        """Review độc lập: W1/W2 tranh chấp ID, W3 là lease sống của phiên thứ ba, và một
        lease khác sai hình dạng (`W4: 5`): trước đây REGISTRY_CORRUPT nên repair-registry
        khôi phục bản cũ và âm thầm XÓA W3 (lease sống) cùng bằng chứng tranh chấp."""
        self.planned(10)
        path = os.path.join(self.fx, REG)
        if os.path.exists(path):
            os.remove(path)
        for slot in ('W1', 'W2', 'W3'):
            wc(self.fx, 'claim', '--writer', slot, '--count', '2')
        self._git('init', '-q')
        self._git('add', REG)
        self._git('commit', '-q', '-m', 'v1 valid (W1,W2,W3)')
        reg = self.reg()
        reg['leases']['W2']['ids'].append(reg['leases']['W1']['ids'][0])
        reg['leases']['W4'] = 5
        with open(path, 'w') as f:
            json.dump(reg, f)
        before = _hash(path)
        for args in (['check-registry'], ['status'], ['repair-registry'],
                     ['repair-registry', '--from-git']):
            rc, out, so, se = wc(self.fx, *args)
            self.assertEqual(rc, 1, (args, so, se))
            self.assertEqual(out.get('code'), 'REGISTRY_CONFLICT', (args, so, se))
        self.assertEqual(_hash(path), before, 'registry khong duoc bi rollback/ghi')
        self.assertIn('W3', self.reg()['leases'], 'lease song W3 phai con nguyen')

    def _history(self):
        """v1 hợp lệ (W1+W2) đã commit; trả (path, registry v1)."""
        self.planned(8)
        path = os.path.join(self.fx, REG)
        if os.path.exists(path):
            os.remove(path)
        wc(self.fx, 'claim', '--writer', 'W1', '--count', '2')
        wc(self.fx, 'claim', '--writer', 'W2', '--count', '2')
        self._git('init', '-q')
        self._git('add', REG)
        self._git('commit', '-q', '-m', 'v1 valid')
        return path, self.reg()

    def test_repair_from_git_skips_a_non_utf8_historical_version(self):
        path, good = self._history()
        with open(path, 'wb') as f:
            f.write(b'{"schema_version": "2", "leases": {}, "note": "caf\xe9"}')
        self._git('add', REG)
        self._git('commit', '-q', '-m', 'v2 invalid utf8')
        with open(path, 'w') as f:
            f.write('{"schema_version": "2", "leases": {')
        self._git('add', REG)
        self._git('commit', '-q', '-m', 'v3 truncated (HEAD)')
        rc, out, so, se = wc(self.fx, 'repair-registry', '--from-git')
        self.assertEqual(rc, 0, (so, se))
        self.assertTrue(out.get('source', '').startswith('git:'), out)
        self.assertEqual(sorted(self.reg()['leases']), ['W1', 'W2'])
        self.assertEqual(self.reg()['leases']['W1']['ids'], good['leases']['W1']['ids'])

    def test_unknown_slot_key_is_corruption_and_never_evicts_a_live_lease(self):
        """Review độc lập: khóa 'W4' được nhận, heartbeat của W1 cắt MAX_WRITERS
        và ĐÁ lease sống W3 (claim mới nhất). Giờ: REGISTRY_CORRUPT, không ghi gì,
        `repair-registry --from-git` khôi phục bản tốt gần nhất với W1/W2 nguyên vẹn."""
        path, good = self._history()
        wc(self.fx, 'claim', '--writer', 'W3', '--count', '2')
        self._git('add', REG)
        self._git('commit', '-q', '-m', 'v2 with W3')
        reg = self.reg()
        reg['leases']['W4'] = dict(reg['leases']['W1'], session='s-ghost',
                                   ids=[self.planned(30)[-1]],
                                   claimed_at='2026-01-01T00:00:00Z')
        with open(path, 'w') as f:
            json.dump(reg, f)
        self._git('add', REG)
        self._git('commit', '-q', '-m', 'v3 bogus W4')
        before = _hash(path)
        for args in (['check-registry'], ['status'],
                     ['heartbeat', '--writer', 'W1'], ['prune']):
            rc, out, so, se = wc(self.fx, *args)
            self.assertEqual(rc, 1, (args, so, se))
            self.assertEqual(out.get('code'), 'REGISTRY_CORRUPT', (args, so, se))
        self.assertEqual(_hash(path), before, 'không lệnh nào được ghi registry')
        rc, out, so, se = wc(self.fx, 'repair-registry', '--from-git')
        self.assertEqual(rc, 0, (so, se))
        self.assertEqual(sorted(self.reg()['leases']), ['W1', 'W2', 'W3'])

    def test_release_cli_cannot_give_a_session_two_live_slots(self):
        """Codex P2 (vòng 3): đường trực tiếp tài liệu hóa
        `release --writer <slot legacy> --session <phiên đã giữ slot khác> --ids <1 ID>`
        từng ghi registry mà một phiên giữ hai slot sống (rồi mọi lệnh sau đó
        REGISTRY_CONFLICT). Phải bị từ chối, registry không đổi, vẫn hợp lệ."""
        self.planned(8)
        path = os.path.join(self.fx, REG)
        if os.path.exists(path):
            os.remove(path)
        wc(self.fx, 'claim', '--writer', 'W1', '--count', '2')
        wc(self.fx, 'claim', '--writer', 'W2', '--count', '2')
        reg = self.reg()
        reg['leases']['W2'].pop('session')               # W2 = lease legacy v1
        w2_ids = list(reg['leases']['W2']['ids'])
        with open(path, 'w') as f:
            json.dump(reg, f)
        before = _hash(path)
        rc, out, so, se = wc(self.fx, 'release', '--writer', 'W2', '--session',
                             reg['leases']['W1']['session'], '--ids', w2_ids[0])
        self.assertEqual(rc, 1, (so, se))
        self.assertEqual(out.get('code'), 'SESSION_HOLDS_OTHER_SLOT', out)
        self.assertEqual(_hash(path), before, 'lệnh bị từ chối không được ghi registry')
        rc, out, so, se = wc(self.fx, 'check-registry')
        self.assertEqual(rc, 0, (so, se))

    def test_01_w1_claims_10_ids(self):
        ids = self.planned(10)
        mh = self.matrix_guard()
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                           '--count', '10')
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(out['leased_total']), 10)
        self.assertEqual(out['leased_total'], sorted(ids[:10]))
        self.assertEqual(self.matrix_guard(), mh, 'matrix bị mutate')

    def test_02_w2_cannot_claim_w1_ids(self):
        self.planned(20)
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                           '--count', '10')
        self.assertEqual(rc, 0)
        w1_ids = out['leased_total']
        mh = self.matrix_guard()
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W2',
                           '--ids', ','.join(w1_ids[:3]))
        self.assertEqual(rc, 1, 'W2 phải bị refuse khi lease ID của W1')
        self.assertIn('lease', json.dumps(out))
        self.assertEqual(self.matrix_guard(), mh, 'matrix bị mutate')

    def test_03_w2_claims_next_10(self):
        self.planned(20)
        _, out, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                         '--count', '10')
        w1 = set(out['leased_total'])
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W2',
                           '--count', '10')
        self.assertEqual(rc, 0)
        self.assertEqual(len(out['leased_total']), 10)
        self.assertFalse(w1 & set(out['leased_total']),
                         'hai writer không được trùng ID')

    def test_04_w3_claims_next(self):
        ids = self.planned(30)
        for w in ('W1', 'W2'):
            rc, out, _, _ = wc(self.fx, 'claim', '--writer', w,
                               '--count', '10')
            self.assertEqual(rc, 0)
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W3',
                           '--count', '10')
        self.assertEqual(rc, 0)
        self.assertEqual(len(out['leased_total']), 10)
        self.assertEqual(out['leased_total'], sorted(ids[20:30]))

    def test_05_fourth_writer_refused(self):
        self.planned(30)
        for w in ('W1', 'W2', 'W3'):
            rc, _, _, _ = wc(self.fx, 'claim', '--writer', w,
                             '--count', '10')
            self.assertEqual(rc, 0)
        mh = self.matrix_guard()
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W4',
                          '--count', '10')
        self.assertEqual(rc, 1, 'writer thứ 4 phải bị refuse')
        self.assertNotIn('W4', self.reg()['leases'])
        self.assertEqual(self.matrix_guard(), mh, 'matrix bị mutate')

    def test_06_release_returns_right_ids(self):
        ids = self.planned(6)
        _, out, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                         '--ids', ','.join(ids[:3]))
        mh = self.matrix_guard()
        rc, out, _, _ = wc(self.fx, 'release', '--writer', 'W1',
                          '--ids', ','.join(ids[:2]))
        self.assertEqual(rc, 0)
        self.assertEqual(out['released'], sorted(ids[:2]))
        self.assertEqual(out['leased_total'], ids[2:3])
        self.assertEqual(self.matrix_guard(), mh, 'matrix bị mutate')
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W2',
                          '--ids', ids[0])
        self.assertEqual(rc, 0, 'id đã release phải claim lại được')

    def test_07_ttl_expiry_reclaim(self):
        ids = self.planned(4)
        _, out, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                         '--ids', ','.join(ids[:2]))
        reg = self.reg()
        reg['leases']['W1']['expires_at'] = '2000-01-01T00:00:00Z'
        with open(os.path.join(self.fx, REG), 'w', encoding='utf-8') as f:
            json.dump(reg, f)
        mh = self.matrix_guard()
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W2',
                          '--ids', ','.join(ids[:2]))
        self.assertEqual(rc, 0, 'lease hết TTL phải reclaim được')
        self.assertEqual(out['leased_total'], sorted(ids[:2]))
        self.assertEqual(self.matrix_guard(), mh, 'matrix bị mutate')

    def test_08_stale_published_lease_pruned(self):
        ids = self.planned(4)
        _, _, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                       '--ids', ','.join(ids[:2]))
        rows = matrix_rows(self.fx)
        for r in rows:
            if r['id'] == ids[0]:
                r['status'] = 'PUBLISHED'
        save_matrix(self.fx, rows)
        mh = self.matrix_guard()
        rc, out, _, _ = wc(self.fx, 'show')
        self.assertEqual(rc, 0)
        leases = out['writers']['W1']
        self.assertNotIn(ids[0], leases,
                         'ID PUBLISHED phải bị prune khỏi lease')
        self.assertIn(ids[1], leases)
        self.assertEqual(self.matrix_guard(), mh, 'show KHÔNG mutate matrix')

    def test_09_blocked_existing_lease_pruned(self):
        ids = self.planned(6)
        _, _, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                       '--ids', ','.join(ids[:3]))
        rows = matrix_rows(self.fx)
        st = {ids[0]: 'BLOCKED', ids[1]: 'EXISTING'}
        for r in rows:
            if r['id'] in st:
                r['status'] = st[r['id']]
        save_matrix(self.fx, rows)
        rc, out, _, _ = wc(self.fx, 'prune')
        self.assertEqual(rc, 0)
        kept = out['report']['kept']['W1']
        self.assertNotIn(ids[0], kept, 'ID BLOCKED phải bị prune')
        self.assertNotIn(ids[1], kept, 'ID EXISTING phải bị prune')
        self.assertIn(ids[2], kept)

    def test_10_merge_race_deterministic(self):
        ids = self.planned(4)
        _, out, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                         '--ids', ids[0])
        remote = {'schema_version': '1', 'leases': {
            'W2': {'ids': [ids[0]], 'claimed_at': '2099-01-01T00:00:00Z',
                   'expires_at': '2099-01-03T00:00:00Z'}}}
        rp = os.path.join(self.fx, 'tmp-remote-registry.json')
        with open(rp, 'w', encoding='utf-8') as f:
            json.dump(remote, f)
        mh = self.matrix_guard()
        rc, out, _, _ = wc(self.fx, 'merge', '--file', rp)
        self.assertEqual(rc, 0)
        self.assertEqual(out['lost_to_other_writer'],
                         [{'id': ids[0], 'winner': 'W1', 'loser': 'W2'}],
                         'claimed_at sớm hơn phải thắng')
        self.assertEqual(self.reg()['leases']['W1']['ids'], [ids[0]])
        self.assertEqual(self.matrix_guard(), mh, 'matrix bị mutate')

    def test_11_earlier_remote_timestamp_cannot_steal_live_id(self):
        ids = self.planned(4)
        _, _, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                       '--ids', ','.join(ids[:2]))
        remote = {'schema_version': '1', 'leases': {
            'W2': {'ids': [ids[0]], 'claimed_at': '2000-01-01T00:00:00Z',
                   'expires_at': '2099-01-03T00:00:00Z'}}}
        rp = os.path.join(self.fx, 'tmp-remote-registry.json')
        with open(rp, 'w', encoding='utf-8') as f:
            json.dump(remote, f)
        rc, out, _, _ = wc(self.fx, 'merge', '--file', rp)
        self.assertEqual(rc, 0)
        self.assertEqual(out['lost_to_other_writer'],
                         [{'id': ids[0], 'winner': 'W1', 'loser': 'W2'}])
        reg = self.reg()['leases']
        self.assertIn(ids[0], reg['W1']['ids'])
        self.assertNotIn('W2', reg, 'không chuyển chủ lease sống bằng timestamp')

    def test_12_claim_refuses_non_planned_and_cap(self):
        ids = self.planned(6)
        rows = matrix_rows(self.fx)
        for r in rows:
            if r['id'] == ids[0]:
                r['status'] = 'REVIEW'
        save_matrix(self.fx, rows)
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                          '--ids', ids[0])
        self.assertEqual(rc, 1, 'id không PLANNED phải bị refuse')
        rc, out, _, _ = wc(self.fx, 'claim', '--writer', 'W1',
                          '--count', '11')
        self.assertEqual(rc, 1, 'claim 11 > MAX_LEASE phải bị refuse')



class ClassificationOracleTest(unittest.TestCase):
    """Property test: parse_registry vs an INDEPENDENT statement of the documented
    classification (OK / CORRUPT / CONFLICT) over seeded random registries. Expired
    leases are disposable; live ownership conflicts are computed on recognizable data
    (valid IDs, valid session tokens) and win over every repairable error; only then
    do the strict structure errors of live leases make a registry CORRUPT. Every OK
    registry must also be safe to use for every operation."""

    ID_OK = re.compile(r'^BLG-[0-9]+\Z')
    SESS_OK = re.compile(r'^[A-Za-z0-9._-]{1,64}\Z')
    SLOT_OK = re.compile(r'^W[1-3]\Z')
    TS_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?'
                       r'(Z|[+-]\d{2}:?\d{2})?$')
    VALID_IDS = ['BLG-%05d' % i for i in range(1, 25)]
    BAD_IDS = ['bad-id', 'BLG-1x', 'BLG-00001\n', '', 5, None, ['BLG-00001'], {'a': 1}, True]
    SESSIONS_OK = ['s-one', 's-two', 's-three', 's-x']
    SESSIONS_BAD = ['bad session!', 's-a\n', '', 5, ['s'], True, 's' * 65]
    EPOCH = [None, 1, 2, 0, 'abc', True, 1.5, [1], {'a': 1}, -3, 10 ** 30]
    TTL = [None, 12.0, 48, 0.25, 'abc', True, [], float('nan'), float('inf'),
           10 ** 1000, 10 ** 300, -5]
    LABEL = [None, 'lbl', 5, {}, ['x'], True]

    def setUp(self):
        self.now = time.time()
        self.rng = __import__('random').Random(20261012)
        self.rows = [{'id': 'BLG-%05d' % n, 'status': 'PLANNED'} for n in range(1, 60)]

    def iso(self, e):
        """Realistic timestamp spellings the registry accepts: Z, fractional seconds,
        a space separator, numeric offsets, no zone (UTC)."""
        base = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(e))
        k = self.rng.random()
        if k < 0.55:
            return base + 'Z'
        if k < 0.70:
            return base + '.849Z'
        if k < 0.80:
            return base.replace('T', ' ') + 'Z'
        if k < 0.90:
            off = self.rng.choice([7, -5, 0, 3])
            local = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(e + off * 3600))
            return '%s%s%02d:00' % (local, '+' if off >= 0 else '-', abs(off))
        return base

    @classmethod
    def parse_ts(cls, s):
        """Independent timestamp reader (None = unreadable)."""
        m = cls.TS_RE.match(s.strip()) if isinstance(s, str) else None
        if not m:
            return None
        try:
            y, mo, d, h, mi, sec = (int(x) for x in m.groups()[:6])
            base = calendar.timegm(datetime.datetime(y, mo, d, h, mi, sec).timetuple())
        except ValueError:
            return None
        tz = m.group(7)
        if tz and tz != 'Z':
            digits = tz[1:].replace(':', '')
            off = int(digits[:2]) * 3600 + int(digits[2:]) * 60
            base -= off if tz[0] == '+' else -off
        return base

    def stamp(self):
        return self.rng.choice([None, self.iso(self.now - 1000), 5, [], 'garbage', True])

    def gen_lease(self):
        rng, r = self.rng, {}
        k = rng.random()
        if k < 0.45:
            r['expires_at'] = self.iso(self.now + 3600)
        elif k < 0.80:
            r['expires_at'] = self.iso(self.now - 3600)
        elif k < 0.85:
            r['expires_at'] = 'garbage'
        elif k < 0.90:
            r['expires_at'] = None
        elif k < 0.93:
            r['expires_at'] = 5
        else:
            r['expires_at'] = self.iso(self.now + 7200)
        ids = [rng.choice(self.VALID_IDS) for _ in range(rng.choice([0, 1, 2, 2, 3, 5, 11, 12]))]
        if rng.random() < 0.15:
            ids.append(rng.choice(self.BAD_IDS))
        if rng.random() < 0.10 and ids:
            ids.append(ids[0])
        if rng.random() < 0.03:
            ids = rng.choice(['BLG-00001', 5, {'a': 1}, None])
        if rng.random() > 0.04:
            r['ids'] = ids
        s = rng.random()
        if s < 0.55:
            r['session'] = rng.choice(self.SESSIONS_OK)
        elif s < 0.70:
            r['session'] = rng.choice(self.SESSIONS_BAD)
        elif s >= 0.80:
            r['session'] = None
        if rng.random() < 0.25:
            r['epoch'] = rng.choice(self.EPOCH)
        if rng.random() < 0.25:
            r['ttl_hours'] = rng.choice(self.TTL)
        if rng.random() < 0.20:
            r['label'] = rng.choice(self.LABEL)
        if rng.random() < 0.20:
            r['claimed_at'] = self.stamp()
        if rng.random() < 0.20:
            r['heartbeat_at'] = self.stamp()
        return r

    def gen_registry(self):
        rng, leases = self.rng, {}
        for _ in range(rng.choice([0, 1, 2, 3, 3, 4, 5])):
            key = rng.choice(['W1', 'W2', 'W3', 'W1', 'W2', 'W3', 'W4', 'w1', 'W1 ', 'W1\n', 'W0'])
            leases[key] = self.gen_lease() if rng.random() > 0.02 else rng.choice([None, 5, [], 'x'])
        return {'schema_version': '2', 'leases': leases}

    @staticmethod
    def finite(x):
        try:
            return math.isfinite(x)
        except OverflowError:
            return False

    def oracle(self, d):
        if not isinstance(d, dict) or not isinstance(d.get('leases'), dict):
            return 'CORRUPT'
        shape_bad, live = False, {}
        for w, l in d['leases'].items():
            if not isinstance(l, dict):
                shape_bad = True            # reported only AFTER the conflict analysis
                continue
            e = l.get('expires_at')
            if e not in (None, ''):
                epoch = self.parse_ts(e)
                if epoch is None:
                    shape_bad = True
                    continue
                live[w] = epoch >= self.now
            else:
                live[w] = False
        holders, sessions = {}, {}
        for w, l in d['leases'].items():
            if not live.get(w):
                continue
            ids = l.get('ids')
            valid = [a for a in ids if isinstance(a, str) and self.ID_OK.match(a)] \
                if isinstance(ids, list) else []
            for a in set(valid):
                holders.setdefault(a, set()).add(w)
            s = l.get('session')
            if valid and isinstance(s, str) and self.SESS_OK.match(s):
                sessions.setdefault(s, set()).add(w)
        if any(len(v) > 1 for v in holders.values()) or any(len(v) > 1 for v in sessions.values()):
            return 'CONFLICT'
        if shape_bad:
            return 'CORRUPT'
        for w, l in d['leases'].items():
            if not live[w]:
                continue
            ids = l.get('ids', [])
            if not isinstance(ids, list) or any(
                    not (isinstance(a, str) and self.ID_OK.match(a)) for a in ids):
                return 'CORRUPT'
            ep = l.get('epoch')
            if ep is not None and (isinstance(ep, bool) or not isinstance(ep, int)):
                return 'CORRUPT'
            tt = l.get('ttl_hours')
            if tt is not None and (isinstance(tt, bool) or not isinstance(tt, (int, float))
                                   or not self.finite(tt)):
                return 'CORRUPT'
            if any(l.get(k) is not None and not isinstance(l.get(k), str)
                   for k in ('label', 'claimed_at', 'heartbeat_at')):
                return 'CORRUPT'
            if not (isinstance(w, str) and self.SLOT_OK.match(w)):
                return 'CORRUPT'
            if len(set(ids)) > WC.MAX_LEASE:
                return 'CORRUPT'
            s = l.get('session')
            if s is not None and not (isinstance(s, str) and self.SESS_OK.match(s)):
                return 'CORRUPT'
        return 'OK'

    def test_parse_registry_matches_the_documented_classification(self):
        seen = {}
        for _ in range(4000):
            text = json.dumps(self.gen_registry())
            want = self.oracle(json.loads(text))
            try:
                reg = WC.parse_registry(text)
                got = 'OK'
            except WC.OwnershipConflict:
                got = 'CONFLICT'
            except WC.RegistryCorrupt:
                got = 'CORRUPT'
            self.assertEqual(got, want, text[:300])
            seen[got] = seen.get(got, 0) + 1
            if got != 'OK':
                continue
            for slot in ('W1', 'W2', 'W3'):
                for sess in ('s-one', 's-new'):
                    for op in (lambda r: WC.apply_claim(r, self.rows, slot, sess, count=1, now=self.now),
                               lambda r: WC.apply_heartbeat(r, self.rows, slot, sess, now=self.now),
                               lambda r: WC.apply_release(r, self.rows, slot, sess,
                                                          ids=['BLG-00001'], now=self.now),
                               lambda r: WC.prune_registry(r, self.rows, self.now),
                               lambda r: WC.check_invariants(r, self.rows, self.now),
                               lambda r: WC.orphan_rows(r, self.rows, self.now)):
                        op(copy.deepcopy(reg))          # must not raise
        for kind in ('OK', 'CORRUPT', 'CONFLICT'):
            self.assertGreater(seen.get(kind, 0), 100, 'generator must exercise %s' % kind)


if __name__ == '__main__':
    unittest.main(verbosity=2)
