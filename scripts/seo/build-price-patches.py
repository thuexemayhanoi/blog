#!/usr/bin/env python3
"""SEO Master — sinh danh sách sửa giá `revise-patches/1` cho `scripts/factory/revise-published.py`.

Đọc `_data/pricing.yml` (giá chủ xe duyệt), quét thân/description từng bài bằng `price_phrases.py`
(chỉ kỳ hạn tuần/tháng; cụm gắn được MỘT xe + MỘT kỳ hạn) và xuất mỗi cụm lệch giá thành một sửa
`old -> new` có ngữ cảnh DUY NHẤT trong bài. KHÔNG ghi bài, KHÔNG ghi evidence: kết quả chỉ là đề xuất
để `revise-published.py plan` chấm lại độc lập rồi `apply` ghi (có chủ duyệt, có sao lưu).

Không sửa: dòng `title:` (bất biến theo matrix/URL; cụm nằm ở title được liệt kê ở `blocked_title`),
cụm không ràng buộc được xe/kỳ hạn (UNBOUND), câu có phép tính/so sánh (REVIEW: chỉ khi --include-review).
Cụm mà ngữ cảnh không duy nhất trong dòng bị bỏ qua (`non_unique`) để người xử lý tay.

Dùng:
  python3 scripts/seo/build-price-patches.py --out patches.json [--include-review] [--ids BLG-1,BLG-2]
         [--pricing FILE] [--only-intact] [--report]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import price_phrases as pp  # noqa: E402

PATCHES_SCHEMA = "revise-patches/1"
CTX_STEPS = (16, 24, 32, 48, 72, 120)


def load_rows() -> dict[str, dict]:
    with open(ROOT / "data/content-matrix.csv", encoding="utf-8", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def fingerprint(row: dict) -> str:
    fields = ("title", "intent", "primary_keyword", "expected_url", "output_path", "canonical_url")
    return hashlib.sha256(json.dumps({k: row[k] for k in fields}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def evidence_intact(row: dict, post: bytes) -> bool:
    p = ROOT / "data/qa" / f"{row['id']}.json"
    if not p.is_file():
        return False
    ev = json.loads(p.read_text(encoding="utf-8"))
    return (hashlib.sha256(post).hexdigest() == ev.get("content_sha256")
            and fingerprint(row) == ev.get("matrix_row_sha256"))


def line_bounds(text: str, pos: int) -> tuple[int, int]:
    s = text.rfind("\n", 0, pos) + 1
    e = text.find("\n", pos)
    return s, len(text) if e < 0 else e


def title_span(text: str) -> tuple[int, int]:
    m = re.search(r"^title:.*$", text, re.M)
    return (m.start(), m.end()) if m else (-1, -1)


def build_edits(text: str, phrases: list[pp.Phrase]):
    """Nhóm các cụm gần nhau trong cùng dòng thành MỘT sửa; mở rộng ngữ cảnh cho tới khi `old` duy nhất."""
    t0, t1 = title_span(text)
    blocked, todo = [], []
    for p in phrases:
        if p.fix_start < 0:
            continue
        if t0 <= p.fix_start < t1 or t0 < p.fix_end <= t1:
            blocked.append(p)
        else:
            todo.append(p)
    todo.sort(key=lambda p: p.fix_start)
    groups: list[list[pp.Phrase]] = []
    for p in todo:
        if groups and line_bounds(text, groups[-1][-1].fix_start)[0] == line_bounds(text, p.fix_start)[0] \
                and p.fix_start - groups[-1][-1].fix_end < 40:
            groups[-1].append(p)
        else:
            groups.append([p])
    edits, non_unique = [], []
    for g in groups:
        ls, le = line_bounds(text, g[0].fix_start)
        a0, b0 = g[0].fix_start, g[-1].fix_end
        chosen = None
        for k in CTX_STEPS:
            a, b = max(ls, a0 - k), min(le, b0 + k)
            old = text[a:b]
            if text.count(old) != 1:
                continue
            new, pos = [], a
            for p in g:
                new += [text[pos:p.fix_start], p.fix_new]
                pos = p.fix_end
            new.append(text[pos:b])
            chosen = {"old": old, "new": "".join(new), "note": "; ".join(f"{p.vehicle}/{p.period}" for p in g)}
            break
        if chosen is None:
            non_unique.append(g)
        else:
            edits.append(chosen)
    return edits, blocked, non_unique


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out")
    ap.add_argument("--pricing", help="đường dẫn pricing.yml (mặc định _data/pricing.yml)")
    ap.add_argument("--ids", default="")
    ap.add_argument("--include-review", action="store_true", help="gồm cả cụm trong câu có phép tính/so sánh (đã được người duyệt)")
    ap.add_argument("--only-intact", action="store_true", help="chỉ bài có evidence nguyên vẹn (revise-published.py chỉ sửa được loại này)")
    ap.add_argument("--purpose", default="price-sync")
    ap.add_argument("--reason", default="Đồng bộ giá thuê tuần/tháng với _data/pricing.yml (bảng giá chủ xe duyệt)")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    expected = pp.load_expected(Path(a.pricing) if a.pricing else None)
    rows = load_rows()
    want = {x.strip() for x in a.ids.split(",") if x.strip()}
    statuses = {"MISMATCH"} | ({"REVIEW"} if a.include_review else set())
    patches, report = {}, {"posts_scanned": 0, "blocked_title": {}, "non_unique": {}, "skipped_drift": [], "no_evidence": 0}
    for row in rows.values():
        if row["status"] != "PUBLISHED" or (want and row["id"] not in want):
            continue
        path = ROOT / row["output_path"]
        if not path.is_file():
            continue
        report["posts_scanned"] += 1
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        tm = re.search(r"^title:\s*(.+)$", text, re.M)
        vt = pp.vehicles_in(tm.group(1) if tm else "")
        phs = [p for p in pp.scan_text(text, expected, vt[0] if len(vt) == 1 else "") if p.status in statuses]
        if not phs:
            continue
        if a.only_intact and not evidence_intact(row, raw):
            report["skipped_drift"].append(row["id"])
            continue
        edits, blocked, non_unique = build_edits(text, phs)
        if blocked:
            report["blocked_title"][row["id"]] = [p.text for p in blocked]
        if non_unique:
            report["non_unique"][row["id"]] = [[p.text for p in g] for g in non_unique]
        if edits:
            patches[row["id"]] = {"edits": edits}
    out = {"schema": PATCHES_SCHEMA, "purpose": a.purpose, "reason": a.reason, "patches": patches}
    summary = {"patches": len(patches), "edits": sum(len(p["edits"]) for p in patches.values()),
               "posts_scanned": report["posts_scanned"], "skipped_drift": len(report["skipped_drift"]),
               "blocked_title": len(report["blocked_title"]), "non_unique": len(report["non_unique"])}
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if a.report:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
