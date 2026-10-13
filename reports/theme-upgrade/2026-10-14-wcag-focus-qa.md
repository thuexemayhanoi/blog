# WCAG P0 — Muted text contrast and keyboard focus QA

2026-10-14 / `fix/premium-theme-wcag-contrast-2026-10-14`.

## Verified source and contrast
The current token `--color-text-muted` had insufficient contrast for small body labels:
- Light mode `#a0a0a0` on `#ffffff`: **2.61:1**.
- Dark mode `#606060` on `#1a1a1a`: **2.77:1**.
New values:
- Light `#686868` on `#ffffff`: **5.57:1** (WCAG 2.2 AA ordinary text ≥4.5:1).
- Dark `#a8a8a8` on `#1a1a1a`: **7.32:1**.
Ratios calculated using standard sRGB-relative-luminance contrast formula; contrast of the *entire site* is NOT measured, only these token/background pairs.

Additional fixes: `button:focus-visible` explicit 3px outline in `base.css`; `.form-select:focus-visible` and `.form-input:focus-visible` use 2px primary outline and offset, overriding prior `outline:none` focus rule. Preserve existing labels, form field attributes, pricing calculator behaviour and keyboard handlers.

Files scoped to `assets/css/tokens.css`, `assets/css/base.css`, `assets/css/components.css`. No SEO/URLs/Factory/Writer content, navigation data, JavaScript or workflows changed.

Checks remaining: run GitHub FULL quality gate on exact PR SHA, check rendered CSS cascade for focus rings on desktop/iPhone + VoiceOver/keyboard, check both dark/light in actual UI, avoid claiming entire site WCAG 2.2 AA from token contrast alone. Any regression → isolate rollback. Do not merge if QA fails.
