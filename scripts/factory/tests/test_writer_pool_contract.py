#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hợp đồng writer-pool: MỘT nguồn sự thật (data/factory/writer-pool.json).

Trước đây slot (12) nằm ở JSON nhưng trần queue (10/push, 30/run) và lease
(10) bị hard-code ở 3 file với chú thích "3 writer x 10". Test này khoá:
  - writer-claim.py, push-selection.py, factory-queue.py đọc CÙNG giá trị
    từ writer-pool.json (không lệch nhau);
  - parse_pool() từ chối cấu hình mơ hồ/nâng giới hạn một cách âm thầm;
  - AGENTS.md nêu đúng max_slots hiện hành.
Offline, không ghi production state.
"""
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
FACTORY = os.path.join(ROOT, 'scripts', 'factory')


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name,
                                                  os.path.join(FACTORY, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PoolContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, 'data', 'factory', 'writer-pool.json'),
                  encoding='utf-8') as f:
            cls.pool = json.load(f)
        cls.claim = load('wc_contract', 'writer-claim.py')
        cls.select = load('ps_contract', 'push-selection.py')
        cls.queue = load('fq_contract', 'factory-queue.py')

    def test_all_modules_read_the_same_limits(self):
        p = self.pool
        self.assertEqual(self.claim.MAX_LEASE, p['max_ids_per_writer'])
        self.assertEqual(self.claim.MAX_QUEUE_PER_PUSH, p['max_queue_per_push'])
        self.assertEqual(self.claim.MAX_QUEUE_PER_RUN, p['max_queue_per_run'])
        self.assertEqual(self.select.MAX_QUEUE_PER_PUSH, p['max_queue_per_push'])
        self.assertEqual(self.select.MAX_QUEUE_PER_RUN, p['max_queue_per_run'])
        self.assertEqual(self.queue.MAX_QUEUE, p['max_queue_per_run'])

    def test_slot_count_matches_pool_unless_legacy_override(self):
        if os.environ.get('BLOG_WRITER_SLOTS') is None:
            self.assertEqual(self.claim.MAX_WRITERS, self.pool['max_slots'])
            self.assertEqual(len(self.claim.SLOTS), self.pool['max_slots'])

    def test_checked_in_pool_is_self_consistent(self):
        # parse_pool(checked-in config) phải đạt và không thay đổi giá trị.
        self.assertEqual(self.claim.parse_pool(self.pool),
                         {k: self.pool[k] for k in
                          ('max_slots', 'max_ids_per_writer',
                           'max_queue_per_push', 'max_queue_per_run')})
        # một run phải chứa được ít nhất một push đầy
        self.assertLessEqual(self.pool['max_queue_per_push'],
                             self.pool['max_queue_per_run'])
        self.assertLessEqual(self.pool['max_queue_per_push'],
                             self.pool['max_ids_per_writer'])

    def test_parse_pool_defaults_and_valid(self):
        d = self.claim.parse_pool(None)
        self.assertEqual(d, {'max_slots': 3, 'max_ids_per_writer': 10,
                             'max_queue_per_push': 10, 'max_queue_per_run': 30})
        self.assertEqual(self.claim.parse_pool({'max_slots': 12})['max_slots'], 12)
        ok = self.claim.parse_pool({'max_slots': 64, 'max_ids_per_writer': 5,
                                    'max_queue_per_push': 5,
                                    'max_queue_per_run': 60})
        self.assertEqual(ok['max_queue_per_run'], 60)

    def test_parse_pool_rejects_bad_values(self):
        bad = [
            'x', [], 7,
            {'max_slots': True}, {'max_slots': '12'}, {'max_slots': 12.0},
            {'max_slots': 2}, {'max_slots': 65},
            {'max_ids_per_writer': 0}, {'max_ids_per_writer': 11},
            {'max_queue_per_push': 0},
            # push > lease
            {'max_ids_per_writer': 5, 'max_queue_per_push': 6},
            # run < push
            {'max_queue_per_push': 10, 'max_queue_per_run': 9},
            # run vượt trần
            {'max_queue_per_run': 61},
            {'max_queue_per_run': False},
        ]
        for raw in bad:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    self.claim.parse_pool(raw)

    def test_agents_md_states_current_slot_limit(self):
        with open(os.path.join(ROOT, 'AGENTS.md'), encoding='utf-8') as f:
            text = f.read()
        self.assertIn('max_slots=%d' % self.pool['max_slots'], text)


if __name__ == '__main__':
    unittest.main()
