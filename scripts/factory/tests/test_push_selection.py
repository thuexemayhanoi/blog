#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test CANONICAL queue selector — scripts/factory/push-selection.py.

Hợp đồng 6 workflow (docs/factory-workflow-contract.md): đường nóng
sản xuất là factory-publish.yml — workflow CHỈ orchestration, mọi
business rule selection thuộc về push-selection.py (một nguồn sự thật,
KHÔNG còn selector Python inline trùng lặp trong YAML).

Semantics được chặt (port CHÍNH XÁC từ selector inline cũ):
  - queue tối đa 10 draft/push (MAX_QUEUE_PER_PUSH); KHÔNG có min —
    push 1 draft hợp lệ; queue LẺ hợp lệ (pair cuối 1 ID);
  - EXACT article_id; refuse (exit 3, fail-closed): thiếu article_id /
    ID trùng / > 10 / ID lạ / hàng PUBLISHED-EXISTING-BLOCKED;
  - deterministic matrix order; mode new/repair (repair KHÔNG claim lại
    từ đầu); production-control enabled=false dừng sạch TRƯỚC claim;
  - selector KHÔNG mutate production state;
  - guard fail-closed ở tầng engine (prepare-next TỪ CHỐI khi còn
    transaction active hoặc writer-lock của writer khác).

BO TEST NAY KHÔNG viết bài thật: mọi mutation trên bản sao tạm
(FxTestCase của test_qa_modes.py); production matrix/checkpoint phải
BYTE-IDENTICAL trước/sau toàn bộ bộ test (hash guard ở
setUpModule/tearDownModule).

Chạy: python3 scripts/factory/tests/test_push_selection.py (từ repo)
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

from test_qa_modes import (FxTestCase, borrow_planned_row, cp_json,
                            make_draft, matrix_rows, save_matrix,
                            write_json)

REAL_GUARD_FILES = [
    'data/content-matrix.csv',
    'data/state/checkpoint.json',
    'data/state/transaction.json',
    'data/factory/production-control.json',
]
_GUARD = {}

# chuỗi GHÉP để file test không chứa slug template nguyên vẹn —
# draft-leak gate grep slug này trên cây build (scripts/ bị copy)
TPL_SLUG = 'mau' + '-nhap' + '-bai' + '-moi'


def _file_hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def setUpModule():
    for rel in REAL_GUARD_FILES:
        _GUARD[rel] = _file_hash(os.path.join(ROOT, rel))


def tearDownModule():
    for rel in REAL_GUARD_FILES:
        got = _file_hash(os.path.join(ROOT, rel))
        assert got == _GUARD[rel], (
            'PRODUCTION STATE BỊ ĐỔI TRONG TEST: %s (%s != %s)'
            % (rel, got, _GUARD[rel]))


def selection(fx, added=(), modified=(), rc_expect=0, env=None):
    """Chạy push-selection.py trên fixture; trả (rc, dict JSON)."""
    ap = os.path.join(fx, 'tmp-added.txt')
    mp = os.path.join(fx, 'tmp-modified.txt')
    with open(ap, 'w', encoding='utf-8') as f:
        f.write('\n'.join(added) + ('\n' if added else ''))
    with open(mp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(modified) + ('\n' if modified else ''))
    r = subprocess.run(
        [sys.executable, 'scripts/factory/push-selection.py',
         '--added', ap, '--modified', mp],
        cwd=fx, capture_output=True, text=True, env=env)
    assert r.returncode == rc_expect, (
        'push-selection rc=%d (kỳ vọng %d): %s%s'
        % (r.returncode, rc_expect, r.stdout, r.stderr))
    lines = [l for l in r.stdout.splitlines() if l.strip().startswith('{')]
    return r.returncode, json.loads(lines[-1])


def planned_rows(fx):
    return [r for r in matrix_rows(fx) if r['status'] == 'PLANNED']


def writing_rows(fx):
    return [r for r in matrix_rows(fx) if r['status'] == 'WRITING']


def draft_rel(row):
    slug = row['output_path'][len('_posts/{date}-'):-3]
    return '_drafts/2026-09-28-%s.md' % slug


class CanonicalQueueSelectionTest(FxTestCase):
    """Queue 2..10, exact-ID, refuse fail-closed, deterministic order,
    mode new/repair, paused-before-claim, no-op, no mutation."""

    # ---------------------------------------------------------- helpers

    def _borrow_with_drafts(self, count):
        """Mượn `count` hàng PLANNED (hermetic, theo thứ tự matrix) và
        viết draft đạt gate cho mỗi hàng."""
        borrow_planned_row(self.fx, count=count)
        rows = planned_rows(self.fx)
        self.assertGreaterEqual(len(rows), count)
        chosen = rows[:count]
        for row in chosen:
            make_draft(self.fx, row)
        return chosen

    def _set_status(self, ids, status):
        rows = matrix_rows(self.fx)
        for r in rows:
            if r['id'] in set(ids):
                r['status'] = status
        save_matrix(self.fx, rows)

    def _select_added(self, rows, **kw):
        return selection(self.fx, added=[draft_rel(r) for r in rows], **kw)

    # --------------------------------------------- queue 2..10 + pairs

    def test_01_two_drafts_pass_selection(self):
        rows = self._borrow_with_drafts(2)
        ids = [r['id'] for r in rows]
        rc, sel = self._select_added(rows)
        self.assertEqual(rc, 0)
        self.assertTrue(sel['proceed'])
        self.assertEqual(sel['mode'], 'new')
        self.assertEqual(sel['queue'], ids)
        self.assertEqual(sel['claim_ids'], ids)
        self.assertEqual(sel['qa_ids'], ids)
        self.assertEqual(sel['pairs'], 1)
        self.assertIsNone(sel['refuse'])

    def test_02_four_drafts_two_pairs(self):
        rows = self._borrow_with_drafts(4)
        rc, sel = self._select_added(rows)
        self.assertTrue(sel['proceed'])
        self.assertEqual(len(sel['queue']), 4)
        self.assertEqual(sel['pairs'], 2)

    def test_03_six_drafts_three_pairs(self):
        rows = self._borrow_with_drafts(6)
        rc, sel = self._select_added(rows)
        self.assertEqual(len(sel['queue']), 6)
        self.assertEqual(sel['pairs'], 3)

    def test_04_eight_drafts_four_pairs(self):
        rows = self._borrow_with_drafts(8)
        rc, sel = self._select_added(rows)
        self.assertEqual(len(sel['queue']), 8)
        self.assertEqual(sel['pairs'], 4)

    def test_05_ten_drafts_five_pairs(self):
        rows = self._borrow_with_drafts(10)
        rc, sel = self._select_added(rows)
        self.assertEqual(len(sel['queue']), 10)
        self.assertEqual(sel['pairs'], 5)

    def test_06_eleven_drafts_refused(self):
        rows = self._borrow_with_drafts(11)
        rc, sel = self._select_added(rows, rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('toi da 10', sel['refuse'])

    # hợp đồng hiện tại cho phép queue LẺ (pair cuối 1 ID) — không có
    # min 2: push 1 draft cũng hợp lệ (port đúng inline cũ)
    def test_07_three_drafts_two_pairs(self):
        rows = self._borrow_with_drafts(3)
        rc, sel = self._select_added(rows)
        self.assertEqual(len(sel['queue']), 3)
        self.assertEqual(sel['pairs'], 2)

    def test_08_five_drafts_three_pairs(self):
        rows = self._borrow_with_drafts(5)
        rc, sel = self._select_added(rows)
        self.assertEqual(len(sel['queue']), 5)
        self.assertEqual(sel['pairs'], 3)

    def test_09_nine_drafts_five_pairs(self):
        rows = self._borrow_with_drafts(9)
        rc, sel = self._select_added(rows)
        self.assertEqual(len(sel['queue']), 9)
        self.assertEqual(sel['pairs'], 5)

    def test_10_single_draft_allowed(self):
        rows = self._borrow_with_drafts(1)
        rc, sel = self._select_added(rows)
        self.assertTrue(sel['proceed'])
        self.assertEqual(len(sel['queue']), 1)
        self.assertEqual(sel['pairs'], 1)

    # ---------------------------------------------------- refuse gates

    def test_11_duplicate_id_refused(self):
        rows = self._borrow_with_drafts(1)
        p = draft_rel(rows[0])
        # cùng draft xuất hiện ở CẢ added lẫn modified -> trùng ID
        rc, sel = selection(self.fx, added=[p], modified=[p], rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('id trung nhau trong cung mot push', sel['refuse'])

    def test_12_two_files_same_id_refused(self):
        rows = self._borrow_with_drafts(1)
        src = os.path.join(self.fx, draft_rel(rows[0]))
        dup = os.path.join(self.fx, '_drafts/2026-09-28-zz-dup-test.md')
        with open(src, encoding='utf-8') as f:
            content = f.read()
        with open(dup, 'w', encoding='utf-8') as f:
            f.write(content)  # cùng article_id, tên file khác
        rc, sel = selection(
            self.fx, added=[draft_rel(rows[0]),
                            '_drafts/2026-09-28-zz-dup-test.md'],
            rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('id trung nhau trong cung mot push', sel['refuse'])

    def test_13_missing_article_id_refused(self):
        rows = self._borrow_with_drafts(1)
        p = os.path.join(self.fx, draft_rel(rows[0]))
        with open(p, encoding='utf-8') as f:
            lines = f.read().splitlines()
        kept = [l for l in lines if not l.startswith('article_id:')]
        with open(p, 'w', encoding='utf-8') as f:
            f.write('\n'.join(kept) + '\n')
        rc, sel = self._select_added(rows, rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('thieu article_id', sel['refuse'])

    def test_14_unknown_id_refused(self):
        p = os.path.join(self.fx, '_drafts/2026-09-28-zz-id-la.md')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('---\ntitle: "Test ID la"\narticle_id: BLG-99999\n'
                    '---\n\nNoi dung test.\n')
        rc, sel = selection(self.fx, added=['_drafts/2026-09-28-zz-id-la.md'],
                            rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('id khong co trong matrix', sel['refuse'])

    def _refused_locked_status(self, status):
        rows = self._borrow_with_drafts(1)
        aid = rows[0]['id']
        self._set_status([aid], status)
        rc, sel = self._select_added(rows, rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('id da xong/khoa, khong duoc sua lai', sel['refuse'])
        self.assertIn(aid, sel['refuse'])

    def test_15_published_refused(self):
        self._refused_locked_status('PUBLISHED')

    def test_16_existing_refused(self):
        self._refused_locked_status('EXISTING')

    def test_17_blocked_refused(self):
        self._refused_locked_status('BLOCKED')

    # ---------------------------------------------- mode new / repair

    def test_18_repair_push_no_new_claim(self):
        rows = self._borrow_with_drafts(2)
        ids = [r['id'] for r in rows]
        self._set_status(ids, 'REPAIR')
        rc, sel = self._select_added(rows)
        self.assertTrue(sel['proceed'])
        self.assertEqual(sel['mode'], 'repair')
        self.assertEqual(sel['queue'], ids)
        self.assertEqual(sel['claim_ids'], [],
                         'repair KHÔNG claim lại từ đầu')
        self.assertEqual(sel['pairs'], 1)

    def test_19_mixed_new_and_repair_mode_new(self):
        """Semantics hiện tại: push trộn bài mới + repair được phép —
        mode=new, claim CHỈ hàng PLANNED của queue (consume chia pair
        và claim đúng subset PLANNED từng pair)."""
        rows = self._borrow_with_drafts(2)
        ids = [r['id'] for r in rows]
        self._set_status([ids[1]], 'REPAIR')
        rc, sel = self._select_added(rows)
        self.assertTrue(sel['proceed'])
        self.assertEqual(sel['mode'], 'new')
        self.assertEqual(sel['queue'], ids)
        self.assertEqual(sel['claim_ids'], [ids[0]])

    # ------------------------------------- production-control paused

    def test_20_control_disabled_stops_before_claim(self):
        rows = self._borrow_with_drafts(2)
        before = len(planned_rows(self.fx))
        write_json(self.fx, 'data/factory/production-control.json',
                   {'enabled': False, 'chunk_size': 2})
        rc, sel = self._select_added(rows)
        self.assertEqual(rc, 0, 'paused phải exit sạch, KHÔNG refuse')
        self.assertFalse(sel['proceed'])
        self.assertEqual(sel['mode'], 'paused')
        self.assertEqual(sel['queue'], [])
        # dừng TRƯỚC claim: không hàng nào rời PLANNED
        self.assertEqual(len(planned_rows(self.fx)), before)

    def test_21_control_disabled_repair_still_allowed(self):
        rows = self._borrow_with_drafts(2)
        ids = [r['id'] for r in rows]
        self._set_status(ids, 'REPAIR')
        write_json(self.fx, 'data/factory/production-control.json',
                   {'enabled': False, 'chunk_size': 2})
        rc, sel = self._select_added(rows)
        self.assertTrue(sel['proceed'])
        self.assertEqual(sel['mode'], 'repair')
        self.assertEqual(sel['queue'], ids)

    # --------------------------------------------------- no-op / misc

    def test_22_noop_when_no_draft(self):
        rc, sel = selection(self.fx, added=(), modified=())
        self.assertEqual(rc, 0)
        self.assertFalse(sel['proceed'])
        self.assertEqual(sel['mode'], 'skip')
        self.assertEqual(sel['queue'], [])

    def test_23_template_draft_ignored(self):
        p = os.path.join(self.fx, '_drafts/2026-01-01-%s.md' % TPL_SLUG)
        with open(p, 'w', encoding='utf-8') as f:
            f.write('---\ntitle: "Mau"\narticle_id: BLG-00001\n---\n')
        rc, sel = selection(
            self.fx, added=['_drafts/2026-01-01-%s.md' % TPL_SLUG])
        self.assertEqual(rc, 0)
        self.assertFalse(sel['proceed'])
        self.assertEqual(sel['mode'], 'skip',
                         'template phải bị loại, KHÔNG vào queue')

    def test_24_deterministic_matrix_order(self):
        """Queue sắp theo THỨ TỰ MATRIX — KHÔNG theo thứ tự file push."""
        rows = self._borrow_with_drafts(4)
        matrix_ids = [r['id'] for r in rows]
        added_reversed = [draft_rel(r) for r in reversed(rows)]
        rc, sel = selection(self.fx, added=added_reversed)
        self.assertTrue(sel['proceed'])
        self.assertEqual(sel['queue'], matrix_ids)
        self.assertNotEqual(added_reversed, sel['queue'])

    def test_25_selector_does_not_mutate_state(self):
        rows = self._borrow_with_drafts(2)
        watched = ['data/content-matrix.csv', 'data/state/checkpoint.json',
                   'data/factory/production-control.json',
                   'data/state/transaction.json']
        before = {rel: _file_hash(os.path.join(self.fx, rel))
                  for rel in watched}
        drafts_before = sorted(os.listdir(os.path.join(self.fx, '_drafts')))
        rc, sel = self._select_added(rows)
        self.assertTrue(sel['proceed'])
        for rel in watched:
            self.assertEqual(_file_hash(os.path.join(self.fx, rel)),
                             before[rel],
                             'selector KHÔNG được mutate %s' % rel)
        self.assertEqual(
            sorted(os.listdir(os.path.join(self.fx, '_drafts'))),
            drafts_before, 'selector KHÔNG được đụng draft')

    def test_26_github_output_contract(self):
        """Workflow đọc step outputs: selector phải ghi queue/mode/pairs
        vào $GITHUB_OUTPUT khi biến này tồn tại (Actions); KHÔNG có biến
        thì stdout JSON vẫn là kết quả đầy đủ."""
        rows = self._borrow_with_drafts(3)
        gout = os.path.join(self.fx, 'tmp-gh-output.txt')
        env = dict(os.environ, GITHUB_OUTPUT=gout)
        rc, sel = self._select_added(rows, env=env)
        self.assertTrue(sel['proceed'])
        with open(gout, encoding='utf-8') as f:
            out = f.read()
        ids = ','.join(r['id'] for r in rows)
        self.assertIn('queue=%s\n' % ids, out)
        self.assertIn('mode=new\n', out)
        self.assertIn('pairs=2\n', out)

    # ------------------------------- engine guard fail-closed (op level)

    def test_27_active_txn_fail_closed(self):
        """Guard fail-closed của đường nóng: transaction active còn
        tồn tại -> prepare-next TỪ CHỐI claim (workflow guard chặn
        TRƯỚC khi consume; đây chứng minh engine cũng fail-closed)."""
        rows = self._borrow_with_drafts(1)
        aid = rows[0]['id']
        tp = os.path.join(self.fx, 'data/state/transaction.json')
        txn = json.load(open(tp, encoding='utf-8'))
        txn['active'] = True
        txn['pending'] = {'step': 'promote %s' % aid}
        json.dump(txn, open(tp, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        rc, sel = self._select_added(rows)
        self.assertEqual(sel['mode'], 'new')
        r = self.operator('prepare-next', '--ids', aid, '--scope', 'fast')
        self.assertNotEqual(r.returncode, 0,
                            'txn active mà vẫn claim = fail-open BUG')
        self.assertEqual(writing_rows(self.fx), [])

    def test_28_writer_lock_fail_closed(self):
        rows = self._borrow_with_drafts(1)
        aid = rows[0]['id']
        sentinel = os.path.join(self.fx, 'data/state/writer-lock.active')
        with open(sentinel, 'w', encoding='utf-8') as f:
            f.write('token-khac-000')
        lp = os.path.join(self.fx, 'data/state/writer-lock.json')
        meta = json.load(open(lp, encoding='utf-8')) if os.path.exists(lp) \
            else {}
        meta.update({'locked': True, 'holder': 'writer-khac',
                     'token': 'token-khac-000'})
        json.dump(meta, open(lp, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        r = self.operator('prepare-next', '--ids', aid, '--scope', 'fast')
        self.assertNotEqual(r.returncode, 0,
                            'lock của writer khác mà vẫn claim = '
                            'fail-open BUG')
        self.assertIn('writer-lock', r.stdout + r.stderr)
        self.assertEqual(writing_rows(self.fx), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
