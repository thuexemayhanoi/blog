#!/usr/bin/env python3
"""SEO Master — kiểm tra hồi quy SEO trên một thư mục _site đã build (đọc-only, không mạng).

Dùng: check-regressions.py --site <_site> [--baseline-pages N]
Thoát 0 chỉ khi mọi bất biến PASS. Mỗi bất biến in một dòng PASS/FAIL kèm bằng chứng.

Bất biến:
  H1   trang chủ khớp từng ký tự với scripts/seo/frozen-homepage.json (H1, title, meta description, hero, canonical)
  H2   mọi trang HTML (trừ 404): đúng 1 canonical về https://blog.thuexemaynguyentu.com/, đúng 1 <h1>
  H3   không trang nào có hai <link rel="icon">
  H4   thanh phân trang <= MAX_PAGINATION_LINKS liên kết (chống phình liên kết)
  H5   mọi hub/pillar (trừ du-lich legacy) có phần giới thiệu >= 60 từ trước khối danh sách (chống hub rỗng)
  H6   hub con có khối "Bài nên đọc trước" khi _data/seo-leads.yml có dữ liệu cho hub đó
  H7   không bài nào thiếu breadcrumb; sitemap không chứa trang noindex/404
  H8   <title>/meta/og không có ký tự & trần
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[2]
SITE_URL = "https://blog.thuexemaynguyentu.com"
MAX_PAGINATION_LINKS = 60
MIN_HUB_INTRO_WORDS = 60

TITLE = re.compile(r"<title>(.*?)</title>", re.S)
CANON = re.compile(r'<link rel="canonical" href="([^"]*)"')
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
ICON = re.compile(r'<link rel="icon"')
PAG = re.compile(r'<nav class="pagination".*?</nav>', re.S)
ANCHOR = re.compile(r"<a ")
BAD_AMP = re.compile(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)")


def intro_words(page_html: str) -> int:
    """Số từ phần giới thiệu: giữa </h1> và <h2> đầu tiên trong trang (không tính menu/breadcrumb/danh sách bài)."""
    if "</h1>" not in page_html:
        return 0
    seg = page_html.split("</h1>", 1)[1].split("<h2", 1)[0]
    return len(re.sub(r"<[^>]+>", " ", seg).split())


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    args = ap.parse_args()
    site = Path(args.site)
    results: list[tuple[str, bool, str]] = []

    def check(code: str, ok: bool, evidence: str) -> None:
        results.append((code, ok, evidence))

    frozen = json.loads((ROOT / "scripts" / "seo" / "frozen-homepage.json").read_text(encoding="utf-8"))
    home = read(site / "index.html")
    g = lambda rx: html.unescape(re.sub(r"\s+", " ", re.search(rx, home, re.S).group(1)).strip())  # noqa: E731
    h1s = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in H1.findall(home)]
    diffs = []
    if h1s != [frozen["h1"]]:
        diffs.append(f"h1={h1s}")
    if g(r"<title>(.*?)</title>") != frozen["seo_title"]:
        diffs.append("title")
    if g(r'<meta name="description" content="(.*?)">') != frozen["meta_description"]:
        diffs.append("meta_description")
    if g(r'<p class="hero-subtitle">(.*?)</p>') != frozen["hero_description"]:
        diffs.append("hero_description")
    if g(r'<link rel="canonical" href="(.*?)"') != frozen["canonical"]:
        diffs.append("canonical")
    check("H1", not diffs, "trang chủ khớp bản đã duyệt" if not diffs else f"LỆCH: {diffs}")

    pages = [p for p in site.rglob("index.html")]
    pages.append(site / "404.html")
    bad_canon, bad_h1, dup_icon, bad_amp, no_bc, big_pag = [], [], [], [], [], []
    hub_urls = {"thue-xe", "xe-may", "an-toan-phap-ly", "cung-duong", "ky-nang", "hoi-dap", "du-lich"}
    for p in pages:
        if not p.exists():
            continue
        rel = p.relative_to(site).as_posix()
        t = read(p)
        if rel == "404.html":
            continue
        canon = CANON.findall(t)
        if len(canon) != 1 or not canon[0].startswith(SITE_URL + "/"):
            bad_canon.append(rel)
        if len(H1.findall(t)) != 1:
            bad_h1.append(rel)
        if len(ICON.findall(t)) > 1:
            dup_icon.append(rel)
        head = t[: t.find("</head>")] if "</head>" in t else t[:8000]
        for m in re.findall(r'<title>(.*?)</title>|content="([^"]*)"', head, re.S):
            if BAD_AMP.search(m[0] or m[1]):
                bad_amp.append(rel)
                break
        pag = PAG.search(t)
        if pag and len(ANCHOR.findall(pag.group(0))) > MAX_PAGINATION_LINKS:
            big_pag.append(rel)
        if re.search(r"/20\d\d/\d\d/\d\d/", "/" + rel) and 'aria-label="Đường dẫn"' not in t:
            no_bc.append(rel)
    check("H2", not bad_canon and not bad_h1, f"canonical sai/thiếu: {len(bad_canon)} {bad_canon[:3]}; H1 != 1: {len(bad_h1)} {bad_h1[:3]}")
    check("H3", not dup_icon, f"trang có >1 <link rel=icon>: {len(dup_icon)} {dup_icon[:3]}")
    check("H4", not big_pag, f"phân trang > {MAX_PAGINATION_LINKS} liên kết: {len(big_pag)} {big_pag[:3]}")
    check("H8", not bad_amp, f"& trần trong head: {len(bad_amp)} {bad_amp[:3]}")
    check("H7a", not no_bc, f"bài thiếu breadcrumb: {len(no_bc)} {no_bc[:3]}")

    # H5/H6: hub/pillar
    tax = json.loads((ROOT / "data" / "content-taxonomy.json").read_text(encoding="utf-8"))
    leads = yaml.safe_load((ROOT / "_data" / "seo-leads.yml").read_text(encoding="utf-8")) or {}
    thin, no_leads = [], []
    for par in tax["parents"]:
        if par["slug"] == "du-lich":
            continue
        if intro_words(read(site / par["slug"] / "index.html")) < MIN_HUB_INTRO_WORDS:
            thin.append(par["slug"])
    for c in tax["children"]:
        pth = site / c["hub_url"].strip("/") / "index.html"
        if not pth.exists():
            continue
        txt = read(pth)
        if intro_words(txt) < MIN_HUB_INTRO_WORDS:
            thin.append(c["hub_url"])
        if leads.get(c["child_id"]) and "Bài nên đọc trước" not in txt:
            no_leads.append(c["hub_url"])
    check("H5", not thin, f"hub/pillar mỏng (< {MIN_HUB_INTRO_WORDS} từ giới thiệu): {len(thin)} {thin[:5]}")
    check("H6", not no_leads, f"hub có dữ liệu lead nhưng không in khối: {len(no_leads)} {no_leads[:5]}")

    # H7b: sitemap không chứa noindex/404
    sm = read(site / "sitemap.xml")
    locs = [unquote(u.replace(SITE_URL, "")) for u in re.findall(r"<loc>([^<]+)</loc>", sm)]
    noidx = []
    for u in locs:
        p = site / u.strip("/") / "index.html" if u != "/" else site / "index.html"
        if p.exists() and re.search(r'<meta name="robots" content="[^"]*noindex', read(p)):
            noidx.append(u)
    check("H7b", not noidx and "/404.html" not in locs, f"sitemap chứa noindex/404: {noidx[:3]}; tổng URL {len(locs)}")

    width = max(len(c) for c, _, _ in results)
    failed = 0
    for code, ok, ev in results:
        print(f"{'PASS' if ok else 'FAIL'}  {code:<{width}}  {ev}")
        failed += 0 if ok else 1
    print(f"\nKẾT QUẢ: {'PASS' if not failed else 'FAIL'} ({len(results) - failed}/{len(results)} bất biến)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
