# Prototype — shared FAQ component (NOT applied to the site)

Status: **reference only**. Nothing here is under `_includes/`, `_layouts/` or `_data/` of the site, `reports/` is excluded from the
Jekyll build (`_config.yml` → `exclude: reports/`), so none of it can reach production. It was built and run in a throw-away Jekyll
site **outside the repository** (github-pages gem 232 = Jekyll 3.10.0, the same engine as the production build) to prove that the proposed
architecture works before asking for approval.

## What it proves (see `faq-implementation-plan.md` §3)

* One data variable drives BOTH the visible block and the `FAQPage` JSON-LD → no way for them to diverge.
* Renders **nothing** unless `status: approved` and at least 2 items have `approved: true` (a page without data is byte-identical).
* O(1) per page (a data lookup by key; no loop over `site.posts`, so the ~12 min build does not get slower).
* Output is valid JSON even for quotes, backslashes, `&`, `<b>` and `<script>` in the answer text; `jsonify` alone does **not** escape `</`,
  so the component adds `replace: '</', '<\/'` (otherwise an answer containing `</script>` would break out of the JSON-LD block).
* Jekyll 3.10 cannot pass `site.data.faq[page.slug]` directly as an include parameter (`Invalid syntax for include tag`) — assign it to a
  variable first (`{% assign faq_data = site.data.faq[page.slug] %}{% include faq.html items=faq_data %}`).
* `faq_parity_check.py <_site>` fails the build when the visible Q&A and the JSON-LD differ (tested both ways: pass on correct output,
  exit 1 when only the visible paragraph is altered).

## Layout hook that would be added (not applied)

```liquid
{%- comment -%} _layouts/post.html, after {{ content }} and before the related block {%- endcomment -%}
{% assign faq_data = site.data.faq[page.slug] %}
{% include faq.html items=faq_data %}
```

## Files

* `_includes/faq.html` — component (visible block + JSON-LD from the same variable)
* `_data/faq/test-post.yml` — sample data incl. hostile characters used by the test
* `faq_parity_check.py` — visible-vs-JSON-LD parity check for a built `_site`
