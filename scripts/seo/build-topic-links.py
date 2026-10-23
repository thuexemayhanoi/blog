#!/usr/bin/env python3
"""SEO Master — sinh `_data/seo-topic-links.json`: liên kết ngữ cảnh hai chiều giữa các bài CÙNG `cannibalization_key`
(cùng từ khóa chính theo matrix) nằm ở cụm khác nhau, để người đọc và công cụ tìm kiếm thấy chúng là cùng một chủ đề.

Đầu vào : data/content-matrix.csv (cannibalization_key, status, output_path, expected_url), _posts/*.md (title, permalink, robots).
Đầu ra  : _data/seo-topic-links.json — khóa = URL thật của bài, giá trị = danh sách bài cùng chủ đề (tiêu đề + URL).
          Template `_includes/topic-siblings.html` đọc tệp này; trang không có trong tệp thì không in gì.

Không sửa _posts, matrix, data/qa. Không đổi URL, không canonical/noindex/redirect, không xóa hay gộp bài.
Nhóm chỉ gồm bài đang phát hành (PUBLISHED/EXISTING/REVIEW, tệp có thật, không noindex, không published:false).
Thứ tự liên kết: bài dài hơn trước (bài chủ lực đề xuất của nhóm đứng đầu), rồi theo ngày — ổn định, không ngẫu nhiên.
Mỗi bài tối đa MAX_LINKS liên kết (nhóm lớn hơn: giữ bài dài nhất). Idempotent: chạy lại không đổi byte khi dữ liệu nguồn không đổi.

Nhãn: FACT = đọc từ tệp. Việc bài nào là "chủ lực" chỉ là đề xuất (INFERRED, theo độ dài) — template KHÔNG nêu bài nào là chủ lực.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_data" / "seo-topic-links.json"
LIVE_STATUS = ("PUBLISHED", "EXISTING", "REVIEW")
MAX_LINKS = 3
SCHEMA = "seo-topic-links/1"
META_KEY = "_meta"


def read_matrix(root: Path = ROOT) -> list[dict]:
    with (root / "data" / "content-matrix.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def split_front(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---", 4)
    if end < 0:
        return "", text
    return text[4:end], text[end + 4:].lstrip("\n")


def yaml_scalar(raw: str) -> str:
    """Giá trị scalar một dòng của front matter (đủ cho title/permalink/robots): bỏ nháy và giải escape cơ bản."""
    v = raw.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        try:
            return json.loads(v)
        except ValueError:
            return v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(v) >= 2 and v[0] == "'" and v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def fm_value(fm: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*?)[ \t]*$", fm, re.M)
    return yaml_scalar(m.group(1)) if m else ""


def count_words(body: str) -> int:
    return len(re.findall(r"\w+", body, re.UNICODE))


def live_members(root: Path = ROOT) -> dict[str, list[dict]]:
    """cannibalization_key -> các bài đang phát hành, sắp theo (số từ giảm dần, ngày, URL)."""
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for r in read_matrix(root):
        key = (r.get("cannibalization_key") or "").strip()
        if not key or r["status"] not in LIVE_STATUS:
            continue
        path = root / r["output_path"]
        if not path.is_file():
            continue
        fm, body = split_front(path.read_text(encoding="utf-8"))
        if not fm:
            continue
        if fm_value(fm, "published").lower() == "false":
            continue
        if "noindex" in fm_value(fm, "robots").lower():
            continue
        title = fm_value(fm, "title")
        # URL thật: `permalink` trong front matter (50 bài ký-năng dùng dạng /yyyy-mm-dd/), không có thì expected_url của matrix
        url = fm_value(fm, "permalink") or r["expected_url"]
        if not title or not url.startswith("/"):
            continue
        groups[key].append({"id": r["id"], "title": title, "url": url, "words": count_words(body),
                            "date": fm_value(fm, "date")})
    for ms in groups.values():
        ms.sort(key=lambda m: (-m["words"], m["date"], m["url"]))
    return groups


def build(root: Path = ROOT) -> dict:
    groups = live_members(root)
    data: dict[str, dict] = {}
    n_groups = n_posts = 0
    for key, ms in sorted(groups.items()):
        if len(ms) < 2:
            continue
        # cùng URL xuất hiện hai lần (dữ liệu hỏng): bỏ, không tự sinh liên kết sai
        if len({m["url"] for m in ms}) != len(ms):
            continue
        n_groups += 1
        for m in ms:
            others = [o for o in ms if o["url"] != m["url"]][:MAX_LINKS]
            data[m["url"]] = {"group": key, "links": [{"url": o["url"], "title": o["title"]} for o in others]}
            n_posts += 1
    meta = {"schema": SCHEMA, "groups": n_groups, "posts": n_posts, "max_links": MAX_LINKS,
            "source": "data/content-matrix.csv (cannibalization_key) + _posts front matter",
            "note": "Sinh bởi scripts/seo/build-topic-links.py — KHÔNG sửa tay. Khóa = URL thật của bài."}
    return {META_KEY: meta, **dict(sorted(data.items()))}


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true", help="không ghi; thoát 1 nếu tệp hiện có khác bản sinh lại")
    args = ap.parse_args(argv)
    text = render(build())
    out = Path(args.out)
    if args.check:
        have = out.read_text(encoding="utf-8") if out.exists() else ""
        if have != text:
            print(f"LỆCH: {out} không khớp matrix/_posts hiện tại (chạy lại build-topic-links.py)")
            return 1
        print(f"OK: {out}")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    meta = json.loads(text)[META_KEY]
    print(f"ghi {out}: {meta['groups']} nhóm, {meta['posts']} bài")
    return 0


if __name__ == "__main__":
    sys.exit(main())
