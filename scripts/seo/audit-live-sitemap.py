#!/usr/bin/env python3
"""Read-only production sitemap and Vietnamese d-slug audit (Issue #77).

No changes to published pages, permalinks, canonical, redirects or QA evidence.
Uses HTTP HEAD without automatic redirect following, falling back to GET for 405.
Designed for manual/on-demand GitHub Actions, not continuous crawling.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "https://blog.thuexemaynguyentu.com"
SITEMAP = ORIGIN + "/sitemap.xml"
MAP = ROOT / "reports/factory/seo-master/slug-d-migration-map.csv"
USER_AGENT = "NguyenTu-site-audit/1.0 (+read-only; sitemap)"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def status(url: str, timeout: float) -> tuple[int, str, str]:
    """Return (real HTTP status, Location header, error), never follow redirects."""
    last = ""
    for method in ("HEAD", "GET"):
        headers = {"User-Agent": USER_AGENT, "Cache-Control": "no-cache"}
        if method == "GET":
            headers["Range"] = "bytes=0-0"
        request = urllib.request.Request(url, method=method, headers=headers)
        try:
            with OPENER.open(request, timeout=timeout) as response:
                return response.status, response.headers.get("Location", ""), ""
        except urllib.error.HTTPError as exc:
            if exc.code == 405 and method == "HEAD":
                continue
            return exc.code, exc.headers.get("Location", ""), ""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = str(exc)[:200]
            break
    return 0, "", last or "request blocked"


def sitemap_urls(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    urls = []
    seen = set()
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "loc" or not node.text:
            continue
        url = node.text.strip()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "blog.thuexemaynguyentu.com":
            raise ValueError("foreign sitemap URL: " + url)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    if not urls:
        raise ValueError("sitemap has no URL entries")
    return urls


def slug_pairs(path: Path, limit: int) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        rows = csv.DictReader(fh)
        if not {"old_url", "new_url"} <= set(rows.fieldnames or []):
            raise ValueError("slug manifest is missing old_url/new_url")
        pairs = []
        for row in rows:
            old, new = row["old_url"], row["new_url"]
            if old.startswith("/") and new.startswith("/") and old != new:
                pairs.append((ORIGIN + old, ORIGIN + new))
                if limit and len(pairs) >= limit:
                    break
    return pairs


def audit(urls: list[str], workers: int, timeout: float, kind: str):
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(status, u, timeout): u for u in urls}
        for item in as_completed(pending):
            u = pending[item]
            try:
                st, location, err = item.result()
            except Exception as exc:  # keep a full report on a single failed task
                st, location, err = 0, "", str(exc)[:200]
            classification = ("OK" if st == 200 else
                              "NOT_FOUND" if st in (404, 410) else
                              "REDIRECT" if st in (301, 302, 303, 307, 308) else
                              "UNCERTAIN" if st == 0 or st in (403, 429, 500, 502, 503, 504) else
                              "HTTP_ERROR")
            results.append({"kind": kind, "url": u, "status": st,
                            "classification": classification, "location": location,
                            "error": err})
    return sorted(results, key=lambda x: x["url"])


def write_reports(dest: Path, rows: list[dict], note: dict):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "kind", "url", "status", "classification", "location", "error"])
        writer.writeheader()
        writer.writerows(rows)
    summary = dest.with_suffix(".json")
    summary.write_text(json.dumps(note, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def selftest():
    xml = (b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           b'<url><loc>https://blog.thuexemaynguyentu.com/xe-may/</loc></url>'
           b'<url><loc>https://blog.thuexemaynguyentu.com/xe-may/</loc></url></urlset>')
    assert sitemap_urls(xml) == [ORIGIN + "/xe-may/"]
    try:
        sitemap_urls(b"<urlset><url><loc>https://example.com/</loc></url></urlset>")
        raise AssertionError("foreign hosts must be rejected")
    except ValueError:
        pass
    assert status.__name__ == "status"
    print("SELFTEST PASS: XML parsing, domain guard and deduplication")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sitemap", default=SITEMAP)
    ap.add_argument("--out", default="reports/live-url-audit.csv")
    ap.add_argument("--max-urls", type=int, default=0,
                    help="0 = check entire sitemap; positive = bounded test")
    ap.add_argument("--slug-samples", type=int, default=20,
                    help="Check OLD/NEW example pairs; 0 disables pair checks")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if a.max_urls < 0 or not 1 <= a.workers <= 12 or not 2 <= a.timeout <= 60:
        ap.error("max-urls >=0; workers 1..12; timeout 2..60 required")
    if a.sitemap != SITEMAP:
        ap.error("only the approved production sitemap is permitted")
    try:
        with urllib.request.urlopen(urllib.request.Request(
                SITEMAP, headers={"User-Agent": USER_AGENT}), timeout=a.timeout) as response:
            if response.status != 200:
                raise ValueError("sitemap HTTP " + str(response.status))
            xml = response.read(16 * 1024 * 1024)
        all_urls = sitemap_urls(xml)
    except Exception as exc:
        print("BLOCKED: could not read live sitemap:", exc, file=sys.stderr)
        return 2
    chosen = all_urls[:a.max_urls] if a.max_urls else all_urls
    rows = audit(chosen, a.workers, a.timeout, "sitemap")
    sitemap_set = set(all_urls)
    # Checks sample canonical slug suggestions without changing any URL. These
    # new routes are NOT sitemap URLs yet, so 404 here means migration BLOCKED,
    # not that a live sitemap link is currently broken.
    pairs = slug_pairs(MAP, a.slug_samples) if a.slug_samples else []
    pairs = [(old, new) for old, new in pairs if old in sitemap_set]
    other = [u for old, new in pairs for u in (old, new)]
    probes = audit(sorted(set(other)), a.workers, a.timeout, "slug-probe") if other else []
    index = {r["url"]: r for r in probes}
    blocked = [
        {"old": old, "new": new, "old_http": index[old]["status"],
         "new_http": index[new]["status"]}
        for old, new in pairs
        if index[old]["status"] == 200 and index[new]["status"] == 404
    ]
    all_rows = rows + probes
    counts = {label: sum(r["classification"] == label for r in rows)
              for label in ("OK", "NOT_FOUND", "REDIRECT", "UNCERTAIN", "HTTP_ERROR")}
    note = {"sitemap_count": len(all_urls), "urls_checked": len(chosen),
            "counts": counts, "slug_pairs_probed": len(pairs),
            "slug_pairs_blocked_old_200_new_404": len(blocked),
            "slug_blocked_examples": blocked[:10],
            "scope": "sitemap HEAD audit + read-only OLD/NEW diagnostics",
            "important": "An OLD-200/NEW-404 pair must NOT be migrated without a real HTTP 301/308."}
    summary = write_reports(ROOT / a.out, all_rows, note)
    print(json.dumps(note, ensure_ascii=False, indent=2))
    print("reports:", ROOT / a.out, summary)
    if counts["NOT_FOUND"] or counts["REDIRECT"] or counts["HTTP_ERROR"]:
        return 1
    if counts["UNCERTAIN"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
