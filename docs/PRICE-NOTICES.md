# Khối "Giá thuê tham khảo hiện hành" (hiển thị bảng giá hiện hành, không đổi nội dung bài)

## Vì sao có
Sau khi đồng bộ bảng giá chủ xe (`_data/pricing.yml`, PR #44) còn một số bài PUBLISHED nêu giá tuần/tháng cũ mà **chưa sửa được nội dung gốc**:
- evidence QA đã lệch hash do đổi domain: sửa gốc phải qua `reattest-legacy-qa.py` có chủ duyệt (kế hoạch `plan`: bản hiện tại còn số tiền cũ nên `FRESH_QA_FAILED`);
- hoặc title/luận điểm của bài gắn với giá cũ (title bất biến: đổi title kéo theo hàng matrix + URL, ngoài phạm vi công cụ `revise-published.py`).

Khối này hiển thị bảng giá hiện hành ở đầu bài để người đọc không bị dẫn sai. **Không đổi một byte nào của bài.**

## Cách hoạt động
- Dữ liệu: `_data/price-notices.json` (`posts[<URL bài>]` → `id`, `kinds` = loại tồn dư). Sinh bởi `scripts/seo/build-price-notices.py`
  (`python3 scripts/seo/build-price-notices.py --report`; `--check` đối chiếu): bài PUBLISHED có evidence mà `price_phrases.find_residual` còn báo giá cũ.
  `EXCLUDE` là các bài đã đọc tay là dương tính giả (số không phải giá thuê, hoặc câu chỉ còn là phép tính đúng từ giá ngày/giá hiện hành, ví dụ
  "bảy ngày là 1,4 triệu" = 7 × 200.000đ). `check-price-consistency.py` ghi cột `disposition` cho bài factory: `NOTICE_LAYER` (bài có khối này) hoặc
  `REVIEWED_FALSE_POSITIVE` (bài trong `EXCLUDE`); cụm không có nhãn là việc còn phải xử lý.
- Template: `_includes/price-notice.html`, gọi từ `_layouts/post.html` trước mục lục. Số liệu lấy **nguyên** từ `_data/pricing.yml` qua
  `_includes/pricing-rate-table.html` (không gõ tay số tiền); trang không có trong dữ liệu thì không in gì; tra khóa O(1) theo `page.url`.
- Kiểm thử: `scripts/factory/tests/test_price_notices.py` (khóa là URL thật của bài PUBLISHED có evidence, `id` khớp matrix, không đặt cho bài đang
  có lease/draft, bộ sinh đúng/idempotent, include đúng một lần trước mục lục, không số tiền gõ tay, không quét `site.posts`).

- Bộ quét (`price_phrases.py`, sửa 2026-10-29): cụm số đứng ngay sau chữ "cọc" (tính từ con số gần nhất phía trước, không có kỳ hạn chen sau chữ "cọc")
  là TIỀN CỌC, không kế thừa kỳ hạn "tháng/tuần" của câu — trước đây "…900.000–1.200.000 đồng một tháng, cọc 2.000.000–3.000.000 đồng" bị báo
  MISMATCH giả và bài mới đúng giá bị đưa vào khối đính chính. Hồi quy: `test_price_phrases.py`.

## Quy tắc vận hành
1. Khi một bài đã được sửa gốc (reattest + `revise-published.py`), chạy lại `build-price-notices.py` để gỡ bài khỏi danh sách.
2. Giá luôn là giá tham khảo, cần xác nhận trước khi đặt xe; không thêm mức giá/cọc/chính sách chưa có trong `_data/pricing.yml` hoặc `data/business-facts.json`.
3. Bài legacy (không evidence) **không** dùng khối này: sửa trực tiếp trong bài.
