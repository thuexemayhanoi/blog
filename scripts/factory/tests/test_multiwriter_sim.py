#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STRESS/CONCURRENCY ĐẦU-CUỐI: 3 AI writer + publisher + engine THẬT.

Chạy OFFLINE trên origin bare cục bộ (bản sao cây làm việc) — KHÔNG đụng
main/production thật. Publisher chạy ĐÚNG các bước của factory-publish.yml
(selection --backlog -> factory-queue -> validate -> publisher-push) bằng
script production; concurrency GitHub được mô phỏng đúng ngữ nghĩa (1 run
chạy + 1 run chờ, run chờ cũ bị HỦY). Origin cấm non-fast-forward (không
force push) và mọi test kiểm chứng:
  - không mất bài, không trùng ID/slug, không đè lease;
  - không bao giờ hai publisher cùng ghi production;
  - QA không bị hạ: bài PUBLISHED có bằng chứng QA đạt ngưỡng 75/70 và
    sha256 nội dung == nội dung đã chấm; bài hỏng KHÔNG tự PASS;
  - phục hồi được từ trạng thái hợp lệ.

Kịch bản (bắt buộc theo MASTER TASK mục 7) — S1..S10 ở đây; các kịch bản
claim/push/lease/409-422-503 nằm ở test_writer_session.py:
  S1  3 writer push gần như cùng lúc: run chờ bị HỦY nhưng draft của nó
      vẫn được publish (drain)                    [lost-trigger P0-2]
  S2  QA FAIL -> REPAIR của W1 KHÔNG chặn W2/W3, writer khác không sửa
      được draft REPAIR của W1, W1 sửa -> publish   [deadlock P0-1]
  S3  writer hết quota giữa batch + lease hết hạn -> reclaim, writer cũ bị
      chặn push
  S4  Factory Refill chiếm slot chờ của publisher -> nudge -> drain
  S5  push draft cho bài ĐÃ PUBLISHED -> no-op, bài giữ nguyên
  S6  writer sửa draft ĐÚNG LÚC publisher đang chốt -> publisher dừng, KHÔNG
      lọt nội dung chưa QA                         [rebase hole P0-3]
  S7  Actions bị hủy giữa chừng + run lại + chạy lại trigger cũ: idempotent
  S8  stale lock -> run FAIL an toàn -> gỡ lock -> phục hồi
  S9  checkpoint lệch -> fail-closed -> repair-checkpoint -> phục hồi
  S10 draft với lease hết hạn bị cách ly; writer mới reclaim + publish

S1..S10 (~6 phút, 3 CPU) nằm trong CI (job engine-tests, chỉ ở FULL mode);
`FACTORY_SIM_FULL=1` thêm kịch bản S11 (3 writer x 10 ID = 30 ID, ~3 phút).
Chạy: python3 scripts/factory/tests/test_multiwriter_sim.py
"""
import hashlib
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_engine import EngineSim, cleanup_golden, matrix_of  # noqa: E402
from sim_helpers import git, REPO_ROOT                      # noqa: E402


def setUpModule():
    pass


def tearDownModule():
    cleanup_golden()


class SimBase(unittest.TestCase):
    def setUp(self):
        self.sim = EngineSim()
        self.addCleanup(self.sim.cleanup)

    def begin(self, name, count=4, slot='auto'):
        rc, out = self.sim.begin(name, slot, count=count)
        self.assertEqual(rc, 0, out)
        return out

    def md_drafts(self):
        return [f for f in self.sim.origin_files('_drafts/')
                if f.endswith('.md') and 'mau-nhap' not in f]


class TestConcurrentPublish(SimBase):

    def test_s1_three_writers_cancelled_pending_run_loses_nothing(self):
        sim = self.sim
        ids = {}
        for n in ('w1', 'w2', 'w3'):
            ids[n] = self.begin(n, 4)['leased_total']
        all_ids = [i for n in ids for i in ids[n]]
        self.assertEqual(len(set(all_ids)), 12, 'ID rieng cua 3 writer')
        for n in ids:
            sim.write_drafts(n, ids[n])

        def concurrent_pushes(s):
            s.push('w2', ids['w2'])        # trigger pending (run chờ)
            s.push('w3', ids['w3'])        # thay run chờ -> run W2 bị HỦY
        # W1 push -> run R1 (đang chạy) -> trong R1 W2, W3 đẩy
        r1 = sim.session('w1', 'push', '--no-qa')
        from sim_helpers import parse_session_out
        o1 = parse_session_out(r1.stdout)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        sim.submit('publish', o1['commit'], before_commit=concurrent_pushes)
        kinds = [(r.status, len(r.published)) for r in sim.runs]
        self.assertEqual(len(sim.cancelled), 1,
                         'run cho cua W2 phai bi huy: %s' % sim.runs)
        statuses = sim.origin_status()
        for n in ids:
            for aid in ids[n]:
                self.assertEqual(statuses[aid], 'PUBLISHED',
                                 '%s (%s) mat bai: %s' % (aid, n, sim.runs))
        self.assertEqual(self.md_drafts(), [],
                         'khong draft nao con bi bo roi trong _drafts/')
        sim.assert_invariants(self, published_ids=all_ids)
        # chỉ MỘT run ghi production tại một thời điểm: mỗi run thành công
        # đẩy đúng một commit nối tiếp (origin cấm non-FF)
        pushed = [r for r in sim.runs if r.pushed]
        self.assertEqual(len(pushed), 2)

    def test_s2_repair_does_not_block_others_and_cannot_be_stolen(self):
        sim = self.sim
        a = self.begin('w1', 2)['leased_total']
        b = self.begin('w2', 2)['leased_total']
        sim.write_drafts('w1', a, bad=[a[1]])
        sim.write_drafts('w2', b)
        sim.push('w1', a)
        st = sim.origin_status()
        self.assertEqual(st[a[0]], 'PUBLISHED')
        self.assertEqual(st[a[1]], 'REPAIR', 'bai QA FAIL KHONG duoc auto PASS')
        # (v1) hàng REPAIR của W1 làm prepare-next bail -> FATAL cho W2
        sim.push('w2', b)
        st = sim.origin_status()
        self.assertEqual({st[i] for i in b}, {'PUBLISHED'},
                         'REPAIR cua W1 KHONG duoc chan W2: %s' % sim.runs)
        self.assertEqual(st[a[1]], 'REPAIR')
        # W3 cố sửa draft REPAIR của W1 bằng commit trực tiếp (bypass tool)
        sim.begin('w3', 'auto', count=2)
        draft = [f for f in self.md_drafts() if a[1] and True][0]
        txt = sim.origin_show(draft)
        evil = txt.replace('writer: W1', 'writer: W3') + '\nW3 sua chen.\n'
        w3 = sim.clones['w3']
        git(w3, 'fetch', '-q', 'origin', 'main')
        git(w3, 'checkout', '-q', '-B', 'main', 'origin/main')
        with open(os.path.join(w3, draft), 'w', encoding='utf-8') as f:
            f.write(evil)
        git(w3, 'commit', '-q', '-am', 'w3 sua draft REPAIR cua W1')
        git(w3, 'push', '-q', 'origin', 'HEAD:main')
        head = sim.origin_head()
        sim.maybe_trigger(head)
        last = sim.runs[-1]
        self.assertEqual(last.status, 'failure', last)
        self.assertIn('lease dang thuoc writer', last.reason)
        self.assertEqual(sim.origin_status()[a[1]], 'REPAIR')
        self.assertEqual(sim.origin_head(), head, 'run bi refuse KHONG doi gi')

    def test_s3_quota_cut_lease_expiry_reclaim_old_session_blocked(self):
        sim = self.sim
        w1 = self.begin('w1', 4)
        ids = w1['leased_total']
        sim.write_drafts('w1', ids)
        sim.push('w1', ids[:2])                       # hết quota: push dở 2/4
        st = sim.origin_status()
        self.assertEqual({st[i] for i in ids[:2]}, {'PUBLISHED'})
        # lease W1 hết hạn (mất kết nối) — W2 reclaim hợp lệ
        reg = sim.origin_registry()
        reg['leases']['W1']['expires_at'] = '2000-01-01T00:00:00Z'
        wd = sim.clone('admin')
        with open(os.path.join(wd, 'data/state/writer-claims.json'), 'w') as f:
            json.dump(reg, f)
        git(wd, 'commit', '-q', '-am', 'simulate lease expiry')
        git(wd, 'push', '-q', 'origin', 'HEAD:main')
        w2 = self.begin('w2', 4, slot='W1')
        self.assertEqual(w2['epoch'], w1['epoch'] + 1)
        self.assertEqual(set(ids[2:]) <= set(w2['leased_total']), True,
                         'ID chua push cua W1 duoc reclaim')
        sim.write_drafts('w2', w2['leased_total'])
        # W1 tỉnh lại push phần còn lại -> bị chặn (không đè)
        head = sim.origin_head()
        r = sim.session('w1', 'push', '--no-qa')
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertEqual(sim.origin_head(), head)
        sim.push('w2', w2['leased_total'])
        st = sim.origin_status()
        for i in w2['leased_total']:
            self.assertEqual(st[i], 'PUBLISHED')
        sim.assert_invariants(self, published_ids=ids[:2] + w2['leased_total'])

    def test_s4_refill_takes_pending_slot_then_nudge_recovers(self):
        sim = self.sim
        a = self.begin('w1', 2)['leased_total']
        b = self.begin('w2', 2)['leased_total']
        sim.write_drafts('w1', a)
        sim.write_drafts('w2', b)

        def refill_race(s):
            s.push('w2', b)                         # run chờ của W2 ...
            s.submit('opaque', s.origin_head(), action=None)   # ... bị refill thay

        from sim_helpers import parse_session_out
        r1 = sim.session('w1', 'push', '--no-qa')
        o1 = parse_session_out(r1.stdout)
        sim.submit('publish', o1['commit'], before_commit=refill_race)
        st = sim.origin_status()
        self.assertEqual({st[i] for i in a}, {'PUBLISHED'})
        self.assertEqual({st[i] for i in b}, {'PLANNED'},
                         'draft W2 chua publish: run cho bi refill thay')
        self.assertEqual(len(sim.cancelled), 1)
        self.assertEqual(len([f for f in self.md_drafts()]), 2,
                         'draft cua W2 van xep hang tren main (khong mat)')
        # writer-side: confirm phát hiện kẹt -> nudge -> publish drain
        r = sim.session('w2', 'confirm', '--ids', ','.join(b), '--timeout',
                        '1', '--poll', '0.3', '--nudge-after', '0.2',
                        '--max-nudges', '1')
        o = parse_session_out(r.stdout)
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertEqual(o['nudged'], 1)
        sim.maybe_trigger(sim.origin_head())        # nudge đổi _drafts/**
        st = sim.origin_status()
        self.assertEqual({st[i] for i in b}, {'PUBLISHED'},
                         'nudge phai kich publisher drain: %s' % sim.runs)
        sim.assert_invariants(self, published_ids=a + b)

    def test_s5_published_article_is_immutable(self):
        sim = self.sim
        a = self.begin('w1', 2)['leased_total']
        sim.write_drafts('w1', a)
        sim.push('w1', a)
        post = sim.origin_matrix()
        row = {r['id']: r for r in post}[a[0]]
        before = sim.origin_blob(row['output_path'])
        # writer cố push lại draft (nội dung khác) cho ID đã PUBLISHED
        w = sim.clones['w1']
        git(w, 'fetch', '-q', 'origin', 'main')
        git(w, 'checkout', '-q', '-B', 'main', 'origin/main')
        slug = row['output_path'][len('_posts/2026-09-28-'):-3]
        p = os.path.join(w, '_drafts', '2026-09-28-%s.md' % slug)
        with open(p, 'w', encoding='utf-8') as f:
            f.write('---\ntitle: x\narticle_id: %s\nwriter: W1\n---\nNOI DUNG '
                    'LAM XUYEN BAI DA PUBLISH\n' % a[0])
        git(w, 'add', '-A')
        git(w, 'commit', '-q', '-m', 'stray re-push of published id')
        git(w, 'push', '-q', 'origin', 'HEAD:main')
        head = sim.origin_head()
        sim.maybe_trigger(head)
        last = sim.runs[-1]
        self.assertIn(last.status, ('noop', 'success'), last)
        self.assertEqual(sim.origin_blob(row['output_path']), before,
                         'bai da PUBLISHED KHONG duoc doi')
        self.assertEqual(sim.origin_head(), head,
                         'publisher KHONG tao commit cho push trung')
        sim.assert_invariants(self, published_ids=a)

    def test_s6_writer_edit_during_publish_cannot_bypass_qa(self):
        sim = self.sim
        a = self.begin('w1', 2)['leased_total']
        files = sim.write_drafts('w1', a)
        from sim_helpers import parse_session_out
        r1 = sim.session('w1', 'push', '--no-qa')
        o1 = parse_session_out(r1.stdout)

        def edit_during(s):
            # writer đổi nội dung draft THỨ NHẤT ngay lúc publisher chốt
            path = files[a[0]]
            with open(path, 'a', encoding='utf-8') as f:
                f.write('\nDong them sau khi push (chua QA).\n')
            s.push('w1', [a[0]])
        sim.submit('publish', o1['commit'], before_commit=edit_during)
        first = [r for r in sim.runs if r.kind == 'publish'][0]
        self.assertEqual(first.status, 'failure', sim.runs)
        self.assertEqual(first.reason, 'push: upstream_overlap')
        st = sim.origin_status()
        self.assertEqual({st[i] for i in a}, {'PUBLISHED'},
                         'run ke drain va publish bai cuoi: %s' % sim.runs)
        sim.assert_invariants(self, published_ids=a)   # sha == QA evidence
        row = {r['id']: r for r in sim.origin_matrix()}[a[0]]
        self.assertIn('Dong them sau khi push',
                      sim.origin_blob(row['output_path']),
                      'noi dung moi da duoc QA lai roi moi publish')

    def test_s7_cancelled_run_rerun_and_stale_trigger_idempotent(self):
        sim = self.sim
        a = self.begin('w1', 4)['leased_total']
        sim.write_drafts('w1', a)
        from sim_helpers import parse_session_out
        r = sim.session('w1', 'push', '--no-qa')
        o = parse_session_out(r.stdout)
        head = sim.origin_head()
        sim.submit('publish', o['commit'], cancel_before_commit=True)
        self.assertEqual(sim.runs[-1].status, 'cancelled')
        self.assertEqual(sim.origin_head(), head, 'huy giua chung KHONG de lai nua vo')
        self.assertEqual({sim.origin_status()[i] for i in a}, {'PLANNED'})
        sim.submit('publish', o['commit'])               # re-run
        self.assertEqual(sim.runs[-1].status, 'success', sim.runs[-1])
        st = sim.origin_status()
        self.assertEqual({st[i] for i in a}, {'PUBLISHED'})
        head2 = sim.origin_head()
        sim.submit('publish', o['commit'])               # chạy lại trigger cũ
        self.assertEqual(sim.runs[-1].status, 'noop', sim.runs[-1])
        self.assertEqual(sim.origin_head(), head2)
        # mỗi ID đúng MỘT lần trong lịch sử giao dịch
        rows = sim.origin_matrix()
        for aid in a:
            self.assertEqual(
                len([x for x in rows if x['id'] == aid]), 1)
        sim.assert_invariants(self, published_ids=a)

    def test_s8_stale_lock_fails_closed_then_recovers(self):
        sim = self.sim
        a = self.begin('w1', 2)['leased_total']
        sim.write_drafts('w1', a)
        adm = sim.clone('admin')
        with open(os.path.join(adm, 'data/state/writer-lock.active'),
                  'w') as f:
            f.write('stale-token')
        git(adm, 'add', '-A')
        git(adm, 'commit', '-q', '-m', 'simulate stale lock')
        git(adm, 'push', '-q', 'origin', 'HEAD:main')
        sim.push('w1', a)
        self.assertEqual(sim.runs[-1].status, 'failure', sim.runs[-1])
        self.assertIn('stale lock', sim.runs[-1].reason)
        self.assertEqual({sim.origin_status()[i] for i in a}, {'PLANNED'})
        # người vận hành gỡ lock (op recover xác nhận) -> run kế publish
        git(adm, 'pull', '-q', '--ff-only', 'origin', 'main')
        git(adm, 'rm', '-q', 'data/state/writer-lock.active')
        git(adm, 'commit', '-q', '-m', 'recover: remove stale lock')
        git(adm, 'push', '-q', 'origin', 'HEAD:main')
        sim.submit('publish', sim.origin_head())
        self.assertEqual({sim.origin_status()[i] for i in a}, {'PUBLISHED'},
                         sim.runs)
        sim.assert_invariants(self, published_ids=a)

    def test_s9_stale_checkpoint_fails_closed_then_repair_checkpoint(self):
        sim = self.sim
        a = self.begin('w1', 2)['leased_total']
        sim.write_drafts('w1', a)
        adm = sim.clone('admin')
        cp_path = os.path.join(adm, 'data/state/checkpoint.json')
        cp = json.load(open(cp_path, encoding='utf-8'))
        cp['counts']['planned'] += 7                    # checkpoint lệch matrix
        with open(cp_path, 'w', encoding='utf-8') as f:
            json.dump(cp, f, indent=2)
        git(adm, 'commit', '-q', '-am', 'stale checkpoint pushed by mistake')
        git(adm, 'push', '-q', 'origin', 'HEAD:main')
        head = sim.origin_head()
        sim.push('w1', a)
        self.assertEqual(sim.runs[-1].status, 'failure', sim.runs[-1])
        self.assertEqual({sim.origin_status()[i] for i in a}, {'PLANNED'},
                         'fail-closed: khong publish khi engine lech')
        # canonical op repair-checkpoint (docs/RECOVERY.md) rồi run kế
        git(adm, 'pull', '-q', '--ff-only', 'origin', 'main')
        r = subprocess.run([sys.executable,
                            'scripts/factory/factory-operator.py',
                            'repair-checkpoint'], cwd=adm,
                           capture_output=True, text=True,
                           env=sim.env())
        self.assertEqual(r.returncode, 0, r.stdout[-600:] + r.stderr[-300:])
        git(adm, 'add', '-A')
        git(adm, 'commit', '-q', '-m', 'repair-checkpoint')
        git(adm, 'push', '-q', 'origin', 'HEAD:main')
        sim.submit('publish', sim.origin_head())
        self.assertEqual({sim.origin_status()[i] for i in a}, {'PUBLISHED'},
                         sim.runs)
        sim.assert_invariants(self, published_ids=a)

    def test_s10_expired_lease_drafts_quarantined_then_new_owner_publishes(self):
        sim = self.sim
        w1 = self.begin('w1', 2)
        ids = w1['leased_total']
        files = sim.write_drafts('w1', ids)
        # draft đã được push (commit trực tiếp) nhưng publisher chưa kịp chạy
        # và lease hết hạn trước đó
        w = sim.clones['w1']
        sim.session('w1', 'check', '--no-qa')       # gắn identity
        git(w, 'fetch', '-q', 'origin', 'main')
        git(w, 'add', '-A', '_drafts')
        git(w, 'commit', '-q', '-m', 'draft push (publisher chua chay)')
        git(w, 'push', '-q', 'origin', 'HEAD:main')
        reg = sim.origin_registry()
        reg['leases']['W1']['expires_at'] = '2000-01-01T00:00:00Z'
        adm = sim.clone('admin')
        git(adm, 'pull', '-q', '--ff-only', 'origin', 'main')
        with open(os.path.join(adm, 'data/state/writer-claims.json'), 'w') as f:
            json.dump(reg, f)
        git(adm, 'commit', '-q', '-am', 'lease expired')
        git(adm, 'push', '-q', 'origin', 'HEAD:main')
        sim.submit('publish', sim.origin_head())
        self.assertEqual(sim.runs[-1].status, 'noop', sim.runs[-1])
        self.assertEqual(len(sim.runs[-1].quarantine), 2,
                         'draft lease het han bi cach ly, khong publish')
        self.assertEqual({sim.origin_status()[i] for i in ids}, {'PLANNED'})
        # writer mới reclaim ID, nhận bản draft có sẵn, gắn identity mới, push
        rc, w2 = sim.begin('w2', 'auto', count=2)
        self.assertEqual(rc, 0)
        self.assertEqual(set(ids), set(w2['leased_total']))
        r = sim.push('w2', w2['leased_total'])
        st = sim.origin_status()
        self.assertEqual({st[i] for i in ids}, {'PUBLISHED'}, sim.runs)
        sim.assert_invariants(self, published_ids=ids)


class TestPoisonDrafts(SimBase):
    """Draft "độc" (review publisher P1/P2) với engine THẬT: không bao giờ làm
    kẹt writer khác; push hỏng không làm mất draft của người khác."""

    @staticmethod
    def drop_date(path):
        with open(path, encoding='utf-8') as f:
            lines = f.read().split('\n')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(l for l in lines if not l.startswith('date:')))

    def test_s12_poison_draft_never_wedges_other_writers(self):
        sim = self.sim
        a = self.begin('w1', 2)['leased_total']
        b = self.begin('w2', 2)['leased_total']
        sim.write_drafts('w1', a)
        files = sim.write_drafts('w2', b)
        self.drop_date(files[b[0]])      # qa_check_one raise KeyError('date')
        # W2 đẩy draft độc bằng --no-qa (bypass QA cục bộ): bị REFUSE, KHÔNG
        # làm hỏng cây production
        head = sim.origin_head()
        sim.push('w2', [b[0]])
        refused = sim.runs[-1]
        self.assertEqual(refused.status, 'failure', refused)
        self.assertIn('date', refused.reason)
        self.assertEqual(sim.origin_status()[b[0]], 'PLANNED')
        # draft độc nằm lại trong _drafts/; W1 push hợp lệ vẫn publish bình
        # thường (trước đây backlog nạp lại draft độc => FATAL mọi run)
        sim.push('w1', a)
        run = sim.runs[-1]
        self.assertEqual(run.status, 'success', run)
        self.assertEqual(sorted(run.published), sorted(a))
        self.assertTrue(any('date' in str(q) for q in run.quarantine),
                        run.quarantine)
        self.assertEqual(sim.origin_status()[b[0]], 'PLANNED')
        self.assertEqual(len(self.md_drafts()), 1, 'chi con draft doc')
        # W2 sửa draft (thêm date) + push lại -> publish
        sim.write_drafts('w2', [b[0]])
        sim.push('w2', [b[0]])
        self.assertEqual(sim.runs[-1].status, 'success', sim.runs[-1])
        self.assertEqual(sim.origin_status()[b[0]], 'PUBLISHED')
        sim.assert_invariants(self, published_ids=a + [b[0]])

    def test_s13_refused_push_does_not_strand_another_writers_draft(self):
        """Run chờ của W1 bị push HỎNG của W2 thay thế (GitHub chỉ giữ 1 run
        chờ): selector của run W2 vẫn drain backlog => draft của W1 không kẹt;
        run vẫn ĐỎ để chủ push hỏng thấy lỗi."""
        sim = self.sim
        from sim_helpers import parse_session_out
        a = self.begin('w1', 2)['leased_total']
        b = self.begin('w2', 2)['leased_total']
        c = self.begin('w3', 2)['leased_total']
        sim.write_drafts('w1', a)
        files = sim.write_drafts('w2', b)
        sim.write_drafts('w3', c)
        self.drop_date(files[b[0]])

        def during(s):
            s.push('w1', a)                # run chờ của W1
            s.push('w2', [b[0]])           # push HỎNG thay run chờ của W1
        r3 = sim.session('w3', 'push', '--no-qa')
        o3 = parse_session_out(r3.stdout)
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        sim.submit('publish', o3['commit'], before_commit=during)
        self.assertEqual(len(sim.cancelled), 1, sim.runs)
        st = sim.origin_status()
        for aid in c + a:
            self.assertEqual(st[aid], 'PUBLISHED',
                             '%s ket: %s' % (aid, sim.runs))
        self.assertEqual(st[b[0]], 'PLANNED')
        last = sim.runs[-1]
        self.assertEqual(last.status, 'failure')
        self.assertTrue(last.pushed, 'phan hop le van duoc commit')
        self.assertIn('date', last.reason)
        sim.assert_invariants(self, published_ids=c + a)


@unittest.skipUnless(os.environ.get('FACTORY_SIM_FULL') == '1',
                     'dat FACTORY_SIM_FULL=1 de chay kich ban 3x10 (cham)')
class TestFullScale(SimBase):

    def test_s11_three_writers_ten_each_thirty_ids(self):
        sim = self.sim
        ids = {}
        for n in ('w1', 'w2', 'w3'):
            ids[n] = self.begin(n, 10)['leased_total']
        all_ids = [i for n in ids for i in ids[n]]
        self.assertEqual(len(set(all_ids)), 30)
        for n in ids:
            sim.write_drafts(n, ids[n])
        for n in ids:
            sim.push(n, ids[n], qa=True)
        st = sim.origin_status()
        self.assertEqual({st[i] for i in all_ids}, {'PUBLISHED'}, sim.runs)
        self.assertEqual(self.md_drafts(), [])
        sim.assert_invariants(self, published_ids=all_ids)


if __name__ == '__main__':
    unittest.main(verbosity=2)
