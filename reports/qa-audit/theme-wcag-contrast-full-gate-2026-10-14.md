# Read-only FULL Jekyll Quality Gate trigger for theme WCAG contrast fix

This file exists solely to trigger the repository's existing `quality-gate.yml` workflow, whose `pull_request.paths` includes `reports/qa-audit/**`. `scripts/factory/gate-scope.py` fails closed to FULL mode for this QA path. Reports are excluded from Jekyll output by `_config.yml`. No workflow or Writer/Factory code has been changed.

Target: PR #35 `fix/premium-theme-wcag-contrast-2026-10-14`.

Source evidence: https://github.com/thuexemayhanoi/blog/blob/fix/premium-theme-wcag-contrast-2026-10-14/reports/theme-upgrade/2026-10-14-wcag-focus-qa.md

Specific assertions: base-surface `--color-text-muted` contrast improved to at least 4.5:1 light/dark; button, input and select focus-visible outlines are nonzero; all original URLs, canonical, NAP, CSS bundle names, JS and Writer state unchanged.

FULL gate + offline Engine tests required before theme production release. Additional mobile/keyboard and actual contrast visual QA remains distinct from CI; no unverified WCAG certification claimed.
