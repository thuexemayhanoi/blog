# SCHEMA / GEO — dữ liệu có cấu trúc và tối ưu công cụ tìm kiếm AI

Mục tiêu: schema khớp nội dung thật; không bịa review/rating; không hứa thứ hạng.

Nguồn chuẩn: `_includes/seo.html` (WebSite, Organization, LocalBusiness, BlogPosting, BreadcrumbList), `data/business-facts.json`.

## Quy tắc

- LocalBusiness/Organization: chỉ NAP đã xác minh của /blog (điện thoại, địa chỉ, giờ 09:00–21:00). Không sao chép dữ liệu của shop.
- KHÔNG thêm aggregateRating/review nếu không có đánh giá thật, có nguồn công khai. Tính đến lần kiểm kê này: KHÔNG có đánh giá thật → cấm thêm.
- BlogPosting: title/description/date/canonical phải trùng render thật.
- BreadcrumbList: khớp breadcrumb hiển thị (Trang chủ → Cẩm nang → Parent → Child). Mọi loại trang (bài, hub, topic, danh sách, trang tĩnh) phát BreadcrumbList từ CÙNG biến với breadcrumb hiển thị.
- FAQPage: CHỈ qua component dùng chung `_includes/faq.html` (xem `docs/FAQ-COMPONENT.md`); không có FAQPage nếu không có khối hỏi–đáp hiển thị, và JSON-LD luôn == nội dung hiển thị (CI kiểm). FAQPage không bảo đảm rich result/AI Overviews (Google đã ngừng hiển thị FAQ rich result từ 2026-05-07); giá trị chính là khối hỏi–đáp rõ ràng cho người đọc.
- Mọi chuỗi chèn vào JSON-LD đi qua `jsonify` rồi thay `</` bằng `<\/` (jsonify không escape `</`); `priceRange` lấy từ `_data/pricing.yml`.
- GEO (trả lời của công cụ AI): nội dung trả lời trực tiếp câu hỏi người dùng ở đoạn đầu bài; khẳng định có nguồn (đặc biệt pháp lý); không khẳng định suông "tốt nhất/uy tín số 1".

## Kiểm tra

Sau build: lấy schema từ trang live, đối chiếu từng trường với dữ liệu chuẩn. Lệch → sửa `_includes/seo.html` hoặc frontmatter, không sửa tay JSON trong bài.

Tự động trong CI: `scripts/faq/faq_parity_check.py --site ./_site` kiểm MỌI khối JSON-LD trên site build đều parse được và FAQPage khớp khối hiển thị.

Xử lý lỗi: schema sai NAP hoặc bịa rating → coi là critical failure → sửa trước khi xuất bản bài mới.

TODO/NOT IMPLEMENTED: chưa kiểm tra qua Rich Results Test trong lần chạy này (NOT VERIFIED).
