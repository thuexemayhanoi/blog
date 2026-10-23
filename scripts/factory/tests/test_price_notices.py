#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bất biến cho khối "Giá thuê tham khảo hiện hành": scripts/seo/build-price-notices.py, _data/price-notices.json,
_includes/price-notice.html, _layouts/post.html.

Khối này chỉ HIỂN THỊ bảng giá hiện hành (nguyên từ _data/pricing.yml) ở đầu bài PUBLISHED còn nêu giá tuần/tháng cũ mà chưa sửa được
nội dung gốc; không đổi byte bài nên không đụng evidence.

  P1  Dữ liệu: mỗi khóa là URL thật của đúng một bài PUBLISHED có evidence QA, `id` khớp matrix, không bài đang có lease/draft.
  P2  Bộ sinh: bài còn tồn dư giá cũ vào danh sách; bài sạch thì không; bài trong EXCLUDE bị loại; idempotent.
  P2b check-price-consistency.py: cột disposition khớp _data/price-notices.json và EXCLUDE; mọi mã EXCLUDE là bài PUBLISHED thật.
  P3  Template: include đúng một lần trong layout post, đứng TRƯỚC mục lục; tra khóa theo page.url; số liệu chỉ qua pricing-rate-table
      (không gõ số tiền trong include); không quét site.posts.

Chạy: python3 scripts/factory/tests/test_price_notices.py (từ gốc repository)
"""
import csv
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("build_price_notices", ROOT / "scripts" / "seo" / "build-price-notices.py")
bpn = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bpn)

# kỳ vọng tối thiểu (không phụ thuộc PyYAML): Click tuần 700.000
EXPECTED = {"click": {"week": (700000, 700000), "month": (900000, 1200000)},
            "airblade": {"week": (1000000, 1000000), "month": (1500000, 1500000)}}


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class TestData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(read("_data/price-notices.json"))
        with (ROOT / "data" / "content-matrix.csv").open(encoding="utf-8", newline="") as fh:
            cls.rows = [r for r in csv.DictReader(fh) if r["status"] == "PUBLISHED"]
        cls.by_url = {}
        for r in cls.rows:
            path = ROOT / r["output_path"]
            if path.is_file():
                cls.by_url[bpn.post_url(r, path.read_text(encoding="utf-8"))] = r

    def test_shape(self):
        meta = self.data["_meta"]
        self.assertEqual(meta["schema"], bpn.SCHEMA)
        self.assertEqual(meta["posts"], len(self.data["posts"]))

    def test_posts_are_real_published_posts_with_evidence(self):
        for url, entry in self.data["posts"].items():
            row = self.by_url.get(url)
            self.assertIsNotNone(row, f"{url}: không phải URL của bài PUBLISHED")
            self.assertEqual(entry["id"], row["id"], url)
            self.assertTrue((ROOT / "data" / "qa" / f"{row['id']}.json").is_file(), f"{row['id']}: không có evidence")
            self.assertNotIn(row["id"], bpn.EXCLUDE)

    def test_no_notice_on_posts_with_live_lease_or_draft(self):
        claims = json.loads(read("data/state/writer-claims.json"))
        leased = {i for lease in (claims.get("leases") or {}).values() for i in lease.get("ids", [])}
        drafts = [p.stem for p in (ROOT / "_drafts").glob("*.md")] if (ROOT / "_drafts").is_dir() else []
        for entry in self.data["posts"].values():
            self.assertNotIn(entry["id"], leased)
            self.assertFalse(any(entry["id"] in d for d in drafts))


class TestBuilder(unittest.TestCase):
    def make_repo(self, tmp, posts):
        root = Path(tmp)
        (root / "data" / "qa").mkdir(parents=True)
        (root / "_posts").mkdir()
        with (root / "data" / "content-matrix.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["id", "status", "expected_url", "output_path"])
            w.writeheader()
            for pid, status, body, with_ev in posts:
                out = f"_posts/2026-10-10-{pid.lower()}.md"
                w.writerow({"id": pid, "status": status, "expected_url": f"/x/{pid.lower()}/", "output_path": out})
                (root / out).write_text(f'---\ntitle: "Honda Click"\nlayout: post\n---\n\n{body}\n', encoding="utf-8")
                if with_ev:
                    (root / "data" / "qa" / f"{pid}.json").write_text("{}", encoding="utf-8")
        return root

    def run_builder(self, posts):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_repo(tmp, posts)
            real = bpn.pp.load_expected
            bpn.pp.load_expected = lambda p=None: EXPECTED
            try:
                return bpn.build(root=root)
            finally:
                bpn.pp.load_expected = real

    def test_stale_post_listed_clean_post_not(self):
        d = self.run_builder([
            ("BLG-1", "PUBLISHED", "Honda Click thuê tuần 600.000 đ.", True),     # giá tuần cũ
            ("BLG-2", "PUBLISHED", "Honda Click thuê tuần 700.000 đ.", True),     # đúng bảng giá
            ("BLG-3", "PUBLISHED", "Honda Click thuê tuần 600.000 đ.", False),    # legacy không evidence: sửa trực tiếp, không dùng khối này
            ("BLG-4", "PLANNED", "Honda Click thuê tuần 600.000 đ.", True),       # chưa phát hành
        ])
        self.assertEqual({v["id"] for v in d["posts"].values()}, {"BLG-1"})
        self.assertEqual(d["_meta"]["posts"], 1)

    def test_exclude_and_idempotent(self):
        self.assertTrue(bpn.EXCLUDE)
        posts = [("BLG-1", "PUBLISHED", "Honda Click thuê tuần 600.000 đ.", True)]
        self.assertEqual(bpn.render(self.run_builder(posts)), bpn.render(self.run_builder(posts)))


class TestConsistencyReport(unittest.TestCase):
    """check-price-consistency.py gắn `disposition` theo đúng dữ liệu khối giá và danh sách dương tính giả."""

    def test_dispositions_match_data_and_exclude(self):
        spec = importlib.util.spec_from_file_location("check_price_consistency", ROOT / "scripts" / "seo" / "check-price-consistency.py")
        cpc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cpc)
        notices, reviewed = cpc.dispositions()
        self.assertEqual(notices, {v["id"] for v in json.loads(read("_data/price-notices.json"))["posts"].values()})
        self.assertEqual(reviewed, set(bpn.EXCLUDE))
        self.assertFalse(notices & reviewed)

    def test_every_excluded_id_is_a_published_post(self):
        with (ROOT / "data" / "content-matrix.csv").open(encoding="utf-8", newline="") as fh:
            published = {r["id"] for r in csv.DictReader(fh) if r["status"] == "PUBLISHED"}
        self.assertLessEqual(set(bpn.EXCLUDE), published)


class TestTemplate(unittest.TestCase):
    def test_layout_includes_once_before_toc(self):
        layout = read("_layouts/post.html")
        self.assertEqual(layout.count("{% include price-notice.html %}"), 1)
        self.assertLess(layout.index("include price-notice.html"), layout.index('class="article-toc"'))

    def test_include_is_constant_time_and_has_no_hardcoded_amounts(self):
        raw = read("_includes/price-notice.html")
        inc = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", raw, flags=re.S)
        self.assertIn("site.data.price-notices.posts[page.url]", inc)
        self.assertIn("pricing-rate-table.html", inc)
        self.assertNotIn("site.posts", inc)
        self.assertIsNone(re.search(r"\d{1,3}(?:\.\d{3})+", inc), "không gõ tay số tiền trong include")


if __name__ == "__main__":
    unittest.main(verbosity=2)
