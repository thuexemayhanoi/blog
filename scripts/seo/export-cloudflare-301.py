#!/usr/bin/env python3
"""Stage Cloudflare Bulk Redirects for Vietnamese đ→d slug migration (#77).

This tool ONLY writes a CSV to an explicitly named output path; it NEVER
changes a published permalink, deploys a redirect, edits DNS or QA evidence.

Cloudflare dashboard CSV format (no header):
SOURCE_URL,TARGET_URL,301,TRUE,FALSE,FALSE,FALSE

WARNING: Do NOT activate any redirect until its NEW destination is HTTP 200
and the old route can return HTTP 301/308 on the real production hostname.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "reports/factory/seo-master/slug-d-migration-map.csv"
DOMAIN = "blog.thuexemaynguyentu.com"
ORIGIN = "https://" + DOMAIN


def manifest_rows(source: Path) -> list[dict]:
    with source.open(encoding="utf-8", newline="") as stream:
        rows = csv.DictReader(stream)
        required = {"article_id", "old_url", "new_url", "collision_flags",
                    "old_output_path", "migration_ready"}
        if not required.issubset(rows.fieldnames or []):
            raise ValueError("migration map missing mandatory columns")
        return list(rows)


def validate(rows: list[dict], site: Path | None = ROOT) -> None:
    if not rows:
        raise ValueError("empty migration map")
    old_seen = set()
    new_seen = set()
    for i, row in enumerate(rows, start=1):
        aid, old, new = row["article_id"], row["old_url"], row["new_url"]
        if not re.fullmatch(r"BLG-\d{5}", aid):
            raise ValueError("invalid article ID in row %s: %s" % (i, aid))
        if not all(p.startswith("/") and p.endswith("/")
                   and urlsplit(p).query == "" and urlsplit(p).fragment == ""
                   and re.fullmatch(r"/[a-z0-9/-]+/", p)
                   for p in (old, new)):
            raise ValueError("invalid local OLD/NEW path: %s" % aid)
        if old == new or old in old_seen or new in new_seen:
            raise ValueError("duplicate/colliding old/new path: %s" % aid)
        if row["collision_flags"].strip():
            raise ValueError("collision flag present, STOP: %s" % aid)
        if row["migration_ready"].upper() != "NO":
            raise ValueError("unexpected migration_ready: %s" % aid)
        if site:
            rel = Path(row["old_output_path"])
            if rel.is_absolute() or ".." in rel.parts or rel.parts[0] != "_posts":
                raise ValueError("unexpected post path: %s" % aid)
            post = site / rel
            if not post.is_file():
                raise ValueError("missing published source: %s" % post)
            text = post.read_text(encoding="utf-8")[:4000]
            if not re.search(r"(?m)^permalink:\s*['\"]?" + re.escape(old) + r"['\"]?\s*$", text):
                raise ValueError("published permalink no longer matches manifest: %s" % aid)
        old_seen.add(old)
        new_seen.add(new)


def write_dashboard_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        for row in rows:
            # Source without scheme matches http AND https on Cloudflare.
            # Preserve query string = TRUE. All wildcard parameters = FALSE.
            writer.writerow((DOMAIN + row["old_url"], ORIGIN + row["new_url"],
                             301, "TRUE", "FALSE", "FALSE", "FALSE"))


def selftest() -> int:
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix="slug-d-cf-") as d:
        root = Path(d)
        (root / "_posts").mkdir()
        post = root / "_posts" / "2026-10-01-oi-xe.md"
        post.write_text("---\npermalink: /xe-may/2026/10/01/oi-xe/\n---\n", encoding="utf-8")
        row = {"article_id": "BLG-02000", "old_url": "/xe-may/2026/10/01/oi-xe/",
               "new_url": "/xe-may/2026/10/01/doi-xe/",
               "collision_flags": "", "migration_ready": "NO",
               "old_output_path": "_posts/2026-10-01-oi-xe.md"}
        validate([row], root)
        dest = root / "output.csv"
        write_dashboard_csv([row], dest)
        lines = list(csv.reader(io.StringIO(dest.read_text(encoding="utf-8"))))
        assert lines == [[DOMAIN + row["old_url"], ORIGIN + row["new_url"],
                          "301", "TRUE", "FALSE", "FALSE", "FALSE"]], lines
        for invalid in ([row, row], [{**row, "new_url": row["old_url"]}],
                        [{**row, "collision_flags": "NEW_URL_EXISTS"}]):
            try:
                validate(invalid, root)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid map not rejected")
    print("PASS: Cloudflare seven-field CSV, duplicate/collision guards and URL integrity")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, help="explicit staging CSV destination")
    parser.add_argument("--start", type=int, default=0,
                        help="0-based first row in stable migration map")
    parser.add_argument("--limit", type=int, default=0,
                        help="0 = all remaining; else batch size, recommended <= 50")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.start < 0 or args.limit < 0:
        parser.error("--start and --limit must be non-negative")
    if not args.validate_only and not args.out:
        parser.error("--out required unless --validate-only or --selftest")
    rows = manifest_rows(args.source)
    try:
        validate(rows, ROOT if args.source.resolve() == SOURCE.resolve() else None)
    except ValueError as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2
    selected = rows[args.start:(args.start + args.limit if args.limit else None)]
    if not selected:
        print("BLOCKED: empty chosen batch", file=sys.stderr)
        return 2
    summary = {"validated_manifest_urls": len(rows),
               "staged_redirects": len(selected), "start": args.start,
               "first_article_id": selected[0]["article_id"],
               "last_article_id": selected[-1]["article_id"],
               "HTTP_status": 301, "preserve_query_string": True,
               "production_redirects_activated": False,
               "DO_NOT_ENABLE_UNTIL_NEW_HTTP_200": True}
    if args.out and not args.validate_only:
        if args.out.exists():
            print("BLOCKED: output already exists: " + str(args.out), file=sys.stderr)
            return 2
        write_dashboard_csv(selected, args.out)
        summary["file"] = str(args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
