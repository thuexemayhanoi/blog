#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test đường nóng PUSH factory — push-selection.py + chuỗi
prepare-next --ids / qa --ids / publish --ids trên FIXTURE.

LƯU Ý kiến trúc (hợp đồng 6 workflow — docs/PROC-PUBLISH.md): đường nóng
sản xuất hiện là factory-publish.yml với inline selection (turbo queue
2..10 draft/push, consume pair 2); push-selection.py là TOOLING
REGRESSION chunk_size=2 — bộ test này chặt đúng semantics của tooling
đó (exact-ID, refuse, backlog, repair), KHÔNG mô phỏng queue 2..10 của
workflow. BO TEST NAY KHÔNG viết bài thật: mọi mutation
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
                            make_draft, matrix_rows, save_matrix,
                            write_json)

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
        # hermetic: ÉP fixture về đúng tiền đề PLANNED=0 — repo thật có
        # thể đã có hàng PLANNED lúc chép (snapshot drift, vd 20 hàng
        # refill-2026-09-30); test KHÔNG được phụ thuộc trạng thái sản
        # xuất thật. Hàng PLANNED fixture -> BLOCKED (được bảo vệ, không
        # claim được) + đồng bộ checkpoint counts cho validate khớp.
        rows = matrix_rows(self.fx)
        n_planned = sum(1 for r in rows if r['status'] == 'PLANNED')
        if n_planned:
            for r in rows:
                if r['status'] == 'PLANNED':
                    r['status'] = 'BLOCKED'
                    r['notes'] = (r['notes'] + ' | ' if r['notes'] else '') \
                        + 'fixture test_7: ép planned=0 (hermetic)'
            save_matrix(self.fx, rows)
            cp = cp_json(self.fx, 'data/state/checkpoint.json')
            cp['counts']['planned'] = 0
            cp['counts']['blocked'] = int(cp['counts'].get('blocked', 0)) \
                + n_planned
            write_json(self.fx, 'data/state/checkpoint.json', cp)
        self.assertEqual(len(planned_rows(self.fx)), 0)
        before = open(os.path.join(self.fx, 'data/content-matrix.csv'),
                      'rb').read()
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
        # NO DRAFT BACKLOG: bài PASS phải được publish NGAY trong cùng
        # vòng (workflow chỉ publish PASS_IDS từ qa-outcome), bài REPAIR
        # giữ nguyên là mục tiêu repair duy nhất
        r = self.operator('publish', '--ids', unrelated, '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        self.assertEqual(by_id[unrelated]['status'], 'PUBLISHED')
        self.assertEqual(by_id[target]['status'], 'REPAIR')
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
        self.assertEqual(by_id[unrelated]['status'], 'PUBLISHED')

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




class BacklogSelectionTest(FxTestCase):
    """Kịch bản 11-15: BACKLOG recovery (mô hình /vanchinh, 2026-10-01).

    Đây là semantics của TOOLING push-selection.py (chunk_size=2) —
    factory-publish.yml trên production chọn queue theo push hiện tại
    (2..10, pair 2) và KHÔNG quét backlog toàn `_drafts/`.

    Pipeline trước chết trước claim/QA/publish để draft HỢP LỆ sót trong
    `_drafts/` cho hàng PLANNED/WRITING/QA/REPAIR/PASS. Selection phải:
    - phát hiện EXACT các ID có draft thật (tối đa chunk_size, REPAIRABLE
      trước rồi PLANNED, theo article_id)
    - KHÔNG BAO GIỜ claim hàng PLANNED không có draft
    - backlog CÓ ƯU TIÊN hơn bài mới (draft vừa push được hoãn,
      KHÔNG mất, tự thành backlog ở lần chạy kế tiếp)
    - draft sót KHÔNG hợp lệ bị bỏ qua — KHÔNG chặn publish
    - KHÔNG BAO GIỜ đụng hàng PUBLISHED.
    """

    def _borrow(self, count):
        """Mượn `count` hàng PLANNED (hermetic, no-op khi repo còn dư) và
        trả về ĐÚNG `count` hàng đầu theo article_id — KHÔNG dùng cả
        40 hàng PLANNED thật của fixture."""
        borrow_planned_row(self.fx, count=count)
        rows = sorted(planned_rows(self.fx), key=lambda r: r['id'])
        self.assertGreaterEqual(len(rows), count)
        return rows[:count]

    def _stranded(self, rows):
        """Tạo draft 'sót' (không push) cho các hàng cho trước."""
        for row in rows:
            make_draft(self.fx, row)
        return sorted(r['id'] for r in rows)

    def _ops(self, sel):
        """Chạy ĐÚNG chuỗi op của đường nóng factory-publish.yml sau
        selection:
        claim CHỈ claim_ids (prepare-next), QA/publish qa_ids, publish
        chỉ hàng PASS trong qa-outcome (A PASS + B REPAIR: publish A)."""
        if sel['claim_ids']:
            joined = ','.join(sel['claim_ids'])
            r = self.operator('prepare-next', '--ids', joined,
                              '--scope', 'fast')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(sel['qa_ids'])
        joined = ','.join(sel['qa_ids'])
        r = self.operator('qa', '--ids', joined, '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        oc = json.load(open(os.path.join(self.fx, 'reports/factory',
                                         'qa-outcome.json'),
                            encoding='utf-8'))
        passed = sorted(i for i, v in oc.get('outcomes', {}).items()
                        if v == 'PASS')
        self.assertEqual(passed, sorted(sel['qa_ids']),
                         'draft mẫu đạt gate phải PASS hết')
        r = self.operator('publish', '--ids', ','.join(passed),
                          '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PUBLISHED', r.stdout)

    # ------------------- 11. backlog có ưu tiên hơn bài mới

    def test_11_backlog_priority_over_new_push(self):
        # pipeline trước chết: draft A,B sót (hàng PLANNED còn nguyên)
        rows = self._borrow(4)
        stranded_ids = self._stranded(rows[:2])
        # writer push cặp mới C,D (hợp lệ)
        fresh = rows[2:]
        for row in fresh:
            make_draft(self.fx, row)
        fresh_ids = sorted(r['id'] for r in fresh)
        rc, sel = selection(self.fx, added=[draft_rel(r) for r in fresh])
        self.assertEqual(sel['mode'], 'backlog')
        self.assertTrue(sel['proceed'])
        self.assertEqual(sel['claim_ids'], stranded_ids)
        self.assertEqual(sel['qa_ids'], stranded_ids)
        self.assertEqual(sel['deferred_pushed_ids'], fresh_ids)
        self.assertEqual(sorted(sel['backlog_ids']), stranded_ids)
        # chuỗi tự lành: hot path hoàn tất backlog; cặp vừa push trở
        # thành backlog của lần chạy kế tiếp (KHÔNG yêu cầu writer
        # viết lại draft đã push)
        self._ops(sel)
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        for aid in stranded_ids:
            self.assertEqual(by_id[aid]['status'], 'PUBLISHED')
        for aid in fresh_ids:
            self.assertEqual(by_id[aid]['status'], 'PLANNED',
                            'draft hoãn KHÔNG bị claim oan')
            self.assertTrue(os.path.exists(
                os.path.join(self.fx, draft_rel(by_id[aid]))),
                            'draft hoãn KHÔNG mất — KHÔNG yêu cầu writer '
                            'viết lại draft đã push')
        # lần chạy kế tiếp (push rỗng — như commit promote re-trigger):
        # backlog pick đúng cặp bị hoãn
        rc, sel2 = selection(self.fx)
        self.assertEqual(sel2['mode'], 'backlog')
        self.assertEqual(sel2['claim_ids'], fresh_ids)
        self.assertEqual(sel2['qa_ids'], fresh_ids)
        self.assertEqual(sel2['deferred_pushed_ids'], [])
        self._ops(sel2)
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        for aid in fresh_ids:
            self.assertEqual(by_id[aid]['status'], 'PUBLISHED')

    # ------------------- 12. backlog cap chunk_size, thứ tự deterministic

    def test_12_backlog_cap_chunk_size(self):
        rows = self._borrow(3)
        ids = self._stranded(rows)
        rc, sel = selection(self.fx)  # push rỗng (vd commit promote)
        self.assertEqual(sel['mode'], 'backlog')
        self.assertTrue(sel['proceed'])
        self.assertEqual(len(sel['qa_ids']), 2,
                         'backlog tối đa chunk_size = 2 mỗi lần chạy')
        self.assertEqual(sel['qa_ids'], ids[:2])
        self.assertEqual(sel['claim_ids'], ids[:2])
        self.assertEqual(sorted(sel['backlog_ids']), ids)
        # KHÔNG claim hàng PLANNED không có draft
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        for aid in sel['claim_ids']:
            self.assertTrue(os.path.exists(
                os.path.join(self.fx, draft_rel(by_id[aid]))),
                '%s bị claim nhưng KHÔNG có draft thật' % aid)

    # ------------------- 13. việc dở REPAIRABLE trước hàng PLANNED

    def test_13_backlog_repairable_first(self):
        rows = self._borrow(3)
        # hàng dở: claim rồi (WRITING) nhưng pipeline chết trước QA
        w = rows[0]
        make_draft(self.fx, w)
        r = self.operator('prepare-next', '--ids', w['id'], '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([x['id'] for x in writing_rows(self.fx)], [w['id']])
        # 2 hàng PLANNED khác cũng có draft sót
        p_ids = self._stranded(rows[1:])
        rc, sel = selection(self.fx)
        self.assertEqual(sel['mode'], 'backlog')
        self.assertTrue(sel['proceed'])
        # REPAIRABLE (WRITING) trước — engine resume-first: còn việc dở
        # thì chunk CHỈ chứa hàng dở (prepare-next TỪ CHỐI claim mới khi
        # còn WRITING/QA/REPAIR/PASS); hàng PLANNED sót đợi lần kế tiếp
        self.assertEqual(sel['qa_ids'], [w['id']])
        self.assertEqual(sel['claim_ids'], [],
                         'còn hàng WRITING chưa xong — KHÔNG claim mới')
        # hot path: QA/publish đúng hàng dở; 2 hàng PLANNED có draft sót
        # KHÔNG bị đụng (đợi lần sau)
        self._ops(sel)
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        self.assertEqual(by_id[w['id']]['status'], 'PUBLISHED')
        self.assertEqual(by_id[p_ids[0]]['status'], 'PLANNED')
        self.assertEqual(by_id[p_ids[1]]['status'], 'PLANNED')
        # lần chạy kế tiếp (không còn việc dở): backlog pick 2 hàng
        # PLANNED sót theo article_id, cap chunk_size
        rc, sel2 = selection(self.fx)
        self.assertEqual(sel2['mode'], 'backlog')
        self.assertEqual(sel2['claim_ids'], p_ids)
        self.assertEqual(sel2['qa_ids'], p_ids)
        self._ops(sel2)
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        for aid in p_ids:
            self.assertEqual(by_id[aid]['status'], 'PUBLISHED')

    # ------------------- 14. draft sót không hợp lệ bị BỎ QUA

    def test_14_backlog_ignores_invalid_stranded_drafts(self):
        rows = self._borrow(2)
        good, other = rows
        make_draft(self.fx, good)
        drafts = os.path.join(self.fx, '_drafts')
        # (a) file không phải draft factory (mẫu nháp — thiếu article_id).
        # Ten file co y KHONG trung slug cua template that: scripts/
        # KHONG nam trong exclude cua _config.yml nen Jekyll copy file
        # test nay vao _site - quality gate draft-leak grep slug cua
        # template tren TOAN BO _site, file test khong duoc chua slug do.
        with open(os.path.join(drafts, '2026-01-01-mau-nhap-khong-xuat-ban.md'),
                  'w', encoding='utf-8') as f:
            f.write('---\ntitle: "MẪU NHÁP — không xuất bản"\n---\n\n'
                    'nội dung mẫu, không có article_id.\n')
        # (b) draft có article_id hợp lệ nhưng SAI tên slug — không chọn
        other_slug = other['output_path'][len('_posts/{date}-'):-3]
        with open(os.path.join(drafts, '2026-09-28-sai-ten-%s.md' % other_slug),
                  'w', encoding='utf-8') as f:
            f.write('---\ntitle: "sai tên"\narticle_id: %s\n---\n'
                    'nội dung.\n' % other['id'])
        # (c) draft sót trỏ ID đã PUBLISHED — bỏ qua, KHÔNG ghi đè
        pub = next(r for r in matrix_rows(self.fx)
                   if r['status'] == 'PUBLISHED')
        pub_slug = pub['output_path']
        pub_slug = pub_slug[len('_posts/{date}-'):-3] \
            if pub_slug.startswith('_posts/{date}-') else \
            pub_slug[len('_posts/'):-3][pub_slug[len('_posts/'):-3].index('-') + 1:]
        with open(os.path.join(drafts,
                               '2026-09-28-%s.md' % pub_slug),
                  'w', encoding='utf-8') as f:
            f.write('---\ntitle: "ghi đè?"\narticle_id: %s\n---\n'
                    'nội dung.\n' % pub['id'])
        rc, sel = selection(self.fx)
        self.assertEqual(sel['mode'], 'backlog')
        self.assertEqual(sel['qa_ids'], [good['id']],
                         'chỉ draft hợp lệ được chọn; draft lỗi bị bỏ qua, '
                         'KHÔNG refuse')
        self.assertEqual(sel['claim_ids'], [good['id']])
        self.assertEqual(sel['refuse'], None)
        # hàng PUBLISHED KHÔNG bị đụng
        by_id = {x['id']: x for x in matrix_rows(self.fx)}
        self.assertEqual(by_id[pub['id']]['status'], 'PUBLISHED')

    # ------------------- 15. control=false: backlog PLANNED dừng sạch

    def test_15_backlog_paused_when_control_disabled(self):
        row = self._borrow(1)[0]
        make_draft(self.fx, row)
        cp = 'data/factory/production-control.json'
        ctl = json.load(open(os.path.join(self.fx, cp), encoding='utf-8'))
        ctl['enabled'] = False
        write_json(self.fx, cp, ctl)
        # push rỗng + backlog toàn PLANNED -> paused (KHÔNG claim khi tắt)
        rc, sel = selection(self.fx)
        self.assertEqual(sel['mode'], 'paused')
        self.assertFalse(sel['proceed'])
        self.assertEqual(sel['claim_ids'], [])
        self.assertEqual([x['id'] for x in writing_rows(self.fx)], [],
                          'enabled=false mà vẫn claim = fail-open BUG')
        # enabled=false: prepare-next (claim mới) phải dừng sạch
        r = self.operator('prepare-next', '--ids', row['id'],
                          '--scope', 'fast')
        self.assertNotEqual(r.returncode, 0,
                            'prepare-next phải dừng khi enabled=false')
        # enabled=false + hàng dở REPAIRABLE có draft: QA/publish việc
        # dở vẫn hợp lệ (repair không bị chặn)
        ctl['enabled'] = True
        write_json(self.fx, cp, ctl)
        r = self.operator('prepare-next', '--ids', row['id'],
                          '--scope', 'fast')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ctl['enabled'] = False
        write_json(self.fx, cp, ctl)
        rc, sel2 = selection(self.fx)
        self.assertEqual(sel2['mode'], 'backlog')
        self.assertTrue(sel2['proceed'])
        self.assertEqual(sel2['claim_ids'], [],
                          'enabled=false KHÔNG claim, chỉ QA/publish dở')
        self.assertEqual(sel2['qa_ids'], [row['id']])


if __name__ == '__main__':
    unittest.main(verbosity=2)
