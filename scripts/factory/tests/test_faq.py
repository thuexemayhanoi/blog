#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test hạ tầng FAQ dùng chung: scripts/faq/validate_faq.py + scripts/faq/faq_parity_check.py + hợp đồng template/CI.

Chứng minh (offline, chỉ stdlib, không Jekyll):
  - validator: FAQ hợp lệ qua; từng loại vi phạm (mồ côi, không nguyên văn, chủ đề BLOCKED, số tiền ngoài bảng giá,
    cụm bị cấm, trùng/gần trùng, sai số lượng mục, HTML trong câu trả lời, src sai, khoá mơ hồ) đều bị chặn;
  - parity: JSON-LD khớp khối hiển thị => qua; lệch/mồ côi/JSON hỏng => lỗi (kể cả escape `</script>`);
  - hợp đồng: template escape đúng cách, layout gọi component, CI chạy cả hai công cụ, suite nằm trong nhóm `ci`.

Chạy: python3 scripts/factory/tests/test_faq.py (từ gốc repository)
"""
import html
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


VF = load('validate_faq_t', 'scripts/faq/validate_faq.py')
PC = load('faq_parity_t', 'scripts/faq/faq_parity_check.py')

BODY_A = """---
layout: post
title: "Bài A"
---
## Thuê xe máy ở Hà Nội cần giấy tờ gì

Khi thuê xe máy tại Hà Nội bạn cần mang theo căn cước công dân hoặc hộ chiếu còn hiệu lực. Cửa hàng mở cửa từ 09:00 đến 21:00 mỗi ngày.

Giá thuê Honda Wave là 150.000đ/ngày theo bảng giá đã duyệt. Mức cọc cần xác nhận trực tiếp với cửa hàng trước khi nhận xe.

Tiền cọc là 3 triệu đồng và hoàn lại đầy đủ khi trả xe. Một số khách thuê gói 100.000đ/ngày. Cửa hàng hỗ trợ 24/7 cho mọi khách.
"""
BODY_B = """---
layout: post
title: "Bài B"
---
Bạn nên kiểm tra phanh, đèn và lốp trước khi nhận xe để tránh phát sinh tranh cãi về sau.

Hãy chụp ảnh tình trạng xe khi nhận và khi trả để hai bên cùng đối chiếu rõ ràng.
"""
PAGE = """---
layout: page
title: "Trang X"
faq_key: page-x
---
Cửa hàng nằm tại 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội và nhận khách mỗi ngày trong tuần.
Bạn có thể gọi điện hoặc nhắn Zalo để hỏi tình trạng xe trước khi đến cửa hàng.
"""
FACTS = {'approved_pricing': {'Honda Wave': {'day': 150000, 'deposit': 'Xác nhận trực tiếp'},
                              'Honda Vision': {'day': 200000, 'week': '800000 - 1000000'}}}


def good_item(**kw):
    it = {'q': 'Thuê xe máy ở Hà Nội cần mang theo giấy tờ gì?',
          'a': 'Khi thuê xe máy tại Hà Nội bạn cần mang theo căn cước công dân hoặc hộ chiếu còn hiệu lực.',
          'src': 'body'}
    it.update(kw)
    return it


def second_item(**kw):
    it = {'q': 'Cửa hàng mở cửa vào những giờ nào mỗi ngày?',
          'a': 'Cửa hàng mở cửa từ 09:00 đến 21:00 mỗi ngày.', 'src': 'body'}
    it.update(kw)
    return it


class Fixture:
    def __init__(self, test):
        self.root = tempfile.mkdtemp(prefix='faqtest_')
        test.addCleanup(shutil.rmtree, self.root, True)
        for rel, txt in (('_posts/2026-01-01-slug-a.md', BODY_A), ('_posts/2026-01-02-slug-b.md', BODY_B),
                         ('thue-xe/page-x.md', PAGE)):
            self.write(rel, txt)
        self.write('data/business-facts.json', json.dumps(FACTS))

    def write(self, rel, txt):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(txt)

    def faq(self, key, items, **top):
        d = {'schema': False, 'items': items}
        d.update(top)
        self.write('_data/faq/%s.json' % key, json.dumps(d, ensure_ascii=False))

    def run(self):
        return VF.validate(self.root)[0]


class TestValidator(unittest.TestCase):

    def setUp(self):
        self.fx = Fixture(self)

    def assertErr(self, errors, needle):
        self.assertTrue(any(needle in e for e in errors), 'thiếu lỗi %r trong %s' % (needle, errors))

    def test_no_faq_dir_is_ok(self):
        self.assertEqual(self.fx.run(), [])

    def test_valid_post_and_page(self):
        self.fx.faq('slug-a', [good_item(), second_item()], schema=True)
        self.fx.faq('page-x', [
            {'q': 'Cửa hàng nằm ở địa chỉ nào tại Hà Nội?',
             'a': 'Cửa hàng nằm tại 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội và nhận khách mỗi ngày trong tuần.', 'src': 'page'},
            {'q': 'Làm sao biết tình trạng xe trước khi đến cửa hàng?',
             'a': 'Bạn có thể gọi điện hoặc nhắn Zalo để hỏi tình trạng xe trước khi đến cửa hàng.', 'src': 'page'}])
        errors, stats = VF.validate(self.fx.root)
        self.assertEqual(errors, [])
        self.assertEqual((stats['files'], stats['items'], stats['schema_true']), (2, 4, 1))

    def test_orphan_key(self):
        self.fx.faq('khong-ton-tai', [good_item(), second_item()])
        self.assertErr(self.fx.run(), 'mồ côi')

    def test_answer_must_be_verbatim(self):
        self.fx.faq('slug-a', [good_item(a='Bạn cần mang theo căn cước công dân và bằng lái xe quốc tế bản gốc.'), second_item()])
        self.assertErr(self.fx.run(), 'không trích nguyên văn')

    def test_verbatim_ignores_case_punctuation_markdown(self):
        self.fx.faq('slug-a', [good_item(a='KHI THUÊ xe máy tại Hà Nội, bạn cần mang theo căn cước công dân hoặc hộ chiếu còn hiệu lực!'),
                               second_item()])
        self.assertEqual(self.fx.run(), [])

    def test_blocked_topic_with_number(self):
        self.fx.faq('slug-a', [good_item(q='Tiền cọc khi thuê xe máy là bao nhiêu tiền?',
                                         a='Tiền cọc là 3 triệu đồng và hoàn lại đầy đủ khi trả xe.'), second_item()])
        errs = self.fx.run()
        self.assertErr(errs, 'BLOCKED')

    def test_blocked_topic_without_hedge(self):
        self.fx.write('_posts/2026-01-03-slug-c.md', BODY_B + '\nBảo hiểm xe máy được tính theo quy định hiện hành của nhà nước.\n')
        self.fx.faq('slug-c', [
            {'q': 'Xe thuê có kèm bảo hiểm cho người thuê không?',
             'a': 'Bảo hiểm xe máy được tính theo quy định hiện hành của nhà nước.', 'src': 'body'},
            {'q': 'Nên làm gì trước khi nhận xe thuê?',
             'a': 'Bạn nên kiểm tra phanh, đèn và lốp trước khi nhận xe để tránh phát sinh tranh cãi về sau.', 'src': 'body'}])
        self.assertErr(self.fx.run(), 'BLOCKED')

    def test_blocked_topic_hedge_only_is_allowed(self):
        self.fx.faq('slug-a', [
            {'q': 'Mức đặt cọc khi thuê xe được tính thế nào?',
             'a': 'Mức cọc cần xác nhận trực tiếp với cửa hàng trước khi nhận xe.', 'src': 'body'}, second_item()])
        self.assertEqual(self.fx.run(), [])

    def test_amount_must_be_approved(self):
        self.fx.faq('slug-a', [
            {'q': 'Có gói thuê nào giá 100.000đ mỗi ngày không?',
             'a': 'Một số khách thuê gói 100.000đ/ngày.', 'src': 'body'}, second_item()])
        errs = self.fx.run()
        self.assertErr(errs, 'bảng giá đã duyệt')

    def test_approved_amount_ok(self):
        self.fx.faq('slug-a', [
            {'q': 'Giá thuê Honda Wave một ngày là bao nhiêu tiền?',
             'a': 'Giá thuê Honda Wave là 150.000đ/ngày theo bảng giá đã duyệt.', 'src': 'body'}, second_item()])
        self.assertEqual(self.fx.run(), [])

    def test_forbidden_claim(self):
        self.fx.faq('slug-a', [
            {'q': 'Cửa hàng có hỗ trợ khách thuê xe 24/7 không?',
             'a': 'Cửa hàng hỗ trợ 24/7 cho mọi khách.', 'src': 'body'}, second_item()])
        self.assertErr(self.fx.run(), 'cụm bị cấm')

    def test_duplicate_and_near_duplicate_questions(self):
        self.fx.faq('slug-a', [good_item(), second_item()])
        self.fx.faq('slug-b', [
            {'q': 'Thuê xe máy ở Hà Nội cần mang theo giấy tờ gì?',
             'a': 'Bạn nên kiểm tra phanh, đèn và lốp trước khi nhận xe để tránh phát sinh tranh cãi về sau.', 'src': 'body'},
            {'q': 'Nên chụp ảnh tình trạng xe khi nhận và khi trả không?',
             'a': 'Hãy chụp ảnh tình trạng xe khi nhận và khi trả để hai bên cùng đối chiếu rõ ràng.', 'src': 'body'}])
        self.assertErr(self.fx.run(), 'câu hỏi trùng')
        self.fx.faq('slug-b', [
            {'q': 'Thuê xe máy ở Hà Nội cần mang theo những giấy tờ gì?',
             'a': 'Bạn nên kiểm tra phanh, đèn và lốp trước khi nhận xe để tránh phát sinh tranh cãi về sau.', 'src': 'body'},
            {'q': 'Nên chụp ảnh tình trạng xe khi nhận và khi trả không?',
             'a': 'Hãy chụp ảnh tình trạng xe khi nhận và khi trả để hai bên cùng đối chiếu rõ ràng.', 'src': 'body'}])
        self.assertErr(self.fx.run(), 'gần trùng')

    def test_item_count_bounds(self):
        self.fx.faq('slug-a', [good_item()])
        self.assertErr(self.fx.run(), '2–8 mục')
        self.fx.faq('slug-a', [good_item(q='Câu hỏi số %d về thuê xe máy ở Hà Nội?' % i) for i in range(9)])
        self.assertErr(self.fx.run(), '2–8 mục')

    def test_plain_text_only(self):
        self.fx.faq('slug-a', [good_item(a='Khi thuê xe máy tại Hà Nội bạn cần mang theo **căn cước công dân** hoặc hộ chiếu còn hiệu lực.'),
                               second_item()])
        self.assertErr(self.fx.run(), 'văn bản thuần')

    def test_src_and_target_kind_must_match(self):
        self.fx.faq('slug-a', [good_item(src='page'), second_item()])
        self.assertErr(self.fx.run(), 'src phải là "body"')

    def test_schema_must_be_boolean(self):
        self.fx.faq('slug-a', [good_item(), second_item()], schema='yes')
        self.assertErr(self.fx.run(), 'boolean')

    def test_ambiguous_key(self):
        self.fx.write('thue-xe/slug-a-page.md', PAGE.replace('page-x', 'slug-a'))
        self.fx.faq('slug-a', [good_item(), second_item()])
        self.assertErr(self.fx.run(), 'không duy nhất')

    def test_bad_json(self):
        self.fx.write('_data/faq/slug-a.json', '{not json')
        self.assertErr(self.fx.run(), 'JSON không hợp lệ')

    def test_short_sentence(self):
        self.fx.faq('slug-a', [good_item(a='Khi thuê xe máy tại Hà Nội bạn cần mang theo căn cước công dân hoặc hộ chiếu còn hiệu lực. Có.'),
                               second_item()])
        self.assertErr(self.fx.run(), 'quá ngắn')

    def test_cli_exit_codes(self):
        import subprocess
        self.fx.faq('slug-a', [good_item(), second_item()])
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/faq/validate_faq.py'), '--root', self.fx.root],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.fx.faq('khong-co', [good_item(), second_item()])
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/faq/validate_faq.py'), '--root', self.fx.root],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)


def render(items, schema=True, ld_items=None, schema_flag=None, heading='Câu hỏi thường gặp'):
    """Mô phỏng ĐÚNG đầu ra của _includes/faq.html (visible qua escape, JSON-LD qua jsonify + '</' -> '<\\/')."""
    flag = schema if schema_flag is None else schema_flag
    vis = ''.join('<div class="faq-item">\n    <h3>%s</h3>\n    <p>%s</p>\n  </div>' % (html.escape(q), html.escape(a))
                  for q, a in items)
    out = '<html><body><main><section class="faq" id="faq" aria-labelledby="faq-heading"%s>\n  <h2 id="faq-heading">%s</h2>\n  %s\n</section>' % (
        ' data-faq-schema="1"' if flag else '', html.escape(heading), vis)
    if schema:
        li = ld_items if ld_items is not None else items
        doc = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in li]}
        out += '\n<script type="application/ld+json">\n%s\n</script>' % json.dumps(doc, ensure_ascii=False).replace('</', '<\\/')
    return out + '</main></body></html>'


class TestParity(unittest.TestCase):

    def setUp(self):
        self.site = tempfile.mkdtemp(prefix='faqsite_')
        self.addCleanup(shutil.rmtree, self.site, True)

    def page(self, rel, text):
        p = os.path.join(self.site, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(text)

    def check(self):
        return PC.check_site(self.site)

    ITEMS = [('Thuê xe máy cần giấy tờ gì?', 'Bạn cần mang căn cước công dân hoặc hộ chiếu còn hiệu lực.'),
             ('Cửa hàng mở cửa lúc mấy giờ?', 'Cửa hàng mở cửa từ 09:00 đến 21:00 mỗi ngày.')]

    def test_no_faq_ok(self):
        self.page('a/index.html', '<html><body><script type="application/ld+json">{"@type":"WebSite"}</script></body></html>')
        errs, pages, with_faq = self.check()
        self.assertEqual((errs, pages, with_faq), ([], 1, 0))

    def test_good_page(self):
        self.page('a/index.html', render(self.ITEMS))
        errs, _, with_faq = self.check()
        self.assertEqual((errs, with_faq), ([], 1))

    def test_visible_only_without_schema_flag_is_ok(self):
        self.page('a/index.html', render(self.ITEMS, schema=False))
        self.assertEqual(self.check()[0], [])

    def test_special_characters_roundtrip(self):
        items = [('Giá "rẻ" & <b>tốt</b> có thật không?', 'Không dùng </script> hay dấu \' & ký tự lạ trong câu trả lời nhé.'),
                 self.ITEMS[1]]
        self.page('a/index.html', render(items))
        self.assertEqual(self.check()[0], [])

    def test_mismatch(self):
        self.page('a/index.html', render(self.ITEMS, ld_items=[self.ITEMS[0], ('Cửa hàng mở cửa lúc mấy giờ?', 'Khác hoàn toàn.')]))
        self.assertTrue(any('KHÁC' in e for e in self.check()[0]))

    def test_order_matters(self):
        self.page('a/index.html', render(self.ITEMS, ld_items=list(reversed(self.ITEMS))))
        self.assertTrue(any('KHÁC' in e for e in self.check()[0]))

    def test_schema_without_visible(self):
        doc = {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': 'a?', 'acceptedAnswer': {'@type': 'Answer', 'text': 'b'}}]}
        self.page('a/index.html', '<html><body><script type="application/ld+json">%s</script></body></html>' % json.dumps(doc))
        self.assertTrue(any('không có khối FAQ hiển thị' in e for e in self.check()[0]))

    def test_flag_without_schema(self):
        self.page('a/index.html', render(self.ITEMS, schema=False, schema_flag=True))
        self.assertTrue(any('không có FAQPage' in e for e in self.check()[0]))

    def test_schema_without_flag(self):
        self.page('a/index.html', render(self.ITEMS, schema=True, schema_flag=False))
        self.assertTrue(any('không đánh dấu' in e for e in self.check()[0]))

    def test_invalid_jsonld_anywhere(self):
        self.page('x/index.html', '<html><body><script type="application/ld+json">{"a": "unterminated}</script></body></html>')
        self.assertTrue(any('không parse được' in e for e in self.check()[0]))

    def test_two_faqpage_blocks(self):
        page = render(self.ITEMS)
        extra = '<script type="application/ld+json">%s</script>' % json.dumps(
            {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': 'a?', 'acceptedAnswer': {'@type': 'Answer', 'text': 'b'}}]})
        self.page('a/index.html', page.replace('</body>', extra + '</body>'))
        self.assertTrue(any('2 khối FAQPage' in e for e in self.check()[0]))

    def test_single_pair_rejected(self):
        self.page('a/index.html', render(self.ITEMS[:1]))
        self.assertTrue(any('< 2 cặp' in e for e in self.check()[0]))

    def test_faqpage_inside_graph(self):
        doc = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'WebSite', 'name': 'x'},
            {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}}
                                                for q, a in self.ITEMS]}]}
        page = render(self.ITEMS, schema=False, schema_flag=True)
        page = page.replace('</body>', '<script type="application/ld+json">%s</script></body>' % json.dumps(doc, ensure_ascii=False))
        self.page('a/index.html', page)
        self.assertEqual(self.check()[0], [])


class TestContracts(unittest.TestCase):
    """Template + CI nối dây đúng (bắt lỡ tay xoá bước kiểm tra hoặc đổi cách escape)."""

    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
            return f.read()

    def test_component_escaping(self):
        t = self.read('_includes/faq.html')
        self.assertIn("jsonify | replace: '</', '<\\/'", t)
        self.assertIn('| escape', t)
        self.assertIn('data-faq-schema', t)
        self.assertIn('faq_data.items.size >= 2', t)  # mặc định không in gì khi thiếu dữ liệu

    def test_layouts_call_component(self):
        self.assertIn('{% include faq.html key=page.slug %}', self.read('_layouts/post.html'))
        self.assertIn('{% include faq.html key=page.faq_key %}', self.read('_layouts/page.html'))

    def test_ci_runs_both_tools(self):
        wf = self.read('.github/workflows/quality-gate.yml')
        self.assertIn('scripts/faq/validate_faq.py', wf)
        self.assertIn('scripts/faq/faq_parity_check.py --site ./_site', wf)

    def test_suite_registered(self):
        self.assertIn("'test_faq'", self.read('scripts/factory/run-tests.py'))

    def test_real_repo_faq_data_is_valid(self):
        errors, _ = VF.validate(ROOT)
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
