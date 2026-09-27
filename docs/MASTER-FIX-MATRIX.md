# MASTER FIX MATRIX — theo dõi lỗi và trạng thái

Mỗi hàng: lỗi → nguyên nhân → tệp/commit sửa → kiểm thử → kết quả live → trạng thái. Trạng thái: VERIFIED / NOT VERIFIED / BLOCKED. Cập nhật sau mỗi lần chạy; không ghi PASS khi chưa kiểm tra.

| # | Lỗi | Nguyên nhân | Tệp/commit sửa | Kiểm thử | Kết quả live | Trạng thái |
|---|---|---|---|---|---|---|
| A1 | `data/content-matrix.csv` thiếu dù report cũ ghi "10.000 hàng" | Tệp sinh lúc bootstrap chưa bao giờ được commit; không có trong lịch sử git, nhánh, hay `data/state/foundation-seed/` (thư mục này cũng không tồn tại) | Không thể sửa bằng cách tạo matrix mới. Bằng chứng + phương án: `reports/factory/matrix-recovery-blocked.md` | `list_commits` đường dẫn: 0 kết quả; 20 ID ví dụ đối chiếu khớp ánh xạ tái tạo | N/A | BLOCKED (chờ chủ xe cấp bản gốc hoặc duyệt tái sinh matrix mới) |
| A2 | `data/content-taxonomy.json` thiếu | Chưa commit khi bootstrap | `scripts/factory/restore-foundation.py` sinh từ seed `data/state/taxonomy-config.json` | `validate.py`: 7 parent/51 child, ID/slug khớp seed 100% | Không ảnh hưởng giao diện | VERIFIED |
| A3 | `data/content-inventory.csv` thiếu | Chưa commit khi bootstrap | `restore-foundation.py` sinh từ `data/state/existing-map.json` + `_posts/` | 483/483 bài ánh xạ, URL giữ nguyên, counts theo parent khớp report cũ | Không ảnh hưởng giao diện | VERIFIED |
| A4 | `validate.py` crash `FileNotFoundError` khi thiếu file; report ghi số tay | Validator đọc thẳng không kiểm tra tồn tại | Viết lại `scripts/factory/validate.py`: báo thiếu rõ ràng, mã 0/1/2; `generate-reports.py` sinh report từ dữ liệu thật | Chạy thật: PASS các phần nền, BLOCKED matrix (exit 2), manifest.py exit 2 rõ ràng | N/A | VERIFIED |
| B1 | Hub cha/hub con trống bài (mapping không hoạt động) | `_data/factory-taxonomy.yml`, `_data/factory-map.yml` không tồn tại; layout đọc `site.data.factory-*` | Sinh 2 tệp `_data` từ seed; thêm bước CI kiểm tra | `validate.py` + build trong CI | Xem mục E cuối file | VERIFIED |
| B2 | Lookup mapping bài legacy luôn rỗng | `post.url | split: '/' | last` trả chuỗi rỗng với URL có dấu `/` cuối | `_layouts/hub.html`, `_layouts/topic.html`: dùng `post.slug` | CI build kiểm hub render số bài | Xem mục E cuối file | VERIFIED |
| B3 | 39 link trong `chu-de.md` thiếu baseurl → 404 ở domain gốc | Link viết cứng `/thue-xe/...` không qua `relative_url` | `chu-de.md`: toàn bộ link qua `relative_url`; thêm đúng một H1 | Đếm link qua `grep`; CI build kiểm tra `_site/chu-de/index.html` chứa `/blog/thue-xe/gia-thue` | Xem mục E cuối file | VERIFIED |
| B4 | Thiếu H1 ở `/blog/chu-de/` | Layout `default` không render H1, trang không tự có | `chu-de.md`: thêm `# Tất cả chủ đề cẩm nang` (duy nhất) | Render check trong CI build | Xem mục E cuối file | VERIFIED |
| B5 | 7 child hub có bài nhưng không có trang công khai (Honda Wave/Vision/Air Blade/Click, Biển báo, Ngoại thành, Cung đường nội thành) | Chưa tạo trang hub lúc bootstrap | Tạo 7 trang `layout: topic` đúng permalink taxonomy | `validate.py` WARN=0 | Xem mục E cuối file | VERIFIED |
| B6 | H1 parent hub hiển thị slug thô ("thue-xe") | Title frontmatter dùng slug làm tiền tố | Sửa title 6 trang hub cha thành tên chủ đề tiếng Việt | Đọc lại frontmatter | Xem mục E cuối file | VERIFIED |
| C1 | Validator queue cũ chỉ nhận `NNN-slug.md`; "skipped" bị hiểu là PASS toàn `_posts` | Hai campaign trộn lẫn | Tách trong `docs/CONTENT-FACTORY.md`, `AGENTS.md`, `reports/factory/policy-conflicts.md`; CI factory riêng | Đọc docs + CI | N/A | VERIFIED |
| C2 | Xung đột chính sách nội bộ (cọc 2–5 triệu, phí trễ 20k/giờ chỉ có trong validator cũ) | Hai nguồn fact khác nhau trong /blog | `reports/factory/policy-conflicts.md`: ghi từng nguồn, BLOCKED, không tự chọn | Đối chiếu 3 nguồn | N/A | BLOCKED (chờ chủ xe quyết định) |
| C3 | Không có vùng nháp không deploy | Chưa có `_drafts/` | Tạo `_drafts/` + mẫu; CI build chứng minh nháp không vào sitemap/output | CI build + grep | Xem mục E cuối file | VERIFIED |
| C4 | Gate chỉ dựa Pages build success | Thiếu CI validator | `.github/workflows/factory-validate.yml`: restore idempotent, report khớp dữ liệu, validate, build, nháp, hub | Chạy workflow thật trên GitHub | Run 36299837072 tại HEAD 1bb9f129c9: mọi bước bằng chứng SUCCESS; chỉ "Validate foundation" fail đúng chủ đích vì matrix BLOCKED | VERIFIED (đỏ có chủ đích, không bị che) |
| A5 | Audit cũ ghi sai định dạng URL legacy (`/blog/YYYY/MM/DD/slug/`) | URL thật do Jekyll sinh gồm tên danh mục có dấu + ngày frontmatter chuẩn hoá UTC: `/blog/kinh nghiệm/2026/09/17/...` | `restore-foundation.py` + `validate.py` ghi đúng quy tắc thật; inventory ghi URL thật | Đối chiếu 483/483 URL với `sitemap.xml` công khai: khớp 100% | Live: mọi URL inventory trả 200 | VERIFIED |
| D1 | Thiếu AGENTS.md; README lỗi thời; docs trùng lặp | Chưa chuẩn hóa | `AGENTS.md`, `README.md`, docs cập nhật; `docs/mistral/README.md` thành con trỏ | Đọc lại | N/A | VERIFIED |

## E. Kiểm tra live sau deploy — kết quả thật tại HEAD 1bb9f129c9

Pages deploy run 36299836303: success. Factory validate run 36299837072: các bước bằng chứng đều SUCCESS; chỉ bước "Validate foundation" thất bại đúng chủ đích (matrix BLOCKED, exit 2).

Kiểm tra live ngày 27/09/2026, tất cả trả 200:

- Trang chủ `/blog/`, `/blog/chu-de/` (H1 "Tất cả chủ đề cẩm nang" render đúng, link có tiền tố `/blog/`).
- 7 hub cha: thue-xe, kinh-nghiem, an-toan-phap-ly, cung-duong, du-lich và 2 hub còn lại — H1 hiển thị tên chủ đề tiếng Việt, không còn slug thô.
- Hub con mới tạo: `/blog/xe-may/honda-wave/` (H1 "Honda Wave", bài `2026/09/18/thue-honda-wave-o-ha-noi` render trong danh sách), `/blog/an-toan-phap-ly/bien-bao/`, `/blog/du-lich/ngoai-thanh/`, `/blog/cung-duong/cung-duong-noi-thanh/`.
- Bài legacy URL định dạng thật: `/blog/du%20l%E1%BB%8Bch/2026/09/13/goi-y-kham-pha-ha-noi-bang-xe-may-cho-nguoi-moi/` → 200.
- `sitemap.xml`: 544 loc, 483 URL bài, không có `_drafts` (grep `mau-nhap-bai-moi` = 0).

Không kiểm được trong lần này (không có môi trường): Safari/iPhone thực, Lighthouse/Core Web Vitals đo thật — NOT VERIFIED.

## F. Đợt sửa 2026-09-27 (matrix TẠO MỚI + UI/UX + publish gate + chunk chạy thật)

| ID | Lỗi | Nguyên nhân | Sửa | Kiểm thử | Kết quả live | Trạng thái |
|---|---|---|---|---|---|---|
| F1 | Matrix bị mất vĩnh viễn, không nhận được hàng nào | Bản gốc không từng commit, không khôi phục được | Chủ xe duyệt TẠO MỚI: 833 hàng = 473 EXISTING + 10 REVIEW (giữ nguyên) + 350 PLANNED; sinh từ `matrix-seed.json` + taxonomy + inventory; ghi rõ TẠO MỚI không phải khôi phục | `generate-matrix.py` chống trùng máy (id/slug/canonical/output_path/intent/keyword) tất cả PASS; CI bước matrix idempotent SUCCESS; chạy lại không mất trạng thái PUBLISHED | N/A (dữ liệu) | VERIFIED |
| F2 | Chênh chỉ tiêu: seed chỉ có 350 hàng có giá trị riêng so với planned_target 6.570 | Không đủ chủ đề thật | BÁO THIẾU 6.220 hàng, không đệm hàng rỗng/nhân bản (điều cấm) | `matrix-report.md` ghi rõ từng child | N/A | BÁO THIẾU (chủ động, đúng yêu cầu) |
| F3 | `generate-reports.py` ghi đè checkpoint, published=0, updated_at lấy ngày bài cũ | Script v1 không đọc matrix | v2: đếm trạng thái thật từ matrix, preserve chunk/last_completed/transaction/lock, updated_at tách riêng | `test_reports_resume.py` PASS; chạy thật: last_completed=BLG-00493, planned=347, published=3, không reset | N/A | VERIFIED |
| F4 | UI trang chủ đề: chữ sát mép, danh sách link dài, không H1 phân cấp | `chu-de.md` xuất markdown thô không có container; `topic-list` không có CSS | Viết lại `chu-de.md` + `_includes/topic-directory.html`: card theo nhóm cha với SVG, hàng bấm ≥44px, grid 1/2/3 cột, `details/summary` (không cần JS), số bài thật từ `factory-parents.yml`/bài đã đăng, "Chưa có bài" cho nhóm trống; CSS `components.css`/`responsive.css` đồng bộ dark/light; nút nổi: z-index chuẩn + `env(safe-area-inset-bottom)` + padding cuối trang | DOM live: `topic-card`=77, `topic-row`=204, `<details>`=14, H1 "Tất cả chủ đề cẩm nang" render, không tràn ngang theo CSS (max-width, margin 16-20px) | VERIFIED (phân tích DOM/CSS; ảnh chụp màn hình và trình duyệt thật KHÔNG làm được trong môi trường này — NOT VERIFIED) |
| F5 | Publish chỉ là hướng dẫn văn bản, không có gate cứng | Chưa có script | `scripts/factory/publish-gate.py`: kiểm matrix PASS + `data/qa/<id>.json` (quality≥90, seo≥90, business PASS, legal PASS/NOT_REQUIRED, không critical failure) + lock/transaction; tự chốt ngày thật vào URL, cập nhật checkpoint | Gate từ chối hàng PLANNED (chạy thật, exit 1); `test_publish_gate.py` PASS: từ chối thiếu bằng chứng/điểm thấp/business FAIL; dry-run không đổi gì | N/A | VERIFIED |
| F6 | Chưa chứng minh chu trình đầy đủ | Matrix trước đó BLOCKED | Chunk thật 3 bài (≤10): BLG-00484 (bảng giá theo loại xe), BLG-00485 (yếu tố ảnh hưởng giá), BLG-00493 (so sánh báo giá) — cùng C-THUE-GIA, không trùng intent, chỉ dùng số từ `_data/pricing.yml`; cọc/phí trễ/phí giao xe ghi "cần xác nhận trực tiếp" (policy BLOCKED) | 3 file `data/qa/*.json` đầy đủ; gate promote 3/3; checkpoint last_completed=BLG-00493, next_claimable=BLG-00486 | 3 URL /blog/thue-xe/2026/09/27/... trả 200; hub /blog/thue-xe/gia-thue/ hiển thị 3 bài; sitemap 547 loc (+3, không có draft); canonical đúng | VERIFIED |
| F7 | `_posts` factory làm lệch inventory/legacy check | Bài mới mang `article_id` không nằm trong existing-map | `restore-foundation.py` + `validate.py` tách legacy/factory; validate kiểm chứng bài factory = hàng matrix PUBLISHED (tệp, output_path, không còn `{date}`) | Validate exit 0; kiểm chứng âm: thêm `_posts` giả với `article_id` không hợp lệ → validate FAIL đúng, xóa đi → PASS | N/A | VERIFIED |
| F8 | CI đỏ ở bước Generate matrix sau promote | `generate-matrix.py` v1 đếm cả bài factory + reset trạng thái PUBLISHED | v2: bỏ bài factory khỏi đếm legacy; tái sinh giữ nguyên trạng thái runtime (PUBLISHED/ngày thật) | Matrix CSV tái sinh giống hệt tệp đã commit (byte-identical); CI run 36301726800 toàn bộ bước SUCCESS, validate exit 0 — XANH lần đầu | N/A | VERIFIED |

### Kiểm tra live tại HEAD 1849593f17 (đợt này)

- Factory validate run 36301726800: SUCCESS toàn bộ (validate exit 0). Pages build run 36301726576: success.
- 3 URL bài mới trả 200; sitemap 547 loc, +3 URL mới, không draft; hub C-THUE-GIA render 3 bài; chu-de render 77 topic-card / 204 topic-row / 14 details.
- KHÔNG kiểm được: Safari/iPhone thật, Lighthouse/CWV đo thật, ảnh chụp màn hình trước/sau — NOT VERIFIED (môi trường không có trình duyệt).

## Mục tiêu tiếp theo (không tự thực hiện khi chưa được giao)

1. Chủ xe quyết định 3 mục chính sách BLOCKED trong `reports/factory/policy-conflicts.md` (cọc/phí trễ/bảo hiểm).
2. Đọc nội dung 10 bài REVIEW theo cặp để xử lý cannibalization.
3. Mở rộng `matrix-seed.json` thêm chủ đề thật cho 6.220 hàng còn thiếu khi có yêu cầu.
4. GSC/post-publish tracking: TODO/NOT IMPLEMENTED (chưa có quyền truy cập).
5. Lighthouse/CWV, Safari/iPhone: chưa có môi trường đo.
