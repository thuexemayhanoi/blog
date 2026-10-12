# Legacy QA evidence — read-only audit + controlled re-attestation

Scope: **thuexemayhanoi/blog**, production main, https://blog.thuexemaynguyentu.com/.
Snapshot: `eb2afa24a46caa102a4b3045704b62ca15fd1841`; pre-migration baseline:
`1b55bd810aac85dc919eb2a43d71de30ad8d4595` (parent of `04d46bef`).
No published content, matrix, checkpoint, lease or QA evidence is rewritten by the audit itself;
evidence is only ever replaced through the re-attestation tool described below.

## Provenance findings

1918 PUBLISHED rows: **1069** have at least one hash mismatch; **1066** content
hash mismatches, **1067** matrix fingerprint mismatches, **2133** validator errors.
849 rows match both hashes. These counts are the snapshot, not a live counter.

1063 rows are `DOMAIN_ONLY_PROVEN`: immutable pre-migration post bytes AND
the six-field matrix fingerprint match their recorded QA hashes; applying
the exact migration v3 transform yields the current bytes/fingerprint fields.
No whitespace removal, fuzzy text match, or hash replacement is used.
The transform replaces `https://thuexemayhanoi.github.io/blog` with the custom
domain and repeatedly removes bounded root-relative `/blog/` prefixes.

Six exceptions must stay out of a blanket migration attestation:

| ID | Evidence found in git history | Required handling |
|---|---|---|
| BLG-01279 | `45342291` changed parent_id after publication, before migration; baseline content already differs from QA | Review taxonomy correction and rescore exact current bytes |
| BLG-01478 | Recorded QA hash binds draft at `7e3cf0b6`; extra paragraphs/line changes reached `_posts/` in `e4516bfa` | Real content change; review independently |
| BLG-01479 | Recorded QA hash binds draft at `7e3cf0b6`; added FAQ/line changes reached `_posts/` in `e4516bfa` | Real content change; review independently |
| BLG-01494 | `9ca552bd` changed an accent after publication, before migration | Real text change; review independently even if small |
| BLG-01722 | `ee38654a` removed a stray fragment after publication, after migration | Real content change; review independently |
| BLG-01741 | `2c162d7b` removed an editing artifact after publication, after migration | Real content change; review independently |

The 01478/01479 publication mismatch predates PR #7. Its current regression
guards are `publisher-push.py` overlap/hash checks and multiwriter simulations;
do not edit these old posts during this technical work.

## Reproduce without modifying evidence

```bash
python3 scripts/factory/audit-legacy-qa.py --baseline 1b55bd810aac85dc919eb2a43d71de30ad8d4595
# Optional: independent read-only score of current published bytes:
python3 scripts/factory/audit-legacy-qa.py --baseline 1b55bd810aac85dc919eb2a43d71de30ad8d4595 --rescore-stale
python3 scripts/factory/validate.py --scope full
```

The audit emits JSON to stdout only. It cannot promote, write QA, or set PASS. Run it on a clean
checkout of the commit you cite: it reads the matrix, posts, QA evidence, scorer, business facts and
taxonomy from the working tree, so it refuses a tree that differs from `HEAD` (`DIRTY_TREE`;
`--allow-dirty` is the explicit opt-out and marks the output `head_bound: false`). "Differs" means any
tracked change plus untracked files the scorer can read: anything under `data/`, `scripts/`, `_posts/`, and
any `.md`/`.html` page outside the directories `canonical_routes()` skips (it reads every page's `permalink:`);
a writer's untracked `_drafts/` entry or an `> audit.json` redirect does not trip it.
`--rescore-stale` calls `factory-operator.py qa_check_one` on each actual post,
using the actual current corpus, taxonomy, business facts and unchanged 75/70
thresholds. It does not call `op_qa`, publish, prepare-next or recovery.
Fresh QA failures remain failures, even when the historical diff is domain-only.

Read-only rescore on this snapshot (canonical scorer WITH the approved-amount
whitelist initialised, exactly like `factory-operator.main` and `writer-loop`):
**1060** of the 1063 domain-only cases are eligible proposals awaiting approval;
**3** fail current canonical QA (BLG-00484, BLG-00485, BLG-00493: quality 75, seo 65;
failed checks `description_keyword`, `headings_intent`, `intent_opening`,
`links_count`, `links_matrix_required`, `links_parent_hub`, `word_count`).
The six exceptions stay manual review (they now also score PASS on the current
scorer, but their evidence was never bound to the published bytes). No old
evidence was replaced and no production row was marked REPAIR by this analysis.

**Correction (Codex P1 on PR #9, reproduced):** the first version of this audit
did not call `build_amount_whitelist`, so every money amount looked unapproved
(`APPROVED_AMOUNTS` was empty) and 87 domain-only articles that quote approved
prices (150.000 / 200.000 / ...) were reported as failing `business_amounts`; the
earlier 976 / 87 counts were wrong and are superseded by the numbers above.
`RealScorerTest.test_rescore_uses_the_approved_amount_whitelist` guards the
regression (approved price passes, an unapproved amount still fails).
`rescore_published` also pins the process cwd to the scorer's own repo root for
the call (and restores it): `qa_check_one` opens the post by its repo-relative
path, and the CLI only worked from other directories because importing the
operator happens to `chdir` (`test_rescore_does_not_depend_on_the_callers_working_directory`).

**Independent cross-check (2026-10-12, separate analysis with its own code that
does not import this tool):** 1063 DOMAIN_ONLY / 6 other / 849 matching at the
snapshot, identical ids; the migration rule was re-derived from
`scripts/migrate-custom-domain.py` at `1b55bd81` (`MIGRATION_VERSION = 3`) and
reproduces `04d46bef` byte-for-byte on all in-scope files. Caveat it found:
33 DOMAIN_ONLY articles (BLG-00484..00497, parts of 00605..00614, 00629..00634,
00727, 00730, 00731, 01098, 01138) had a documented hash-only re-stamp before the
baseline (same `scored_at`, new `content_sha256`), so their OLD scores are weaker
provenance. That is why a re-attestation must never reuse old scores: it only
accepts a FRESH independent scoring of the exact current bytes.

## Re-attestation procedure — `scripts/factory/reattest-legacy-qa.py`

Owner authorization: the project owner authorized (chat, 2026-10-12, "ỦY QUYỀN TOÀN DIỆN",
item 9) preparing the re-attestation **only** for evidence that is proven valid, with
independent scoring, full provenance, backups, tests and rollback. The owner's later MASTER
instruction (2026-10-12, section 9) forbids re-attesting old evidence outside a procedure that
has been approved AND accepted: **nothing is applied to production evidence until the owner has
accepted this procedure** (acceptance package: the tool, its tests, an independent review, a
rehearsal on a disposable worktree and a read-only dry run on the real tree). The accepted
reference is then passed as `--approval-ref`; the tool refuses to write without one.

```bash
# 0. start from a clean checkout of the commit you will cite (plan/apply refuse a tree that differs from HEAD)
# 1. proposal (read-only, several minutes of CPU): manifest of every stale row with its binding facts
python3 scripts/factory/reattest-legacy-qa.py plan --baseline 1b55bd810aac85dc919eb2a43d71de30ad8d4595 --out plan.json
# 2. bounded batch on a branch (<= 300 IDs); everything is re-verified at apply time
python3 scripts/factory/reattest-legacy-qa.py apply --manifest plan.json --approval-ref "<owner approval>" --limit 10 --dry-run
python3 scripts/factory/reattest-legacy-qa.py apply --manifest plan.json --approval-ref "<owner approval>" --limit 10 --batch-id <id>
# 3. check and, if anything is wrong, undo byte-exactly
python3 scripts/factory/reattest-legacy-qa.py verify   --backup reports/qa-audit/reattest/<id>.json
python3 scripts/factory/reattest-legacy-qa.py rollback --backup reports/qa-audit/reattest/<id>.json [--ids A,B] [--dry-run]
```

What it guarantees (covered by `scripts/factory/tests/test_reattest_legacy_qa.py`):

1. **Provenance, not labels.** An ID qualifies only when the old evidence hashes bind the
   immutable baseline bytes AND matrix row, and the exact migration-v3 transform of those bytes
   reproduces the current bytes/row fields (no whitespace stripping, no fuzzy match). The
   baseline is **pinned** in the tool (`1b55bd81…`, the parent of the migration commit) and must
   be an ancestor of `HEAD` (`BASELINE_NOT_PINNED`, `BASELINE_NOT_ANCESTOR`).
2. **Independent scoring.** The canonical scorer (`qa_check_one`, current corpus/taxonomy/
   business facts, the approved-amount whitelist) re-scores the current bytes. Old scores/results
   are never reused; any failing gate (quality, seo, business_fact, legal, critical failure) means
   the ID is refused — there is no force flag. The **75/70 floors are hard-coded in the tool**:
   a scorer whose constants are lower is refused (`THRESHOLD_BELOW_FLOOR`), so lowering the
   repository's own thresholds cannot make a failing article eligible.
3. **The manifest is not authority.** `apply` re-derives everything from git and the current
   bytes; a stale, edited or forged manifest can only make `apply` refuse. The manifest must have
   been made for the same baseline, scorer, business-facts, taxonomy and thresholds
   (`SCORER_CHANGED_SINCE_PLAN`: re-plan). One failing ID stops the whole batch before anything is
   written (atomic); `--skip-ineligible` only skips IDs whose *state changed since the plan* and
   reports them. IDs, batch ids and `output_path` are validated (`BAD_ID`, `BAD_BATCH_ID`,
   `BAD_OUTPUT_PATH`).
4. **Backup before write, and an honest failure path.** `reports/qa-audit/reattest/<batch>.json`
   (verbatim old evidence plus old/new sha256 of every ID) is written and read back before the
   first evidence file changes. Each evidence file is compare-and-swapped (it must still equal the
   bytes that were checked). If `apply` fails midway, every ID the run had started to write is
   restored; the backup is deleted only when all of them are back to the old bytes, otherwise it
   is kept (`PARTIAL_APPLY_BACKUP_KEPT`) so `rollback --backup` can finish the job.
5. **Minimal footprint.** Only the approved `data/qa/<ID>.json` files and the backup are
   written; `_posts/`, matrix, checkpoint, leases and drafts are never touched. The new evidence
   carries a `reattestation` block (old evidence hash, baseline proof, scorer/business-facts/
   taxonomy hashes, approval, `rescored_at`); `scored_at`/`published_at` keep their historical
   values so the production watchdog (which reads them as progress signals) sees no fake activity
   — evidence without a historical `scored_at` is refused (`NO_HISTORICAL_SCORED_AT`). Notes the
   scorer never produces (`post_publish_repair`, `hash_sync_note`, `rescore_note`,
   `restamped_note`: 25 of the 1,060 eligible files, the ones re-stamped or repaired after
   publication) are copied verbatim into `reattestation.previous_evidence_annotations`.
6. **Rollback.** `rollback` restores the old evidence byte-exactly, and only if the file still
   equals the bytes the tool wrote; `--ids` must name IDs of the backup (`UNKNOWN_IDS`). Re-running
   `apply` on already-current evidence is a no-op — but only when the evidence on disk still equals
   a fresh independent score (a hand-edited score with intact hashes is refused as
   `UNEXPECTED_CURRENT_EVIDENCE`, not treated as done).
7. **Clean tree, bound manifest.** A score is only attributable to a commit when the matrix,
   posts, evidence, scorer, business facts and taxonomy are that commit's. `plan` and `apply`
   (dry runs included) refuse a working tree that differs from `HEAD` (`DIRTY_TREE`, same check as
   `audit-legacy-qa.py`); `plan --allow-dirty` is the explicit opt-out and marks the manifest
   `head_bound: false`, which `apply` refuses (`MANIFEST_NOT_HEAD_BOUND`, as it does for manifests
   that predate the field). "Differs" includes files hidden from `git status` by
   `skip-worktree` / `assume-unchanged` flags, and `apply` re-checks the tree right before it writes.
   A successful `apply` leaves the tree dirty on purpose: commit the batch (evidence + backup)
   before the next one; `verify` and `rollback` are never guarded.
8. **`verify` is an independent re-derivation, not a self-check.** Besides hashes, provenance and
   the gates it re-scores every ID and compares the whole evidence (everything except the
   provenance stamps) with the scorer's output, so a score edited together with its backup entry
   is caught (`--no-rescore` keeps only the structural checks). CI wiring: a push/PR that touches
   `data/qa/**` or `reports/qa-audit/**` now triggers the quality gate (FULL: the backup is outside
   the content contract) and verifies every backup file added or changed by the change.

The three genuine failures (BLG-00484/00485/00493) and the six real-change cases are never
re-attested by this tool; they stay for separate handling (content repair or explicit review).

## Negative tests and limits

`test_legacy_qa_audit.py` checks changed prose/whitespace, changed intent,
forged old hashes, borrowed fresh hashes/IDs, below-threshold scores,
business/legal failures, critical failure and no mutations. A real-scorer
fixture supplies forged PASS/100 labels with matching old hashes but an
unapproved amount: independent current QA returns FAIL and the proposal is
rejected. `test_publish_gate` already rejects stale content and changed rows.

Hashes establish integrity/provenance, not cryptographic authorship. Someone
with privileged access to change code and all evidence cannot be stopped by
an unsigned JSON field. The future write path therefore needs owner-approved
manifests, CI review and immutable history; no blanket security claim is made.

`validate --scope full` stays FAIL for every row that is not yet re-attested (2 errors per
ID: content hash and matrix fingerprint); it drops by exactly 2 per re-attested ID. The nine
rows above (3 genuine failures + 6 real changes) remain failing by design until handled
separately. A green FULL build-mode quality gate (which validates scope chunk) proves the
current build/links and engine checks, not all historical evidence hashes.
