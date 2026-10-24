#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test chính sách slug/URL DUY NHẤT (Issue #77) — OFFLINE.

Chứng minh:
  S1  slugkit.slugify: đ/Đ -> d, NFC/NFD cho cùng kết quả, cắt 80 ký tự, chỉ a-z0-9 và gạch ngang đơn; bằng ĐÚNG công thức
      lịch sử (bản tham chiếu đóng băng trong test) trên mọi tiêu đề của matrix + bộ chuỗi hiểm.
  S2  một nguồn duy nhất: generate-matrix.py, refill-queue.py, expand-topic-universe.py, scripts/seo/slugs.py dùng chính
      slugkit; không file nào trong scripts/ định nghĩa lại slugify/slug_*; không ai tự nối slug bằng re.sub(r'\\s+', '-').
  S3  URL: expected_url/output_path/date_path, replace_slug_in_url (cả hình dạng có tiền tố ngày), is_factory_url
      (từ chối khoảng trắng/Unicode/%XX/chữ hoa/gạch đôi).
  S4  chính sách trên DỮ LIỆU THẬT: mọi hàng factory khớp slugify(title) (trừ danh sách đóng băng chưa di trú, và chỉ
      khi slug đúng bằng slug lỗi cũ); danh sách đóng băng bất biến (sha256 ghim); registry <-> matrix <-> bài <-> evidence
      <-> tệp chuyển hướng nhất quán.
  S5  chính sách BẮT ĐƯỢC hồi quy: slug mất chữ d ở hàng mới, ngoại lệ dùng sai, slug không hợp lệ, URL Unicode, slug
      trùng, output_path lệch; registry thiếu/sai tệp chuyển hướng, chuỗi chuyển hướng, matrix lệch registry.
  S6  check-slug-redirects.py (kiểm OUTPUT build): trang cũ = HTTP 200 + meta refresh 0s + canonical mới + không trong
      sitemap; trang mới hợp lệ; không trang chuyển hướng lạ; ratchet liên kết vào trang chuyển hướng.
  S7  validate.py thật sự gọi chính sách (nối dây).

Chạy: python3 scripts/factory/tests/test_slug_policy.py (từ gốc repository)
"""
import csv
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'factory'))
import slug_redirects as SR  # noqa: E402
import slugkit  # noqa: E402


def load(name, rel):
    cwd = os.getcwd()
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    os.chdir(cwd)
    return m


def matrix_rows():
    with open(os.path.join(ROOT, 'data/content-matrix.csv'), encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


# --- bản tham chiếu ĐÓNG BĂNG của công thức lịch sử (đã sửa chữ đ) — KHÔNG import từ slugkit
def _ref_norm(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def ref_slugify(s):
    s = s.replace('đ', 'd').replace('Đ', 'D')
    return re.sub(r'\s+', '-', _ref_norm(s))[:80].strip('-')


ADVERSARIAL = [
    '', ' ', '---', 'đ', 'Đ', 'ĐĐĐ', 'xe đạp điện', 'Đặt cọc xe máy', 'ĐƯỜNG ĐI Đà Nẵng', 'Thuê xe máy ở Hà Nội',
    '  Xe   số -- giá?  ', 'Honda Air-Blade 125cc', 'a' * 79 + 'đ', 'a' * 80 + 'đ', 'a' * 100,
    ('từ ' * 40) + 'đường', 'ê hệ NFD: ' + unicodedata.normalize('NFD', 'Hà Nội đẹp'), 'emoji 😀 và ký-tự_lạ!',
    'Tab\tNewline\nxuống dòng', 'ĐỪNG nhầm Đ với D', 'Ơ ư ă â ê ô', 'Số 1: Điều kiện & lệ phí (2026)',
]


class SlugkitTest(unittest.TestCase):

    def test_golden(self):
        for title, want in (('xe đạp điện', 'xe-dap-dien'), ('Đặt cọc xe máy', 'dat-coc-xe-may'),
                            ('ĐƯỜNG ĐI Đà Nẵng', 'duong-di-da-nang'), ('Thuê xe máy ở Hà Nội', 'thue-xe-may-o-ha-noi'),
                            ('Bằng A1 chạy được những loại xe máy nào khi thuê',
                             'bang-a1-chay-duoc-nhung-loai-xe-may-nao-khi-thue')):
            self.assertEqual(slugkit.slugify(title), want)
        self.assertEqual(slugkit.slugify_legacy_without_d('xe đạp điện'), 'xe-ap-ien')

    def test_equals_frozen_reference_on_all_matrix_titles_and_adversarial(self):
        titles = [r['title'] for r in matrix_rows()] + ADVERSARIAL
        bad = [t for t in titles if slugkit.slugify(t) != ref_slugify(t)]
        self.assertEqual(bad, [], 'slugify lệch công thức lịch sử: %r' % bad[:3])
        bad = [t for t in titles if slugkit.norm(t) != _ref_norm(t)]
        self.assertEqual(bad, [], 'norm() (khoá trùng) bị đổi: %r' % bad[:3])

    def test_nfc_and_nfd_inputs_agree(self):
        for t in [r['title'] for r in matrix_rows()][:3000] + ADVERSARIAL:
            self.assertEqual(slugkit.slugify(unicodedata.normalize('NFC', t)),
                             slugkit.slugify(unicodedata.normalize('NFD', t)), t)

    def test_output_alphabet_and_length(self):
        for t in [r['title'] for r in matrix_rows()] + ADVERSARIAL:
            s = slugkit.slugify(t)
            self.assertLessEqual(len(s), slugkit.MAX_SLUG_LEN)
            self.assertTrue(s == '' or slugkit.SLUG_RE.match(s), (t, s))

    def test_d_after_cut_does_not_change_slug(self):
        t = 'a' * 80 + 'đ'
        self.assertEqual(slugkit.slugify(t), slugkit.slugify_legacy_without_d(t))

    def test_url_builders(self):
        self.assertEqual(slugkit.expected_url('hoi-dap', 'x'), '/hoi-dap/{date}/x/')
        self.assertEqual(slugkit.expected_url('hoi-dap', 'x', '2026-10-07 09:00:00 +0700'), '/hoi-dap/2026/10/07/x/')
        self.assertEqual(slugkit.output_path('x'), '_posts/{date}-x.md')
        self.assertEqual(slugkit.output_path('x', '2026-10-07'), '_posts/2026-10-07-x.md')
        with self.assertRaises(ValueError):
            slugkit.date_path('07/10/2026')

    def test_replace_slug_in_url(self):
        f = slugkit.replace_slug_in_url
        self.assertEqual(f('/an-toan/2026/09/28/at-xe/', 'at-xe', 'dat-xe'), '/an-toan/2026/09/28/dat-xe/')
        self.assertEqual(f('/hoi-dap/2026-09-29-at-xe/', 'at-xe', 'dat-xe'), '/hoi-dap/2026-09-29-dat-xe/')
        self.assertEqual(f('/ky-nang/2026-09-29/at-xe/', 'at-xe', 'dat-xe'), '/ky-nang/2026-09-29/dat-xe/')
        for bad in (('/a/b/bat-xe/', 'at-xe', 'dat-xe'), ('/a/b/at-xe', 'at-xe', 'dat-xe'), ('/a/b/xe/', 'at-xe', 'dat-xe')):
            with self.assertRaises(ValueError):
                f(*bad)

    def test_factory_url_policy(self):
        ok = ('/an-toan-phap-ly/2026/09/28/abc-def/', '/hoi-dap/2026-09-29-at-xe/', '/ky-nang/2026-09-29/at-xe/',
              '/x/{date}/ab/')
        bad = ('/chia sẻ/2026/09/18/x/', '/a/2026/09/28/Ab/', '/a/2026/09/28/a--b/', '/a/2026/09/28/x%20y/',
               '/a/2026/09/28/x', 'a/2026/09/28/x/', '/a/2026/09/28/đ/', '')
        for u in ok:
            self.assertTrue(slugkit.is_factory_url(u), u)
        for u in bad:
            self.assertFalse(slugkit.is_factory_url(u), u)

    def test_is_valid_slug(self):
        for s in ('a', 'a-b-1', 'x' * 80):
            self.assertTrue(slugkit.is_valid_slug(s), s)
        for s in ('', '-a', 'a-', 'a--b', 'A', 'a b', 'đ', 'x' * 81, 'a_b'):
            self.assertFalse(slugkit.is_valid_slug(s), s)
        self.assertTrue(slugkit.is_valid_slug('2026-09-29-at-xe', allow_date_prefix=True))


class SingleSourceTest(unittest.TestCase):

    def test_consumers_use_the_same_function_objects(self):
        gen = load('gm_t', 'scripts/factory/generate-matrix.py')
        ref = load('rq_t', 'scripts/factory/refill-queue.py')
        slugs = load('slugs_t', 'scripts/seo/slugs.py')
        self.assertIs(gen.slugify, slugkit.slugify)
        self.assertIs(gen.norm, slugkit.norm)
        self.assertIs(ref.slugify, slugkit.slugify)
        self.assertIs(ref.norm, slugkit.norm)
        self.assertIs(slugs.slug_correct, slugkit.slugify)
        self.assertIs(slugs.slug_old, slugkit.slugify_legacy_without_d)

    def test_no_second_implementation_in_scripts(self):
        defs = re.compile(r'^\s*def\s+(slugify|slug_correct|slug_old|make_slug|to_slug|slugify_vi)\b', re.M)
        join = re.compile(r"re\.sub\(\s*r?['\"]\\s\+['\"]\s*,\s*['\"]-['\"]")
        offenders = []
        for dp, dn, files in os.walk(os.path.join(ROOT, 'scripts')):
            dn[:] = [d for d in dn if d not in ('tests', '__pycache__', 'node_modules')]
            for fn in files:
                if not fn.endswith('.py') or fn == 'slugkit.py':
                    continue
                p = os.path.join(dp, fn)
                with open(p, encoding='utf-8') as f:
                    text = f.read()
                if defs.search(text) or join.search(text):
                    offenders.append(os.path.relpath(p, ROOT))
        self.assertEqual(offenders, [], 'slug chỉ được sinh bởi scripts/factory/slugkit.py: %s' % offenders)


class RealDataTest(unittest.TestCase):

    def test_baseline_is_frozen_and_complete(self):
        self.assertEqual(SR.baseline_sha256(), SR.BASELINE_SHA256)
        base = SR.load_baseline()
        self.assertEqual(len(base), 1410)
        by_id = {r['id']: r for r in matrix_rows()}
        for aid, b in base.items():
            self.assertIn(aid, by_id)
        # mọi bài trong baseline hoặc còn slug lỗi cũ (chưa di trú) hoặc đã có trong registry với slug mới
        reg = {r['article_id']: r for r in SR.load_registry()}
        for aid, b in base.items():
            row = by_id[aid]
            # 36 bài có tiền tố ngày trong URL/slug của baseline; cột slug của matrix không mang tiền tố
            if aid in reg:
                self.assertEqual(row['slug'], slugkit.split_date_prefix(b['new_slug'])[1])
            else:
                self.assertEqual(row['slug'], slugkit.split_date_prefix(b['old_slug'])[1], aid)

    def test_policy_and_registry_are_clean_on_real_data(self):
        rows = matrix_rows()
        self.assertEqual(SR.policy_errors(rows), [])
        self.assertEqual(SR.source_errors(None, rows), [])

    def test_pending_shrinks_only_by_migration(self):
        self.assertEqual(SR.pending_ids() | SR.migrated_ids(), set(SR.load_baseline()))
        self.assertFalse(SR.pending_ids() & SR.migrated_ids())


def fake_row(i, **kw):
    title = kw.pop('title', 'Đặt xe máy số %d' % i)
    slug = kw.pop('slug', slugkit.slugify(title))
    r = {'id': 'BLG-%05d' % i, 'status': 'PUBLISHED', 'title': title, 'source': 'planned:matrix-seed/C-X', 'slug': slug,
         'expected_url': '/hoi-dap/2026/10/07/%s/' % slug, 'canonical_url': '/hoi-dap/2026/10/07/%s/' % slug,
         'output_path': '_posts/2026-10-07-%s.md' % slug}
    r.update(kw)
    return r


class PolicyRegressionTest(unittest.TestCase):

    def codes(self, rows):
        return SR.policy_errors(rows)

    def test_clean_rows(self):
        self.assertEqual(self.codes([fake_row(1), fake_row(2)]), [])

    def test_new_row_with_lost_d_is_rejected(self):
        bad = fake_row(5, slug=slugkit.slugify_legacy_without_d('Đặt xe máy số 5'))
        errs = self.codes([bad])
        self.assertTrue(any('slugify(title)' in e for e in errs), errs)

    def test_exception_only_for_frozen_ids_and_only_for_the_known_defect(self):
        pending = sorted(SR.pending_ids())
        if not pending:
            self.skipTest('đã di trú hết')
        aid = pending[0]
        base = SR.load_baseline()[aid]
        ok = fake_row(int(aid[4:]), title=base['title'], slug=base['old_slug'])
        ok.update(expected_url=base['old_url'], canonical_url=base['old_url'], output_path=base['old_output_path'])
        self.assertEqual(self.codes([ok]), [])
        wrong = dict(ok, slug='mot-slug-khac')
        wrong.update(output_path='_posts/2026-10-07-mot-slug-khac.md', expected_url='/hoi-dap/2026/10/07/mot-slug-khac/',
                     canonical_url='/hoi-dap/2026/10/07/mot-slug-khac/')
        self.assertTrue(any('ngoại lệ lịch sử' in e for e in self.codes([wrong])))

    def test_invalid_slug_unicode_url_duplicate_and_output_path(self):
        self.assertTrue(any('không hợp lệ' in e for e in self.codes([fake_row(7, slug='Dat--Xe')])))
        self.assertTrue(any('ASCII' in e for e in self.codes([fake_row(8, expected_url='/chia sẻ/2026/10/07/x/')])))
        a, b = fake_row(9, title='Cùng tiêu đề'), fake_row(10, title='Cùng tiêu đề')
        self.assertTrue(any('slug trùng' in e for e in self.codes([a, b])))
        self.assertTrue(any('output_path' in e for e in self.codes([fake_row(11, output_path='_posts/2026-10-07-khac.md')])))

    def test_legacy_rows_are_out_of_scope(self):
        self.assertEqual(self.codes([{'id': 'BLG-00001', 'status': 'EXISTING', 'source': 'legacy:x', 'title': 'Đ', 'slug': 'Đ'}]), [])


# ----------------------------------------------------------------- registry/stub trên cây tạm

def make_root(rows_matrix, registry_rows, posts=True, stubs=True, evidence=True):
    root = tempfile.mkdtemp(prefix='slugpolicy-')
    os.makedirs(os.path.join(root, 'reports/factory/seo-master'))
    os.makedirs(os.path.join(root, 'data/qa'))
    os.makedirs(os.path.join(root, '_posts'))
    shutil.copy(os.path.join(ROOT, SR.BASELINE_REL), os.path.join(root, SR.BASELINE_REL))
    with open(os.path.join(root, SR.REGISTRY_REL), 'w', encoding='utf-8', newline='') as f:
        f.write(SR.registry_text(registry_rows))
    if stubs:
        for rel, text in SR.expected_stub_files(root).items():
            os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
            with open(os.path.join(root, rel), 'w', encoding='utf-8') as f:
                f.write(text)
    import hashlib
    for r in registry_rows:
        if posts:
            body = '---\npermalink: %s\n---\nnoi dung\n' % r['new_url']
            with open(os.path.join(root, r['new_output_path']), 'w', encoding='utf-8') as f:
                f.write(body)
            if evidence:
                ev = {'source_path': r['new_output_path'], 'content_sha256': hashlib.sha256(body.encode()).hexdigest(),
                      'revision': {'kind': 'permalink-migration', 'new_url': r['new_url']}}
                with open(os.path.join(root, 'data/qa/%s.json' % r['article_id']), 'w', encoding='utf-8') as f:
                    json.dump(ev, f)
    return root


def reg_entry(aid='BLG-00621'):
    b = SR.load_baseline()[aid]
    return {'article_id': aid, 'title': b['title'], 'old_url': b['old_url'], 'new_url': b['new_url'],
            'old_slug': slugkit.split_date_prefix(b['old_slug'])[1], 'new_slug': slugkit.split_date_prefix(b['new_slug'])[1],
            'old_output_path': b['old_output_path'],
            'new_output_path': b['new_output_path'], 'status': 'MIGRATED', 'batch_id': 't', 'migrated_at': ''}


def matrix_for(entry):
    return [fake_row(int(entry['article_id'][4:]), title=entry['title'], slug=entry['new_slug'],
                     expected_url=entry['new_url'], canonical_url=entry['new_url'],
                     output_path=entry['new_output_path'])]


class RegistrySourceTest(unittest.TestCase):

    def setUp(self):
        self.e = reg_entry()
        self.rows = matrix_for(self.e)
        self.roots = []

    def tearDown(self):
        for r in self.roots:
            shutil.rmtree(r, True)

    def errs(self, **kw):
        rows = kw.pop('rows', self.rows)
        reg = kw.pop('reg', [self.e])
        root = make_root(rows, reg, **kw)
        self.roots.append(root)
        return SR.source_errors(root, rows)

    def test_consistent_state_is_clean(self):
        self.assertEqual(self.errs(), [])

    def test_date_prefixed_legacy_shape_is_clean_too(self):
        base = SR.load_baseline()
        dated = [aid for aid, b in base.items() if slugkit.split_date_prefix(b['old_slug'])[0]]     # /cat/yyyy-mm-dd-slug/
        seg = [aid for aid, b in base.items() if re.search(r'/\d{4}-\d{2}-\d{2}/[^/]+/$', b['old_url'])]  # /cat/yyyy-mm-dd/slug/
        self.assertEqual((len(dated), len(seg)), (7, 29))        # 36 bài có URL khác dạng chuẩn /yyyy/mm/dd/
        for aid in (dated[0], seg[0]):
            e = reg_entry(aid)
            self.assertNotRegex(e['new_slug'], r'^\d{4}-')       # cột slug của matrix không mang tiền tố ngày
            self.assertEqual(self.errs(rows=matrix_for(e), reg=[e]), [], aid)

    def test_missing_or_edited_or_foreign_stub(self):
        self.assertTrue(any('thiếu trang chuyển hướng' in e for e in self.errs(stubs=False)))
        root = make_root(self.rows, [self.e])
        self.roots.append(root)
        p = os.path.join(root, SR.stub_relpath(self.e['article_id']))
        open(p, 'a', encoding='utf-8').write('<script>x</script>\n')
        self.assertTrue(any('không khớp registry' in e for e in SR.source_errors(root, self.rows)))
        open(os.path.join(root, SR.STUB_DIR, 'BLG-99999.html'), 'w', encoding='utf-8').write('---\n---\n')
        self.assertTrue(any('lạ' in e for e in SR.source_errors(root, self.rows)))

    def test_matrix_registry_mismatch_and_old_url_still_owned(self):
        bad = [dict(self.rows[0], slug='khac')]
        self.assertTrue(any('matrix slug' in e for e in self.errs(rows=bad)))
        owner = fake_row(99, expected_url=self.e['old_url'], canonical_url=self.e['old_url'])
        self.assertTrue(any('vẫn là URL của hàng' in e for e in self.errs(rows=self.rows + [owner])))

    def test_chain_and_duplicates_and_unknown_id(self):
        other = dict(reg_entry('BLG-00618'))
        other['old_url'] = self.e['new_url']                    # NEW của mục này là OLD của mục kia
        errs = self.errs(rows=self.rows + matrix_for(other), reg=[self.e, other])
        self.assertTrue(any('chuỗi chuyển hướng' in e for e in errs), errs)
        errs = self.errs(rows=self.rows, reg=[self.e, dict(self.e)])
        self.assertTrue(any('trùng' in e for e in errs))
        fake = dict(self.e, article_id='BLG-77777')
        self.assertTrue(any('không thuộc danh sách đóng băng' in e for e in self.errs(rows=matrix_for(fake), reg=[fake])))

    def test_evidence_and_post_must_match(self):
        self.assertTrue(any('thiếu evidence' in e for e in self.errs(evidence=False)))
        self.assertTrue(any('thiếu bài' in e for e in self.errs(posts=False)))
        root = make_root(self.rows, [self.e])
        self.roots.append(root)
        open(os.path.join(root, self.e['new_output_path']), 'a', encoding='utf-8').write('đổi\n')
        self.assertTrue(any('content_sha256' in e for e in SR.source_errors(root, self.rows)))

    def test_old_post_file_must_be_gone(self):
        root = make_root(self.rows, [self.e])
        self.roots.append(root)
        open(os.path.join(root, self.e['old_output_path']), 'w', encoding='utf-8').write('x')
        self.assertTrue(any('tệp bài cũ' in e for e in SR.source_errors(root, self.rows)))

    def test_baseline_tamper_detected(self):
        root = make_root(self.rows, [self.e])
        self.roots.append(root)
        with open(os.path.join(root, SR.BASELINE_REL), 'a', encoding='utf-8') as f:
            f.write('BLG-99999,x\n')
        self.assertTrue(any('bất biến' in e for e in SR.source_errors(root, self.rows)))


# ----------------------------------------------------------------- check-slug-redirects.py trên _site tạm

CHECK = load('check_slug_redirects_t', 'scripts/factory/check-slug-redirects.py')


def stub_page(old_new, delay=0, canon=None, extra=''):
    new = old_new
    canon = SR.SITE_URL + new if canon is None else canon
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><link rel="canonical" href="%s">'
            '<meta http-equiv="refresh" content="%s; url=%s">%s</head><body><h1>x</h1></body></html>'
            % (canon, delay, new, extra))


def real_page(url, canon=None, links=(), h1=True):
    canon = SR.SITE_URL + url if canon is None else canon
    return ('<!DOCTYPE html><html><head><link rel="canonical" href="%s"></head><body>%s%s</body></html>'
            % (canon, '<h1>Bài</h1>' if h1 else '', ''.join('<a href="%s">l</a>' % l for l in links)))


class BuiltSiteCheckTest(unittest.TestCase):

    def setUp(self):
        self.e = reg_entry()
        self.root = make_root(matrix_for(self.e), [self.e])
        self.site = tempfile.mkdtemp(prefix='site-')

    def tearDown(self):
        shutil.rmtree(self.root, True)
        shutil.rmtree(self.site, True)

    def put(self, url, text):
        d = os.path.join(self.site, url.strip('/'))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(text)

    def sitemap(self, urls):
        with open(os.path.join(self.site, 'sitemap.xml'), 'w', encoding='utf-8') as f:
            f.write('<urlset>%s</urlset>' % ''.join('<url><loc>%s%s</loc></url>' % (SR.SITE_URL, u) for u in urls))

    def good(self):
        self.put(self.e['old_url'], stub_page(self.e['new_url']))
        self.put(self.e['new_url'], real_page(self.e['new_url']))
        self.sitemap([self.e['new_url'], '/'])

    def res(self, **kw):
        return CHECK.check(self.site, self.root, **kw)

    def test_good_site_passes(self):
        self.good()
        r = self.res(max_stub_links=0)
        self.assertEqual(r['errors'], [])
        self.assertEqual(r['registry'], 1)

    def test_each_failure_is_reported(self):
        cases = {
            'meta refresh trễ': lambda: self.put(self.e['old_url'], stub_page(self.e['new_url'], delay=5)),
            'canonical trang cũ': lambda: self.put(self.e['old_url'], stub_page(self.e['new_url'], canon=SR.SITE_URL + '/khac/')),
            'meta refresh trỏ': lambda: self.put(self.e['old_url'], stub_page('/sai/')),
            'là trang chuyển hướng (chuỗi)': lambda: self.put(self.e['new_url'], stub_page('/x/')),
            'canonical trang mới': lambda: self.put(self.e['new_url'], real_page(self.e['new_url'], canon=SR.SITE_URL + '/khac/')),
            'không có <h1>': lambda: self.put(self.e['new_url'], real_page(self.e['new_url'], h1=False)),
            'vẫn nằm trong sitemap': lambda: self.sitemap([self.e['new_url'], self.e['old_url']]),
            'không có trong sitemap': lambda: self.sitemap(['/']),
            'thiếu trang chuyển hướng': lambda: shutil.rmtree(os.path.join(self.site, self.e['old_url'].strip('/'))),
            'thiếu trang mới': lambda: shutil.rmtree(os.path.join(self.site, self.e['new_url'].strip('/'))),
            'không có trong registry': lambda: self.put('/trang-la/', stub_page('/x/')),
        }
        for needle, mutate in cases.items():
            self.good()
            mutate()
            errs = self.res(max_stub_links=100)['errors']
            self.assertTrue(any(needle in e for e in errs), (needle, errs))

    def test_stub_link_ratchet(self):
        self.good()
        self.put('/bai-khac/', real_page('/bai-khac/', links=[self.e['old_url'], self.e['old_url'] + '#x',
                                                              SR.SITE_URL + self.e['old_url'], '/an-toan/']))
        r = self.res(max_stub_links=3)
        self.assertEqual((r['stub_links'], r['stub_link_sources'], r['errors']), (3, 1, []))
        r = self.res(max_stub_links=2)
        self.assertTrue(any('ngưỡng 2' in e for e in r['errors']))
        r = self.res(max_stub_links=9)
        self.assertTrue(any('ratchet có thể hạ' in n for n in r['notes']))

    def test_cli_exit_codes(self):
        self.good()
        self.assertEqual(CHECK.main(['--site', self.site, '--root', self.root, '--max-stub-links', '0']), 0)
        shutil.rmtree(os.path.join(self.site, self.e['new_url'].strip('/')))
        self.assertEqual(CHECK.main(['--site', self.site, '--root', self.root]), 1)
        self.assertEqual(CHECK.main(['--site', os.path.join(self.site, 'khong-co')]), 2)


class WiringTest(unittest.TestCase):

    def test_validate_calls_the_policy(self):
        with open(os.path.join(ROOT, 'scripts/factory/validate.py'), encoding='utf-8') as f:
            text = f.read()
        self.assertIn('slug_redirects.policy_errors(mrows)', text)
        self.assertIn('slug_redirects.source_errors(None, mrows)', text)

    def test_gate_runs_built_site_check_and_triggers_on_redirects_dir(self):
        with open(os.path.join(ROOT, '.github/workflows/quality-gate.yml'), encoding='utf-8') as f:
            y = f.read()
        self.assertIn('scripts/factory/check-slug-redirects.py --site ./_site', y)
        self.assertGreaterEqual(y.count("'redirects/**'"), 2)       # push + pull_request paths

    def test_generators_use_slugkit_builders(self):
        with open(os.path.join(ROOT, 'scripts/factory/generate-matrix.py'), encoding='utf-8') as f:
            gm = f.read()
        self.assertIn('slugkit.expected_url(cat, slug)', gm)
        self.assertIn('slugkit.output_path(slug)', gm)


if __name__ == '__main__':
    unittest.main(verbosity=1)
