# Live URL diagnostics — Issue #77

Run `python3 scripts/seo/audit-live-sitemap.py --selftest` before auditing. To scan the public sitemap and report HTTP 404 evidence without changing any URLs: `python3 scripts/seo/audit-live-sitemap.py --workers 8 --timeout 15 --slug-samples 30 --out reports/live-url-audit.csv`.

The script writes CSV and JSON reports in `reports/` (excluded from the deployed Jekyll site). It checks sitemap URLs without automatically following redirects. It also samples the old URL and proposed corrected URL for the Vietnamese letter “đ”. A valid OLD 200 and missing NEW 404 are a **blocked migration**, not a broken current sitemap URL.

The 1,410 historical URLs identified in `reports/factory/seo-master/slug-d-audit.json` are NOT automatically changed. On GitHub Pages the project does not currently demonstrate real HTTP 301/308 routing. Do not rewrite any published permalink, sitemap URL, canonical or QA hash without validated OLD 301/308 to NEW 200, independent QA provenance, and rollback.

For link targets absent from the sitemap, the separate built-page link audit already runs in the FULL Quality Gate via `scripts/factory/check-built-links.py --site ./_site`.

## Chạy audit trên GitHub (không cần máy cá nhân)

Môi trường agent bị chặn miền production, nên audit live chạy trên GitHub runner bằng workflow có sẵn
`factory-liveness.yml` (chỉ `workflow_dispatch`, `contents: read`, không commit/push; hợp đồng đúng 8 workflow giữ nguyên):

1. GitHub → Actions → **Factory liveness** → *Run workflow*.
2. Bật `live_audit`. Tùy chọn `redirect_probe` dạng `start:limit` (ví dụ `0:50`) để probe OLD → NEW của lô đó.
3. Job `Live URL audit` làm theo thứ tự: selftest công cụ → **infra probe** → **crawl** → (tùy chọn) **redirect probe** → upload artifact `live-url-audit`.
   Kết quả nằm ở *Summary* của run (infra JSON, đếm mã HTTP) và log (`TARGET <mã> <url> sources=N`, `ROW ...`).

`scripts/seo/live-url-audit.py` (stdlib, không theo redirect, chỉ GET/HEAD, chỉ origin production):

| Chế độ | Việc làm | Đầu ra |
|---|---|---|
| `infra` | DNS, TLS, header (`server`, `cf-ray`, `x-github-request-id`, `via`...) cho `/`, sitemap, robots, OLD/NEW mẫu | JSON + `edge` = `github-pages` / `cloudflare` / `vercel` / `fastly` / `netlify` / `unknown` |
| `crawl` | Mọi URL trong sitemap + mọi đích `<a href>` nội bộ; 404/410/5xx/3xx, soft 404, canonical lệch/thiếu, `noindex` trong sitemap | CSV `source,target,status,fix,retest` + `*.summary.json` |
| `redirects` | OLD phải 301/308 một bước tới đúng NEW (giữ query), NEW 200 và canonical tự trỏ | JSON `slug-redirect-evidence/1` (`all_ok`) |

Cách đọc `infra`: `edge = github-pages` nghĩa là chưa có lớp edge nào đứng trước, **không thể** đặt HTTP 301 theo từng đường dẫn;
`edge = cloudflare` (có `cf-ray`) nghĩa là có proxy, cần chủ hạ tầng xác nhận quyền tạo Bulk Redirect trước khi di trú.
Test offline: `python3 scripts/factory/tests/test_live_url_audit.py` (máy chủ HTTP cục bộ, không mạng ngoài).
