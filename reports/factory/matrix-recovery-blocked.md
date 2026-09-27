# BLOCKED — khôi phục data/content-matrix.csv

Ngày: 2026-09-27. Kết luận: KHÔNG THỂ khôi phục ma trận 10.000 hàng từ bất kỳ nguồn nào hiện được truy cập.

## Bối cảnh

Commit nền tảng `2bc2999d58ad018b75b16c9620e7af391595868f` ghi trong `reports/factory/latest.md` (bản cũ): "Ma trận: 10,000/10,000 hàng". Thực tế repository main không chứa tệp này.

## Bằng chứng đã kiểm tra

1. `data/content-matrix.csv` không tồn tại trên `main`.
2. Lịch sử git của đường dẫn `data/content-matrix.csv`: 0 commit (toàn bộ 183+ commit đã rà).
3. Nhánh khác: chỉ có `img-binary-test`, `service-images` (nhánh hình ảnh), không chứa dữ liệu matrix.
4. `data/content-taxonomy.json`, `data/content-inventory.csv` cũng chưa từng được commit (0 commit trên đường dẫn).
5. `docs/CONTENT-FACTORY.md` nhắc `data/state/foundation-seed/` ("dữ liệu gốc đã dùng để bootstrap") nhưng thư mục này không tồn tại trên main và không có trong lịch sử git.
6. Không có artifact/checkpoint nào khác trong phạm vi được phép truy cập chứa bản sao matrix.

## Phần KHÔNG thể khôi phục

10.000 hàng matrix gồm 483 hàng legacy (473 EXISTING + 10 REVIEW) và 9.517 hàng PLANNED. Với hàng PLANNED, các trường `title`, `primary_keyword`, `secondary_keywords`, `audience`, `internal_links`... đã được sinh bằng generator không được commit. Seed `data/state/taxonomy-config.json` chứa `pools`, `templates`, `quota` (chỉ tiêu số hàng) nhưng KHÔNG chứa kết quả sinh ra, và không có script generator + seed random nào để tái tạo đúng từng hàng. Tự sinh lại các hàng PLANNED là TẠO MA TRẬN MỚI, không phải khôi phục — bị cấm theo quy định hiện hành khi chưa có duyệt của chủ xe.

## Phần CÓ THỂ khôi phục (đã thực hiện)

- `data/content-taxonomy.json`: khôi phục từ seed `data/state/taxonomy-config.json` (đã commit) — 7 parent, 51 child, ID và slug giữ nguyên.
- `data/content-inventory.csv`: khôi phục từ `data/state/existing-map.json` (đã commit) + danh sách `_posts/` thật — 483 bài legacy, URL giữ nguyên, 100% ánh xạ.
- `_data/factory-taxonomy.yml`, `_data/factory-map.yml`: sinh từ hai nguồn trên phục vụ layout hub.
- Script: `scripts/factory/restore-foundation.py` (chạy được, idempotent, không bịa dữ liệu).
- Đối chiếu chéo: 20 ID ví dụ trong `reports/factory/content-hierarchy.md` (bản cũ) khớp 100% ánh xạ tái tạo; tổng số bài theo parent khớp `reports/factory/inventory-summary.md` (bản cũ).

## Hậu quả và hướng xử lý (cần quyết định của chủ xe)

- Không nhận được hàng PLANNED nào cho tới khi matrix được giải quyết.
- `scripts/factory/validate.py` báo rõ `BLOCKED` khi thiếu matrix (không crash, không tự PASS).
- Checkpoint/progress phản ánh `next_claimable_id: null` thay vì số bịa.
- Hai lựa chọn:
  1. Chủ xe cung cấp bản gốc `data/content-matrix.csv` (từ máy cá nhân đã chạy bootstrap) → khôi phục đúng dữ liệu, giữ nguyên ID.
  2. Chủ xe duyệt TÁI SINH ma trận mới từ seed `data/state/taxonomy-config.json` (là ma trận mới, không phải khôi phục) → cần ghi rõ đây là quyết định tạo mới và duyệt lại toàn bộ chỉ tiêu.

Trong lúc chờ: mọi sửa khác (hub, liên kết, SEO, CI, tài liệu) đã thực hiện độc lập với matrix.
