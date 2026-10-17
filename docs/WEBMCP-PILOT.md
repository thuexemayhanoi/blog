# WebMCP pilot — /blog (2026-10-17)

Scope: **one read-only browser tool** named `ask_site`. No privileged actions,
no booking/checkout, no AI API, no WordPress integration, no polyfill or SDK.
Static Jekyll Pages remains a fully working ordinary website when WebMCP is
unsupported. This is a **page-local** WebMCP tool, not a remote MCP server for
connecting to ChatGPT's plugin interface.

## Architecture / intended user journey

- Visitor asks an in-browser AI: "Bài nào nói về thủ tục thuê xe máy Hà Nội?"
- When the browser supports WebMCP, `document.modelContext.registerTool`
  registers `ask_site({question: "thủ tục thuê xe"})`.
- The tool lazily fetches `/assets/data/webmcp-index.json` from the **same
  origin**; Jekyll generates it from **published `site.posts` only**.
- It scores normalized Vietnamese keywords in titles/descriptions and returns
  up to five **actual, same-origin** source links plus short excerpts.
- The agent reads sources and writes any prose answer itself. The tool does
  **not** claim to interpret complete article bodies or make factual guarantees.
- `pagehide` aborts this page's registration; absent WebMCP results in no-op.

## Scope and limits

- Tool name: `ask_site`, one global read-only tool registered on each page.
- Input: 2–120 character Vietnamese query, up to 12 normalized tokens.
- Output: five top matched sources, count, index scope and caution. Strictly
  published article metadata; not private drafts, WordPress data or claims.
- One full public metadata index (no content bodies) is fetched **only on
  invocation** and cached in memory for the page lifetime.
- This does not replace the existing 300-article interactive search
  `/tim-kiem/`; they are independent. The WebMCP index covers the
  published `site.posts`, not merely 300 titles.
- Safari/iPhone or any browser without native WebMCP still uses all existing
  UI; it **will not show a WebMCP tool**. Do not call this an iOS feature.
- The JSON is publicly accessible but not listed in the sitemap.
- Do not use this as proof of SEO/AEO ranking or Google crawling quality.

## Security / compatibility

- Browser-native `document.modelContext`; legacy navigator fallback only
  when needed. No polyfill, cross-origin proxy, outbound API or credentials.
- Fetch uses same-origin credentials and agent AbortSignal.
- Only root-relative same-origin URL paths, no `//`, `?`, `#`,
  backslashes, whitespace or path lengths >512 chars; client never
  injects HTML or executes strings from the index.
- No DOM or URL mutation. Read-only annotation; contents treated untrusted.
- Does not touch production Writer Pool / CAS / Factory Publisher.

## Verification

1. Static: `node --check assets/js/webmcp-ask-site.js`.
2. Mock semantics: `node scripts/tests/test-webmcp.cjs` checks registration,
   read-only schema, accent folding, ranking, malformed URLs, cancel,
   empty result and no-op on unsupported browsers.
3. Jekyll: full `quality-gate.yml` (or build locally with site's Jekyll
   toolchain). Confirm rendered `assets/data/webmcp-index.json` parses and
   contains only published posts; ensure the content count is plausible.
4. Native WebMCP runtime **requires a browser supporting the origin trial/
   WebMCP API**: enable it on a dev/staging origin, load a page and confirm
   `document.modelContext` and `getTools()` (when the consumer supports it).
   Invoke `ask_site` and check source URLs, cancellation and UI unaffected.
   An origin trial token or browser flag may be necessary.
5. If target-agent/browser checks are not performed, report
   **could-not-verify**, not "works in Chrome" or "works on iPhone".

Production release only after user accepts PR + QA and deployment checks.
Rollback = revert the include in `_layouts/default.html`; the index and JS
then become inert.

Authoritative spec: https://webmachinelearning.github.io/webmcp/
Chrome: https://developer.chrome.com/docs/ai/webmcp/imperative-api

## Demo tren iPhone (ordinary JS search, separate from WebMCP)

- Open https://blog.thuexemaynguyentu.com/ and tap "🔎 Tìm bài thông minh"
  in the homepage hero, or go directly to /tim-kiem/.
- The mobile search now uses the same lazy full published metadata index,
  not just the former 300 recent articles. Suggested query chips work on Safari.
- Search returns original article URLs; it is keyword retrieval, NOT an
  AI-generated answer. Google site-search fallback remains available.
- Verify locally with: node scripts/tests/test-site-search.cjs
- The two Node suites are now executed by EXISTING quality-gate.yml.
- Exactly EIGHT workflows remain mandatory; no additional GitHub Actions
  workflow may be created for WebMCP.
