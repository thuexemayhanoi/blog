# Live URL diagnostics — Issue #77

Run `python3 scripts/seo/audit-live-sitemap.py --selftest` before auditing. To scan the public sitemap and report HTTP 404 evidence without changing any URLs: `python3 scripts/seo/audit-live-sitemap.py --workers 8 --timeout 15 --slug-samples 30 --out reports/live-url-audit.csv`.

The script writes CSV and JSON reports in `reports/` (excluded from the deployed Jekyll site). It checks sitemap URLs without automatically following redirects. It also samples the old URL and proposed corrected URL for the Vietnamese letter “đ”. A valid OLD 200 and missing NEW 404 are a **blocked migration**, not a broken current sitemap URL.

The 1,410 historical URLs identified in `reports/factory/seo-master/slug-d-audit.json` are NOT automatically changed. On GitHub Pages the project does not currently demonstrate real HTTP 301/308 routing. Do not rewrite any published permalink, sitemap URL, canonical or QA hash without validated OLD 301/308 to NEW 200, independent QA provenance, and rollback.

For link targets absent from the sitemap, the separate built-page link audit already runs in the FULL Quality Gate via `scripts/factory/check-built-links.py --site ./_site`.
