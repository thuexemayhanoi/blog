#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test slugify tiếng Việt (chữ "đ") + bất biến "URL đã sinh không đổi".

Sự cố (audit SEO 2026-10-12): slugify() dùng norm() (NFD rồi bỏ dấu kết hợp). "đ" KHÔNG có dạng phân rã NFD
nên bị xoá: "xe đạp điện" -> "xe-ap-ien". 1.371/1.371 bài factory có "đ" trong title bị sai slug. Sửa: đổi đ -> d
trước khi chuẩn hoá, ở CẢ HAI bản (generate-matrix.py và refill-queue.py), và KHÔNG đổi norm() (khoá trùng).

Chứng minh:
  S1  slugify đúng với đ/Đ, dấu thanh, dấu câu, cắt 80 ký tự; hai bản (generator/refill) cho CÙNG kết quả;
  S2  norm() không đổi (khoá trùng/cannibalization không trượt);
  S3  tái sinh matrix trên dữ liệu đã commit KHÔNG đổi byte nào (hàng PLANNED/PUBLISHED giữ slug+URL cũ, kể cả
      cột `slug` — cột này nằm trong hàng mà bằng chứng QA ràng buộc);
  S4  hàng MỚI (thêm vào seed) nhận slug đúng, các hàng cũ vẫn nguyên;
  S5  bất biến dữ liệu thật: cột `slug` == slug trong output_path với mọi hàng PLANNED/PUBLISHED.

Chạy: python3 scripts/factory/tests/test_slugify_vi.py (từ gốc repository)
"""
import csv
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    cwd = os.getcwd()
    try:
        spec.loader.exec_module(m)
    finally:
        os.chdir(cwd)  # refill-queue.py chdir về ROOT lúc import
    return m


GEN = load('gen_matrix_t', 'scripts/factory/generate-matrix.py')
REF = load('refill_queue_t', 'scripts/factory/refill-queue.py')

CASES = [
    ('xe đạp điện', 'xe-dap-dien'),
    ('Thuê xe đạp điện ở Đống Đa', 'thue-xe-dap-dien-o-dong-da'),
    ('ĐÀ NẴNG - ĐÀ LẠT', 'da-nang-da-lat'),
    ('Giá thuê xe máy điện ở Hà Nội', 'gia-thue-xe-may-dien-o-ha-noi'),
    ('Đặt xe máy trước qua điện thoại hoặc Zalo', 'dat-xe-may-truoc-qua-dien-thoai-hoac-zalo'),
    ('Thủ tục thuê xe máy: cần gì? (2026)', 'thu-tuc-thue-xe-may-can-gi-2026'),
    ('  Xe   ga  ', 'xe-ga'),
    ('đ', 'd'),
]


class TestSlugify(unittest.TestCase):

    def test_cases_both_implementations(self):
        for title, want in CASES:
            self.assertEqual(GEN.slugify(title), want, title)
            self.assertEqual(REF.slugify(title), want, title)

    def test_cut_at_80_without_trailing_dash(self):
        t = 'đ' * 5 + ' ' + 'điện ' * 40
        a, b = GEN.slugify(t), REF.slugify(t)
        self.assertEqual(a, b)
        self.assertLessEqual(len(a), 80)
        self.assertFalse(a.endswith('-') or a.startswith('-'))
        self.assertTrue(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', a))

    def test_implementations_agree_on_random_vietnamese(self):
        rnd = random.Random(20261012)
        alphabet = list('aăâeêioôơuưyđĐAĂÂEÊIOÔƠUƯYàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ'
                        'bcdfghklmnpqrstvxz  ,.:;()-0123456789')
        for _ in range(500):
            s = ''.join(rnd.choice(alphabet) for _ in range(rnd.randint(1, 120)))
            a, b = GEN.slugify(s), REF.slugify(s)
            self.assertEqual(a, b, repr(s))
            self.assertTrue(re.fullmatch(r'(?:[a-z0-9]+(?:-[a-z0-9]+)*)?', a), (s, a))

    def test_norm_is_unchanged(self):
        """norm() là khoá trùng/cannibalization: KHÔNG được đổi cùng slugify (sẽ trượt khoá của cả matrix)."""
        self.assertEqual(GEN.norm('Xe đạp điện'), 'xe ap ien')
        self.assertEqual(REF.norm('Xe đạp điện'), 'xe ap ien')


class TestGeneratorInvariant(unittest.TestCase):
    """Chạy generate-matrix.py trên BẢN SAO tối thiểu của repo (production không bị đụng)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='slugify-test-')
        cls.work = os.path.join(cls.tmp, 'repo')
        os.makedirs(cls.work)
        shutil.copytree(os.path.join(ROOT, 'data'), os.path.join(cls.work, 'data'))
        shutil.copytree(os.path.join(ROOT, 'scripts'), os.path.join(cls.work, 'scripts'))
        os.makedirs(os.path.join(cls.work, '_posts'))
        for fn in os.listdir(os.path.join(ROOT, '_posts')):
            if fn.endswith('.md'):
                shutil.copy(os.path.join(ROOT, '_posts', fn), os.path.join(cls.work, '_posts', fn))
        os.makedirs(os.path.join(cls.work, 'reports/factory'))
        for fn in os.listdir(os.path.join(ROOT, 'reports/factory')):
            src = os.path.join(ROOT, 'reports/factory', fn)
            if not os.path.isdir(src):
                shutil.copy(src, os.path.join(cls.work, 'reports/factory', fn))
        os.makedirs(os.path.join(cls.work, '_data'))
        cls.matrix = os.path.join(cls.work, 'data/content-matrix.csv')
        with open(cls.matrix, 'rb') as f:
            cls.matrix_before = f.read()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def gen(self):
        r = subprocess.run([sys.executable, 'scripts/factory/generate-matrix.py'], cwd=self.work,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def rows(self):
        with open(self.matrix, encoding='utf-8', newline='') as f:
            return list(csv.DictReader(f))

    def restore(self):
        with open(self.matrix, 'wb') as f:
            f.write(self.matrix_before)

    def test_s3_regeneration_changes_nothing(self):
        self.restore()
        self.gen()
        with open(self.matrix, 'rb') as f:
            self.assertEqual(f.read(), self.matrix_before,
                             'tái sinh matrix trên dữ liệu đã commit phải byte-identical (slug/URL cũ được giữ)')

    def test_s3b_defective_slugs_are_kept_for_planned_and_published(self):
        self.restore()
        before = {r['id']: (r['slug'], r['expected_url'], r['output_path'], r['canonical_url']) for r in self.rows()}
        self.gen()
        after = {r['id']: (r['slug'], r['expected_url'], r['output_path'], r['canonical_url']) for r in self.rows()}
        self.assertEqual(before, after)
        # các slug đang giữ (kể cả slug cũ thiếu chữ "đ") vẫn là slug hợp lệ a-z0-9-
        invalid = [i for i, r in ((r['id'], r) for r in self.rows())
                   if r['status'] in ('PLANNED', 'PUBLISHED')
                   and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', r['slug'])]
        self.assertEqual(invalid, [])

    def test_s4_new_seed_row_gets_fixed_slug(self):
        self.restore()
        seed_path = os.path.join(self.work, 'data/state/matrix-seed.json')
        with open(seed_path, encoding='utf-8') as f:
            seed = json.load(f)
        cid = 'C-THUE-GIA'
        title = 'Thuê xe đạp điện ở Đống Đa: giá và điều kiện cần hỏi'
        seed['children'][cid]['rows'].append({
            'title': title, 'intent': 'Biết cần hỏi gì khi thuê xe đạp điện ở Đống Đa', 'kw': 'thuê xe đạp điện đống đa',
            'kw2': ['xe đạp điện đống đa'], 'links': ['/thue-xe/gia-thue/'], 'subtopic': 'slug-test',
            'audience': 'Khách mới', 'word_target': 1200})
        with open(seed_path, 'w', encoding='utf-8') as f:
            json.dump(seed, f, ensure_ascii=False, indent=1)
        before = {r['id']: r for r in self.rows()}
        self.gen()
        after = {r['id']: r for r in self.rows()}
        new = [r for i, r in after.items() if i not in before]
        self.assertEqual(len(new), 1)
        r = new[0]
        want = 'thue-xe-dap-dien-o-dong-da-gia-va-dieu-kien-can-hoi'
        self.assertEqual(r['slug'], want)
        self.assertTrue(r['output_path'].endswith('{date}-%s.md' % want), r['output_path'])
        self.assertIn('/%s/' % want, r['canonical_url'])
        for i, old in before.items():
            self.assertEqual(after[i], old, 'hàng cũ %s bị đổi' % i)
        self.restore()


def old_slugify(title):
    """slugify TRƯỚC bản sửa: norm() xoá "đ" nên "xe đạp điện" -> "xe-ap-ien" (dùng dựng lại trạng thái trước migration)."""
    return re.sub(r'\s+', '-', GEN.norm(title))[:80].strip('-')


class TestReslugFlag(unittest.TestCase):
    """--reslug-planned-after: một lần, có kiểm soát, fail-closed (chạy trên bản sao, production không bị đụng).

    Matrix thật đã được re-slug bằng đợt riêng (PR #21) nên KHÔNG còn hàng PLANNED slug cũ-lỗi để thử cờ; và registry thật
    đổi theo tiến độ factory. Vì vậy fixture được DỰNG LẠI trên bản sao: (1) ranh giới = lease lớn nhất của registry bản sao
    + 100 (luôn >= +40 theo đúng luật của công cụ), (2) hàng PLANNED sau ranh giới có chữ đ lấy lại slug CŨ (đã mất đ) —
    đúng trạng thái trước migration. Không test nào còn phụ thuộc vào việc matrix thật có/không còn hàng lỗi."""

    BOUNDARY = 'BLG-02600'   # ghi đè ở setUpClass theo registry bản sao (giá trị này chỉ là mặc định)
    MIN_DEGRADED = 10

    @staticmethod
    def _csv_write(path, fieldnames, rows):
        with open(path, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator='\n')
            w.writeheader()
            w.writerows(rows)

    @classmethod
    def setUpClass(cls):
        cls.base = TestGeneratorInvariant
        cls.base.setUpClass()
        cls.work, cls.matrix = cls.base.work, cls.base.matrix
        cls.registry = os.path.join(cls.work, 'data/state/writer-claims.json')
        with open(cls.registry, 'rb') as f:
            cls.registry_before = f.read()
        reg = json.loads(cls.registry_before.decode('utf-8'))
        leased = [int(i[4:]) for lease in (reg.get('leases') or {}).values() for i in (lease.get('ids') or [])]
        cls.BOUNDARY = 'BLG-%05d' % (max(leased + [2504]) + 100)
        cls._degrade_far_planned_rows()

    @classmethod
    def _degrade_far_planned_rows(cls):
        with open(cls.matrix, encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            fields, rows = reader.fieldnames, list(reader)
        b = int(cls.BOUNDARY[4:])
        degraded = 0
        for r in rows:
            if r['status'] != 'PLANNED' or int(r['id'][4:]) <= b:
                continue
            new, old = r['slug'], old_slugify(r['title'])
            if old == new:
                continue
            r['slug'] = old
            for col in ('expected_url', 'canonical_url'):
                head, sep, tail = r[col].rpartition('/%s/' % new)
                if sep:
                    r[col] = head + '/%s/' % old + tail
            head, sep, tail = r['output_path'].rpartition('{date}-%s.md' % new)
            if sep:
                r['output_path'] = head + '{date}-%s.md' % old + tail
            degraded += 1
        assert degraded >= cls.MIN_DEGRADED, 'fixture cần >= %d hàng PLANNED có chữ đ sau ranh giới %s (có %d)' % (
            cls.MIN_DEGRADED, cls.BOUNDARY, degraded)
        cls._csv_write(cls.matrix, fields, rows)
        with open(cls.matrix, 'rb') as f:
            cls.base.matrix_before = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.base.tearDownClass()

    def setUp(self):
        with open(self.matrix, 'wb') as f:
            f.write(self.base.matrix_before)
        with open(self.registry, 'wb') as f:
            f.write(self.registry_before)
        drafts = os.path.join(self.work, '_drafts')
        shutil.rmtree(drafts, True)

    def run_gen(self, *args):
        return subprocess.run([sys.executable, 'scripts/factory/generate-matrix.py'] + list(args), cwd=self.work,
                              capture_output=True, text=True)

    def rows(self):
        with open(self.matrix, encoding='utf-8', newline='') as f:
            return {r['id']: r for r in csv.DictReader(f)}

    def matrix_bytes(self):
        with open(self.matrix, 'rb') as f:
            return f.read()

    def test_happy_path_only_url_columns_of_far_planned_rows_change(self):
        before = self.rows()
        r = self.run_gen('--reslug-planned-after', self.BOUNDARY)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        after = self.rows()
        self.assertEqual(set(before), set(after))
        b = int(self.BOUNDARY[4:])
        changed = [i for i in before if before[i] != after[i]]
        self.assertGreaterEqual(len(changed), self.MIN_DEGRADED, 'phải có nhiều hàng PLANNED có chữ đ được sửa')
        for i in changed:
            self.assertEqual(before[i]['status'], 'PLANNED')
            self.assertGreater(int(i[4:]), b)
            for col in before[i]:
                if col in ('slug', 'expected_url', 'output_path', 'canonical_url'):
                    continue
                self.assertEqual(before[i][col], after[i][col], '%s.%s' % (i, col))
            self.assertEqual(after[i]['slug'], GEN.slugify(after[i]['title']))
            self.assertTrue(after[i]['output_path'].endswith('{date}-%s.md' % after[i]['slug']))
            self.assertEqual(after[i]['expected_url'], after[i]['canonical_url'])
            self.assertIn('/%s/' % after[i]['slug'], after[i]['canonical_url'])
        for i in before:
            if int(i[4:]) <= b or before[i]['status'] != 'PLANNED':
                self.assertEqual(before[i], after[i], 'hàng ngoài phạm vi bị đổi: %s' % i)

    def test_idempotent_and_followed_by_plain_regeneration(self):
        self.assertEqual(self.run_gen('--reslug-planned-after', self.BOUNDARY).returncode, 0)
        first = self.matrix_bytes()
        self.assertEqual(self.run_gen('--reslug-planned-after', self.BOUNDARY).returncode, 0)
        self.assertEqual(self.matrix_bytes(), first, 'chạy lại cùng cờ phải byte-identical')
        self.assertEqual(self.run_gen().returncode, 0)
        self.assertEqual(self.matrix_bytes(), first, 'tái sinh thường sau khi sửa slug không được đổi gì (slug mới được giữ)')

    def test_refuses_boundary_too_close_to_lease(self):
        r = self.run_gen('--reslug-planned-after', 'BLG-02490')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('FAIL-CLOSED', r.stdout + r.stderr)
        self.assertEqual(self.matrix_bytes(), self.base.matrix_before)

    def test_refuses_when_draft_is_beyond_boundary(self):
        os.makedirs(os.path.join(self.work, '_drafts'), exist_ok=True)
        draft_id = 'BLG-%05d' % (int(self.BOUNDARY[4:]) + 50)   # bản nháp NẰM SAU ranh giới
        with open(os.path.join(self.work, '_drafts', '2026-10-12-x.md'), 'w', encoding='utf-8') as f:
            f.write('---\narticle_id: %s\ntitle: "x"\n---\nnội dung\n' % draft_id)
        r = self.run_gen('--reslug-planned-after', self.BOUNDARY)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('bản nháp', r.stdout + r.stderr)
        self.assertEqual(self.matrix_bytes(), self.base.matrix_before)

    def test_refuses_unreadable_registry_and_bad_boundary(self):
        with open(self.registry, 'w', encoding='utf-8') as f:
            f.write('{không phải json')
        r = self.run_gen('--reslug-planned-after', self.BOUNDARY)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('FAIL-CLOSED', r.stdout + r.stderr)
        with open(self.registry, 'wb') as f:
            f.write(self.registry_before)
        r = self.run_gen('--reslug-planned-after', '2600')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.matrix_bytes(), self.base.matrix_before)

    def test_refuses_slug_collision_and_writes_nothing(self):
        rows = self.rows()
        b = int(self.BOUNDARY[4:])
        victim = next(r for i, r in rows.items() if r['status'] == 'PLANNED' and int(i[4:]) > b
                      and GEN.slugify(r['title']) != r['slug'])
        # một hàng KHÁC (legacy) đang giữ đúng slug mới của victim => sau reslug sẽ trùng
        with open(self.matrix, encoding='utf-8', newline='') as f:
            text = f.read()
        other = rows['BLG-00001']
        lines = text.split('\n')
        for n, line in enumerate(lines):
            if line.startswith('BLG-00001,'):
                row = next(csv.reader([line]))
                row[list(other).index('slug')] = GEN.slugify(victim['title'])
                import io
                buf = io.StringIO()
                csv.writer(buf, lineterminator='').writerow(row)
                lines[n] = buf.getvalue()
        with open(self.matrix, 'w', encoding='utf-8', newline='') as f:
            f.write('\n'.join(lines))
        tampered = self.matrix_bytes()
        r = self.run_gen('--reslug-planned-after', self.BOUNDARY)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('slug trùng', r.stdout + r.stderr)
        self.assertEqual(self.matrix_bytes(), tampered, 'lỗi phải xảy ra TRƯỚC khi ghi file')


class TestRealMatrix(unittest.TestCase):

    def test_s5_slug_column_matches_output_path(self):
        with open(os.path.join(ROOT, 'data/content-matrix.csv'), encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        bad = []
        for r in rows:
            if r['status'] not in ('PLANNED', 'PUBLISHED'):
                continue
            op = r['output_path']
            sl = op.split('-', 1)[1][:-3] if '{date}' in op else os.path.basename(op)[11:-3]
            if r['slug'] != sl:
                bad.append((r['id'], r['slug'], sl))
        self.assertEqual(bad, [], 'cột slug lệch output_path: %s' % bad[:5])


if __name__ == '__main__':
    unittest.main(verbosity=1)
