#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test: production-control enabled=false là TẠM DỪNG THẬT với writer và refill (OFFLINE).

Trước đây công tắc chỉ chặn claim của PUBLISHER và selector; một AI writer vẫn `begin` nhận ID mới
và refill vẫn vật chất hoá hàng mới. Giờ:
  - apply_claim(paused=True): KHÔNG nhận hàng PLANNED mới (code PAUSED); nối lại lease/REPAIR sẵn có
    và --adopt hàng in-flight (hoàn tất việc dở, không mất draft) vẫn được;
  - writer-session begin đọc công tắc từ cây origin vừa fetch (CAS) nên không bị stale;
  - op refill và stage-refill-batch thoát sạch exit 0, KHÔNG đổi ledger/seed/matrix/checkpoint;
  - thiếu/hỏng file công tắc = enabled (cùng hợp đồng operator/selector), chỉ `enabled:false` mới dừng.

Chạy: python3 scripts/factory/tests/test_pause_enforcement.py
"""
import importlib.util
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)

from sim_helpers import Sim, make_matrix, parse_session_out  # noqa: E402
from test_qa_modes import FxTestCase, run_py  # noqa: E402


def load_wc():
    spec = importlib.util.spec_from_file_location('wc_pause_t', os.path.join(ROOT, 'scripts/factory/writer-claim.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


WC = load_wc()
PAUSED = json.dumps({'enabled': False, 'chunk_size': 2})
ENABLED = json.dumps({'enabled': True, 'chunk_size': 2})


def registry():
    return {'schema_version': '2', 'updated_at': None, 'leases': {}}


def rows(n=12, status=None):
    r = make_matrix(n)
    for x in r:
        if status and x['id'] in status:
            x['status'] = status[x['id']]
    return r


class ControlParsingTest(unittest.TestCase):

    def test_only_explicit_false_pauses(self):
        self.assertFalse(WC.control_enabled(b'{"enabled": false}'))
        self.assertFalse(WC.control_enabled('{"enabled": false, "chunk_size": 2}'))
        self.assertTrue(WC.control_enabled(b'{"enabled": true}'))
        self.assertTrue(WC.control_enabled(b'{}'))
        self.assertTrue(WC.control_enabled(b'khong phai json'), 'file hỏng = mặc định enabled (hợp đồng chung)')
        self.assertTrue(WC.control_enabled(b'null'))


class ApplyClaimPauseTest(unittest.TestCase):

    def test_paused_refuses_new_planned_ids_by_count(self):
        reg = registry()
        before = json.dumps(reg, sort_keys=True)
        res = WC.apply_claim(reg, rows(), 'W1', 's-a-w1', count=3, paused=True)
        self.assertFalse(res['ok'])
        self.assertEqual(res['code'], 'PAUSED')
        self.assertEqual(json.dumps(reg, sort_keys=True), before, 'registry không đổi khi bị từ chối')

    def test_paused_refuses_explicit_planned_id(self):
        reg = registry()
        res = WC.apply_claim(reg, rows(), 'W1', 's-a-w1', ids=['BLG-00001'], paused=True)
        self.assertEqual(res['code'], 'PAUSED')
        self.assertEqual(reg['leases'], {})

    def test_unpaused_still_claims(self):
        reg = registry()
        res = WC.apply_claim(reg, rows(), 'W1', 's-a-w1', count=3, paused=False)
        self.assertTrue(res['ok'])
        self.assertEqual(len(res['claimed']), 3)
        self.assertNotIn('paused', res)

    def test_paused_keeps_existing_lease_and_adds_nothing(self):
        reg = registry()
        self.assertTrue(WC.apply_claim(reg, rows(), 'W1', 's-a-w1', count=2)['ok'])
        held = list(reg['leases']['W1']['ids'])
        res = WC.apply_claim(reg, rows(), 'W1', 's-a-w1', count=5, paused=True, allow_empty_pool=True)
        self.assertTrue(res['ok'])
        self.assertEqual(res['claimed'], [], 'không nhận thêm ID mới khi tạm dừng')
        self.assertEqual(res['leased_total'], held)
        self.assertTrue(res['paused'])

    def test_paused_without_lease_and_allow_empty_still_refused(self):
        res = WC.apply_claim(registry(), rows(), 'W2', 's-b-w2', count=2, paused=True, allow_empty_pool=True)
        self.assertEqual(res['code'], 'PAUSED')

    def test_paused_allows_adopting_inflight_orphan(self):
        reg = registry()
        rs = rows(status={'BLG-00004': 'REPAIR'})
        res = WC.apply_claim(reg, rs, 'W1', 's-a-w1', ids=['BLG-00004'], adopt=True, paused=True)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['leased_total'], ['BLG-00004'])

    def test_paused_orphan_adopt_by_count_takes_only_inflight(self):
        reg = registry()
        rs = rows(status={'BLG-00004': 'REPAIR'})
        res = WC.apply_claim(reg, rs, 'W1', 's-a-w1', count=3, adopt=True, paused=True)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['claimed'], ['BLG-00004'], 'chỉ nhận hàng in-flight, không nhận PLANNED')


class WriterSessionPauseTest(unittest.TestCase):

    def setUp(self):
        self.sim = Sim(n_planned=12)
        self.addCleanup(self.sim.cleanup)
        self.path = self.sim.clone('w1')

    def begin(self, *extra):
        r = self.sim.session_cmd('w1', 'begin', '--slot', 'W1', *extra, env={'FACTORY_WRITER_SESSION': 's-pause-w1'})
        return r, parse_session_out(r.stdout)

    def test_begin_refused_when_origin_paused_and_nothing_changes(self):
        self.sim.commit_on_origin({'data/factory/production-control.json': PAUSED}, 'pause')
        commits = self.sim.origin_commit_count()
        r, out = self.begin('--count', '2')
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(out.get('code'), 'PAUSED', r.stdout + r.stderr)
        self.assertEqual(self.sim.origin_registry()['leases'], {})
        self.assertEqual(self.sim.origin_commit_count(), commits, 'không commit gì lên origin')

    def test_pause_read_from_fresh_origin_not_stale_local_copy(self):
        # clone chưa pull công tắc: origin bị tạm dừng SAU khi clone vẫn phải chặn (CAS đọc origin)
        self.sim.commit_on_origin({'data/factory/production-control.json': PAUSED}, 'pause after clone')
        self.assertFalse(os.path.exists(os.path.join(self.path, 'data/factory/production-control.json')))
        r, out = self.begin('--count', '1')
        self.assertEqual(out.get('code'), 'PAUSED')

    def test_begin_works_after_resume_and_resume_only_while_paused(self):
        self.sim.commit_on_origin({'data/factory/production-control.json': ENABLED}, 'enable')
        r, out = self.begin('--count', '2')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        held = out['leased_total']
        self.assertEqual(len(held), 2)
        self.sim.commit_on_origin({'data/factory/production-control.json': PAUSED}, 'pause again')
        # gia hạn/nối lại đúng số ID đang giữ khi tạm dừng vẫn được (không mất lease/draft)
        r2, out2 = self.begin('--count', '2')
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(out2['leased_total'], held)
        # xin thêm ID mới khi tạm dừng: không nhận gì thêm
        r3, out3 = self.begin('--count', '5')
        if r3.returncode == 0:
            self.assertEqual(out3['leased_total'], held)
            self.assertEqual(out3.get('claimed'), [])
        else:
            self.assertEqual(out3.get('code'), 'PAUSED')


class RefillPauseTest(FxTestCase):

    def pause(self):
        with open(os.path.join(self.fx, 'data/factory/production-control.json'), 'w', encoding='utf-8') as f:
            f.write(PAUSED)

    def snapshot(self):
        names = ['data/content-matrix.csv', 'data/state/refill-candidates.json', 'data/state/matrix-seed.json',
                 'data/state/checkpoint.json']
        out = {}
        for n in names:
            with open(os.path.join(self.fx, n), 'rb') as f:
                out[n] = f.read()
        return out

    def test_op_refill_is_clean_noop_when_paused(self):
        self.pause()
        before = self.snapshot()
        r = run_py(['scripts/factory/factory-operator.py', 'refill'], self.fx)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('production-control enabled=false', r.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_stage_refill_batch_is_noop_when_paused_but_gates_when_enabled(self):
        bd = os.path.join(self.fx, 'data/factory/refill-batches')
        os.makedirs(bd, exist_ok=True)
        with open(os.path.join(bd, 'bad-batch.json'), 'w', encoding='utf-8') as f:
            f.write('{"khong": "hop le"}')
        before = self.snapshot()
        self.pause()
        r = run_py(['scripts/factory/stage-refill-batch.py', '--all'], self.fx)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PAUSED', r.stdout)
        self.assertEqual(self.snapshot(), before)
        # bật lại: cùng batch hỏng bị gate G1-G9 từ chối (chứng minh chỉ công tắc làm nó no-op)
        with open(os.path.join(self.fx, 'data/factory/production-control.json'), 'w', encoding='utf-8') as f:
            f.write(ENABLED)
        r2 = run_py(['scripts/factory/stage-refill-batch.py', '--all'], self.fx)
        self.assertNotEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(self.snapshot(), before, 'gate fail-closed: ledger vẫn nguyên')


if __name__ == '__main__':
    unittest.main(verbosity=1)
