# AI Content Collision Guard v2 — Draft technical specification

Repository: thuexemayhanoi/blog. Frozen audit commit: ea7c82f57185eb85487bb61287ff3539d8e41ce9.
STATUS: DESIGN ONLY on audit branch; NOT INTEGRATED, NOT TESTED, NOT DEPLOYED.

## Existing baseline; preserve it
Current scripts/factory/refill-queue.py contains G1-G8: valid child and capacity, normalized keyword/intent, unique slug/output_path/canonical/title, minimum word target, ledger ID, valid taxonomy. Existing docs/SEO-OWNERSHIP.md establishes intent ownership. Keep all checks; never weaken or replace factory-publish.yml, publish-gate.py, transaction, lease, or quality thresholds. G1-G8 cannot alone prove semantic uniqueness across different subtopics and paraphrased titles.

## Sources
Pin Git commit and read all: data/content-matrix.csv (EVERY status), content-inventory.csv, published _posts, _drafts, _queue, state/refill-candidates.json, state/matrix-seed.json, factory/refill-batches, writer-claims, taxonomy, editorial plan. On an unavailable source stop with REVIEW; never guess a clean result.

## Decision chain
NEW TOPIC -> NORMALIZE -> exact ID/slug/canonical/title/keyword -> retrieve near matches from all children using keyword/intent/entities -> compare full published/draft text for top candidates -> examine user question, geography, persona, timeframe, commercial vs informational purpose -> decide. Similarity scores only retrieve candidates; never ALLOW_CREATE automatically by a single threshold.

| Output | Meaning | Allowed action |
| --- | --- | --- |
| ALLOW_CREATE | Unique user intent demonstrated and competing URLs checked | May enter existing gates after approval |
| UPGRADE_EXISTING | Relevant URL exists but content insufficient | Recommend enhancement to existing URL; no auto write |
| REVIEW_COLLISION | Ambiguity, conflicting evidence, stale index or missing source | BLOCK publishing; review manually |
| REJECT_DUPLICATE | Same user intent/content without added value | Reject proposed topic only; never remove a live URL |

## Candidate record
Required attributes: candidate ID, source HEAD SHA, proposed title, primary intent, entities, status, possible competing URL/ID pairs, intent comparison evidence, distinct angle, decision, reviewer, decision timestamp. A stale source SHA forces REVIEW; do not silently permit publish. Producer commits the candidate decision to an audit report, NEVER updates checkpoint by itself.

## Implementation architecture
- Keep index keyed by file content SHA-256 + canonical URL + status + taxonomy/intent fingerprint; include published, staged, planned, in-progress and draft states.
- Build initial inverted lexical/semantic retrieval index in batches; checkpoint every batch. Incrementally invalidate changed files/rows; avoid full 20k-post rescan per topic.
- Query local content-index first; shortlist neighbors from same child, sibling child and cross-parent intent groups. Inspect primary text/H1/meta/outlines of shortlisted pages; confirm content comparison before rejecting or allowing.
- Same-title detection must not collapse distinct personas or conditions. Same-intent paraphrases must not pass merely by changing words or child.
- Add a read-only pre-refill preflight and a pre-publish race check at current main SHA only when explicitly approved. Retain canonical publisher; never add a second publisher.
- No external AI requests, new heavy dependencies, secret keys or runtime API calls inside production GitHub Actions.

## Existing test cases
reports/factory/review-pairs.md: BLG-00005/00053, 00017/00018, 00410/00411, 00423/00424 are distinct by documented editorial analysis; BLG-00227/00228 share mid-term vehicle-exchange intent and require owner decision. All 10 rows remain REVIEW. None may be auto-merged, redirected or moved to EXISTING by this specification.

## Acceptance / QA
Test exact duplicate; paraphrase in same child; paraphrase across child; old Unicode/percent-encoded permalink; distinct winter vs rain; different personas; duplicate in active lease; repeat candidate during parallel writer session; missing published body; changed metadata/content SHA; stale head; index vs manifest drift. Fail closed, produce audit evidence, preserve all existing gates. Require full suite and owner approval before integration, merge or deployment.
