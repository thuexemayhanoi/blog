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

### Bổ sung 2026-10-23: đọc được thẻ `<head>` live (FACT)

Nimble Extract với `output_format: simplified_html` và `driver: vx6` trả nguyên HTML kể cả `<head>` (các lần trước dùng định dạng mặc định nên chỉ nhận văn bản trang).
Kiểm lại trên domain live sau deploy `316f01e0` (HEAD `main` lúc đó = `2edcfd64`, chưa có commit publisher nào xen vào):

| URL | Kết quả |
|---|---|
| `/` | `<title>`, `<meta name="description">`, `og:title`, `og:description`, canonical, H1 và mô tả hero **khớp từng ký tự** với `scripts/seo/frozen-homepage.json` (bản duyệt `4f61156e`); NAP, giờ mở cửa, liên kết "Xe 50cc", "Honda Vision" có mặt |
| `/kinh-nghiem/trang/100/` | thanh phân trang 45 liên kết (bản cũ phát 382), `rel="prev"` và `rel="next"`, canonical đúng URL, 1 H1, 1 `<link rel="icon">`, breadcrumb, không có `&` trần ở title/meta |
| `/an-toan-phap-ly/2026/09/28/bao-hiem-tu-nguyen-cho-xe-may-co-ang-khong/` | 1 canonical đúng URL, 1 H1, breadcrumb, khối bài trước/sau, JSON-LD BlogPosting + BreadcrumbList, 1 favicon |
| `/robots.txt` | `User-agent: *`, `Allow: /`, `Sitemap: https://blog.thuexemaynguyentu.com/sitemap.xml` |
| `/sitemap.xml` | 6.842 URL, trùng hoàn toàn (không thừa, không thiếu) với sitemap của bản build cuối; không có `/404.html` hay `/tim-kiem/` |

Ghi chú: một phép dò `&` trần trên toàn bộ `<head>` báo 2 vị trí; cả hai là toán tử `&&` trong script chuyển giao diện sáng/tối (không phải thuộc tính HTML), nên không lỗi.
Phạm vi kiểm tra của `check-regressions.py` (title và thuộc tính `content`) cho 0 vi phạm trên cả ba trang live.

Chưa xác minh được (UNKNOWN): thứ hạng, lập chỉ mục và số liệu Search Console của `blog.thuexemaynguyentu.com`. Đã kiểm tra các nguồn đang kết nối vào ngày này:
Windsor `searchconsole` chỉ có hai property là `https://thuexemaynguyentu.com/` và `https://chatbot.thuexemaynguyentu.com/` (không có blog; property tiền tố URL của website chính không bao gồm tên miền con);
OpenSEO không có tài khoản Google nào được kết nối. Cần chủ website thêm property của blog vào một trong hai nguồn này mới có số liệu thật.

## Rollback

Commit đơn lẻ, chỉ chạm template/dữ liệu/nội dung hub/công cụ/báo cáo: `git revert ba59ea27` khôi phục toàn bộ (URL, canonical, bài và bằng chứng QA không bị đụng).


---

# Đợt 2 (2026-10-23) — sửa nội dung, lớp hiển thị và công cụ bảo trì

Nguồn thẩm quyền: MASTER WORK — NGUYỄN TÚ BLOG SEO FULL REPAIR A–Z. Mọi thay đổi đi qua PR, Quality gate FULL (job `gate` + job `engine-tests`) xanh trên head của PR trước khi merge squash;
không force push; không đụng URL, canonical, matrix, checkpoint nhà máy, lease của writer khác, H1/title/meta/hero trang chủ đã duyệt.

## PR đã merge (FACT, GitHub Actions)

| PR | Nội dung | Commit merge | Quality gate (run; job) | Pages |
|---|---|---|---|---|
| #43 | seo(slug): audit 1.410 URL thiếu chữ đ, bản đồ OLD→NEW, BLOCKED_INFRA_301, test chặn tái diễn | `b322c800` | #1281 success; gate 9 phút 08 giây; engine-tests 12 phút 18 giây (success) | #5502 success (9 phút 14 giây) |
| #44 | fix(pricing): đồng bộ giá tuần/tháng với bảng giá chủ cửa hàng và website chính | `a89dd8c9` | #1282 success; gate 13 phút 24 giây; engine-tests 11 phút 00 giây (success) | #5504 success (7 phút 31 giây) |
| #45 | seo(content): đồng bộ giá tuần/tháng trong 23 bài legacy, rút gọn 4 meta, sửa H1 lạc | `002ac9c9` | #1284 success; gate 0 phút 34 giây; engine-tests 0 phút 00 giây (skipped) | #5503 cancelled (10 phút 07 giây) |
| #46 | feat(factory): revise-published.py — đường bảo trì chính thức sửa nội dung bài PUBLISHED có evidence | `3fbc0e45` | #1289 success; gate 13 phút 13 giây; engine-tests 14 phút 49 giây (success) | #5507 success (8 phút 51 giây) |
| #47 | fix(pricing): sửa nốt giá tháng Air Blade 1.400.000đ còn sót trong bang-gia-xe-ga | `205be933` | không có (PR chỉ đổi `.md` gốc/tài liệu) | #5505 cancelled (11 phút 12 giây) |
| #48 | fix(content): Wave có giá tuần/tháng theo bảng giá chủ xe (2 bài legacy) và dẫn đúng TT 108/2026 (BLG-00314) | `a11be2e2` | #1290 success; gate 0 phút 30 giây; engine-tests — (skipped) | #5506 success (9 phút 56 giây) |
| #49 | feat(content): lớp "Lưu ý cập nhật pháp lý" có nguồn chính thức cho 22 bài chưa sửa được nội dung gốc | `9a6460d7` | #1292 success; gate 14 phút 18 giây; engine-tests 18 phút 13 giây (success) | #5508 cancelled (7 phút 54 giây) |
| #50 | feat(seo): liên kết ngữ cảnh "Cùng chủ đề" cho 49 nhóm bài trùng từ khóa chính (107 bài) | `ea45d355` | #1296 success; gate 9 phút 29 giây; engine-tests 18 phút 50 giây (success) | #5510 success (10 phút 08 giây) |
| #51 | fix(content): đính chính pháp lý 3 bài PUBLISHED qua revise-published (lô revise-20261023-legal-01) | `aa8b6d82` | #1295 success; gate 13 phút 16 giây; engine-tests 18 phút 58 giây (success) | #5509 cancelled (10 phút 31 giây) |
| #53 | feat(content): khối "Giá thuê tham khảo hiện hành" cho 68 bài còn giá cũ mà chưa sửa được nội dung gốc | `d794f64b` | #1307 success; gate 12 phút 47 giây; engine-tests 18 phút 59 giây (success) | #5516 success (9 phút 02 giây) |
| #54 | fix(content): đồng bộ giá tuần/tháng theo bảng giá chủ xe — lô 5/5 (21 bài, revise-published) | `51be40d8` | #1300 success; gate 9 phút 09 giây; engine-tests 18 phút 19 giây (success) | #5511 cancelled (5 phút 17 giây) |
| #55 | fix(content): đồng bộ giá tuần/tháng theo bảng giá chủ xe — lô 1/5 (50 bài, revise-published) | `b2374a12` | #1301 success; gate 10 phút 00 giây; engine-tests 19 phút 03 giây (success) | #5513 cancelled (1 phút 38 giây) |
| #56 | fix(content): đồng bộ giá tuần/tháng theo bảng giá chủ xe — lô 4/5 (42 bài, revise-published) | `799afb54` | #1302 success; gate 12 phút 05 giây; engine-tests 16 phút 01 giây (success) | #5512 cancelled (0 phút 54 giây) |
| #57 | fix(content): đồng bộ giá tuần/tháng theo bảng giá chủ xe — lô 2/5 (50 bài, revise-published) | `29189f71` | #1303 success; gate 16 phút 44 giây; engine-tests 12 phút 53 giây (success) | #5514 success (10 phút 50 giây) |
| #58 | fix(content): đồng bộ giá tuần/tháng theo bảng giá chủ xe — lô 3/5 (50 bài, revise-published) | `a44a1885` | #1304 success; gate 16 phút 34 giây; engine-tests 18 phút 58 giây (success) | #5515 cancelled (1 phút 33 giây) |

## Quality gate trên HEAD của push vào `main` (FACT)

Mỗi lần merge, workflow Quality gate chạy lại trên đúng commit đã push (`event=push`); đây là bằng chứng gate xanh trên HEAD thật chứ không chỉ trên nhánh PR.

| PR | Commit trên main | Run Quality gate (push) |
|---|---|---|
| #44 | `a89dd8c9` | #1286 success |
| #45 | `002ac9c9` | #1285 success |
| #46 | `3fbc0e45` | #1294 success |
| #47 | `205be933` | — (không kích hoạt: PR chỉ đổi `.md` gốc) |
| #48 | `a11be2e2` | #1291 success |
| #49 | `9a6460d7` | #1297 success |
| #50 | `ea45d355` | #1305 success |
| #51 | `aa8b6d82` | #1299 success |
| #53 | `d794f64b` | #1313 success |
| #54 | `51be40d8` | #1308 success |
| #55 | `b2374a12` | #1310 success |
| #56 | `799afb54` | #1309 success |
| #57 | `29189f71` | #1311 success |
| #58 | `a44a1885` | #1312 success |

Ghi chú về Pages: GitHub hủy run Pages đang chạy khi có commit mới hơn trên `main` (run `cancelled` ở bảng trên không phải lỗi); nội dung mỗi commit được phát hành bởi run thành công kế tiếp.
Run cuối: Pages #5516 (commit main d794f64b, #53): success, 11:43:47 → 11:52:49Z (9 phút 02 giây). Các run Pages #5515 và #5509/#5508/#5511/#5512/#5513 bị GitHub hủy vì có commit mới hơn; nội dung được phát hành bởi run thành công kế tiếp.

## Kiểm tra cục bộ trên bản build đã gộp (FACT)

Jekyll build đầy đủ cây trùng main d794f64b (3.10.0, minima 2.5.1, sitemap, feed): BUILD_EXIT=0, 611 s; 6.844 trang HTML; `check-built-links.py` PASS (0 liên kết nội bộ hỏng); `faq_parity_check.py`: 6.844 trang, 2 trang có FAQ, 0 lỗi; sitemap 6.842 URL; `validate.py --scope chunk` PASS (0 cảnh báo); khối legal-notice 22/22, price-notice 68/68, topic-siblings 107/107 đúng URL, 0 trang thừa.

`check-regressions.py` trên bản dựng cuối: **PASS 9/9** (H1/title/meta/hero/canonical trang chủ khớp bản duyệt; canonical 1 và H1 1 trên mọi trang; 1 favicon; phân trang ≤ 60 liên kết; không `&` trần ở head; breadcrumb mọi bài; hub/pillar ≥ 60 từ giới thiệu; hub có lead block; sitemap 6.842 URL không noindex/404).

Kiểm kê lại từ bản build đã gộp (build-inventory → build-matrix → build-leads → enrich-inventory): DESC_TOO_LONG 4 → 0, H1_IN_BODY 1 → 0, BLOCKED_EVIDENCE_SHA 4 → 0; SLUG_D_STRIPPED 1.410 (không đổi, BLOCKED); CANNIBALIZATION_SUPPORT 58 và NEAR_TITLE_PAIR 64 không đổi về số lượng nhưng 107 bài đã có liên kết cùng chủ đề hai chiều (bài có ≥ 10 liên kết vào: 2.166 → 2.188); FRESHNESS_REVIEW 385 giữ nguyên vì là tín hiệu suy luận từ regex (INFERRED), không phải kết luận sai/đúng; `_data/seo-leads.yml` và matrix-summary không đổi.

## Xác minh live (Nimble Extract, `simplified_html` + `vx6`)

| URL | Kết quả |
|---|---|
| `/` | H1, SEO title, meta description, mô tả hero, canonical khớp từng ký tự `frozen-homepage.json` (bản duyệt 4f61156e) |
| `/robots.txt` | User-agent: *, Allow: /, Sitemap: https://blog.thuexemaynguyentu.com/sitemap.xml |
| `/sitemap.xml` | 6.842 URL duy nhất, trùng hoàn toàn (0 thừa, 0 thiếu) với sitemap của bản build đã gộp mọi PR |
| `/thue-xe/2026/09/30/gia-thue-xe-may-dip-tet-o-ha-noi-co-tang-khong/ (BLG-00943)` | 1 H1, canonical đúng, khối "Giá thuê tham khảo hiện hành" với bảng giá đúng `_data/pricing.yml` và cọc tham khảo 2–5 triệu |
| `/hoi-dap/2026/09/29/i-xe-khong-mu-bao-hiem-phat-bao-nhieu/ (BLG-00874)` | không còn khối giá/khối pháp lý (số 600.000 đ là mức phạt, đã loại khỏi danh sách) |
| `/thue-xe/2026/10/15/di-hoi-cho-trien-lam-nhieu-ngay-o-trung-tam-trien-lam-quoc-gia-dong-anh-dat-thue/ (BLG-03602, lô 1)` | có "tuần 1.000.000 đ"; không còn "tuần 800.000 đ"; 1 H1; canonical đúng |
| `/hoi-dap/2026/10/16/dat-xe-so-roi-muon-doi-sang-xe-ga-truoc-ngay-nhan-nhan-tiem-som-the-nao-de-con-x/ (BLG-04086, lô 3)` | có "theo tuần 1.000.000 đ"; không còn "theo tuần 800.000 đ"; 1 H1; canonical đúng |
| `/hoi-dap/2026/10/16/moi-mua-xe-may-dang-cho-lam-dang-ky-bien-so-thue-xe-tam-vai-ngay-tinh-theo-ngay/ (BLG-04066, lô 5)` | có "ngày; 1.000.000 đồng"; không còn "ngày; 800.000 đồng"; 1 H1; canonical đúng |
| `/an-toan-phap-ly/2026/10/20/ngay-trung-tuyen-ngay-cap-va-thoi-han-in-tren-the-bang-lai-xe-may-doc-dung-tung/ (BLG-05623)` | nêu Thông tư 108/2026; 1 H1; canonical đúng |
| `/an-toan-phap-ly/2026/09/28/bien-bao-cam-xe-may-thuong-gap/` | khối "Lưu ý cập nhật pháp lý" có QCVN 41:2024/BGTVT và liên kết nguồn chính thức (Pages #5510) |
| `/an-toan-phap-ly/2026/10/10/bang-lai-a1-chay-uoc-nhung-xe-nao/ (BLG-01903)` | A1 đến 125 cm3 hoặc 11 kW theo Điều 57 Luật 36/2024/QH15; không còn A2/175 cm3 (Pages #5510) |
| `/an-toan-phap-ly/2026/10/15/va-cham-lien-hoan-nhieu-xe-may-tren-cau-duong-vanh-dai-ha-noi-bao-hiem-tnds-cua/` | khối "Cùng chủ đề trong cẩm nang" với liên kết tới bài cùng nhóm (Pages #5510) |
| `/bang-gia-xe-ga/` | Air Blade 200.000đ/ngày, 1.000.000đ/tuần, 1.500.000đ/tháng; không còn 1.400.000 (Pages #5510) |

## Chưa xác minh được (UNKNOWN)

Thứ hạng, lập chỉ mục và số liệu Search Console của `blog.thuexemaynguyentu.com` (chưa có property trong Windsor/OpenSEO). Không có kết luận nào về hiệu quả xếp hạng được đưa ra.

## Rollback

Mỗi PR là một squash commit độc lập: `git revert <commit merge>`. Với lô revise: `python3 scripts/factory/revise-published.py rollback --backup reports/qa-audit/revise/<batch>.json`
(sao lưu byte-exact; không ghi đè thay đổi của người khác).
