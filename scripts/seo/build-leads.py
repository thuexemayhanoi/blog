#!/usr/bin/env python3
"""SEO Master — chọn "bài chủ lực" cho từng hub con và sinh _data/seo-leads.yml.

Mục đích (PILLAR -> HUB -> TOPIC CLUSTER -> POST): mỗi trang hub con có một khối "Bài nên đọc trước" trỏ tới vài bài
đã xuất bản khớp nhất với từ khóa cụm (`cluster_keyword` trong data/content-taxonomy.json). Đây là URL chủ lực của cụm
theo bằng chứng đo được, không phải bài mới nhất.

Nguyên tắc chọn (xác định, tái lập được, không dùng dữ liệu GSC vì blog chưa có):
  1. chỉ bài đã xuất bản thật (matrix_status PUBLISHED/EXISTING) thuộc đúng child_id;
  2. điểm = 3*[tiêu đề chứa nguyên cụm từ khóa] + 2*[tiêu đề bắt đầu bằng cụm] + 2*độ phủ token từ khóa
            + 1*điểm QA chuẩn hóa + 0.5*độ sâu (số từ, trần 1800) - 0.12*số token phụ ngoài từ khóa (trần 15):
            tiêu đề ngắn, ít token phụ = truy vấn rộng (INFERRED) nên hợp làm điểm vào của hub hơn bài long-tail;
  3. loại bài bổ trợ của nhóm trùng khóa cannibalization (chỉ bài dài nhất của nhóm được xét) để không đẩy cặp trùng intent;
  4. đa dạng: bỏ bài có tiêu đề gần trùng (Jaccard >= 0.6) với bài đã chọn;
  5. tối đa 5 bài/hub; hub không có ứng viên đạt ngưỡng tối thiểu thì để trống (không hiển thị khối).

Đầu vào : reports/factory/seo-master/url-inventory.csv (build-inventory.py), data/content-taxonomy.json, data/qa/*.json (chỉ đọc)
Đầu ra  : _data/seo-leads.yml  (KHÔNG sửa tay; chạy lại script này)
Read-only với _posts/, matrix, data/qa. Không mạng.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MAX_LEADS = 5
MIN_SCORE = 2.0  # tối thiểu: phải khớp tốt từ khóa cụm, không chọn bài lạc đề cho đủ số lượng
STOP = set("va la cua cho khi o tai co can khong nhu the nao de den tu trong voi cac mot nhung".split())


def nd(s: str) -> str:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def toks(s: str) -> frozenset[str]:
    return frozenset(w for w in re.findall(r"[a-z0-9]+", nd(s)) if w not in STOP and len(w) > 1)


def qa_score(article_id: str) -> float:
    p = ROOT / "data" / "qa" / f"{article_id}.json"
    if not article_id or not p.exists():
        return 0.9
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return max(0.0, min(1.0, (float(d.get("quality") or 0) + float(d.get("seo") or 0)) / 200.0))
    except (OSError, ValueError, TypeError):
        return 0.9


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", default=str(ROOT / "reports" / "factory" / "seo-master" / "url-inventory.csv"))
    ap.add_argument("--out", default=str(ROOT / "_data" / "seo-leads.yml"))
    ap.add_argument("--print", action="store_true", help="in kết quả dễ đọc, không ghi tệp")
    args = ap.parse_args()

    with open(args.inventory, encoding="utf-8", newline="") as fh:
        posts = [r for r in csv.DictReader(fh) if r["type"] == "Post"]
    tax = json.loads((ROOT / "data" / "content-taxonomy.json").read_text(encoding="utf-8"))

    # nhóm trùng khóa cannibalization: chỉ bài dài nhất của nhóm được xét làm bài chủ lực
    groups = collections.defaultdict(list)
    for r in posts:
        if r.get("cannibalization_key"):
            groups[r["cannibalization_key"]].append(r)
    excluded = set()
    for rs in groups.values():
        if len(rs) > 1:
            best = max(rs, key=lambda r: (int(r["words"] or 0), r["url"]))
            excluded.update(r["url"] for r in rs if r is not best)

    by_child = collections.defaultdict(list)
    for r in posts:
        if r["matrix_status"] in ("PUBLISHED", "EXISTING") and r["url"] not in excluded:
            by_child[r["child_id"]].append(r)

    result: dict[str, list[dict]] = {}
    report = []
    for c in tax["children"]:
        kw = nd(c.get("cluster_keyword") or c["title"])
        kt = toks(kw)
        if not kt:
            continue
        scored = []
        for r in by_child.get(c["child_id"], []):
            t = nd(r["title"])
            tt = toks(r["title"])
            cover = len(kt & tt) / len(kt)
            phrase = 1.0 if kw in t else 0.0
            starts = 1.0 if t.startswith(kw) else 0.0
            depth = min(int(r["words"] or 0), 1800) / 1800.0
            extra = min(len(tt - kt), 15)
            score = 3 * phrase + 2 * starts + 2 * cover + 1 * qa_score(r["article_id"]) + 0.5 * depth - 0.12 * extra
            scored.append((score, r, tt))
        scored.sort(key=lambda x: (-x[0], x[1]["url"]))
        chosen: list[tuple[float, dict, frozenset]] = []
        for score, r, tt in scored:
            if score < MIN_SCORE:
                break
            if any(len(tt & ct) / max(1, len(tt | ct)) >= 0.6 for _, _, ct in chosen):
                continue
            chosen.append((score, r, tt))
            if len(chosen) >= MAX_LEADS:
                break
        if chosen:
            result[c["child_id"]] = [{"u": r["url"], "t": r["title"]} for _, r, _ in chosen]
        report.append((c["child_id"], c["hub_url"], kw, len(by_child.get(c["child_id"], [])), len(chosen)))

    if args.print:
        for cid, hub, kw, n, k in report:
            print(f"{cid:22s} {hub:38s} kw='{kw}' candidates={n} leads={k}")
            for l in result.get(cid, []):
                print(f"     - {l['t'][:100]}")
        return 0

    header = ("# Sinh bởi scripts/seo/build-leads.py (SEO Master) — KHÔNG sửa tay; chạy lại script khi cần làm mới.\n"
              "# child_id -> danh sách bài chủ lực (u = URL thật như site phục vụ, t = tiêu đề). Dùng bởi _layouts/topic.html.\n"
              "# Tiêu chí chọn: xem docstring scripts/seo/build-leads.py. Không dùng dữ liệu GSC (blog chưa có).\n")
    body = yaml.safe_dump(result, allow_unicode=True, sort_keys=True, width=1000, default_flow_style=False)
    Path(args.out).write_text(header + body, encoding="utf-8")
    print(f"ghi {args.out}: {len(result)}/{len(tax['children'])} hub có bài chủ lực, "
          f"{sum(len(v) for v in result.values())} liên kết")
    return 0


if __name__ == "__main__":
    sys.exit(main())
