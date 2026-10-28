#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test retire-slug-stubs.py (gỡ trang chuyển hướng URL cũ, quyết định chủ 2026-10-27) — OFFLINE, repo tạm.

Chứng minh:
  R1  plan/apply/verify/rollback: chỉ dòng MIGRATED đủ điều kiện được gỡ; apply ghi sao lưu (đọc lại) TRƯỚC khi xóa trang chuyển hướng
      và đổi status -> RETIRED; nguồn vẫn sạch sau apply; rollback trả byte-exact (trang chuyển hướng + status MIGRATED).
  R2  còn liên kết tới URL cũ (kể cả thiếu '/' cuối) => BLOCKED_STILL_LINKED, apply từ chối và KHÔNG ghi gì.
  R3  thiếu --approval-ref / --live-ref, trang chuyển hướng bị sửa tay (nguồn không sạch), batch-id trùng => từ chối.
  R4  sau apply, liên kết mới tới URL đã gỡ bị verify và slug_redirects.source_errors bắt; rollback không đè thay đổi sau apply.
"""
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'factory'))
import slug_redirects as SR  # noqa: E402
import slugkit  # noqa: E402

spec = importlib.util.spec_from_file_location('retire_t', os.path.join(ROOT, 'scripts/factory/retire-slug-stubs.py'))
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

APPROVAL = 'chu-repo:test-approval-2026-10-27'
LIVE = 'factory-liveness run 1 stub_check all_ok (test)'


def reg_entry(aid):
    b = SR.load_baseline()[aid]
    return {'article_id': aid, 'title': b['title'], 'old_url': b['old_url'], 'new_url': b['new_url'],
            'old_slug': slugkit.split_date_prefix(b['old_slug'])[1], 'new_slug': slugkit.split_date_prefix(b['new_slug'])[1],
            'old_output_path': b['old_output_path'], 'new_output_path': b['new_output_path'], 'status': SR.MIGRATED,
            'batch_id': 't', 'migrated_at': ''}


def make_root(entries):
    root = tempfile.mkdtemp(prefix='retire-')
    for d in ('reports/factory/seo-master', 'data/qa', '_posts'):
        os.makedirs(os.path.join(root, d))
    shutil.copy(os.path.join(ROOT, SR.BASELINE_REL), os.path.join(root, SR.BASELINE_REL))
    with open(os.path.join(root, SR.REGISTRY_REL), 'w', encoding='utf-8', newline='') as f:
        f.write(SR.registry_text(entries))
    for rel, text in SR.expected_stub_files(root).items():
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        with open(os.path.join(root, rel), 'w', encoding='utf-8') as f:
            f.write(text)
    cols = ['id', 'status', 'source', 'title', 'slug', 'expected_url', 'canonical_url', 'output_path']
    with open(os.path.join(root, 'data/content-matrix.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator='\n')
        w.writeheader()
        for e in entries:
            w.writerow({'id': e['article_id'], 'status': 'PUBLISHED', 'source': 'planned:t', 'title': e['title'],
                        'slug': e['new_slug'], 'expected_url': e['new_url'], 'canonical_url': e['new_url'],
                        'output_path': e['new_output_path']})
    for e in entries:
        body = '---\npermalink: %s\n---\nnoi dung\n' % e['new_url']
        with open(os.path.join(root, e['new_output_path']), 'w', encoding='utf-8') as f:
            f.write(body)
        ev = {'source_path': e['new_output_path'], 'content_sha256': hashlib.sha256(body.encode()).hexdigest(),
              'revision': {'kind': 'permalink-migration', 'new_url': e['new_url']}}
        with open(os.path.join(root, 'data/qa/%s.json' % e['article_id']), 'w', encoding='utf-8') as f:
            json.dump(ev, f)
    return root


def read(root, rel):
    with open(os.path.join(root, rel), 'rb') as f:
        return f.read()


class RetireTest(unittest.TestCase):

    def setUp(self):
        ids = sorted(SR.load_baseline())[:2]
        self.a, self.b = reg_entry(ids[0]), reg_entry(ids[1])
        self.root = make_root([self.a, self.b])

    def tearDown(self):
        shutil.rmtree(self.root, True)

    def stub(self, e):
        return os.path.join(self.root, SR.stub_relpath(e['article_id']))

    def apply(self, ids, **kw):
        return T.apply_batch(self.root, ids, kw.get('approval', APPROVAL), kw.get('live', LIVE), kw.get('batch', 'retire-t1'))

    def link(self, url, name='z.md'):
        with open(os.path.join(self.root, '_posts', name), 'w', encoding='utf-8') as f:
            f.write('xem [bai](%s) nhe\n' % url)

    def test_plan_apply_verify_rollback(self):
        plan = T.make_plan(self.root)
        self.assertEqual(plan['eligible'], sorted([self.a['article_id'], self.b['article_id']]))
        self.assertEqual(plan['source_error_count'], 0)
        reg_before = read(self.root, SR.REGISTRY_REL)
        out = self.apply([self.a['article_id']])
        self.assertTrue(out['ok'])
        self.assertFalse(os.path.exists(self.stub(self.a)))
        self.assertTrue(os.path.exists(self.stub(self.b)))
        rows = {r['article_id']: r for r in SR.load_registry(self.root)}
        self.assertEqual((rows[self.a['article_id']]['status'], rows[self.b['article_id']]['status']), (SR.RETIRED, SR.MIGRATED))
        self.assertEqual(SR.source_errors(self.root), [])
        backup = json.loads(read(self.root, 'reports/qa-audit/retire/retire-t1.json'))
        self.assertEqual((backup['approval_ref'], backup['live_ref']), (APPROVAL, LIVE))
        self.assertEqual(backup['entries'][self.a['article_id']]['stub_text'], SR.stub_source(self.a))
        self.assertEqual(T.verify_backup(self.root, backup), [])
        self.assertEqual(T.make_plan(self.root)['eligible'], [self.b['article_id']])              # mặc định: chỉ dòng MIGRATED
        self.assertEqual(T.make_plan(self.root, [self.a['article_id']])['excluded'][self.a['article_id']]['decision'],
                         'NOT_MIGRATED')
        rb = T.rollback_backup(self.root, backup)
        self.assertEqual(rb['restored'], [self.a['article_id']])
        self.assertEqual(read(self.root, SR.REGISTRY_REL), reg_before)
        self.assertEqual(SR.source_errors(self.root), [])

    def test_still_linked_is_refused_and_nothing_written(self):
        self.link(self.a['old_url'].rstrip('/'))
        plan = T.make_plan(self.root)
        self.assertEqual(plan['excluded'][self.a['article_id']]['decision'], 'BLOCKED_STILL_LINKED')
        self.assertIn('_posts/z.md', plan['excluded'][self.a['article_id']]['reason'])
        self.assertEqual(plan['eligible'], [self.b['article_id']])
        reg_before = read(self.root, SR.REGISTRY_REL)
        with self.assertRaises(T.Refuse) as cm:
            self.apply([self.a['article_id'], self.b['article_id']])
        self.assertEqual(cm.exception.code, 'NOT_ELIGIBLE')
        self.assertEqual(read(self.root, SR.REGISTRY_REL), reg_before)
        self.assertTrue(os.path.exists(self.stub(self.a)) and os.path.exists(self.stub(self.b)))
        self.assertFalse(os.path.exists(os.path.join(self.root, 'reports/qa-audit/retire')))

    def test_queued_draft_link_blocks_retirement_and_hand_retire_is_caught(self):
        os.makedirs(os.path.join(self.root, '_drafts'))
        with open(os.path.join(self.root, '_drafts', 'nhap.md'), 'w', encoding='utf-8') as f:
            f.write("xem [bai]({{ '%s' | relative_url }})\n" % self.a['old_url'])
        plan = T.make_plan(self.root)
        self.assertEqual(plan['excluded'][self.a['article_id']]['decision'], 'BLOCKED_STILL_LINKED')
        self.assertIn('_drafts/nhap.md', plan['excluded'][self.a['article_id']]['reason'])
        shutil.rmtree(os.path.join(self.root, '_drafts'))
        rows = SR.load_registry(self.root)                       # gỡ tay: đổi status + xóa trang, không qua công cụ
        for r in rows:
            if r['article_id'] == self.b['article_id']:
                r['status'] = SR.RETIRED
        with open(os.path.join(self.root, SR.REGISTRY_REL), 'w', encoding='utf-8') as f:
            f.write(SR.registry_text(rows))
        os.remove(self.stub(self.b))
        self.assertTrue(any(self.b['article_id'] in e and 'không có sao lưu' in e for e in SR.source_errors(self.root)))

    def test_rollback_resumes_after_interruption_and_all_eligible_is_capped(self):
        self.apply([self.a['article_id'], self.b['article_id']])
        backup = json.loads(read(self.root, 'reports/qa-audit/retire/retire-t1.json'))
        with open(self.stub(self.a), 'w', encoding='utf-8') as f:          # rollback bị ngắt sau khi đã ghi lại trang A
            f.write(backup['entries'][self.a['article_id']]['stub_text'])
        rb = T.rollback_backup(self.root, backup)
        self.assertEqual(sorted(rb['restored']), sorted([self.a['article_id'], self.b['article_id']]))
        self.assertEqual(SR.source_errors(self.root), [])
        rb = T.rollback_backup(self.root, backup)                         # chạy lại: không còn gì để làm, không lỗi
        self.assertEqual((rb['restored'], rb['skipped_changed_since_apply']), ([], []))
        self.assertEqual(len(rb['already_restored']), 2)
        old_max, old_clean, cwd_root = T.MAX_BATCH, T.require_clean_tree, T.ROOT
        try:                                                              # --all-eligible lấy MAX_BATCH ID đầu, không từ chối cả lô
            T.MAX_BATCH = 1
            T.ROOT = __import__('pathlib').Path(self.root)
            T.require_clean_tree = lambda root: None
            self.assertEqual(T.main(['apply', '--all-eligible', '--approval-ref', APPROVAL, '--live-ref', LIVE,
                                     '--batch-id', 'retire-t9']), 0)
            rows = {r['article_id']: r['status'] for r in SR.load_registry(self.root)}
            self.assertEqual(sorted(rows.values()), [SR.MIGRATED, SR.RETIRED])
        finally:
            T.MAX_BATCH, T.ROOT, T.require_clean_tree = old_max, cwd_root, old_clean

    def test_failed_apply_leaves_no_backup_evidence(self):
        real = T.atomic_write
        calls = {'n': 0}

        def flaky(path, data):
            calls['n'] += 1
            if str(path).endswith(SR.REGISTRY_REL) and calls['n'] == 2:     # lần ghi registry đầu tiên (sau sao lưu) hỏng
                raise OSError('disk full')
            return real(path, data)
        T.atomic_write = flaky
        try:
            with self.assertRaises(OSError):
                self.apply([self.a['article_id']])
        finally:
            T.atomic_write = real
        self.assertTrue(os.path.exists(self.stub(self.a)))
        self.assertFalse(os.path.exists(os.path.join(self.root, 'reports/qa-audit/retire/retire-t1.json')))
        self.assertTrue(os.path.exists(os.path.join(self.root, 'reports/qa-audit/retire/retire-t1.json.aborted')))
        self.assertEqual(SR.source_errors(self.root), [])
        self.assertTrue(self.apply([self.a['article_id']])['ok'])           # chạy lại cùng batch-id được

    def test_refusals(self):
        for kw, code in (({'approval': ''}, 'NO_APPROVAL'), ({'live': ' '}, 'NO_LIVE_EVIDENCE'),
                         ({'batch': '../x'}, 'BAD_BATCH_ID')):
            with self.assertRaises(T.Refuse) as cm:
                self.apply([self.a['article_id']], **kw)
            self.assertEqual(cm.exception.code, code)
        with open(self.stub(self.a), 'a', encoding='utf-8') as f:
            f.write('<script>x</script>\n')
        self.assertEqual(T.make_plan(self.root)['excluded'][self.a['article_id']]['decision'], 'STUB_MISMATCH')
        with self.assertRaises(T.Refuse) as cm:
            self.apply([self.b['article_id']])
        self.assertEqual(cm.exception.code, 'SOURCE_NOT_CLEAN')

    def test_backup_exists_and_unknown_ids(self):
        self.apply([self.a['article_id']])
        with self.assertRaises(T.Refuse) as cm:
            self.apply([self.b['article_id']])
        self.assertEqual(cm.exception.code, 'BACKUP_EXISTS')
        with self.assertRaises(T.Refuse) as cm:
            self.apply(['BLG-99999'], batch='retire-t2')
        self.assertEqual(cm.exception.code, 'UNKNOWN_IDS')

    def test_new_link_to_retired_url_is_caught_and_rollback_does_not_clobber(self):
        self.apply([self.a['article_id']])
        backup = json.loads(read(self.root, 'reports/qa-audit/retire/retire-t1.json'))
        self.link(self.a['old_url'], 'moi.md')
        self.assertTrue(any('con lien ket' in p for p in T.verify_backup(self.root, backup)))
        self.assertTrue(any('ĐÃ GỠ' in e for e in SR.source_errors(self.root)))
        os.remove(os.path.join(self.root, '_posts', 'moi.md'))
        with open(self.stub(self.a), 'w', encoding='utf-8') as f:          # ai đó đã tạo lại tệp sau apply
            f.write('khac\n')
        rb = T.rollback_backup(self.root, backup)
        self.assertEqual((rb['restored'], rb['skipped_changed_since_apply']), ([], [self.a['article_id']]))
        with open(self.stub(self.a), encoding='utf-8') as f:
            self.assertEqual(f.read(), 'khac\n')


if __name__ == '__main__':
    unittest.main()
