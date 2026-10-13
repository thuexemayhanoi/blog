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
