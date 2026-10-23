# Khối "Giá thuê tham khảo hiện hành" (hiển thị bảng giá hiện hành, không đổi nội dung bài)

## Vì sao có
Sau khi đồng bộ bảng giá chủ xe (`_data/pricing.yml`, PR #44) còn một số bài PUBLISHED nêu giá tuần/tháng cũ mà **chưa sửa được nội dung gốc**:
- evidence QA đã lệch hash do đổi domain: sửa gốc phải qua `reattest-legacy-qa.py` có chủ duyệt (kế hoạch `plan`: bản hiện tại còn số tiền cũ nên `FRESH_QA_FAILED`);
- hoặc title/luận điểm của bài gắn với giá cũ (title bất biến: đổi title kéo theo hàng matrix + URL, ngoài phạm vi công cụ `revise-published.py`).

Khối này hiển thị bảng giá hiện hành ở đầu bài để người đọc không bị dẫn sai. **Không đổi một byte nào của bài.**

## Cách hoạt động
- Dữ liệu: `_data/price-notices.json` (`posts[<URL bài>]` → `id`, `kinds` = loại tồn dư). Sinh bởi `scripts/seo/build-price-notices.py`
  (`python3 scripts/seo/build-price-notices.py --report`; `--check` đối chiếu): bài PUBLISHED có evidence mà `price_phrases.find_residual` còn báo giá cũ.
  `EXCLUDE` là các bài đã đọc tay là dương tính giả.
- Template: `_includes/price-notice.html`, gọi từ `_layouts/post.html` trước mục lục. Số liệu lấy **nguyên** từ `_data/pricing.yml` qua
  `_includes/pricing-rate-table.html` (không gõ tay số tiền); trang không có trong dữ liệu thì không in gì; tra khóa O(1) theo `page.url`.
- Kiểm thử: `scripts/factory/tests/test_price_notices.py` (khóa là URL thật của bài PUBLISHED có evidence, `id` khớp matrix, không đặt cho bài đang
  có lease/draft, bộ sinh đúng/idempotent, include đúng một lần trước mục lục, không số tiền gõ tay, không quét `site.posts`).

## Quy tắc vận hành
1. Khi một bài đã được sửa gốc (reattest + `revise-published.py`), chạy lại `build-price-notices.py` để gỡ bài khỏi danh sách.
2. Giá luôn là giá tham khảo, cần xác nhận trước khi đặt xe; không thêm mức giá/cọc/chính sách chưa có trong `_data/pricing.yml` hoặc `data/business-facts.json`.
3. Bài legacy (không evidence) **không** dùng khối này: sửa trực tiếp trong bài.
