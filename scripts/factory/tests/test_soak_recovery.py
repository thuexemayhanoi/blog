#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOAK TEST 20 vòng — tầng 4: long-run + failure recovery (hermetic).

Hợp đồng 4 tầng (docs/ENGINE-RUNBOOK.md mục 11): tầng 4 chứng minh engine
sống sót qua 20 vòng sản xuất liên tiếp TRÊN MỘT BẢN SAO HERMETIC (fixture
temp), kèm failure injection đúng hợp đồng:
  i=1   transaction treo FRESH (updated_at bây giờ) -> watchdog
        HEALTHY_ACTIVE (đang làm, không kết tội) -> recover rollback ->
        qa lại -> publish.
  i=7   generate-reports.py hỏng giữa chừng -> publish DỪNG rc=1
        ('run_reports FAIL'), bài ĐÃ promote vẫn nhất quán; sửa reports ->
        hậu kiểm sạch, vòng sau continue bình thường.
  i=10  mất file _posts của bài PUBLISHED (borrow) -> preflight validate
        FAIL -> prepare-next TỪ CHỐI MUTATE ('không được mutate khi engine
        lệch'); khôi phục file -> chạy tiếp.
  i=13  block 1: lock treo khi KHÔNG còn việc dở -> watchdog HEALTHY_IDLE
        (không chặn sản xuất); block 2: lock treo khi chunk đang làm ->
        STALE_LOCK + op qa TỪ CHỐI ('writer-lock đang được giữ', rc=1).
  i=16  transaction treo 3h -> watchdog STALE_TXN -> recover rollback ->
        qa lại -> publish.
  i=19  retry idempotent: qa lại hàng PUBLISHED 'được bảo vệ' (rc=0),
        publish lại 'gate chỉ nhận PASS' (rc=1).

Bất biến MỖI vòng:
  #1 production state của repository THẬT KHÔNG bị đụng (hash 4 file).
  #2 validate --scope chunk PASS sau mỗi vòng.
  #3 checkpoint counts khớp đếm matrix thật.
  #4 transaction inactive + lock sạch sau mỗi vòng.
  #5 last_completed_article_id == đúng bài promote CUỐI (exact, không
     high-water mark — lc "lùi" khi borrow hàng ID thấp là fixture
     artifact, KHÔNG phải defect engine).
  #8 history (lọc started_at >= t0) KHÔNG có article_id trùng (borrow
     track skip_ids — mượn lại hàng đã mượn tạo duplicate PUBLISHED).

Hậu kiểm cuối: validate batch + reports idempotent (fingerprint) + op
status + hash production state.

Chạy: python3 scripts/factory/tests/test_soak_recovery.py (~5-8 phút)
"""
import datetime
import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_qa_modes import (FxTestCase, borrow_planned_row, make_draft,  # noqa: E402
                           matrix_rows, cp_json, write_json)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

PROD_STATE = ('data/content-matrix.csv',
              'data/state/checkpoint.json',
              'data/state/transaction.json',
              'data/state/writer-lock.json')

CHUNK = 1
ROUNDS = 20
INJECT_TXN_FRESH = (1,)
INJECT_TXN_STALE = (16,)
INJECT_REPORTS_BREAK = (7,)
INJECT_MISSING_POST = (10,)
INJECT_LOCK = (13,)
INJECT_IDEMPOTENT_RETRY = (19,)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S+00:00')


def iso_hours_ago(h):
    return (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=h)).strftime('%Y-%m-%dT%H:%M:%S+00:00')


class SoakRecoveryTest(FxTestCase):

    def prod_digest(self):
        """Bất biến #1: repository THẬT phải nguyên vẹn sau mọi vòng."""
        h = hashlib.sha256()
        for rel in PROD_STATE:
            h.update(open(os.path.join(ROOT, rel), 'rb').read())
        return h.hexdigest()

    def watchdog_state(self):
        r = self.py('scripts/factory/watchdog.py')
        line = [ln for ln in r.stdout.splitlines()
                if ln.startswith('WATCHDOG_JSON: ')]
        self.assertTrue(line, 'thiếu WATCHDOG_JSON: %r' % (r.stdout
                                                          + r.stderr))
        return json.loads(line[0].split(': ', 1)[1])

    def write_txn_active(self, aid, draft, age_h):
        dest = '_posts/%s' % os.path.basename(draft)
        txn = {
            'active': True,
            'pending': {'article_id': aid, 'step': 'promote %s' % aid,
                        'destination': dest, 'draft': draft},
            'history': [{'destination': dest, 'source': draft,
                         'started_at': iso_hours_ago(age_h)}],
            'updated_at': iso_hours_ago(age_h),
            'note': 'fixture soak: transaction treo',
        }
        write_json(self.fx, 'data/state/transaction.json', txn)

    def inject_stale_lock(self, age_h=3):
        ts = iso_hours_ago(age_h)
        sentinel = os.path.join(self.fx, 'data/state/writer-lock.active')
        with open(sentinel, 'w', encoding='utf-8') as f:
            f.write('soaktoken')
        write_json(self.fx, 'data/state/writer-lock.json', {
            'locked': True, 'holder': 'soak-fixture', 'token': 'soaktoken',
            'acquired_at': ts, 'expires_at': None, 'updated_at': ts,
            'note': 'fixture soak: lock treo'})

    def clear_lock(self):
        sentinel = os.path.join(self.fx, 'data/state/writer-lock.active')
        if os.path.exists(sentinel):
            os.remove(sentinel)
        write_json(self.fx, 'data/state/writer-lock.json', {
            'locked': False, 'holder': None, 'acquired_at': None,
            'expires_at': None, 'updated_at': now_iso(),
            'note': 'fixture soak: lock đã dọn'})

    def soak_history(self, t0):
        txn = cp_json(self.fx, 'data/state/transaction.json')
        return [h for h in (txn.get('history') or [])
                if h and h.get('started_at') and h['started_at'] >= t0]

    def assert_no_duplicate_history(self, t0):
        """Bất biến #8: không article_id nào được promote hai lần trong
        lịch sử của soak (mượn lại hàng đã mượn = duplicate PUBLISHED)."""
        hist = self.soak_history(t0)
        seen, dup = set(), None
        for h in hist:
            aid = h.get('article_id')
            if not aid:
                continue
            if aid in seen:
                dup = aid
                break
            seen.add(aid)
        self.assertIsNone(dup, 'duplicate PUBLISHED trong history: %s' % dup)

    def break_reports(self):
        p = os.path.join(self.fx, 'scripts/factory/generate-reports.py')
        with open(p, 'a', encoding='utf-8') as f:
            f.write('\nimport sys as _s\n_s.exit(1)\n')

    def restore_reports(self):
        src = os.path.join(ROOT, 'scripts/factory/generate-reports.py')
        dst = os.path.join(self.fx, 'scripts/factory/generate-reports.py')
        with open(src, 'rb') as a, open(dst, 'wb') as b:
            b.write(a.read())

    def claim_chunk(self):
        """Claim CHUNK hàng (borrow hermetic khi queue cạn, track skip_ids)."""
        rows = matrix_rows(self.fx)
        planned_before = {r['id'] for r in rows if r['status'] == 'PLANNED'}
        if len(planned_before) < CHUNK:
            borrow_planned_row(self.fx, CHUNK, skip_ids=self.borrowed_ids)
            rows = matrix_rows(self.fx)
            newly = [r['id'] for r in rows
                     if r['status'] == 'PLANNED'
                     and r['id'] not in planned_before]
            self.assertEqual(len(newly), CHUNK - len(planned_before))
            self.borrowed_ids.extend(newly)
        r = self.operator('prepare-next', '--count', str(CHUNK))
        self.assertEqual(r.returncode, 0, 'round %d: %s' % (self.round, r.stdout
                                                            + r.stderr))
        rows = matrix_rows(self.fx)
        writing = [r for r in rows if r['status'] == 'WRITING']
        self.assertEqual(len(writing), CHUNK,
                         'round %d: claim sai số hàng' % self.round)
        return writing

    def check_round_invariants(self, expected_lc, t0):
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        # #5 exact contract: lc == bài promote cuối, không high-water mark
        self.assertEqual(cp['last_completed_article_id'], expected_lc,
                         'round %d: lc lệch hợp đồng exact' % self.round)
        # #3 counts khớp matrix thật
        rows = matrix_rows(self.fx)
        counts = {}
        for r in rows:
            counts[r['status']] = counts.get(r['status'], 0) + 1
        self.assertEqual(cp['counts']['planned'], counts.get('PLANNED', 0))
        self.assertEqual(cp['counts']['writing'], counts.get('WRITING', 0))
        self.assertEqual(cp['counts']['published'], counts.get('PUBLISHED', 0))
        # #2 validate chunk PASS
        rv = self.validate('chunk')
        self.assertEqual(rv.returncode, 0,
                         'round %d: %s' % (self.round, rv.stdout))
        # #4 txn inactive + lock sạch
        txn = cp_json(self.fx, 'data/state/transaction.json')
        self.assertFalse(txn.get('active'),
                          'round %d: transaction còn treo' % self.round)
        self.assertFalse(os.path.exists(os.path.join(
            self.fx, 'data/state/writer-lock.active')),
            'round %d: sentinel còn' % self.round)
        # #8 history không trùng
        self.assert_no_duplicate_history(t0)
        # #1 production state NGUYÊN VẸN
        self.assertEqual(self.prod_digest(), self.prod_before,
                         'round %d: production state bị đụng!' % self.round)

    def test_soak_20_rounds_with_failure_injection(self):
        t0 = now_iso()
        self.prod_before = self.prod_digest()
        self.borrowed_ids = []
        self.round = 0
        # fixture: pause chunk dở của repo thật -> 9 hàng PLANNED
        self.pause_in_progress_chunk()
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        expected_lc = cp['last_completed_article_id']
        self.assertTrue(expected_lc)
        for i in range(ROUNDS):
            self.round = i
            expected_lc = self.do_round(i, expected_lc, t0)
        self.final_postcheck(t0, expected_lc)

    def do_round(self, i, expected_lc, t0):
        # ---- inject trước khi claim (queue rỗng ở đầu vòng)
        if i in INJECT_LOCK:
            # block 1: lock treo + KHÔNG việc dở -> HEALTHY_IDLE
            self.inject_stale_lock()
            st = self.watchdog_state()
            self.assertEqual(st['state'], 'HEALTHY_IDLE',
                             'lock mồ côi không việc dở phải HEALTHY_IDLE: %r'
                             % st)
            self.clear_lock()
        if i in INJECT_MISSING_POST:
            # mất file _posts của bài borrow đã xuất bản -> engine lệch ->
            # preflight phải TỪ CHỐI MUTATE
            victim_id = self.borrowed_ids[0]
            rows = matrix_rows(self.fx)
            victim = next(r for r in rows if r['id'] == victim_id)
            vpath = os.path.join(self.fx, victim['output_path'])
            self.assertTrue(os.path.exists(vpath), 'victim thiếu: %s' % victim_id)
            backup = open(vpath, 'rb').read()
            os.remove(vpath)
            r = self.operator('prepare-next', '--count', str(CHUNK))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn('không được mutate khi engine lệch', r.stdout)
            with open(vpath, 'wb') as f:
                f.write(backup)
        # ---- claim chunk (borrow hermetic khi cạn)
        writing = self.claim_chunk()
        ids = [r['id'] for r in writing]
        # ---- inject giữa chừng (chunk đang làm)
        if i in INJECT_LOCK:
            # block 2: lock treo + việc dở in-flight -> STALE_LOCK + qa từ chối
            self.inject_stale_lock()
            st = self.watchdog_state()
            self.assertEqual(st['state'], 'STALE_LOCK',
                             'lock treo + việc dở phải STALE_LOCK: %r' % st)
            rq = self.operator('qa', '--ids', ids[0])
            self.assertEqual(rq.returncode, 1, rq.stdout + rq.stderr)
            self.assertIn('writer-lock đang được giữ', rq.stdout)
            self.clear_lock()
        # ---- draft cho từng hàng
        drafts = [make_draft(self.fx, r) for r in writing]
        # ---- transaction treo: fresh (i=1) / stale 3h (i=16)
        if i in INJECT_TXN_FRESH or i in INJECT_TXN_STALE:
            stale = i in INJECT_TXN_STALE
            self.write_txn_active(ids[0], drafts[0], 3 if stale else 0)
            st = self.watchdog_state()
            self.assertEqual(
                st['state'],
                'STALE_TXN' if stale else 'HEALTHY_ACTIVE',
                'watchdog sai trạng thái txn %s: %r' % (ids[0], st))
            rcv = self.operator('recover')
            self.assertEqual(rcv.returncode, 0, rcv.stdout + rcv.stderr)
            self.assertIn('RECOVERED_ROLLED_BACK', rcv.stdout)
            self.assertIn('transaction đã đóng', rcv.stdout)
        # ---- QA
        r = self.operator('qa', '--ids', ','.join(ids))
        self.assertEqual(r.returncode, 0,
                         'round %d qa: %s' % (i, r.stdout + r.stderr))
        rows = matrix_rows(self.fx)
        by_id = {r2['id']: r2 for r2 in rows}
        for aid in ids:
            self.assertEqual(by_id[aid]['status'], 'PASS',
                             'round %d: %s không PASS' % (i, aid))
        # ---- publish (kèm failure injection i=7)
        if i in INJECT_REPORTS_BREAK:
            self.break_reports()
            r = self.operator('publish', '--ids', ','.join(ids))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn('run_reports FAIL', r.stdout)
            self.restore_reports()
            rr = self.py('scripts/factory/generate-reports.py')
            self.assertEqual(rr.returncode, 0, rr.stdout + rr.stderr)
            rv = self.validate('chunk')
            self.assertEqual(rv.returncode, 0, rv.stdout)
            # bài ĐÃ promote: gate chạy trước reports — state nhất quán
            rows = matrix_rows(self.fx)
            self.assertEqual(
                next(x['status'] for x in rows if x['id'] == ids[0]),
                'PUBLISHED')
        else:
            r = self.operator('publish', '--ids', ','.join(ids))
            self.assertEqual(r.returncode, 0,
                             'round %d publish: %s' % (i, r.stdout + r.stderr))
        expected_lc = ids[-1]
        # ---- retry idempotent (i=19)
        if i in INJECT_IDEMPOTENT_RETRY:
            rq = self.operator('qa', '--ids', ','.join(ids))
            self.assertEqual(rq.returncode, 0, rq.stdout + rq.stderr)
            self.assertIn('được bảo vệ', rq.stdout)
            rp = self.operator('publish', '--ids', ','.join(ids))
            self.assertEqual(rp.returncode, 1, rp.stdout + rp.stderr)
            self.assertIn('gate chỉ nhận PASS', rp.stdout)
        # ---- bất biến mỗi vòng
        self.check_round_invariants(expected_lc, t0)
        return expected_lc

    def final_postcheck(self, t0, expected_lc):
        """Hậu kiểm cuối: DEEP-validate + reports idempotent + status +
        production purity."""
        rv = self.validate('batch')
        self.assertEqual(rv.returncode, 0, rv.stdout)
        # reports idempotent: vân tay dữ liệu ổn định qua 2 lần sinh
        fkeys = ('data_fingerprint', 'matrix_sha256', 'taxonomy_sha256',
                 'inventory_sha256', 'rows', 'data_through')
        prog1 = json.load(open(os.path.join(self.fx,
                                            'reports/factory/progress.json'),
                               encoding='utf-8'))
        rr = self.py('scripts/factory/generate-reports.py')
        self.assertEqual(rr.returncode, 0, rr.stdout + rr.stderr)
        prog2 = json.load(open(os.path.join(self.fx,
                                            'reports/factory/progress.json'),
                               encoding='utf-8'))
        for k in fkeys:
            self.assertEqual(prog1.get(k), prog2.get(k),
                             'reports không idempotent ở %s' % k)
        rs = self.operator('status')
        self.assertEqual(rs.returncode, 0, rs.stdout + rs.stderr)
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        self.assertEqual(cp['last_completed_article_id'], expected_lc)
        txn = cp_json(self.fx, 'data/state/transaction.json')
        self.assertFalse(txn.get('active'))
        self.assert_no_duplicate_history(t0)
        # bất biến #1 lần cuối: production state NGUYÊN VẸN
        self.assertEqual(self.prod_digest(), self.prod_before,
                         'production state bị đụng qua soak!')


if __name__ == '__main__':
    unittest.main(verbosity=2)
