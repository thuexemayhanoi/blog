#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test scripts/seo/price_phrases.py + build-price-patches.py (thuần văn bản, không cần repo).

Bất biến chính: chỉ kỳ hạn TUẦN/THÁNG gắn được MỘT xe + MỘT kỳ hạn mới bị coi là giá thuê; số tiền cạnh chữ "ngày"
(phép tính, chênh lệch) và câu có so sánh/phép tính KHÔNG bao giờ tự sửa; sửa xong quét lại không còn lệch (idempotent);
dòng `title:` (bất biến theo matrix) không bao giờ bị đưa vào danh sách sửa; ngữ cảnh `old` của mỗi sửa là DUY NHẤT.
"""
import importlib.util
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SEO = HERE.parents[2] / 'scripts' / 'seo'
sys.path.insert(0, str(SEO))
import price_phrases as pp  # noqa: E402

spec = importlib.util.spec_from_file_location('build_price_patches_under_test', SEO / 'build-price-patches.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
spec = importlib.util.spec_from_file_location('revise_for_patch_test', HERE.parent / 'revise-published.py')
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

EXPECTED = {
    'wave': {'day': (150000, 150000), 'week': (700000, 700000), 'month': (900000, 1200000)},
    'vision': {'day': (200000, 200000), 'week': (1000000, 1000000), 'month': (1800000, 2000000)},
    'airblade': {'day': (200000, 200000), 'week': (1000000, 1000000), 'month': (1500000, 1500000)},
    'click': {'day': (150000, 150000), 'week': (700000, 700000), 'month': (900000, 1200000)},
}


def scan(text, doc_vehicle=''):
    return pp.scan_text(text, EXPECTED, doc_vehicle)


def apply_fixes(text, statuses=('MISMATCH',)):
    phs = [p for p in scan(text) if p.status in statuses and p.fix_start >= 0]
    for p in sorted(phs, key=lambda p: p.fix_start, reverse=True):
        assert text[p.fix_start:p.fix_end] == p.fix_old
        text = text[:p.fix_start] + p.fix_new + text[p.fix_end:]
    return text


class TestPricePhrases(unittest.TestCase):

    def test_list_form_week_and_month_are_fixed_day_is_untouched(self):
        t = 'Honda Air Blade có giá 200.000đ/ngày, 800.000đ/tuần và 1.400.000đ/tháng.'
        self.assertEqual(apply_fixes(t), 'Honda Air Blade có giá 200.000đ/ngày, 1.000.000đ/tuần và 1.500.000đ/tháng.')
        by_text = {p.text.strip(): p.status for p in scan(t)}
        self.assertEqual(by_text['200.000đ'], 'SKIP_DAY')

    def test_ranges_collapse_to_the_new_single_price_and_keep_units(self):
        cases = {
            'Theo tuần, Click hoặc Mio khoảng 600.000đ đến 700.000đ.': 'Theo tuần, Click hoặc Mio khoảng 700.000đ.',
            'Honda Click tuần 600.000–700.000 đồng.': 'Honda Click tuần 700.000 đồng.',
            'Vision thuê theo tuần dao động từ 800.000đ đến 1.000.000đ, nhiều khách chọn.':
                'Vision thuê theo tuần khoảng 1.000.000đ, nhiều khách chọn.',
            'Honda Vision có gói tuần từ 800.000đ đến 1.000.000đ.': 'Honda Vision có gói tuần 1.000.000đ.',
        }
        for old, new in cases.items():
            self.assertEqual(apply_fixes(old), new, old)

    def test_range_stays_a_range_when_the_new_price_is_a_range(self):
        t = 'Honda Click hoặc Yamaha Mio theo tháng từ 1.000.000đ đến 1.200.000đ tùy xe.'
        self.assertEqual(apply_fixes(t), 'Honda Click hoặc Yamaha Mio theo tháng từ 900.000đ đến 1.200.000đ tùy xe.')

    def test_matching_prices_are_ok_and_never_rewritten(self):
        t = 'Honda Vision 200.000đ/ngày, 1.000.000đ/tuần và 1.800.000đ đến 2.000.000đ/tháng.'
        self.assertEqual(apply_fixes(t), t)
        self.assertEqual([p.status for p in scan(t) if p.period != 'day'], ['OK', 'OK'])

    def test_arithmetic_and_differences_next_to_day_are_never_treated_as_rental_rates(self):
        for t in ('Vision đắt hơn Wave 50.000đ mỗi ngày.',
                  'Nếu bạn thuê 7 ngày lẻ, chi phí theo giá ngày là 1.400.000đ.',
                  'Honda Click 5 ngày lẻ đã lên tới 750.000đ.'):
            self.assertEqual(apply_fixes(t), t, t)
            self.assertFalse([p for p in scan(t) if p.status in ('MISMATCH', 'REVIEW')], t)

    def test_sentences_with_comparison_or_arithmetic_cues_go_to_review_not_autofix(self):
        t = 'Ví dụ, 5 ngày lẻ của Honda Click đã lên tới 750.000đ, ngang ngửa gói tuần 600.000đ đến 700.000đ.'
        week = [p for p in scan(t) if p.period == 'week']
        self.assertEqual([p.status for p in week], ['REVIEW'])
        self.assertEqual(apply_fixes(t), t)                       # MISMATCH-only: REVIEW không tự sửa
        t2 = 'Thuê 4 tuần Honda Wave tính theo giá tuần là 2.800.000đ.'
        self.assertEqual(apply_fixes(t2), t2)
        self.assertTrue(all(p.status != 'MISMATCH' for p in scan(t2)))

    def test_rate_forms_with_one_per_period_are_not_mistaken_for_arithmetic(self):
        t = 'Dòng Air Blade khoảng 200.000đ một ngày, 800.000đ một tuần, 1.400.000đ một tháng.'
        self.assertEqual(apply_fixes(t), 'Dòng Air Blade khoảng 200.000đ một ngày, 1.000.000đ một tuần, 1.500.000đ một tháng.')

    def test_table_rows_bind_to_vehicle_cell_and_header_period(self):
        t = ('| Loại xe | Theo ngày | Theo tuần | Theo tháng |\n|---|---|---|---|\n'
             '| Honda Air Blade | 200.000đ | 800.000đ | 1.400.000đ |\n'
             '| Honda Click | 150.000đ | 600.000đ – 700.000đ | 1.000.000đ – 1.200.000đ |\n')
        out = apply_fixes(t)
        self.assertIn('| Honda Air Blade | 200.000đ | 1.000.000đ | 1.500.000đ |', out)
        self.assertIn('| Honda Click | 150.000đ | 700.000đ | 900.000đ – 1.200.000đ |', out)

    def test_phrase_without_vehicle_or_period_is_unbound_and_untouched(self):
        for t in ('Giá tuần thường khoảng 800.000đ tùy dòng xe.', 'Hai bên thống nhất mức 800.000đ khi đặt xe.'):
            self.assertEqual(apply_fixes(t), t)
            self.assertTrue(all(p.status in ('UNBOUND', 'OK', 'SKIP_DAY') for p in scan(t)))

    def test_document_vehicle_is_used_only_when_the_sentence_names_no_vehicle(self):
        t = 'Theo tuần, mức tham khảo là 800.000đ.'
        self.assertEqual(apply_fixes(t), t)                        # không biết xe nào
        phs = scan(t, doc_vehicle='airblade')
        self.assertEqual([p.status for p in phs], ['MISMATCH'])
        # đơn vị "đ" cuối câu nằm NGOÀI vùng thay (sau số là dấu chấm): ghép lại phải ra đúng câu
        p = phs[0]
        self.assertEqual(t[:p.fix_start] + p.fix_new + t[p.fix_end:], 'Theo tuần, mức tham khảo là 1.000.000đ.')
        phs = scan(t, doc_vehicle='vision')                        # xe khác => giá đúng khác (cùng 1.000.000 cho Vision)
        self.assertEqual([p.status for p in phs], ['MISMATCH'])

    def test_section_heading_names_the_vehicle_and_a_compared_vehicle_makes_it_ambiguous(self):
        simple = '### Honda Air Blade\n\nGiá thuê 200.000đ/ngày, 1.400.000đ/tháng.\n'
        self.assertEqual(apply_fixes(simple), '### Honda Air Blade\n\nGiá thuê 200.000đ/ngày, 1.500.000đ/tháng.\n')
        compared = '### Honda Air Blade\n\nXe ga thể thao, chắc chắn hơn Vision. Giá thuê 200.000đ/ngày, 1.400.000đ/tháng.\n'
        self.assertEqual(apply_fixes(compared), compared)              # không đoán: Air Blade hay Vision
        self.assertTrue(all(p.status == 'UNBOUND' for p in scan(compared)))
        other = '### Giá thuê\n\nHonda Vision rộng cốp. Giá thuê tuần 800.000đ.\n'
        # heading không nêu xe: dùng xe duy nhất của câu trước
        self.assertEqual(apply_fixes(other), '### Giá thuê\n\nHonda Vision rộng cốp. Giá thuê tuần 1.000.000đ.\n')

    def test_fixing_is_idempotent(self):
        t = ('Honda Vision: 200.000đ/ngày, từ 800.000đ đến 1.000.000đ/tuần, 1.800.000đ đến 2.000.000đ/tháng. '
             'Honda Air Blade: 800.000đ/tuần, 1.400.000đ/tháng. Honda Click: tuần 600.000đ đến 700.000đ, tháng 1.000.000đ đến 1.200.000đ.')
        once = apply_fixes(t)
        self.assertEqual(apply_fixes(once), once)
        self.assertFalse([p for p in scan(once) if p.status in ('MISMATCH', 'REVIEW')])


class TestBuildPricePatches(unittest.TestCase):
    FRONT = '---\ntitle: "Honda Air Blade tuần 800.000đ"\ndescription: "D"\n---\n'

    def edits(self, text):
        phs = [p for p in scan(text) if p.status == 'MISMATCH']
        return B.build_edits(text, phs)

    def test_old_context_is_unique_and_replays_to_the_fixed_text(self):
        text = self.FRONT + '\nHonda Air Blade giá 200.000đ/ngày, 800.000đ/tuần và 1.400.000đ/tháng.\n\nKhác: Honda Vision 200.000đ/ngày.\n'
        edits, blocked, non_unique = self.edits(text)
        self.assertEqual(non_unique, [])
        self.assertEqual(len(edits), 1)                             # hai cụm gần nhau gộp một sửa
        e = edits[0]
        self.assertEqual(text.count(e['old']), 1)
        fixed = text.replace(e['old'], e['new'])
        self.assertIn('1.000.000đ/tuần và 1.500.000đ/tháng', fixed)

    def test_title_line_is_never_edited_and_is_reported(self):
        text = self.FRONT + '\nHonda Air Blade giá 800.000đ/tuần.\n'
        edits, blocked, _ = self.edits(text)
        self.assertEqual([p.text for p in blocked], ['800.000đ'])
        for e in edits:
            self.assertNotIn('title:', e['old'])
        fixed = text
        for e in edits:
            fixed = fixed.replace(e['old'], e['new'])
        self.assertIn('title: "Honda Air Blade tuần 800.000đ"', fixed)     # title nguyên vẹn
        self.assertIn('giá 1.000.000đ/tuần', fixed)

    def test_edits_never_overlap_and_replay_through_the_revise_tool(self):
        """Cụm cách nhau 10 / 45 / 70 ký tự trong cùng dòng: mọi sửa sinh ra phải áp được bằng revise-published.apply_edits
        (công cụ từ chối sửa chồng nhau) và cho đúng văn bản đã sửa."""
        gaps = [' ' * 1, ' và ' + 'x' * 38, ' rồi ' + 'y' * 66]
        line = ('Honda Air Blade giá 800.000đ/tuần' + gaps[0] + 'và 1.400.000đ/tháng' + gaps[1]
                + '; Honda Vision có gói tuần từ 800.000đ đến 1.000.000đ' + gaps[2] + '; Honda Click tuần 600.000đ đến 700.000đ.')
        text = self.FRONT.replace('Honda Air Blade tuần 800.000đ', 'Bảng giá') + '\n' + line + '\n'
        edits, _, non_unique = self.edits(text)
        self.assertEqual(non_unique, [])
        out, _ = R.apply_edits(text, edits)
        expect = apply_fixes(text)
        self.assertEqual(out, expect)
        self.assertIn('1.000.000đ/tuần', out)
        self.assertIn('Honda Click tuần 700.000đ.', out)

    def test_residual_check_flags_leftovers_but_honours_reviewed_keep_snippets(self):
        txt = 'Honda Wave: 150.000đ/ngày; giá tuần hãy liên hệ Nguyễn Tú. Vision tuần 800 nghìn đồng, tháng 1,4 triệu đồng.'
        left = pp.find_residual(txt, EXPECTED)
        kinds = {x.split(':')[0] for x in left}
        self.assertTrue({'ALT_STALE', 'WAVE_ABSENT'} <= kinds, left)
        keep = ('Vision tuần 800 nghìn đồng, tháng 1,4 triệu đồng',)
        self.assertEqual({x.split(':')[0] for x in pp.find_residual(txt, EXPECTED, '', keep)}, {'WAVE_ABSENT'})
        clean = 'Honda Wave: 150.000đ/ngày, 700.000đ/tuần, 900.000đ đến 1.200.000đ/tháng.'
        self.assertEqual(pp.find_residual(clean, EXPECTED), [])
        arithmetic = 'Vắng bốn ngày, bạn để mất 800.000đ nếu chọn giữ xe 200.000đ một ngày.'
        self.assertEqual([x for x in pp.find_residual(arithmetic, EXPECTED) if 'STALE' in x], [x for x in pp.find_residual(arithmetic, EXPECTED) if 'STALE' in x])

    def test_non_unique_context_is_skipped_for_manual_handling(self):
        line = 'Honda Air Blade giá 800.000đ/tuần.'
        text = self.FRONT.replace('Honda Air Blade tuần 800.000đ', 'Bảng giá') + '\n' + line + '\n' + line + '\n'
        edits, _, non_unique = self.edits(text)
        self.assertEqual(edits, [])
        self.assertEqual(len(non_unique), 2)


if __name__ == '__main__':
    unittest.main()
