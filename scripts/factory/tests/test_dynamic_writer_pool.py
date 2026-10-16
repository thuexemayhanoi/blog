#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Opt-in expanded writer pool — offline CAS regression, no production mutation."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim_helpers import Sim, parse_session_out, REPO_ROOT

ENV = {'BLOG_WRITER_SLOTS': '12'}


class DynamicPoolTest(unittest.TestCase):
    def setUp(self):
        self.sim = Sim(n_planned=160)
        self.addCleanup(self.sim.cleanup)

    def begin(self, name, *args):
        if name not in self.sim.clones:
            self.sim.clone(name)
        proc = self.sim.session_cmd(name, 'begin', *args, env=ENV)
        return proc, parse_session_out(proc.stdout)

    def test_fourth_ai_can_write_while_three_legacy_slots_are_held(self):
        seen = set()
        for name, expected in [('a', 'W1'), ('b', 'W2'),
                               ('c', 'W3'), ('mistral', 'W4')]:
            r, out = self.begin(name, '--slot', 'auto', '--count', '10')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(out['slot'], expected)
            ids = set(out['leased_total'])
            self.assertEqual(len(ids), 10)
            self.assertFalse(ids & seen, 'two writers received the same BLG-ID')
            seen.update(ids)
        reg = self.sim.origin_registry()
        self.assertEqual(len(seen), 40)
        self.assertEqual(sorted(reg['leases']), ['W1', 'W2', 'W3', 'W4'])
        self.assertEqual(len({x['session'] for x in reg['leases'].values()}), 4)

    def test_extra_slots_still_obey_exclusive_id_and_session_ownership(self):
        r, one = self.begin('mistral', '--slot', 'W4', '--ids', 'BLG-00005')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r2, two = self.begin('second', '--slot', 'W5', '--ids', 'BLG-00005')
        self.assertEqual(r2.returncode, 1, r2.stdout + r2.stderr)
        self.assertEqual(two['code'], 'ID_TAKEN')
        r3, third = self.begin('second', '--slot', 'W4', '--count', '1')
        self.assertEqual(r3.returncode, 1, r3.stdout + r3.stderr)
        self.assertEqual(third['code'], 'SLOT_HELD')
        self.assertEqual(self.sim.origin_registry()['leases']['W4']['ids'],
                         ['BLG-00005'])

    def test_auto_resumes_same_extra_slot_without_claiming_twice(self):
        r, first = self.begin('mistral', '--slot', 'auto', '--count', '3',
                              '--session', 's-mistral-pool')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r2, again = self.begin('mistral', '--slot', 'auto', '--count', '3',
                               '--session', 's-mistral-pool')
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(first['leased_total'], again['leased_total'])
        self.assertEqual(first['slot'], again['slot'])

    def test_slot_capacity_is_configured_and_bounded(self):
        cfg = os.path.join(REPO_ROOT, 'data', 'factory', 'writer-pool.json')
        with open(cfg, encoding='utf-8') as f:
            pool = json.load(f)
        self.assertEqual(pool['max_slots'], 12)
        r, out = self.begin('invalid', '--slot', 'W13')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(out['code'], 'BAD_SLOT')


if __name__ == '__main__':
    unittest.main()
