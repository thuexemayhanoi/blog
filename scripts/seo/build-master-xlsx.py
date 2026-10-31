#!/usr/bin/env python3
"""SEO Master — sinh workbook Excel "Master SEO Matrix" (23 sheet) từ dữ liệu SEO Master đã có trong repo.

Đọc-only với dữ liệu nguồn; chỉ ghi một tệp .xlsx. Không gọi mạng.

Đầu vào (mặc định thư mục reports/factory/seo-master/):
  url-inventory.csv, keyword-intent-map.csv, pillar-topic-mapping.csv, cannibalization-classification.csv,
  internal-link-candidates.csv, internal-link-recommendations.csv, technical-issues.csv, fix-log.csv,
  checkpoint.json, keyword-serp-*.json (nghiên cứu từ khóa + SERP có ngày), wave*-audit-findings.json (kết quả audit
  có kiểm chứng), wave*-changes.json (nhật ký thay đổi của đợt), image-inventory.csv, structured-data-summary.json,
  performance-lab.json (tùy chọn — thiếu thì sheet ghi N/A kèm lý do)
  data/content-matrix.csv, data/qa/<ID>.json, data/content-taxonomy.json, _data/business.yml, data/business-facts.json

Nguyên tắc: không bịa số. Ô thiếu dữ liệu ghi "N/A" kèm nguồn còn thiếu (ví dụ chưa kết nối Search Console của blog).
Dashboard dùng công thức (COUNTIF/COUNTIFS/SUM) tham chiếu các sheet dữ liệu để tự tính lại khi dữ liệu đổi.

Dùng:
  python3 scripts/seo/build-master-xlsx.py --out reports/factory/seo-master/Master-SEO-Matrix.xlsx
Sau đó tính lại công thức và kiểm lỗi bằng LibreOffice (recalc) trước khi giao.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://blog.thuexemaynguyentu.com"
NA_GSC = "N/A — Search Console của blog chưa kết nối (OpenRush/OpenSEO: không có property)"
NA_VOL = "N/A — chưa có dữ liệu volume cho từ khóa này"

FONT = "Arial"
F_BASE = Font(name=FONT, size=10)
F_HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_TITLE = Font(name=FONT, size=14, bold=True, color="1F3864")
F_BOLD = Font(name=FONT, size=10, bold=True)
F_NOTE = Font(name=FONT, size=9, italic=True, color="595959")
FILL_HEAD = PatternFill("solid", fgColor="1F3864")
FILL_KPI = PatternFill("solid", fgColor="DEEAF6")
FILL_P0 = PatternFill("solid", fgColor="F4B6B6")
FILL_P1 = PatternFill("solid", fgColor="F8CBAD")
FILL_P2 = PatternFill("solid", fgColor="FFE699")
FILL_OK = PatternFill("solid", fgColor="C6EFCE")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")


def read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(p: Path, default=None):
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def latest(d: Path, pattern: str) -> Path | None:
    files = sorted(d.glob(pattern))
    return files[-1] if files else None


def norm_kw(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class Book:
    def __init__(self) -> None:
        self.wb = Workbook()
        self.wb.remove(self.wb.active)

    def sheet(self, name: str, headers: list[str], rows: list[list], widths: dict[int, int] | None = None,
              note: str | None = None, freeze: str = "B2") -> "Worksheet":  # noqa: F821
        ws = self.wb.create_sheet(name)
        start = 1
        if note:
            ws.cell(row=1, column=1, value=note).font = F_NOTE
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(4, min(len(headers), 10)))
            start = 2
        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=start, column=c, value=h)
            cell.font, cell.fill, cell.border = F_HEAD, FILL_HEAD, BORDER
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        for r, row in enumerate(rows, start + 1):
            for c, v in enumerate(row, 1):
                cell = ws.cell(row=r, column=c, value=v)
                cell.font = F_BASE
        last_row = start + max(len(rows), 1)
        ws.auto_filter.ref = f"A{start}:{get_column_letter(len(headers))}{last_row}"
        ws.freeze_panes = ws[f"{freeze[0]}{start + 1}"] if freeze else None
        for c in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(c)].width = (widths or {}).get(c, 16)
        ws.row_dimensions[start].height = 32
        return ws

    def save(self, out: Path) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        self.wb.save(out)


def priority_fill(ws, col_letter: str, first: int, last: int) -> None:
    rng = f"{col_letter}{first}:{col_letter}{last}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"P0"'], fill=FILL_P0))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"P1"'], fill=FILL_P1))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"P2"'], fill=FILL_P2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "reports" / "factory" / "seo-master"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "factory" / "seo-master" / "Master-SEO-Matrix.xlsx"))
    ap.add_argument("--as-of", default="", help="ngày dữ liệu (YYYY-MM-DD), in ở dashboard")
    a = ap.parse_args()
    d = Path(a.dir)

    inv = read_csv(d / "url-inventory.csv")
    if not inv:
        raise SystemExit(f"thiếu {d / 'url-inventory.csv'}")
    kim = read_csv(d / "keyword-intent-map.csv")
    ptm = read_csv(d / "pillar-topic-mapping.csv")
    ccl = read_csv(d / "cannibalization-classification.csv")
    ilc = read_csv(d / "internal-link-candidates.csv")
    ilr = read_csv(d / "internal-link-recommendations.csv")
    tech = read_csv(d / "technical-issues.csv")
    fixlog = read_csv(d / "fix-log.csv")
    ckpt = read_json(d / "checkpoint.json", {}) or {}
    kw_path = latest(d, "keyword-serp-*.json")
    kw = read_json(kw_path, {}) if kw_path else {}
    aud_path = latest(d, "wave*-audit-findings.json")
    audit = read_json(aud_path, {}) if aud_path else {}
    chg_path = latest(d, "wave*-changes.json")
    changes = read_json(chg_path, {}) if chg_path else {}
    img_rows = read_csv(d / "image-inventory.csv")
    sd_sum = read_json(d / "structured-data-summary.json", {}) or {}
    perf = read_json(d / "performance-lab.json", {}) or {}
    matrix = {r["id"]: r for r in read_csv(ROOT / "data" / "content-matrix.csv")}
    tax = read_json(ROOT / "data" / "content-taxonomy.json", {}) or {}
    business = yaml.safe_load((ROOT / "_data" / "business.yml").read_text(encoding="utf-8"))
    facts = read_json(ROOT / "data" / "business-facts.json", {}) or {}

    qa: dict[str, dict] = {}
    for p in glob.glob(str(ROOT / "data" / "qa" / "*.json")):
        try:
            j = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        aid = j.get("article_id") or Path(p).stem
        qa[aid] = j

    research = {norm_kw(k["kw"]): k for k in kw.get("keywords", [])}
    parents = {p["parent_id"]: p for p in tax.get("parents", [])}
    children = {c["child_id"]: c for c in tax.get("children", [])}

    b = Book()
    as_of = a.as_of or (kw.get("collected_at") or "")

    # ---------------- 2. URL INVENTORY ----------------
    inv_headers = [
        "URL", "Page ID (article_id)", "Loại nội dung", "Ngôn ngữ", "Trạng thái xuất bản", "Indexability",
        "Hub (parent)", "Silo (child)", "Cluster key", "Từ khóa chính", "Từ khóa phụ", "Search intent",
        "Search volume", "Keyword difficulty", "Impressions", "Clicks", "CTR", "Avg position",
        "SEO Title (HTML)", "Độ dài title", "Meta description", "Độ dài meta", "H1", "Canonical", "Trong sitemap",
        "Liên kết vào (HTML)", "Vai trò SEO", "Hành động SEO", "Priority", "Trạng thái hành động", "Rủi ro lỗi thời",
        "QA quality", "QA seo", "QA business_fact", "QA legal", "Ngày (front matter)", "Bằng chứng",
    ]
    inv_rows = []
    for r in inv:
        aid = r.get("article_id", "")
        m = matrix.get(aid, {})
        q = qa.get(aid, {})
        robots = r.get("html_robots", "")
        if r["type"] == "RedirectStub":
            idx = "REDIRECT_STUB (meta refresh 0s + canonical mới, không trong sitemap)"
        elif "noindex" in robots:
            idx = "NOINDEX (chủ đích)"
        elif r.get("in_sitemap") == "True":
            idx = "INDEXABLE (200 local, self-canonical, trong sitemap)"
        else:
            idx = "INDEXABLE_NOT_IN_SITEMAP"
        pk = r.get("primary_keyword") or m.get("primary_keyword", "")
        res = research.get(norm_kw(pk))
        vol = res["volume"] if res and res.get("volume") is not None else NA_VOL if pk else "N/A"
        kd = res.get("seo_difficulty") if res and res.get("seo_difficulty") is not None else "N/A"
        status = r.get("matrix_status") or ("LIVE (trang tĩnh/hub/danh sách)" if r["type"] != "Post" else "LIVE")
        title = r.get("html_title", "")
        meta = r.get("html_meta_description", "")
        parent = parents.get(r.get("parent_id", ""), {}).get("title", r.get("parent_id", ""))
        child = r.get("child_title") or children.get(r.get("child_id", ""), {}).get("title", r.get("child_id", ""))
        action = r.get("needs_action", "") or "KEEP"
        inv_rows.append([
            SITE + r["url"], aid or "N/A (không phải bài factory)", r["type"], "vi", status, idx,
            parent, child, r.get("cannibalization_key", ""), pk, r.get("secondary_keywords", ""),
            r.get("search_intent") or m.get("search_intent", ""), vol, kd, "N/A", "N/A", "N/A", "N/A",
            title, len(title), meta, len(meta), r.get("html_h1", ""), r.get("html_canonical", ""),
            "YES" if r.get("in_sitemap") == "True" else "NO",
            int(r["inbound_links_html"]) if (r.get("inbound_links_html") or "").isdigit() else None,
            r.get("seo_role", ""), action, r.get("fix_priority", ""), r.get("action_status", ""),
            r.get("staleness_risk", ""),
            q.get("quality", "N/A"), q.get("seo", "N/A"), q.get("business_fact", "N/A"), q.get("legal", "N/A"),
            r.get("date", ""),
            "FACT: build cục bộ + url-inventory.csv; volume/GSC: " + ("Ubersuggest " + as_of if res else "N/A"),
        ])
    ws_inv = b.sheet("URL INVENTORY", inv_headers, inv_rows,
                     widths={1: 60, 3: 11, 5: 14, 6: 22, 7: 18, 8: 20, 10: 28, 19: 50, 21: 50, 23: 40, 24: 40, 28: 22},
                     note=f"Nguồn: build Jekyll cục bộ của HEAD + reports/factory/seo-master/url-inventory.csv; QA từ data/qa/<ID>.json. "
                          f"Impressions/Clicks/CTR/Position: {NA_GSC}.")
    inv_last = 2 + len(inv_rows)
    priority_fill(ws_inv, "AC", 3, inv_last)
    ws_inv.cell(row=2, column=13).comment = Comment("Chỉ có volume cho các từ khóa đã tra (Ubersuggest, Việt Nam, " + as_of + "). Không ước đoán.", "SEO")

    # ---------------- 3. KEYWORD MASTER ----------------
    km_rows = []
    for k in kw.get("keywords", []):
        km_rows.append([k["kw"], "research", k.get("volume") if k.get("volume") is not None else "N/A",
                        k.get("seo_difficulty", "N/A") if k.get("seo_difficulty") is not None else "N/A",
                        k.get("cpc_usd", "N/A") if k.get("cpc_usd") is not None else "N/A",
                        k.get("intent", "N/A"), k.get("note", ""), kw.get("sources", {}).get("volume", "")])
    for r in kim:
        km_rows.append([r["keyword"], f"commercial group {r['id']}", research.get(norm_kw(r["keyword"]), {}).get("volume", "N/A") or "N/A",
                        "N/A", "N/A", r.get("intent", ""), f"lead: {r.get('lead_url','')} | xung đột site chính: {r.get('main_site_conflict','')}",
                        "scripts/seo/seo-matrix-config.yml"])
    # từ khóa chính của bài factory (dedupe), để lọc/tra cứu
    pk_counter = Counter(norm_kw(m.get("primary_keyword", "")) for m in matrix.values() if m.get("primary_keyword"))
    for k, n in sorted(pk_counter.items(), key=lambda x: (-x[1], x[0])):
        km_rows.append([k, "matrix primary_keyword", research.get(k, {}).get("volume", NA_VOL) if research.get(k) else NA_VOL,
                        "N/A", "N/A", "", f"{n} hàng matrix dùng từ khóa này", "data/content-matrix.csv"])
    ws_km = b.sheet("KEYWORD MASTER", ["Từ khóa", "Nguồn/nhóm", "Volume (VN/tháng)", "SEO difficulty", "CPC (USD)", "Intent", "Ghi chú", "Nguồn dữ liệu"],
                    km_rows, widths={1: 48, 2: 24, 7: 70, 8: 40},
                    note="Volume chỉ có cho từ khóa đã tra thật (Ubersuggest free 3 báo cáo/ngày). Phân nhóm head/primary/long-tail theo cột Nguồn/nhóm; giá trị N/A = chưa có dữ liệu, không ước đoán.")

    # ---------------- 4. KEYWORD GAP ----------------
    gap_rows = []
    for g in audit.get("keyword_gaps", []):
        gap_rows.append([g.get("intent", ""), g.get("example_queries", ""), g.get("serp_evidence", ""), g.get("blog_coverage", ""),
                         g.get("decision", ""), g.get("priority", ""), g.get("note", "")])
    if not gap_rows:
        gap_rows.append(["N/A", "", "", "", "Chưa có kết quả audit keyword gap", "", ""])
    b.sheet("KEYWORD GAP", ["Intent / chủ đề", "Truy vấn mẫu", "Bằng chứng SERP", "Blog đã có?", "Quyết định", "Priority", "Ghi chú"],
            gap_rows, widths={1: 40, 2: 40, 3: 50, 4: 40, 5: 40, 7: 50})

    # ---------------- 5. COMPETITOR SERP ----------------
    serp_rows = []
    for q, v in (kw.get("serp_top10") or {}).items():
        for i, o in enumerate(v.get("organic", []), 1):
            serp_rows.append([q, "organic", i, o, ", ".join(v.get("features", [])), "YES" if v.get("blog_present") else "NO",
                              v.get("blog_organic_rank", "N/A") if v.get("blog_present") else "N/A"])
        for i, o in enumerate(v.get("local_pack", []), 1):
            serp_rows.append([q, "local_pack", i, o, ", ".join(v.get("features", [])), "", ""])
    b.sheet("COMPETITOR SERP", ["Truy vấn", "Loại kết quả", "Vị trí trong nhóm", "Kết quả (domain/tiêu đề)", "SERP features", "Blog có mặt top 10?", "Vị trí organic của blog"],
            serp_rows, widths={1: 32, 4: 70, 5: 30},
            note=f"SERP Google Việt Nam, tiếng Việt, desktop, top 10 — {kw.get('sources', {}).get('serp', '')}; thu thập {as_of}. Một lần chụp, không phải thứ hạng cố định.")

    # ---------------- 6. URL–KEYWORD MAPPING ----------------
    map_rows = []
    for r in inv:
        if r["type"] != "Post":
            continue
        map_rows.append([SITE + r["url"], r.get("article_id", ""), r.get("primary_keyword", ""), r.get("search_intent", ""),
                         r.get("cannibalization_key", ""), r.get("keyword_groups", ""), r.get("cannibalization_role", ""),
                         r.get("child_title", "")])
    for r in kim:
        map_rows.append([SITE + r["lead_url"] if r.get("lead_url", "").startswith("/") else r.get("lead_url", ""), "LEAD " + r["id"], r["keyword"],
                         r.get("intent", ""), "", r["id"], "LEAD (URL chủ lực nhóm thương mại)", ""])
    b.sheet("URL–KEYWORD MAPPING", ["URL", "ID", "Từ khóa chính", "Intent", "Cluster key", "Nhóm thương mại", "Vai trò cannibalization", "Silo"],
            map_rows, widths={1: 60, 3: 40, 4: 22, 5: 34, 7: 26, 8: 26})

    # ---------------- 7. CANNIBALIZATION ----------------
    can_rows = [[r["no"], r["cannibalization_key"], int(r["group_size"] or 0), r["classification"], r["suggested_lead_id"],
                 SITE + r["suggested_lead_url"], r["lead_basis"], r["member_ids"], r["max_body_similarity_6gram"], r["action_now"], r["action_later"]]
                for r in ccl]
    for g in audit.get("new_cannibalization", []):
        can_rows.append([g.get("no", "NEW"), g.get("key", ""), g.get("size", ""), g.get("classification", ""), g.get("lead_id", ""),
                         g.get("lead_url", ""), g.get("basis", ""), g.get("members", ""), "", g.get("action_now", ""), g.get("action_later", "")])
    b.sheet("CANNIBALIZATION", ["#", "Cluster key", "Số bài", "Phân loại", "Lead ID", "Lead URL", "Cơ sở chọn lead", "Thành viên", "Độ giống thân bài (6-gram)", "Đã làm", "Để sau"],
            can_rows, widths={2: 34, 4: 22, 6: 50, 7: 50, 8: 40, 10: 40, 11: 40},
            note="Phân biệt trùng intent gây hại (SAME_INTENT_MONITOR) với góc khác nhau (DISTINCT_ANGLE_KEEP). Không gộp/xóa/redirect khi chưa có dữ liệu Search Console + chủ duyệt.")

    # helper: rows by role
    def rows_role(types: set[str]) -> list[dict]:
        return [r for r in inv if r["type"] in types]

    # ---------------- 8. HOMEPAGE & PILLAR ----------------
    hp_rows = []
    for r in rows_role({"Home", "Pillar"}):
        hp_rows.append([SITE + r["url"], r["type"], r.get("html_title", ""), len(r.get("html_title", "")), r.get("html_meta_description", ""),
                        len(r.get("html_meta_description", "")), r.get("html_h1", ""), r.get("words", ""), r.get("inbound_links_html", ""),
                        r.get("outbound_internal_main", ""), r.get("jsonld_types", ""),
                        "Đóng băng (chủ duyệt 4f61156e)" if r["type"] == "Home" else "Pillar — cập nhật theo audit wave4"])
    b.sheet("HOMEPAGE & PILLAR", ["URL", "Loại", "Title", "Độ dài title", "Meta description", "Độ dài meta", "H1", "Số từ", "Liên kết vào", "Liên kết ra", "Schema", "Ghi chú"],
            hp_rows, widths={1: 45, 3: 50, 5: 60, 7: 35, 11: 40, 12: 40})

    # ---------------- 9. SEO HUB MATRIX ----------------
    posts_by_child = Counter(r.get("child_id", "") for r in inv if r["type"] == "Post")
    hub_child = {}
    for c in tax.get("children", []):
        hub_child[c.get("hub_url", "")] = c
    hub_rows = []
    for r in rows_role({"Hub"}):
        c = hub_child.get(r["url"], {})
        cid = c.get("child_id", "")
        hub_rows.append([SITE + r["url"], cid, parents.get(c.get("parent_id", ""), {}).get("title", ""), r.get("html_title", ""),
                         len(r.get("html_title", "")), r.get("html_meta_description", ""), len(r.get("html_meta_description", "")),
                         r.get("html_h1", ""), int(r.get("words") or 0), posts_by_child.get(cid, 0),
                         int(r.get("inbound_links_html") or 0), int(r.get("outbound_internal_main") or 0), r.get("jsonld_types", "")])
    ws_hub = b.sheet("SEO HUB MATRIX", ["Hub URL", "Child ID", "Pillar", "Title", "Độ dài title", "Meta description", "Độ dài meta", "H1",
                                        "Số từ (trang)", "Số bài thuộc hub", "Liên kết vào", "Liên kết ra", "Schema"],
                     hub_rows, widths={1: 48, 3: 22, 4: 50, 6: 60, 8: 30, 13: 40})
    n = len(hub_rows) + 1
    ws_hub.cell(row=n + 2, column=1, value="Tổng bài thuộc hub").font = F_BOLD
    ws_hub.cell(row=n + 2, column=10, value=f"=SUM(J2:J{n})").font = F_BOLD
    ws_hub.cell(row=n + 3, column=1, value="Hub có meta < 120 ký tự").font = F_BOLD
    ws_hub.cell(row=n + 3, column=7, value=f'=COUNTIF(G2:G{n},"<120")').font = F_BOLD

    # ---------------- 10. SILO & CATEGORY MATRIX ----------------
    silo_rows = []
    for c in tax.get("children", []):
        p = parents.get(c.get("parent_id", ""), {})
        silo_rows.append([p.get("title", ""), p.get("hub_url", ""), c.get("child_id", ""), c.get("title", ""), c.get("hub_url", ""),
                          posts_by_child.get(c.get("child_id", ""), 0), c.get("description", "")])
    ws_silo = b.sheet("SILO & CATEGORY MATRIX", ["Pillar", "Pillar URL", "Child ID", "Silo", "Silo URL", "Số bài", "Mô tả"],
                      silo_rows, widths={1: 24, 2: 20, 4: 30, 5: 40, 7: 70})
    n = len(silo_rows) + 1
    ws_silo.cell(row=n + 2, column=5, value="Tổng").font = F_BOLD
    ws_silo.cell(row=n + 2, column=6, value=f"=SUM(F2:F{n})").font = F_BOLD

    # ---------------- 11. CONTENT CLUSTERS ----------------
    b.sheet("CONTENT CLUSTERS", ["#", "Nhóm chủ đề", "Pillar", "Pillar URL", "Hub con", "Bài theo cấu trúc", "Bài khớp từ khóa (cận trên)", "Bài (hợp)",
                                 "Lead URL", "Đánh giá", "Hành động", "Bằng chứng"],
            [[r["group_no"], r["group_name"], r["pillar_id"], r["pillar_url"], r["child_hubs"], int(r["posts_by_child_structure"] or 0),
              int(r["posts_by_keyword_match_upper_bound"] or 0), int(r["posts_union"] or 0), r["lead_url"], r["verdict"], r["action"], r["evidence_type"]]
             for r in ptm], widths={2: 30, 5: 60, 9: 30, 11: 50})

    # ---------------- 12. PAGE & POST OPTIMIZATION ----------------
    opt_rows = []
    for r in inv:
        if r.get("needs_action"):
            opt_rows.append([SITE + r["url"], r.get("article_id", ""), r["type"], r.get("needs_action", ""), r.get("fix_priority", ""),
                             r.get("action_status", ""), r.get("stale_signals", ""), r.get("cannibalization_role", "")])
    for f in audit.get("page_actions", []):
        opt_rows.append([f.get("url", ""), "", f.get("type", ""), f.get("action", ""), f.get("priority", ""), f.get("status", ""), f.get("note", ""), ""])
    ws_opt = b.sheet("PAGE & POST OPTIMIZATION", ["URL", "ID", "Loại", "Hành động cần làm", "Priority", "Trạng thái", "Tín hiệu", "Vai trò cannibalization"],
                     opt_rows, widths={1: 60, 4: 40, 6: 26, 7: 40},
                     note="FRESHNESS_REVIEW = gợi ý rà soát (INFERRED, regex số tiền/pháp lý), không phải kết luận sai. Sửa bài PUBLISHED chỉ qua revise-published.py có chủ duyệt.")
    priority_fill(ws_opt, "E", 3, 2 + len(opt_rows))

    # ---------------- 13. TECHNICAL SEO AUDIT ----------------
    tech_rows = []
    for dim in audit.get("dimensions", []):
        for f in dim.get("findings", []):
            tech_rows.append([f.get("id", ""), dim.get("dimension", ""), f.get("title", ""), f.get("severity", ""), f.get("evidence_type", ""),
                              f.get("affected_count", ""), f.get("evidence", ""), f.get("root_cause", ""), f.get("proposed_fix", ""),
                              f.get("fix_class", ""), f.get("verdict", ""), f.get("status", "OPEN"), "; ".join(f.get("guidance_refs", []) or [])])
    for t in tech:
        tech_rows.append([t["code"], "wave1-inventory", t["code"], t["priority"], "FACT", 1, t["evidence"], t["cause"], t["proposed_fix"], "", "", t["status"], ""])
    ws_tech = b.sheet("TECHNICAL SEO AUDIT", ["ID", "Nhóm", "Vấn đề", "Priority", "Bằng chứng (loại)", "Số URL", "Bằng chứng", "Nguyên nhân",
                                             "Đề xuất sửa", "Loại sửa", "Kiểm chứng phản biện", "Trạng thái", "Căn cứ"],
                      tech_rows, widths={2: 18, 3: 50, 7: 60, 8: 40, 9: 60, 11: 30, 13: 50})
    priority_fill(ws_tech, "D", 2, 1 + len(tech_rows))

    # ---------------- 14. INDEX & SITEMAP ----------------
    idx_counter = Counter((r["type"], "sitemap" if r.get("in_sitemap") == "True" else "không sitemap",
                           "noindex" if "noindex" in (r.get("html_robots") or "") else "index") for r in inv)
    idx_rows = [[t, s, i, n_] for (t, s, i), n_ in sorted(idx_counter.items())]
    ws_idx = b.sheet("INDEX & SITEMAP", ["Loại trang", "Sitemap", "Robots", "Số URL"], idx_rows, widths={1: 18, 2: 16, 3: 12},
                     note="FACT từ build cục bộ. Trạng thái lập chỉ mục thật trên Google: UNKNOWN (" + NA_GSC + ").")
    n = len(idx_rows) + 2
    ws_idx.cell(row=n + 2, column=1, value="Tổng URL kiểm kê").font = F_BOLD
    ws_idx.cell(row=n + 2, column=4, value=f"=SUM(D3:D{n})").font = F_BOLD
    ws_idx.cell(row=n + 3, column=1, value="URL trong sitemap").font = F_BOLD
    ws_idx.cell(row=n + 3, column=4, value=f'=SUMIF(B3:B{n},"sitemap",D3:D{n})').font = F_BOLD

    # ---------------- 15. HREFLANG MATRIX ----------------
    href = audit.get("hreflang", {})
    b.sheet("HREFLANG MATRIX", ["Phạm vi", "Ngôn ngữ", "Trạng thái", "Quyết định", "Bằng chứng"],
            [["Toàn site", "vi (đơn ngữ)", href.get("state", "Site chỉ có tiếng Việt; thư mục en/ bị exclude khỏi build (_config.yml)"),
              href.get("decision", "Không ghép cặp ngôn ngữ (không có trang tương đương). Không tạo hreflang giả."), href.get("evidence", "FACT: _config.yml exclude en/")]],
            widths={1: 14, 2: 14, 3: 60, 4: 60, 5: 50})

    # ---------------- 16. IMAGE SEO ----------------
    if img_rows:
        hdr = list(img_rows[0].keys())
        b.sheet("IMAGE SEO", hdr, [[r[h] for h in hdr] for r in img_rows], widths={1: 50})
    else:
        b.sheet("IMAGE SEO", ["Phạm vi", "Trạng thái"], [["Ảnh đại diện bài viết", "IMAGE PENDING — bài không có ảnh riêng; không có công cụ tạo ảnh/ảnh thật được xác minh"]],
                widths={1: 30, 2: 90})

    # ---------------- 17. INTERNAL LINK MATRIX ----------------
    il_rows = []
    for r in rows_role({"Home", "Pillar", "Hub", "Page"}):
        il_rows.append([SITE + r["url"], r["type"], int(r.get("inbound_links_html") or 0), int(r.get("outbound_internal_main") or 0), "", "", ""])
    for r in ilr:
        il_rows.append([SITE + r["target_lead_url"], "LEAD " + r["group"], int(r.get("already_link_to_lead") or 0), "", int(r.get("matching_posts") or 0),
                        int(r.get("missing_link_to_lead") or 0), r.get("recommendation", "")])
    ws_il = b.sheet("INTERNAL LINK MATRIX", ["URL đích", "Loại/nhóm", "Liên kết vào (HTML)", "Liên kết ra", "Bài khớp nhóm", "Bài chưa liên kết về lead", "Khuyến nghị"],
                    il_rows, widths={1: 55, 2: 16, 7: 70},
                    note=f"Đồ thị liên kết từ HTML đã render. Ứng viên liên kết ngữ cảnh chi tiết: internal-link-candidates.csv ({len(ilc)} hàng). Không chèn liên kết hàng loạt cùng anchor.")

    # ---------------- 18. STRUCTURED DATA ----------------
    sd_rows = []
    for t, v in (sd_sum.get("by_template") or {}).items():
        sd_rows.append([t, v.get("pages", ""), v.get("types", ""), v.get("issues", ""), v.get("status", "")])
    if not sd_rows:
        types = Counter()
        for r in inv:
            types[(r["type"], r.get("jsonld_types", ""))] += 1
        sd_rows = [[t, n_, j, "", "FACT (build cục bộ)"] for (t, j), n_ in sorted(types.items())]
    b.sheet("STRUCTURED DATA", ["Template", "Số trang", "Schema types", "Vấn đề", "Trạng thái"], sd_rows, widths={1: 18, 3: 60, 4: 60, 5: 30},
            note="JSON-LD phản ánh nội dung hiển thị; không review/rating/geo bịa. FAQPage chỉ qua _includes/faq.html (CI kiểm parity).")

    # ---------------- 19. LOCAL SEO & CONVERSION ----------------
    vf = facts.get("verified_facts", {})
    loc_rows = [
        ["Tên", vf.get("display_name", ""), business.get("display_name", ""), "Khớp" if vf.get("display_name") == business.get("display_name") else "LỆCH"],
        ["Địa chỉ", vf.get("address", ""), business.get("address", {}).get("full", ""), "Khớp" if vf.get("address") == business.get("address", {}).get("full") else "LỆCH"],
        ["Điện thoại", vf.get("phone", ""), business.get("contact", {}).get("phone", ""), "Khớp" if vf.get("phone") == business.get("contact", {}).get("phone") else "LỆCH"],
        ["Giờ mở cửa", vf.get("hours", ""), business.get("hours", ""), "Khớp" if vf.get("hours") == business.get("hours") else "LỆCH"],
        ["Zalo", "", business.get("contact", {}).get("zalo", ""), "Nguồn _data/business.yml"],
        ["WhatsApp", "", business.get("contact", {}).get("whatsapp", ""), "Nguồn _data/business.yml"],
        ["Google Maps", "", business.get("contact", {}).get("maps", ""), "Nguồn _data/business.yml"],
        ["Google Business Profile", "N/A", "N/A", "UNKNOWN — không có quyền truy cập GBP trong phiên này"],
    ]
    for f in audit.get("local_checks", []):
        loc_rows.append([f.get("item", ""), f.get("expected", ""), f.get("observed", ""), f.get("status", "")])
    b.sheet("LOCAL SEO & CONVERSION", ["Hạng mục", "Nguồn xác thực (business-facts.json)", "Giá trị dùng trên site", "Trạng thái"], loc_rows,
            widths={1: 28, 2: 55, 3: 55, 4: 50})

    # ---------------- 20. GSC PERFORMANCE ----------------
    b.sheet("GSC PERFORMANCE", ["Chỉ số", "28 ngày", "3 tháng", "Kỳ so sánh", "Ghi chú"],
            [[m, "N/A", "N/A", "N/A", NA_GSC] for m in ["Clicks", "Impressions", "CTR", "Average position", "Trang được index", "Core Web Vitals (field)", "Sitemap coverage"]],
            widths={1: 26, 5: 80},
            note="Baseline KPI sẽ điền khi chủ website thêm property blog.thuexemaynguyentu.com vào công cụ có quyền đọc (OpenRush/OpenSEO/Windsor). Không dùng số của website khác.")

    # ---------------- 21. PRIORITY BACKLOG ----------------
    bl_rows = []
    for dim in audit.get("dimensions", []):
        for f in dim.get("findings", []):
            bl_rows.append([f.get("id", ""), "audit " + (aud_path.stem if aud_path else ""), f.get("title", ""), f.get("severity", ""), dim.get("dimension", ""),
                            f.get("fix_class", ""), f.get("affected_count", ""), f.get("status", "OPEN"), f.get("next", "") or f.get("proposed_fix", "")])
    for it in ckpt.get("items", []):
        st = it.get("status", "")
        pr = "P1" if st.startswith("BLOCKED") else "P2" if st in ("OPEN", "PARTIAL", "DEFERRED") else "P3"
        bl_rows.append([it.get("id", ""), "checkpoint wave1-3", it.get("what") or it.get("why", ""), pr if st != "DONE" else "-", "seo-master",
                        "", "", st, it.get("next", "")])
    ws_bl = b.sheet("PRIORITY BACKLOG", ["ID", "Nguồn", "Việc", "Priority", "Nhóm", "Loại sửa", "Số URL", "Trạng thái", "Bước tiếp theo"],
                    bl_rows, widths={1: 16, 2: 22, 3: 70, 5: 18, 6: 18, 8: 26, 9: 70})
    bl_last = 1 + len(bl_rows)
    priority_fill(ws_bl, "D", 2, bl_last)

    # ---------------- 22. QA RESULTS ----------------
    qa_rows = []
    for c in changes.get("qa_checks", []):
        qa_rows.append([c.get("check", ""), c.get("scope", ""), c.get("result", ""), c.get("evidence", "")])
    for s in changes.get("qa_scores", []):
        qa_rows.append([f"QA nội bộ /100: {s.get('target','')}", s.get("breakdown", ""), s.get("score", ""), s.get("note", "")])
    qa_vals = [q.get("quality") for q in qa.values() if isinstance(q.get("quality"), (int, float))]
    qa_rows.append(["Evidence factory data/qa: số bài có điểm", "data/qa/*.json", len(qa_vals), "FACT"])
    for lo, hi in [(90, 101), (85, 90), (75, 85), (0, 75)]:
        qa_rows.append([f"Evidence factory: quality {lo}–{hi - 1}", "data/qa/*.json", sum(1 for v in qa_vals if lo <= v < hi), "FACT"])
    b.sheet("QA RESULTS", ["Kiểm tra", "Phạm vi", "Kết quả", "Bằng chứng"], qa_rows, widths={1: 50, 2: 40, 3: 18, 4: 80},
            note="Thang QA nội bộ 100 điểm (intent 20, chính xác 20, on-page 15, kiến trúc 15, kỹ thuật 15, UX/CRO 10, schema 5) là công cụ quản trị, không phải điểm Google.")

    # ---------------- 23. CHANGELOG & CHECKPOINT ----------------
    ch_rows = []
    for c in changes.get("changes", []):
        ch_rows.append([c.get("id", ""), c.get("date", ""), c.get("area", ""), c.get("files", ""), c.get("what", ""), c.get("status", ""),
                        c.get("commit", ""), c.get("verification", "")])
    for r in fixlog:
        ch_rows.append([r["id"], "", r["area"], r["target"], r["action"], r["status"], r["commit"], r["live_verification"]])
    ws_ch = b.sheet("CHANGELOG & CHECKPOINT", ["ID", "Ngày", "Khu vực", "Tệp", "Thay đổi", "Trạng thái", "Commit", "Xác minh"], ch_rows,
                    widths={3: 18, 4: 40, 5: 70, 6: 16, 7: 14, 8: 60})
    r0 = len(ch_rows) + 4
    ws_ch.cell(row=r0, column=1, value="CHECKPOINT").font = F_BOLD
    cp = changes.get("checkpoint", {}) or {}
    for i, (k, v) in enumerate(cp.items(), 1):
        ws_ch.cell(row=r0 + i, column=1, value=k).font = F_BOLD
        ws_ch.cell(row=r0 + i, column=2, value=v if not isinstance(v, (list, dict)) else json.dumps(v, ensure_ascii=False)).font = F_BASE

    # ---------------- 1. EXECUTIVE DASHBOARD (đặt đầu) ----------------
    ws = b.wb.create_sheet("EXECUTIVE DASHBOARD", 0)
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 70
    ws.cell(row=1, column=1, value="MASTER SEO MATRIX — blog.thuexemaynguyentu.com").font = F_TITLE
    ws.cell(row=2, column=1, value=f"Dữ liệu đến: {as_of}. Mọi ô số dưới đây là công thức tham chiếu các sheet dữ liệu.").font = F_NOTE
    U = "'URL INVENTORY'"
    BL = "'PRIORITY BACKLOG'"
    kpis = [
        ("Tổng URL kiểm kê", f"=COUNTA({U}!A3:A{inv_last})", "Build cục bộ HEAD; xem URL INVENTORY"),
        ("URL đã kiểm tra (có kết quả HTML)", f"=COUNTIF({U}!F3:F{inv_last},\"INDEXABLE*\")+COUNTIF({U}!F3:F{inv_last},\"NOINDEX*\")+COUNTIF({U}!F3:F{inv_last},\"REDIRECT*\")", ""),
        ("URL indexable (trong sitemap)", f"=COUNTIF({U}!F3:F{inv_last},\"INDEXABLE (200*\")", "Kỹ thuật cho phép index; index thật trên Google = UNKNOWN"),
        ("URL noindex (chủ đích)", f"=COUNTIF({U}!F3:F{inv_last},\"NOINDEX*\")", "/tim-kiem/"),
        ("URL chuyển hướng (stub di trú slug)", f"=COUNTIF({U}!F3:F{inv_last},\"REDIRECT*\")", "HTTP 200 + meta refresh 0s, không phải 301"),
        ("URL index trên Google (xác nhận GSC)", "N/A", NA_GSC),
        ("Bài viết (Post)", f"=COUNTIF({U}!C3:C{inv_last},\"Post\")", ""),
        ("Pillar", f"=COUNTIF({U}!C3:C{inv_last},\"Pillar\")", ""),
        ("Hub", f"=COUNTIF({U}!C3:C{inv_last},\"Hub\")", ""),
        ("Trang danh sách (phân trang)", f"=COUNTIF({U}!C3:C{inv_last},\"Listing\")", ""),
        ("Trang tĩnh", f"=COUNTIF({U}!C3:C{inv_last},\"Page\")", ""),
        ("Việc P0 (backlog, chưa DONE)", f"=COUNTIFS({BL}!D2:D{bl_last},\"P0\",{BL}!H2:H{bl_last},\"<>DONE\")", ""),
        ("Việc P1 (backlog, chưa DONE)", f"=COUNTIFS({BL}!D2:D{bl_last},\"P1\",{BL}!H2:H{bl_last},\"<>DONE\")", ""),
        ("Việc P2 (backlog, chưa DONE)", f"=COUNTIFS({BL}!D2:D{bl_last},\"P2\",{BL}!H2:H{bl_last},\"<>DONE\")", ""),
        ("Việc P3 (backlog, chưa DONE)", f"=COUNTIFS({BL}!D2:D{bl_last},\"P3\",{BL}!H2:H{bl_last},\"<>DONE\")", ""),
        ("Việc đã sửa (DONE)", f"=COUNTIF({BL}!H2:H{bl_last},\"DONE\")", "Gồm wave 1–3 + wave hiện tại"),
        ("Việc BLOCKED / chờ chủ", f"=COUNTIF({BL}!H2:H{bl_last},\"BLOCKED*\")+COUNTIF({BL}!H2:H{bl_last},\"NEEDS_OWNER*\")", ""),
        ("URL cần hành động (needs_action)", f"=COUNTIF({U}!AB3:AB{inv_last},\"<>KEEP\")", "Xem PAGE & POST OPTIMIZATION"),
        ("Bài factory có evidence QA", f"=COUNTIF({U}!AF3:AF{inv_last},\">=0\")", "data/qa/<ID>.json"),
        ("Bài factory QA ≥ 90 (EXCELLENT)", f"=COUNTIF({U}!AF3:AF{inv_last},\">=90\")", ""),
        ("Bài factory QA 75–89", f"=COUNTIFS({U}!AF3:AF{inv_last},\">=75\",{U}!AF3:AF{inv_last},\"<90\")", ""),
        ("Clicks / Impressions / CTR / Position (blog)", "N/A", NA_GSC),
    ]
    ws.cell(row=4, column=1, value="Chỉ số").font = F_HEAD
    ws.cell(row=4, column=2, value="Giá trị").font = F_HEAD
    ws.cell(row=4, column=3, value="Ghi chú / nguồn").font = F_HEAD
    for c in range(1, 4):
        ws.cell(row=4, column=c).fill = FILL_HEAD
    for i, (k, f, note) in enumerate(kpis, 5):
        ws.cell(row=i, column=1, value=k).font = F_BASE
        cell = ws.cell(row=i, column=2, value=f)
        cell.font, cell.fill, cell.border = F_BOLD, FILL_KPI, BORDER
        ws.cell(row=i, column=3, value=note).font = F_NOTE
    # tiến độ theo pillar
    r0 = 5 + len(kpis) + 2
    ws.cell(row=r0, column=1, value="Tiến độ theo Pillar / Hub (số bài theo cột Hub (parent) của URL INVENTORY)").font = F_BOLD
    ws.cell(row=r0 + 1, column=1, value="Pillar").font = F_HEAD
    ws.cell(row=r0 + 1, column=2, value="Số bài").font = F_HEAD
    ws.cell(row=r0 + 1, column=3, value="Bài cần hành động").font = F_HEAD
    for c in range(1, 4):
        ws.cell(row=r0 + 1, column=c).fill = FILL_HEAD
    for i, p in enumerate(tax.get("parents", []), r0 + 2):
        ws.cell(row=i, column=1, value=p["title"]).font = F_BASE
        ws.cell(row=i, column=2, value=f"=COUNTIFS({U}!G3:G{inv_last},A{i},{U}!C3:C{inv_last},\"Post\")").font = F_BOLD
        ws.cell(row=i, column=3, value=f"=COUNTIFS({U}!G3:G{inv_last},A{i},{U}!AB3:AB{inv_last},\"<>KEEP\")").font = F_BOLD
    ws.freeze_panes = "A5"

    for wsx in b.wb.worksheets:
        wsx.sheet_view.zoomScale = 100
    b.save(Path(a.out))
    print(f"OK: {a.out} — {len(b.wb.sheetnames)} sheet: {', '.join(b.wb.sheetnames)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
