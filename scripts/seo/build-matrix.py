#!/usr/bin/env python3
"""SEO Master — sinh Keyword–Intent Map, ánh xạ 34 nhóm, rủi ro cannibalization, gợi ý liên kết nội bộ.

Đầu vào : reports/factory/seo-master/url-inventory.csv (từ build-inventory.py), scripts/seo/seo-matrix-config.yml,
          data/content-taxonomy.json; tùy chọn --graph đồ thị liên kết đã render.
Đầu ra  : reports/factory/seo-master/{keyword-intent-map,pillar-topic-mapping,cannibalization-risk,
          internal-link-recommendations}.csv
Read-only với repo ngoài thư mục đầu ra. Không gọi mạng. Mọi số liệu: FACT (đo từ tệp), INFERRED (regex/heuristic).
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


def nd(s: str) -> str:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def read_csv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(p: Path, cols: list[str], rows: list[dict]) -> None:
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def known_urls(inv: list[dict], tax: dict) -> set[str]:
    urls = {r["url"] for r in inv if r.get("url")}
    for f in ROOT.glob("*.md"):
        m = re.search(r"^permalink:\s*(\S+)", f.read_text(encoding="utf-8", errors="ignore"), re.M)
        if m:
            urls.add(m.group(1))
    for c in tax["children"]:
        urls.add(c["hub_url"])
    for p in tax["parents"]:
        urls.add(p["hub_url"])
    urls.add("/")
    return urls


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "reports" / "factory" / "seo-master"))
    ap.add_argument("--graph", help="JSON {url: [outlinks]} do build-inventory.py --graph-out sinh ra")
    args = ap.parse_args()
    d = Path(args.dir)
    inv = read_csv(d / "url-inventory.csv")
    cfg = yaml.safe_load((ROOT / "scripts" / "seo" / "seo-matrix-config.yml").read_text(encoding="utf-8"))
    tax = json.loads((ROOT / "data" / "content-taxonomy.json").read_text(encoding="utf-8"))
    children = {c["child_id"]: c for c in tax["children"]}
    parents = {p["parent_id"]: p for p in tax["parents"]}
    posts = [r for r in inv if r["type"] == "Post"]
    for r in posts:
        raw = f"{r['title']} {r.get('tags_text','')}".lower()
        r["_text"] = nd(raw)
        r["_dia"] = raw  # giữ dấu: phân biệt "chùa/chưa", "phở/phố", "sạc/sắc"

    def compile_rx(patterns):
        out = []
        for x in patterns:
            if x.startswith("dia:"):
                out.append((True, re.compile(x[4:])))
            else:
                out.append((False, re.compile(x)))
        return out

    def matches(r, rxs):
        return any(rx.search(r["_dia"] if dia else r["_text"]) for dia, rx in rxs)
    urls = known_urls(inv, tax)
    graph: dict[str, set[str]] = {}
    if args.graph:
        graph = {u: set(v) for u, v in json.loads(Path(args.graph).read_text(encoding="utf-8")).items()}

    def posts_linking_to(target: str, pool: list[dict]) -> int:
        if not graph:
            return -1
        return sum(1 for r in pool if target in graph.get(r["url"], ()))

    problems: list[str] = []

    # ------------------------------------------------------------------ Keyword–Intent Map (12 nhóm)
    kim_rows = []
    for g in cfg["commercial_groups"]:
        rx = compile_rx(g["regex"])
        hit = [r for r in posts if matches(r, rx)]
        lead = g["lead_url"]
        if lead not in urls:
            problems.append(f"{g['id']}: lead_url không tồn tại: {lead}")
        for u in g["support_urls"]:
            if u not in urls:
                problems.append(f"{g['id']}: support_url không tồn tại: {u}")
        lead_child = next((c for c in children.values() if c["hub_url"] == lead), None)
        child_posts = [r for r in posts if lead_child and r["child_id"] == lead_child["child_id"]]
        top_support = sorted(hit, key=lambda r: -int(r["words"] or 0))[:3]
        link_to_lead = posts_linking_to(lead, hit) if hit else 0
        kim_rows.append({
            "id": g["id"], "keyword": g["keyword"], "intent": g["intent"],
            "homepage_role": g.get("role_home", "không nhắm từ trang chủ"),
            "lead_url": lead, "lead_url_exists": lead in urls, "lead_why": g["lead_why"],
            "support_urls": " | ".join(g["support_urls"]),
            "posts_matching_keyword_title_tags": len(hit),
            "posts_in_lead_child_hub": len(child_posts) if lead_child else "n/a",
            "matching_posts_linking_to_lead_in_html": "UNKNOWN(no graph)" if link_to_lead < 0 else link_to_lead,
            "sample_support_posts": " | ".join(r["url"] for r in top_support),
            "main_site_conflict": g["main_site_conflict"], "mitigation": g["mitigation"],
            "priority": g["priority"], "evidence_type": "FACT(count) + INFERRED(intent/conflict)",
        })
    write_csv(d / "keyword-intent-map.csv", list(kim_rows[0].keys()), kim_rows)

    # ------------------------------------------------------------------ ánh xạ 34 nhóm
    tg_rows = []
    for g in cfg["topic_groups"]:
        child_ids = g.get("children", [])
        struct = [r for r in posts if r["child_id"] in child_ids]
        rx = compile_rx(g.get("regex", []))
        kw = [r for r in posts if rx and matches(r, rx)]
        union = {r["url"] for r in struct} | {r["url"] for r in kw}
        lead = g["lead_url"]
        if lead not in urls:
            problems.append(f"nhóm {g['n']}: lead_url không tồn tại: {lead}")
        total = len(union)
        if total >= 20:
            verdict = "MAPPED_STRONG"
            action = "Giữ hub hiện có; không tạo URL mới."
        elif total >= 3:
            verdict = "MAPPED_THIN"
            action = "Ánh xạ vào hub gần nhất; KHÔNG tạo hub (chưa đủ nội dung thật)."
        else:
            verdict = "NO_REAL_CONTENT"
            action = "Ghi nhận khoảng trống. KHÔNG tạo hub/trang rỗng; chỉ viết khi có nguồn xác minh và nhu cầu."
        tg_rows.append({
            "group_no": g["n"], "group_name": g["name"], "pillar_id": g["pillar"],
            "pillar_url": parents[g["pillar"]]["hub_url"],
            "child_hubs": " | ".join(children[c]["hub_url"] for c in child_ids if c in children),
            "posts_by_child_structure": len(struct), "posts_by_keyword_match_upper_bound": len(kw),
            "posts_union": total, "lead_url": lead, "lead_url_exists": lead in urls,
            "commercial_page": g.get("commercial_page", ""), "verdict": verdict, "action": action,
            "note": g.get("note", ""), "evidence_type": "FACT(count) + INFERRED(regex)",
        })
    write_csv(d / "pillar-topic-mapping.csv", list(tg_rows[0].keys()), tg_rows)

    # ------------------------------------------------------------------ cannibalization
    by_key = collections.defaultdict(list)
    for r in posts:
        if r.get("cannibalization_key"):
            by_key[r["cannibalization_key"]].append(r)
    can_rows = []
    for key, rs in sorted(by_key.items()):
        if len(rs) < 2:
            continue
        rs = sorted(rs, key=lambda r: (-int(r["words"] or 0), r["date"]))
        lead = rs[0]
        same_child = len({r["child_id"] for r in rs}) == 1
        for r in rs:
            can_rows.append({
                "cannibalization_key": key, "group_size": len(rs), "same_child": same_child,
                "url": r["url"], "article_id": r["article_id"], "child_id": r["child_id"],
                "title": r["title"], "words": r["words"],
                "role": "URL_CHU_LUC_DE_XUAT" if r is lead else "BAI_BO_TRO",
                "proposed_action": "Giữ URL; thêm liên kết ngữ cảnh hai chiều; phân biệt intent trong lần bảo trì nhỏ có QA" if r is not lead else "Giữ làm URL chủ lực của intent",
                "risk": "CAO" if same_child else "TRUNG BÌNH",
                "evidence_type": "FACT(trùng khóa matrix) + INFERRED(intent)",
            })

    # near-duplicate title trong cùng child (Jaccard token >= 0.7) — INFERRED
    stop = set("va la cua cho khi o tai co can khong nhu the nao bang xe may ha noi thue cac mot nhung de den tu trong voi".split())

    def toks(t: str) -> frozenset[str]:
        return frozenset(w for w in re.findall(r"[a-z0-9]+", nd(t)) if w not in stop and len(w) > 1)

    by_child = collections.defaultdict(list)
    for r in posts:
        by_child[r["child_id"]].append((r, toks(r["title"])))
    near = 0
    seen_pairs = {tuple(sorted((x["url"] for x in rs))) for rs in by_key.values() if len(rs) > 1}
    for cid, lst in by_child.items():
        for i in range(len(lst)):
            ri, ti = lst[i]
            if len(ti) < 4:
                continue
            for j in range(i + 1, len(lst)):
                rj, tj = lst[j]
                if len(tj) < 4:
                    continue
                inter = len(ti & tj)
                if not inter:
                    continue
                score = inter / len(ti | tj)
                if score >= 0.7 and tuple(sorted((ri["url"], rj["url"]))) not in seen_pairs:
                    near += 1
                    can_rows.append({
                        "cannibalization_key": f"NEAR_TITLE:{cid}", "group_size": 2, "same_child": True,
                        "url": ri["url"], "article_id": ri["article_id"], "child_id": cid, "title": ri["title"],
                        "words": ri["words"], "role": "CAP_GAN_TRUNG_INTENT",
                        "proposed_action": f"So khớp với {rj['url']} (Jaccard={score:.2f}); điều tra intent trước khi hành động",
                        "risk": "TRUNG BÌNH", "evidence_type": "INFERRED(heuristic tiêu đề)",
                    })
    ccols = ["cannibalization_key", "group_size", "same_child", "url", "article_id", "child_id", "title", "words",
             "role", "proposed_action", "risk", "evidence_type"]
    write_csv(d / "cannibalization-risk.csv", ccols, can_rows)

    # ------------------------------------------------------------------ internal link recommendations
    rec_rows = []
    for g in cfg["commercial_groups"]:
        rx = compile_rx(g["regex"])
        hit = [r for r in posts if matches(r, rx)]
        for target in [g["lead_url"]]:
            if not graph:
                continue
            missing = [r for r in hit if target not in graph.get(r["url"], ())]
            rec_rows.append({
                "group": g["id"], "keyword": g["keyword"], "target_lead_url": target,
                "matching_posts": len(hit), "already_link_to_lead": len(hit) - len(missing),
                "missing_link_to_lead": len(missing),
                "recommendation": ("Thêm liên kết ngữ cảnh tự nhiên có chọn lọc (không chèn hàng loạt cùng một anchor); "
                                   "ưu tiên sửa ở include dùng chung (breadcrumb/related/footer) trước khi sửa từng bài"),
                "evidence_type": "FACT(đồ thị HTML render)",
            })
    if rec_rows:
        write_csv(d / "internal-link-recommendations.csv", list(rec_rows[0].keys()), rec_rows)

    summary = {
        "keyword_groups": len(kim_rows), "topic_groups": len(tg_rows),
        "topic_verdicts": dict(collections.Counter(r["verdict"] for r in tg_rows)),
        "cannibalization_key_groups": len({r["cannibalization_key"] for r in can_rows if not r["cannibalization_key"].startswith("NEAR_")}),
        "near_title_pairs": near, "config_problems": problems,
    }
    (d / "matrix-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
