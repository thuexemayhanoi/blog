# SEO KỸ THUẬT — kiểm tra và quy trình

Mục tiêu: mọi trang công khai đạt được: HTTP 200, index được, canonical đúng, sitemap sạch, không link hỏng, không orphan, không trùng nội dung.

Đầu vào: site sau build. Nguồn chuẩn: `_config.yml` (baseurl `/blog`), `robots.txt`, sitemap do `jekyll-sitemap` sinh.

## Kiểm tra (làm có bằng chứng, ghi NOT VERIFIED khi chưa làm)

1. HTTP: mỗi URL đại diện (trang chủ, 7 hub cha, 39 hub con có nội dung, bài đại diện, `/blog/sitemap.xml`, `/blog/robots.txt`) trả 200. Lệnh: `curl -s -o /dev/null -w "%{http_code}" <url>`.
2. Indexability: không `noindex` ngoài chủ đích; robots.txt Allow toàn site + trỏ sitemap.
3. Canonical: khớp URL thật, có baseurl `/blog`, không trùng lặp canonical. Kiểm tra từng hub + bài đại diện.
4. Sitemap: chứa hub + bài; KHÔNG chứa trang nháp, trang nhánh `en/` (đã exclude trong `_config.yml`), URL 404.
5. Link hỏng: rà link nội bộ bằng build + kiểm tra live; đặc biệt trang chủ đề `/blog/chu-de/` — tất cả link phải qua `relative_url` (lỗi 39 link thiếu baseurl đã sửa tại commit này; tái phát hiện = FAIL).
6. Orphan: mọi hub con có bài phải được nối từ hub cha và `/blog/chu-de/`; validator cảnh báo child có bài mà thiếu trang hub.
7. Trùng nội dung: đối chiếu canonical + tiêu đề chuẩn hóa trong cùng child (xem `docs/SEO-OWNERSHIP.md`).

Kết quả mong đợi: 100% URL đại diện 200, không link hỏng mới, sitemap sạch. FAIL ở mục nào → sửa đúng tệp nguồn (không tạo commit "verification"), build lại, kiểm tra lại.

## Quy trình sau mỗi thay đổi kỹ thuật

Mục tiêu → sửa nguồn → build → kiểm tra live → cập nhật Master Fix Matrix (`docs/MASTER-FIX-MATRIX.md`) → commit có mô tả kiểm tra đã làm. Rollback: revert commit, không sửa nóng trên build.

TODO/NOT IMPLEMENTED: redirect 301 từ ngoài (không kiểm soát được GitHub Pages trừ tệp 404) — các URL legacy tuyệt đối không đổi nên chưa cần redirect nội bộ.
