# Premium Theme Upgrade — SAFE CHECKPOINT

Updated: 2026-10-14 (Asia/Ho_Chi_Minh)
Repository: `thuexemayhanoi/blog`; production: `https://blog.thuexemaynguyentu.com/`
Snapshot base: `d3a6b13e528f4738e88c9df36efa6445517c09f9`.

## Source of truth
- Root matrix: `THEME_UPGRADE_MATRIX.md` (only present on `feature/premium-theme-p0-a11y-2026-10-14` until owner-approved merge).
- PR #28: https://github.com/thuexemayhanoi/blog/pull/28 — P0-A header semantics, accessible mouse/keyboard dropdown, mobile trap/restore focus, inert state.
- PR #29: https://github.com/thuexemayhanoi/blog/pull/29 — P0-B Jekyll 404 design tokens, real topic directory link; contains `reports/qa-audit/theme-404-p0-2026-10-14.md` to trigger existing FULL gate.
- SEO PR #25/#26/#27 are *independent*, remain untouched.

## Commits by batch
- `af0edfc7` Theme P0-P3 Matrix.
- `75406e67` P0-A header semantic roles, unique submenu ids + controls.
- `45f50c4a` P0-A mobile and desktop interaction controller.
- `30c54fc7` P0-A CSS dropdown/submenu semantics.
- `606fd3f8` Matrix implementation ledger.
- P0-B separate branch commits `14814bb6` and `054353d0`.

## GitHub Actions evidence at this checkpoint
- PR #28 FULL gate: https://github.com/thuexemayhanoi/blog/actions/runs/38445415584 — **IN PROGRESS** when last checked.
- PR #29 FULL gate: https://github.com/thuexemayhanoi/blog/actions/runs/38445625607 — **IN PROGRESS** when last checked.
- Static source tests for #28: JS parsed, identical source menu URL loops, modal accessible state attrs and event handlers. No browser/VoiceOver CI automation available.
- Static source tests for #29: frontmatter unchanged, CSS var references mapped to `tokens.css`, retained 404 robots/noindex and H1.
- **Not yet VERIFIED**: final Jekyll site artifact, mobile/desktop rendering of branch changes, assistive-tech behavior, Lighthouse CWV/CLS, and SEO regressions on exact rendered production URLs.
- Tavily extracted live homepage/topic/404, validating production exists but not previewing these unmerged changes.

## Exact safe next work
1. Refresh `main` latest SHA, read active Writer lease status **READ ONLY** and check PR #28/#29 full gate on their *latest heads* (do not assume previous head checks cover later matrix-only commit).
2. If any gate fails, fetch failing job steps/logs, fix only the relevant theme files on corresponding branch, rerun QA. Do not disable tests or change Factory.
3. After PASS, independently test keyboard focus: desktop hover/click/ArrowDown/Escape/outside, mobile Tab/Shift+Tab, Escape, overlay close, opener focus restoration, touch accordion and screen reader semantics; test 360px/390px/768px/1024px/1440px, dark/light, no CLS.
4. Scope further P1 batches independently: CSS-only premium mega-menu based on existing real taxonomy, keyboard skip link, no-client-40k search architecture, and homepage/reading/footer polish. Avoid making a duplicate menu/search component or fake links.
5. Keep draft PRs; owner authorizes release. Before any merge, re-evaluate HEAD/branch drift while W1/W2 publish. For eventual authorized production: merge a single independent batch, wait Pages deployment, verify exact URL and 200/canonical/robots/layout; rollback with ordinary revert of theme commit only.
6. Do NOT modify 3 SEO PRs, `_posts/`, `_drafts/`, `data/state/`, matrix/content index, manifests, claims, transactions, workflow files, NAP or pricing, and DO NOT activate Writer.

These are actual changes on independent GitHub branches, not production changes. No task automation was scheduled/modified as part of this theme job.

## Additional independent performance batch E1
- [PR #30](https://github.com/thuexemayhanoi/blog/pull/30), branch `feature/premium-theme-p1-remove-unused-nav-payload-2026-10-14`.
- Commit `c1298c816aaa616943e2fd0aeac7e3769b236217`: remove unused `window.NGUYEN_TU_NAVIGATION` serialization only in `_layouts/default.html`.
- Read-only usage audit: `main.js`, `calculator.js`, `assistant.js` contain **zero** usages of `NGUYEN_TU_NAVIGATION`; all required business, assistant, pricing globals and include tags preserved.
- [Existing FULL Quality Gate](https://github.com/thuexemayhanoi/blog/actions/runs/38446332380) **IN PROGRESS** at last check. No measured payload savings yet; do not claim benchmark.
- Three distinct Draft PRs #28 (accessibility), #29 (404), #30 (head payload), no merge to production.

## Latest verification reminder
Multiple new checkpoint/matrix commits were added to PR #28 after the first build started. GitHub checks are SHA-scoped; a green check on the earlier `30c54fc7` commit is **not** evidence that the newest PR #28 head `6e2cf4de` passed. Refresh checks for the current PR HEAD. Avoid additional workflow traffic solely for reporting.


## Latest operational checkpoint — after owner-approved release 2026-10-14

**This section supersedes historical pre-merge statuses above.**

Seven premium theme PRs #28–#34 are **MERGED**; last verified theme merge is `15a24a758fef41f9aaedca3a6857f529258515f5` (#34). The three independent SEO PRs #25/#26/#27 remain untouched. Current Matrix is at repo root `THEME_UPGRADE_MATRIX.md`, with historical dates and checked release ledger.

### Updated safe release queue
1. [PR #35 WCAG contrast + focus](https://github.com/thuexemayhanoi/blog/pull/35), head `cb49de43cbda3d1db4fe67476796e6af87dacadd`, **AWAIT FULL Quality Gate**. This PR uses `reports/qa-audit/theme-wcag-contrast-full-gate-2026-10-14.md` to trigger existing Jekyll FULL gate. If all required jobs PASS and mergeable, publish only this isolated batch; otherwise fix on its branch and rerun.
2. Confirm GitHub Pages successful deploy on FINAL `main` SHA. Prior Pages runs may have been cancelled by newer theme releases or active Writer commits: do not call them success until exact latest production commit is verified.
3. Verify https://blog.thuexemaynguyentu.com/ plus `/404.html`, `/tim-kiem/`, `/assets/data/search-recent.json`, `/thue-xe/`, one post URL and `/bang-gia/`; ensure nav, search, calculator, H1, article progress, footer Back to Top, dark/light, canonical and robots. On-site local search covers latest 300 titles only. Full-browser/mobile/VoiceOver and measured Core Web Vitals are **not yet certified**.
4. Check Writer W1/W2 claims **read-only**, reconcile `main` with Factory automated publications and no push/force reset of leases, checkpoint, matrix, articles or generated queues.
5. Release any changes only through small reviewed commits/PR and full exact SHA gate; on error revert the relevant squash merge only, never revert unrelated Writer commits.

### Current integration
- Main changes are existing production releases; do not open duplicate PRs for #28–#34.
- Source-level checks passed for actual navigation icon/routes, lazy 300-post JSON index, business photo image path in `assets/images/services`, CSS syntax guards and calculator only on home + `/bang-gia/`.
- Main is volatile; this checkpoint intentionally records a **snapshot**, not a frozen latest HEAD.
- Matrix statuses distinguish MERGED from LIVE QA and 40k benchmark. Do not mark 100% or WCAG2.2 AA compliance without real device/performance evidence.

### Rollback
If a specific just-released theme feature fails production QA, use an ordinary non-force revert commit of that PR's exact squash merge, then rerun Jekyll FULL QA. Do not revert the entire main history (it contains Writer publications). Theme merges #28–#34 and SHAs are listed in Matrix release ledger.
