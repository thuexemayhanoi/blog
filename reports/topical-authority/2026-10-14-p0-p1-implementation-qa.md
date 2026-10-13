# P0 Legal + P1 Hub Implementation — Branch-only QA Snapshot

Date: 2026-10-14 (Asia/Bangkok)
Repository: `thuexemayhanoi/blog`
Production: `https://blog.thuexemaynguyentu.com/`
Status: **ALL THREE PRS ARE DRAFT; NO MERGE / NO DEPLOY BY THIS TASK.**

## Ownership and safety
- Writer W1 is actively publishing on GitHub `main`. Latest verified lease: `s-mistral-w1` on `BLG-02703`.. `BLG-02712` (read-only).
- Each change was made on a separate **feature/fix** branch based on a main snapshot. Existing Writer W1/W2 leases, Factory code, ledger, article queue, `data/state/`, `data/content-matrix.csv`, `_data/pricing.yml`, sitemap and canonical URLs were not changed by these PRs.
- GitHub main advances continuously. PR base/head mergeability MUST be rechecked against current `main` immediately before any potential merge.
- No automatic publication authorization; owner must explicitly approve deployment separately.

## PR #26 — P0 Legal factual accuracy
URL: https://github.com/thuexemayhanoi/blog/pull/26
Branch: `fix/p0-license-facts-2026-10-14`
Commit: `8e755d9ee9e4a60cc0aa30cf43bf7026c265acb9`
Changed file (ONLY): `_posts/2026-09-27-cac-hang-bang-lai-xe-may-tai-viet-nam.md` (`BLG-00614`).

Implemented ten exact, bounded substitutions in article text:
1. 18+ minimum for A1 rather than incorrectly 16; clarify 16-year-old moped driver exception.
2. B1 covers both three-wheel motorcycles and A1-scope vehicles.
3. A1/A/B1 have no preset expiry under Article 57(5)(a); licence validity and points remain separate conditions.
4. Mirror changes in FAQ and contextual copy to avoid contradictory advice in the same article.
5. Avoid blanket statements that all mopeds require motorcycle licences.
6. Add an official legal source link and warn about older transitional licence classes.

**Quality**:
- Original article source blob: `1328f3a119820924f485751f5dbf03c11de5dd76`.
- Frontmatter is byte-identical; original `permalink`, `article_id`, SEO title, description, author, taxonomy preserved.
- Strict source assertions: 10/10 old text patterns matched exactly once; after patch, original concrete false claims are absent.
- GitHub PR diff: one article, approximately 8 added + 8 removed lines (same structural headings).
- GitHub Actions run: https://github.com/thuexemayhanoi/blog/actions/runs/38437300022
- **Quality gate (content FAST / engine FULL): SUCCESS** on patch SHA; **engine unit + concurrency tests: SKIPPED** for this content-only patch. Successful content gate is not proof of live rendered HTML/mobile QA.
- Legislation source: https://xaydungchinhsach.chinhphu.vn/toan-van-luat-trat-tu-an-toan-giao-thong-duong-bo-119240909105718285.htm — Articles 56, 57, 59 (read and checked). Subject to current amendments and historical licence transition rules.

## PR #25 — P1 Pricing Hub
URL: https://github.com/thuexemayhanoi/blog/pull/25
Branch: `feature/p1-gia-thue-hub-pilot-2026-10-13`
Commit: `6a75b1731e6d96aac80c3d3096ab24302c186dcc`
Changed file ONLY: `thue-xe/gia-thue.md`
- Original YAML frontmatter fully preserved.
- New body: ~716 whitespace words, four H2 sections + four FAQ H3; existing Jekyll `_layouts/topic.html` supplies single H1.
- 12/12 internal links confirmed to exist in repo with matching `permalink`.
- No hardcoded prices; amounts from business data must not be invented.
- No GitHub check runs attached to PR head at last query. **Rendered Jekyll build, accessibility, canonical output, Core Web Vitals, and production preview are unverified**.

## PR #27 — P1 Procedure Hub
URL: https://github.com/thuexemayhanoi/blog/pull/27
Branch: `feature/p1-rental-procedure-hub-2026-10-14`
Commit: `22fd3d351a17d9f88fb39a67b7c754741582c964`
Changed file ONLY: `thue-xe/thu-tuc.md`
- Original frontmatter preserved.
- New body: ~806 whitespace words. Steps: vehicle/timing; documents and eligibility; price/deposit; pickup checks; return; four FAQ.
- **6/6** internal destination files and explicit permalinks verified in GitHub main.
- No invented deposit amounts, delivery coverage, out-of-hours policies or legal mandates for passport custody.
- No check runs associated with PR head at last query; **rendered build and production visual QA remain unverified**.

## SEO / GEO considerations
- Keep current URL/canonical/H1 metadata stable: changes improve descriptive scope of the existing hubs instead of creating competing near-duplicate commercial landing pages.
- Do not automatically add FAQPage JSON-LD to every FAQ; choose only if rich-result eligibility/current policy is applicable, and never assume Google will show rich results.
- No real GSC dataset was available for /blog; do not claim traffic, CTR, impressions, rankings or indexing changes.
- Review global navigation, mobile UX and exact rendered schema for each PR before production approval.
- Because all hub copy changes are additive on the same URL, no redirect/301 needed.

## Stop/release gate
P0 legal accuracy is owner-approved **for branch editing and QA**, NOT automatically released. Before production release: owner reviews PR #26, explicit merge/deploy authorization, re-check latest `main` for concurrent Writer changes and schema/HTML fidelity; verify exact URL content and deployment after merge.

P1 hubs: PR #25 and #27 remain Draft pending successful Jekyll build/HTML checks, owner pricing/policy review and deliberate release ordering. Safest rollout: legal P0 first, then price Hub, then procedure Hub, with production QA between each; never batch all three into an unreviewed deployment.

Rollback (if later deployed): revert the exact approved merge commits by ordinary non-force commit, preserving published Writer commits and content state.

No changes to production in this audit run.
