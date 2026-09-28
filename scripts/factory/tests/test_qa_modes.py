#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test QA modes (FAST/DEEP/FULL) + release-chunk + bất biến sản xuất thủ công.

Chạy: python3 scripts/factory/tests/test_qa_modes.py (từ gốc repository)

Chứng minh (docs/PROC-PUBLISH.md "QA modes"):
  - FAST (scope chunk) CHỈ kiểm chunk hiện tại + nền bắt buộc: một lỗi
    toàn site (URL legacy sai, hash QA bài PUBLISHED ngoài chunk) KHÔNG
    chặn FAST, nhưng DEEP/FULL phát hiện được.
  - FAST vẫn chấm đầy đủ từng bài (ngưỡng 90/90, legal, business facts)
    và VẪN publish được khi FULL audit FAIL (lỗi ngoài chunk).
  - release-chunk: pause an toàn — chỉ trả hàng WRITING chưa có draft;
    hàng có draft/QA evidence được giữ; PUBLISHED không bị hạ.
  - prepare-next: chặn khi còn hàng dở (resume-first), kẹp max 10.
  - lock O_EXCL chặn hai writer; recover hoàn tất transaction treo.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

IGNORE = shutil.ignore_patterns('.git', '_site', '.jekyll-cache', '__pycache__',
                                'node_modules', 'vendor', '*.pyc')


def run_py(args, cwd):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                       cwd=cwd)
    return r


def matrix_rows(fx):
    with open(os.path.join(fx, 'data/content-matrix.csv'), encoding='utf-8',
              newline='') as f:
        return list(csv.DictReader(f))


def save_matrix(fx, rows):
    with open(os.path.join(fx, 'data/content-matrix.csv'), 'w', encoding='utf-8',
              newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def cp_json(fx, rel):
    return json.load(open(os.path.join(fx, rel), encoding='utf-8'))


def write_json(fx, rel, obj):
    p = os.path.join(fx, rel)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def corrupt_legacy_url(fx):
    """Lỗi toàn site: đổi current_url của 1 bài legacy trong inventory."""
    p = os.path.join(fx, 'data/content-inventory.csv')
    rows = list(csv.DictReader(open(p, encoding='utf-8')))
    rows[0]['current_url'] = '/blog/kinh-nghiem/1999/01/01/sai-url-danh-roi/'
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def corrupt_published_qa_hash(fx, aid):
    p = os.path.join(fx, 'data/qa', aid + '.json')
    qa = json.load(open(p, encoding='utf-8'))
    qa['content_sha256'] = '0' * 64
    json.dump(qa, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)



def ensure_writing_chunk(fx):
    """Hermetic: nếu bản sao chưa có hàng WRITING (repo thật có thể đang
    PAUSED), claim chunk qua op chuẩn prepare-next để test có chunk làm việc."""
    rows = matrix_rows(fx)
    if any(r['status'] == 'WRITING' for r in rows):
        return matrix_rows(fx)
    r = run_py(['scripts/factory/factory-operator.py', 'prepare-next',
                '--count', '10'], fx)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-500:]
    return matrix_rows(fx)


def first_writing(fx):
    return next(r for r in matrix_rows(fx) if r['status'] == 'WRITING')


def first_published_planned(fx):
    return next(r for r in matrix_rows(fx)
                if r['status'] == 'PUBLISHED' and r['source'].startswith('planned:'))


# draft mẫu đạt gate cho hàng cho trước (word_target nhỏ để test gọn)
DRAFT_TMPL = """---
date: {date} 09:00:00 +0700
layout: post
title: "{title}"
author: "Nguyễn Tú"
description: "{desc}"
categories: [An toàn pháp lý]
lang: vi
tags: [{tag}]
permalink: {permalink}
parent_id: {parent_id}
child_id: {child_id}
article_id: {aid}
---

{kw} là câu hỏi của nhiều người đi xe máy quanh Hà Nội. Bài này tóm tắt
cách nhận biết trường hợp thiếu bảo hiểm và việc cần làm tiếp theo.

## {kw} theo quy định hiện hành

Khi bị kiểm tra trên đường ở khu vực Long Biên hoặc Hoàn Kiếm, người lái
xe cần xuất trình giấy chứng nhận bảo hiểm trách nhiệm dân sự còn hiệu
lực. Thiếu giấy này, cán bộ xử phạt sẽ lập biên bản theo quy định.

## Cần làm gì khi thiếu bảo hiểm

Bạn nên [xem chủ đề bảo hiểm](/blog/an-toan-phap-ly/bao-hiem/) và đối
chiếu [quy định giao thông](/blog/an-toan-phap-ly/quy-dinh-giao-thong/),
đồng thời quay lại [trang thuê xe](/blog/thue-xe/) để đọc nhóm bài liên
quan trước khi tiếp tục hành trình.

## Nguồn tham khảo

Văn bản chính thức: https://vanban.chinhphu.vn/?pageid=1

Lưu ý: mức phạt và quy định có thể thay đổi, kiểm tra văn bản mới nhất
trước khi áp dụng.
"""


def make_draft(fx, row):
    d = '2026-09-28'
    slug = row['output_path'][len('_posts/{date}-'):-3]
    desc = ('%s: cách xác định trường hợp thiếu bảo hiểm khi lưu thông ở Hà Nội, '
            'thủ tục cần làm và nguồn văn bản chính thức để đối chiếu.'
            % row['primary_keyword'])
    text = DRAFT_TMPL.format(
        date=d, title=row['title'], desc=desc, tag='bao-hiem',
        kw=row['primary_keyword'],
        permalink=row['canonical_url'].replace('{date}', '2026/09/28'),
        parent_id=row['parent_id'], child_id=row['child_id'], aid=row['id'])
    assert 140 <= len(desc) <= 160, len(desc)
    open(os.path.join(fx, '_drafts', '%s-%s.md' % (d, slug)), 'w',
         encoding='utf-8').write(text)
    return os.path.join(fx, '_drafts', '%s-%s.md' % (d, slug))


def set_word_target(fx, aid, n):
    rows = matrix_rows(fx)
    for r in rows:
        if r['id'] == aid:
            r['word_target'] = str(n)
    save_matrix(fx, rows)


class FxTestCase(unittest.TestCase):
    """Sao chép repository thật vào thư mục tạm cho MỖI test — mọi mutation
    xảy ra trên bản sao riêng, test độc lập với nhau."""

    def setUp(self):
        base = tempfile.mkdtemp(prefix='qa-modes-')
        self.fx = os.path.join(base, 'repo')
        shutil.copytree(ROOT, self.fx, ignore=IGNORE)
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)

    def py(self, *args):
        return run_py(list(args), self.fx)

    def validate(self, scope, ids=''):
        cmd = ['scripts/factory/validate.py', '--scope', scope]
        if ids:
            cmd += ['--ids', ids]
        return self.py(*cmd)

    def operator(self, *args):
        return self.py('scripts/factory/factory-operator.py', *args)


class TestScopeGating(FxTestCase):

    def test_sections_by_scope(self):
        r = self.validate('chunk')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('"scope": "chunk"', r.stdout)
        self.assertNotIn('"live_sitemap"', r.stdout)
        self.assertNotIn('"inventory_legacy_urls"', r.stdout)
        r = self.validate('batch')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('"inventory_legacy_urls"', r.stdout)
        self.assertNotIn('"live_sitemap"', r.stdout)
        r = self.validate('full')
        self.assertIn('"live_sitemap"', r.stdout)

    def test_site_wide_legacy_url_breaks_deep_and_full_not_fast(self):
        corrupt_legacy_url(self.fx)
        r = self.validate('chunk')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.validate('batch')
        self.assertEqual(r.returncode, 1)
        self.assertIn('URL legacy sai', r.stdout)
        r = self.validate('full')
        self.assertEqual(r.returncode, 1)

    def test_qa_evidence_outside_chunk_ignored_by_fast(self):
        pub = first_published_planned(self.fx)
        corrupt_published_qa_hash(self.fx, pub['id'])
        outside = next(r_['id'] for r_ in matrix_rows(self.fx)
                      if r_['status'] in ('PLANNED', 'WRITING'))
        # FAST (chunk, theo checkpoint chunk hiện tại) không kiểm bài ngoài chunk
        r = self.validate('chunk', outside)
        self.assertEqual(r.returncode, 0, r.stdout)
        # FAST khi bài đó nằm trong ids -> phải FAIL
        r = self.validate('chunk', pub['id'])
        self.assertEqual(r.returncode, 1)
        self.assertIn('content_sha256', r.stdout)
        # DEEP kiểm toàn bộ -> FAIL
        r = self.validate('batch')
        self.assertEqual(r.returncode, 1)

    def test_bad_scope_rejected(self):
        r = self.validate('khongtoncai')
        self.assertNotEqual(r.returncode, 0)


class TestReleaseChunk(FxTestCase):

    def setUp(self):
        super().setUp()
        self.before = ensure_writing_chunk(self.fx)

    def test_release_writing_rows_without_drafts(self):
        rows = matrix_rows(self.fx)
        writing = [r['id'] for r in rows if r['status'] == 'WRITING']
        self.assertEqual(len(writing), 10)
        r = self.operator('release-chunk')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = matrix_rows(self.fx)
        for aid in writing:
            self.assertEqual(next(x['status'] for x in rows if x['id'] == aid),
                             'PLANNED')
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        self.assertIsNone(cp['in_progress_chunk'])
        self.assertEqual(cp['next_claimable_id'], min(writing))
        planned_before = sum(1 for r_ in self.before if r_['status'] == 'PLANNED')
        writing_before = sum(1 for r_ in self.before if r_['status'] == 'WRITING')
        self.assertEqual(cp['counts']['planned'], planned_before + writing_before)
        self.assertEqual(cp['counts']['writing'], 0)

    def test_release_keeps_rows_with_drafts(self):
        rows = matrix_rows(self.fx)
        keep = first_writing(self.fx)
        make_draft(self.fx, keep)
        r = self.operator('release-chunk')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == keep['id']),
                         'WRITING')
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        self.assertEqual(cp['in_progress_chunk'], [keep['id']])

    def test_release_refuses_published(self):
        pub = first_published_planned(self.fx)
        r = self.operator('release-chunk', '--ids', pub['id'])
        self.assertEqual(r.returncode, 0)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == pub['id']),
                         'PUBLISHED')

    def test_published_not_regressed_by_qa(self):
        pub = first_published_planned(self.fx)
        r = self.operator('qa', '--ids', pub['id'])
        self.assertEqual(r.returncode, 0)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == pub['id']),
                         'PUBLISHED')


class TestManualProductionFlow(FxTestCase):

    def test_prepare_next_resumes_writing_first_and_clamps_10(self):
        ensure_writing_chunk(self.fx)
        # còn hàng WRITING -> từ chối nhận mới (resume-first)
        r = self.operator('prepare-next', '--count', '5')
        self.assertEqual(r.returncode, 1)
        self.assertIn('chưa xong', r.stdout)
        # release chunk để tiếp tục kẹp max
        self.assertEqual(self.operator('release-chunk').returncode, 0)
        r = self.operator('prepare-next', '--count', '15')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = matrix_rows(self.fx)
        self.assertEqual(len([x for x in rows if x['status'] == 'WRITING']), 10)
        cp = cp_json(self.fx, 'data/state/checkpoint.json')
        self.assertEqual(len(cp['in_progress_chunk']), 10)
        # next_claimable nhảy đúng: 10 ID đầu (theo thứ tự id)
        self.assertTrue(all(cp['next_claimable_id'] not in cp['in_progress_chunk']
                            for _ in [0]))

    def test_fast_qa_publishes_while_full_audit_fails(self):
        corrupt_legacy_url(self.fx)          # lỗi toàn site
        r = self.validate('full')
        self.assertEqual(r.returncode, 1)   # FULL phát hiện
        ensure_writing_chunk(self.fx)
        row = first_writing(self.fx)
        set_word_target(self.fx, row['id'], 100)
        make_draft(self.fx, row)
        r = self.operator('qa', '--scope', 'fast', '--ids', row['id'])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PASS', r.stdout)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == row['id']),
                         'PASS')
        r = self.operator('publish', '--scope', 'fast', '--ids', row['id'])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('PUBLISHED', r.stdout)
        # bài thật nằm trong _posts, hàng matrix chốt PUBLISHED, URL có ngày thật
        rows = matrix_rows(self.fx)
        m = next(x for x in rows if x['id'] == row['id'])
        self.assertEqual(m['status'], 'PUBLISHED')
        self.assertNotIn('{date}', m['expected_url'])
        self.assertTrue(os.path.exists(os.path.join(self.fx, m['output_path'])))

    def test_fast_qa_repair_when_seo_below_threshold(self):
        ensure_writing_chunk(self.fx)
        row = first_writing(self.fx)
        set_word_target(self.fx, row['id'], 100)
        p = make_draft(self.fx, row)
        # phá meta description (ngắn, thiếu từ khóa) -> seo < 90 -> REPAIR,
        # KHÔNG hạ ngưỡng
        text = open(p, encoding='utf-8').read()
        text = re.sub(r'^description: .*$', 'description: "ngắn"',
                      text, count=1, flags=re.M)
        open(p, 'w', encoding='utf-8').write(text)
        r = self.operator('qa', '--scope', 'fast', '--ids', row['id'])
        self.assertEqual(r.returncode, 0)
        self.assertIn('REPAIR', r.stdout)
        rows = matrix_rows(self.fx)
        self.assertEqual(next(x['status'] for x in rows if x['id'] == row['id']),
                         'REPAIR')

    def test_threshold_constants_unchanged(self):
        self.assertEqual(op_mod().SEO_MIN, 90)
        self.assertEqual(op_mod().QUALITY_MIN, 90)
        self.assertEqual(op_mod().MAX_CHUNK, 10)

    def test_lock_blocks_second_writer(self):
        code = (
            "import importlib.util, os\n"
            "spec = importlib.util.spec_from_file_location('pg', "
            "'scripts/factory/publish-gate.py')\n"
            "pg = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(pg)\n"
            "r1 = pg.acquire_lock('test-writer-1')\n"
            "print('first-ok')\n"
            "try:\n"
            "    pg.acquire_lock('test-writer-2')\n"
            "    raise SystemExit('writer-2 duoc phep: SAI')\n"
            "except SystemExit as e:\n"
            "    if 'SAI' in str(e):\n"
            "        raise\n"
            "    print('writer-2 bi chan: OK')\n"
            "finally:\n"
            "    r1()\n"
        )
        r = subprocess.run([sys.executable, '-c', code], capture_output=True,
                           text=True, cwd=self.fx)
        self.assertIn('first-ok', r.stdout)
        self.assertIn('writer-2 bi chan: OK', r.stdout)
        # lock đã được nhả sạch sau test
        self.assertFalse(os.path.exists(os.path.join(
            self.fx, 'data/state/writer-lock.active')))

    def test_recover_completes_hanging_transaction(self):
        pub = first_published_planned(self.fx)
        txn = cp_json(self.fx, 'data/state/transaction.json')
        txn['active'] = True
        txn['pending'] = {'article_id': pub['id'], 'step': 'promote',
                          'destination': pub['output_path'],
                          'source': '_drafts/2026-09-27-x.md'}
        write_json(self.fx, 'data/state/transaction.json', txn)
        r = self.operator('recover')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('transaction hoàn tất', r.stdout)
        txn = cp_json(self.fx, 'data/state/transaction.json')
        self.assertFalse(txn['active'])
        last = next((h for h in reversed(txn.get('history') or []) if h), None)
        self.assertIsNotNone(last)
        self.assertEqual(last.get('result'), 'RECOVERED_COMPLETED')


def op_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'factory_operator_test', os.path.join(ROOT, 'scripts/factory/factory-operator.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


if __name__ == '__main__':
    unittest.main(verbosity=2)
