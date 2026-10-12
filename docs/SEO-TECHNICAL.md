# SEO KỸ THUẬT — kiểm tra và quy trình

Mục tiêu: mọi trang công khai đạt được: HTTP 200, index được, canonical đúng, sitemap sạch, không link hỏng, không orphan, không trùng nội dung.

Đầu vào: site sau build. Nguồn chuẩn: `_config.yml` (`baseurl: ""`, domain riêng ở gốc `https://blog.thuexemaynguyentu.com/`), `robots.txt`, sitemap do `jekyll-sitemap` sinh. Repo tên `/blog` **không có nghĩa** URL bài viết phải thêm `/blog/`.

## Kiểm tra (làm có bằng chứng, ghi NOT VERIFIED khi chưa làm)

1. HTTP: mỗi URL đại diện (trang chủ, các hub cha và hub con **có bài** lấy từ taxonomy/matrix hiện hành, bài đại diện, `/sitemap.xml`, `/robots.txt`) trả 200. **Không cố định số hub** trong tài liệu: taxonomy thay đổi theo các đợt mở rộng. Lệnh: `curl -s -o /dev/null -w "%{http_code}" <url>`.
2. Indexability: không `noindex` ngoài chủ đích; robots.txt Allow toàn site + trỏ sitemap.
3. Canonical: khớp URL thật từ `_config.yml` và Jekyll; với custom domain hiện tại URL bắt đầu `https://blog.thuexemaynguyentu.com/`, **không tự chèn tiền tố `/blog/`**. Ví dụ đúng: `https://blog.thuexemaynguyentu.com/thue-xe/`; URL `https://blog.thuexemaynguyentu.com/blog/thue-xe/` không phải mặc định. Kiểm tra từng hub + bài đại diện, không sửa URL legacy (kể cả đường dẫn Unicode đã percent-encode).
4. Sitemap: chứa hub + bài; KHÔNG chứa trang nháp, trang nhánh `en/` (đã exclude trong `_config.yml`), URL 404.
5. Link hỏng: rà link nội bộ bằng build + kiểm tra live; đặc biệt `/chu-de/`. Dùng `relative_url` cho liên kết nội bộ theo `docs/INTERNAL-LINKING.md`, nhưng **không** tự nối thêm `/blog/` vì `baseurl` hiện rỗng. Lỗi lịch sử 39 link thiếu `relative_url` đã được xử lý; chỉ coi là tái phát nếu link build/live thật sự hỏng.
6. Orphan: mọi hub con có bài phải được nối từ hub cha và `/chu-de/`; validator cảnh báo child có bài mà thiếu trang hub.
7. Trùng nội dung: đối chiếu canonical + tiêu đề chuẩn hóa trong cùng child (xem `docs/SEO-OWNERSHIP.md`).

Kết quả mong đợi: 100% URL đại diện 200, không link hỏng mới, sitemap sạch. FAIL ở mục nào → sửa đúng tệp nguồn (không tạo commit "verification"), build lại, kiểm tra lại.

## Quy trình sau mỗi thay đổi kỹ thuật

Mục tiêu → sửa nguồn → build → kiểm tra live → cập nhật Master Fix Matrix (`docs/MASTER-FIX-MATRIX.md`) → commit có mô tả kiểm tra đã làm. Rollback: revert commit, không sửa nóng trên build.

TODO/NOT IMPLEMENTED: redirect 301 từ ngoài (không kiểm soát được GitHub Pages trừ tệp 404) — các URL legacy tuyệt đối không đổi nên chưa cần redirect nội bộ.
