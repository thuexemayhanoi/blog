#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Danh sách bài vừa PUBLISHED theo QA published_at; không sửa ngày/URL bài cũ."""
import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT = os.path.join(ROOT, "_data", "recent_published.json")
HCM = dt.timezone(dt.timedelta(hours=7))
ID_RE = re.compile(r"BLG-\d{5}")


def generate():
    with open(os.path.join(ROOT, "data/content-matrix.csv"), encoding="utf-8", newline="") as f:
        published = {row["id"]: row for row in csv.DictReader(f)
                     if row.get("status") == "PUBLISHED"}
    found = []
    for qa_path in glob.glob(os.path.join(ROOT, "data/qa/BLG-*.json")):
        aid = os.path.splitext(os.path.basename(qa_path))[0]
        if not ID_RE.fullmatch(aid) or aid not in published:
            continue
        try:
            with open(qa_path, encoding="utf-8") as f:
                ev = json.load(f)
            stamp = ev.get("published_at")
            if not isinstance(stamp, str):
                continue
            when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if when.tzinfo is None:
                continue
            rel = published[aid].get("output_path", "")
            if not re.fullmatch(r"_posts/[a-zA-Z0-9_-]+\.md", rel):
                continue
            post_path = os.path.join(ROOT, rel)
            if not os.path.isfile(post_path) or ev.get("source_path") != rel:
                continue
            with open(post_path, encoding="utf-8") as f:
                front = f.read(2500).split("---", 2)
            if len(front) < 3 or not re.search(
                r"^article_id:\s*" + re.escape(aid) + r"\s*$", front[1], re.M
            ) or not re.search(r"^lang:\s*vi\s*$", front[1], re.M):
                continue
            found.append((when, aid))
        except (OSError, ValueError, TypeError, KeyError):
            continue
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return {"articles": [
        {"id": aid, "published_at": when.astimezone(HCM).isoformat(timespec="seconds")}
        for when, aid in found[:12]
    ]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    content = json.dumps(generate(), ensure_ascii=False, indent=2) + "\n"
    existing = ""
    if os.path.isfile(OUTPUT):
        with open(OUTPUT, encoding="utf-8") as f:
            existing = f.read()
    if args.check:
        if existing != content:
            print("FAIL: danh sách bài đăng mới không đồng bộ", file=sys.stderr)
            return 1
        print("PASS: recent published index")
        return 0
    if existing != content:
        os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
        with open(OUTPUT, "w", encoding="utf-8") as f:
            f.write(content)
    print("Latest published entries: %d" % len(json.loads(content)["articles"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
