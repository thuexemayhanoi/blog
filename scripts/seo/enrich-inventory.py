#!/usr/bin/env python3
"""SEO Master — làm giàu url-inventory.csv: vai trò SEO, từ khóa phụ, hành động, ưu tiên, rủi ro lỗi thời.

Chạy SAU build-inventory.py và build-matrix.py (đọc kết quả của hai script đó, ghi lại url-inventory.csv).
Idempotent: cột bổ sung được tính lại từ đầu mỗi lần chạy, kết quả giống hệt khi dữ liệu nguồn không đổi.

Đầu vào : reports/factory/seo-master/{url-inventory,technical-issues,cannibalization-risk,keyword-intent-map}.csv,
          _data/seo-leads.yml, data/content-matrix.csv (chỉ cột id/title), _posts/*.md (đọc nội dung để tìm tín hiệu lỗi thời).
Đầu ra  : url-inventory.csv (thêm cột) + khối "enrichment" trong inventory-summary.json.
Không gọi mạng, không ghi ngoài thư mục báo cáo. Nhãn: FACT = đọc từ tệp; INFERRED = heuristic (ghi rõ trong cột).

Cột thêm vào:
  seo_role              HOME | PILLAR | HUB | LISTING | PAGE | LEAD_POST | CANNIBALIZATION_LEAD | SUPPORT_POST | TOPIC_POST
  cannibalization_role  LEAD | SUPPORT | NEAR_TITLE | "" (từ cannibalization-risk.csv; ưu tiên LEAD > SUPPORT > NEAR_TITLE)
  keyword_groups        K01:L|K03:S ... (L = URL chủ lực của nhóm, S = URL bổ trợ; từ keyword-intent-map.csv)
  secondary_keywords    tối đa 3 từ khóa phụ lấy từ tags front matter (FACT), bỏ từ khóa chính
  needs_action          mã hành động, phân tách bằng "|" ("" = không có lỗi đã biết)
  fix_priority          P0..P4 (mức cao nhất trong needs_action; P4 = chỉ bảo trì định kỳ)
  action_status         OPEN | BLOCKED_URL_CONTRACT | BLOCKED_EVIDENCE_SHA | DEFERRED_OWNER_PLAN | EXPECTED | NONE
  staleness_risk        HIGH | MEDIUM | LOW | "" (INFERRED, chỉ cho bài; xem tín hiệu bên dưới)
  stale_signals         AMOUNT|LEGAL|TIME (tín hiệu có trong nội dung bài; INFERRED)
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
from urllib.parse import unquote

import yaml

from slugs import is_d_stripped

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "reports" / "factory" / "seo-master"

NEW_COLS = ["seo_role", "cannibalization_role", "keyword_groups", "secondary_keywords", "needs_action",
            "fix_priority", "action_status", "staleness_risk", "stale_signals"]

# Mã hành động -> (ưu tiên, trạng thái). Ưu tiên nhỏ = gấp hơn.
ACTIONS = {
    "CANONICAL_OR_H1_BROKEN": ("P0", "OPEN"),
    "NOT_IN_SITEMAP": ("P0", "OPEN"),
    "ORPHAN_NO_INBOUND": ("P1", "OPEN"),
    "H1_IN_BODY": ("P2", "OPEN"),
    "CANNIBALIZATION_SUPPORT": ("P2", "DEFERRED_OWNER_PLAN"),
    "SLUG_D_STRIPPED": ("P2", "BLOCKED_URL_CONTRACT"),
    "NEAR_TITLE_PAIR": ("P3", "DEFERRED_OWNER_PLAN"),
    "DESC_TOO_LONG": ("P3", "BLOCKED_EVIDENCE_SHA"),
    "LOW_INBOUND": ("P3", "OPEN"),
    "FRESHNESS_REVIEW": ("P3", "OPEN"),
    "NOINDEX_INTENTIONAL": ("P4", "EXPECTED"),
}

# Tín hiệu lỗi thời (INFERRED). Giá/phạt/quy định đổi theo thời gian nên cần rà soát định kỳ theo nguồn chính thức.
RX_AMOUNT = re.compile(r"\d[\d\.,]*\s*(?:đ\b|đồng|vnđ|vnd|nghìn|ngàn|triệu|%|km/h)", re.I)
RX_LEGAL = re.compile(r"nghị định|thông tư|\bluật\b|mức phạt|xử phạt|bị phạt|có hiệu lực", re.I)
RX_TIME = re.compile(r"\bnăm 20\d\d\b|từ ngày \d|mới nhất", re.I)  # không dùng "hiện nay"/năm trần: gần như chữ đệm


def nd(s: str) -> str:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def post_body(source_file: str) -> str:
    p = ROOT / source_file
    if not source_file or not p.is_file():
        return ""
    t = p.read_text(encoding="utf-8", errors="replace")
    if t.startswith("---"):
        parts = t.split("---", 2)
        if len(parts) == 3:
            return parts[2]
    return t


def stale_signals(body: str) -> list[str]:
    sig = []
    if RX_AMOUNT.search(body):
        sig.append("AMOUNT")
    if RX_LEGAL.search(body):
        sig.append("LEGAL")
    if RX_TIME.search(body):
        sig.append("TIME")
    return sig


def stale_level(sig: list[str]) -> str:
    s = set(sig)
    if {"AMOUNT", "LEGAL"} <= s:
        return "HIGH"
    if s:
        return "MEDIUM"
    return "LOW"


def slug_d_stripped(row: dict, matrix_title: str) -> bool:
    """FACT: slug thật của URL khác slug đúng và KHỚP TUYỆT ĐỐI với slug cũ (đ bị xóa) tính từ tiêu đề matrix."""
    slug = unquote(row["url"].rstrip("/").rsplit("/", 1)[-1])
    return is_d_stripped(matrix_title or row.get("title", ""), slug)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(D))
    args = ap.parse_args()
    d = Path(args.dir)
    inv = read_csv(d / "url-inventory.csv")
    for r in inv:
        for c in NEW_COLS:
            r.pop(c, None)
    fieldnames = [c for c in inv[0].keys() if c not in NEW_COLS]

    issues = read_csv(d / "technical-issues.csv")
    by_target: dict[str, list[str]] = collections.defaultdict(list)
    for i in issues:
        by_target[i["target"]].append(i["code"])
    cannib_roles: dict[str, set[str]] = collections.defaultdict(set)
    for c in read_csv(d / "cannibalization-risk.csv"):
        cannib_roles[c["url"]].add(c["role"])
    kmap = read_csv(d / "keyword-intent-map.csv")
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for k in kmap:
        groups[k["lead_url"]].append(f"{k['id']}:L")
        for s in [x.strip() for x in k["support_urls"].split("|") if x.strip()]:
            groups[s].append(f"{k['id']}:S")
    with (ROOT / "data" / "content-matrix.csv").open(encoding="utf-8", newline="") as fh:
        matrix_titles = {m["id"]: m["title"] for m in csv.DictReader(fh)}
    leads_yml = yaml.safe_load((ROOT / "_data" / "seo-leads.yml").read_text(encoding="utf-8")) or {}
    lead_urls = {x["u"] for lst in leads_yml.values() for x in lst}

    counters: dict[str, collections.Counter] = {k: collections.Counter() for k in
                                                ("seo_role", "fix_priority", "action_status", "staleness_risk", "needs_action")}
    for r in inv:
        typ, url = r["type"], r["url"]
        actions: list[str] = []
        # ---- vai trò
        if typ == "Home":
            role = "HOME"
        elif typ == "Pillar":
            role = "PILLAR"
        elif typ == "Hub":
            role = "HUB"
        elif typ == "Listing":
            role = "LISTING"
        elif typ == "Page":
            role = "PAGE"
        else:
            role = "LEAD_POST" if url in lead_urls else None
        roles = cannib_roles.get(url, set())
        near_pair = "CAP_GAN_TRUNG_INTENT" in roles
        crole = ("LEAD" if "URL_CHU_LUC_DE_XUAT" in roles else "SUPPORT" if "BAI_BO_TRO" in roles
                 else "NEAR_TITLE" if near_pair else "")
        if role is None:
            role = {"LEAD": "CANNIBALIZATION_LEAD", "SUPPORT": "SUPPORT_POST"}.get(crole, "TOPIC_POST")
        r["seo_role"] = role
        r["cannibalization_role"] = crole
        r["keyword_groups"] = "|".join(groups.get(url, []))

        # ---- từ khóa phụ (FACT: tags front matter)
        prim = nd(r.get("primary_keyword", ""))
        sec: list[str] = []
        for t in [x.strip() for x in r.get("tags_text", "").split("|") if x.strip()]:
            if nd(t) != prim and t not in sec:
                sec.append(t)
        r["secondary_keywords"] = " | ".join(sec[:3])

        # ---- hành động
        codes = by_target.get(r.get("source_file", ""), []) + by_target.get(url, [])
        if "H1_IN_BODY" in codes:
            actions.append("H1_IN_BODY")
        if "DESC_TOO_LONG" in codes:
            actions.append("DESC_TOO_LONG")
        if "NOINDEX" in codes:
            actions.append("NOINDEX_INTENTIONAL")
        if crole == "SUPPORT":
            actions.append("CANNIBALIZATION_SUPPORT")
        if near_pair:
            actions.append("NEAR_TITLE_PAIR")
        if typ == "Post":
            if r.get("canonical_ok") != "True" or r.get("html_h1_count") not in ("1", 1):
                actions.append("CANONICAL_OR_H1_BROKEN")
            if r.get("in_sitemap") != "True":
                actions.append("NOT_IN_SITEMAP")
            if r.get("orphan_risk") == "HIGH":
                actions.append("ORPHAN_NO_INBOUND")
            elif r.get("orphan_risk") == "LOW_INBOUND":
                actions.append("LOW_INBOUND")
            if r.get("matrix_status") == "PUBLISHED" and slug_d_stripped(r, matrix_titles.get(r.get("article_id", ""), "")):
                actions.append("SLUG_D_STRIPPED")
            # ---- lỗi thời (INFERRED)
            sig = stale_signals(post_body(r.get("source_file", "")))
            r["stale_signals"] = "|".join(sig)
            r["staleness_risk"] = stale_level(sig)
            if r["staleness_risk"] == "HIGH":
                actions.append("FRESHNESS_REVIEW")
        else:
            r["stale_signals"] = ""
            r["staleness_risk"] = ""
        actions = sorted(set(actions), key=lambda a: (ACTIONS[a][0], a))
        r["needs_action"] = "|".join(actions)
        if actions:
            prio, status = ACTIONS[actions[0]]
        else:
            prio, status = "P4", "NONE"
        r["fix_priority"], r["action_status"] = prio, status
        counters["seo_role"][role] += 1
        counters["fix_priority"][prio] += 1
        counters["action_status"][status] += 1
        if typ == "Post":
            counters["staleness_risk"][r["staleness_risk"]] += 1
        for a in actions:
            counters["needs_action"][a] += 1

    cols = fieldnames + NEW_COLS
    with (d / "url-inventory.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in inv:
            w.writerow({k: r.get(k, "") for k in cols})

    sp = d / "inventory-summary.json"
    summary = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    summary["enrichment"] = {k: dict(sorted(v.items())) for k, v in counters.items()}
    summary["enrichment"]["note"] = ("staleness_risk/stale_signals = INFERRED (regex trên nội dung bài); "
                                     "FRESHNESS_REVIEW chỉ là gợi ý rà soát theo nguồn chính thức, không phải kết luận sai/đúng")
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary["enrichment"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
