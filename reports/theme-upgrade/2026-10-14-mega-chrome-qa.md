# Theme Mega Menu + Global Navigation: Pre-release QA

Date: 2026-10-14 (Asia/Ho_Chi_Minh).
Production: https://blog.thuexemaynguyentu.com/
Base: `e0751b6bc15f9b4e38ab9819b2755eb25a23b593`.
Branch: `feature/premium-theme-mega-chrome-2026-10-14`.
Scope: only `_includes/header.html`, `assets/css/components.css`, `_layouts/default.html`, `assets/css/base.css`, `_includes/footer.html` and this report. No SEO/Writer content altered.

## Implemented
- Premium responsive desktop mega menu from **existing real** `_data/navigation.yml` categories. Blog mega panel also renders `CHỦ ĐỀ NỔI BẬT` from the existing footer data; all links are already published topic URLs. Pricing mega contains its existing 4 link categories and a genuine existing `/bang-gia/` overview.
- Preserve original `aria-controls`, `aria-expanded`, dropdown JS and all mobile accordion logic. CSS only changes presentation of the desktop dropdown.
- Global visible-on-focus "Chuyển đến nội dung chính" skip link, semantic main target and disabled smooth scrolling for reduced motion.
- Add footer back-to-top link to a real `#site-top` anchor, reuse original NAP/footer data, light/dark tokens and mobile responsiveness. Unsupported `chevron-up` icon was removed and replaced with text arrow.
- No invented price, empty categories, URL, articles or metadata changes.

## Checks completed before PR
- Header still has two `child.url` rendering loops (desktop/mobile) plus existing featured links from real footer group.
- CSS braces balanced; no artificial icon.
- Layout retains the `seo.html`, `header.html`, `footer.html`, `assistant.html` includes.
- Footer retains brand, NAP source, social and legal section loops; links unchanged except new `#site-top` anchor.
- **These checks do not constitute passed Jekyll build, automated browser, WCAG 2.2 AA or Core Web Vitals.**

## Required release gate
- GitHub Actions Quality Gate FULL on exact last PR head SHA: Jekyll build, generated link checks, canonical, schema, sitemap and Engine tests.
- Rendered desktop at 1200/1440, mobile 375/390/768, light/dark: mega dropdown not clipped or overflowing; all links open correctly; keyboard ArrowDown/Escape, Tab, outside click work; mobile focus trap unchanged and no duplicate focus target; skip link and back-to-top work with keyboard.
- Check live production HEAD after any merge; preserve Writer commits. No merge/deploy if QA fails. Normal non-force revert is rollback.
