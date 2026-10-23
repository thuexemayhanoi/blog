#!/usr/bin/env python3
"""SEO Master — sinh danh sách sửa giá `revise-patches/1` cho `scripts/factory/revise-published.py`.

Đọc `_data/pricing.yml` (giá chủ xe duyệt), quét thân/description từng bài bằng `price_phrases.py`
(chỉ kỳ hạn tuần/tháng; cụm gắn được MỘT xe + MỘT kỳ hạn) và xuất mỗi cụm lệch giá thành một sửa
`old -> new` có ngữ cảnh DUY NHẤT trong bài. KHÔNG ghi bài, KHÔNG ghi evidence: kết quả chỉ là đề xuất
để `revise-published.py plan` chấm lại độc lập rồi `apply` ghi (có chủ duyệt, có sao lưu).

Không sửa: dòng `title:` (bất biến theo matrix/URL; cụm nằm ở title được liệt kê ở `blocked_title`),
cụm không ràng buộc được xe/kỳ hạn (UNBOUND), câu có phép tính/so sánh (REVIEW: chỉ khi --include-review).
Cụm mà ngữ cảnh không duy nhất trong dòng bị bỏ qua (`non_unique`) để người xử lý tay.

`--manual FILE` nhận các sửa DO NGƯỜI DUYỆT (JSON: {"BLG-xxx": {"edits": [{"old", "new", "count"?}], "keep": ["đoạn số học hợp lệ"],
"skip": "lý do"}}): chồng được với sửa tự động (cụm tự động nằm trong vùng sửa tay bị bỏ). Mỗi bài LUÔN được quét lại sau khi sửa
(`find_residual`): còn cụm lệch, giá cũ viết kiểu k/tr/triệu/nghìn hoặc câu "Wave chưa có giá tuần/tháng" ngoài `keep` thì bài KHÔNG
vào danh sách (`residual`) — không bao giờ sửa dở một bài khiến nó tự mâu thuẫn.

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


def manual_spans(text: str, edits: list[dict]) -> list[pp.Phrase]:
    """Sửa tay -> vùng thay trong văn bản gốc (`old` phải xuất hiện đúng `count` lần, mặc định 1)."""
    out = []
    for ed in edits:
        old, new, count = ed["old"], ed["new"], ed.get("count", 1)
        pos = [m.start() for m in re.finditer(re.escape(old), text)]
        if len(pos) != count:
            raise ValueError(f"sửa tay: {old[:60]!r} xuất hiện {len(pos)} lần, cần {count}")
        for a in pos:
            ph = pp.Phrase(a, a + len(old), old, 0, 0, False, vehicle="manual", period="", status="MANUAL")
            ph.fix_start, ph.fix_end, ph.fix_old, ph.fix_new = a, a + len(old), old, new
            out.append(ph)
    return out


def window_for(text: str, g: list[pp.Phrase]):
    """Cửa sổ ngữ cảnh NHỎ NHẤT (trong một dòng) bao các cụm của nhóm sao cho chuỗi `old` là DUY NHẤT trong bài."""
    ls, le = line_bounds(text, g[0].fix_start)
    a0, b0 = g[0].fix_start, g[-1].fix_end
    for k in CTX_STEPS:
        a, b = max(ls, a0 - k), min(le, b0 + k)
        if text.count(text[a:b]) == 1:
            return a, b
    return None


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
    placed: list[tuple[int, int, list[pp.Phrase]]] = []
    non_unique = []
    for g in groups:
        w = window_for(text, g)
        # hai cửa sổ ngữ cảnh chạm nhau => gộp thành MỘT sửa (công cụ revise từ chối các sửa chồng nhau)
        while w is not None and placed and placed[-1][1] > w[0]:
            g = placed.pop()[2] + g
            w = window_for(text, g)
        if w is None:
            non_unique.append(g)
        else:
            placed.append((w[0], w[1], g))
    edits = []
    for a, b, g in placed:
        new, pos = [], a
        for p in g:
            new += [text[pos:p.fix_start], p.fix_new]
            pos = p.fix_end
        new.append(text[pos:b])
        edits.append({"old": text[a:b], "new": "".join(new), "note": "; ".join(f"{p.vehicle}/{p.period}" for p in g)})
    return edits, blocked, non_unique


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out")
    ap.add_argument("--pricing", help="đường dẫn pricing.yml (mặc định _data/pricing.yml)")
    ap.add_argument("--ids", default="")
    ap.add_argument("--include-review", action="store_true", help="gồm cả cụm trong câu có phép tính/so sánh (đã được người duyệt)")
    ap.add_argument("--manual", help="JSON các sửa tay đã duyệt (xem đầu file)")
    ap.add_argument("--only-manual", action="store_true", help="chỉ xử lý các ID có trong --manual")
    ap.add_argument("--only-intact", action="store_true", help="chỉ bài có evidence nguyên vẹn (revise-published.py chỉ sửa được loại này)")
    ap.add_argument("--purpose", default="price-sync")
    ap.add_argument("--reason", default="Đồng bộ giá thuê tuần/tháng với _data/pricing.yml (bảng giá chủ xe duyệt)")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    expected = pp.load_expected(Path(a.pricing) if a.pricing else None)
    rows = load_rows()
    want = {x.strip() for x in a.ids.split(",") if x.strip()}
    statuses = {"MISMATCH"} | ({"REVIEW"} if a.include_review else set())
    manual = json.loads(Path(a.manual).read_text(encoding="utf-8")) if a.manual else {}
    patches = {}
    report = {"posts_scanned": 0, "blocked_title": {}, "non_unique": {}, "skipped_drift": [], "residual": {}, "skipped_by_reviewer": {},
              "manual_errors": {}}
    for row in rows.values():
        if row["status"] != "PUBLISHED" or (want and row["id"] not in want):
            continue
        if a.only_manual and row["id"] not in manual:
            continue
        if manual.get(row["id"], {}).get("skip"):
            report["skipped_by_reviewer"][row["id"]] = manual[row["id"]]["skip"]
            continue
        path = ROOT / row["output_path"]
        if not path.is_file():
            continue
        report["posts_scanned"] += 1
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        tm = re.search(r"^title:\s*(.+)$", text, re.M)
        vt = pp.vehicles_in(tm.group(1) if tm else "")
        doc_vehicle = vt[0] if len(vt) == 1 else ""
        phs = [p for p in pp.scan_text(text, expected, doc_vehicle) if p.status in statuses]
        mine = manual.get(row["id"], {})
        try:
            spans = manual_spans(text, mine.get("edits", []))
        except ValueError as e:
            report["manual_errors"][row["id"]] = str(e)
            continue
        if not phs and not spans:
            continue
        if a.only_intact and not evidence_intact(row, raw):
            report["skipped_drift"].append(row["id"])
            continue
        phs = [p for p in phs if not any(p.fix_start < s.fix_end and s.fix_start < p.fix_end for s in spans)]
        edits, blocked, non_unique = build_edits(text, phs + spans)
        if blocked:
            report["blocked_title"][row["id"]] = [p.text for p in blocked]
        if non_unique:
            report["non_unique"][row["id"]] = [[p.text for p in g] for g in non_unique]
        if blocked or non_unique:
            continue                      # sửa dở sẽ làm bài tự mâu thuẫn: dành cho người xử lý tay
        new_text = text
        for e in edits:
            new_text = new_text.replace(e["old"], e["new"])
        left = pp.find_residual(new_text, expected, doc_vehicle, tuple(mine.get("keep", ())))
        if left:
            report["residual"][row["id"]] = left
            continue
        if edits:
            patches[row["id"]] = {"edits": edits}
    out = {"schema": PATCHES_SCHEMA, "purpose": a.purpose, "reason": a.reason, "patches": patches}
    summary = {"patches": len(patches), "edits": sum(len(p["edits"]) for p in patches.values()),
               "posts_scanned": report["posts_scanned"], "skipped_drift": len(report["skipped_drift"]),
               "blocked_title": len(report["blocked_title"]), "non_unique": len(report["non_unique"]),
               "residual": len(report["residual"]), "manual_errors": len(report["manual_errors"]),
               "skipped_by_reviewer": len(report["skipped_by_reviewer"])}
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if a.report:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
