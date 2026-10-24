"""SEO Master — hàm slug cho audit/di trú, DÙNG CHUNG `scripts/factory/slugkit.py` (không còn bản sao).

Có hai dạng slug cho cùng một tiêu đề:
  slug_correct(title)  slug đúng hiện hành: đ -> d trước khi bỏ dấu ("xe đạp điện" -> "xe-dap-dien")
  slug_old(title)      slug do slugify cũ sinh ra: chữ đ không có dạng phân rã NFD nên bị regex xóa mất
                       ("xe đạp điện" -> "xe-ap-ien"); đây là lỗi đã khiến nhiều URL đã xuất bản thiếu chữ d

Tests: scripts/factory/tests/test_slugify_vi.py (lớp TestSeoSlugForms) và test_slug_policy.py.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_SLUGKIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "factory", "slugkit.py")


def _load_slugkit():
    """Nạp scripts/factory/slugkit.py THEO ĐƯỜNG DẪN (cùng một module object với `import slugkit` ở nơi khác), không thêm
    scripts/factory vào sys.path: thư mục đó có queue.py che mất module chuẩn `queue` (hỏng ThreadPoolExecutor/multiprocessing)."""
    mod = sys.modules.get("slugkit")
    if mod is None:
        spec = importlib.util.spec_from_file_location("slugkit", _SLUGKIT)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["slugkit"] = mod
        spec.loader.exec_module(mod)
    return mod


slugkit = _load_slugkit()

DATE_PREFIX = slugkit.DATE_PREFIX_RE
MAX_SLUG = slugkit.MAX_SLUG_LEN
slug_correct = slugkit.slugify
slug_old = slugkit.slugify_legacy_without_d
split_date_prefix = slugkit.split_date_prefix


def slug_forms(title: str) -> dict[str, object]:
    """Cả hai dạng + cờ cho biết tiêu đề có bị ảnh hưởng bởi lỗi chữ đ hay không."""
    ok, old = slug_correct(title), slug_old(title)
    return {"correct": ok, "old": old, "differs": ok != old}


def is_d_stripped(title: str, actual_slug: str) -> bool:
    """FACT: slug thật khớp tuyệt đối slug cũ (đ bị xóa) và khác slug đúng (bỏ qua tiền tố ngày của bài legacy)."""
    if "đ" not in title.lower():
        return False
    forms = slug_forms(title)
    if not forms["differs"]:
        return False  # chữ đ nằm sau đoạn bị cắt 80 ký tự: URL không bị ảnh hưởng
    _, rest = split_date_prefix(actual_slug)
    return rest == forms["old"]
