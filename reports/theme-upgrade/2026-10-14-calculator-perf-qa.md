# Theme Performance — Calculator script on-demand

Date: 2026-10-14; branch `feature/premium-theme-calculator-lazy-2026-10-14`.

Changed only `_layouts/default.html`: the existing `assets/js/calculator.js` bundle is now loaded for the homepage layout and `/bang-gia/` page only. Both contain `{% include rental-calculator.html %}` in their source; `bang-gia-xe-so.md`, `bang-gia-xe-ga.md`, `bang-gia-xe-dien.md`, `bang-gia-xe-50cc.md` do not.

The global assistant JS does **not** call the Calculator controller; `main.js`, `assistant.js` and the injected business/pricing/assistant data remain unchanged. This avoids downloading ~7.4kB (source bytes, **not measured transfer size**) of unnecessary calculator JS on ordinary post/category pages. Does not modify pricing business data, amount displays, NAP, Factory, robots, canonical, sitemap or any article.

Source checks performed: calculator script source exists, target conditions have exact permalink and layout, assistant has no Calculator dependency, SEO header/footers and all other JS includes preserved. Production browser/Lighthouse and gzip network-savings not yet measured. Requires GitHub FULL Jekyll gate and smoke check of both actual calculator interfaces and a normal article before release.
