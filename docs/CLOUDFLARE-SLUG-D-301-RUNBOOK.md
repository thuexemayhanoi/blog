# Phương án chuyển slug chữ đ → d bằng HTTP 301 — Issue #77

**Trạng thái: CHỈ CHUẨN BỊ. CHƯA KÍCH HOẠT BẤT KỲ CHUYỂN HƯỚNG NÀO.**

## Dữ liệu đã xác minh

- Bản đồ `reports/factory/seo-master/slug-d-migration-map.csv` chứa 1.410 cặp OLD→NEW, không trùng OLD/NEW theo nguồn audit cũ.
- `reports/factory/seo-master/cloudflare-301-DO-NOT-ACTIVATE.csv` có chính xác 1.410 dòng, không có header, định dạng Cloudflare Bulk Redirects theo tài liệu 2026. **Đây là BẢN THAM KHẢO, tuyệt đối không upload toàn bộ.**
- Mỗi dòng gồm `source_url,target_url,301,TRUE,FALSE,FALSE,FALSE`. Source không gồm scheme để khớp HTTP/HTTPS; preserve query string=TRUE; không dùng subpath hoặc wildcard.
- CSV **không** sửa code/site và **không được nhập/kích hoạt** khi các URL đích vẫn HTTP 404.
- Công cụ `scripts/seo/export-cloudflare-301.py` dựng lại CSV, kiểm tra file post/permalink gốc, matrix và trùng lặp. `--selftest`, `--validate-only`, `--start N --limit 50 --out /tmp/batch.csv`. **Batch nào chứa mismatch sẽ bị từ chối trước khi tạo file.**

## Lỗi dữ liệu vừa phát hiện: 36 bài có Matrix URL khác permalink

- Đối chiếu trực tiếp map 1.410 URL với `data/content-matrix.csv` hiện hành: **36 bài PUBLISHED** có `expected_url` khác frontmatter `permalink` thật của `_posts` (31 bài `/ky-nang/`, 5 bài `/hoi-dap/`). Ví dụ ID `BLG-00868`: bài thật `/hoi-dap/2026-09-29-at-xe-truoc-bao-lau-thi-nen/`, Matrix lại `/hoi-dap/2026/09/29/at-xe-truoc-bao-lau-thi-nen/`.
- File chi tiết: `reports/factory/seo-master/slug-d-36-matrix-drift-20261024.csv`.
- **Không sửa tay Matrix, slug hay QA evidence** của 36 bài. Xác minh sitemap/HTTP thật trước, dùng công cụ reattestation/revision chính thức và backup riêng.
- Bản xuất toàn bộ 1.410 URL phải bị chặn bởi script `--validate-only` cho đến khi xử lý các mismatch; batch không chứa mismatch vẫn có thể tạo *CSV nháp* để kiểm tra. Không kích hoạt 301 khi NEW chưa tồn tại.

## 50 URL 404 thật trong Matrix đã xác minh live (ưu tiên sửa riêng)

- So khớp **6.147 URL bài PUBLISHED/EXISTING/REVIEW** với sitemap live: 50 URL `expected_url` của các ID **BLG-00820…BLG-00869** không có trong sitemap.
- Đã kiểm tra HTTP trực tiếp **50/50 URL Matrix = 404**, nhưng **50/50 trang đích thật = truy cập được**; không có 50 bài bị mất.
- Cấu trúc Matrix sai `/<hub>/2026/09/29/<slug>/`. URL hiện hữu trong sitemap là 35 dạng `/<hub>/2026-09-29/<slug>/` và 15 dạng `/<hub>/2026-09-29-<slug>/`.
- Bản đồ từng ID: `reports/factory/seo-master/matrix-50-404-to-live-200-20261024.csv`. File Cloudflare CSV **50 nguồn 404 → 50 trang đích đã sống**: `reports/factory/seo-master/cloudflare-301-50-MATRIX-404-DO-NOT-ACTIVATE.csv`.
- **36/50** đồng thời thuộc danh sách 1.410 slug mất chữ `d`; 14 trường hợp còn lại chỉ lệch cấu trúc ngày tháng. 36 bài nói trên có QA evidence `DRIFT_CONTENT_SHA`.
- Khi xác nhận Cloudflare proxied DNS và rule chạy thật, đây là lô thích hợp để xử lý trước: **nguồn hiện 404, đích đã live 200**. Không cần đổi permalink bài thật để triển khai redirect `404 → 301 → live 200`. Tuy nhiên vẫn phải kiểm tra cấu hình, query string và các xung đột redirect hiện có.
- Không được đổi Matrix/QA thủ công. Sau khi redirect ổn định, cập nhật Matrix và QA bằng công cụ bảo trì có provenance, backup, rollback.

## Điều kiện cần hoàn thành trước khi di trú bất kỳ bài nào

1. Xác minh chủ tên miền và nền tảng DNS. Nếu chọn Cloudflare, phải khai báo domain đúng cách và bật **proxied DNS** cho host `blog.thuexemaynguyentu.com` mà không làm sai CNAME hiện hành; giữ SSL và toàn bộ URL khác.
2. Xác nhận Cloudflare Bulk Redirect List/Rule có thể dùng trên tài khoản. Free plan hỗ trợ 10.000 URL nhưng cần xác minh hạn mức thực tế còn lại.
3. Chuẩn bị tool migration nội dung đã xuất bản và QA evidence với dry-run, score độc lập và backup/rollback. KHÔNG sửa trực tiếp `data/qa` hay hạ QUALITY>=75, SEO>=70.
4. Với mỗi lô tối đa 50 URL: dựng URL NEW trả HTTP 200 trên production, nội dung chuẩn và canonical phù hợp; URL OLD vẫn phải phục vụ cho đến khi bật 301. Kiểm chứng URL NEW trước khi áp dụng redirect.
5. Chỉ nhập CSV của lô đã có NEW 200, tạo Bulk Redirect Rule và **Save and Deploy**. Dùng HTTP HEAD không follow redirect để xác nhận OLD trả 301, Location trỏ đúng NEW; truy cập NEW trả 200. Query string giữ nguyên.
6. Khi 301 chạy thật, cập nhật sitemap/canonical/internal links và matrix/post/QA theo transaction đã duyệt. Build Jekyll, FULL gate + built-links + live audit; rollback đúng lô nếu lỗi.
7. Không chuyển hướng về trang chủ, không đổi tất cả 1.410 URL trong một commit, không dùng meta-refresh/JS HTTP 200 thay 301.

## Cách dùng Cloudflare trên điện thoại (khi điều kiện 1–4 đã đạt)

- Vào Cloudflare Dashboard → tài khoản đang phục vụ tên miền → **Bulk Redirects** → **Create Bulk Redirect List**.
- Nhập CSV **chỉ của lô đã được chứng minh NEW HTTP 200** (`--start 0 --limit 50` cho lô đầu; không nhập file full 1.410 nếu các URL NEW chưa tồn tại).
- Xem kỹ danh sách → **Continue to Redirect Rules** → gắn list và kích hoạt rule.
- Sau khi kích hoạt kiểm 301 và Location bằng công cụ độc lập. Chỉ tiếp tục lô sau khi tất cả URL trong lô trước đạt.

## Kiểm thử an toàn

- `python3 scripts/seo/export-cloudflare-301.py --selftest`
- `python3 scripts/seo/export-cloudflare-301.py --validate-only` (**dự kiến BLOCKED** vì 36 mismatch hiện hữu, không được diễn giải là đã sẵn sàng)
- `python3 scripts/seo/export-cloudflare-301.py --start 0 --limit 50 --out /tmp/first-50-DO-NOT-ACTIVATE.csv` (chỉ xuất dữ liệu, không bật redirect)
- `python3 scripts/factory/tests/test_slugify_vi.py` (có test đồng bộ export CSV, nguồn `_posts` và map).
- `python3 scripts/factory/check-built-links.py --site ./_site` và `python3 scripts/seo/audit-live-sitemap.py --max-urls 100 --slug-samples 10`.

**Tài liệu chính thức:** https://developers.cloudflare.com/rules/url-forwarding/bulk-redirects/reference/csv-file-format/ và https://developers.cloudflare.com/rules/url-forwarding/bulk-redirects/create-dashboard/.

**Writer vẫn ở trạng thái pause `enabled:false`; không tự bật lại sau commit này.**
