"""SEO Master — hàm slug dùng chung (bản sao có chủ đích của quy tắc trong scripts/factory/generate-matrix.py).

Có hai dạng slug cho cùng một tiêu đề:
  slug_correct(title)  slug đúng hiện hành: đ -> d trước khi bỏ dấu ("xe đạp điện" -> "xe-dap-dien")
  slug_old(title)      slug do slugify cũ sinh ra: chữ đ không có dạng phân rã NFD nên bị regex xóa mất
                       ("xe đạp điện" -> "xe-ap-ien"); đây là lỗi đã khiến nhiều URL đã xuất bản thiếu chữ d

Tests: scripts/factory/tests/test_slugify_vi.py (lớp TestSeoSlugForms) khóa hành vi này và đối chiếu với generate-matrix.py.
"""
from __future__ import annotations

import re
import unicodedata

DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")
MAX_SLUG = 80


def _norm(s: str) -> str:
    """Giống generate-matrix.norm(): bỏ dấu, thường, chỉ giữ a-z0-9 và khoảng trắng."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def slug_correct(title: str) -> str:
    return re.sub(r"\s+", "-", _norm(title.replace("đ", "d").replace("Đ", "D")))[:MAX_SLUG].strip("-")


def slug_old(title: str) -> str:
    return re.sub(r"\s+", "-", _norm(title))[:MAX_SLUG].strip("-")


def split_date_prefix(slug: str) -> tuple[str, str]:
    """Một số bài legacy có tiền tố ngày trong slug: trả (tiền tố gồm dấu '-', phần còn lại)."""
    m = DATE_PREFIX.match(slug)
    return (m.group(0), slug[m.end():]) if m else ("", slug)


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
