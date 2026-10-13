# Theme Editorial / Hero — QA Snapshot

Date 2026-10-14; branch `feature/premium-theme-editorial-2026-10-14`.

Changes:
- Replace homepage's truly empty `visual-card` with a responsive `figure`/image + caption, sourced from **existing** `business.vehicle_types | first` and verified `_data/business.yml` image `/assets/images/services/xe-so-honda-wave.jpeg`; no new marketing claim or invented offer. Width/height 640x480, `fetchpriority=high`, descriptive existing alt text; caption discloses vehicle availability needs confirmation.
- Add premium responsive hero and editorial CSS loaded **only** on `home` and `post` layouts; retain all current SEO, metadata, global CSS, page heading markup and JSON-LD.
- Attach decorative 3px `reading-progress` indicator on post layout only; lightweight JS `reading-progress.js` loaded only for articles, passive scroll/rAF and resizing, `aria-hidden=true` to avoid screen-reader notifications.
- Improve article heading scroll targets, readability and cards without modifying article content/H1/slugs.

Verified source-level: homepage image source real; placeholder removed; H1 and pricing calculator still present; article H1/breadcrumb/FAQ/related still present; JS parsed; CSS braces balanced. No Writer/Factory/SEO module changed.

Pending acceptance: GitHub Actions FULL quality gate on exact head SHA, Jekyll build, internal link integrity, JSON-LD parity, canonical/sitemap, engine tests, visual review desktop/mobile incl. iPhone 375/390, dark/light, image crop, mobile CLS, and Core Web Vitals benchmark (not measured). No production release until gate success.
