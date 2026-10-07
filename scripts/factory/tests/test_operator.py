#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test operator.py — QA deterministic, whitelist, business-fact gate.

Chạy: python3 scripts/factory/tests/test_operator.py (từ gốc repository)
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'factory'))
import importlib.util
_spec = importlib.util.spec_from_file_location(
    'factory_operator', os.path.join(ROOT, 'scripts', 'factory', 'factory-operator.py'))
op = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(op)  # noqa: E402  (module chdir về ROOT lúc import)

BIZ = {
    'approved_pricing': {
        'Honda Wave': {'day': 150000, 'week': None, 'month': None},
        'Honda Vision': {'day': 200000, 'week': '800000 - 1000000',
                         'month': None},
    },
    'verified_facts': {'phone': '0942 467 674'},
    'forbidden_claims': ['khuyến mại'],
}
TAX = {
    'parents': [{'parent_id': 'P-THUE-XE', 'title': 'Thuê xe máy',
                 'hub_url': '/thue-xe/'}],
    'children': [{'child_id': 'C-THUE-GIA', 'title': 'Giá thuê xe',
                   'hub_url': '/bang-gia/', 'search_intent': 'commercial'}],
}


def row(**kw):
    base = {
        'id': 'BLG-90001', 'status': 'WRITING',
        'title': 'Giá thuê xe máy theo ngày ở Hà Nội',
        'intent': 'Xem giá thuê xe máy theo ngày',
        'primary_keyword': 'giá thuê xe máy theo ngày',
        'secondary_keywords': 'thuê xe ngày giá bao nhiêu',
        'parent_id': 'P-THUE-XE', 'child_id': 'C-THUE-GIA',
        'group': 'THUE',
        'expected_url': '/thue-xe/{date}/gia-thue-xe-may-theo-ngay-o-ha-noi/',
        'output_path': '_posts/{date}-gia-thue-xe-may-theo-ngay-o-ha-noi.md',
        'canonical_url': '/thue-xe/{date}/gia-thue-xe-may-theo-ngay-o-ha-noi/',
        'internal_links': '/bang-gia/',
        'source_required': 'false', 'legal_risk': 'none',
        'cannibalization_key': 'gia thue xe may theo ngay',
        'word_target': '150',
        'repair_count': '',
        'notes': '',
        'parent_hub': 'thue-xe',
        'location_scope': '',
    }
    base.update(kw)
    return base


BODY = """Giá thuê xe máy theo ngày ở Hà Nội phụ thuộc dòng xe. Bài này tóm tắt
mức giá tham khảo đã duyệt để bạn dự tính chi phí khi đi lại quanh Long Biên.

## Giá thuê xe máy theo ngày: mức tham khảo

Xe số Honda Wave có giá tham khảo 150.000 đồng mỗi ngày. Xe ga như Honda Vision
tham khảo 200.000 đồng mỗi ngày, còn thuê theo tuần dao động 800.000 - 1.000.000
đồng tùy thời điểm.

## Cách tính chi phí cho chuyến đi

Bạn nên [xem bảng giá đầy đủ](/bang-gia/) trước khi đặt xe, tham khảo
[trang chủ đề thuê xe](/thue-xe/) và đọc [hướng dẫn liên hệ](/lien-he/) để xác
nhận giá thực tế. Với quãng đường quanh quận Long Biên, một chiếc xe số thường
đủ cho chuyến ngày.

Giá thực tế và tiền đặt cọc cần xác nhận trực tiếp trước khi nhận xe.
"""

FRONT = """---
date: 2026-09-27 09:00:00 +0700
layout: post
title: "Giá thuê xe máy theo ngày ở Hà Nội"
author: "Nguyễn Tú"
description: "Giá thuê xe máy theo ngày ở Hà Nội theo bảng giá đã duyệt: mức tham khảo từng dòng xe, cách đọc giá theo ngày và những khoản cần xác nhận trước khi đặt."
categories: [Kinh nghiệm]
lang: vi
tags: [giá thuê xe máy theo ngày]
permalink: /thue-xe/2026/09/27/gia-thue-xe-may-theo-ngay-o-ha-noi/
parent_id: P-THUE-XE
child_id: C-THUE-GIA
article_id: BLG-90001
---

"""


class OperatorQATest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pwd = os.getcwd()
        os.makedirs(os.path.join(self.tmp, '_drafts'))
        open(os.path.join(self.tmp, '_drafts',
                          '2026-09-27-gia-thue-xe-may-theo-ngay-o-ha-noi.md'),
             'w', encoding='utf-8').write(FRONT + BODY)
        os.chdir(self.tmp)
        op.APPROVED_AMOUNTS.clear()
        op.build_amount_whitelist(BIZ)

    def tearDown(self):
        os.chdir(self.pwd)

    def qa(self, r):
        return op.qa_check_one(r, [r], BIZ, TAX)

    def test_pass_row(self):
        ev = self.qa(row())
        self.assertEqual(ev['result'], 'PASS', ev['checks'])
        self.assertGreaterEqual(ev['quality'], 75)
        self.assertGreaterEqual(ev['seo'], 70)
        self.assertEqual(ev['business_fact'], 'PASS')
        self.assertEqual(ev['legal'], 'NOT_REQUIRED')
        self.assertTrue(ev['content_sha256'])
        self.assertTrue(ev['matrix_row_sha256'])

    def test_no_draft(self):
        os.remove('_drafts/2026-09-27-gia-thue-xe-may-theo-ngay-o-ha-noi.md')
        ev = self.qa(row())
        self.assertEqual(ev['result'], 'NO_DRAFT')

    def test_forbidden_claim_rejected(self):
        bad = FRONT + BODY.replace('Giá thực tế', 'Khuyến mãi giảm giá. Giá thực tế')
        open('_drafts/2026-09-27-gia-thue-xe-may-theo-ngay-o-ha-noi.md',
             'w', encoding='utf-8').write(bad)
        ev = self.qa(row())
        self.assertEqual(ev['business_fact'], 'FAIL')
        self.assertTrue(ev['critical_failure'])
        self.assertEqual(ev['result'], 'REPAIR')

    def test_invented_amount_rejected(self):
        bad = FRONT + BODY.replace('150.000', '150.000') + \
            '\n\nPhí giao xe cố định là 50.000 đồng mỗi chuyến nội thành.\n'
        open('_drafts/2026-09-27-gia-thue-xe-may-theo-ngay-o-ha-noi.md',
             'w', encoding='utf-8').write(bad)
        ev = self.qa(row())
        self.assertEqual(ev['business_fact'], 'FAIL')

    def test_wrong_phone_rejected(self):
        bad = FRONT + BODY.replace('xác nhận trực tiếp', 'gọi 0987654321 xác nhận')
        open('_drafts/2026-09-27-gia-thue-xe-may-theo-ngay-o-ha-noi.md',
             'w', encoding='utf-8').write(bad)
        ev = self.qa(row())
        self.assertFalse(ev['checks']['phone_ok'])

    def test_legal_row_requires_gov_source(self):
        r = row(source_required='true', legal_risk='high')
        ev = self.qa(r)
        self.assertEqual(ev['legal'], 'FAIL')
        self.assertEqual(ev['result'], 'REPAIR')
        # thêm nguồn chính thức + disclaimer -> PASS legal
        good = FRONT + BODY + (
            '\n\n## Nguồn tham khảo\n\n'
            'Nghị định của Chính phủ: https://vanban.chinhphu.vn/?pageid=1\n\n'
            'Lưu ý: mức phạt và quy định có thể thay đổi, kiểm tra văn bản '
            'mới nhất trước khi áp dụng.\n')
        open('_drafts/2026-09-27-gia-thue-xe-may-theo-ngay-o-ha-noi.md',
             'w', encoding='utf-8').write(good)
        ev = self.qa(r)
        self.assertEqual(ev['legal'], 'PASS', ev['checks'])

    def test_cannibalization_clash_detected(self):
        other = row(id='BLG-90002', status='PUBLISHED')
        ev = op.qa_check_one(row(), [row(), other], BIZ, TAX)
        self.assertFalse(ev['checks']['cannibalization'])
        self.assertIn('BLG-90002', ev['cannibalization_clash'])

    def test_research_class(self):
        self.assertEqual(op.research_class(
            row(source_required='true'), TAX), 'C')
        self.assertEqual(op.research_class(
            row(parent_hub='du-lich'), TAX), 'B')
        self.assertEqual(op.research_class(row(), TAX), 'A')

    def test_amount_whitelist(self):
        for v in (150000, 200000, 800000, 850000, 1000000):
            self.assertIn(v, op.APPROVED_AMOUNTS)
        self.assertNotIn(50000, op.APPROVED_AMOUNTS)

    def test_op_whitelist_rejects_unknown(self):
        os.chdir(self.pwd)
        r = subprocess.run([sys.executable, 'scripts/factory/factory-operator.py',
                            'run-shell'], capture_output=True, text=True,
                           cwd=ROOT)
        self.assertNotEqual(r.returncode, 0)

    def test_pure_helpers(self):
        self.assertEqual(op.vnd_amounts('giá 150.000 đồng và 800.000 - 1.000.000'),
                         {150000, 800000, 1000000})
        self.assertEqual(op.internal_links_in('xem [bảng giá](/bang-gia/) nha'),
                         ['/bang-gia/'])
        self.assertEqual(op.norm_title('Giá thuê xe máy! '), 'giá thuê xe máy')



class VerifyStepsTest(unittest.TestCase):
    """verify_steps tách kiểm tra cần thiết mỗi chunk (FAST) khỏi kiểm tra
    toàn hệ thống (DEEP/FULL). FAST không chạy suite copy toàn repository
    (test_link_integrity, test_qa_modes); FULL giữ nguyên danh mục cũ
    (validate full + mọi test engine + capacity-audit + queue)."""

    def test_fast_steps_are_chunk_scoped(self):
        steps = op.verify_steps('fast')
        self.assertEqual(steps[0],
                         ['scripts/factory/validate.py', '--scope', 'chunk'])
        tests = [s[0] for s in steps
                 if s[0].startswith('scripts/factory/tests/')]
        self.assertNotIn('scripts/factory/tests/test_link_integrity.py', tests)
        self.assertNotIn('scripts/factory/tests/test_qa_modes.py', tests)
        self.assertIn('scripts/factory/tests/test_publish_gate.py', tests)
        self.assertIn('scripts/factory/tests/test_workflow_syntax.py', tests)
        self.assertIn(['scripts/factory/capacity-audit.py'], steps)
        self.assertIn(['scripts/factory/queue.py', '--stats'], steps)

    def test_full_keeps_whole_catalogue(self):
        steps = op.verify_steps('full')
        self.assertEqual(steps[0],
                         ['scripts/factory/validate.py', '--scope', 'full'])
        tests = sorted(s[0] for s in steps
                       if s[0].startswith('scripts/factory/tests/'))
        self.assertEqual(tests, sorted([
            'scripts/factory/tests/test_publish_gate.py',
            'scripts/factory/tests/test_operator.py',
            'scripts/factory/tests/test_refill_safety.py',
            'scripts/factory/tests/test_push_selection.py',
            'scripts/factory/tests/test_workflow_syntax.py',
            'scripts/factory/tests/test_link_integrity.py',
            'scripts/factory/tests/test_qa_modes.py',
            'scripts/factory/tests/test_publish_flow.py',
            'scripts/factory/tests/test_refill_semantics.py',
            # FULL mạnh hơn DEEP (hợp đồng 4 tầng): + hardening + watchdog
            # + soak (tầng 4: long-run/failure recovery 20 vòng hermetic).
            'scripts/factory/tests/test_hardening.py',
            'scripts/factory/tests/test_watchdog.py',
            'scripts/factory/tests/test_soak_recovery.py',
        ]))
        self.assertIn(['scripts/factory/capacity-audit.py'], steps)
        self.assertIn(['scripts/factory/queue.py', '--stats'], steps)

    def test_full_is_stricter_than_deep(self):
        """FULL phải chứa MỌI suite của DEEP và nhiều hơn (không giảm
        kiểm tra khi nâng mức — hợp đồng 4 tầng)."""
        def suites(mode):
            return {s[0] for s in op.verify_steps(mode)
                    if s[0].startswith('scripts/factory/tests/')}
        deep, full = suites('deep'), suites('full')
        self.assertGreaterEqual(full, deep)
        self.assertGreater(full, deep)
        for extra in ('test_hardening.py', 'test_watchdog.py',
                      'test_soak_recovery.py'):
            self.assertIn('scripts/factory/tests/' + extra, full)
            self.assertNotIn('scripts/factory/tests/' + extra, deep)
        fast = suites('fast')
        self.assertGreaterEqual(deep, fast)

    def test_deep_maps_to_batch(self):
        steps = op.verify_steps('deep')
        self.assertEqual(steps[0],
                         ['scripts/factory/validate.py', '--scope', 'batch'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
