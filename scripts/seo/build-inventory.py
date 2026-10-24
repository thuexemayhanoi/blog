#!/usr/bin/env python3
"""SEO Master — URL inventory + audit từ NGUỒN THẬT (read-only với repo).

Đầu vào:
  - _posts/*.md (frontmatter + body)           -> dữ kiện nguồn
  - data/content-matrix.csv, content-taxonomy.json (tái sử dụng, KHÔNG tạo hệ thống cạnh tranh)
  - --site <thư mục _site> (tùy chọn)         -> dữ kiện HTML đã render (title/meta/canonical/H1/JSON-LD/link)

Đầu ra (mặc định reports/factory/seo-master/):
  - url-inventory.csv       một hàng / URL (post + page + hub + listing)
  - technical-issues.csv    mỗi lỗi: url/tệp, bằng chứng, ưu tiên, nguyên nhân, cách xử lý
  - inventory-summary.json  số liệu tổng hợp (FACT) + phạm vi đã kiểm

Nguyên tắc: không ghi vào _posts/, matrix, data/state, data/qa. Không gọi mạng.
Phân loại: FACT (đo được từ tệp), INFERRED (suy luận), UNKNOWN (chưa có dữ liệu).
Stdlib + PyYAML.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml

try:
    _YAML_LOADER = yaml.CSafeLoader
except AttributeError:  # pragma: no cover
    _YAML_LOADER = yaml.SafeLoader

ROOT = Path(__file__).resolve().parents[2]
SITE_URL = "https://blog.thuexemaynguyentu.com"
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)

# --------------------------------------------------------------------------- helpers


def norm_url(u: str) -> str:
    """Chuẩn hóa URL nội bộ để so sánh: bỏ domain, giải mã %, bỏ query/hash, thêm '/' cuối nếu là thư mục."""
    if not u:
        return ""
    p = urlparse(u)
    path = unquote(p.path or "/")
    if p.netloc and p.netloc not in ("blog.thuexemaynguyentu.com",):
        return ""  # ngoài site
    if not path.startswith("/"):
        return ""
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    return path


def strip_md(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[#>*_|\-]+", " ", text)
    return text


def word_count(text: str) -> int:
    return len(strip_md(text).split())


def load_posts() -> list[dict]:
    rows = []
    for f in sorted((ROOT / "_posts").glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        m = FM_RE.match(raw)
        fm = {}
        body = raw
        parse_err = ""
        if m:
            try:
                fm = yaml.load(m.group(1), Loader=_YAML_LOADER) or {}
            except Exception as exc:  # noqa: BLE001
                parse_err = str(exc)[:100]
            body = raw[m.end():]
        else:
            parse_err = "no_frontmatter"
        rows.append({"file": f"_posts/{f.name}", "fm": fm, "body": body, "parse_err": parse_err,
                     "sha1": hashlib.sha1(raw.encode()).hexdigest()[:12]})
    return rows


def load_static_pages() -> dict[str, dict]:
    """Trang tĩnh nguồn (.md ở gốc và trong thư mục pillar): url -> {file, words, layout, faq}. Bỏ listing sinh tự động."""
    out: dict[str, dict] = {}
    cands = list(ROOT.glob("*.md"))
    for d in ("thue-xe", "xe-may", "an-toan-phap-ly", "du-lich", "cung-duong", "ky-nang", "hoi-dap"):
        cands += list((ROOT / d).glob("*.md"))
    for f in cands:
        if f.name in ("README.md", "AGENTS.md", "THEME_UPGRADE_MATRIX.md"):
            continue
        raw = f.read_text(encoding="utf-8", errors="replace")
        m = FM_RE.match(raw)
        if not m:
            continue
        try:
            fm = yaml.load(m.group(1), Loader=_YAML_LOADER) or {}
        except Exception:  # noqa: BLE001
            continue
        if not fm.get("permalink"):
            continue
        body = raw[m.end():]
        out[norm_url(str(fm["permalink"]))] = {
            "file": str(f.relative_to(ROOT)), "words": word_count(body), "layout": fm.get("layout", ""),
        }
    return out


def load_matrix() -> dict[str, dict]:
    p = ROOT / "data" / "content-matrix.csv"
    out = {}
    if not p.exists():
        return out
    with p.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["output_path"]] = r
    return out


def load_taxonomy() -> tuple[dict, dict]:
    p = ROOT / "data" / "content-taxonomy.json"
    t = json.loads(p.read_text(encoding="utf-8"))
    parents = {x["parent_id"]: x for x in t["parents"]}
    children = {x["child_id"]: x for x in t["children"]}
    return parents, children


def load_legacy_map() -> dict[str, dict]:
    """_data/factory-map.yml: slug -> {p, c} cho bài legacy (không có parent/child trong frontmatter)."""
    p = ROOT / "_data" / "factory-map.yml"
    if not p.exists():
        return {}
    return yaml.load(p.read_text(encoding="utf-8"), Loader=_YAML_LOADER) or {}


def source_url(fm: dict, matrix_row: dict | None, filename: str) -> str:
    if fm.get("permalink"):
        return norm_url(str(fm["permalink"]))
    if matrix_row and matrix_row.get("expected_url"):
        return norm_url(matrix_row["expected_url"])
    return ""


HEAD_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.M)
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)


def body_headings(body: str) -> list[tuple[int, str]]:
    clean = re.sub(r"```.*?```", "", body, flags=re.S)
    return [(len(m.group(1)), m.group(2)) for m in HEAD_RE.finditer(clean)]


def body_links(body: str) -> list[str]:
    clean = re.sub(r"```.*?```", "", body, flags=re.S)
    links = MD_LINK_RE.findall(clean) + HTML_HREF_RE.findall(clean)
    return links


POST_URL_TAG = re.compile(r"\{%\s*post_url\s+([^\s%]+)\s*%\}")

# --------------------------------------------------------------------------- HTML phase

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
META_DESC_RE = re.compile(r"""<meta\s+name=["']description["']\s+content=["'](.*?)["']\s*/?>""", re.S | re.I)
CANON_RE = re.compile(r"""<link\s+rel=["']canonical["']\s+href=["'](.*?)["']""", re.I)
ROBOTS_RE = re.compile(r"""<meta\s+name=["']robots["']\s+content=["'](.*?)["']""", re.I)
H1_RE = re.compile(r"<h1[\s>].*?</h1>", re.S | re.I)
LD_RE = re.compile(r"""<script type=["']application/ld\+json["']>(.*?)</script>""", re.S | re.I)
A_HREF_RE = re.compile(r"""<a\s[^>]*?href=["']([^"']+)["']""", re.I)
ICON_RE = re.compile(r"""<link\s+rel=["']icon["']""", re.I)
REFRESH_RE = re.compile(r"""<meta\s[^>]*?http-equiv=["']refresh["'][^>]*?content=["']\s*\d+\s*;\s*url=([^"']+)["']""", re.I)
BREADCRUMB_RE = re.compile(r"""aria-label=["']Đường dẫn["']""")
MAIN_RE = re.compile(r"<main\b.*?</main>", re.S | re.I)


def scan_html(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="replace")
    d: dict = {"bytes": len(txt.encode("utf-8", "replace"))}
    m = TITLE_RE.search(txt)
    d["title"] = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else ""
    m = META_DESC_RE.search(txt)
    d["meta_description"] = html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else ""
    m = CANON_RE.search(txt)
    d["canonical"] = m.group(1) if m else ""
    m = ROBOTS_RE.search(txt)
    d["robots"] = m.group(1) if m else ""
    m = REFRESH_RE.search(txt)
    d["meta_refresh"] = html.unescape(m.group(1)).strip() if m else ""      # trang chuyển hướng slug đ->d (HTTP 200 + meta refresh)
    d["h1_count"] = len(H1_RE.findall(txt))
    h1 = H1_RE.search(txt)
    d["h1"] = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h1.group(0))).strip()) if h1 else ""
    types = []
    ld_errors = 0
    for blob in LD_RE.findall(txt):
        try:
            j = json.loads(blob)
        except Exception:  # noqa: BLE001
            ld_errors += 1
            continue
        nodes = j.get("@graph", [j]) if isinstance(j, dict) else j
        for n in nodes:
            t = n.get("@type") if isinstance(n, dict) else None
            if isinstance(t, list):
                types.extend(t)
            elif t:
                types.append(t)
    d["jsonld_types"] = "|".join(sorted(set(types)))
    d["jsonld_errors"] = ld_errors
    d["icon_links"] = len(ICON_RE.findall(txt))
    d["has_breadcrumb"] = bool(BREADCRUMB_RE.search(txt))
    main = MAIN_RE.search(txt)
    scope = main.group(0) if main else txt
    d["_links_main"] = [h for h in A_HREF_RE.findall(scope)]
    d["_links_all"] = [h for h in A_HREF_RE.findall(txt)]
    return d


def url_of_html(site: Path, p: Path) -> str:
    rel = p.relative_to(site).as_posix()
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return "/" + rel if not rel.startswith("/") else rel


# --------------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", help="thư mục _site đã build (bật phase HTML)")
    ap.add_argument("--out", default=str(ROOT / "reports" / "factory" / "seo-master"))
    ap.add_argument("--graph-out", help="ghi đồ thị liên kết nội bộ đã render (JSON, không commit) để build-matrix.py dùng")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    posts = load_posts()
    matrix = load_matrix()
    parents, children = load_taxonomy()
    legacy_map = load_legacy_map()
    static_pages = load_static_pages()

    issues: list[dict] = []

    def issue(code, prio, target, evidence, cause, fix, status="OPEN"):
        issues.append({"code": code, "priority": prio, "target": target, "evidence": evidence,
                       "cause": cause, "proposed_fix": fix, "status": status})

    inv: dict[str, dict] = {}  # key = norm url
    by_file: dict[str, dict] = {}
    title_idx = collections.defaultdict(list)
    desc_idx = collections.defaultdict(list)
    slug_idx = collections.defaultdict(list)
    kw_idx = collections.defaultdict(list)

    for p in posts:
        fm = p["fm"]
        mrow = matrix.get(p["file"])
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", Path(p["file"]).stem)
        url = source_url(fm, mrow, p["file"])
        pid = fm.get("parent_id")
        cid = fm.get("child_id")
        lm = legacy_map.get(slug) or {}
        if not pid:
            pid = lm.get("p")
        if not cid:
            cid = lm.get("c")
        title = str(fm.get("title", "")).strip()
        desc = str(fm.get("description", "")).strip()
        heads = body_headings(p["body"])
        h1_in_body = sum(1 for lvl, _ in heads if lvl == 1)
        skipped = 0
        prev = 1  # H1 do layout
        for lvl, _ in heads:
            if lvl > prev + 1:
                skipped += 1
            prev = lvl
        links = body_links(p["body"])
        internal = []
        ext = 0
        for l in links:
            if l.startswith(("http://", "https://")):
                n = norm_url(l)
                if n:
                    internal.append(n)
                else:
                    ext += 1
            elif l.startswith("/"):
                internal.append(norm_url(l))
            elif POST_URL_TAG.search(l) or l.startswith(("#", "mailto:", "tel:")):
                pass
        row = {
            "url": url,
            "type": "Post",
            "source_file": p["file"],
            "article_id": fm.get("article_id", ""),
            "matrix_status": (mrow or {}).get("status", ""),
            "parent_id": pid or "",
            "child_id": cid or "",
            "child_title": (children.get(cid) or {}).get("title", ""),
            "date": str(fm.get("date", ""))[:10],
            "title": title,
            "title_len": len(title),
            "description": desc,
            "description_len": len(desc),
            "primary_keyword": (mrow or {}).get("primary_keyword", ""),
            "search_intent": (mrow or {}).get("search_intent", "") or (mrow or {}).get("intent", ""),
            "cannibalization_key": (mrow or {}).get("cannibalization_key", ""),
            "words": word_count(p["body"]),
            "h1_in_body": h1_in_body,
            "h2": sum(1 for l, _ in heads if l == 2),
            "h3": sum(1 for l, _ in heads if l == 3),
            "heading_skips": skipped,
            "body_internal_links": len(internal),
            "body_external_links": ext,
            "tags": len(fm.get("tags") or []),
            "tags_text": " | ".join(str(t) for t in (fm.get("tags") or [])),
            "writer": fm.get("writer", ""),
            "_internal": internal,
            "_links_raw": links,
        }
        by_file[p["file"]] = row
        if url:
            if url in inv:
                issue("DUP_URL", "P0", p["file"], f"url {url} trùng với {inv[url]['source_file']}",
                      "permalink trùng", "Điều tra thủ công; KHÔNG đổi URL hàng loạt")
            inv[url] = row
        else:
            issue("NO_URL", "P1", p["file"], "không suy ra được URL từ permalink/matrix",
                  "bài legacy thiếu expected_url", "Đối chiếu sitemap sau build")
        if p["parse_err"]:
            issue("FRONTMATTER_PARSE", "P0", p["file"], p["parse_err"], "YAML lỗi", "Sửa frontmatter qua quy trình bảo trì có kiểm soát")
        if title:
            title_idx[title.lower()].append(p["file"])
        if desc:
            desc_idx[desc.lower()].append(p["file"])
        slug_idx[slug].append(p["file"])
        if row["cannibalization_key"]:
            kw_idx[row["cannibalization_key"]].append(p["file"])
        if h1_in_body:
            issue("H1_IN_BODY", "P2", p["file"], f"{h1_in_body} H1 trong body (layout đã render H1 từ title)",
                  "nội dung có '# '", "Hạ thành H2 qua batch bảo trì nhỏ có QA", )
        if not desc:
            issue("NO_DESCRIPTION", "P1", p["file"], "thiếu description", "frontmatter", "Bổ sung description")
        elif len(desc) > 200:
            issue("DESC_TOO_LONG", "P3", p["file"], f"{len(desc)} ký tự", "meta quá dài", "Rút gọn khi bảo trì bài")

    # ------------------------------------------------------------------ duplicates (FACT)
    def dup_issue(idx, code, label):
        n = 0
        for key, files in idx.items():
            if len(files) > 1:
                n += 1
                for f in files:
                    issue(code, "P2", f, f"{label} trùng với {len(files)-1} bài khác: {', '.join(x for x in files if x != f)[:200]}",
                          "trùng nội dung metadata", "Phân biệt theo intent, KHÔNG xóa/đổi URL")
        return n

    n_dup_title = dup_issue(title_idx, "DUP_TITLE", "title")
    n_dup_desc = dup_issue(desc_idx, "DUP_DESCRIPTION", "description")
    n_dup_slug = dup_issue(slug_idx, "DUP_SLUG", "slug")
    n_dup_cann = dup_issue(kw_idx, "DUP_CANNIBALIZATION_KEY", "cannibalization_key")

    # ------------------------------------------------------------------ internal link resolution (body-level)
    known = set(inv.keys())
    # trang tĩnh nguồn (hub/pillar/...) -> thêm vào known khi chưa có site
    page_urls = set()
    for f in ROOT.glob("*.md"):
        pass
    broken_total = 0
    resolved_total = 0
    inbound = collections.Counter()
    for url, row in inv.items():
        for t in row["_internal"]:
            if t in known:
                resolved_total += 1
                if t != url:
                    inbound[t] += 1
    summary = {
        "generated_by": "scripts/seo/build-inventory.py",
        "posts_total": len(posts),
        "posts_with_url": len(inv),
        "dup_title_groups": n_dup_title,
        "dup_description_groups": n_dup_desc,
        "dup_slug_groups": n_dup_slug,
        "dup_cannibalization_key_groups": n_dup_cann,
        "body_internal_links_resolved_to_post": resolved_total,
    }

    # ------------------------------------------------------------------ HTML phase
    pages: dict[str, dict] = {}
    if args.site:
        site = Path(args.site)
        sitemap_urls: set[str] = set()
        sm = site / "sitemap.xml"
        if sm.exists():
            for loc in re.findall(r"<loc>(.*?)</loc>", sm.read_text(encoding="utf-8")):
                sitemap_urls.add(norm_url(loc))
        html_files = [p for p in site.rglob("*.html")]
        inbound_html = collections.Counter()
        inbound_html_main = collections.Counter()
        outlinks = {}
        for hp in html_files:
            u = url_of_html(site, hp) if hp.name == "index.html" else "/" + hp.relative_to(site).as_posix()
            u = norm_url(u)
            d = scan_html(hp)
            pages[u] = d
        all_urls = set(pages)
        for u, d in pages.items():
            tgt_all = set()
            for h in d["_links_all"]:
                n = norm_url(h) if (h.startswith("/") or h.startswith("http")) else ""
                if n:
                    tgt_all.add(n)
            outlinks[u] = tgt_all
            for n in tgt_all:
                if n != u:
                    inbound_html[n] += 1
            tgt_main = set()
            for h in d["_links_main"]:
                n = norm_url(h) if (h.startswith("/") or h.startswith("http")) else ""
                if n:
                    tgt_main.add(n)
            for n in tgt_main:
                if n != u:
                    inbound_html_main[n] += 1
            d["out_internal_main"] = len(tgt_main)
            d["out_internal_all"] = len(tgt_all)
            del d["_links_main"]
            del d["_links_all"]
        broken = collections.defaultdict(list)
        # broken: target không nằm trong all_urls (đã chuẩn hóa)
        for u, tg in outlinks.items():
            for n in tg:
                if n in all_urls:
                    continue
                last = n.rstrip("/").rsplit("/", 1)[-1]
                if "." in last:  # file tĩnh (css/js/img/xml) — kiểm riêng bằng sự tồn tại tệp
                    f = site / unquote(n.lstrip("/"))
                    if f.exists():
                        continue
                broken[n].append(u)
        if args.graph_out:
            Path(args.graph_out).write_text(json.dumps({u: sorted(t) for u, t in outlinks.items()}, ensure_ascii=False), encoding="utf-8")
        summary["html_pages"] = len(pages)
        summary["sitemap_urls"] = len(sitemap_urls)
        summary["broken_internal_targets"] = len(broken)
        for n, srcs in sorted(broken.items(), key=lambda kv: -len(kv[1]))[:500]:
            issue("BROKEN_INTERNAL_LINK", "P0", n, f"được link từ {len(srcs)} trang, ví dụ {srcs[0]}",
                  "đích không có trong _site", "Sửa tại nguồn link (template/hub) hoặc tạo trang đích nếu hợp lệ")

        for u, d in pages.items():
            if u == "/404.html":
                continue
            if d.get("meta_refresh"):
                # trang chuyển hướng (docs/SLUG-URL-POLICY.md): canonical phải là URL đích, không được nằm trong sitemap; các kiểm tra
                # canonical/H1/sitemap dành cho bài không áp dụng (đây KHÔNG phải HTTP 301)
                tgt = norm_url(d["meta_refresh"])
                if norm_url(d["canonical"]) != tgt:
                    issue("STUB_CANONICAL_MISMATCH", "P0", u, f"canonical={d['canonical']} meta_refresh={d['meta_refresh']}",
                          "trang chuyển hướng canonical khác đích", "Sinh lại trang chuyển hướng bằng migrate-slug-urls.py")
                if u in sitemap_urls:
                    issue("STUB_IN_SITEMAP", "P0", u, "trang chuyển hướng nằm trong sitemap.xml", "sitemap: false bị bỏ",
                          "Trang chuyển hướng phải có sitemap: false")
                continue
            if d["h1_count"] != 1:
                issue("H1_COUNT", "P1", u, f"h1_count={d['h1_count']}", "layout/nội dung", "Chuẩn hóa tại layout")
            if not d["canonical"]:
                issue("NO_CANONICAL", "P0", u, "thiếu canonical", "seo.html", "Thêm canonical tại include dùng chung")
            elif norm_url(d["canonical"]) != u and u != "/404.html":
                issue("CANONICAL_MISMATCH", "P0", u, f"canonical={d['canonical']}", "canonical khác URL render", "Điều tra")
            if "noindex" in d["robots"].lower():
                issue("NOINDEX", "P1", u, f"robots={d['robots']}", "meta robots", "Xác nhận chủ đích")
            if d["icon_links"] > 1:
                issue("DUP_ICON_LINK", "P3", u, f"{d['icon_links']} <link rel=icon>", "seo.html + default.html cùng emit favicon", "Bỏ một nguồn favicon")
            if d["jsonld_errors"]:
                issue("JSONLD_INVALID", "P0", u, f"{d['jsonld_errors']} khối JSON-LD không parse được", "template", "Sửa template")
            if u not in sitemap_urls and "noindex" not in d["robots"].lower() and u != "/404.html" and u != "/tim-kiem/":
                issue("NOT_IN_SITEMAP", "P2", u, "trang render nhưng không có trong sitemap.xml", "exclude/sitemap plugin", "Kiểm tra chủ đích")
        for su in sitemap_urls:
            if su and su not in all_urls:
                issue("SITEMAP_URL_NOT_RENDERED", "P0", su, "URL trong sitemap nhưng không có trang HTML", "lệch build", "Điều tra")

        # gắn dữ kiện render vào inv
        for u, row in inv.items():
            d = pages.get(u)
            if d:
                # Văn bản metadata của bài trùng với nguồn => chỉ ghi cờ so khớp (giữ tệp nhẹ, diff gọn khi làm mới)
                exp_canon = SITE_URL + u
                row.update({
                    "http_status_local": "200(local build)",
                    "title_in_html_ok": bool(d["title"]) and html.unescape(row.get("title", "")) in d["title"],
                    "meta_desc_matches_source": d["meta_description"] == html.unescape(row.get("description", "")) and bool(d["meta_description"]),
                    "canonical_ok": norm_url(d["canonical"]) == u and d["canonical"].startswith(SITE_URL + "/"),
                    "html_robots": d["robots"],
                    "html_h1_count": d["h1_count"], "h1_matches_title": d["h1"] == html.unescape(row.get("title", "")),
                    "jsonld_types": d["jsonld_types"], "has_breadcrumb": d["has_breadcrumb"],
                    "in_sitemap": u in sitemap_urls,
                    "inbound_links_html": inbound_html.get(u, 0),
                    "inbound_links_html_main": inbound_html_main.get(u, 0),
                    "outbound_internal_main": d["out_internal_main"],
                })
            else:
                row.update({"http_status_local": "MISSING_IN_BUILD"})
                issue("POST_NOT_RENDERED", "P0", u or row["source_file"], "bài không có trang HTML trong build", "Jekyll", "Điều tra")
        # trang không phải post
        post_urls = set(inv.keys())
        for u, d in pages.items():
            if u in post_urls or u == "/404.html":
                continue
            typ = "Page"
            if d.get("meta_refresh"):
                typ = "RedirectStub"
            elif u == "/":
                typ = "Home"
            elif u.count("/") == 2 and u in {"/thue-xe/", "/xe-may/", "/an-toan-phap-ly/", "/du-lich/", "/cung-duong/", "/ky-nang/", "/hoi-dap/"}:
                typ = "Pillar"
            elif u.count("/") == 3 and any(u.startswith(f"/{p}/") for p in ("thue-xe", "xe-may", "an-toan-phap-ly", "du-lich", "cung-duong", "ky-nang", "hoi-dap")):
                typ = "Hub"
            elif u.startswith(("/listing/", "/page/")) or "/trang/" in u or re.search(r"/\d+/$", u):
                typ = "Listing"
            sp = static_pages.get(u, {})
            inv.setdefault(u, {
                "url": u, "type": typ, "source_file": sp.get("file", ""), "words": sp.get("words", ""),
                "title": d["title"], "html_title": d["title"],
                "html_meta_description": d["meta_description"], "html_canonical": d["canonical"],
                "html_robots": d["robots"], "html_h1_count": d["h1_count"], "html_h1": d["h1"],
                "jsonld_types": d["jsonld_types"], "has_breadcrumb": d["has_breadcrumb"],
                "in_sitemap": u in sitemap_urls, "inbound_links_html": inbound_html.get(u, 0),
                "inbound_links_html_main": inbound_html_main.get(u, 0),
                "outbound_internal_main": d["out_internal_main"], "http_status_local": "200(local build)",
            })
        # orphan risk (INFERRED): post không có inbound link nào trong HTML render ngoài sitemap
        orphan = 0
        for u, row in inv.items():
            if row.get("type") == "Post":
                n_in = row.get("inbound_links_html", 0)
                row["orphan_risk"] = "HIGH" if n_in == 0 else ("LOW_INBOUND" if n_in == 1 else "OK")
                if n_in == 0:
                    orphan += 1
        summary["posts_zero_inbound_in_rendered_html"] = orphan
        summary["pages_by_type"] = dict(collections.Counter(r.get("type") for r in inv.values()))
        # phân phối inbound cho post
        dist = collections.Counter()
        for r in inv.values():
            if r.get("type") == "Post":
                n = r.get("inbound_links_html", 0)
                dist["0" if n == 0 else "1" if n == 1 else "2-4" if n <= 4 else "5-9" if n <= 9 else "10+"] += 1
        summary["post_inbound_distribution"] = dict(dist)

    # ------------------------------------------------------------------ ghi file
    cols = ["url", "type", "source_file", "article_id", "matrix_status", "parent_id", "child_id", "child_title",
            "date", "title", "title_len", "description_len", "primary_keyword", "search_intent",
            "cannibalization_key", "words", "h1_in_body", "h2", "h3", "heading_skips", "body_internal_links",
            "body_external_links", "tags", "tags_text", "writer", "http_status_local", "html_title", "html_meta_description",
            "title_in_html_ok", "meta_desc_matches_source", "canonical_ok", "html_canonical", "html_robots",
            "html_h1_count", "html_h1", "h1_matches_title", "jsonld_types", "has_breadcrumb",
            "in_sitemap", "inbound_links_html", "inbound_links_html_main", "outbound_internal_main", "orphan_risk"]
    rows_sorted = sorted(inv.values(), key=lambda r: (r.get("type", ""), r.get("url", "")))
    with (out / "url-inventory.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows_sorted:
            w.writerow({k: r.get(k, "") for k in cols})
    icols = ["code", "priority", "target", "evidence", "cause", "proposed_fix", "status"]
    with (out / "technical-issues.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=icols)
        w.writeheader()
        for i in issues:
            w.writerow(i)
    summary["issues_by_code"] = dict(collections.Counter(i["code"] for i in issues))
    summary["inventory_rows"] = len(rows_sorted)
    summary["phase_html"] = bool(args.site)
    (out / "inventory-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
