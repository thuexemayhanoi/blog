#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bất biến bề mặt SEO giữa hai bản build Jekyll (docs/POST-DESIGN-SYSTEM.md).

Dùng trước khi đổi layout/CSS: build bản đang chạy (main) và bản mới, rồi chứng minh mọi trang
giữ nguyên title, meta, canonical/hreflang, JSON-LD, heading, liên kết, ảnh và chữ hiển thị.
Chỉ ĐỌC hai thư mục build; cần lxml.

SEO-surface invariance diff between two built Jekyll sites.

Compares, for every HTML page present in either build:
  head   : <title>, every <meta> (name/property/http-equiv/charset + content),
           <link> rel=canonical/alternate/icon/manifest/etc. (stylesheets,
           preloads and other performance hints are reported separately),
           <html lang>, JSON-LD blocks (parsed, order-preserving)
  body   : heading outline (h1..h6 text), links (href + text, document order),
           images (src + alt), visible text (whitespace-normalised)
Also reports files that exist on only one side (HTML and non-HTML).

Usage: seo-invariance.py BASE_DIR NEW_DIR [--json OUT] [--examples N] [--jobs J]
Exit code 0 when every category is identical on every page, else 1.
"""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

from lxml import html as LH

WS = re.compile(r"\s+")
PERF_RELS = {"stylesheet", "preload", "prefetch", "preconnect", "dns-prefetch", "modulepreload"}
SKIP_TEXT_TAGS = {"script", "style", "noscript", "template"}


def norm(s):
    return WS.sub(" ", s or "").strip()


def visible_text(el):
    out = []

    def walk(node):
        if not isinstance(node.tag, str):
            if node.tail:
                out.append(node.tail)
            return
        if node.tag in SKIP_TEXT_TAGS:
            if node.tail:
                out.append(node.tail)
            return
        if node.text:
            out.append(node.text)
        for ch in node:
            walk(ch)
        if node.tail:
            out.append(node.tail)

    walk(el)
    return norm(" ".join(out))


def text_of(el):
    """Text of one element subtree, excluding script/style."""
    parts = []

    def walk(node):
        if not isinstance(node.tag, str) or node.tag in SKIP_TEXT_TAGS:
            return
        if node.text:
            parts.append(node.text)
        for ch in node:
            walk(ch)
            if ch.tail:
                parts.append(ch.tail)

    walk(el)
    return norm(" ".join(parts))


def extract(path):
    try:
        raw = open(path, "rb").read()
        doc = LH.document_fromstring(raw.decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}
    head = doc.find("head")
    body = doc.find("body")
    r = {}
    r["lang"] = doc.get("lang")
    titles = doc.xpath("//head/title")
    r["title"] = [norm(t.text_content()) for t in titles]
    metas = []
    if head is not None:
        for m in head.iter("meta"):
            metas.append(tuple(sorted((k, v) for k, v in m.attrib.items())))
    r["meta"] = metas
    links, perf = [], []
    if head is not None:
        for l in head.iter("link"):
            rels = set((l.get("rel") or "").lower().split())
            item = tuple(sorted((k, v) for k, v in l.attrib.items()))
            (perf if rels & PERF_RELS else links).append(item)
    r["head_links"] = links
    r["perf_links"] = perf
    ld = []
    for s in doc.xpath('//script[@type="application/ld+json"]'):
        txt = s.text or ""
        try:
            ld.append(json.dumps(json.loads(txt), ensure_ascii=False, sort_keys=False))
        except Exception:  # noqa: BLE001
            ld.append("UNPARSEABLE:" + norm(txt))
    r["jsonld"] = ld
    if body is None:
        r.update(headings=[], links=[], images=[], text="", body_class=None)
        return r
    r["headings"] = [(h.tag, text_of(h)) for h in body.iter("h1", "h2", "h3", "h4", "h5", "h6")]
    r["links"] = [(a.get("href"), text_of(a), a.get("rel"), a.get("target"), a.get("aria-current"))
                  for a in body.iter("a") if a.get("href") is not None]
    r["images"] = [(i.get("src"), i.get("alt"), i.get("srcset")) for i in body.iter("img")]
    r["text"] = visible_text(body)
    r["aria_labels"] = sorted(norm(e.get("aria-label")) for e in body.iter() if isinstance(e.tag, str) and e.get("aria-label"))
    return r


def list_files(root):
    htmls, others = {}, {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root)
            (htmls if fn.endswith(".html") else others)[rel] = p
    return htmls, others


CATS = ["lang", "title", "meta", "head_links", "jsonld", "headings", "links", "images", "text", "aria_labels"]
INFO_CATS = ["perf_links"]


def compare(args):
    rel, a, b = args
    ea, eb = extract(a), extract(b)
    if "error" in ea or "error" in eb:
        return rel, {"error": (ea.get("error"), eb.get("error"))}
    d = {}
    for c in CATS + INFO_CATS:
        if ea.get(c) != eb.get(c):
            d[c] = (ea.get(c), eb.get(c))
    return rel, d


def first_diff(a, b):
    if isinstance(a, list) and isinstance(b, list):
        sa, sb = [x for x in a if x not in b], [x for x in b if x not in a]
        if sa or sb:
            return {"only_base": sa[:6], "only_new": sb[:6], "len": (len(a), len(b))}
        return {"order_changed": True, "len": (len(a), len(b))}
    if isinstance(a, str) and isinstance(b, str):
        i = 0
        n = min(len(a), len(b))
        while i < n and a[i] == b[i]:
            i += 1
        return {"at": i, "base": a[max(0, i - 60):i + 140], "new": b[max(0, i - 60):i + 140], "len": (len(a), len(b))}
    return {"base": a, "new": b}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("--json")
    ap.add_argument("--examples", type=int, default=4)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", help="comma list of relative html paths to compare (default: all)")
    a = ap.parse_args()
    bh, bo = list_files(a.base)
    nh, no = list_files(a.new)
    only_base_html = sorted(set(bh) - set(nh))
    only_new_html = sorted(set(nh) - set(bh))
    only_base_other = sorted(set(bo) - set(no))
    only_new_other = sorted(set(no) - set(bo))
    common = sorted(set(bh) & set(nh))
    if a.only:
        want = set(a.only.split(","))
        common = [c for c in common if c in want]
    jobs = [(rel, bh[rel], nh[rel]) for rel in common]
    per_cat = {c: [] for c in CATS + INFO_CATS + ["error"]}
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        for rel, d in ex.map(compare, jobs, chunksize=64):
            for c, v in d.items():
                per_cat[c].append((rel, v))
    report = {
        "pages_compared": len(common),
        "html_only_in_base": only_base_html,
        "html_only_in_new": only_new_html,
        "other_only_in_base": only_base_other,
        "other_only_in_new": only_new_other,
        "diff_counts": {c: len(v) for c, v in per_cat.items()},
        "diff_pages": {c: [rel for rel, _ in v] for c, v in per_cat.items() if c not in INFO_CATS},
        "examples": {},
    }
    for c, v in per_cat.items():
        report["examples"][c] = [
            {"page": rel, "diff": ({"error": d} if c == "error" else first_diff(d[0], d[1]))}
            for rel, d in v[: a.examples]
        ]
    print("pages compared      :", len(common))
    print("html only in base   :", len(only_base_html), only_base_html[:8])
    print("html only in new    :", len(only_new_html), only_new_html[:8])
    print("other only in base  :", len(only_base_other), only_base_other[:12])
    print("other only in new   :", len(only_new_other), only_new_other[:12])
    hard = 0
    for c in CATS + ["error"]:
        n = len(per_cat[c])
        hard += n
        print("%-20s: %d pages differ" % (c, n))
        for ex_ in report["examples"][c]:
            print("    ", ex_["page"], json.dumps(ex_["diff"], ensure_ascii=False)[:700])
    for c in INFO_CATS:
        print("%-20s: %d pages differ (informational)" % (c, len(per_cat[c])))
        for ex_ in report["examples"][c][:2]:
            print("    ", ex_["page"], json.dumps(ex_["diff"], ensure_ascii=False)[:500])
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    hard += len(only_base_html) + len(only_new_html)
    sys.exit(0 if hard == 0 else 1)


if __name__ == "__main__":
    main()
