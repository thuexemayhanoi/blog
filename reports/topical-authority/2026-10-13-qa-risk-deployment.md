# QA & RELEASE GATE — Topical Authority Audit — 2026-10-13

Target: thuexemayhanoi/blog / blog.thuexemaynguyentu.com.
Production snapshot SHA: ea7c82f57185eb85487bb61287ff3539d8e41ce9.
Proposed branch: audit/topical-authority-2026-10-13.
Release status: **HOLD / NO PRODUCTION RELEASE APPROVED**.

## Evidence ledger

| Check | Result | Evidence / qualification |
| --- | --- | --- |
| Repo correctly scoped | PASS | GitHub metadata; owner thuexemayhanoi, repo blog |
| Domain correct | PASS | CNAME: blog.thuexemaynguyentu.com |
| Jekyll source | PASS | _config.yml, AGENTS.md |
| Factory latest production deploy | PASS AT BASE | Pages run #38412122559 success; 2026-10-13T14:17:45Z |
| Factory publisher | PASS AT PRECEDING WRITER COMMIT | run #38412063251 success on bf1451fa |
| Quality Gate | PASS AT PRECEDING WRITER COMMIT | run #38412063294 success on bf1451fa |
| robots.txt HTTP | PASS SAMPLE | Firecrawl status 200, User-agent * Allow / |
| sitemap.xml HTTP | PASS SAMPLE | Firecrawl status 200 |
| /thue-xe/ HTTP | PASS SAMPLE | Firecrawl status 200 |
| main hub SEO title/H1 | PASS SAMPLE | H1: Thuê xe máy Hà Nội |
| Meta/canonical/schema generation | SOURCE PRESENT | _includes/seo.html has rel=canonical and Organization/LocalBusiness/WebSite/BlogPosting JSON-LD template |
| Rendered JSON-LD validator | PENDING | Scrape HTML excludes head and is not sufficient for validation |
| Global URL unique sample | PASS DISCOVERY SNAPSHOT | latest Firecrawl map 3,039 unique normalized URLs; no exact duplicate URL keys in that map |
| Production post inventory | PARTIAL | 483 legacy rows + factory published tally; no full file/body HTTP audit |
| Global GSC CTR/ranks | UNAVAILABLE | SiteGuru has no blog subdomain property |
| Content quality & near duplicates | PARTIAL | 5 documented legacy pairs; other 2k+ not full-text compared |
| Every internal link / orphan | PENDING | Proposed 12 relationships are NOT a complete edge census |
| Each page canonical/noindex/status | PENDING | Do not call every URL validated |
| Schema validation all templates | PENDING | Source exists, rendered validator not executed |
| Mobile / CWV | PENDING | No Lighthouse or device metrics collected |
| Audit branch CI | NOT RUN | Report-only changes and no branch CI claim |

## HIGH priority findings
- Factory continuously moves main HEAD; every batch needs immutable SHA and checkpoint.
- 10 legacy REVIEW (5 pairs), one material intent overlap candidate BLG-00227 vs BLG-00228; keep URLs.
- 1 BLOCKED row / PARTIAL_BLOCKED checkpoint; latest publish succeeds, so investigate without assuming entire pipeline broken.
- Live URL map varied between 2,850 and 3,039; investigate freshness/sitemap consistency.
- Blog _data/pricing.yml differs from the business-owner reference rates supplied in conversation for some weekly/monthly products. Do not auto edit; resolve content provenance.
- GSC for subdomain missing from connected SiteGuru, so no real query-level cannibalization decisions.

## Do not merge yet
Only report/spec documents were prepared. No code/test changes to quality gate, no Writer, no posts, no URL canonical redirects. There is nothing intended for production deployment in this batch. Keep audit artifacts on branch until review.

## Proposed next audited batch (approval required to change code/content)
1. Verify 100–200 live URL records at a time: HTTP 200/3xx/4xx, robots, canonical, sitemap presence and corresponding GitHub record; store checkpoints + failed URL evidence.
2. Review every P1 hub using page excerpts, GSC intents (if connected), and exact keyword ownership, classify KEEP/UPGRADE/REVIEW/CREATE only with evidence.
3. Test collision guard on read-only fixtures including drafts/queue, then integrate only if false-positive/false-negative cases and concurrency are controlled.
4. Run Jekyll build, repository existing test suite, link integrity, static output sitemap and JSON-LD parse, then mobile Lighthouse and compare against baseline.
5. Make a small targeted PR with change log and byte-safe rollback, seek explicit approval; never alter legacy URL or writer ownership.

## Rollback strategy
Current production SHA stays at ea7c82f... for this audit snapshot; audit branch new commits are isolated and unused by GitHub Pages. Rollback of this audit means closing/abandoning the branch; do NOT reset/rebase production or delete generated production content. For later production implementation, use targeted revert only after checking live writer commits and preserving lease/transaction and content hashes.
