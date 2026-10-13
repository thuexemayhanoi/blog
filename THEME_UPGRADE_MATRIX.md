# THEME UPGRADE MATRIX — Premium GitHub Publishing Theme

Project: `thuexemayhanoi/blog`; production https://blog.thuexemaynguyentu.com/; production branch `main`.
Created: 2026-10-14 (Asia/Ho_Chi_Minh).
Audit base: `d3a6b13e528f4738e88c9df36efa6445517c09f9` (active Writer main; always refresh).
Technical branch: `feature/premium-theme-p0-a11y-2026-10-14`.
**No merges or production deploy without separate owner approval.**
Do not modify or conflict with draft SEO PR #25 (price hub), #26 (license article), #27 (procedure hub); these are separate content concerns.
Never edit Writer leases, `_drafts/`, `_posts/`, `data/state/`, publication workflow, checkpoints, content-index, manifests, editorial ledger, SEO metadata, URLs or canonical.

## Actual current architecture
- Static GitHub Pages **Jekyll (Minima base)**: `_config.yml`, `_layouts/`, `_includes/`.
- Global layout `_layouts/default.html`; page types `home`, `post`, `hub`, `topic`, `topic-listing`, `listing`, `category`, `page`.
- Shared header/footer `_includes/header.html` + `footer.html`, navigation source `_data/navigation.yml` (nonempty menu categories with genuine permalinks), business NAP `_data/business.yml`.
- CSS `assets/css/tokens.css` (3 KB), `base.css` (4 KB), `components.css` (47 KB), `responsive.css` (19 KB); JS `main.js` (10 KB), `assistant.js` (9 KB), `calculator.js` (8 KB). File sizes from GitHub API at audit snapshot (not transferred bytes).
- Homepage already has hero, category/topic directory, price calculator, pricing previews and latest articles. Article already has build-time TOC when >=4 H2, breadcrumb, related posts, previous/next, CTA. Footer is multi-column details/summary.
- Central SEO `_includes/seo.html`: custom-domain canonical + Organization, LocalBusiness and post BlogPosting JSON-LD; do not refactor within theme work.
- Existing `quality-gate.yml` controls FAST vs FULL. FULL includes Jekyll Pages build, internal link checks, JSON-LD FAQ parity, canonical and domain checks, sitemap and draft leaks, offline engine tests. No new workflows needed.
- Website public browser inspection is supplemental; source-level findings cannot be represented as measured Core Web Vitals, device visual tests or deployed fixes.

## Matrix

| ID | Severity | Area | Evidence in actual HEAD | Safe action / acceptance | Status | Batch |
|---|---|---|---|---|---|---|
| TH-P0-01 | P0 | Desktop dropdown semantics | `header.html` sets menubar/menu/menuitem roles despite regular site navigation; dropdown button starts `aria-expanded=false`. `main.js` only binds hover + inline style, never synchronizes expanded state | Use normal nav/list/link semantics; assign stable unique `aria-controls`; pointer, keyboard click, Escape, focus-out/away states synchronized. No change to menu destinations | VERIFIED; IMPLEMENTATION PENDING | A |
| TH-P0-02 | P0 | Mobile focus management | `main.js` mobile open/close only applies body class and text state; no focus return/focus trap; mobile panel `role=dialog aria-modal=true` without focus ownership | Move focus inside on open; trap Tab/Shift+Tab; Escape/overlay/close return to opener; hide panel from screen readers/tab flow when closed. Preserve touch accordion, contact overlay and existing UI classes | VERIFIED; IMPLEMENTATION PENDING | A |
| TH-P0-03 | P0 | Keyboard focus | `base.css` resets `button:focus{outline:none}` while `:focus-visible` provides global outline. Confirm appearance for keyboard in all theme controls | Keep visible keyboard focus, especially dropdown and mobile close, check contrast WCAG 2.2 AA on light/dark | PARTIAL SOURCE EVIDENCE; VISUAL QA PENDING | A |
| TH-P0-04 | P0 | 404 design tokens | `404.html` style uses undefined legacy tokens `--bg-light`, `--bg`, `--space-3xl`, `--font-size-5xl`, `--primary` | Swap to existing tokens without changing 404 permalink, robots noindex, sitemap false or H1; verify mobile and dark backgrounds | VERIFIED; IMPLEMENTATION PENDING | B |
| TH-P1-01 | P1 | Mega menu | Current desktop nav has flat dropdown list for menu items `Cẩm nang` and `Bảng giá`, no categorized multi-column design | Enhance with responsive multi-column grid using existing navigation data and real links; no empty categories | EXISTING BASIC FEATURE; UPGRADE PENDING | C |
| TH-P1-02 | P1 | Global search | `header.html` provides no searchable site-wide control; 404 suggests search but shows no form | Design compact index/search that scales without loading 10k–40k posts client-side; stage before claiming functionality | MISSING | C |
| TH-P1-03 | P1 | Mobile menu | Existing accordion toggles `aria-expanded`, but no `aria-controls` for submenu except custom pricing ID | Add unique control IDs and managed hidden behavior; test Touch/VoiceOver | PARTIAL | A/C |
| TH-P1-04 | P1 | Article UX | `post.html` already includes H1, meta, TOC, breadcrumb, related, prev-next and CTA | Improve reading progress only if low overhead; ensure TOC anchor labels robust and accessible; do not modify article content | EXISTS; ENHANCEMENT PENDING | D |
| TH-P1-05 | P1 | Homepage hero | `home.html` uses empty `visual-card glass-card`; hero and feature/post grids already exist | Meaningful image/card or remove blank decorative panel after comparing actual live layout; preserve heading/meta | PARTIAL | D |
| TH-P1-06 | P1 | Performance | `default.html` serializes pricing, business, assistant **and navigation** on every page plus 3 JS bundles | Audit consumers and load only required data/scripts safely; evaluate CLS/LCP/INP with measurement; no unproven score claims | SOURCE ISSUE TO PROFILE | E |
| TH-P1-07 | P1 | CSS consistency | `responsive.css` duplicates mobile menu breakpoint sections; 4 stylesheets total ~74KB source | Audit cascade conflicts and rationalize incrementally after screenshot regression, preserve working components | VERIFIED DUPLICATION | E |
| TH-P1-08 | P1 | Scale 40k | Topic/post layouts loop `site.posts`; article next/prev also loops all matching posts; homepage uses site posts | Benchmark Jekyll build sizes/time at milestones, use materialized indexes and pagination rather than client-side global payload | CAPACITY NOT BENCHMARKED | F |
| TH-P2-01 | P2 | Footer | Already has multi-column details accordion, NAP, social and policy links, copyright from `site.time` | Check mobile collapse/focus, add Back to Top if useful, do not duplicate link groups | EXISTS; POLISH PENDING | D |
| TH-P2-02 | P2 | 404 search/CTA | 404 currently suggests 'Sử dụng menu điều hướng' and 'Tìm kiếm trên website' with no search widget | Replace unsupported instruction or add functional search only after search architecture exists | VERIFIED | B/C |
| TH-P2-03 | P2 | Breadcrumb, pagination | Dedicated templates already cover post/hub/topic/listing; `topic.html` limits 24 posts and uses indexed listing pages | Verify rendering + pagination against data and link QA; no duplicate breadcrumb | EXISTS; QA PENDING | F |
| TH-P2-04 | P2 | Design token accessibility | Semantic tokens light/dark present, but some legacy style blocks use incompatible names; contrast not audited | Align P0 legacy styles and audit WCAG 2.2 AA by component | PARTIAL | B/E |
| TH-P3-01 | P3 | Future additions | Consider reading progress, subtle transitions and topical suggestions | Add only after P0/P1 benchmarks and SEO QA | BACKLOG | G |

## Execution / evidence policy
1. `AUDIT → MATRIX → FIX → TEST → COMMIT → PUSH BRANCH → GitHub CI QA → UPDATE MATRIX → NEXT`. Push commits individually, never large unreviewed commits.
2. **Batch A**: Navigation accessibility — only `_includes/header.html`, `assets/js/main.js`, and scoped CSS when needed; verify keyboard state, Escape, focus trap, touch, existing links and no duplicate event listeners.
3. **Batch B**: 404 token corrections — only `404.html` unless a shared token truly needed; preserve robots/SEO.
4. **Batch C–G**: Plan and test separately; do not claim they are done because implementation is described.
5. To trigger existing FULL build on pull request, this feature branch changes `_includes/` (engine paths), so no new workflow is necessary. QA evidence must be read from exact head SHA; code exists ≠ test pass.
6. QA checks: normal browser/live screenshot before deployment; syntax/static assertions, Jekyll FULL, built internal links, canonical/JSON-LD/robots/sitemap, navigation keyboard, mobile viewport, dark mode, CLS and performance where instrumented.
7. Keep scope to technical branch. Rollback after a future authorized merge via non-force revert of individual theme commits. Avoid reverting Writer publication commits.
8. **Checkpoint**: see `reports/theme-upgrade/CHECKPOINT.md` for current commits, QA signals, pending items and next safe operation. Never mark DONE without CI + production QA evidence.
