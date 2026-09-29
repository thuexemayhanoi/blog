#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đường thành công CÔ LẬP: draft đạt QA -> PASS -> publish -> xác minh
toàn bộ hậu kỳ (matrix/checkpoint/route-sitemap/hash/draft xử lý đúng).

Mọi mutation trên bản sao tạm của repository (FxTestCase của
test_qa_modes.py); không đụng production, không hạ ngưỡng QA.

Xác minh sau publish:
 - hàng matrix: PASS -> PUBLISHED, expected_url/output_path có ngày thật
 - draft: ĐÃ RỜI _drafts (gate move) và bài thật nằm đúng _posts/<date>-<slug>.md
 - hash: sha256 bài xuất bản == qa.content_sha256 (bằng chứng QA gắn với
   nội dung thật), qa.matrix_row_sha256 có mặt
 - checkpoint: in_progress_chunk chốt (None), last_completed_article_id
   đúng bài, counts.published tăng đúng 1, WRITING về 0
 - route/sitemap: URL công khai của bài nằm trong route truth mà sitemap
   phục vụ (link_route_ok PASS với URL percent-encoded)
 - QA evidence giữ nguyên sau publish (không bị xóa, không bị sửa)

Chạy: python3 scripts/factory/tests/test_publish_flow.py
"""
import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print('::notice::[diag] pubflow: start', flush=True)
from test_qa_modes import (FxTestCase, cp_json, first_writing, make_draft,
                            matrix_rows)


def sha256_file(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def op_module(fx):
    """Nạp factory-operator.py của FIXTURE (không phải của repo thật)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'factory_operator_flow', os.path.join(fx, 'scripts/factory/factory-operator.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.BASEURL = m._site_baseurl()
    return m


class SuccessFlowTest(FxTestCase):

    def test_draft_pass_qa_then_publish_verifies_everything(self):
        # 1. chunk 1 hàng, hoàn toàn do fixture tạo (hermetic)
        self.ensure_writing_chunk(count=1)
        row = first_writing(self.fx)
        self.assertEqual(row['status'], 'WRITING')
        published_before = sum(1 for r in matrix_rows(self.fx)
                               if r['status'] == 'PUBLISHED')
        cp_before = cp_json(self.fx, 'data/state/checkpoint.json')
        print('::notice::[diag] pubflow step1 ok', flush=True)

        # 2. writer giao draft đạt chuẩn -> QA FAST chấm
        draft_path = make_draft(self.fx, row)
        self.assertTrue(os.path.exists(draft_path))
        r = self.operator('qa', '--scope', 'fast', '--ids', row['id'])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PASS', r.stdout)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == row['id']),
                         'PASS')
        print('::notice::[diag] pubflow step2 ok', flush=True)

        # 3. bằng chứng QA: hash nội dung + vân tay hàng (gate sẽ gắn lại)
        ev_path = os.path.join(self.fx, 'data', 'qa', row['id'] + '.json')
        ev = json.load(open(ev_path, encoding='utf-8'))
        self.assertEqual(ev.get('result'), 'PASS')
        self.assertTrue(ev.get('content_sha256'))
        self.assertTrue(ev.get('matrix_row_sha256'))
        self.assertEqual(ev['content_sha256'], sha256_file(draft_path))
        print('::notice::[diag] pubflow step3 ok', flush=True)

        # 4. publish đúng quy trình (chỉ promote hàng PASS, gate tự kiểm)
        r = self.operator('publish', '--scope', 'fast', '--ids', row['id'])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PUBLISHED', r.stdout)
        print('::notice::[diag] pubflow step4 ok', flush=True)

        # 5. draft đã được xử lý: rời _drafts, bài thật vào _posts đúng chỗ
        self.assertFalse(os.path.exists(draft_path),
                         'draft vẫn còn trong _drafts sau publish')
        rows = matrix_rows(self.fx)
        m = next(x for x in rows if x['id'] == row['id'])
        self.assertEqual(m['status'], 'PUBLISHED')
        self.assertNotIn('{date}', m['expected_url'])
        self.assertNotIn('{date}', m['output_path'])
        post_path = os.path.join(self.fx, m['output_path'])
        self.assertTrue(os.path.exists(post_path),
                        'thiếu bài thật tại %s' % m['output_path'])
        print('::notice::[diag] pubflow step5 ok', flush=True)

        # 6. hash: bài xuất bản KHÔNG đổi nội dung sau QA
        self.assertEqual(sha256_file(post_path), ev['content_sha256'],
                         'nội dung bài xuất bản lệch bằng chứng QA')
        # bằng chứng QA giữ nguyên sau publish
        ev_after = json.load(open(ev_path, encoding='utf-8'))
        self.assertEqual(ev_after['content_sha256'], ev['content_sha256'])
        print('::notice::[diag] pubflow step6 ok', flush=True)

        # 7. checkpoint: chunk chốt, đếm đúng, last_completed đúng bài
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        self.assertIsNone(cp['in_progress_chunk'])
        self.assertEqual(cp['last_completed_article_id'], row['id'])
        self.assertEqual(cp['counts']['published'],
                         cp_before['counts']['published'] + 1)
        self.assertEqual(cp['counts']['published'], published_before + 1)
        self.assertEqual(cp['counts']['writing'], 0)
        print('::notice::[diag] pubflow step7 ok', flush=True)

        # 8. route/sitemap: URL công khai của bài nằm trong route truth
        op = op_module(self.fx)
        url = op.public_url(m['expected_url'])
        self.assertNotIn(' ', url)
        self.assertIs(op.link_route_ok(url), True,
                      'URL bài mới không nằm trong route truth (sitemap)')
        import urllib.parse
        route = urllib.parse.unquote(url)
        if not route.endswith('/'):
            route += '/'
        self.assertIn(route, op.canonical_routes())
        print('::notice::[diag] pubflow step8 ok', flush=True)


if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules['__main__'])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        for t, tb in (result.errors + result.failures):
            flat = tb[-1400:].replace('\r', '').replace('\n', ' | ')
            for k in range(0, len(flat), 650):
                print('::notice::[diag] pubflow %s p%d: %s'
                      % (t, k // 650, flat[k:k + 650]), flush=True)
        sys.exit(1)
