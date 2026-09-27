# SCHEMA / GEO — dữ liệu có cấu trúc và tối ưu công cụ tìm kiếm AI

Mục tiêu: schema khớp nội dung thật; không bịa review/rating; không hứa thứ hạng.

Nguồn chuẩn: `_includes/seo.html` (WebSite, Organization, LocalBusiness, BlogPosting, BreadcrumbList), `data/business-facts.json`.

## Quy tắc

- LocalBusiness/Organization: chỉ NAP đã xác minh của /blog (điện thoại, địa chỉ, giờ 09:00–21:00). Không sao chép dữ liệu của shop.
- KHÔNG thêm aggregateRating/review nếu không có đánh giá thật, có nguồn công khai. Tính đến lần kiểm kê này: KHÔNG có đánh giá thật → cấm thêm.
- BlogPosting: title/description/date/canonical phải trùng render thật.
- BreadcrumbList: khớp breadcrumb hiển thị (Trang chủ → Cẩm nang → Parent → Child).
- GEO (trả lời của công cụ AI): nội dung trả lời trực tiếp câu hỏi người dùng ở đoạn đầu bài; khẳng định có nguồn (đặc biệt pháp lý); không khẳng định suông "tốt nhất/uy tín số 1".

## Kiểm tra

Sau build: lấy schema từ trang live, đối chiếu từng trường với dữ liệu chuẩn. Lệch → sửa `_includes/seo.html` hoặc frontmatter, không sửa tay JSON trong bài.

Xử lý lỗi: schema sai NAP hoặc bịa rating → coi là critical failure → sửa trước khi xuất bản bài mới.

TODO/NOT IMPLEMENTED: chưa kiểm tra qua Rich Results Test trong lần chạy này (NOT VERIFIED).
