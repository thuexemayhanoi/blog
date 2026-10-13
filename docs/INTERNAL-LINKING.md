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

## Khối "Bài viết liên quan" của layout (`_includes/related-articles.html`)

- Mỗi bài hiển thị tối đa 4 bài **cùng cụm (child_id)**, xếp cũ → mới (bài legacy theo `_data/legacy-clusters.yml`, rồi bài factory theo ngày) và lấy 4 bài **kế tiếp theo vòng tròn**. Hệ quả: mọi bài trong cụm ≥ 5 bài nhận đúng 4 link liên quan, bộ liên quan khác nhau giữa các bài, bài đã đăng **không đổi** bộ liên quan khi có bài mới (chỉ vài bài cuối cụm quay vòng). Cụm < 5 bài được bù từ cùng parent rồi cùng danh mục.
- Trước đây khối này lấy 4 bài **mới nhất** của cụm cho *mọi* bài (cùng một bộ 4 bài; khoảng 89% bài không nhận link liên quan nào) và quét toàn bộ `site.posts` ở từng trang (O(N²), phần lớn thời gian build Jekyll). Chi phí hiện ~ O(kích thước cụm).
- `_data/legacy-clusters.yml` được **sinh** bởi `scripts/factory/restore-foundation.py` (cùng nguồn `existing-map.json` với `factory-map.yml`) — không sửa tay. Bất biến dữ liệu: `scripts/factory/tests/test_related_cluster_data.py`.

## Cơ hội reverse-link (liên kết ngược)

- Nếu bài mới là nguồn hỗ trợ mạnh cho một bài published cũ, ghi lại cơ hội backlink (bài cũ → bài mới) vào ghi chú/báo cáo của chunk, kèm lý do.
- Xử lý các cơ hội reverse-link trong các đợt bảo trì có kiểm soát (maintenance batch nhỏ, có QA).
- KHÔNG viết lại hàng trăm bài cũ một lúc; không tự động sửa hàng loạt bài published.

## URL legacy chứa Unicode/khoảng trắng

Một số URL bài legacy chứa khoảng trắng và chữ Việt chưa mã hoá, ví dụ
`/du lịch/2026/09/13/...` hay `/kinh nghiệm/...` (URL thật,
Jekyll lowercase category). Quy tắc:

- Manifest (`internal_link_candidates`) cung cấp sẵn URL dạng
  percent-encoded CHÍNH XÁC như site phục vụ (đồng nhất sitemap), ví dụ
  `/du%20l%E1%BB%8Bch/2026/09/13/...`. Writer dùng nguyên văn URL
  này — KHÔNG bỏ phần mã hoá, KHÔNG tự viết lại thành `/du-lich/` khi
  route đó không tồn tại.
- QA (`links_routes_valid`) chấp nhận cả hai dạng: raw và percent-encoded,
  nhưng LUÔN từ chối URL trỏ route không tồn tại (ví dụ tự bịa
  `/du-lich/...`). URL bài đã xuất bản KHÔNG được đổi.

## Kiểm soát chất lượng

- Liên kết phải phục vụ người đọc, không phục vụ SEO cơ học.
- Không tạo ma trận anchor-text lặp trên quy mô lớn.
- QA (docs/QUALITY-RUBRIC.md) chấm liên kết nội bộ theo tiêu chí ở đây.
