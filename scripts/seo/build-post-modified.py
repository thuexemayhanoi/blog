#!/usr/bin/env python3
"""SEO Master — sinh _data/post-modified.json: ngày sửa nội dung thật của bài PUBLISHED.

Nguồn sự thật DUY NHẤT: sao lưu của scripts/factory/revise-published.py (reports/qa-audit/revise/*.json, trường
created_at = thời điểm apply, UTC; entries = ID bài đã sửa) + front matter article_id/permalink của _posts/.
Không đoán ngày từ git hay thời điểm build: chỉ bài có sửa nội dung có kiểm soát (giá, pháp lý, cọc) mới có dateModified mới.

_includes/seo.html (BlogPosting.dateModified) và _layouts/post.html (dòng "Cập nhật dd/mm/yyyy") đọc tệp này theo page.article_id.
Chạy lại sau mỗi lô revise-published (đầu ra xác định: cùng đầu vào -> cùng byte).

Dùng:
  python3 scripts/seo/build-post-modified.py           # ghi _data/post-modified.json
  python3 scripts/seo/build-post-modified.py --check   # exit 1 nếu tệp đã commit lệch nguồn
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_data" / "post-modified.json"
TZ = dt.timezone(dt.timedelta(hours=7))
FM = re.compile(r"\A---\s*\n(.*?)\n---", re.S)


def build() -> dict:
    last: dict[str, dt.datetime] = {}
    batches: list[str] = []
    for f in sorted((ROOT / "reports" / "qa-audit" / "revise").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        ts = dt.datetime.fromisoformat(d["created_at"]).astimezone(TZ)
        ents = d.get("entries") or {}
        ids = list(ents.keys()) if isinstance(ents, dict) else [e.get("id") for e in ents]
        batches.append(d.get("batch_id") or f.stem)
        for aid in ids:
            if aid and (aid not in last or ts > last[aid]):
                last[aid] = ts
    posts: dict[str, dict] = {}
    for p in sorted((ROOT / "_posts").glob("*.md")):
        head = p.read_text(encoding="utf-8")[:4000]
        m = FM.match(head)
        if not m:
            continue
        a = re.search(r"^article_id:\s*\"?([A-Z]+-\d+)", m.group(1), re.M)
        if not a or a.group(1) not in last:
            continue
        # Khóa theo article_id (bền khi URL di trú slug). KHÔNG ghi URL vào _data: check-slug-redirects.py quét _data tìm URL đã gỡ.
        posts[a.group(1)] = {"modified": last[a.group(1)].isoformat(timespec="seconds")}
    missing = sorted(set(last) - set(posts))
    if missing:
        print(f"CẢNH BÁO: {len(missing)} ID có trong sao lưu revise nhưng không thấy trong _posts: {missing[:10]}", file=sys.stderr)
    return {
        "_meta": {
            "schema": "post-modified/1",
            "source": "reports/qa-audit/revise/*.json (created_at) + _posts front matter (article_id)",
            "generator": "scripts/seo/build-post-modified.py",
            "batches": batches,
            "count": len(posts),
        },
        "posts": dict(sorted(posts.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    data = json.dumps(build(), ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    if a.check:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != data:
            print("FAIL: _data/post-modified.json lệch nguồn — chạy scripts/seo/build-post-modified.py")
            return 1
        print("OK: _data/post-modified.json khớp nguồn")
        return 0
    OUT.write_text(data, encoding="utf-8")
    print(f"OK: {OUT.relative_to(ROOT)} — {json.loads(data)['_meta']['count']} bài")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
