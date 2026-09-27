# Báo cáo xung đột chính sách nội bộ (policy conflicts)

Ngày: 2026-09-27. Phạm vi: `data/business-facts.json`, `docs/ARTICLE-RULES.md`, `scripts/validate-queue.js` (validator campaign cũ hanoi-seo-480). Quy tắc: giữ dữ liệu /blog, ghi rõ từng nguồn, KHÔNG tự chọn/bịa chính sách. Mục chưa giải quyết → BLOCKED.

## Nguồn đối chiếu

- A = `data/business-facts.json` (commit 2bc2999d, nguồn gốc `_data/business.yml` + `_data/pricing.yml`).
- B = `docs/ARTICLE-RULES.md` (commit 2bc2999d).
- C = `scripts/validate-queue.js` (campaign cũ, ghi "Source of truth: git-hub-maintainer-v-2 Knowledge (OWNER-APPROVED facts)").

## Xung đột chưa giải quyết — BLOCKED với writer

### 1. Tiền đặt cọc — BLOCKED

- A: `deposit: "Xác nhận trực tiếp"` cho mọi dòng xe; `content_rules`: "Không bịa con số nào ngoài các giá đã duyệt". Không có khoảng số cọc nào.
- B: "Tiền đặt cọc: 'cần xác nhận trực tiếp', không nêu con số."
- C: "Deposit: 2.000.000–5.000.000 VND depending on vehicle/case. NOT 1–3 million." và gate `DEPOSIT_ENDPOINTS = {'2.000.000','5.000.000'}`.

Xung đột trực tiếp giữa A/B và C. `_data/pricing.yml` (mà A trích làm nguồn) không có khoảng cọc. Cho tới khi chủ xe quyết định, bài factory MỚI phải theo A/B (không nêu số cọc). Không dùng khoảng 2–5 triệu của C vì nó không có trong nguồn chuẩn hiện tại của /blog.

### 2. Phí trả xe trễ — BLOCKED

- A: không có trường phí trễ; `content_rules` cấm con số ngoài giá đã duyệt.
- B: im lặng.
- C: "Late return: 20.000 VND per late hour. More than 6 hours late may add one additional full rental day, approx. 150.000–200.000 VND" và gate `APPROVED_LATE_AMOUNTS = {'20.000','150.000','200.000'}`.

Xung đột: C duyệt số mà A cấm. Bài mới KHÔNG nêu phí trễ cho tới khi chủ xe xác nhận.

### 3. Bảo hiểm cho người thuê — BLOCKED (một chiều)

- A, B: im lặng.
- C: "Nguyễn Tú does NOT provide motorbike insurance to renters."

C là nguồn duy nhất trong /blog cho khẳng định này. Không được đưa vào bài mới với tư cách "đã kiểm chứng" cho tới khi chủ xe xác nhận lại; nếu viết, phải theo hình thức "hỏi Nguyễn Tú trước khi đặt xe".

### 4. Giữ giấy tờ tùy thân / mũ bảo hiểm / hoàn tiền — BLOCKED (một chiều)

- A, B: im lặng (B chỉ nói đặt cọc nói chung).
- C: cấm khẳng định giữ giấy tờ, cấm khẳng định kèm mũ bảo hiểm (trừ dạng "nên hỏi"), cấm hứa hoàn tiền thời gian chưa dùng.

Quy tắc C là quy tắc cấm-bịa, nhất quán với tinh thần A ("cấm bịa"). Áp dụng như quy tắc an toàn khi viết: không khẳng định, dùng dạng "xác nhận trước".

## Các điểm NHẤT QUÁN (không xung đột)

- Giá thuê đã duyệt (Wave 150k/ngày; Vision 200k/ngày, 800k–1tr/tuần, 1,8–2tr/tháng; Air Blade 200k/ngày, 800k/tuần, 1,4tr/tháng; Click/Mio 150k/ngày, 600–700k/tuần, 1–1,2tr/tháng; xe điện/xe đạp điện/50cc: liên hệ): A và C khớp.
- Không khuyến mại, không 24/7, không cam kết, không đánh giá bịa: A và C khớp.
- Điện thoại 0942 467 674, địa chỉ 112 Nguyễn Văn Cừ, giờ 09:00–21:00, không giao xe ngoài giờ: A và C khớp.
- Không phí giao xe cố định: A (`delivery.fixed_fees: null`) và C khớp; `_data/pricing.yml` phần phí giao bị comment.

## Phân biệt hai chế độ kiểm tra (quan trọng)

- C (`scripts/validate-queue.js`) CHỈ áp dụng cho tệp dạng `NNN-slug.md` trong `_queue/` của campaign cũ hanoi-seo-480. Queue hiện rỗng bài; kết quả "skipped" KHÔNG thể dùng để tuyên bố `_posts` PASS.
- Bài factory mới và bài legacy kiểm tra bằng `scripts/factory/validate.py` + gate trong `docs/CONTENT-FACTORY.md`.
- Hai chế độ không thay thế nhau. Không hạ gate này để lấy PASS của gate kia.

## Việc cần quyết định của chủ xe

1. Khoảng đặt cọc 2–5 triệu (nguồn C) có còn đúng không, và có đưa vào `data/business-facts.json` không?
2. Phí trễ 20.000đ/giờ (nguồn C) có còn đúng không?
3. Có cung cấp mũ bảo hiểm / bảo hiểm cho người thuê không?

Cho tới khi có trả lời: các mục 1–3 ở trên là BLOCKED cho nội dung mới.
