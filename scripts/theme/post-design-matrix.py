#!/usr/bin/env python3
"""Excel Master Matrix của Post Design System (docs/POST-DESIGN-SYSTEM.md).

Chỉ ĐỌC kết quả QA do scripts/theme/post-design-qa.cjs ghi (inventory.json + batch-NNN.json)
và, nếu có, báo cáo bất biến SEO (scripts/theme/seo-invariance.py --json). Không đọc/ghi
_posts/, matrix sản xuất, data/ hay checkpoint.

    python3 scripts/theme/post-design-matrix.py --qa <thư mục QA> \
        --out reports/theme-upgrade/post-design-matrix.xlsx [--invariance <json>] [--csv <file.csv>]

Mỗi bài một dòng: lô, URL, tiêu đề, thành phần được áp dụng, quyết định KEEP/FIX, kết quả QA.
  KEEP = bài giữ nguyên cấu trúc, chỉ dùng lớp typography/bố cục chung.
  FIX  = bài được nâng cấp bằng ít nhất một thành phần của thư viện (thẻ, bảng, accordion…).
Lô chưa QA hiển thị PENDING, nên chạy lại sau mỗi lô là cập nhật tiến độ.
"""
import argparse
import csv
import glob
import json
import os
import sys
from collections import Counter, OrderedDict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# Tên hiển thị của 15 thành phần (khóa = dấu hiệu đo được trong trang).
COMPONENTS = OrderedDict([
    ("summary", "Summary Card"),
    ("highlight", "Highlight Card (sapo)"),
    ("tip", "Expert Tips"),
    ("warning", "Warning Card"),
    ("table", "Premium Pricing Table"),
    ("proscons", "Pros & Cons"),
    ("steps", "Timeline"),
    ("checklist", "Checklist"),
    ("compare", "Comparison Card"),
    ("related", "Related Content"),
    ("contact", "Local Service Card"),
    ("cta", "CTA Card"),
    ("faq", "FAQ Accordion"),
    ("number", "Number Card (chip số liệu)"),
    ("quote", "Quote Card"),
])
# Thành phần khung, bài nào cũng có: không tính vào quyết định KEEP/FIX.
CHROME = ("highlight", "related", "cta", "number")
EXTRA = OrderedDict([
    ("sources", "Nguồn đối chiếu (chú thích)"),
    ("legal", "Lưu ý pháp lý"),
    ("price", "Lưu ý bảng giá"),
    ("photos", "Ảnh thực tế + chú thích"),
    ("toc", "Mục lục"),
])


def components_of(row):
    """Trả về (dict thành phần -> ghi chú) cho một bài đã đo."""
    kinds = {}
    for kind in row.get("kinds", []):
        name, _, card = kind.partition(":")
        kinds[name] = "thẻ" if card else "mục"
    found = OrderedDict()
    if "summary" in kinds:
        found["summary"] = "thẻ"
    if row.get("title"):
        found["highlight"] = "sapo"
    if "tip" in kinds:
        found["tip"] = kinds["tip"]
    if "warning" in kinds:
        found["warning"] = kinds["warning"]
    if row.get("tables"):
        found["table"] = "%d bảng" % row["tables"]
    if row.get("pros"):
        found["proscons"] = "%d tiêu đề" % row["pros"]
    if "steps" in kinds:
        found["steps"] = "mục"
    if "checklist" in kinds:
        found["checklist"] = "mục"
    if "compare" in kinds:
        found["compare"] = "mục"
    if row.get("related") or row.get("siblings"):
        found["related"] = "khung"
    if "contact" in kinds:
        found["contact"] = "thẻ"
    if row.get("cta"):
        found["cta"] = "khung"
    if row.get("accBuilt"):
        found["faq"] = "%d câu" % row.get("accButtons", 0)
    found["number"] = "khung"
    if row.get("quotes"):
        found["quote"] = "%d trích dẫn" % row["quotes"]
    extra = OrderedDict()
    if "sources" in kinds:
        extra["sources"] = "chú thích"
    if row.get("legalNotice"):
        extra["legal"] = "có"
    if row.get("priceNotice"):
        extra["price"] = "có"
    if row.get("photos"):
        extra["photos"] = "%d ảnh" % row["photos"]
    if row.get("toc"):
        extra["toc"] = "có"
    return found, extra


def load(qa_dir):
    with open(os.path.join(qa_dir, "inventory.json"), encoding="utf-8") as handle:
        inventory = json.load(handle)
    measured = {}
    checked = {}
    for name in sorted(glob.glob(os.path.join(qa_dir, "batch-*.json"))):
        with open(name, encoding="utf-8") as handle:
            data = json.load(handle)
        for row in data["posts"]:
            measured[row["url"]] = row
        checked[data["batch"]] = data.get("checked_at", "")
    return inventory, measured, checked


def load_invariance(path):
    """None = chưa có báo cáo; ngược lại trả về (số trang so sánh, tập trang lệch)."""
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    hard = ("lang", "title", "meta", "head_links", "jsonld", "headings", "links", "images", "text", "aria_labels", "error")
    differing = set()
    for cat in hard:
        for page in report.get("diff_pages", {}).get(cat, []):
            differing.add(page)
    total = sum(report.get("diff_counts", {}).get(cat, 0) for cat in hard)
    total += len(report.get("html_only_in_base", [])) + len(report.get("html_only_in_new", []))
    return {"compared": report.get("pages_compared", 0), "hard": total, "pages": differing}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--invariance")
    parser.add_argument("--csv")
    opts = parser.parse_args()

    inventory, measured, checked = load(opts.qa)
    invariance = load_invariance(opts.invariance)

    headers = ["STT", "Lô", "URL", "Tiêu đề (H1)", "Ngày đăng", "Số từ (thân bài)", "Số H2", "Số H3",
               "Quyết định", "Số thành phần nội dung", "Thành phần nội dung áp dụng", "Thành phần khung",
               "Phần bổ trợ", "QA hiển thị", "Tràn ngang 390/820/1440 (px)", "CLS", "Lỗi JS/HTTP",
               "SEO bất biến (title/meta/H1/URL/canonical/link/chữ)", "Ghi chú"]
    rows = []
    stats = Counter()
    per_batch = OrderedDict()
    comp_count = Counter()
    for item in inventory["posts"]:
        url = item["url"]
        batch = item["batch"]
        bucket = per_batch.setdefault(batch, Counter())
        bucket["total"] += 1
        row = measured.get(url)
        if row is None:
            rows.append([item["n"], batch, url, "", "", "", "", "", "PENDING", "", "", "", "", "PENDING", "", "", "", "", "chưa QA"])
            stats["pending"] += 1
            bucket["pending"] += 1
            continue
        found, extra = components_of(row)
        content = [key for key in found if key not in CHROME]
        chrome = [key for key in found if key in CHROME]
        decision = "FIX" if content else "KEEP"
        for key in found:
            comp_count[key] += 1
        for key in extra:
            comp_count[key] += 1
        if invariance is None:
            seo = "chưa chạy"
        elif invariance["hard"] == 0:
            seo = "PASS"
        else:
            seo = "FAIL" if url.lstrip("/") + "index.html" in invariance["pages"] else "PASS"
        overflow = "/".join(str((row.get(vp) or {}).get("overflow", "?")) for vp in ("mobile", "tablet", "desktop"))
        note = "; ".join(row.get("issues", [])) if row.get("issues") else (
            "typography chung, không cần thành phần riêng" if decision == "KEEP" else "")
        rows.append([
            item["n"], batch, url, row.get("title", "").strip(), row.get("date", ""), row.get("words", ""),
            row.get("h2", ""), row.get("h3", ""), decision, len(content),
            ", ".join("%s (%s)" % (COMPONENTS[key], found[key]) for key in content),
            ", ".join(COMPONENTS[key] for key in chrome),
            ", ".join("%s (%s)" % (EXTRA[key], extra[key]) for key in extra),
            row.get("qa", ""), overflow, row.get("cls", ""), len(row.get("errors", [])), seo, note,
        ])
        stats[decision] += 1
        stats["qa_" + row.get("qa", "?")] += 1
        bucket[decision] += 1
        bucket["qa_" + row.get("qa", "?")] += 1
        if seo == "FAIL":
            stats["seo_fail"] += 1

    workbook = Workbook()
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="0066CC")
    fills = {"KEEP": PatternFill("solid", fgColor="E8F0FE"), "FIX": PatternFill("solid", fgColor="EAF6EE"),
             "PASS": PatternFill("solid", fgColor="EAF6EE"), "FAIL": PatternFill("solid", fgColor="FDE2E1"),
             "PENDING": PatternFill("solid", fgColor="FFF6E3")}

    sheet = workbook.active
    sheet.title = "Master Matrix"
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = head_font
        cell.fill = head_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for row in rows:
        sheet.append(row)
    for index, row in enumerate(rows, start=2):
        for col in (9, 14, 18):
            fill = fills.get(str(row[col - 1]))
            if fill:
                sheet.cell(row=index, column=col).fill = fill
    widths = [7, 6, 70, 60, 12, 10, 7, 7, 11, 10, 60, 44, 40, 11, 16, 8, 9, 20, 50]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "D2"
    sheet.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(headers)), len(rows) + 1)
    sheet.row_dimensions[1].height = 42

    total = len(rows)
    done = total - stats["pending"]
    summary = workbook.create_sheet("Tổng hợp")
    lines = [
        ("Tổng số bài (layout: post)", total),
        ("Đã QA", done),
        ("Chưa QA (PENDING)", stats["pending"]),
        ("Tiến độ", "%.1f%%" % (100.0 * done / total if total else 0)),
        ("KEEP — giữ cấu trúc, typography chung", stats["KEEP"]),
        ("FIX — nâng cấp bằng thành phần", stats["FIX"]),
        ("QA hiển thị PASS", stats["qa_PASS"]),
        ("QA hiển thị FAIL", stats["qa_FAIL"]),
        ("SEO bất biến", "chưa chạy" if invariance is None else (
            "PASS — %d trang so sánh, 0 khác biệt" % invariance["compared"] if invariance["hard"] == 0
            else "FAIL — %d khác biệt" % invariance["hard"])),
        ("Số lô (≤ %d bài/lô)" % inventory.get("batch_size", 100), len(per_batch)),
    ]
    summary.append(["Chỉ số", "Giá trị"])
    for line in lines:
        summary.append(list(line))
    summary.append([])
    summary.append(["Thành phần", "Số bài áp dụng"])
    for key, label in list(COMPONENTS.items()) + list(EXTRA.items()):
        summary.append([label, comp_count.get(key, 0)])
    summary.append([])
    summary.append(["Lô", "Số bài", "KEEP", "FIX", "QA PASS", "QA FAIL", "Chưa QA", "Thời điểm QA (UTC)"])
    for batch, bucket in per_batch.items():
        summary.append([batch, bucket["total"], bucket["KEEP"], bucket["FIX"], bucket["qa_PASS"], bucket["qa_FAIL"],
                        bucket["pending"], checked.get(batch, "")])
    for row in summary.iter_rows(min_row=1, max_row=1):
        for cell in row:
            cell.font = head_font
            cell.fill = head_fill
    summary.column_dimensions["A"].width = 46
    summary.column_dimensions["B"].width = 44
    for letter in "CDEFG":
        summary.column_dimensions[letter].width = 11
    summary.column_dimensions["H"].width = 28

    legend = workbook.create_sheet("Chú giải")
    notes = [
        ("KEEP", "Bài giữ nguyên cấu trúc; chỉ nhận lớp typography, mục lục, thanh tiến độ và khung chung."),
        ("FIX", "Bài được nâng cấp bằng ≥ 1 thành phần nội dung (thẻ tóm tắt, cảnh báo, bảng, accordion, timeline…)."),
        ("Thành phần khung", "Sapo (Highlight), chip số liệu (Number), bài liên quan (Related), CTA: có ở mọi bài, không tính vào KEEP/FIX."),
        ("QA hiển thị", "Chromium ở 390/820/1440px: không tràn ngang, không phần tử vượt khung, đúng 1 H1, bảng nằm trong khung cuộn, "
                        "accordion dựng đủ và mở câu đầu, mục lục thu gọn trên điện thoại, CLS ≤ 0,05, không lỗi JS/HTTP."),
        ("SEO bất biến", "So với bản đang chạy: title, meta, canonical/hreflang, JSON-LD, heading, liên kết, ảnh, chữ và aria-label giống hệt."),
        ("Cách áp dụng", "Thành phần được chọn lúc render theo tiêu đề H2 và cấu trúc sẵn có của từng bài; không sửa file bài, "
                         "không thêm chữ, không đổi liên kết, giá, cọc, NAP."),
        ("Nguồn dữ liệu", "scripts/theme/post-design-qa.cjs (đo trên bản build) → scripts/theme/post-design-matrix.py (bảng này)."),
    ]
    legend.append(["Mục", "Ý nghĩa"])
    for note in notes:
        legend.append(list(note))
    for cell in legend[1]:
        cell.font = head_font
        cell.fill = head_fill
    legend.column_dimensions["A"].width = 22
    legend.column_dimensions["B"].width = 130
    for row in legend.iter_rows(min_row=2):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")

    os.makedirs(os.path.dirname(os.path.abspath(opts.out)), exist_ok=True)
    workbook.save(opts.out)
    if opts.csv:
        with open(opts.csv, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
    print("matrix: %d bài, đã QA %d (KEEP %d, FIX %d, PASS %d, FAIL %d), PENDING %d -> %s" % (
        total, done, stats["KEEP"], stats["FIX"], stats["qa_PASS"], stats["qa_FAIL"], stats["pending"], opts.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
