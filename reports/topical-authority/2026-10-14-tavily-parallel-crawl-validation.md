# P0 Crawl Tool Replacement — Tavily + Parallel Search

Date: 2026-10-14
Repo: thuexemayhanoi/blog
Website: https://blog.thuexemaynguyentu.com/
Branch: audit/topical-authority-2026-10-13
Status: READ-ONLY WEB AUDIT; NO WRITER/PRODUCTION MUTATION.

## Purpose
Replace Firecrawl in further public-site URL mapping and content extraction with Tavily, and use Parallel Search as targeted search/fetch corroboration. GitHub repository remains the authoritative source for article IDs, status, URL ownership and production work. External search engines are not used to assert Google's actual indexed URL count.

## Verified connector operations
- Tavily Map: root URL; max_depth=2, max_breadth=120, limit=250, same-domain only. Returned **250 result URLs**, matching requested limit. This is a **bounded discovery sample**, not a complete site inventory. Prior Firecrawl snapshot of 3,039 discovered URL records should be retained as independent comparison, not replaced with a smaller Tavily map result.
- Tavily Extract: extracted 3/3 targeted pages successfully, with no failed_results:
  1. https://blog.thuexemaynguyentu.com/thue-xe/
  2. https://blog.thuexemaynguyentu.com/thue-xe/gia-thue/
  3. https://blog.thuexemaynguyentu.com/thue-xe/thue-theo-dia-diem/
- Last pending rental child hub (thue-theo-dia-diem) extracted: H1 "Thuê xe theo địa điểm"; an introductory paragraph describes rentals around railway stations, bus stations, airports and Hanoi areas; then article listings. It is structurally similar to other short-topic hubs. The previous Firecrawl RATE_LIMIT status was a tool limit, not evidence of a broken live URL.
- Tavily Crawl: URL root /thue-xe/, max_depth=2, limit=40, same domain, path filter /thue-xe/.*; returned 40 matching URL entries (hit requested cap). Because semantic instructions were supplied, extracted portions are short (~503 chars each): **NOT full-text duplicate/content quality analysis**; these are sample evidence and crawl discovery only.
- Parallel Search web_search: targeted site searches returned relevant competitors and external historical mentions, but did not establish a complete indexed list for the /blog subdomain. Search snippets and site: operators must not be interpreted as authoritative GSC impressions or Google index coverage.
- Parallel Search web_fetch: fetched excerpts for 2/2 key child hubs (gia-thue and thue-theo-dia-diem); no fetch errors. Both independently showed topic heading and article listing.

## Primary hub scan status update
Earlier hub batch: 10 out of 11 /thue-xe/ children verified with Firecrawl, one blocked by provider rate limit.
Current Tavily extraction: /thue-xe/thue-theo-dia-diem/ retrieved successfully.
Thus, **11/11 commercial child hubs have now been read by at least one public content extraction provider**.
This does **not** mean that all their outgoing links, HTML metadata, canonical, content quality, mobile rendering, legal claims or GSC statuses have been verified.

## Priority findings
P0: Keep an immutable GitHub HEAD snapshot for all article/URL comparisons while Writer W1 and W2 run.
P0: Do not rewrite previous 3,039 URL sample as a complete index; create a SHA- and time-labeled cross-provider coverage union and check discrepancies in batches.
P1: Complete QA for draft PR #25 Hub Gia thue; do not merge without owner approval.
P1: The Location hub has content but predominantly navigational listing; evaluate adding location-choice guidance *to this existing URL* only after factual verification of real service geography/delivery.
P2: Run Tavily Extract over selected PUBLISHED/DRAFT collisions after retrieving their exact URLs from GitHub; do not perform whole-site deep extraction needlessly.
P2: Use Parallel Search for source verification, competitors and topical query hypotheses, NOT as a canonical crawler.
P3: Integrate semantic collision guard only following independent QA, with fail-closed REVIEW policy.

## Tool strategy
1. GitHub: canonical content inventory / state / checkpoint / editorial ownership.
2. Tavily Map (bounded, depth/limit recorded): URL discovery for specific site section.
3. Tavily Extract: direct markdown of exact candidate URLs, batching up to 20 per request; validate failures.
4. Tavily Crawl (bounded, no semantic instructions when complete text needed): selected topical sections only; inspect partial payload and tool caps.
5. Parallel Search: external citations/source corroboration; Parallel web_fetch if search excerpts insufficient.
6. If either provider exhausts its limit, preserve checkpoint and mark incomplete; never report false full coverage or alter production.

No live site, Writer ownership, content queue, canonical URL, published post, schema, sitemap or SEO metadata was changed as part of this report.
