# blog
Nguyễn Tú

---

## Blog Thuê Xe Máy Hà Nội

Đây là repository dùng để học và xây dựng blog bằng GitHub Pages.

Website dự kiến: https://thuexemayhanoi.github.io/blog/

Mục tiêu học:
* Hiểu từng file trong một blog GitHub Pages.
* Hiểu từng thư mục dùng để làm gì.
* Học từng bước, mỗi lần chỉ thêm một phần nhỏ.
* Sau khi hiểu cấu trúc cơ bản mới làm giao diện, bài viết và SEO.

Trạng thái hiện tại: Blog hoàn chỉnh với Jekyll + GitHub Pages.

---

## Cấu trúc thư mục

/
├── README.md              # File giới thiệu repository và ghi chú quá trình học
├── _config.yml            # Cấu hình toàn site (tên, mô tả, URL, ngôn ngữ, v.v.)
├── index.md               # Trang chủ của blog
├── about.md               # Trang giới thiệu
├── contact.md             # Trang liên hệ
├── blog.md                # Trang danh sách bài viết
├── 404.html               # Trang lỗi 404
├── robots.txt             # Cấu hình cho bot tìm kiếm
├── _posts/                # Nơi chứa bài blog (file markdown)
│   └── 2026-09-13-kinh-nghiem-thue-xe-may-ha-noi.md
├── _layouts/              # Khung HTML chung
│   ├── default.html       # Layout mặc định cho tất cả trang
│   ├── home.html          # Layout riêng cho trang chủ
│   └── post.html          # Layout riêng cho bài viết
├── _includes/             # Các phần dùng lại (header, footer)
│   ├── header.html        # Header của website
│   └── footer.html        # Footer của website
└── assets/                # Tài nguyên tĩnh (CSS, hình ảnh)
    └── css/
        └── style.css      # File CSS chính

---

## Giải thích từng file

### _config.yml → Cấu hình toàn site
- Thiết lập tiêu đề, mô tả, URL, ngôn ngữ
- Cấu hình plugin, bộ sưu tập
- Định nghĩa biến toàn cục (business info)

### _posts/ → Nơi chứa bài blog
- Mỗi bài là 1 file markdown
- Tên file: YYYY-MM-DD-ten-bai-viet.md
- Jekyll tự động xử lý ngày tháng và URL

### _layouts/ → Khung HTML chung
- default.html: Layout gốc cho tất cả trang
- home.html: Layout đặc biệt cho trang chủ
- post.html: Layout cho bài viết

### _includes/ → Các phần dùng lại
- header.html: Phần đầu trang (logo, menu)
- footer.html: Phần chân trang (thông tin, liên kết)

### assets/ → Tài nguyên tĩnh
- css/style.css: File CSS chính
- (Có thể thêm hình ảnh vào assets/images/)

### index.md → Trang chủ
- Sử dụng layout: home
- Hiển thị bài viết mới nhất

### about.md → Giới thiệu
- Giới thiệu về blog và doanh nghiệp

### contact.md → Liên hệ
- Thông tin liên hệ đầy đủ
- Bản đồ Google Maps

### blog.md → Danh sách bài viết
- Hiển thị tất cả bài viết
- Sử dụng Liquid để lặp qua site.posts

### 404.html → Trang lỗi
- Hiển thị khi truy cập đường dẫn không tồn tại

### robots.txt → Cấu hình bot
- Cho phép bot index toàn bộ site
- Chỉ đường đến sitemap.xml

---

## URL dự kiến

https://thuexemayhanoi.github.io/blog/

---

## Để bật GitHub Pages

Nếu chưa bật:

1. Vào Settings → Pages
2. Chọn "Deploy from a branch"
3. Chọn branch: main
4. Chọn folder: /(root)
5. Click Save

Blog sẽ tự động deploy sau vài phút.