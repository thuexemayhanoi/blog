# INTERNAL-LINKING — chính sách liên kết nội bộ (canonical)

Tài liệu này là nguồn chuẩn duy nhất (canonical) cho liên kết nội bộ. Các tài liệu khác liên kết về đây, không viết lại luật khác đi.

## Nguyên tắc cốt lõi

Liên kết nội bộ được thực hiện TRONG LÚC viết bài mới — không phải một dự án dọn dẹp hàng nghìn bài sau này. Mỗi bài mới phải hoàn thiện các liên kết của chính nó trước khi qua publish gate.

## Quy trình cho mỗi bài mới

1. Xác định parent hub (trang chủ đề cấp cha trong taxonomy) mà bài thuộc về.
2. Kiểm tra các bài đã published thực sự liên quan (đọc danh sách thật, không giả định).
3. Chọn liên kết ngữ cảnh thực dụng cho người đọc.
4. Tránh liên kết theo từ khóa không liên quan.
5. Tránh lặp neo anchor khớp chính xác (exact-match anchor spam).
6. Không bao giờ liên kết tới URL không tồn tại. Hiện chưa có cơ chế pending-link chính thức — nếu chưa có URL đích, bỏ liên kết.

## Cấu trúc ưu tiên

```
bài mới
 -> parent hub
 -> các bài sibling liên quan chặt
 -> bài hỗ trợ sâu hơn khi hữu ích
```

## Cơ hội reverse-link (liên kết ngược)

- Nếu bài mới là nguồn hỗ trợ mạnh cho một bài published cũ, ghi lại cơ hội backlink (bài cũ → bài mới) vào ghi chú/báo cáo của chunk, kèm lý do.
- Xử lý các cơ hội reverse-link trong các đợt bảo trì có kiểm soát (maintenance batch nhỏ, có QA).
- KHÔNG viết lại hàng trăm bài cũ một lúc; không tự động sửa hàng loạt bài published.

## Kiểm soát chất lượng

- Liên kết phải phục vụ người đọc, không phục vụ SEO cơ học.
- Không tạo ma trận anchor-text lặp trên quy mô lớn.
- QA (docs/QUALITY-RUBRIC.md) chấm liên kết nội bộ theo tiêu chí ở đây.
