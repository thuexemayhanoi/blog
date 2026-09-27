# RECOVERY — phục hồi sự cố

## Chạy mới bắt đầu bằng

1. `git fetch` HEAD mới nhất; đọc README.md, docs/mistral/README.md.
2. Đọc trạng thái theo thứ tự: `data/state/transaction.json` → `data/state/checkpoint.json` → `data/state/writer-lock.json` → `reports/factory/progress.json`.

## Transaction treo (`active: true`)

- Đọc `pending`: nêu rõ bước đang dở (VD: "đã push bài, chưa cập nhật matrix").
- Đối chiếu repository thật: bài đã tồn tại trên main chưa? Matrix đã cập nhật chưa?
- Hoàn tất đúng theo sự thật: nếu bài đã push mà matrix chưa cập nhật → cập nhật matrix/report/checkpoint rồi đóng transaction. Nếu chưa push gì → hủy transaction, trả hàng về PLANNED.
- Không bao giờ nhận chunk mới khi còn transaction treo.

## Lock treo (`locked: true` nhưng chủ không hoạt động)

- Kiểm tra `expires_at` đã quá hạn và không có commit mới của chủ lock → ghi đè lock với `holder` mới, ghi rõ lý do vào `note` + thời điểm.

## Chunk dở

- Dùng checkpoint `last_completed_article_id` + ma trận: các hàng `WRITING`/`QA` trong chunk → hoàn tất trước khi nhận chunk mới.

## Conflict Git / push bị từ chối

- Fetch lại, rebase phần việc của mình; nếu xung đột với matrix/state → lấy phiên bản remote làm chuẩn, việc mình đang làm đối chiếu lại theo ID. Không force push.

## Sai số ma trận

Chạy `python3 scripts/factory/validate.py` (từ gốc repository). Nếu ma trận thiếu/hỏng: KHÔNG tự sinh lại toàn bộ; khôi phục từ lịch sử git commit gần nhất còn hợp lệ. Hiện ma trận BLOCKED (chưa từng được commit): xem `reports/factory/matrix-recovery-blocked.md`, không tạo matrix mới rồi gọi là khôi phục.

## Bài đã push nhưng Pages build lỗi

- Không tạo commit README-only. Sửa đúng tệp nguồn gây lỗi (frontmatter, Liquid, permalink) và push lại; xác nhận build/deploy thật.

## Báo cáo sau khi phục hồi

Ghi vào `reports/factory/latest.md`: nguyên nhân, hành động, HEAD mới, trạng thái build/deploy, các kiểm tra runtime đã làm.
