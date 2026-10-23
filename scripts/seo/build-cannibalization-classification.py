#!/usr/bin/env python3
"""SEO Master — sinh `reports/factory/seo-master/cannibalization-classification.csv`: mỗi nhóm bài trùng `cannibalization_key`
(cùng từ khóa chính theo matrix) với phân loại intent, URL chủ lực đã rà, cơ sở chọn và độ giống văn bản.

Đầu vào : data/content-matrix.csv, _posts/*.md, data/content-taxonomy.json,
          scripts/seo/cannibalization-leads.json (sổ chủ lực đã rà theo INTENT — sửa tay có lý do).
Đầu ra  : reports/factory/seo-master/cannibalization-classification.csv (idempotent; --check để kiểm lệch).

Không sửa _posts, matrix, data/qa. Không đổi URL, không canonical/noindex/redirect. Nhóm chưa có trong sổ: phân loại UNREVIEWED,
chủ lực tạm = bài dài nhất (bị gắn nhãn rõ, không coi là quyết định). Độ dài bài KHÔNG phải tiêu chí chọn chủ lực của sổ.
Nhãn: FACT = đo từ tệp (trùng khóa, Jaccard 6-gram); INFERRED = đọc tiêu đề/mô tả/hub, chưa có dữ liệu truy vấn Search Console.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import itertools
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_REL = Path("reports/factory/seo-master/cannibalization-classification.csv")
_spec = importlib.util.spec_from_file_location("build_topic_links", Path(__file__).with_name("build-topic-links.py"))
btl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(btl)

FIELDS = ["no", "cannibalization_key", "group_size", "classification", "suggested_lead_id", "suggested_lead_url", "lead_basis",
          "longest_post_id", "lead_is_longest", "cross_group_note", "max_body_similarity_6gram", "member_ids", "member_urls",
          "member_clusters", "action_now", "action_later", "evidence_type", "reviewed_on"]
UNREVIEWED = "UNREVIEWED"


def shingles(text: str, n: int = 6) -> set[str]:
    body = btl.split_front(text)[1]
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)
    w = re.sub(r"[^\wÀ-ỹ ]+", " ", body.lower()).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def build_rows(root: Path = ROOT) -> tuple[list[dict], list[str]]:
    """(các dòng CSV, danh sách vấn đề của sổ chủ lực)"""
    registry = json.loads((root / btl.LEADS_REL).read_text(encoding="utf-8")) if (root / btl.LEADS_REL).is_file() else {}
    leads = registry.get("groups", {})
    reviewed_on = registry.get("reviewed_on", "")
    tax = json.loads((root / "data" / "content-taxonomy.json").read_text(encoding="utf-8")) if (root / "data" / "content-taxonomy.json").is_file() else {"children": []}
    child_title = {c["child_id"]: c["title"] for c in tax["children"]}
    matrix = {r["id"]: r for r in btl.read_matrix(root)}
    groups = {k: ms for k, ms in btl.live_members(root).items() if len(ms) >= 2 and len({m["url"] for m in ms}) == len(ms)}
    problems: list[str] = []
    for key, entry in leads.items():
        ids = [m["id"] for m in groups.get(key, [])]
        if not ids:
            problems.append(f"{key}: không còn nhóm >= 2 bài đang phát hành")
        elif entry.get("lead_id") not in ids:
            problems.append(f"{key}: lead_id {entry.get('lead_id')} không thuộc nhóm {ids}")
    rows = []
    for no, (key, ms) in enumerate(sorted(groups.items()), 1):
        longest = ms[0]  # live_members đã sắp theo (số từ giảm dần, ngày, URL)
        entry = leads.get(key)
        lead = next((m for m in ms if entry and m["id"] == entry.get("lead_id")), longest)
        cls = entry["classification"] if entry else UNREVIEWED
        sh = {m["id"]: shingles((root / matrix[m["id"]]["output_path"]).read_text(encoding="utf-8")) for m in ms}
        sim = max((len(sh[a["id"]] & sh[b["id"]]) / max(1, len(sh[a["id"]] | sh[b["id"]])) for a, b in itertools.combinations(ms, 2)), default=0.0)
        ordered = [lead] + [m for m in ms if m is not lead]
        rows.append({
            "no": f"{no:02d}", "cannibalization_key": key, "group_size": len(ms), "classification": cls,
            "suggested_lead_id": lead["id"], "suggested_lead_url": lead["url"],
            "lead_basis": entry["basis"] if entry else "chưa rà intent: tạm lấy bài dài nhất của nhóm (không phải quyết định)",
            "longest_post_id": longest["id"], "lead_is_longest": "YES" if lead is longest else "NO",
            "cross_group_note": (entry or {}).get("cross_group_note", ""),
            "max_body_similarity_6gram": f"{sim:.3f}",
            "member_ids": " | ".join(m["id"] for m in ordered), "member_urls": " | ".join(m["url"] for m in ordered),
            "member_clusters": " | ".join(f"{m['id']}: {child_title.get(matrix[m['id']].get('child_id', ''), matrix[m['id']].get('child_id', ''))}" for m in ordered),
            "action_now": 'Đã có khối "Cùng chủ đề" hai chiều (PR #50); giữ URL, không gộp/xóa/redirect',
            "action_later": ("Giữ riêng; phân biệt intent bằng liên kết ngữ cảnh" if cls == "DISTINCT_ANGLE_KEEP" else
                             "Rà intent và xếp loại trong scripts/seo/cannibalization-leads.json" if cls == UNREVIEWED else
                             "Xem xét gộp nội dung + chuyển hướng HTTP 301 khi có hạ tầng 301, dữ liệu Search Console của blog và chủ duyệt URL chủ lực"),
            "evidence_type": "FACT(trùng khóa matrix; Jaccard 6-gram thân bài) + INFERRED(đọc tiêu đề, mô tả và hub; chưa có dữ liệu truy vấn Search Console)",
            "reviewed_on": reviewed_on if entry else "",
        })
    return rows, problems


def render(rows: list[dict]) -> str:
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / OUT_REL))
    ap.add_argument("--check", action="store_true", help="không ghi; thoát 1 nếu tệp hiện có khác bản sinh lại hoặc sổ chủ lực có vấn đề")
    args = ap.parse_args(argv)
    rows, problems = build_rows()
    for p in problems:
        print("VẤN ĐỀ:", p)
    text = render(rows)
    out = Path(args.out)
    if args.check:
        have = out.read_text(encoding="utf-8") if out.exists() else ""
        if have != text:
            print(f"LỆCH: {out} không khớp matrix/_posts/sổ chủ lực hiện tại (chạy lại build-cannibalization-classification.py)")
            return 1
        print(f"OK: {out}")
        return 1 if problems else 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    unrev = sum(1 for r in rows if r["classification"] == UNREVIEWED)
    print(f"ghi {out}: {len(rows)} nhóm ({unrev} chưa rà intent), {sum(r['group_size'] for r in rows)} bài")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
