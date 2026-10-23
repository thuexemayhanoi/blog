#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bất biến cho liên kết "Cùng chủ đề" (cannibalization): scripts/seo/build-topic-links.py,
_data/seo-topic-links.json, _includes/topic-siblings.html.

  T1  Dữ liệu đã commit: mỗi khóa là URL thật của đúng MỘT bài đang phát hành; mỗi liên kết trỏ tới bài thật có đúng tiêu đề;
      không tự link, không trùng, hai chiều (trừ nhóm lớn hơn MAX_LINKS + 1 bị cắt bớt), số liệu `_meta` khớp.
  T2  Bộ sinh: chỉ nhóm >= 2 bài đang phát hành; bỏ PLANNED/noindex/published:false/tệp thiếu; bài dài hơn đứng trước;
      cắt MAX_LINKS; ưu tiên `permalink` của front matter; idempotent.
  T3  Template: include đúng một lần trong layout post, không quét site.posts (chi phí O(1)/trang).

Chạy: python3 scripts/factory/tests/test_topic_links.py (từ gốc repository)
"""
import csv
import importlib.util
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("build_topic_links", ROOT / "scripts" / "seo" / "build-topic-links.py")
btl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(btl)

MATRIX_COLS = ["id", "status", "title", "expected_url", "output_path", "cannibalization_key"]


def post(title, body_words, extra="", date="2026-10-10 09:00:00 +0700"):
    body = " ".join(["từ"] * body_words)
    return f'---\ndate: {date}\nlayout: post\ntitle: "{title}"\n{extra}---\n\n{body}\n'


def make_repo(tmp, rows):
    """rows: (id, status, title, url, key, body_words, extra_fm, write_file)"""
    root = Path(tmp)
    (root / "data").mkdir()
    (root / "_posts").mkdir()
    with (root / "data" / "content-matrix.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MATRIX_COLS)
        w.writeheader()
        for rid, status, title, url, key, words, extra, write in rows:
            out = f"_posts/2026-10-10-{rid.lower()}.md"
            w.writerow({"id": rid, "status": status, "title": title, "expected_url": url, "output_path": out,
                        "cannibalization_key": key})
            if write:
                (root / out).write_text(post(title, words, extra), encoding="utf-8")
    return root


class TestGenerator(unittest.TestCase):
    def build(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp, rows)
            return btl.build(root)

    def test_groups_links_and_order(self):
        d = self.build([
            ("BLG-1", "PUBLISHED", "Ngắn", "/a/1/", "k1", 10, "", True),
            ("BLG-2", "PUBLISHED", "Dài", "/b/2/", "k1", 50, "", True),
            ("BLG-3", "PUBLISHED", "Lẻ loi", "/c/3/", "k2", 30, "", True),
        ])
        meta = d.pop("_meta")
        self.assertEqual((meta["groups"], meta["posts"]), (1, 2))
        self.assertEqual(set(d), {"/a/1/", "/b/2/"})                       # nhóm một bài không sinh liên kết
        self.assertEqual(d["/a/1/"]["links"], [{"url": "/b/2/", "title": "Dài"}])
        self.assertEqual(d["/b/2/"]["links"], [{"url": "/a/1/", "title": "Ngắn"}])

    def test_excluded_members(self):
        d = self.build([
            ("BLG-1", "PUBLISHED", "A", "/a/", "k", 40, "", True),
            ("BLG-2", "PLANNED", "B", "/b/", "k", 40, "", False),            # chưa phát hành
            ("BLG-3", "PUBLISHED", "C", "/c/", "k", 40, "robots: noindex\n", True),
            ("BLG-4", "PUBLISHED", "D", "/d/", "k", 40, "published: false\n", True),
            ("BLG-5", "PUBLISHED", "E", "/e/", "k", 40, "", False),           # tệp thiếu
        ])
        d.pop("_meta")
        self.assertEqual(d, {})                                              # chỉ còn một bài hợp lệ => không có nhóm

    def test_max_links_and_symmetry_threshold(self):
        rows = [(f"BLG-{i}", "PUBLISHED", f"T{i}", f"/p{i}/", "k", 100 - i, "", True) for i in range(1, 7)]
        d = self.build(rows)
        d.pop("_meta")
        self.assertEqual(len(d), 6)
        self.assertTrue(all(len(v["links"]) == btl.MAX_LINKS for v in d.values()))
        self.assertNotIn("/p1/", [l["url"] for l in d["/p1/"]["links"]])      # không tự link

    def test_permalink_beats_expected_url(self):
        d = self.build([
            ("BLG-1", "PUBLISHED", "A", "/x/2026/09/29/a/", "k", 40, "permalink: /x/2026-09-29/a/\n", True),
            ("BLG-2", "EXISTING", "B", "/y/b/", "k", 30, "", True),
        ])
        d.pop("_meta")
        self.assertEqual(set(d), {"/x/2026-09-29/a/", "/y/b/"})

    def test_title_unescape_and_idempotent(self):
        rows = [("BLG-1", "PUBLISHED", 'Câu "trích" lạ', "/a/", "k", 40, "", True),
                ("BLG-2", "PUBLISHED", "B", "/b/", "k", 30, "", True)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_repo(tmp, [])
            # tạo lại với tiêu đề có dấu nháy kép đã escape trong YAML
            (root / "_posts").mkdir(exist_ok=True)
            with (root / "data" / "content-matrix.csv").open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=MATRIX_COLS)
                w.writeheader()
                for rid, status, title, url, key, words, extra, write in rows:
                    out = f"_posts/2026-10-10-{rid.lower()}.md"
                    w.writerow({"id": rid, "status": status, "title": title, "expected_url": url, "output_path": out,
                                "cannibalization_key": key})
                    (root / out).write_text(post(title.replace('"', '\\"'), words), encoding="utf-8")
            first = btl.render(btl.build(root))
            second = btl.render(btl.build(root))
            self.assertEqual(first, second)
            self.assertEqual(json.loads(first)["/b/"]["links"][0]["title"], 'Câu "trích" lạ')


class TestCommittedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "_data" / "seo-topic-links.json").read_text(encoding="utf-8"))
        cls.meta = cls.data.pop("_meta")
        cls.live = {}
        for r in btl.read_matrix(ROOT):
            if r["status"] not in btl.LIVE_STATUS:
                continue
            path = ROOT / r["output_path"]
            if not path.is_file():
                continue
            fm, _ = btl.split_front(path.read_text(encoding="utf-8"))
            url = btl.fm_value(fm, "permalink") or r["expected_url"]
            cls.live.setdefault(url, []).append({"id": r["id"], "title": btl.fm_value(fm, "title"), "fm": fm})

    def test_meta_matches_data(self):
        self.assertEqual(self.meta["schema"], btl.SCHEMA)
        self.assertEqual(self.meta["posts"], len(self.data))
        self.assertEqual(self.meta["groups"], len({v["group"] for v in self.data.values()}))
        self.assertGreater(self.meta["groups"], 0)

    def test_keys_are_real_live_posts(self):
        for url in self.data:
            self.assertEqual(len(self.live.get(url, [])), 1, f"{url}: phải là URL của đúng một bài đang phát hành")

    def test_links_point_to_real_posts_with_exact_titles(self):
        for url, v in self.data.items():
            self.assertTrue(1 <= len(v["links"]) <= btl.MAX_LINKS, url)
            seen = set()
            for l in v["links"]:
                self.assertNotEqual(l["url"], url, f"{url}: tự link")
                self.assertNotIn(l["url"], seen, f"{url}: link trùng")
                seen.add(l["url"])
                tgt = self.live.get(l["url"])
                self.assertTrue(tgt and len(tgt) == 1, f"{url} -> {l['url']}: bài đích không tồn tại/không phát hành")
                self.assertEqual(l["title"], tgt[0]["title"], f"{l['url']}: tiêu đề lệch front matter")
                self.assertNotIn("noindex", btl.fm_value(tgt[0]["fm"], "robots").lower(), l["url"])

    def test_links_are_two_way_within_a_group(self):
        by_group = {}
        for url, v in self.data.items():
            by_group.setdefault(v["group"], []).append(url)
        for g, urls in by_group.items():
            self.assertGreaterEqual(len(urls), 2, g)
            if len(urls) > btl.MAX_LINKS + 1:
                continue                                                     # nhóm lớn bị cắt bớt, không đòi đối xứng
            for url in urls:
                self.assertEqual({l["url"] for l in self.data[url]["links"]}, set(urls) - {url}, f"{g}: {url}")


class TestTemplate(unittest.TestCase):
    def test_layout_includes_once(self):
        layout = (ROOT / "_layouts" / "post.html").read_text(encoding="utf-8")
        self.assertEqual(layout.count("{% include topic-siblings.html %}"), 1)
        self.assertLess(layout.index("include faq.html"), layout.index("include topic-siblings.html"))

    def test_include_is_constant_time_and_keyed_by_url(self):
        raw = (ROOT / "_includes" / "topic-siblings.html").read_text(encoding="utf-8")
        inc = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", raw, flags=re.S)   # chỉ xét mã, không xét chú thích
        self.assertIn("site.data.seo-topic-links[page.url]", inc)
        self.assertNotIn("site.posts", inc)                                  # không quét toàn site (O(N^2) khi build 6.000 bài)
        self.assertIn("relative_url", inc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
