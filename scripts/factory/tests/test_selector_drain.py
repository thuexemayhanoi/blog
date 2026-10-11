#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test selector v2 (push-selection.py): DRAIN backlog + ownership theo
session + idempotent re-run + cách ly draft hỏng — fixture NHẸ (LightRepo).

Chứng minh các lỗ hổng đã audit (P0/P1) KHÔNG còn:
  P0-2 lost trigger: run bị GitHub hủy -> draft của push đó VẪN được run
       sau nhặt (backlog drain);
  P1-4 REPAIR ownership: writer khác không sửa được draft REPAIR đang
       thuộc lease sống của writer này;
  P1-2 registry hỏng -> refuse fail-closed (không coi là rỗng);
  P1-10 re-run push cũ (draft đã chuyển _posts/) -> no-op xanh, không RED;
  poison: một draft hỏng/được bảo vệ KHÔNG chặn các draft khác.

Chạy: python3 scripts/factory/tests/test_selector_drain.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_helpers import LightRepo

FUTURE = '2099-01-01T00:00:00Z'


def lease(ids, session=None, writer_claimed='2026-10-11T00:00:00Z'):
    d = {'ids': list(ids), 'claimed_at': writer_claimed,
         'expires_at': FUTURE}
    if session:
        d['session'] = session
        d['epoch'] = 1
        d['heartbeat_at'] = writer_claimed
    return d


class DrainBase(unittest.TestCase):
    def setUp(self):
        self.r = LightRepo(n_planned=200)
        self.addCleanup(self.r.cleanup)

    def sel(self, **kw):
        return self.r.select(**kw)


class TestBacklogDrain(DrainBase):

    def test_01_cancelled_run_drafts_are_picked_up_by_next_run(self):
        """W2 push (run bị hủy) + W3 push (run sống): run của W3 phải
        xử lý cả draft của W2 — không draft nào bị bỏ rơi."""
        ids2 = ['BLG-00011', 'BLG-00012']
        ids3 = ['BLG-00021', 'BLG-00022']
        self.r.registry({'W2': lease(ids2), 'W3': lease(ids3)})
        for a in ids2:
            self.r.draft(a, writer='W2')
        p3 = [self.r.draft(a, writer='W3') for a in ids3]
        # KHÔNG có backlog: hành vi cũ — W2 bị bỏ rơi (tái hiện P0-2)
        _, old, _ = self.sel(added=p3)
        self.assertEqual(old['queue'], ids3)
        # có backlog: nhặt cả W2
        _, new, _ = self.sel(added=p3, backlog=True)
        self.assertEqual(new['queue'], ids2 + ids3)
        self.assertEqual(new['backlog'], ids2)
        self.assertEqual(new['pairs'], 2)
        self.assertEqual(new['writers'],
                         {'BLG-00011': 'W2', 'BLG-00012': 'W2',
                          'BLG-00021': 'W3', 'BLG-00022': 'W3'})

    def test_02_backlog_only_run_from_nudge_trigger(self):
        """Push chỉ đổi `.nudge-W2` (không .md): selector bỏ qua file đó
        nhưng backlog vẫn drain draft đang chờ."""
        ids = ['BLG-00031', 'BLG-00032']
        self.r.registry({'W1': lease(ids)})
        for a in ids:
            self.r.draft(a, writer='W1')
        with open(self.r.path('_drafts/.nudge-W1'), 'w') as f:
            f.write('2026-10-11T00:00:00Z\n')
        _, out, _ = self.sel(added=['_drafts/.nudge-W1'], backlog=True)
        self.assertTrue(out['proceed'])
        self.assertEqual(out['queue'], ids)

    def test_03_queue_capped_at_30_per_run(self):
        ids = ['BLG-%05d' % i for i in range(1, 41)]
        self.r.registry({'W1': lease(ids[:10]), 'W2': lease(ids[10:20]),
                         'W3': lease(ids[20:30])})
        # 40 draft nhưng chỉ 30 ID có lease sống -> 10 bị cách ly
        for a in ids:
            w = 'W1' if a in ids[:10] else 'W2' if a in ids[10:20] else 'W3'
            self.r.draft(a, writer=w)
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(len(out['queue']), 30)
        self.assertEqual(out['queue'], ids[:30])
        self.assertEqual(len(out['quarantine']), 10)

    def test_04_quarantine_never_blocks_valid_drafts(self):
        good = ['BLG-00041', 'BLG-00042']
        self.r.registry({'W1': lease(good)})
        for a in good:
            self.r.draft(a, writer='W1')
        # draft hỏng: thiếu article_id; ID lạ; ID không có lease; REVIEW
        with open(self.r.path('_drafts/2026-10-11-khong-id.md'), 'w') as f:
            f.write('---\ntitle: x\n---\nnoi dung\n')
        self.r.draft('BLG-99999', writer='W1',
                     name='2026-10-11-id-la.md')
        self.r.draft('BLG-00050', writer='W1')          # không lease
        self.r.set_status({'BLG-00051': 'REVIEW'})
        self.r.draft('BLG-00051', writer='W1')
        _, out, _ = self.sel(backlog=True)
        self.assertTrue(out['proceed'], out)
        self.assertEqual(out['queue'], good)
        reasons = ' | '.join(q['reason'] for q in out['quarantine'])
        self.assertIn('thieu article_id', reasons)
        self.assertIn('khong co trong matrix', reasons)
        self.assertIn('khong co lease song', reasons)
        self.assertIn('bao ve', reasons)
        self.assertEqual(len(out['quarantine']), 4)

    def test_05_repair_waits_until_content_changes(self):
        a = 'BLG-00061'
        self.r.registry({'W1': lease([a], session='s-aaa')})
        rel = self.r.draft(a, writer='W1', session='s-aaa')
        self.r.set_status({a: 'REPAIR'})
        self.r.evidence(a, rel, same=True)         # draft chưa đổi từ lần FAIL
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], [])
        self.assertEqual(out['waiting_repair'], [a])
        self.assertEqual(out['mode'], 'skip')
        # writer sửa draft -> hash lệch bằng chứng -> vào queue (mode repair)
        self.r.draft(a, writer='W1', session='s-aaa', body='Da sua noi dung.')
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], [a])
        self.assertEqual(out['mode'], 'repair')
        self.assertEqual(out['claim_ids'], [])

    def test_06_pass_row_waiting_publish_is_drained(self):
        """Pair hỗn hợp để lại hàng PASS: backlog publish nốt, không cần
        writer push lại."""
        a = 'BLG-00071'
        rel = self.r.draft(a, writer='W1')
        self.r.set_status({a: 'PASS'})
        self.r.evidence(a, rel, same=True)
        self.r.registry({})
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], [a])
        self.assertEqual(out['mode'], 'repair')

    def test_07_published_draft_in_backlog_is_ignored(self):
        a = 'BLG-00081'
        self.r.draft(a, writer='W1')
        self.r.set_status({a: 'PUBLISHED'})
        self.r.registry({})
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], [])
        self.assertEqual(out['published_edits'], [a])
        self.assertEqual(out['quarantine'], [])

    def test_08_duplicate_files_same_id_quarantined(self):
        a = 'BLG-00091'
        self.r.registry({'W1': lease([a])})
        self.r.draft(a, writer='W1')
        self.r.draft(a, writer='W1', name='2026-10-12-bai-viet-so-91.md')
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], [])
        self.assertEqual(out['quarantine'][0]['reason'],
                         'nhieu draft cung mot ID')

    def test_09_paused_control_defers_new_claims_only(self):
        a, b = 'BLG-00101', 'BLG-00102'
        self.r.registry({'W1': lease([a])})
        self.r.draft(a, writer='W1')
        self.r.write_json('data/factory/production-control.json',
                          {'enabled': False, 'chunk_size': 2})
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['mode'], 'paused')
        self.assertFalse(out['proceed'])


class TestOwnership(DrainBase):

    def test_10_corrupt_registry_refuses_fail_closed(self):
        a = 'BLG-00111'
        rel = self.r.draft(a, writer='W1')
        with open(self.r.path('data/state/writer-claims.json'), 'w') as f:
            f.write('{"leases": ')
        _, out, _ = self.sel(added=[rel], rc_expect=3)
        self.assertIn('registry writer-claims hong', out['refuse'])
        self.assertFalse(out['proceed'])

    def test_11_session_mismatch_refused_missing_session_warned(self):
        a = 'BLG-00121'
        self.r.registry({'W1': lease([a], session='s-owner')})
        rel = self.r.draft(a, writer='W1', session='s-intruder')
        _, out, _ = self.sel(added=[rel], rc_expect=3)
        self.assertIn('writer_session', out['refuse'])
        rel = self.r.draft(a, writer='W1')              # không khai session
        _, out, _ = self.sel(added=[rel])
        self.assertTrue(out['proceed'])
        self.assertTrue(any('writer_session' in w for w in out['warnings']))
        rel = self.r.draft(a, writer='W1', session='s-owner')
        _, out, _ = self.sel(added=[rel])
        self.assertEqual(out['warnings'], [])

    def test_12_other_writer_cannot_edit_live_repair_draft(self):
        """P1-4: hàng REPAIR thuộc lease sống của W1; W2 push bản sửa -> refuse."""
        a = 'BLG-00131'
        self.r.registry({'W1': lease([a])})
        rel = self.r.draft(a, writer='W2', body='Ban sua cua W2.')
        self.r.set_status({a: 'REPAIR'})
        self.r.evidence(a, rel, same=False)
        _, out, _ = self.sel(modified=[rel], rc_expect=3)
        self.assertIn('lease dang thuoc writer W1', out['refuse'])

    def test_13_orphan_repair_can_be_fixed_by_anyone(self):
        a = 'BLG-00141'
        self.r.registry({})
        rel = self.r.draft(a, writer='W2', body='Ban sua.')
        self.r.set_status({a: 'REPAIR'})
        self.r.evidence(a, rel, same=False)
        _, out, _ = self.sel(modified=[rel])
        self.assertTrue(out['proceed'])
        self.assertEqual(out['mode'], 'repair')

    def test_14_unchanged_pass_draft_needs_no_owner_check(self):
        a = 'BLG-00151'
        self.r.registry({'W3': lease([a])})
        rel = self.r.draft(a, writer='W1')       # tên writer cũ, lease đã đổi
        self.r.set_status({a: 'PASS'})
        self.r.evidence(a, rel, same=True)
        _, out, _ = self.sel(modified=[rel])
        self.assertTrue(out['proceed'])

    def test_15_review_rows_refused_in_push(self):
        a = 'BLG-00161'
        rel = self.r.draft(a, writer='W1')
        self.r.set_status({a: 'REVIEW'})
        self.r.registry({'W1': lease([a])})
        _, out, _ = self.sel(added=[rel], rc_expect=3)
        self.assertIn('khong duoc sua lai', out['refuse'])


class TestIdempotentRerun(DrainBase):

    def test_20_rerun_of_published_push_is_green_noop(self):
        """P1-10: draft đã được chuyển sang _posts/; chạy lại push cũ."""
        a = 'BLG-00171'
        self.r.set_status({a: 'PUBLISHED'})
        for r in self.r.rows:
            if r['id'] == a:
                r['output_path'] = '_posts/2026-10-11-bai-viet-so-171.md'
        self.r.save_matrix()
        self.r.registry({})
        # file _drafts/... không còn tồn tại
        _, out, _ = self.sel(added=['_drafts/2026-10-11-bai-viet-so-171.md'])
        self.assertFalse(out['proceed'])
        self.assertEqual(out['published_edits'], [a])
        self.assertIsNone(out['refuse'])

    def test_21_missing_draft_not_published_still_refused(self):
        _, out, _ = self.sel(added=['_drafts/2026-10-11-bai-viet-so-172.md'],
                             rc_expect=3)
        self.assertIn('khong doc duoc', out['refuse'])


class TestPathWarning(DrainBase):

    def test_30_writer_touching_protected_paths_is_warned(self):
        a = 'BLG-00181'
        self.r.registry({'W1': lease([a])})
        rel = self.r.draft(a, writer='W1')
        _, out, r = self.sel(
            added=[rel],
            changed=[rel, 'data/state/writer-claims.json',
                     'data/content-matrix.csv', '_posts/x.md'])
        self.assertTrue(out['proceed'])
        w = ' '.join(out['warnings'])
        self.assertIn('data/content-matrix.csv', w)
        self.assertIn('_posts/x.md', w)
        self.assertNotIn('writer-claims.json', w)
        self.assertIn('::warning::', r.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
