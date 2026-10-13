# MASTER SEO — Topical Authority Expansion + Production Protection

Date: 2026-10-13. Scope: ONLY thuexemayhanoi/blog -> https://blog.thuexemaynguyentu.com/
Frozen production commit: ea7c82f57185eb85487bb61287ff3539d8e41ce9
Audit branch: audit/topical-authority-2026-10-13
Status: **READ-ONLY PRODUCTION; EVIDENCE INVENTORY AND PRIORITIZED PLAN, NOT A COMPLETE CONTENT AUDIT**.
All artifacts here are excluded from Jekyll build under reports/; no factory, theme, posts, URL, slug, title, meta, canonical or deployment changed.

## 0. Sources and limitations
GitHub: CNAME, _config.yml, AGENTS.md, README.md, data/content-inventory.csv (483 rows), data/content-matrix.csv (2,962 rows *per factory-generated progress report*), data/content-taxonomy.json, state/checkpoint.json, reports/factory/progress.json, reports/factory/review-pairs.md, reports/factory/matrix-report.md, _data/pricing.yml, _includes/seo.html, INTERNAL-LINKING, SEO-OWNERSHIP, refill-queue.py.
GitHub state at snapshot: 2,198 PUBLISHED through factory, 473 EXISTING legacy, 10 REVIEW legacy, 280 PLANNED, 1 BLOCKED; 483 legacy total. Latest published ID BLG-02692 is an ID, NOT the published article count. Factory status field PARTIAL_BLOCKED is present; latest publish workflow and Pages deployment succeeded, so this field is not proof of outage.
Live: Firecrawl scrape /thue-xe/ HTTP 200; /robots.txt HTTP 200 Allow / and sitemap URL; /sitemap.xml HTTP 200. URL discovery by Firecrawl sitemap-only produced 2,850 initially and 3,039 later; discovery results are NOT proof of indexation or each URL HTTP 200. Stored latest 3,039 in separate CSV.
Ubersuggest (Vietnamese query, global location): DA 8, backlinks 68, referring domains 37, 0 organic keywords/estimated traffic in the tool. **Not Google Search Console truth.**
SiteGuru currently lists rentbikehanoi.com and thuexemaynguyentu.com; no property for blog.thuexemaynguyentu.com, so this audit CANNOT provide actual GSC clicks, impressions, CTR, average rank or Search Console coverage for /blog.
The GitHub file accessor returned blank content for the 2.6 MB content-matrix.csv even for small line slices, despite returning its SHA; no direct full-row parse was performed. Existing factory validation can check that matrix; this audit cannot certify every row.
Head HTML is sanitized by the third-party page scraper. Do not claim canonical or JSON-LD missing: _includes/seo.html explicitly generates canonical, Organization, LocalBusiness, WebSite and BlogPosting for posts; final rendered schema validation remains pending.

## 1. GLOBAL CONTENT INVENTORY
Artifact: 2026-10-13-url-discovery.csv (3,039 discovered sitemap/Firecrawl entries; recorded per URL with section/type and NOT_TESTED statuses). Artifact: 2026-10-13-legacy-inventory.csv (483 mapped legacy posts, preserving exact legacy Unicode URLs). Existing content matrix is kept unchanged as owner/source of truth for factory IDs, states, slugs, canonical paths and keyword ownership.
**Incomplete:** 3,039/3,039 URL metadata/deep text/HTTP status/real indexing not individually verified; dynamically changing Firecrawl counts. Do not treat total discovered URLs as published pages.

## 2. SEO MASTER MATRIX
Preserve data/content-matrix.csv as the canonical factory matrix. New auxiliary 2026-10-13-coverage-matrix.csv tracks all 56 child hubs and legacy counts with status REVIEW_CONTENT_BEFORE_CREATE; source posts unchanged. Role recommendations: homepage (/), main parent hub (/thue-xe/), commercial child hubs (/thue-xe/gia-thue/, thu-tuc, dat-coc, thue-ngay, thue-tuan, thue-thang, khach-quoc-te, nhan-tra-xe, su-co, thue-theo-doi-tuong, thue-theo-dia-diem); all other parent hubs support different topical journeys. Existing legacy URL role remains under human review; no keyword owner reassigned.

## 3. CANNIBALIZATION MATRIX
Artifact: 2026-10-13-intent-review-queue.csv. reports/factory/review-pairs.md documents 5 legacy pairs; four SAFE_DISTINCT on editorial inspection; BLG-00227 versus BLG-00228 is a genuine overlap candidate around changing rental vehicle mid-contract. All ten legacy rows remain REVIEW. No merge, redirect, noindex or canonical switch authorized. Cannibalization across the other factory posts is NOT yet verified at full-text and GSC query level; exact title uniqueness is insufficient.

## 4. TOPICAL COVERAGE MATRIX
Confirmed taxonomy: 7 parents, 56 children. In the 483 legacy inventory, 117 map to P-THUE-XE, 239 to P-KY-NANG, 43 to P-XE-MAY, 38 to P-PHAP-LY, 18 to P-HOI-DAP, 17 to P-DU-LICH and 11 to P-CUNG-DUONG. This distribution describes legacy only, NOT total live category depth.
Live /thue-xe/ hub displays 11 child areas: Gia 63, Thu tuc 90, Ngay 55, Tuan 36, Thang 65, Dat coc 32, Quoc te 61, Nhan/tra 90, Su co 100, Doi tuong 29, Dia diem 21 (642 total shown by hub at scrape time). These are rendered hub counts and must not be confused with distinct indexed articles or audited high-quality articles.
Counts cannot determine topical gaps. Need inspect existing content & queries for real pain points before labeling CREATE.

## 5. KNOWLEDGE GAP REPORT (RESEARCH CANDIDATES, NOT ASSERTED EMPTY)
P1: validate user journeys and current answers for daily/weekly/monthly pricing, exact rental duration accounting, deposits and return, documents, pickup/drop-off confirmation, first-time renters, international-driver requirements, rental use case in Hanoi districts, and real incident/escalation advice. Existing 11 child hubs already cover these headings: preferred action UPGRADE_EXISTING if thin, KEEP if adequate, REVIEW where unclear.
P2: cross-check comparison and model decisions across vehicle category, 50cc and electric, insurance/legal source currency, and trip/city mobility. Differentiate a commercial rental query from travel/informational questions. Require independent evidence for any new URL.
P3 CREATE queue: **ZERO approved URLs from this audit**; existing 280 PLANNED are not a command to publish without re-review. New content must pass full semantic collision guard, demand/intent proof, provenance and editorial approval.

## 6. KNOWLEDGE GRAPH / TOPIC CLUSTER MAP
Artifact: 2026-10-13-taxonomy-graph.md. Homepage -> 7 verified parent hubs -> 56 verified child hubs. Map shows structural taxonomy, NOT confirmed HTML link graph. Core commercial pillar at /thue-xe/; supportive legal, model, travel, route, skills, FAQ hubs are not to compete for its head term.

## 7. INTERNAL LINKING MATRIX
Artifact: 2026-10-13-linking-proposals.csv contains 12 proposed navigational, commercial, cross-child, legal and contextual link relationships with HTTP/actual-edge check marked NOT_TESTED. Existing docs/INTERNAL-LINKING.md requires contextual linking at writing time and stable old permalinks. related-articles.html is documented as clustered fixed-size link selection; audit exact live incoming/outgoing links in future batch before any edits. Never auto-insert thousands of sitewide links; never change legacy accented percent-encoded routes.

## 8. CONTENT UPGRADE BACKLOG
P0: verify sitemap vs repository at frozen and latest production SHA; resolve sitemap-discovery count drift; connect proper GSC property; manually review BLOCKED state and active writer transaction; check factual pricing consistency against owner-approved data (see Risk 04); audit collision pair BLG-00227/00228 without mutations.
P1: editorial audit of /thue-xe/ and 11 child hubs: direct answer, navigation, clarity, business provenance, owner relevance and proper schema. Prioritize /thue-xe/gia-thue/, thu-tuc/, dat-coc/, thue-thang/ after actual page-by-page verification.
P2: add only verified missing contextual cross links in small scoped batch on future approved branch; refresh stale supporting articles with verified sources and no headline rewrites.
P3: research genuinely unserved queries, queue candidates as REVIEW first, require new URL proof and use existing Writer gate only after owner approval.
P4: re-evaluate clusters with GSC evidence and ranking/conversion measurement before further expansion.

## 9. NEW CONTENT EDITORIAL PLAN
No new content generated or published. All suggested angles in section 5 are RESEARCH_ONLY. Policy for one proposed URL: search all PUBLISHED/DRAFT/PLANNED/REFILL/WRITING states, compare candidate with competing full article bodies and keywords, record distinct persona/location/problem and verified evidence, get decision ALLOW_CREATE then apply existing G1-G8 and QA. Default REVIEW_COLLISION if ambiguous. If no evidence for new intent, UPGRADE_EXISTING/KEEP. The 280 existing PLANNED entries must be examined rather than automatically reissued or overwritten.

## 10. AI CONTENT COLLISION GUARD SPECIFICATION
Artifact: docs/AI-CONTENT-COLLISION-GUARD-V2.md. Existing G1-G8 preserved. Proposed semantic guard across all child groups and status classes, evidence-based ALLOW_CREATE/UPGRADE_EXISTING/REVIEW_COLLISION/REJECT_DUPLICATE, fail-closed when unknown, SHA-index incremental processing, no heavy dependencies and no production changes. Design only; integration deliberately pending safety QA and approval.

## 11. RISK REGISTER
R01 HIGH: Snapshot drift while Writer publishes; mitigate by pinning HEAD and only overlaying new snapshots for new audit batches.
R02 HIGH: GSC property missing for subdomain; no real position/click/cannibalization query diagnostics.
R03 HIGH: Legacy canonical/Unicode URL preservation; encoded URLs must remain verbatim.
R04 HIGH: PRICING PROVENANCE — current /blog _data/pricing.yml publishes Vision 800k–1m/week, Air Blade 800k/week 1.4m/month, Honda Click/Mio 600–700k/week. These do not match the owner's provided reference pricing in conversation. Repo policy states /blog and /shop business data must not be synced automatically. Therefore flag owner decision and verify which contractual table is authoritative BEFORE any content/price changes. DO NOT auto-correct.
R05 MEDIUM: 5 legacy pairs REVIEW; one real overlap candidate pending explicit decision.
R06 MEDIUM: Factory checkpoint PARTIAL_BLOCKED with 1 BLOCKED matrix item; latest workflow successful but investigate reason and whether any candidate affected.
R07 MEDIUM: Firecrawl URL discovery changed 2,850 -> 3,039; inventory not certified exhaustive/stable and HTTP status per URL unknown.
R08 MEDIUM: No full Jekyll build/schema/links/core web vitals validation performed for this audit branch.
R09 MEDIUM: Current G1-G8 title/keyword checks cannot alone rule out semantic intent overlap across children.
R10 LOW: Ubersuggest organic=0 is third-party coverage, not proof of zero Google clicks/indexing.

## 12. QA, DEPLOYMENT & ROLLBACK PLAN
Verified externally: correct CNAME and Jekyll config; no production write; /thue-xe/, /robots.txt, /sitemap.xml HTTP 200 by scraper; GitHub last Pages build/deploy SUCCESS at base SHA; base Quality gate SUCCESS on parent writer commit; audit branch contains reports/spec only. _includes/seo.html contains canonical and JSON-LD source, but rendered output needs independent parsing.
NOT VERIFIED: every URL HTTP status, per-URL rendered canonical, robots/indexability, actual GSC coverage, all broken internal links, full-body duplicate detection, full static build at branch SHA, schema validator outcome, mobile UX and Core Web Vitals. No rank uplift measured; none claimed.
Next gated QA: compare sorted exact URL inventory across frozen and current main HEAD; perform batch 100–200 live URL checks with checkpoint, identify actual 404/noindex/canonical divergence, verify 56 hub hrefs and 5 collision pairs, run read-only factory validation and Jekyll build on isolated working copy, validate generated schema and link checker, test mobile/performance, compare before/after.
Merge requires explicit owner approval AFTER CI PASS on the exact review commit; freeze exact file diff; any future production modifications need their own targeted branch/PR and rollback to original commit. Do not merge this audit branch automatically.

## Deliverable status matrix
| Deliverable | Status | Evidence |
|---|---|---|
| Global Content Inventory | PARTIAL | 3,039 discovery URL rows, 483 verified legacy mappings |
| SEO Master Matrix | EXISTING BASELINE + AUXILIARY | 2,962 factory state rows reported, 56 topics audited structurally |
| Cannibalization Matrix | PARTIAL | Five grounded legacy pair cases; all other text reviews outstanding |
| Topical Coverage Matrix | STRUCTURE DONE, DEPTH PENDING | 56 child hubs, 483 legacy groupings |
| Knowledge Gap Report | RESEARCH CANDIDATES | No confirmed CREATE |
| Knowledge Graph | TAXONOMY DONE, HREF PENDING | 7 + 56 graph |
| Internal Linking Matrix | PROPOSALS ONLY | 12 edges, NOT_TESTED |
| Content Upgrade Backlog | PRIORITIZED | P0-P4 stated |
| New Content Editorial Plan | HOLD | 0 new CREATE approved |
| AI Collision Guard Spec | COMPLETE SPEC, NOT CODE | separate design doc |
| Risk Register | INITIAL | 10 documented risks |
| QA and Deployment Plan | PARTIAL QA, PLAN COMPLETE | base CI/deploy checked; new branch no CI assertion |

Final: no published page, draft queue, permalink, canonical, redirect, robots, sitemap, factory code, SEO metadata, transaction, checkpoint or writer lease has been changed in this audit.
