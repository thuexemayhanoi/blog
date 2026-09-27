# SEO OWNERSHIP — quyền sở hữu từ khóa

## Nguyên tắc 1 trang = 1 intent

Mỗi bài sở hữu một `cannibalization_key` (child_id + primary keyword chuẩn hóa) duy nhất trong `data/content-matrix.csv`. Hai bài không được cùng sở hữu một intent trong cùng child.

## Phân tầng

- Parent hub sở hữu từ khóa đầu (head) của cụm (ví dụ "thuê xe máy hà nội").
- Child hub sở hữu từ khóa cụm (ví dụ "thuê xe máy theo tháng").
- Bài sở hữu long-tail (theo manifest). Bài không được cạnh tranh với hub của chính mình: không đặt tiêu đề trùng hoàn toàn tên hub.

## Kiểm tra trước khi xuất bản

1. `primary_keyword` của hàng: tra trong `data/content-matrix.csv` — không được trùng với hàng PUBLISHED/EXISTING khác trong cùng child.
2. Tiêu đề chuẩn hóa: so với các bài đã xuất bản cùng child; tương tự mạnh → REVIEW.
3. Sau khi xuất bản: POST-PUBLISH AUDIT — fetch URL thật, kiểm tra title/meta/canonical/breadcrumb, index qua sitemap.

## Đã phát hiện (bootstrap)

10 hàng legacy REVIEW do trùng cannibalization_key theo cặp:
- BLG-00005 ↔ BLG-00053 (C-KY-NANG-TINH-HUONG)
- BLG-00017 ↔ BLG-00018 (C-KY-NANG-THOI-TIET)
- BLG-00227 ↔ BLG-00228 (C-THUE-THU-TUC)
- BLG-00410 ↔ BLG-00411 (C-DIEM-DEN)
- BLG-00423 ↔ BLG-00424 (C-KY-NANG-CO-BAN)

Xử lý: audit từng cặp, phân biệt intent bằng cách viết lại phần mô tả intent (không đổi URL), hoặc đề xuất merge nội bộ. Không được tạo thêm bài thứ ba cho intent đã có.

Lưu ý 2026-09-27: việc đọc và phân biệt nội dung từng cặp cần AI/người đọc, không tự động hóa được; chưa thực hiện trong lần chạy này. Ma trận còn BLOCKED nên `cannibalization_key` chưa kiểm tra được bằng validator cho hàng mới.

## Liên kết nội bộ

Bài → child hub → parent hub → 2–4 bài liên quan. Trang thương mại (/bang-gia/, /lien-he/) chỉ khi ngữ cảnh hỗ trợ chuyển đổi. Không tạo mạng anchor text khớp chính xác hàng loạt.
