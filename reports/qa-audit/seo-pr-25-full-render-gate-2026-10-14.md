# PR #25 — independent full-render gate request

Repository: `thuexemayhanoi/blog`
Branch: `feature/p1-gia-thue-hub-pilot-2026-10-13`
Target: `thue-xe/gia-thue.md`
Production URL (do not deploy yet): `https://blog.thuexemaynguyentu.com/thue-xe/gia-thue/`
Date: 2026-10-14
Status: PENDING FULL CI; evidence request, NOT a QA pass certificate.

## Trigger rationale
The existing `.github/workflows/quality-gate.yml` monitors `reports/qa-audit/**` on pull_request. Its `scripts/factory/gate-scope.py` deliberately classifies this path as unknown outside pure content prefixes and **fails closed to FULL**. This QA-only document therefore triggers the pre-existing, read-only CI with Jekyll build, built link integrity, FAQ/schema checks, canonical and legacy-domain sanity, sitemap/hub checks, and offline engine tests, without adding or modifying a workflow file.

## PR-specific assertions to review after full gate
- Price hub: keep original YAML frontmatter, H1 from topic layout, target URL, 12 internal permalink targets; do not infer rates, deposit amounts or discount guarantees.
- Compare `_site/thue-xe/gia-thue/index.html` to existing public route: exactly one H1 and canonical `https://blog.thuexemaynguyentu.com/thue-xe/gia-thue/`; original slug, frontmatter metadata, search intent and article IDs unchanged.
- Run `python3 scripts/factory/check-built-links.py --site ./_site` and validate every internal link from this URL.
- Ensure only expected file changes besides this QA evidence. Reject draft leak, custom-domain drift and broken schema.
- A successful global Jekyll gate is **not** proof that visual mobile layout, accessibility, external legal content, rates or business policy is correct. Those checks remain separate.
- Because Writer W1 is publishing in parallel, compare latest `main` HEAD immediately before any future merge. Do not modify writer claims, transaction, checkpoint, matrix or production queue.

## Release policy
- PR remains **Draft**.
- Quality gate may read and build but MUST NOT commit to `main`, merge, publish or deploy.
- Owner release approval is a separate step after reporting exact check run SHA and results.
