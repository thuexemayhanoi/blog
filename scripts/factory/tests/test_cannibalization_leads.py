#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bất biến cho sổ URL chủ lực của nhóm trùng từ khóa (cannibalization): scripts/seo/cannibalization-leads.json,
scripts/seo/build-cannibalization-classification.py, thứ tự liên kết trong scripts/seo/build-topic-links.py.

  L1  Sổ đã commit: đúng schema; mỗi nhóm có phân loại hợp lệ, lead_id dạng BLG-n, cơ sở chọn không rỗng.
  L2  Sổ khớp matrix thật: mỗi khóa vẫn còn nhóm >= 2 bài đang phát hành, chủ lực thuộc đúng nhóm đó (không phải bài PLANNED/thiếu tệp).
      (Không đòi nhóm mới phải có trong sổ: writer có thể phát hành bài mới tạo nhóm trùng; bộ sinh gắn nhãn UNREVIEWED.)
  L3  Bộ sinh phân loại: chủ lực theo sổ dù không phải bài dài nhất; nhóm ngoài sổ = UNREVIEWED + bài dài nhất; sổ lệch (lead ngoài nhóm) bị báo.
  L4  Thứ tự liên kết "Cùng chủ đề": chủ lực theo sổ đứng đầu; không có sổ thì bài dài hơn đứng trước (hành vi cũ).

Chạy: python3 scripts/factory/tests/test_cannibalization_leads.py (từ gốc repository)
"""
import csv
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


btl = load("build_topic_links", "scripts/seo/build-topic-links.py")
bcc = load("build_cannibalization_classification", "scripts/seo/build-cannibalization-classification.py")
CLASSES = {"SAME_INTENT_MONITOR", "DISTINCT_ANGLE_KEEP"}
MATRIX_COLS = ["id", "status", "title", "expected_url", "output_path", "cannibalization_key", "child_id"]


class TestRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads((ROOT / btl.LEADS_REL).read_text(encoding="utf-8"))

    def test_shape(self):
        self.assertEqual(self.reg["schema"], "cannibalization-leads/1")
        self.assertRegex(self.reg["reviewed_on"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue({"Q", "H", "C", "K", "tie"} <= set(self.reg["rules"]))
        self.assertTrue(set(self.reg["classification_legend"]) == CLASSES)
        self.assertGreaterEqual(len(self.reg["groups"]), 1)

    def test_every_group_is_well_formed(self):
        for key, g in self.reg["groups"].items():
            self.assertIn(g["classification"], CLASSES, key)
            self.assertRegex(g["lead_id"], r"^BLG-\d+$", key)
            self.assertGreaterEqual(len(g["basis"]), 20, key)
            self.assertIsInstance(g.get("cross_group_note", ""), str, key)

    def test_registry_matches_matrix(self):
        live = btl.live_members(ROOT)
        for key, g in self.reg["groups"].items():
            ids = [m["id"] for m in live.get(key, [])]
            self.assertGreaterEqual(len(ids), 2, f"{key}: không còn nhóm >= 2 bài đang phát hành")
            self.assertIn(g["lead_id"], ids, f"{key}: chủ lực {g['lead_id']} không thuộc nhóm {ids}")

    def test_cross_group_leads_exist(self):
        """Ghi chú liên nhóm nêu một ID chủ lực chung: ID đó phải là chủ lực của một nhóm trong sổ."""
        leads = {g["lead_id"] for g in self.reg["groups"].values()}
        for key, g in self.reg["groups"].items():
            for ref in re.findall(r"BLG-\d+", g.get("cross_group_note", "")):
                self.assertIn(ref, leads, f"{key}: ghi chú liên nhóm nêu {ref} nhưng không phải chủ lực nhóm nào")


def post(title, body_words, date="2026-10-10 09:00:00 +0700"):
    return f'---\ndate: {date}\nlayout: post\ntitle: "{title}"\n---\n\n' + " ".join(["từ"] * body_words) + "\n"


def make_repo(tmp, rows, registry=None):
    """rows: (id, title, url, key, body_words, child_id)"""
    root = Path(tmp)
    (root / "data").mkdir()
    (root / "_posts").mkdir()
    with (root / "data" / "content-matrix.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MATRIX_COLS)
        w.writeheader()
        for rid, title, url, key, words, child in rows:
            out = f"_posts/2026-10-10-{rid.lower()}.md"
            w.writerow({"id": rid, "status": "PUBLISHED", "title": title, "expected_url": url, "output_path": out,
                        "cannibalization_key": key, "child_id": child})
            (root / out).write_text(post(title, words), encoding="utf-8")
    (root / "data" / "content-taxonomy.json").write_text(json.dumps({"children": [
        {"child_id": "C-A", "title": "Cụm A"}, {"child_id": "C-B", "title": "Cụm B"}]}), encoding="utf-8")
    if registry is not None:
        (root / "scripts" / "seo").mkdir(parents=True)
        (root / "scripts" / "seo" / "cannibalization-leads.json").write_text(
            json.dumps({"schema": "cannibalization-leads/1", "reviewed_on": "2026-10-23", "groups": registry}), encoding="utf-8")
    return root


ROWS = [
    ("BLG-1", "Ngắn nhưng đúng truy vấn", "/a/1/", "k1", 10, "C-A"),
    ("BLG-2", "Dài nhưng hẹp", "/b/2/", "k1", 50, "C-B"),
    ("BLG-3", "Nhóm ngoài sổ, dài", "/c/3/", "k2", 40, "C-A"),
    ("BLG-4", "Nhóm ngoài sổ, ngắn", "/d/4/", "k2", 20, "C-B"),
]
REG = {"k1": {"classification": "SAME_INTENT_MONITOR", "lead_id": "BLG-1", "basis": "Q: khớp truy vấn đầu, không theo độ dài", "cross_group_note": ""}}


class TestGenerator(unittest.TestCase):
    def test_lead_follows_registry_not_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, problems = bcc.build_rows(make_repo(tmp, ROWS, REG))
        self.assertEqual(problems, [])
        by = {r["cannibalization_key"]: r for r in rows}
        self.assertEqual((by["k1"]["suggested_lead_id"], by["k1"]["lead_is_longest"], by["k1"]["longest_post_id"]), ("BLG-1", "NO", "BLG-2"))
        self.assertEqual(by["k1"]["classification"], "SAME_INTENT_MONITOR")
        self.assertTrue(by["k1"]["member_ids"].startswith("BLG-1"))
        self.assertIn("BLG-1: Cụm A", by["k1"]["member_clusters"])

    def test_group_outside_registry_is_unreviewed_and_uses_longest(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, _ = bcc.build_rows(make_repo(tmp, ROWS, REG))
        k2 = {r["cannibalization_key"]: r for r in rows}["k2"]
        self.assertEqual((k2["classification"], k2["suggested_lead_id"], k2["lead_is_longest"]), ("UNREVIEWED", "BLG-3", "YES"))
        self.assertIn("không phải quyết định", k2["lead_basis"])

    def test_registry_lead_outside_group_is_reported(self):
        bad = {"k1": dict(REG["k1"], lead_id="BLG-3")}
        with tempfile.TemporaryDirectory() as tmp:
            _, problems = bcc.build_rows(make_repo(tmp, ROWS, bad))
        self.assertTrue(any("k1" in p and "BLG-3" in p for p in problems), problems)

    def test_render_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp, ROWS, REG)
            a = bcc.render(bcc.build_rows(root)[0])
            b = bcc.render(bcc.build_rows(root)[0])
        self.assertEqual(a, b)


class TestTopicLinksOrder(unittest.TestCase):
    def test_registry_lead_first_else_longest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(tmp, ROWS + [("BLG-5", "Thứ ba, trung bình", "/e/5/", "k1", 30, "C-A")], REG)
            d = btl.build(root)
        links = [x["url"] for x in d["/b/2/"]["links"]]
        self.assertEqual(links, ["/a/1/", "/e/5/"])          # chủ lực BLG-1 đứng đầu dù ngắn nhất; còn lại theo độ dài
        self.assertEqual([x["url"] for x in d["/c/3/"]["links"]], ["/d/4/"])
        with tempfile.TemporaryDirectory() as tmp:
            d2 = btl.build(make_repo(tmp, ROWS + [("BLG-5", "Thứ ba, trung bình", "/e/5/", "k1", 30, "C-A")]))
        self.assertEqual([x["url"] for x in d2["/a/1/"]["links"]], ["/b/2/", "/e/5/"])   # không có sổ: bài dài hơn trước


if __name__ == "__main__":
    unittest.main(verbosity=2)
