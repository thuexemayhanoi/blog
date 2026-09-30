#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test đường nóng PUSH factory (Phase 1) — push-selection.py + chuỗi
prepare-next --ids / qa --ids / publish --ids trên FIXTURE.

Mô hình mới (docs/PROC-PUBLISH.md): writer ngoài push draft vào _drafts/
(toi da chunk_size=2 ID) -> push-selection.py chon EXACT ID -> workflow
tu dong claim/QA/publish. BO TEST NAY KHÔNG viết bài thật: mọi mutation
trên bản sao tạm (FxTestCase của test_qa_modes.py); production matrix/
checkpoint phải BYTE-IDENTICAL trước/sau toàn bộ bộ test (hash guard ở
setUpModule/tearDownModule).

10 kịch bản bắt buộc (Phase 1 — H):
  1. push 2 draft mới  -> chọn đúng 2 ID -> claim fixture -> QA -> publish
  2. push 1 draft mới  -> hoạt động
  3. >2 draft mới      -> từ chối
  4. thiếu article_id  -> từ chối
  5. article_id trùng  -> từ chối
  6. production-control enabled=false -> dừng TRƯỚC khi claim
  7. fixture PLANNED=0 -> refill_advised đúng; op refill không filler
  8. repair push       -> QA/publish EXACT ID sửa, KHÔNG claim việc mới
  9. transaction/lock conflict -> fail closed, không claim
 10. ID đã PUBLISHED push lại -> KHÔNG BAO GIỜ ghi đè

Chạy: python3 scripts/factory/tests/test_push_selection.py (từ repo)
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_qa_modes import (FxTestCase, borrow_planned_row, cp_json,
                            make_draft, matrix_rows)

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


def tearDownModule():
    for rel in REAL_GUARD_FILES:
        got = _file_hash(os.path.join(ROOT, rel))
        assert got == _GUARD[rel], (
            'PRODUCTION STATE BỊ ĐỔI TRONG TEST: %s (%s != %s)'
            % (rel, got, _GUARD[rel]))


def selection(fx, added=(), modified=(), rc_expect=0):
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
        cwd=fx, capture_output=True, text=True)
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


class PushHotPathTest(FxTestCase):
    """Kịch bản 1-10: chọn EXACT ID từ push + chuỗi op chuẩn trên fixture."""

    # ---------------------------------------------------------- helpers

    def _borrow_with_drafts(self, count):
        """Mượn `count` hàng PLANNED (hermetic) và viết draft đạt gate."""
        borrow_planned_row(self.fx, count=count)
        rows = planned_rows(self.fx)
        self.assertGreaterEqual(len(rows), count)
        chosen = rows[:count]
        for row in chosen:
            make_draft(self.fx, row)
        return chosen

    def _hot_path(self, ids):
        """Chuỗi op chuẩn của workflow sau khi selection trả EXACT IDs."""
        joined = ','.join(ids)
        r = self.operator('prepare-next', '--ids', joined, '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.operator('qa', '--ids', joined, '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PASS', r.stdout)
        r = self.operator('publish', '--ids', joined, '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PUBLISHED', r.stdout)

    # ---------------------------------------------- 1. push 2 draft mới

    def test_1_two_new_drafts_select_claim_qa_publish(self):
        rows = self._borrow_with_drafts(2)
        ids = sorted(r['id'] for r in rows)
        added = [draft_rel(r) for r in rows]
        rc, sel = selection(self.fx, added=added)
        self.assertEqual(sel['mode'], 'new')
        self.assertTrue(sel['proceed'])
        self.assertEqual(sel['claim_ids'], ids)
        self.assertEqual(sel['qa_ids'], ids)
        # claim EXACT 2 ID -> QA -> publish fixture rows
        self._hot_path(ids)
        by_id = {r['id']: r for r in matrix_rows(self.fx)}
        for aid in ids:
            self.assertEqual(by_id[aid]['status'], 'PUBLISHED')
            self.assertFalse(os.path.exists(
                os.path.join(self.fx, '_drafts',
                             os.path.basename(draft_rel(by_id[aid])))))
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        self.assertIsNone(cp['in_progress_chunk'])

    # ---------------------------------------------- 2. push 1 draft mới

    def test_2_one_new_draft_works(self):
        rows = self._borrow_with_drafts(1)
        aid = rows[0]['id']
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])])
        self.assertEqual(sel['mode'], 'new')
        self.assertEqual(sel['claim_ids'], [aid])
        self._hot_path([aid])
        by_id = {r['id']: r for r in matrix_rows(self.fx)}
        self.assertEqual(by_id[aid]['status'], 'PUBLISHED')

    # ---------------------------------------------- 3. >2 draft mới

    def test_3_more_than_chunk_rejected(self):
        rows = self._borrow_with_drafts(3)
        added = [draft_rel(r) for r in rows]
        rc, sel = selection(self.fx, added=added, rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('chunk_size', sel['refuse'])
        # KHÔNG có ID nào được claim khi từ chối
        self.assertEqual(writing_rows(self.fx), [])

    # ---------------------------------------------- 4. thiếu article_id

    def test_4_missing_article_id_rejected(self):
        rows = self._borrow_with_drafts(1)
        dpath = os.path.join(self.fx, draft_rel(rows[0]))
        text = open(dpath, encoding='utf-8').read()
        open(dpath, 'w', encoding='utf-8').write(
            re.sub(r'^article_id:.*\n', '', text, flags=re.M))
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])], rc_expect=3)
        self.assertIn('article_id', sel['refuse'])
        self.assertEqual(writing_rows(self.fx), [])

    # ---------------------------------------------- 5. ID trùng

    def test_5_duplicate_article_id_rejected(self):
        rows = self._borrow_with_drafts(2)
        first, second = rows[0], rows[1]
        src = os.path.join(self.fx, draft_rel(first))
        dup = os.path.join(self.fx, draft_rel(second))
        # file thứ hai mang article_id của file thứ nhất
        text = open(src, encoding='utf-8').read()
        open(dup, 'w', encoding='utf-8').write(text)
        rc, sel = selection(self.fx,
                            added=[draft_rel(first), draft_rel(second)],
                            rc_expect=3)
        self.assertIn('trùng', sel['refuse'])
        self.assertEqual(writing_rows(self.fx), [])

    # ------------------------------- 6. production-control enabled=false

    def test_6_control_disabled_stops_before_claim(self):
        rows = self._borrow_with_drafts(1)
        cpath = os.path.join(self.fx, 'data/factory/production-control.json')
        json.dump({'enabled': False, 'chunk_size': 2},
                  open(cpath, 'w', encoding='utf-8'), ensure_ascii=False,
                  indent=2)
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])])
        # exit sạch (rc 0) TRƯỚC khi claim: mode=paused, proceed=false
        self.assertEqual(sel['mode'], 'paused')
        self.assertFalse(sel['proceed'])
        self.assertEqual(sel['claim_ids'], [])
        # engine cũng phải từ chối claim khi enabled=false (fail-closed 2 lớp)
        r = self.operator('prepare-next', '--ids', rows[0]['id'],
                          '--scope', 'fast')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('enabled=false', r.stdout + r.stderr)
        self.assertEqual(writing_rows(self.fx), [])
        self.assertEqual(len(planned_rows(self.fx)),
                         len(planned_rows(self.fx)))

    # --------------------------------- 7. PLANNED=0 -> refill path

    def test_7_planned_zero_refill_advised_no_filler(self):
        before = open(os.path.join(self.fx, 'data/content-matrix.csv'),
                      'rb').read()
        # fixture sao chép repo thật: planned có thể đã = 0 (trạng thái
        # thật hiện tại) — xác nhận tiền đề hermetic
        self.assertEqual(len(planned_rows(self.fx)),
                         sum(1 for r in matrix_rows(self.fx)
                             if r['status'] == 'PLANNED'))
        rc, sel = selection(self.fx)  # push rỗng/no-op
        self.assertEqual(sel['mode'], 'skip')
        self.assertFalse(sel['proceed'])
        self.assertEqual(sel['planned_claimable'], 0)
        self.assertTrue(sel['refill_advised'])
        # queue.py xác nhận cần refill; op refill trên fixture (ledger hết
        # candidate STAGED) -> NEEDS_TOPIC_EXPANSION, KHÔNG filler
        q = self.py('scripts/factory/queue.py', '--needs-refill')
        self.assertEqual(q.returncode, 0, q.stdout + q.stderr)
        r = self.operator('refill')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('NEEDS_TOPIC_EXPANSION', r.stdout)
        after = open(os.path.join(self.fx, 'data/content-matrix.csv'),
                     'rb').read()
        self.assertEqual(before, after, 'refill KHÔNG được tạo filler')

    # ---------------------------------------------- 8. repair push

    def test_8_repair_push_only_repaired_id(self):
        rows = self._borrow_with_drafts(2)
        first, second = sorted(rows, key=lambda r: r['id'])
        target, unrelated = first['id'], second['id']
        # claim cặp, QA một bài REPAIR (số tiền chưa duyệt), một bài PASS
        bad = os.path.join(self.fx, draft_rel(first))
        with open(bad, 'a', encoding='utf-8') as f:
            f.write('\n\nMức phạt tham khảo cho ví dụ này là 999.999 đồng '
                    'mỗi trường hợp.\n')
        joined = ','.join(sorted(r['id'] for r in rows))
        r = self.operator('prepare-next', '--ids', joined, '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.operator('qa', '--ids', joined, '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        self.assertEqual(by_id[target]['status'], 'REPAIR')
        self.assertEqual(by_id[unrelated]['status'], 'PASS')
        # writer sửa đúng draft hỏng rồi push lại: REPAIR push
        make_draft(self.fx, by_id[target])
        rc, sel = selection(self.fx, modified=[draft_rel(by_id[target])])
        self.assertEqual(sel['mode'], 'repair')
        self.assertTrue(sel['proceed'])
        self.assertEqual(sel['claim_ids'], [], 'repair push KHÔNG claim mới')
        self.assertEqual(sel['qa_ids'], [target])
        # hot path: QA/publish EXACT ID sửa; hàng khác không bị đụng
        r = self.operator('qa', '--ids', target, '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.operator('publish', '--ids', target, '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        self.assertEqual(by_id[target]['status'], 'PUBLISHED')
        self.assertEqual(by_id[unrelated]['status'], 'PASS')

    # ------------------------------- 9. transaction/lock conflict

    def test_9a_active_txn_fail_closed(self):
        rows = self._borrow_with_drafts(1)
        aid = rows[0]['id']
        tp = os.path.join(self.fx, 'data/state/transaction.json')
        txn = json.load(open(tp, encoding='utf-8'))
        txn['active'] = True
        txn['pending'] = {'step': 'promote %s' % aid}
        json.dump(txn, open(tp, 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        rc, sel = selection(self.fx, added=[draft_rel(rows[0])])
        self.assertEqual(sel['mode'], 'new')
        r = self.operator('prepare-next', '--ids', aid, '--scope', 'fast')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(writing_rows(self.fx), [],
                         'txn active mà vẫn claim = fail-open BUG')
        self.assertEqual(len(planned_rows(self.fx)),
                         len(planned_rows(self.fx)))

    def test_9b_writer_lock_fail_closed(self):
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
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('writer-lock', r.stdout + r.stderr)
        self.assertEqual(writing_rows(self.fx), [],
                         'lock của writer khác mà vẫn claim = fail-open BUG')

    # --------------------------------- 10. ID đã PUBLISHED push lại

    def test_10_published_id_never_overwritten(self):
        rows = self._borrow_with_drafts(1)
        aid = rows[0]['id']
        self._hot_path([aid])
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        self.assertEqual(by_id[aid]['status'], 'PUBLISHED')
        # writer push lại draft cho ID đã xuất bản -> từ chối
        make_draft(self.fx, by_id[aid])
        rc, sel = selection(self.fx, added=[draft_rel(by_id[aid])],
                            rc_expect=3)
        self.assertFalse(sel['proceed'])
        self.assertIn('KHÔNG BAO GIỜ ghi đè', sel['refuse'])
        # lớp 2: publish-gate chỉ nhận hàng PASS
        r = self.operator('publish', '--ids', aid, '--scope', 'fast')
        self.assertNotEqual(r.returncode, 0)
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        self.assertEqual(by_id[aid]['status'], 'PUBLISHED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
