#!/usr/bin/env python3
"""SEO Master — sinh _data/taxonomy-overrides.yml cho bài PUBLISHED có parent_id/child_id front matter KHÔNG tồn tại
trong taxonomy (ví dụ P-AN-TOAN-PHAP-LY, child_id "undefined"). Không sửa _posts/ (bằng chứng QA giữ nguyên SHA):
giá trị đúng lấy từ hàng matrix (data/content-matrix.csv = nguồn sự thật) và chỉ áp dụng khi render
(_includes/article-breadcrumb.html, _layouts/post.html, _layouts/topic.html).

Chỉ ghi ID có front matter sai VÀ hàng matrix hợp lệ (parent/child có trong data/content-taxonomy.json, child thuộc parent).

Dùng:
  python3 scripts/seo/build-taxonomy-overrides.py           # ghi tệp
  python3 scripts/seo/build-taxonomy-overrides.py --check   # exit 1 nếu tệp lệch nguồn
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_data" / "taxonomy-overrides.yml"
FM = re.compile(r"\A---\s*\n(.*?)\n---", re.S)


def fm_value(fm: str, key: str) -> str | None:
    m = re.search(rf"^{key}:\s*\"?([^\"\n]*)\"?\s*$", fm, re.M)
    return m.group(1).strip() if m else None


def build() -> str:
    tax = json.loads((ROOT / "data" / "content-taxonomy.json").read_text(encoding="utf-8"))
    parents = {p["parent_id"] for p in tax["parents"]}
    child_parent = {c["child_id"]: c["parent_id"] for c in tax["children"]}
    with (ROOT / "data" / "content-matrix.csv").open(encoding="utf-8", newline="") as fh:
        matrix = {r["id"]: r for r in csv.DictReader(fh)}
    rows = []
    for p in sorted((ROOT / "_posts").glob("*.md")):
        m = FM.match(p.read_text(encoding="utf-8")[:4000])
        if not m:
            continue
        aid = fm_value(m.group(1), "article_id")
        if not aid:
            continue
        pid, cid = fm_value(m.group(1), "parent_id"), fm_value(m.group(1), "child_id")
        ok = pid in parents and cid in child_parent and child_parent[cid] == pid
        if ok:
            continue
        r = matrix.get(aid)
        if not r:
            continue
        mp, mc = r.get("parent_id", ""), r.get("child_id", "")
        if mp in parents and child_parent.get(mc) == mp:
            rows.append((aid, mp, mc, pid, cid))
    lines = [
        "# SINH TỰ ĐỘNG bởi scripts/seo/build-taxonomy-overrides.py — KHÔNG sửa tay.",
        "# Bài PUBLISHED có parent_id/child_id front matter không có trong taxonomy; giá trị đúng lấy từ data/content-matrix.csv.",
        "# Chỉ dùng khi render (breadcrumb, bài liên quan, danh sách hub); không đổi byte _posts/, URL hay canonical.",
    ]
    for aid, mp, mc, pid, cid in rows:
        lines.append(f'{aid}: {{p: {mp}, c: {mc}}}  # front matter: parent_id={pid or "-"}, child_id={cid or "-"}')
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    data = build()
    if a.check:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != data:
            print("FAIL: _data/taxonomy-overrides.yml lệch nguồn — chạy scripts/seo/build-taxonomy-overrides.py")
            return 1
        print("OK: _data/taxonomy-overrides.yml khớp nguồn")
        return 0
    OUT.write_text(data, encoding="utf-8")
    print(f"OK: {OUT.relative_to(ROOT)} — {data.count(chr(10)) - 3} bài")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
