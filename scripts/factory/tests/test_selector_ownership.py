#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Test OWNERSHIP MULTI-WRITER của CANONICAL selector push-selection.py.

Hợp đồng Phase 2 (migration multi-writer từ /vanchinh):
  - registry data/state/writer-claims.json KHÔNG tồn tại = single-writer
    legacy: selector giữ NGUYÊN semantics cũ (mọi regression test cũ
    vẫn xanh, draft KHÔNG cần khai writer);
  - registry TỒN TẠI = multi-writer mode ON: mọi ID PLANNED cần claim
    PHẢI (i) có lease sống (chưa hết TTL 48h) trong registry và
    (ii) draft PHẢI khai `writer: Wx` khớp writer đang giữ lease;
    vi phạm -> REFUSE fail-closed exit 3, KHÔNG đổi gì;
  - repair rows KHÔNG claim lại từ đầu nên KHÔNG cần lease;
  - selector CHỈ ĐỌC registry — KHÔNG prune/mutate registry bao giờ.

BO TEST NAY KHÔNG viết bài thật: mọi mutation trên bản sao tạm
(FxTestCase của test_qa_modes.py); production state phải
BYTE-IDENTICAL trước/sau (hash guard setUpModule/tearDownModule).

Chạy: python3 scripts/factory/tests/test_selector_ownership.py (từ repo)
"""
import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_qa_modes import (FxTestCase, borrow_planned_row, make_draft,
                            matrix_rows, save_matrix, write_json)
from test_push_selection import selection, planned_rows, draft_rel

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

REAL_GUARD_FILES = [
    'data/content-matrix.csv',
    'data/state/checkpoint.json',
    'data/state/transaction.json',
    'data/factory/production-control.json',
]
_GUARD = {}


def _file_hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def setUpModule():
    for rel in REAL_GUARD_FILES:
        _GUARD[rel] = _file_hash(os.path.join(ROOT, rel))
    reg = os.path.join(ROOT, 'data/state/writer-claims.json')
    if os.path.isfile(reg):
        _GUARD['data/state/writer-claims.json'] = _file_hash(reg)


def tearDownModule():
    for rel, want in _GUARD.items():
        got = _file_hash(os.path.join(ROOT, rel))
        assert got == want, (
            'PRODUCTION STATE BỊ ĐỔI TRONG TEST: %s (%s != %s)'
            % (rel, got, want))


REGISTRY_REL = 'data/state/writer-claims.json'


def registry_path(fx):
    return os.path.join(fx, REGISTRY_REL)


def write_registry(fx, leases):
    write_json(fx, REGISTRY_REL,
               {'schema_version': '1',
                'updated_at': '2026-10-02T00:00:00Z',
                'leases': leases})


def lease_entry(ids, claimed='2026-10-01T00:00:00Z',
                expires='2026-10-04T00:00:00Z'):
    return {'ids': list(ids), 'claimed_at': claimed,
            'expires_at': expires}


def declare_writer(fx, rel, writer):
    """Chèn `writer: Wx` vào frontmatter draft (trước --- kết thúc)."""
    p = os.path.join(fx, rel)
    with open(p, encoding='utf-8') as f:
        text = f.read()
    assert text.startswith('---\n'), rel
    end = text.index('\n---\n', 4)
    text = text[:end] + '\nwriter: %s' % writer + text[end:]
    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)


def borrow(fx, count):
    """Mượn `count` hàng PLANNED + draft đạt gate cho từng hàng."""
    borrow_planned_row(fx, count=count)
    rows = planned_rows(fx)
    assert len(rows) >= count
    chosen = rows[:count]
    for row in chosen:
        make_draft(fx, row)
    return chosen


class SelectorOwnershipTest(FxTestCase):

    # ------------------------------------------- single-writer legacy

    def test_01_legacy_mode_without_registry(self):
        """Registry KHÔNG tồn tại: semantics cũ giữ nguyên — draft KHÔNG
        khai writer vẫn được chọn queue bình thường (multi_writer off)."""
        if os.path.exists(registry_path(self.fx)):
            os.remove(registry_path(self.fx))
        rows = borrow(self.fx, 2)
        rc, sel = selection(self.fx,
                            added=[draft_rel(r) for r in rows])
        self.assertEqual(rc, 0)
        self.assertTrue(sel['proceed'])
        self.assertFalse(sel['multi_writer'])
        self.assertEqual(sel['queue'], [r['id'] for r in rows])

    # ----------------------------------------- multi-writer mode ON

    def test_02_valid_lease_and_writer_proceed(self):
        rows = borrow(self.fx, 2)
        ids = [r['id'] for r in rows]
        write_registry(self.fx, {'W1': lease_entry(ids)})
        for r in rows:
            declare_writer(self.fx, draft_rel(r), 'W1')
        rc, sel = selection(self.fx,
                            added=[draft_rel(r) for r in rows])
        self.assertEqual(rc, 0)
        self.assertTrue(sel['proceed'])
        self.assertTrue(sel['multi_writer'])
        self.assertEqual(sel['queue'], ids)
        self.assertEqual(sel['writers'], {ids[0]: 'W1', ids[1]: 'W1'})

    def test_03_id_without_live_lease_refused(self):
        rows = borrow(self.fx, 2)
        ids = [r['id'] for r in rows]
        # registry ON nhưng W1 chỉ lease ID đầu — ID sau KHÔNG có lease
        write_registry(self.fx, {'W1': lease_entry([ids[0]])})
        for r in rows:
            declare_writer(self.fx, draft_rel(r), 'W1')
        rc, sel = selection(self.fx,
                            added=[draft_rel(r) for r in rows],
                            rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('khong co lease song', sel['refuse'])
        self.assertIn(ids[1], sel['refuse'])
        # fail-closed: KHÔNG hàng nào rời PLANNED (repo thật có thể
        # đã giữ sẵn các hàng PLANNED khác — chỉ chặn đúng 2 hàng mượn)
        after = {r['id']: r['status'] for r in matrix_rows(self.fx)}
        self.assertEqual({after[i] for i in ids}, {'PLANNED'})

    def test_04_wrong_writer_refused(self):
        rows = borrow(self.fx, 1)
        aid = rows[0]['id']
        write_registry(self.fx, {'W1': lease_entry([aid])})
        declare_writer(self.fx, draft_rel(rows[0]), 'W2')
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])],
                            rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('lease dang thuoc writer W1', sel['refuse'])
        self.assertIn('khai writer W2', sel['refuse'])

    def test_05_missing_writer_field_refused(self):
        rows = borrow(self.fx, 1)
        aid = rows[0]['id']
        write_registry(self.fx, {'W1': lease_entry([aid])})
        # draft KHÔNG khai writer -> identity không xác định -> refuse
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])],
                            rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('khai writer None', sel['refuse'])

    def test_06_expired_lease_refused(self):
        """Lease hết TTL 48h là CHẾT — phải refuse (reclaim qua
        writer-claim.py claim/prune, KHÔNG qua selector)."""
        rows = borrow(self.fx, 1)
        aid = rows[0]['id']
        write_registry(self.fx,
                       {'W1': lease_entry([aid],
                                          claimed='2026-09-28T00:00:00Z',
                                          expires='2026-09-30T00:00:00Z')})
        declare_writer(self.fx, draft_rel(rows[0]), 'W1')
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])],
                            rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('khong co lease song', sel['refuse'])

    def test_07_repair_rows_do_not_need_lease(self):
        """Repair rows KHÔNG claim lại từ đầu (engine semantic) —
        prune tự loại id không còn PLANNED khỏi registry, nên repair
        push KHÔNG bị chặn vì lease."""
        rows = borrow(self.fx, 2)
        ids = [r['id'] for r in rows]
        allrows = matrix_rows(self.fx)
        for r in allrows:
            if r['id'] in set(ids):
                r['status'] = 'REPAIR'
        save_matrix(self.fx, allrows)
        # registry ON nhưng KHÔNG lease ID nào
        write_registry(self.fx, {})
        rc, sel = selection(self.fx,
                            added=[draft_rel(r) for r in rows])
        self.assertEqual(rc, 0)
        self.assertTrue(sel['proceed'])
        self.assertEqual(sel['mode'], 'repair')
        self.assertEqual(sel['claim_ids'], [])
        self.assertEqual(sel['queue'], ids)

    def test_08_selector_never_mutates_registry(self):
        rows = borrow(self.fx, 1)
        aid = rows[0]['id']
        write_registry(self.fx, {'W1': lease_entry([aid])})
        declare_writer(self.fx, draft_rel(rows[0]), 'W1')
        before = _file_hash(registry_path(self.fx))
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])])
        self.assertTrue(sel['proceed'])
        self.assertEqual(_file_hash(registry_path(self.fx)), before,
                         'selector KHÔNG được prune/mutate registry '
                         '(chỉ ĐỌC; prune thuộc writer-claim.py)')
        # refuse path cũng KHÔNG được mutate registry
        write_registry(self.fx, {'W1': lease_entry([aid])})
        before = _file_hash(registry_path(self.fx))
        make_draft(self.fx, rows[0])  # draft sạch, KHÔNG còn writer cũ
        declare_writer(self.fx, draft_rel(rows[0]), 'W2')
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])],
                            rc_expect=3)
        self.assertEqual(_file_hash(registry_path(self.fx)), before)

    def test_09_registry_present_empty_leases_refuses_all_claims(self):
        """Fail-closed: registry hỏng/rỗng (JSON hợp lệ, không lease
        sống) trong multi-writer mode -> KHÔNG ID nào được claim."""
        rows = borrow(self.fx, 1)
        declare_writer(self.fx, draft_rel(rows[0]), 'W1')
        write_registry(self.fx, {})
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])],
                            rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('khong co lease song', sel['refuse'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
