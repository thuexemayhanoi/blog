# DESIGN SYSTEM "SỐ NHÀ 112"

Một hệ thống thiết kế duy nhất cho toàn bộ blog Thuê Xe Máy Hà Nội Nguyễn Tú (trang chủ, 6.300+ bài viết, hub, bảng giá, trang tĩnh, tìm kiếm, 404). Tài liệu này là nguồn tham chiếu khi sửa giao diện; mã nguồn ở `assets/css/ds.css`, `ds-home.css`, `ds-article.css`.

## 1. Ý tưởng

Thương hiệu không vay mượn vẻ "sang" của showroom. Nó lấy đúng những thứ đang có ở mặt tiền cửa hàng 112 Nguyễn Văn Cừ (xem `assets/images/photos/mat-tien-cua-hang-112-nguyen-van-cu-*.webp`) và dùng chúng một cách kỷ luật:

| Chất liệu thật | Trở thành | Dùng ở đâu |
|---|---|---|
| Biển số nhà men xanh "112", viền trắng | **Tấm biển men**: nền xanh men, chữ kem, một đường viền kem thụt vào | Nút chính, số chương, biển 112 ở hero và cạnh logo, khối liên hệ, CTA cuối bài, số 404, trang hiện tại của phân trang |
| Chữ dán kính màu kem trên cửa | **Nền giấy kem** và chữ kem trên nền xanh | Nền trang, chữ trên biển |
| Bốn sọc xanh ngang trên cửa kính | **Dải sọc** | Khép hero, dưới tiêu đề trang, mép trên chân trang |
| Vạch kẻ đường đứt nét | **Vạch dẫn hướng** | Đường phân cách giữa các phần, gạch dưới mục menu, thanh tiến độ đọc |
| Đá granite đen ốp mặt tiền | **Mặt đá** | Chân trang, mặt đồng hồ máy tính giá, nút phụ |

Hệ quả: bỏ logo đi, trang vẫn nhận ra được nhờ chữ biển hiệu dáng hẹp, màu men xanh trên nền kem, dải sọc và vạch đứt nét. Không có ảnh stock, không có số liệu hay lời khen tự đặt ra.

## 2. Token (`assets/css/ds.css`, mục 2)

- **Màu gốc**: `--enamel-*` (xanh men, lấy mẫu từ biển số và sọc kính), `--cream-*` (kem), `--granite-*` (đá), `--paver-600` (đỏ gạch vỉa hè, màu nhấn), `--signal-500` (vàng tín hiệu: thanh tiến độ đọc, ghi chú trên mặt đồng hồ).
- **Vai trò**: `--bg`, `--bg-raised`, `--bg-sunken`, `--fg`, `--fg-2`, `--fg-3`, `--rule`, `--rule-strong`, `--brand`, `--brand-strong`, `--brand-soft`, `--on-brand`, `--on-brand-2`, `--accent`, `--link`, `--link-hover`, `--ok`, `--closed`, `--focus`. Thành phần chỉ dùng token vai trò; chế độ tối (`html[data-theme="dark"]`) chỉ đổi token vai trò.
- **Khoảng cách**: `--s-1` … `--s-9` (bội số 4px), `--section-y`, `--gutter`, `--wrap` (1240px), `--measure` (688px, bề rộng cột đọc).
- **Hình khối**: `--r-1` 4px, `--r-2` 8px, `--r-3` 14px. Không dùng bóng đổ trang trí; `--shadow-pop` chỉ cho lớp nổi (menu, trợ lý).
- **Tên token cũ** (`--color-*`, `--spacing-*`, `--font-size-*`, `--radius-*`) vẫn được định nghĩa và trỏ về hệ mới vì `assets/css/pricing-table.css` còn dùng. Mã mới không dùng tên cũ.

## 3. Chữ

- **Chữ hiển thị**: Big Shoulders Display (SIL OFL 1.1, tự host tại `assets/fonts/`, 2 tệp WOFF2: latin 35 KB + vietnamese 10 KB, `font-display: swap`, preload trong `_layouts/default.html`). Dáng hẹp kiểu biển hiệu nên tiêu đề tiếng Việt 60–110 ký tự vẫn gọn dòng trên màn 360px. Font dự phòng `BSD Fallback` được co bằng `size-adjust` (đo trên chuỗi tiếng Việt thật) để khi font tải xong dòng không nhảy.
- **Chữ đọc**: font hệ thống của thiết bị (`--font-text`). Không tải thêm font cho thân bài: nhanh, dấu tiếng Việt chuẩn trên iOS/Android/Windows.
- **Thang chữ**: `--fs-hero`, `--fs-h1`, `--fs-h2`, `--fs-h3`, `--fs-lead`, `--fs-body`, `--fs-small`, `--fs-label` (đều co giãn bằng `clamp()`).
- **Quy tắc**:
  - Tiêu đề trang, nhãn, nút: chữ hiển thị. Nhãn và nút viết hoa, giãn chữ `--track-label`.
  - Tiêu đề bài viết (h1 của bài, h2/h3 trong thân bài): chữ hiển thị, **không** viết hoa (tiêu đề dài, cần dễ đọc).
  - Chiều cao dòng chữ hiển thị không dưới 1,02 để dấu chồng (Ễ, Ộ, Ử) không chạm dòng trên.
  - Số (giá, giờ, điện thoại, ngày): chữ hiển thị + `font-variant-numeric: tabular-nums`.

## 4. Ngôn ngữ chuyển động

Một họ đường cong (`--ease-out`, `--ease-io`), bốn nhịp (`--t-1` 120ms, `--t-2` 240ms, `--t-3` 520ms, `--t-4` 900ms). Chỉ chuyển động `transform`/`opacity`. Năm động tác, mỗi động tác có lý do:

| Tên | Là gì | Vì sao cần |
|---|---|---|
| **Lăn bánh** | Khối nội dung trượt lên theo đúng nhịp cuộn (`animation-timeline: view()`, CSS thuần) | Cuộn có cảm giác đang đi tới; trình duyệt không hỗ trợ thì nội dung đứng yên, không bao giờ bị ẩn |
| **Vạch kẻ** | Đường kẻ kéo ra: gạch dưới mục menu, thanh tiến độ đọc | Chỉ vị trí và tiến độ |
| **Men bóng** | Vệt sáng lướt qua mặt biển khi rê chuột/đưa tiêu điểm vào nút chính, một lần trên biển 112 khi mở trang | Phản hồi tương tác của thứ bấm được; thay cho phóng to/nảy |
| **Đồng hồ** | Con số nhảy lên một nhịp khi máy tính giá đổi kết quả (`main.js` → `.is-ticking`) | Báo rằng giá vừa được tính lại |
| **Sang số** | Chuyển trang mờ dần giữa hai tài liệu (`@view-transition`) | Đi giữa các trang liền mạch, đầu trang đứng yên |

Không có chuyển động nào lặp vô hạn ngoài chấm "đang mở cửa" (trạng thái thật theo giờ Hà Nội). `prefers-reduced-motion: reduce` tắt toàn bộ.

## 5. Thành phần (đều trong `ds.css`)

Nút (`.btn`, `-primary` = biển men, `-secondary` = mặt đá, `-outline`), biểu mẫu, đầu trang + mega menu, menu di động toàn màn hình có số thứ tự, breadcrumb, trạng thái mở/đóng cửa, chân trang, nút gọi nhanh (di động), trợ lý "Hỏi nhanh", thẻ bài viết (hàng mục lục, không phải hộp), phân trang, danh mục chủ đề, danh sách chủ đề, FAQ, CTA cuối bài, ảnh thật (khung 4:3 đồng nhất, không bộ lọc), máy tính giá (mặt đồng hồ), bảng giá (`pricing-table.css` + lớp da ở cuối tệp), tìm kiếm, 404.

## 6. Bố cục từng loại trang

**Trang chủ** (`_layouts/home.html` + `ds-home.css`). Thứ tự phần và câu chữ giữ nguyên bản chủ website đã duyệt.

| Phần | Vì sao tồn tại | Vì sao bố cục này | Chuyển động |
|---|---|---|---|
| Hero | Nói ngay dịch vụ gì, ở đâu | Tiêu đề là hình ảnh; dải phân khối 50cc–125cc tô xanh men; biển 112 neo địa chỉ thật | Chữ nhích lên một lần, biển bắt sáng một lần |
| Máy tính giá | Câu hỏi đầu tiên của người thuê là giá | Một thẻ, kết quả trên mặt đồng hồ tối | Đồng hồ |
| Về Nguyễn Tú | Một câu định vị + bốn điều đã xác minh | Câu lớn, bốn ô đánh số | Lăn bánh |
| Dịch vụ chính | Cho xem xe | Desktop: lưới 2+3; di động: băng chuyền vuốt ngang | Lăn bánh (desktop) |
| Bài mới | Dẫn vào cẩm nang | Hàng mục lục báo chí | Lăn bánh |
| Các chủ đề | Bản đồ nội dung | Bảng chỉ dẫn mở/đóng, không JS | — |
| Bảng giá | Dẫn tới 4 bảng giá | Bốn tấm biển | Men bóng |
| Khu vực phục vụ | Trả lời "có giao tới chỗ tôi không" | Tên quận cỡ lớn như biển chỉ đường | Lăn bánh |
| Giới thiệu + liên hệ | Tin cậy: địa chỉ, giờ, số điện thoại | Văn bản + biển men thông tin | Lăn bánh |
| Lời mời cuối | Một việc: gọi | Toàn bề ngang là mặt biển men | Lăn bánh |

Từ 1024px, mỗi chương có số thứ tự + tiêu đề dính bên trái, nội dung bên phải. Di động: một cột, biển 112 thu nhỏ thành thẻ địa chỉ trên tiêu đề, nút hero xếp 1 + 2×2.

**Bài viết** (`_layouts/post.html` + `ds-article.css`): đầu bài (breadcrumb, tiêu đề, mô tả, dòng thông tin giữa hai đường kẻ) → một cột đọc `--measure`; từ 1100px có ray mục lục dính bên phải. Trên điện thoại mục lục thu gọn trước lần vẽ đầu để nội dung bắt đầu ngay. Mỗi h2 có vạch đứt nét phía trên. Bảng cuộn ngang trong khung bảng.

**Hub / chủ đề / danh sách / trang tĩnh** (`.page-section`): tiêu đề viết hoa + dải sọc, mô tả, nội dung trong cột đọc, danh sách bài dạng hàng mục lục.

## 7. Những thứ KHÔNG được đổi khi sửa giao diện

Thiết kế lại chỉ đụng lớp trình bày. Bề mặt SEO giữ nguyên:

- `<title>`, mọi thẻ `<meta>`, canonical, JSON-LD, URL, cấu trúc heading, chữ hiển thị, tập liên kết và thứ tự liên kết, ảnh (src/alt). Không thêm thẻ meta mới (kể cả `theme-color`).
- Trang chủ: H1, đoạn mô tả hero (`<p class="hero-subtitle">` không thêm thuộc tính), thứ tự các phần (`scripts/seo/frozen-homepage.json`).
- Chữ trang trí do CSS sinh (số chương, "112", tên phố trên biển) phải là sự thật và không thay cho nội dung.
- Các hợp đồng máy đọc: `<nav class="pagination"`, `aria-label="Đường dẫn"`, `section.faq` + `div.faq-item`, `class="article-toc"`, thứ tự include trong `post.html`, chuỗi `?v=20261117-price-notice` của `pricing-table.css`, các selector JS trong `assets/js/*.js`.

## 8. Cách kiểm tra sau khi sửa

1. `node scripts/tests/test-pricing-table.cjs && node scripts/tests/test-pricing-data.cjs`
2. Build Jekyll, rồi `python3 scripts/seo/check-regressions.py --site <_site>`, `python3 scripts/factory/check-built-links.py --site <_site tuyệt đối>`, `python3 scripts/faq/faq_parity_check.py --site <_site>`.
3. Chụp ảnh ở 390px và 1440px, sáng và tối, cho: trang chủ, một bài dài có bảng, `/bang-gia/`, một hub, một trang danh sách, `/lien-he/`, `/tim-kiem/`, `/404.html`; mở menu di động, mega menu, trợ lý.
4. Đổi CSS thì đổi chuỗi `?v=` của `ds*.css` trong `_layouts/default.html`.
