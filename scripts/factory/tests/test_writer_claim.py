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
import hashlib
import importlib.util
import json
import os
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
