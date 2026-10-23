#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bất biến cho lớp "Lưu ý cập nhật pháp lý": _data/legal-notices.json, _includes/legal-notice.html, _layouts/post.html.

Lớp này chỉ HIỂN THỊ đính chính ở đầu bài PUBLISHED có nội dung gốc còn lỗi thời mà chưa sửa được qua quy trình bảo trì (evidence QA lệch
hash). Nó không đổi byte bài nên không đụng content_sha256/matrix_row_sha256.

  L1  Dữ liệu: mỗi khóa là URL thật của đúng một bài PUBLISHED, `id` khớp matrix; mọi mã đều có trong `catalog`; không mã trùng;
      mỗi mục catalog có nội dung đủ dài + nguồn https thuộc miền cơ quan nhà nước (không dẫn blog/tin tức thứ cấp).
  L2  Template: include đúng một lần trong layout post, đứng TRƯỚC mục lục; tra khóa theo page.url (không quét site.posts).
  L3  Không có bài nào vừa có đính chính vừa đang giữ lease/draft (writer đang sửa thì nên sửa gốc, không cần lớp đính chính).

Chạy: python3 scripts/factory/tests/test_legal_notices.py (từ gốc repository)
"""
import csv
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
OFFICIAL_SUFFIXES = ("chinhphu.vn", "bocongan.gov.vn", "csgt.vn")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def post_url(row):
    text = (ROOT / row["output_path"]).read_text(encoding="utf-8")
    m = re.search(r"^permalink:\s*(\S+)", text, re.M)
    return m.group(1).strip("\"'") if m else row["expected_url"]


class TestData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(read("_data/legal-notices.json"))
        with (ROOT / "data" / "content-matrix.csv").open(encoding="utf-8", newline="") as fh:
            cls.rows = list(csv.DictReader(fh))
        cls.by_url = {}
        for r in cls.rows:
            if r["status"] == "PUBLISHED" and (ROOT / r["output_path"]).is_file():
                cls.by_url[post_url(r)] = r

    def test_shape(self):
        self.assertEqual(self.data["_meta"]["schema"], "legal-notices/1")
        self.assertRegex(self.data["_meta"]["verified_on"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(self.data["verified_on_display"], r"^\d{2}/\d{2}/\d{4}$")
        self.assertTrue(self.data["catalog"] and self.data["posts"])

    def test_posts_are_real_published_posts(self):
        for url, entry in self.data["posts"].items():
            row = self.by_url.get(url)
            self.assertIsNotNone(row, f"{url}: không phải URL của bài PUBLISHED")
            self.assertEqual(entry["id"], row["id"], url)
            self.assertTrue(entry["codes"], url)
            self.assertEqual(len(entry["codes"]), len(set(entry["codes"])), f"{url}: mã trùng")

    def test_codes_exist_and_catalog_is_sourced(self):
        used = set()
        for url, entry in self.data["posts"].items():
            for code in entry["codes"]:
                self.assertIn(code, self.data["catalog"], f"{url}: mã {code} không có trong catalog")
                used.add(code)
        self.assertEqual(used, set(self.data["catalog"]), "catalog có mã không bài nào dùng")
        for code, item in self.data["catalog"].items():
            self.assertGreaterEqual(len(item["text"]), 60, code)
            self.assertTrue(item["source_label"].strip(), code)
            u = urlparse(item["source_url"])
            self.assertEqual(u.scheme, "https", code)
            host = u.hostname or ""
            self.assertTrue(any(host == s or host.endswith("." + s) for s in OFFICIAL_SUFFIXES),
                            f"{code}: nguồn {host} không thuộc miền cơ quan nhà nước")

    def test_no_notice_on_posts_with_live_lease_or_draft(self):
        claims = json.loads(read("data/state/writer-claims.json"))
        leased = {i for lease in (claims.get("leases") or {}).values() for i in lease.get("ids", [])}
        drafts = {p.stem for p in (ROOT / "_drafts").glob("*.md")} if (ROOT / "_drafts").is_dir() else set()
        for entry in self.data["posts"].values():
            self.assertNotIn(entry["id"], leased, f"{entry['id']} đang có lease")
            self.assertFalse(any(entry["id"] in d for d in drafts), f"{entry['id']} có draft")


class TestTemplate(unittest.TestCase):
    def test_layout_includes_once_before_toc(self):
        layout = read("_layouts/post.html")
        self.assertEqual(layout.count("{% include legal-notice.html %}"), 1)
        self.assertLess(layout.index("include legal-notice.html"), layout.index('class="article-toc"'))

    def test_include_is_constant_time_and_keyed_by_url(self):
        raw = read("_includes/legal-notice.html")
        inc = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", raw, flags=re.S)
        self.assertIn("site.data.legal-notices", inc)
        self.assertIn("posts[page.url]", inc)
        self.assertNotIn("site.posts", inc)
        self.assertIn('rel="noopener"', inc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
