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


class TestPoisonDrafts(DrainBase):
    """Draft "độc" (review publisher P1): KHÔNG được làm MỌI run đỏ hay kẹt
    PASS vô hạn. Mỗi draft độc bị CÁCH LY (backlog) hoặc REFUSE (push) bởi
    preflight engine-ready; draft hợp lệ của writer khác vẫn chạy."""

    GOOD = ['BLG-00041', 'BLG-00042']
    BAD = 'BLG-00051'

    def setUp(self):
        super().setUp()
        self.r.registry({'W1': lease(self.GOOD), 'W2': lease([self.BAD])})
        for a in self.GOOD:
            self.r.draft(a, writer='W1')

    def _bad_backlog(self, reason_part, **draft_kw):
        self.r.draft(self.BAD, writer='W2', **draft_kw)
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], self.GOOD, out)
        self.assertTrue(out['proceed'])
        reasons = ' | '.join(q['reason'] for q in out['quarantine'])
        self.assertIn(reason_part, reasons)
        return out

    def test_40_non_utf8_draft_is_quarantined_not_fatal(self):
        self._bad_backlog('khong doc duoc', raw=(
            b'---\narticle_id: BLG-00051\nwriter: W2\n---\n\xff\xfe\xfa'))

    def test_41_frontmatter_without_date_is_quarantined(self):
        # factory-operator.qa_check_one raise KeyError('date') => FATAL
        self._bad_backlog('date', omit=('date',))

    def test_42_missing_gate_fields_quarantined_not_stuck_pass(self):
        # QA vẫn PASS draft thiếu categories/title nhưng publish-gate từ chối
        self._bad_backlog('categories', omit=('categories',))

    def test_43_missing_title_quarantined(self):
        self._bad_backlog('title:', omit=('title',))

    def test_44_bad_date_format_quarantined(self):
        self._bad_backlog('YYYY-MM-DD', raw=(
            '---\ntitle: x\ndate: abcd\ndescription: d\ncategories: [a]\n'
            'article_id: BLG-00051\nwriter: W2\n---\n\nnoi dung\n').encode())

    def test_45_wrong_file_slug_quarantined(self):
        # ID hợp lệ + lease đúng nhưng tên file lệch slug hàng: trước đây
        # factory-queue refuse CẢ queue ("id chua co draft") mỗi run
        self._bad_backlog('ten file', name='2026-10-11-khac-slug.md')

    def test_46_placeholder_quarantined(self):
        self._bad_backlog('placeholder', body='Lorem ipsum dolor sit amet.')

    def test_47_two_drafts_for_one_id_ambiguous_in_push_refused(self):
        self.r.draft(self.BAD, writer='W2', name='2026-10-10-bai-viet-so-51.md')
        rel = self.r.draft(self.BAD, writer='W2')
        rc, out, r = self.sel(added=[rel], rc_expect=3)
        self.assertIn('2 draft cho cung mot hang', out['refuse'])

    def test_48_engine_would_pick_another_file_quarantined(self):
        """find_draft = glob `*-<slug>.md` đầu tiên theo tên: file lạ
        `2026-10-11-a-<slug>.md` đứng TRƯỚC file đúng => engine QA/publish
        nhầm bản. Selector không cho vào queue."""
        self.r.draft(self.BAD, writer='W2')
        self.r.draft('BLG-00052', writer='W2',
                     name='2026-10-11-a-bai-viet-so-51.md')
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], self.GOOD)
        reasons = ' | '.join(q['reason'] for q in out['quarantine'])
        self.assertIn('thay vi', reasons)

    def test_49_poison_in_push_is_refused_but_backlog_still_drains(self):
        """Push hỏng của W2 không được làm kẹt draft hợp lệ của W1 (run chờ
        của W1 có thể đã bị run này thay thế): backlog vẫn chạy, run đỏ ở step
        cuối (refused=true)."""
        rel = self.r.draft(self.BAD, writer='W2', omit=('date',))
        out_file = self.r.path('gh-output.txt')
        rc, out, r = self.r.select(added=[rel], backlog=True,
                                   env={'GITHUB_OUTPUT': out_file})
        self.assertEqual(rc, 0)
        self.assertIn('date', out['refuse'])
        self.assertEqual(out['queue'], self.GOOD)
        self.assertTrue(out['proceed'])
        q = {x.get('path'): x['reason'] for x in out['quarantine']}
        self.assertIn('push bi tu choi', q[rel])
        with open(out_file) as f:
            gh = f.read()
        self.assertIn('refused=true', gh)
        self.assertIn('queue=%s' % ','.join(self.GOOD), gh)

    def test_50_refused_push_with_empty_backlog_exits_3(self):
        for a in self.GOOD:
            os.remove(self.r.path('_drafts/2026-10-11-bai-viet-so-%d.md'
                                  % int(a.split('-')[1])))
        rel = self.r.draft(self.BAD, writer='W2', omit=('categories',))
        rc, out, r = self.sel(added=[rel], backlog=True, rc_expect=3)
        self.assertEqual(out['queue'], [])
        self.assertIn('categories', out['refuse'])

    def test_51_paused_does_not_starve_inflight_rows(self):
        """production-control paused + một draft PLANNED trong backlog làm cả
        run `paused` => hàng REPAIR (chủ vừa sửa) không bao giờ chạy."""
        rep = 'BLG-00061'
        self.r.registry({'W1': lease(self.GOOD),
                         'W3': lease([rep], session='s-w3')})
        rel = self.r.draft(rep, writer='W3', session='s-w3')
        self.r.set_status({rep: 'REPAIR'})
        self.r.evidence(rep, rel, same=False)      # đã sửa sau lần FAIL
        self.r.write_json('data/factory/production-control.json',
                          {'enabled': False, 'chunk_size': 2})
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], [rep])
        self.assertEqual(out['mode'], 'repair')
        self.assertEqual(out['claim_ids'], [])
        self.assertTrue(any('paused' in w for w in out['warnings']))


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

    def test_13_orphan_repair_edit_requires_adoption(self):
        """AGENTS.md #11: nhận việc orphan chỉ qua --adopt. Draft REPAIR bị SỬA
        khi KHÔNG có lease sống: push -> refuse; drain -> cách ly (không chặn
        ai); sau khi một writer nhận (lease sống) thì đi tiếp."""
        a = 'BLG-00141'
        self.r.registry({})
        rel = self.r.draft(a, writer='W2', body='Ban sua.')
        self.r.set_status({a: 'REPAIR'})
        self.r.evidence(a, rel, same=False)
        _, out, _ = self.sel(modified=[rel], rc_expect=3)
        self.assertIn('--adopt', out['refuse'])
        _, out, _ = self.sel(backlog=True)
        self.assertFalse(out['proceed'])
        self.assertTrue(any(q.get('id') == a and '--adopt' in q['reason']
                            for q in out['quarantine']), out['quarantine'])
        # W2 nhận (lease sống, đúng chủ): hợp lệ, KHÔNG claim lại (REPAIR)
        self.r.registry({'W2': lease([a], session='s-w2')})
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], [a])
        self.assertEqual(out['mode'], 'repair')
        # ...nhưng writer KHÁC vẫn không sửa được draft đang có chủ sống
        rel = self.r.draft(a, writer='W3', body='Ban sua cua W3.')
        _, out, _ = self.sel(modified=[rel], rc_expect=3)
        self.assertIn('lease dang thuoc writer W2', out['refuse'])

    def test_13b_orphan_rows_without_edit_keep_flowing(self):
        """Hết hạn lease không giam hàng: orphan CHƯA bị sửa sau QA (PASS chờ
        publish) hoặc chưa có bằng chứng (publisher chạy dở) vẫn được xử lý."""
        p_ok, w_ok = 'BLG-00143', 'BLG-00144'
        self.r.registry({})
        rel_p = self.r.draft(p_ok, writer='W1')
        self.r.set_status({p_ok: 'PASS', w_ok: 'WRITING'})
        self.r.evidence(p_ok, rel_p, same=True)
        self.r.draft(w_ok, writer='W1')              # không có bằng chứng
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(sorted(out['queue']), [p_ok, w_ok], out)
        self.assertEqual(out['quarantine'], [])

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


class TestRegistryAndCap(DrainBase):
    """Góp ý Codex vòng 2 (đã kiểm chứng): registry mơ hồ chủ sở hữu và cắt
    trần backlog trước khi xếp hàng in-flight."""

    def test_one_session_in_two_live_slots_fails_closed(self):
        a, b = 'BLG-00171', 'BLG-00172'
        self.r.registry({'W1': dict(lease([a]), session='s-shared'),
                         'W2': dict(lease([b]), session='s-shared')})
        rel = self.r.draft(a, writer='W1')
        _, out, _ = self.sel(added=[rel], rc_expect=3)
        self.assertIn('registry writer-claims khong nhat quan', out['refuse'])
        self.assertFalse(out['proceed'])
        _, out, _ = self.sel(backlog=True, rc_expect=3)
        self.assertEqual(out['queue'], [])

    def test_16_same_id_in_two_live_leases_fails_closed(self):
        a = 'BLG-00171'
        self.r.registry({'W1': lease([a]), 'W2': lease([a])})
        rel = self.r.draft(a, writer='W1')
        _, out, _ = self.sel(added=[rel], rc_expect=3)
        self.assertIn('registry writer-claims khong nhat quan', out['refuse'])
        self.assertIn(a, out['refuse'])
        self.assertFalse(out['proceed'])
        # drain cũng KHÔNG chọn đại một chủ
        _, out, _ = self.sel(backlog=True, rc_expect=3)
        self.assertFalse(out['proceed'])
        self.assertEqual(out['queue'], [])

    def test_16b_expired_duplicate_is_not_a_conflict(self):
        a = 'BLG-00172'
        dead = lease([a])
        dead['expires_at'] = '2000-01-01T00:00:00Z'
        self.r.registry({'W1': dead, 'W2': lease([a])})
        rel = self.r.draft(a, writer='W2')
        _, out, _ = self.sel(added=[rel])
        self.assertEqual(out['queue'], [a])

    def test_16c_id_repeated_inside_one_lease_is_one_owner(self):
        """Codex P2 (vòng 3): `ids: [A, A]` trong MỘT lease không có chủ thứ hai
        — selector vẫn nhận draft của chủ đó, KHÔNG chặn publisher vì registry."""
        a = 'BLG-00173'
        self.r.registry({'W1': lease([a, a])})
        rel = self.r.draft(a, writer='W1')
        _, out, _ = self.sel(added=[rel])
        self.assertEqual(out['queue'], [a])
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], [a])

    def test_16d_non_utf8_registry_is_refused_not_a_traceback(self):
        """Review độc lập: registry byte không phải UTF-8 làm selector crash
        (rc=1, traceback) thay vì REFUSED có cấu trúc (rc=3, fail-closed)."""
        a = 'BLG-00174'
        rel = self.r.draft(a, writer='W1')
        with open(self.r.path('data/state/writer-claims.json'), 'wb') as f:
            f.write(b'{"schema_version": "2", "leases": {}, "label": "caf\xe9"}')
        _, out, _ = self.sel(added=[rel], rc_expect=3)
        self.assertIn('registry writer-claims hong', out['refuse'])
        self.assertFalse(out['proceed'])

    def test_16e_unknown_slot_key_fails_closed_in_the_selector(self):
        a = 'BLG-00175'
        rel = self.r.draft(a, writer='W1')
        self.r.registry({'W1': lease([a]), 'W4': lease(['BLG-00176'])})
        _, out, _ = self.sel(added=[rel], rc_expect=3)
        self.assertIn('registry writer-claims hong', out['refuse'])
        self.assertFalse(out['proceed'])

    def _thirty_planned_plus_late_pass(self):
        ids = ['BLG-%05d' % i for i in range(1, 31)]
        self.r.registry({'W1': lease(ids[:10]), 'W2': lease(ids[10:20]),
                         'W3': lease(ids[20:30])})
        for a in ids:
            w = 'W1' if a in ids[:10] else 'W2' if a in ids[10:20] else 'W3'
            self.r.draft(a, writer=w)
        late = 'BLG-00150'                 # PASS đang chờ publish, matrix muộn
        rel = self.r.draft(late, writer='W1')
        self.r.set_status({late: 'PASS'})
        self.r.evidence(late, rel, same=True)
        return ids, late

    def test_17_cap_keeps_inflight_rows_before_planned(self):
        ids, late = self._thirty_planned_plus_late_pass()
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(len(out['queue']), 30)
        self.assertIn(late, out['queue'])
        self.assertNotIn(ids[-1], out['queue'], 'PLANNED cuoi nhuong cho run ke')
        self.assertEqual(out['queue'], sorted(out['queue']),
                         'dau ra van theo matrix order')

    def test_18_paused_with_full_planned_backlog_still_selects_inflight(self):
        ids, late = self._thirty_planned_plus_late_pass()
        self.r.write_json('data/factory/production-control.json',
                          {'enabled': False, 'chunk_size': 2})
        _, out, _ = self.sel(backlog=True)
        self.assertEqual(out['queue'], [late])
        self.assertEqual(out['mode'], 'repair')
        self.assertTrue(out['proceed'])


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
