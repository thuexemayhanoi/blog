# Blog Thuê Xe Máy Hà Nội Nguyễn Tú

---

## Giới thiệu

Đây là repository NGUYỄN TÚ BLOG - PREMIUM ULTRA, một website/blog doanh nghiệp cao cấp xây dựng bằng Jekyll + GitHub Pages với thiết kế Apple-inspired, Premium Glass, Luxury Minimal.

Website: https://thuexemayhanoi.github.io/blog/
Website doanh nghiệp: https://thuexemaynguyentu.com/

---

## Cấu trúc thư mục

/
+-- README.md
+-- _config.yml
+-- _data/
|   +-- navigation.yml
|   +-- business.yml
+-- _includes/
|   +-- header.html
|   +-- footer.html
|   +-- quick-contact.html
|   +-- seo.html
|   +-- breadcrumb.html
+-- _layouts/
|   +-- default.html
|   +-- home.html
|   +-- page.html
|   +-- post.html
|   +-- category.html
+-- _posts/
|   +-- 2026-09-13-kinh-nghiem-thue-xe-may-ha-noi.md
|   +-- 2026-09-13-goi-y-kham-pha-ha-noi-bang-xe-may-cho-nguoi-moi.md
|   +-- 2026-09-13-xe-so-xe-ga-hay-xe-50cc-nen-chon-loai-nao.md
+-- assets/
|   +-- css/
|   |   +-- style.css
|   +-- js/
|       +-- main.js
+-- index.md
+-- gioi-thieu.md
+-- blog.md
+-- du-lich.md
+-- kinh-nghiem.md
+-- chia-se.md
+-- bang-gia.md
+-- bang-gia-xe-so.md
+-- bang-gia-xe-ga.md
+-- bang-gia-xe-dien.md
+-- bang-gia-xe-50cc.md
+-- lien-he.md
+-- bao-mat.md
+-- dieu-khoan.md
+-- 404.html
+-- robots.txt
+-- sitemap.xml

---

## Giải thích từng folder/file

### _config.yml
Cấu hình toàn site: tiêu đề, mô tả, URL, ngôn ngữ (vi-VN), thông tin doanh nghiệp, plugin Jekyll

### _data/
- navigation.yml: Quản lý toàn bộ menu (header & footer) - Menu 2 tầng
- business.yml: Thông tin doanh nghiệp tập trung (NAP, dịch vụ, khu vực)

### _includes/
- header.html: Header premium (sticky, blur, glass, dropdown menu, mobile hamburger)
- footer.html: Footer premium 4 cột (NGUYỄN TÚ, LIÊN KẾT, BLOG, BẢNG GIÁ)
- quick-contact.html: Liên hệ nhanh (floating desktop + bottom bar mobile)
- seo.html: SEO meta tags, Open Graph, Twitter Card, Schema.org
- breadcrumb.html: Breadcrumb navigation

### _layouts/
- default.html: Layout gốc (SEO, header, quick-contact, footer, JS)
- home.html: Trang chủ premium (Hero, Dịch vụ, Bài viết, Chuyên mục, Bảng giá, Khu vực, Giới thiệu, CTA)
- page.html: Trang tĩnh
- post.html: Bài viết (categories, tags, navigation, CTA)
- category.html: Chuyên mục

### _posts/
Bài viết markdown với Front matter: layout, title, date, author, description, categories, tags, reading_time
Categories: Du lịch, Kinh nghiệm, Chia sẻ

### assets/css/style.css
Premium Ultra Design: Apple-inspired, Glassmorphism, Luxury Minimal
- Màu sắc: Trắng/đen/xám + xanh lam nhẹ (accent)
- Typography: System fonts, lớn, sạch
- Whitespace: Rộng rãi
- Cards: Bo góc, glass blur, border nhẹ, shadow mềm
- Responsive: Mobile-first
- Dark mode: Tự động
- Animation: Tinh tế

### assets/js/main.js
- Mobile menu toggle
- Dropdown menu
- Keyboard navigation
- Smooth scroll
- Lazy loading images
- Accessibility support

### Trang chủ (index.md)
Layout: home - Hero, Dịch vụ, Bài viết mới, Chuyên mục, Bảng giá, Khu vực, Giới thiệu, CTA

### Trang chuyên mục
- du-lich.md, kinh-nghiem.md, chia-se.md
- Layout: category
- Auto-filter posts by category

### Trang bảng giá
- bang-gia.md (main)
- bang-gia-xe-so.md, bang-gia-xe-ga.md, bang-gia-xe-dien.md, bang-gia-xe-50cc.md
- Layout: page
- Không hard-code giá

### Trang tĩnh
- gioi-thieu.md, lien-he.md, bao-mat.md, dieu-khoan.md
- Layout: page

### SEO & Technical
- robots.txt: Cho phép index toàn bộ site
- sitemap.xml: Auto-generated URLs
- 404.html: Custom 404 page
- Canonical URLs: Sử dụng absolute_url
- Baseurl handling: Tất cả URL dùng relative_url/absolute_url

---

## Tính năng đã triển khai

Jekyll + GitHub Pages - Deploy từ branch main, root directory
Apple-inspired Premium Design - Glassmorphism, Luxury Minimal
Mobile-first Responsive - Hoàn chỉnh trên mọi thiết bị
SEO Optimized - Meta tags, Open Graph, Twitter Card, Schema.org
NAP Consistency - Thông tin doanh nghiệp nhất quán khắp site
Menu 2 tầng - Dropdown Blog & Bảng giá, mobile hamburger
Quick Contact - Floating (desktop) + Bottom bar (mobile)
Dark Mode - Tự động theo prefers-color-scheme
Accessibility - Keyboard nav, focus states, aria labels
Performance - System fonts, no external libs, lazy loading
Baseurl Support - Tất cả URL hoạt động với /blog/
Sitemap & Robots - Tối ưu cho search engines

---

## Cách sử dụng

### 1. Bật GitHub Pages (nếu chưa bật)

1. Vào Settings -> Pages
2. Chọn "Deploy from a branch"
3. Chọn branch: main
4. Chọn folder: /(root)
5. Click Save

Website sẽ tự động deploy sau vài phút tại: https://thuexemayhanoi.github.io/blog/

### 2. Thêm bài viết mới

1. Tạo file markdown trong _posts/
2. Tên file: YYYY-MM-DD-ten-bai-viet.md
3. Front matter:

layout: post
title: "Tiêu đề bài viết"
date: YYYY-MM-DD HH:MM:SS +0700
author: "Nguyễn Tú"
description: "Mô tả ngắn"
categories: [Du lịch]
tags: [tag1, tag2]
reading_time: 5

4. Viết nội dung
5. Commit & push

### 3. Cập nhật menu

Sửa file _data/navigation.yml

### 4. Cập nhật thông tin doanh nghiệp

Sửa file _data/business.yml

---

## Thông tin doanh nghiệp

Thương hiệu: Nguyễn Tú
Tên hiển thị: Thuê Xe Máy Hà Nội Nguyễn Tú
Website: https://thuexemaynguyentu.com/
Địa chỉ: 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội, Việt Nam
Điện thoại: 0942 467 674
Email: nguyentuantu8x@gmail.com
Zalo: https://zalo.me/0942467674
Google Maps: https://maps.app.goo.gl/rj78cAggpN5kFD6ZA
Giờ hoạt động: 09:00 - 21:00

---

## Không được làm

Không tạo .github/workflows/
Không dùng GitHub Actions
Không dùng React, Next.js, Vue, Astro
Không dùng Bootstrap, Tailwind
Không thay đổi GitHub Pages Settings
Không hard-code NAP ở nhiều file
Không bịa giá, đánh giá giả
Không copy nguyên website chính

---

URL: https://thuexemayhanoi.github.io/blog/
Baseurl: /blog
Language: vi-VN
Theme: Jekyll (no theme, custom design)

---

© 2026 Nguyễn Tú. All rights reserved.