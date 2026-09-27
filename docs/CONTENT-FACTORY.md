# CONTENT FACTORY — quy trình vận hành

## Kiến trúc

- `data/content-matrix.csv` — ma trận canonical 10.000 hàng, đúng một lần duy nhất, ID ổn định `BLG-00001..BLG-10000`.
- `data/content-taxonomy.json` — taxonomy máy đọc được: 7 parent hub, 51 child hub, ID ổn định (`P-*`, `C-*`).
- `data/content-inventory.csv` — kiểm kê 483 bài legacy, mọi bài đều đã ánh xạ vào taxonomy, URL giữ nguyên.
- `data/state/` — `checkpoint.json`, `writer-lock.json`, `transaction.json`.
- `reports/factory/` — `progress.json`, `latest.md`, `content-hierarchy.md`, `inventory-summary.md`, `business-fact-conflicts.md`.
- `scripts/factory/` — `manifest.py` (sinh manifest mỗi bài), `validate.py` (validator nền tảng).
- `data/state/foundation-seed/` — dữ liệu gốc đã dùng để bootstrap (chỉ để tra cứu, không chỉnh sửa).

## Batches

200 batch × 50 hàng (`BATCH-001..BATCH-200`), gán theo ID tăng dần. Một chunk chạy tối đa 10 bài. Batch trộn đủ loại chủ đề, không gom toàn bộ bài pháp lý vào một batch.

## Vòng lặp sản xuất mỗi chunk

WRITE/REPAIR → ARTICLE QUALITY SCORE → SEO SCORE BEFORE → SAFE OPTIMIZATION → SEO SCORE AFTER → BUSINESS FACT CHECK → LEGAL/SOURCE CHECK → CANNIBALIZATION CHECK → PUBLISH (chỉ bài đủ điều kiện) → POST-PUBLISH AUDIT → UPDATE MATRIX → UPDATE REPORTS → CHECKPOINT.

## Transaction an toàn

1. Trước khi mutate: ghi `data/state/transaction.json` (`active: true`, mô tả bước).
2. Sau khi xong: cập nhật matrix/report/checkpoint, rồi đóng transaction (`active: false`).
3. Chạy sau thấy `active: true`: recover/hoàn tất giao dịch đó TRƯỚC, không nhận việc mới.

## Lock

- Lấy lock (`locked: true`, `holder`, `acquired_at`, `expires_at`) trước khi nhận chunk; nhả lock khi checkpoint xong. Không bao giờ hai writer trên cùng ID.

## Self-healing (thứ tự ưu tiên)

1. Pending transaction (recover trước hết)
2. Chunk chưa hoàn tất
3. Hàng REPAIR
4. Hàng REVIEW (hiện có 10 hàng legacy REVIEW do trùng cannibalization_key — so sánh nội dung, đề xuất merge/redirect nội bộ, KHÔNG đổi URL legacy)
5. POST_AUDIT quá hạn, LEGAL/FRESHNESS quá hạn
6. Hàng PLANNED mới theo `batch_id` tăng dần

## Tiêu chí dừng an toàn

Runtime gần giới hạn, CI lỗi, transaction không thể hòa giải, conflict Git, business fact không kiểm chứng được, legal claim không kiểm chứng được, hay QA hỏng hệ thống: hoàn tất bước an toàn hiện tại → checkpoint → reports → nhả lock (nếu an toàn) → chỉ push phần xanh.

## Hoàn tất factory

Khi không còn hàng actionable: không tạo việc mới, không restart hàng đã xong, không dựng lại ma trận, ghi báo cáo tổng kết rồi thoát sạch.

## Báo cáo mỗi lần chạy

- MAIN HEAD (SHA), GitHub Pages run ID, BUILD status, DEPLOY status.
- Tệp thực sự thay đổi; kiểm tra runtime đã làm (URL công khai, mobile 390px, menu/footer/breadcrumb, calculator/chatbot).
- Không hủy chỉ vì "build thành công": phải kiểm tra runtime thật.

## Không tạo nội dung rác

Mỗi hàng PLANNED là một ý định tìm kiếm hoặc vấn đề người dùng riêng biệt. Không quay tiêu đề, không doorway spam, không lấp đầy số lượng. Nếu thiếu chủ đề chất lượng, cải thiện taxonomy thay vì hạ chuẩn.
