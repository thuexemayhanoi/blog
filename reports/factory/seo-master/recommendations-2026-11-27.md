# SEO 2026-11-27 · Đề xuất bài viết và Keyword Matrix

- Khối bài liên quan ưu tiên tiêu đề có “thuê xe máy” trong tối đa bốn bài đã được chọn theo cụm. Hai nhóm giữ thứ tự tương đối. Quy tắc chọn URL, phân trang và liên kết phân phối đều theo cụm giữ nguyên.
- Keyword Matrix thêm K13 cho “app thuê xe máy Hà Nội”. BLG-06413 là URL chủ lực đã xác minh HTTP 200, canonical tự trỏ và có trong sitemap. Hub thủ tục và trang giá 50cc là URL hỗ trợ.
- Lighthouse 12.8.2, một phép đo mobile tổng hợp trên trang chủ live trước lô này. Hiệu suất 100/100, LCP 1,3 giây, CLS 0, TBT 0 ms, tổng tải 169 KiB. Kết quả dữ liệu thực địa chưa có vì PageSpeed Insights trả lỗi hạn mức 429.
- Bốn kiểm thử bất biến cụm bài liên quan chạy đạt. Mẫu đối chiếu production trước deploy có 46 trang đủ ít nhất hai bài đề xuất.
- NEXT_CURSOR: kiểm tra 46 trang sau deploy và xác minh tập URL trong từng khối đề xuất. Search Console của blog, PAA, Related Searches và CWV thực địa vẫn cần dữ liệu xác minh.
