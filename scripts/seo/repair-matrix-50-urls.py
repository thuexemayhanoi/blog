#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Correct the 50 wrong PUBLISHED Matrix URLs without changing any published page.

Only confirmed BLG-00820..BLG-00869, whose real _posts permalink is already
live. Re-scores every affected article using the canonical factory QA engine;
no caller-supplied PASS, SHA, score or proof is trusted. Does NOT create 301
redirects, publish posts, edit SEO URL on the site, or resume the writer.

Usage (repo root, clean checkout):
 python3 scripts/seo/repair-matrix-50-urls.py --dry-run
 python3 scripts/seo/repair-matrix-50-urls.py --apply --approval-ref ISSUE-77
 python3 scripts/seo/repair-matrix-50-urls.py --rollback --backup <json file>
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MATRIX = Path("data/content-matrix.csv")
MAP = Path("reports/factory/seo-master/matrix-50-404-to-live-200-20261024.csv")
FP_FIELDS = ("title", "intent", "primary_keyword", "expected_url",
             "output_path", "canonical_url")
FLOOR_QUALITY, FLOOR_SEO = 75, 70
EXPECTED_IDS = {"BLG-%05d" % i for i in range(820, 870)}
BACKUP_DIR = Path("reports/qa-audit/matrix-url-fix")


def fail(message: str):
    raise ValueError(message)


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(row: dict) -> str:
    return hash_bytes(json.dumps({k: row[k] for k in FP_FIELDS},
                                 ensure_ascii=False, sort_keys=True).encode("utf-8"))


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, text=True,
                       capture_output=True)
    return p.stdout.strip() if p.returncode == 0 else None


def load_module(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict]:
    with (ROOT / path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def matrix_serialization(rows: list[dict], header: list[str]) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def snapshot_state() -> dict:
    control = json.loads((ROOT / "data/factory/production-control.json").read_text())
    if control.get("enabled") is not False:
        fail("FACTORY_NOT_PAUSED: refuse published-matrix maintenance")

    # Keep writes separate from an active publisher transaction/lease.
    transaction = json.loads((ROOT / "data/state/transaction.json").read_text())
    if transaction.get("active"):
        fail("ACTIVE_PUBLISH_TRANSACTION: must recover/finish first")
    writer = json.loads((ROOT / "data/state/writer-claims.json").read_text())
    active = writer.get("leases") or {}
    if active:
        fail("ACTIVE_WRITER_LEASE: refuse racing with writers")
    return {"control": control, "txn_active": False, "leases": 0}


def prepare():
    state = snapshot_state()
    mapped = read_csv(MAP)
    if len(mapped) != 50 or {r["article_id"] for r in mapped} != EXPECTED_IDS:
        fail("UNEXPECTED_MIGRATION_SCOPE: map must contain EXACT 50 BLG-00820..869")

    original_bytes = (ROOT / MATRIX).read_bytes()
    with (ROOT / MATRIX).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        header = list(reader.fieldnames)
        rows = list(reader)
    by_id = {r["id"]: r for r in rows}
    if len(by_id) != len(rows):
        fail("MATRIX_DUPLICATE_ID")
    all_routes = set()
    for r in rows:
        if r["status"] in ("PUBLISHED", "EXISTING", "REVIEW"):
            all_routes.add(r["expected_url"])

    originals = {}
    affected = []
    for m in mapped:
        aid = m["article_id"]
        row = by_id[aid]
        wrong, right = m["matrix_404_url"], m["actual_200_url"]
        if (row["status"] != "PUBLISHED"
                or row["expected_url"] != wrong
                or row["canonical_url"] != wrong
                or row["output_path"] != m["post_file"]):
            fail("MATRIX_DRIFT: " + aid)
        if right in all_routes:
            fail("LIVE_TARGET_ALREADY_IN_MATRIX: " + aid)
        if not (wrong.startswith("/") and right.startswith("/")
                and wrong.endswith("/") and right.endswith("/")):
            fail("INVALID_ROUTE: " + aid)
        post_rel = Path(row["output_path"])
        if post_rel.is_absolute() or ".." in post_rel.parts or post_rel.parts[0] != "_posts":
            fail("UNSAFE_POST_PATH: " + aid)
        post_bytes = (ROOT / post_rel).read_bytes()
        post = post_bytes.decode("utf-8")
        found = re.search(r"(?m)^permalink:\s*['\"]?([^'\"\s]+)['\"]?\s*$", post[:5000])
        if not found or found.group(1) != right:
            fail("REAL_POST_PERMALINK_MISMATCH: " + aid)
        evidence_path = Path("data/qa") / (aid + ".json")
        old_ev_bytes = (ROOT / evidence_path).read_bytes()
        old_ev = json.loads(old_ev_bytes)
        if (old_ev.get("article_id") != aid or old_ev.get("source_path") != str(post_rel)
                or old_ev.get("result") != "PASS"
                or old_ev.get("quality", 0) < FLOOR_QUALITY
                or old_ev.get("seo", 0) < FLOOR_SEO):
            fail("OLD_EVIDENCE_NOT_PUBLISHED_PASS: " + aid)
        originals[aid] = {
            "evidence_path": str(evidence_path),
            "old_evidence": base64.b64encode(old_ev_bytes).decode("ascii"),
            "old_evidence_sha256": hash_bytes(old_ev_bytes),
            "old_post_sha256": hash_bytes(post_bytes),
            "old_matrix_fp": fingerprint(row),
            "old_url": wrong, "new_url": right,
            "old_content_sha_match": old_ev.get("content_sha256") == hash_bytes(post_bytes),
            "old_matrix_sha_match": old_ev.get("matrix_row_sha256") == fingerprint(row),
        }
        row["expected_url"] = right
        row["canonical_url"] = right
        affected.append(aid)

    # Run the repository's exact canonical scorer from current source. It must
    # independently recalculate the QA score and binding on the changed rows.
    op = load_module("matrix50_factory_qa", "scripts/factory/factory-operator.py")
    audit = load_module("matrix50_canonical_audit", "scripts/factory/audit-legacy-qa.py")
    if op.QUALITY_MIN < FLOOR_QUALITY or op.SEO_MIN < FLOOR_SEO:
        fail("QA_THRESHOLD_LOWER_THAN_FLOOR")
    biz = json.loads((ROOT / "data/business-facts.json").read_text())
    tax = json.loads((ROOT / "data/content-taxonomy.json").read_text())
    op.build_amount_whitelist(biz)
    scores = {}
    for aid in affected:
        row = by_id[aid]
        fresh = audit.rescore_published(op, row, rows, biz, tax)
        post_sha = hash_bytes((ROOT / row["output_path"]).read_bytes())
        if (fresh.get("article_id") != aid
                or fresh.get("content_sha256") != post_sha
                or fresh.get("matrix_row_sha256") != fingerprint(row)
                or fresh.get("source_path") != row["output_path"]):
            fail("FRESH_QA_HASH_NOT_BOUND: " + aid)
        if (fresh.get("result") != "PASS"
                or fresh.get("quality", 0) < FLOOR_QUALITY
                or fresh.get("seo", 0) < FLOOR_SEO
                or fresh.get("business_fact") != "PASS"
                or fresh.get("legal") not in ("PASS", "NOT_REQUIRED")
                or fresh.get("critical_failure") is not False):
            failed = [key for key, passed in fresh.get("checks", {}).items() if not passed]
            fail("CANONICAL_QA_FAILED: %s, checks=%s, score=%s/%s"
                 % (aid, failed, fresh.get("quality"), fresh.get("seo")))
        old = json.loads(base64.b64decode(originals[aid]["old_evidence"]))
        for key in ("scored_at", "published_at"):
            if key in old:
                fresh[key] = old[key]  # avoid synthetic activity timestamps
        for key in ("revision", "reattestation"):
            if key in old:
                fresh[key] = old[key]  # preserve historical provenance
        fresh["matrix_url_repair"] = {
            "schema": "matrix-url-repair/1", "approval_ref": "ISSUE-77",
            "reason": "Align stored Matrix route with unchanged, HTTP 200 _posts permalink",
            "old_url": originals[aid]["old_url"], "new_url": originals[aid]["new_url"],
            "old_evidence_sha256": originals[aid]["old_evidence_sha256"],
            "old_matrix_fp": originals[aid]["old_matrix_fp"],
            "original_content_sha_match": originals[aid]["old_content_sha_match"],
            "original_matrix_sha_match": originals[aid]["old_matrix_sha_match"],
            "independently_rescored": True,
            "scorer_sha256": hash_bytes((ROOT / "scripts/factory/factory-operator.py").read_bytes()),
            "business_facts_sha256": hash_bytes((ROOT / "data/business-facts.json").read_bytes()),
            "taxonomy_sha256": hash_bytes((ROOT / "data/content-taxonomy.json").read_bytes()),
        }
        scores[aid] = json.dumps(fresh, ensure_ascii=False, indent=2).encode("utf-8")

    new_matrix = matrix_serialization(rows, header)
    if new_matrix == original_bytes:
        fail("NO_MATRIX_CHANGE")
    return state, original_bytes, new_matrix, originals, scores, rows


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".url-repair-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def apply(approval_ref: str) -> int:
    if approval_ref != "ISSUE-77":
        fail("EXPLICIT_APPROVAL_REF_REQUIRED: pass --approval-ref ISSUE-77")
    if git("status", "--porcelain", "--", str(MATRIX), "data/qa",
           "data/factory/production-control.json"):
        fail("DIRTY_INPUT_TREE: commit or discard unrelated source changes first")
    state, old_matrix, new_matrix, old_evs, new_evs, _ = prepare()
    before = {
        "matrix": base64.b64encode(old_matrix).decode("ascii"),
        "new_matrix_sha256": hash_bytes(new_matrix),
        "original_matrix_sha256": hash_bytes(old_matrix),
        "old_qa": old_evs,
        "new_qa_sha256": {aid: hash_bytes(b) for aid, b in new_evs.items()},
        "approval_ref": approval_ref,
        "head": git("rev-parse", "HEAD"),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "state": state,
    }
    backup = ROOT / BACKUP_DIR / ("matrix-50-" + before["original_matrix_sha256"][:16] + ".json")
    if backup.exists():
        fail("BACKUP_EXISTS: " + str(backup))
    atomic_write(backup, (json.dumps(before, ensure_ascii=False, indent=2) + "\n").encode())
    touched = []
    try:
        atomic_write(ROOT / MATRIX, new_matrix)
        touched.append((ROOT / MATRIX, old_matrix))
        for aid, ev in new_evs.items():
            p = ROOT / old_evs[aid]["evidence_path"]
            old = base64.b64decode(old_evs[aid]["old_evidence"])
            if hash_bytes(p.read_bytes()) != old_evs[aid]["old_evidence_sha256"]:
                fail("QA_RACED_WITH_OTHER_EDITOR: " + aid)
            atomic_write(p, ev)
            touched.append((p, old))
        for aid, content in new_evs.items():
            path = ROOT / old_evs[aid]["evidence_path"]
            if path.read_bytes() != content:
                fail("POSTWRITE_QA_MISMATCH: " + aid)
        if (ROOT / MATRIX).read_bytes() != new_matrix:
            fail("POSTWRITE_MATRIX_MISMATCH")
    except BaseException:
        for p, previous in reversed(touched):
            atomic_write(p, previous)
        raise
    print(json.dumps({"result": "APPLIED", "changed_matrix_rows": len(new_evs),
                      "changed_post_files": 0, "qa_independently_rescored": len(new_evs),
                      "backup": str(backup.relative_to(ROOT)),
                      "post_publish_redirects_changed": 0}, ensure_ascii=False, indent=2))
    return 0


def rollback(backup_path: Path) -> int:
    b = json.loads(backup_path.read_text(encoding="utf-8"))
    if b["approval_ref"] != "ISSUE-77" or set(b["old_qa"]) != EXPECTED_IDS:
        fail("INVALID_BACKUP")
    if hash_bytes((ROOT / MATRIX).read_bytes()) != b["new_matrix_sha256"]:
        fail("ROLLBACK_MATRIX_HAS_NEW_CHANGES: manual reconciliation required")
    for aid, old in b["old_qa"].items():
        if hash_bytes((ROOT / old["evidence_path"]).read_bytes()) != b["new_qa_sha256"][aid]:
            fail("ROLLBACK_QA_HAS_NEW_CHANGES: " + aid)
    atomic_write(ROOT / MATRIX, base64.b64decode(b["matrix"]))
    for old in b["old_qa"].values():
        atomic_write(ROOT / old["evidence_path"], base64.b64decode(old["old_evidence"]))
    print("ROLLBACK OK: original Matrix + exact original 50 QA bytes restored")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--dry-run", action="store_true")
    actions.add_argument("--apply", action="store_true")
    actions.add_argument("--rollback", action="store_true")
    parser.add_argument("--approval-ref", default="")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    try:
        if args.rollback:
            if not args.backup:
                parser.error("--rollback requires --backup")
            return rollback(args.backup)
        if args.apply:
            return apply(args.approval_ref)
        _, current, candidate, historical, scores, _ = prepare()
        print(json.dumps({
            "result": "DRY_RUN_PASS",
            "verified_live_mapping": "50 URL pairs (see HTTP evidence in Issue #77)",
            "old_matrix_sha256": hash_bytes(current),
            "new_matrix_sha256": hash_bytes(candidate),
            "qa_rescored_pass": len(scores),
            "posts_edited": 0,
            "historical_qa_sha_drift": sum(
                not x["old_content_sha_match"] or not x["old_matrix_sha_match"]
                for x in historical.values()),
            "operator_action_required": "--apply --approval-ref ISSUE-77",
        }, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
