#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DIAGNOSE v4 read-only: simulate post-promote state of
BLG-00635..00644 locally, then run the exact follow-up steps of
op publish + verify. Runner-local mutations only; evidence file
is the only committed artifact. Delete after use."""

import csv
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

IDS = ["BLG-%05d" % n for n in range(635, 645)]
MATRIX = "data/content-matrix.csv"
QA_DIR = "data/qa"
CP = "data/state/checkpoint.json"
PY = sys.executable

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("$ " + " ".join(cmd) + " -> exit %d" % r.returncode)
    print(r.stdout[-3000:])
    if r.stderr:
        print("STDERR: " + r.stderr[-3000:])
    return r.returncode

def now_iso():
    d = datetime.datetime.now(datetime.timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%S+00:00")

def fp_of(r):
    basis = {k: r[k] for k in ("title", "intent",
                               "primary_keyword",
                               "expected_url", "output_path",
                               "canonical_url")}
    s = json.dumps(basis, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

with open(MATRIX, encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))
by_id = {r["id"]: r for r in rows}

pat = re.compile("_posts/\\d{4}-\\d{2}-\\d{2}-(.+)\\.md$")

for aid in IDS:
    row = by_id[aid]
    s = row["output_path"]
    if s.startswith("_posts/{date}-"):
        slug = s[len("_posts/{date}-"):-3]
    else:
        slug = pat.match(s).group(1)
    draft = sorted(glob.glob("_drafts/*-%s.md" % slug))[0]
    m = re.match("(\\d{4}-\\d{2}-\\d{2})-",
                 os.path.basename(draft))
    date_part = m.group(1)
    dest = "_posts/%s-%s.md" % (date_part, slug)
    print("SIM %s: %s -> %s" % (aid, draft, dest))
    shutil.move(draft, dest)
    row["status"] = "PUBLISHED"
 
   row["output_path"] = dest
    rep = "%s/%s/%s" % (date_part[:4], date_part[5:7],
                        date_part[8:])
    row["expected_url"] = row["expected_url"].replace(
        "{date}", rep)
    row["canonical_url"] = row["expected_url"]
    qap = os.path.join(QA_DIR, aid + ".json")
    if os.path.exists(qap):
        qev = json.load(open(qap, encoding="utf-8"))
        qev["source_path"] = dest
        qev["matrix_row_sha256"] = fp_of(row)
        qev["published_at"] = now_iso()
        fh = open(qap, "w", encoding="utf-8")
        json.dump(qev, fh, ensure_ascii=False, indent=2)
        fh.close()

fields = list(rows[0].keys())
with open(MATRIX, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields,
                       lineterminator="\n")
    w.writeheader()
    w.writerows(rows)

cp = json.load(open(CP, encoding="utf-8"))
left = [r["id"] for r in rows if r["status"] == "PLANNED"]
cp["last_completed_article_id"] = IDS[-1]
cp["next_claimable_id"] = left[0] if left else None
cp["updated_at"] = now_iso()
cp["last_run_id"] = "publish-gate-" + IDS[-1]
cp["in_progress_chunk"] = None
cnt = cp.setdefault("counts", {})
for st in ("planned", "writing", "qa", "pass",
            "published", "repair", "blocked", "fail"):
    cnt[st] = sum(1 for r in rows
                  if r["status"] == st.upper())
fh = open(CP, "w", encoding="utf-8")
json.dump(cp, fh, ensure_ascii=False, indent=2)
fh.close()

print()
print("=== POST-PROMOTE CHECKS (op publish + verify order) ===")
rc = run([PY, "scripts/factory/generate-reports.py"])
print("generate-reports exit=%d" % rc)
rc = run([PY, "scripts/factory/validate.py",
          "--scope", "chunk"])
print("validate chunk exit=%d" % rc)
rc = run([PY, "scripts/factory/capacity-audit.py"])
print("capacity-audit exit=%d" % rc)
rc = run([PY, "scripts/factory/generate-listing-pages.py"])
print("listing exit=%d" % rc)
rc = run([PY, "scripts/factory/queue.py", "--stats"])
print("queue stats exit=%d" % rc)
for t in sorted(glob.glob(
        "scripts/factory/tests/test_*.py")):
    rc = run([PY
, t])
    print("%s exit=%d" % (t, rc))
print()
print("DIAGNOSE V4 DONE")
