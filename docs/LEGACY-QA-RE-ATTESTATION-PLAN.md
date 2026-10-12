# Legacy QA evidence — audit-only, approval required

Scope: **thuexemayhanoi/blog**, production main, https://blog.thuexemaynguyentu.com/.
Snapshot: `eb2afa24a46caa102a4b3045704b62ca15fd1841`; pre-migration baseline:
`1b55bd810aac85dc919eb2a43d71de30ad8d4595` (parent of `04d46bef`).
No published content, matrix, checkpoint, lease or QA evidence was rewritten by this audit.

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

The audit emits JSON to stdout only. It cannot promote, write QA, or set PASS.
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

## Proposed attestation procedure — NOT implemented or authorized

1. Obtain separate owner approval for exact IDs and purpose. Freeze a git SHA
   and manifest of old QA blobs, post hashes, row fingerprints, scorer code,
   business-facts/taxonomy hashes and migration commit. Preserve the original
   evidence in an immutable git ref/archive; never delete its history.
2. Reconfirm old hashes against immutable baseline bytes AND row. A migration
   label without this proof is insufficient. Put the six real-change cases in
   a separate manual-review list, with exact diffs and decisions.
3. Independently score current bytes with the canonical scorer in an isolated
   checkout. Do not reuse `result`, quality, seo or checks from old evidence.
   Record all failures. A failure requires a separately authorized content
   repair or explicit deferment, never a new PASS label/hash alone.
4. Prepare append-only attestations linking old evidence, exact new bytes,
   current matrix fingerprint, fresh scorer output, reason, reviewer approval,
   tool version and previous attestation hash. Bind legal/source review where
   the scorer requires it. Proposal manifests remain non-authoritative.
5. Add a dedicated validator/publisher-compatible attestation reader in a new
   reviewed PR. Reject absent approval, unknown IDs, changed code/inputs,
   changed post or row since scoring, broken provenance and failed QA. Use
   CAS against the approved SHA; preserve both old and new evidence.
6. Test on fixtures first; only after approval, apply the approved IDs in
   bounded batches on a separate branch. Validate FULL + build/link/schema,
   review diff, CI, merge, Pages SUCCESS and URL checks. No `_posts` edits in
   an evidence-only batch. Unapproved/failed cases stay unresolved.

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

Until approved and implemented, **FULL evidence validation remains FAIL**.
A green FULL build-mode quality gate (which validates scope chunk) proves
the current build/links and engine checks, not all historical evidence hashes.
