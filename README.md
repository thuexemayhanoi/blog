# Blog Thue Xe May Ha Noi Nguyen Tu

Day la repository dung de hoc va xay dung blog bang GitHub Pages.

## Website

- **URL:** https://thuexemayhanoi.github.io/blog/
- **Website doanh nghiep chinh:** https://thuexemaynguyentu.com/

## Muc tieu hoc

- Hieu tung file trong mot blog GitHub Pages.
- Hieu tung thu muc dung de lam gi.
- Hoc tung buoc, moi lan chi them mot phan nho.
- Sau khi hieu cau truc co ban moi lam giao dien, bai viet va SEO.

## Trang thai hien tai

Repository da hoan thien phien ban **PREMIUM ULTRA** voi:
- Thiet ke Apple-inspired, Premium Glass
- Responsive hoan chinh
- SEO toi uu
- Accessibility tot
- Performance cao

## Cau truc thu muc

/
+-- README.md                    # Tai lieu huong dan
+-- _config.yml                 # Cau hinh toan site (Jekyll)
+-- IMG_2536.jpeg               # Logo thuong hieu
|
+-- _data/
|   +-- business.yml            # Thong tin doanh nghiep (NAP, lien he)
|   +-- categories.yml          # Danh muc bai viet voi URL tuong minh
|   +-- navigation.yml          # Menu dieu huong
|
+-- _includes/
|   +-- breadcrumb.html         # Duong dan (Breadcrumb)
|   +-- footer.html             # Footer website
|   +-- header.html             # Header voi menu desktop/mobile
|   +-- quick-contact.html      # Nut lien he nhanh (desktop + mobile)
|   +-- seo.html                # Meta tags, Open Graph, Schema
|
+-- _layouts/
|   +-- category.html           # Layout cho trang danh muc
|   +-- default.html            # Layout goc
|   +-- home.html               # Layout trang chu
|   +-- page.html               # Layout cho cac trang noi dung
|   +-- post.html               # Layout cho bai blog
|
+-- _posts/
|   +-- 2026-09-13-goi-y-kham-pha-ha-noi-bang-xe-may-cho-nguoi-moi.md
|   +-- 2026-09-13-kinh-nghiem-thue-xe-may-ha-noi.md
|   +-- 2026-09-13-xe-so-xe-ga-hay-xe-50cc-nen-chon-loai-nao.md
|
+-- assets/
|   +-- css/
|   |   +-- style.css           # CSS thuan - Premium Ultra Design
|   +-- js/
|       +-- main.js             # Java

Script thuan - Menu, Dropdown
|
+-- 404.html                    # Trang loi 404
+-- robots.txt                  # Cau hinh cho bot tim kiem
+-- index.md                    # Trang chu
+-- blog.md                     # Trang danh sach bai viet
+-- gioi-thieu.md               # Trang gioi thieu
+-- lien-he.md                  # Trang lien he
+-- du-lich.md                  # Danh muc: Du lich
+-- kinh-nghiem.md             # Danh muc: Kinh nghiem
+-- chia-se.md                  # Danh muc: Chia se
+-- bang-gia.md                 # Trang bang gia tong quan
+-- bang-gia-xe-so.md           # Bang gia: Xe so
+-- bang-gia-xe-ga.md           # Bang gia: Xe ga
+-- bang-gia-xe-dien.md         # Bang gia: Xe dien
+-- bang-gia-xe-50cc.md         # Bang gia: Xe 50cc
+-- bao-mat.md                  # Chinh sach bao mat
+-- dieu-khoan.md               # Dieu khoan su dung

## Giai thich tung file

### Cau hinh
- **_config.yml** -> Cau hinh toan site: tieu de, mo ta, ngon ngu, URL, plugin
- **_data/business.yml** -> Thong tin doanh nghiep: ten, dia chi, dien thoai, email, Zalo, Google Maps
- **_data/categories.yml** -> Danh muc bai viet voi URL tuong minh (tranh slugify tu dong)
- **_data/navigation.yml** -> Menu dieu huong cho header va footer

### Layout
- **_layouts/default.html** -> Layout goc, chua header, footer, SEO
- **_layouts/home.html** -> Layout trang chu voi cac section
- **_layouts/page.html** -> Layout cho cac trang noi dung
- **_layouts/post.html** -> Layout cho bai blog
- **_layouts/category.html** -> Layout cho trang danh muc

### Includes
- **_includes/header.html** -> Header voi logo, menu desktop (dropdown), menu mobile overlay
- **_includes/footer.html** -> Footer voi thong tin doanh nghiep, lien ket
- **_includes/quick-contact.html** -> Nut lien he nhanh: floating desktop + bottom bar mobile
- **_includes/breadcrumb.html** -> Duong dan su dung categories.yml
- **_includes/seo.html** -> Meta tags, Open Graph, Twitter Card, Schema (WebSite, Organization, Local
B
usiness, BlogPosting, BreadcrumbList)

### Assets
- **assets/css/style.css** -> CSS thuan: Apple-inspired Premium Ultra, Glassmorphism, Responsive
- **assets/js/main.js** -> JavaScript thuan: Mobile menu, Dropdown, Keyboard navigation, Accessibility

### Noi dung
- **index.md** -> Trang chu
- **blog.md** -> Trang danh sach tat ca bai viet
- **gioi-thieu.md** -> Trang gioi thieu
- **lien-he.md** -> Trang lien he
- **du-lich.md, kinh-nghiem.md, chia-se.md** -> Trang danh muc
- **bang-gia*.md** -> Trang bang gia cac loai xe
- **bao-mat.md, dieu-khoan.md** -> Trang phap ly
- **_posts/*.md** -> Bai blog

## Cong nghe su dung

- **Jekyll** - Static site generator
- **GitHub Pages** - Hosting (branch main, folder root)
- **HTML5** - Semantic HTML
- **CSS3** - Thuan, khong framework
- **JavaScript** - Thuan, khong library
- **Liquid** - Template engine cua Jekyll

## Plugin

- **jekyll-sitemap** -> Tu dong sinh sitemap.xml
- **jekyll-feed** -> Tu dong sinh RSS feed

## Khoi chay

Website se tu dong deploy khi push len branch main.

URL: https://thuexemayhanoi.github.io/blog/

## Ghi chu quan trong

- **Base URL:** /blog/ (khong hard-code duong dan)
- **Logo:** IMG_2536.jpeg (44x44px trong header)
- **Menu:** 2 tang toi da
- **SEO:** Canonical tro den URL GitHub Pages
- **Mobile:** Uu tien trai nghiem mobile
- **Accessibility:** Ho tro keyboard navigation, focus visible
- **Performance:** Khong framework, khong font ngoai khong can

## Lich su

- **09/2026:** Hoan thien phien ban Premium Ultra


## Runtime Repair Verification

- ✅ All .vi/.en data accessors removed
- ✅ All permalinks added to markdown pages
- ✅ Duplicate Assistant controller removed from main.js
- ✅ Mobile menu motion improved with transform + opacity
- ✅ 404 page breadcrumb removed
- ✅ Chatbot data bindings fixed
- ✅ Rental calculator data bindings fixed
- ✅ All 14 public routes verified

Last verified: 2026-09-15

<!-- FIXED -->