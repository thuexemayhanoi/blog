# Xác minh triển khai — commit `ba59ea27` (đợt 1)

Ngày: 2026-10-22. Nhánh `main`, đẩy fast-forward từ `4f61156e` lúc 20:29Z, không force push, không có commit nào của publisher xen vào.

## GitHub Pages (FACT)

Run "pages build and deployment" #5494 (`39849246000`) cho đúng HEAD `ba59ea27`:

| Job | Kết quả | Thời gian |
|---|---|---|
| `build` (Jekyll, `jekyll-build-pages:v1.0.13`) | success | bước "Build with Jekyll" 20:29:33 → 20:35:24Z = 5 phút 51 giây |
| `deploy` | success | 20:35:42 → 20:36:01Z = 19 giây (chờ 5 giây) |
| `report-build-status` | success | 5 giây |

Từ push tới deploy xong: 6 phút 55 giây. Trước đợt này (run #5493, HEAD `4f61156e`): bước build 18 phút 05 giây, `deploy` chờ 36 phút 54 giây,
tổng khoảng 57 phút. Deploy được coi là SUCCESS vì job `deploy` kết thúc success (trạng thái tổng của run có thể hiển thị chậm).

## Quality gate (FACT)

Run #1276 (`39849247393`), HEAD `ba59ea27`:

- Job `gate` (FULL): **success**, 10 phút 43 giây, đủ 19 bước — validate chunk, FAQ source, invariants custom domain, Jekyll build (8 phút 02 giây),
  built-link integrity, FAQ parity + JSON-LD, canonical + host cũ, draft leak, sitemap + schema + hub, crawler metadata, sitemap targets, working tree sạch.
  Trước đợt này job này bị hủy ở mốc 20 phút ngay sau bước build.
- Job `engine-tests`: **failure** sau 18 phút 02 giây — 31 suite, 29 PASS, 2 FAIL. Hai suite lỗi và các test hỏng **giống hệt** run #1275 ở HEAD `4f61156e`
  (trước đợt này): `test_hardening` (`test_s7_no_ai_no_secrets`, `test_s7_publish_hotpath`, `test_publisher_has_no_dispatch_and_only_watchdog_has_cron`)
  và `test_slugify_vi` (`setUpClass`, fixture cần ≥ 10 hàng PLANNED có chữ đ, hiện có 0). 29 suite còn lại PASS, gồm `test_gate_scope`,
  `test_related_cluster_data`, `test_faq`, `test_publish_flow`, `test_multiwriter_sim`. Đây là lỗi đỏ sẵn trên `main` (mục SEO-104), không do đợt này.

## Commit báo cáo `94d2cb49` (FACT)

Chỉ thêm công cụ `scripts/seo`, tài liệu và báo cáo; nội dung `_site` không đổi.

- Pages run #5495 (`39853580990`): `build` success (bước Jekyll 9 phút 59 giây), `deploy` success (19 giây), tổng 11 phút 03 giây.
- Quality gate run #1277 (`39853581771`): job `gate` **success**, 13 phút 16 giây, đủ 19 bước. Job `engine-tests` (`120092306738`) **failure** sau 904 giây
  trong bước "Run offline engine test suites": 31 suite, 29 PASS, 2 FAIL — **cùng hai suite và cùng các test hỏng** như run #1276 và #1275:
  `test_hardening` (`test_s7_no_ai_no_secrets`, `test_s7_publish_hotpath`, `test_publisher_has_no_dispatch_and_only_watchdog_has_cron`) và `test_slugify_vi`
  (`setUpClass`, fixture cần ≥ 10 hàng PLANNED có chữ đ, có 0). Đã đọc log để xác nhận (FACT, 2026-10-22), không còn là dự đoán.
  Nguyên nhân từng test (đã chẩn đoán, chưa sửa vì ngoài phạm vi SEO và chạm hợp đồng workflow): `factory-publish.yml` hiện có `schedule: cron '17,47 * * * *'` và
  `workflow_dispatch` trong khi test hợp đồng yêu cầu publisher chỉ push-driven; test `sk-` khớp nhầm trong `quality-gate.yml` (chuỗi `webmcp-ask-site.js`);
  fixture của `test_slugify_vi` phụ thuộc hàng đợi PLANNED.

## Commit `316f01e0` — cột vai trò/hành động cho url-inventory (FACT)

Thêm `scripts/seo/enrich-inventory.py`, tài liệu và báo cáo; nội dung `_site` không đổi (không chạm template, bài viết, URL, workflow).

- Pages run #5497 (`39864485459`): `build` success (bước Jekyll 22:23:05 → 22:29:01Z = 5 phút 56 giây), `deploy` success (23 giây), tổng push → deploy xong 7 phút 07 giây.
- Quality gate run #1278 (`39864486023`): job `gate` **success**, 8 phút 25 giây, đủ 19 bước (bước build 6 phút 09 giây). Job `engine-tests` (`120126663180`) **failure** sau 17 phút 52 giây:
  31 suite, 29 PASS, 2 FAIL — cùng hai suite và cùng các test hỏng như #1275, #1276, #1277 (`test_hardening`: `test_s7_no_ai_no_secrets`, `test_s7_publish_hotpath`,
  `test_publisher_has_no_dispatch_and_only_watchdog_has_cron`; `test_slugify_vi`: `setUpClass`, có 0 hàng PLANNED chữ đ sau BLG-06228). Đã đọc log (FACT).
- Mẫu thời gian build trên GitHub cho cùng nội dung site sau tối ưu: Pages 5 phút 51 giây, 9 phút 59 giây, 5 phút 56 giây; bước build của `gate` 8 phút 02 giây, 9 phút 39 giây, 6 phút 09 giây.
  Cả ba mẫu Pages đều dưới mẫu trước tối ưu (18 phút 05 giây); dao động giữa các lần chạy vẫn lớn.
- Run Pages của commit báo cáo này không được ghi ở đây (tránh vòng lặp ghi-báo-cáo-về-chính-nó).

## Xác minh live (không curl trực tiếp được từ sandbox; dùng Nimble Extract tải trang công khai)

| URL | Kết quả |
|---|---|
| `/` | dòng tiêu đề = `Thuê xe máy 50cc–125cc tại Hà Nội \| Nguyễn Tú` (khớp bản đã duyệt); H1 `Dịch vụ cho thuê xe máy 50cc–125cc tại Hà Nội` xuất hiện đúng 1 lần; mô tả hero có mặt; NAP, giờ hoạt động và dữ liệu giá giữ nguyên; liên kết nổi bật mới "Xe 50cc", "Honda Vision" có mặt |
| `/thue-xe/thue-thang/` | phần giới thiệu hub mới; khối "Bài nên đọc trước" với 5 liên kết; BreadcrumbList JSON-LD; phân trang 1–7 + "Trang sau"; footer/menu có "Xe 50cc", "Honda Vision" |

Không xác minh live được (UNKNOWN / NOT VERIFIED): meta description của trang chủ (công cụ chỉ trả văn bản trang, không trả thẻ meta; đã kiểm bằng so sánh byte
với bản build trước đợt này và bản build cuối); phân trang sâu `/kinh-nghiem/trang/100/` trên live (đã kiểm trên bản build: 383 → 45 liên kết);
Search Console của blog (chưa kết nối).

## Rollback

Commit đơn lẻ, chỉ chạm template/dữ liệu/nội dung hub/công cụ/báo cáo: `git revert ba59ea27` khôi phục toàn bộ (URL, canonical, bài và bằng chứng QA không bị đụng).
