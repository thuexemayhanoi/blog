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
import json
import os
import subprocess
import sys
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
    """Chạy writer-claim.py trong fixture; trả (rc, parsed JSON)."""
    r = subprocess.run(
        [sys.executable, 'scripts/factory/writer-claim.py'] + list(args),
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


class WriterClaimTest(FxTestCase):
    """Mọi test chạy trên bản sao repo riêng (self.fx)."""

    def planned(self, n):
        """Đảm bảo fixture có >= n hàng PLANNED (top-up hermetic)."""
        borrow_planned_row(self.fx, count=n)
        return [r['id'] for r in matrix_rows(self.fx)
                if r['status'] == 'PLANNED']

    def reg(self):
        p = os.path.join(self.fx, REG)
        return json.load(open(p, encoding='utf-8')) \
            if os.path.exists(p) else {'leases': {}}

    def matrix_guard(self):
        return _hash(os.path.join(self.fx, MATRIX))

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

    def test_11_same_id_conflict_single_owner(self):
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
        self.assertEqual(out['conflicts'],
                         [{'id': ids[0], 'winner': 'W2', 'loser': 'W1'}])
        reg = self.reg()['leases']
        self.assertIn(ids[0], reg['W2']['ids'])
        self.assertNotIn(ids[0], reg['W1']['ids'],
                         'một ID chỉ MỘT owner sau xung đột')

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
