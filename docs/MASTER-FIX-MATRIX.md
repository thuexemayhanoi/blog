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
| C4 | Gate chỉ dựa Pages build success | Thiếu CI validator | `.github/workflows/factory-validate.yml`: restore idempotent, report khớp dữ liệu, validate, build, nháp, hub | Chạy workflow thật trên GitHub | Xem mục E cuối file | PENDING |
| A5 | Audit cũ ghi sai định dạng URL legacy (`/blog/YYYY/MM/DD/slug/`) | URL thật do Jekyll sinh gồm tên danh mục có dấu + ngày frontmatter chuẩn hoá UTC: `/blog/kinh nghiệm/2026/09/17/...` | `restore-foundation.py` + `validate.py` ghi đúng quy tắc thật; inventory ghi URL thật | Đối chiếu 483/483 URL với `sitemap.xml` công khai: khớp 100% | Live: mọi URL inventory trả 200 | VERIFIED |
| D1 | Thiếu AGENTS.md; README lỗi thời; docs trùng lặp | Chưa chuẩn hóa | `AGENTS.md`, `README.md`, docs cập nhật; `docs/mistral/README.md` thành con trỏ | Đọc lại | N/A | VERIFIED |

## E. Kiểm tra live sau deploy (cập nhật sau khi Pages deploy xong)

Trạng thái: PENDING cho tới khi kiểm tra live xong. Các URL sẽ kiểm: trang chủ, `/blog/chu-de/`, 7 hub cha, 39 hub con, bài đại diện, sitemap.

## Mục tiêu tiếp theo (không tự thực hiện khi chưa được giao)

1. Chủ xe quyết định matrix (cấp bản gốc hoặc duyệt tái sinh mới).
2. Chủ xe quyết định 3 mục chính sách BLOCKED trong `reports/factory/policy-conflicts.md`.
3. Đọc nội dung 10 bài REVIEW theo cặp để xử lý cannibalization.
4. Khi có matrix: chạy 1 chunk ≤ 10 bài chứng minh chu trình đầy đủ.
5. GSC/post-publish tracking: TODO/NOT IMPLEMENTED (chưa có quyền truy cập).
