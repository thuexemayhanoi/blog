# Live URL diagnostics — Issue #77

Run `python3 scripts/seo/audit-live-sitemap.py --selftest` before auditing. To scan the public sitemap and report HTTP 404 evidence without changing any URLs: `python3 scripts/seo/audit-live-sitemap.py --workers 8 --timeout 15 --slug-samples 30 --out reports/live-url-audit.csv`.

The script writes CSV and JSON reports in `reports/` (excluded from the deployed Jekyll site). It checks sitemap URLs without automatically following redirects. It also samples the old URL and proposed corrected URL for the Vietnamese letter “đ”. A valid OLD 200 and missing NEW 404 are a **blocked migration**, not a broken current sitemap URL.

The 1,410 historical URLs identified in `reports/factory/seo-master/slug-d-audit.json` are NOT automatically changed. On GitHub Pages the project does not currently demonstrate real HTTP 301/308 routing. Do not rewrite any published permalink, sitemap URL, canonical or QA hash without validated OLD 301/308 to NEW 200, independent QA provenance, and rollback.

For link targets absent from the sitemap, the separate built-page link audit already runs in the FULL Quality Gate via `scripts/factory/check-built-links.py --site ./_site`.

## Chạy audit trên GitHub (không cần máy cá nhân)

Môi trường agent bị chặn miền production (và host lưu log/artifact của GitHub), nên audit live chạy trên GitHub runner bằng
workflow có sẵn `factory-liveness.yml` (chỉ `workflow_dispatch`, `contents: read`, không commit/push; hợp đồng đúng 8 workflow giữ nguyên):

1. GitHub → Actions → **Factory liveness** → *Run workflow*.
2. Bật `live_audit`. Tùy chọn `stub_check` = `all` hoặc `start:limit` (ví dụ `0:50`) để kiểm QA trang chuyển hướng của registry di trú slug.
   Mặc định log KHÔNG còn in cả khối inventory (hàng nghìn dòng base64): bước cuối `LIVE_AUDIT_SUMMARY_BEGIN … END` in bản tóm tắt gọn (đếm mã HTTP, lỗi, kết quả stub check) để đọc bằng tail log;
   bật `dump_inventory` khi cần giải mã kiểm kê đầy đủ ở máy cục bộ.
3. Job `Live URL audit` làm theo thứ tự: selftest công cụ → **infra probe** → **crawl** → (tùy chọn) **stub check** → upload artifact `live-url-audit`
   (luôn chạy, kể cả khi bước trước lỗi) → purity check.
   Kết quả nằm ở *Summary* của run (infra JSON, đếm mã HTTP) và log (`TARGET <mã> <url> sources=N`, `ROW ...`). Vì agent không tải được
   artifact, kiểm kê đầy đủ cũng được in vào log dạng `LIVE_INVENTORY_BEGIN ... _END` (gzip+base64, có sha256); giải mã bằng
   `python3 scripts/seo/decode-log-blob.py LOG.txt LIVE_INVENTORY out.json` (tương tự `STUB_EVIDENCE`).

`scripts/seo/live-url-audit.py` (stdlib, không theo redirect, chỉ GET/HEAD, chỉ origin production; URL có dấu cách/Unicode được mã hóa %XX và
không bao giờ làm sập lượt quét):

| Chế độ | Việc làm | Đầu ra |
|---|---|---|
| `infra` | DNS, TLS, header (`server`, `cf-ray`, `x-github-request-id`, `via`...) cho `/`, sitemap, robots, OLD/NEW mẫu | JSON + `edge` = `github-pages` / `cloudflare` / `vercel` / `fastly` / `netlify` / `unknown` |
| `crawl` | Mọi URL sitemap + mọi đích `<a href>` nội bộ + tài nguyên (img/script/css). Phân loại: 404/410/5xx/3xx/lỗi mạng, soft 404, canonical lệch/thiếu/trùng, `noindex` trong sitemap, trang meta-refresh trong sitemap, liên kết nội bộ vào trang chuyển hướng, tiền tố `/blog/` hoặc host cũ, đường dẫn không-ASCII, tài nguyên 404, trang mồ côi, trang mỏng/không H1 | CSV `source,target,status,fix,retest`; kiểm kê `url,kind,status,final_url,error_type,cause,handling,inbound` (CSV+JSON); `*.summary.json` |
| `stubs` | Theo `slug-redirect-registry.csv`: URL CŨ = HTTP 200 + `<meta http-equiv="refresh" content="0; url=MỚI">` + canonical MỚI + không có trong sitemap; URL MỚI = HTTP 200 + canonical tự trỏ + không phải trang chuyển hướng + có trong sitemap + có H1/nội dung + không chuỗi/vòng | JSON `slug-stub-evidence/1` (`all_ok`, `problem_counts`); mã thoát 1 nếu có dòng không đạt |
| `redirects` | (dự phòng) OLD phải 301/308 một bước tới đúng NEW; chỉ có nghĩa nếu sau này có lớp edge | JSON `slug-redirect-evidence/1` |

Cách đọc `infra`: `edge = github-pages` nghĩa là chưa có lớp edge nào đứng trước, **không thể** đặt HTTP 301 theo từng đường dẫn. Di trú slug dùng trang
**HTTP 200 + meta refresh 0 giây + canonical** và báo cáo gọi đúng tên như vậy — KHÔNG ghi là "301".
Test offline: `python3 scripts/factory/tests/test_live_url_audit.py` (máy chủ HTTP cục bộ, không mạng ngoài).
