#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quy tắc slug/URL DUY NHẤT của blog (Issue #77).

Mọi thành phần sinh hoặc kiểm tra slug/URL của bài PHẢI dùng module này, không tự viết lại:
  - scripts/factory/generate-matrix.py   (hàng PLANNED mới: slug, expected_url, output_path)
  - scripts/factory/refill-queue.py      (cổng G4/G4b dự đoán slug/output_path/canonical của ứng viên)
  - scripts/factory/expand-topic-universe.py (khoá trùng norm)
  - scripts/seo/slugs.py                 (audit/di trú slug đ -> d)
  - scripts/factory/migrate-slug-urls.py (công cụ di trú URL bài đã xuất bản)
  - scripts/factory/validate.py          (chính sách slug: mọi hàng factory phải khớp slugify(title))
`test_slug_policy.py` quét mã nguồn để không ai thêm bản sao thứ hai.

Vì sao có module này: `norm()` (NFD rồi bỏ dấu kết hợp) làm mất chữ "đ"/"Đ" vì chúng KHÔNG có dạng phân rã
Unicode ("xe đạp điện" -> "xe-ap-ien"). Lỗi đó đã sinh ra 1.410 URL đã xuất bản thiếu chữ d. Quy tắc đúng:
chuẩn hóa NFC -> đổi đ/Đ thành d/D -> NFD bỏ dấu -> chữ thường -> chỉ giữ a-z0-9 và khoảng trắng -> khoảng trắng
thành gạch ngang -> cắt 80 ký tự -> bỏ gạch ngang đầu/cuối.

`norm()` giữ NGUYÊN hành vi cũ vì nó là khoá trùng/cannibalization của cả matrix (đổi nó sẽ trượt khoá).

CLI nhanh cho người viết: python3 scripts/factory/slugkit.py "Đặt xe trước bao lâu" -> dat-xe-truoc-bao-lau
"""
import re
import sys
import unicodedata

MAX_SLUG_LEN = 80
DATE_PLACEHOLDER = '{date}'
SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*\Z')
DATE_PREFIX_RE = re.compile(r'^\d{4}-\d{2}-\d{2}-')
# URL bài factory: chỉ ASCII thường, số, gạch ngang và '/' (không khoảng trắng/Unicode/%). Ba hình dạng thật
# đang có: /<cat>/<yyyy>/<mm>/<dd>/<slug>/ (chuẩn), /<cat>/<yyyy-mm-dd>/<slug>/ và /<cat>/<yyyy-mm-dd>-<slug>/ (legacy);
# {date} là chỗ giữ ngày của hàng PLANNED.
_SEG = r'[a-z0-9]+(?:-[a-z0-9]+)*'
FACTORY_URL_RE = re.compile(
    r'^/%(s)s/(?:\{date\}|\d{4}/\d{2}/\d{2}|\d{4}-\d{2}-\d{2})/%(s)s/\Z'
    r'|^/%(s)s/\d{4}-\d{2}-\d{2}-%(s)s/\Z' % {'s': _SEG})


def norm(s):
    """Khoá chuẩn hóa để so trùng: bỏ dấu, chữ thường, chỉ giữ a-z0-9 và khoảng trắng.
    KHÔNG đổi đ -> d (hành vi lịch sử; cannibalization_key của cả matrix dựa vào nó)."""
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def fold_d(s):
    """NFC rồi đổi đ/Đ (U+0111/U+0110, chữ duy nhất của tiếng Việt không phân rã NFD) thành d/D.
    Eth ð/Ð (U+00F0/U+00D0) trông giống hệt và cũng không phân rã NFD: gõ nhầm/dán nhầm sẽ làm mất chữ d y như lỗi gốc nên
    cũng được gập thành d/D (review Issue #77)."""
    return (unicodedata.normalize('NFC', s or '').replace('đ', 'd').replace('Đ', 'D')
            .replace('\u00f0', 'd').replace('\u00d0', 'D'))


def slugify(title):
    """Slug chuẩn của một tiêu đề. Dùng cho MỌI URL/đường dẫn tệp bài mới."""
    return re.sub(r'\s+', '-', norm(fold_d(title)))[:MAX_SLUG_LEN].strip('-')


def slugify_legacy_without_d(title):
    """Slug do phiên bản LỖI cũ sinh ra (đ/Đ bị xóa mất). CHỈ dùng để audit/dựng lại ánh xạ OLD -> NEW,
    không bao giờ để sinh URL."""
    return re.sub(r'\s+', '-', norm(title or ''))[:MAX_SLUG_LEN].strip('-')


def split_date_prefix(slug):
    """Một số bài legacy có tiền tố ngày trong slug: trả (tiền tố gồm dấu '-', phần còn lại)."""
    m = DATE_PREFIX_RE.match(slug or '')
    return (m.group(0), slug[m.end():]) if m else ('', slug or '')


def is_valid_slug(slug, allow_date_prefix=False):
    """Slug hợp lệ: chỉ a-z0-9 và gạch ngang đơn, không gạch ngang đầu/cuối, tối đa 80 ký tự
    (cộng tiền tố ngày nếu được phép)."""
    slug = slug or ''
    prefix = ''
    if allow_date_prefix:
        prefix, slug = split_date_prefix(slug)
    return bool(slug) and len(slug) <= MAX_SLUG_LEN and bool(SLUG_RE.match(slug))


def date_path(date):
    """'2026-10-07' (hoặc '2026-10-07 09:00:00 +0700') -> '2026/10/07'."""
    d = (date or '')[:10]
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', d):
        raise ValueError('ngày không hợp lệ: %r' % date)
    return d.replace('-', '/')


def expected_url(category, slug, date=None):
    """URL kỳ vọng của bài factory: /<danh mục>/<yyyy>/<mm>/<dd>/<slug>/ (ngày chưa chốt -> {date})."""
    return '/%s/%s/%s/' % (category, date_path(date) if date else DATE_PLACEHOLDER, slug)


def output_path(slug, date=None):
    """Đường dẫn tệp bài: _posts/<yyyy-mm-dd>-<slug>.md (ngày chưa chốt -> {date})."""
    return '_posts/%s-%s.md' % ((date or '')[:10] if date else DATE_PLACEHOLDER, slug)


def replace_slug_in_url(url, old_slug, new_slug):
    """Đổi phần slug ở đoạn cuối của URL, giữ nguyên mọi phần khác (cả hình dạng có tiền tố ngày
    `/hoi-dap/2026-09-29-<slug>/`). ValueError nếu đoạn cuối không kết thúc đúng bằng old_slug."""
    if not url.endswith('/'):
        raise ValueError('URL phải kết thúc bằng /: %r' % url)
    head, _, last = url[:-1].rpartition('/')
    if not last.endswith(old_slug) or (len(last) > len(old_slug) and last[-len(old_slug) - 1] != '-'):
        raise ValueError('đoạn cuối %r không kết thúc bằng slug cũ %r' % (last, old_slug))
    return '%s/%s%s/' % (head, last[:len(last) - len(old_slug)], new_slug)


def is_factory_url(url):
    """URL bài factory đúng chính sách (ASCII thường, không khoảng trắng/Unicode/%)."""
    return bool(FACTORY_URL_RE.match(url or ''))


def _selftest():
    cases = {
        'xe đạp điện': 'xe-dap-dien',
        'Đặt cọc xe máy': 'dat-coc-xe-may',
        'ĐƯỜNG ĐI Đà Nẵng': 'duong-di-da-nang',
        'Thuê xe máy ở Hà Nội': 'thue-xe-may-o-ha-noi',
        '  Xe   số -- giá?  ': 'xe-so-gia',
        'Bằng A1 chạy được những loại xe máy nào khi thuê': 'bang-a1-chay-duoc-nhung-loai-xe-may-nao-khi-thue',
        'ê (NFD) đ': 'e-nfd-d',
    }
    bad = [(t, slugify(t), want) for t, want in cases.items() if slugify(t) != want]
    if bad:
        print('SELFTEST FAIL:', bad)
        return 1
    if slugify_legacy_without_d('xe đạp điện') != 'xe-ap-ien':
        print('SELFTEST FAIL: slug cũ')
        return 1
    print('slugkit selftest OK (%d ca)' % (len(cases) + 1))
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args == ['--selftest']:
        sys.exit(_selftest())
    print(slugify(' '.join(args)))
