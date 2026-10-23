# Lớp "Lưu ý cập nhật pháp lý" (đính chính hiển thị, không đổi nội dung bài)

## Vì sao có
Một số bài PUBLISHED trích văn bản pháp luật đã lỗi thời hoặc ghi chưa chính xác (đối chiếu ngày 23/10/2026 với văn bản chính thức:
Luật 36/2024/QH15 bản hợp nhất 55/VBHN-VPQH, Nghị định 168/2024/NĐ-CP, Thông tư 108/2026/TT-BCA, QCVN 41:2024/BGTVT…).
Nội dung các bài này bị ràng buộc bởi `data/qa/<ID>.json` (`content_sha256`), mà evidence của chúng đã lệch hash do đổi domain:
sửa nội dung thật phải đi qua `reattest-legacy-qa.py` (cần chủ duyệt, `--approval-ref`) rồi `revise-published.py` (xem `docs/REVISE-PUBLISHED.md`).
Trong lúc chờ, lớp này hiển thị một khối đính chính có nguồn ở đầu bài để người đọc không bị dẫn sai. **Không đổi một byte nào của bài.**

## Cách hoạt động
- Dữ liệu: `_data/legal-notices.json`
  - `catalog[<mã>]`: nội dung đính chính dùng chung (`text`, `source_label`, `source_url`) — sửa một chỗ, mọi bài cùng lỗi tự đồng bộ.
  - `posts[<URL bài>]`: `id` (BLG-…) và danh sách `codes` áp dụng cho bài đó.
- Template: `_includes/legal-notice.html`, gọi từ `_layouts/post.html` trước mục lục. Tra khóa theo `page.url` (O(1)); trang không có
  trong dữ liệu thì không in gì.
- Kiểm thử: `scripts/factory/tests/test_legal_notices.py` — khóa là URL thật của bài PUBLISHED, `id` khớp matrix, mọi mã có trong catalog,
  mỗi mục có nguồn `https` thuộc miền cơ quan nhà nước, không đặt cho bài đang có lease/draft, include đúng một lần và đứng trước mục lục.

## Quy tắc vận hành
1. Chỉ thêm mục khi đã đối chiếu **văn bản chính thức** (ghi rõ điều/khoản, số hiệu, ngày hiệu lực); không trích bài báo/blog làm nguồn.
2. Không thêm số liệu thuê xe (giá, cọc, giờ, chính sách) vào lớp này — số liệu kinh doanh chỉ lấy từ `data/business-facts.json`.
3. Khi một bài đã được sửa gốc (reattest + revise), **xóa mục tương ứng** trong `posts` để tránh nói hai lần; mã không còn bài nào dùng thì xóa khỏi
   `catalog` (test sẽ báo mã thừa).
4. Văn bản đổi hiệu lực → cập nhật `catalog` (một chỗ) và `verified_on`/`verified_on_display`.

## Phạm vi lần đầu (23/10/2026)
22 bài, 9 mã: độ tuổi A1 (5), hạng A1/A (2), Thông tư 35/2024 hết hiệu lực (9), QCVN 41:2024 (5) + mã biển (1), mức phạt Nghị định 168/2024 (4 mã, 4 bài),
ví dụ tiền chậm nộp phạt (1). Các bài còn lại có evidence nguyên vẹn hoặc là bài legacy đã được sửa gốc bằng đường chính thức.
