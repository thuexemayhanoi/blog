#!/usr/bin/env python3
"""SEO Master — sinh `_data/price-notices.json`: danh sách bài PUBLISHED còn nêu giá tuần/tháng cũ mà chưa sửa được nội dung gốc.

Với những bài này `_includes/price-notice.html` hiển thị khối "Giá thuê tham khảo hiện hành" lấy từ `_data/pricing.yml` (bảng giá chủ xe),
không đổi byte bài, không đụng evidence. Bài sửa được qua `revise-published.py` thì sửa gốc, không nằm trong danh sách này.

Một bài vào danh sách khi `price_phrases.find_residual` còn báo: cụm giá tuần/tháng lệch bảng giá hiện hành, giá cũ viết kiểu nghìn/triệu,
cụm không ràng buộc được xe/kỳ hạn mang số cũ, hoặc câu nói Wave chưa có giá tuần/tháng. Chỉ xét bài PUBLISHED có evidence QA (bài legacy
không evidence sửa trực tiếp được nên không dùng khối này). `EXCLUDE` là các bài đã duyệt tay là dương tính giả (số không phải giá thuê).

  python3 scripts/seo/build-price-notices.py [--pricing FILE] [--out _data/price-notices.json] [--check] [--report]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import price_phrases as pp  # noqa: E402

OUT = ROOT / "_data" / "price-notices.json"
SCHEMA = "price-notices/1"
# Dương tính giả đã đọc: số 0,8–0,9 là hệ số bám của lốp (BLG-04794); "400–600 nghìn" là mức phạt không đội mũ bảo hiểm (BLG-00634);
# "7 ngày = 1.400.000đ" của BLG-02389 là phép nhân giá ngày (đúng), không phải giá tuần cũ.
# Sau lô sửa giá (revise-published) bốn bài sau chỉ còn câu tính ĐÚNG từ giá hiện hành (đã đọc tay từng câu): BLG-02158 ("bảy ngày là 1,4 triệu" = 7 × 200.000đ),
# BLG-02383 ("dòng tay ga lớn hơn tầm 1.000.000 đồng" = giá tuần Vision/Air Blade), BLG-02384 ("khoảng cách 600.000–1.100.000 đ" = chênh giá tháng
# nhóm xe số và Vision), BLG-03582 ("hai tuần Click hay Mio là 1,4 triệu" = 2 × 700.000đ).
# Ba bài về mức PHẠT giao thông: số 600.000/800.000 đ là tiền phạt (BLG-00639 phạt nguội 600.000–800.000 đ và "400–600 nghìn"; BLG-00872 chở 2 người tối đa 800.000 đ;
# BLG-00874 không mũ bảo hiểm tối đa 600.000 đ), không phải giá thuê xe — trùng ngẫu nhiên với số giá cũ nên bị bộ quét gắn cờ.
EXCLUDE = {"BLG-04794", "BLG-00634", "BLG-02389", "BLG-02158", "BLG-02383", "BLG-02384", "BLG-03582", "BLG-00639", "BLG-00872", "BLG-00874"}


def post_url(row: dict, text: str) -> str:
    m = re.search(r"^permalink:\s*(\S+)", text, re.M)
    return m.group(1).strip("\"'") if m else row["expected_url"]


def build(pricing: Path | None = None, root: Path = ROOT) -> dict:
    expected = pp.load_expected(pricing)
    posts: dict[str, dict] = {}
    with (root / "data" / "content-matrix.csv").open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["status"] == "PUBLISHED"]
    for r in rows:
        if r["id"] in EXCLUDE or not (root / "data" / "qa" / f"{r['id']}.json").is_file():
            continue
        path = root / r["output_path"]
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        tm = re.search(r"^title:\s*(.+)$", text, re.M)
        vt = pp.vehicles_in(tm.group(1) if tm else "")
        residual = pp.find_residual(text, expected, vt[0] if len(vt) == 1 else "")
        if residual:
            posts[post_url(r, text)] = {"id": r["id"], "kinds": sorted({x.split(":")[0] for x in residual})}
    meta = {"schema": SCHEMA, "posts": len(posts),
            "source": "scripts/seo/price_phrases.find_residual trên bài PUBLISHED có evidence; bảng giá lấy từ _data/pricing.yml lúc build",
            "note": "Sinh bởi scripts/seo/build-price-notices.py — KHÔNG sửa tay. Gỡ bài khỏi danh sách khi nội dung gốc đã được sửa qua revise-published.py."}
    return {"_meta": meta, "posts": dict(sorted(posts.items()))}


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pricing")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true", help="không ghi; thoát 1 nếu tệp hiện có khác bản sinh lại")
    ap.add_argument("--report", action="store_true", help="in số bài theo loại tồn dư")
    a = ap.parse_args(argv)
    data = build(Path(a.pricing) if a.pricing else None)
    text = render(data)
    out = Path(a.out)
    if a.report:
        from collections import Counter
        print(json.dumps(Counter(k for v in data["posts"].values() for k in v["kinds"]), ensure_ascii=False))
    if a.check:
        if (out.read_text(encoding="utf-8") if out.exists() else "") != text:
            print(f"LỆCH: {out} không khớp bản sinh lại (chạy lại build-price-notices.py)")
            return 1
        print(f"OK: {out}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"ghi {out}: {len(data['posts'])} bài")
    return 0


if __name__ == "__main__":
    sys.exit(main())
