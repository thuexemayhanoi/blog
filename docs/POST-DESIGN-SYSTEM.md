# Post Design System — hệ trình bày dùng chung cho mọi bài viết

> **Sửa một nơi, đồng bộ toàn bộ bài.** Toàn bộ giao diện bài viết (layout `post`) nằm trong ba file:
> `_layouts/post.html` (gắn thành phần lúc render), `assets/css/post-ds.css` (giao diện),
> `assets/js/post-ds.js` (thanh tiến độ, accordion, mục lục). **Không sửa file trong `_posts/`** để đổi giao diện.

Phạm vi: chỉ trang bài viết. Trang chủ, trang tĩnh, hub/danh mục, header, footer **không đổi** — mọi quy tắc CSS nằm
trong `.post-detail` và stylesheet chỉ được tải khi `page.layout == 'post'`.

## 1. Định hướng

Tham chiếu nguyên tắc (không sao chép giao diện) từ ba nhóm: tạp chí biên tập (cột đọc hẹp, sapo, nhịp heading rõ),
du lịch cao cấp (khoảng trắng rộng, một màu nhấn, thẻ bo góc tinh gọn) và trang thuê xe cao cấp (bảng giá dễ quét,
thẻ liên hệ, CTA rõ). Rút ra năm nguyên tắc cho thương hiệu Nguyễn Tú:

1. **Một cột đọc 43rem** (≈ 70 ký tự/dòng), chữ 17px điện thoại / 18px từ máy tính bảng, giãn dòng 1,75.
2. **Một màu nhấn**: xanh thương hiệu sẵn có (`--color-primary`). Vàng hổ phách chỉ cho cảnh báo, xanh lá chỉ cho mẹo/ưu điểm.
3. **Heading có nhịp**: H2 mang số thứ tự `01, 02…` trên một đường kẻ; H3 có vạch xanh bên trái.
4. **Thẻ là ngoại lệ, không phải mặc định**: mỗi loại thẻ dùng tối đa một lần mỗi bài; bài không có nội dung phù hợp thì
   chỉ dùng typography chung.
5. **Nhẹ**: không font ngoài, không ảnh nền, không thư viện, không hiệu ứng kính/gradient động; chuyển động chỉ là thanh
   tiến độ và mở/đóng accordion, tắt khi người dùng chọn giảm chuyển động.

## 2. Token

`assets/css/post-ds.css` khai báo token cục bộ trên `.post-detail`, tất cả trỏ về token nhận diện hiện có trong
`assets/css/tokens.css` — đổi màu thương hiệu ở tokens.css là bài viết đổi theo, giao diện tối tự đồng bộ.

| Token | Giá trị | Dùng cho |
|---|---|---|
| `--pds-measure` | `43rem` | bề rộng cột đọc |
| `--pds-frame` | `68rem` | khung trang bài (cột đọc + ray mục lục) |
| `--pds-brand`, `--pds-link`, `--pds-tint` | xanh thương hiệu / liên kết / nền nhấn nhạt | heading, liên kết, thẻ tóm tắt, bảng |
| `--pds-ink`, `--pds-ink-2`, `--pds-line` | chữ, chữ phụ, viền | thân bài |
| `--pds-warn*`, `--pds-good*`, `--pds-bad` | hổ phách, xanh lá, đỏ | cảnh báo, mẹo/ưu điểm, nhược điểm |
| `--pds-radius` | `14px` (nhỏ `10px`) | thẻ, bảng, ảnh |

## 3. Thành phần — 15 thành phần và quy tắc tự chọn

Thành phần được chọn **lúc render** dựa trên cấu trúc và tiêu đề H2 sẵn có của từng bài. Chữ, heading, liên kết của bài
giữ nguyên từng ký tự; layout chỉ thêm thẻ bọc `<section class="pds-sec …">` và class.

| # | Thành phần | Tự áp dụng khi | Class thủ công (kramdown IAL) |
|---|---|---|---|
| 1 | **Summary Card** | H2 chứa: tóm lại, kết lại, chốt lại, kết luận, lời kết, gói lại, tổng kết, tóm tắt, ghi nhớ | `{: .pds-card .pds-card--summary}` |
| 2 | **Highlight Card** | sapo đầu bài (`description`) và đoạn mở đầu | `{: .pds-card .pds-card--highlight}` |
| 3 | **Expert Tips** | H2 chứa: mẹo, kinh nghiệm, bí quyết | `{: .pds-card .pds-card--tip}` |
| 4 | **Warning Card** | H2 chứa: lưu ý, cảnh báo, sai lầm, rủi ro, không nên | `{: .pds-card .pds-card--warning}` |
| 5 | **Premium Pricing Table** | mọi bảng Markdown (khung bo góc, hàng tiêu đề nền xanh nhạt, kẻ sọc xen kẽ, cuộn ngang trong khung) | — |
| 6 | **Pros & Cons** | heading bắt đầu bằng "Ưu điểm" / "Nhược điểm" (vạch xanh lá/đỏ; danh sách ngay sau dùng dấu +/−) | `{: .pds-pros}` / `{: .pds-cons}` trên danh sách |
| 7 | **Timeline** | H2 chứa: các bước, quy trình, từng bước, trình tự (danh sách đánh số trong mục) | `{: .pds-timeline}` trên `ol` |
| 8 | **Checklist** | H2 chứa: checklist, danh sách kiểm tra, kiểm tra trước, cần chuẩn bị, chuẩn bị gì, mang theo | `{: .pds-checklist}` trên `ul` |
| 9 | **Comparison Card** | H2 chứa: so sánh, khác nhau (bảng trong mục tô cột đầu) | — |
| 10 | **Related Content** | khối cùng chủ đề, bài trước/sau, bài liên quan (có ở mọi bài) | — |
| 11 | **Local Service Card** | H2 chứa: báo tiệm, liên hệ tiệm, hỗ trợ tại Hà Nội, liên hệ Nguyễn Tú, liên hệ cửa hàng, số liên hệ | `{: .pds-card .pds-card--local}` |
| 12 | **CTA Card** | khối liên hệ cuối bài (có ở mọi bài) | — |
| 13 | **FAQ Accordion** | H2 chứa: câu hỏi thường gặp, hỏi đáp, hỏi nhanh, faq (≥ 2 câu hỏi H3); và khối FAQ dùng chung `_includes/faq.html` | — |
| 14 | **Number Card** | chip ngày đăng / tác giả / thời lượng đọc ở đầu bài | `{: .pds-stats}` trên `ul` (số liệu thật) |
| 15 | **Quote Card** | mọi `blockquote` (trích điều luật, mẫu tin nhắn) | `{: .pds-quote}` |

Ngoài ra: mục "Nguồn tham khảo / Nguồn đối chiếu / Điều bài không khẳng định" hiển thị dạng chú thích nhẹ;
lưu ý pháp lý và lưu ý bảng giá (`_data/legal-notices.json`, `_data/price-notices.json`) là thẻ hổ phách.

**Chống máy móc, chống nhồi thẻ** (thực thi trong `_layouts/post.html`):

- Thứ tự ưu tiên khi một H2 khớp nhiều nhóm: hỏi đáp → nguồn → liên hệ → tóm tắt → cảnh báo → mẹo → các bước → checklist → so sánh.
- Thẻ (tóm tắt, hỏi đáp, nguồn, liên hệ, cảnh báo, mẹo) **tối đa một lần mỗi bài**; lần khớp thứ hai hiển thị như mục thường.
- Cảnh báo / mẹo chỉ thành thẻ khi mục ngắn (< 900 ký tự chữ); mục dài chỉ đổi màu số thứ tự.
- Bài có H2 tự đánh số ("1. …") thì ẩn số thứ tự của hệ thống (`data-pds-numbered`).
- Bài không khớp nhóm nào: chỉ nhận typography, mục lục, thanh tiến độ — trong Master Matrix là `KEEP`.
- **Không thành phần nào tự sinh chữ, số liệu, đánh giá hay thông tin doanh nghiệp.** Thẻ chỉ trình bày lại nội dung bài đã có.

Class thủ công dành cho bài viết mới (đặt sau khối Markdown); không dùng để sửa bài đã PUBLISHED
(đổi nội dung bài PUBLISHED chỉ qua `scripts/factory/revise-published.py`, xem `docs/REVISE-PUBLISHED.md`).

## 4. Hành vi

- **Thanh tiến độ đọc**: 3px, cố định trên cùng, `transform: scaleX` theo cuộn (một `requestAnimationFrame` mỗi khung hình).
- **Mục lục**: bài có ≥ 4 H2. Máy tính (≥ 1100px): ray dính bên phải, mục đang đọc được tô đậm (IntersectionObserver).
  Điện thoại và máy tính bảng: thu gọn mặc định (script nội tuyến chạy trước lần vẽ đầu nên không lệch bố cục).
- **FAQ accordion**: mỗi câu hỏi là nút `aria-expanded` có dấu +/−; câu đầu mở sẵn; liên kết neo tới một câu thì tự mở câu đó.
  HTML tĩnh giữ đủ câu hỏi và câu trả lời (không JS vẫn đọc được; schema FAQ và `faq_parity_check.py` không đổi).
- **Bảng**: bọc trong `<div class="pds-table" tabindex="0">`, cuộn ngang trong khung, thân trang không bao giờ tràn.
- **Sáng/Tối**: mọi màu đi qua token; nút đổi giao diện của site (`data-theme`, khóa `nguyentu-theme`) áp dụng ngay.
- **Giảm chuyển động**: tắt transition, thanh tiến độ vẫn cập nhật tức thời.

## 5. Bất biến SEO — không được phá

- Title, meta, H1, URL, canonical, hreflang, JSON-LD của bài **không đổi** (đầu trang do `_layouts/default.html` + include sinh, hệ này không chạm).
- Chữ, heading và **mọi liên kết** trong thân bài giữ nguyên thứ tự và nội dung; không thêm, bớt hay đổi `href`.
- Không đổi giá, tiền cọc, chính sách, NAP (nguồn: `data/business-facts.json`, `_data/business.yml`, `_data/pricing.yml`).
- Thứ tự include trong `_layouts/post.html` được test khóa: `legal-notice.html` và `price-notice.html` đúng một lần trước
  `class="article-toc"`; `faq.html` trước `topic-siblings.html`.
- Không render thân bài hai lần (cổng `check-slug-redirects.py` đếm liên kết).

## 6. Kiểm tra trước khi merge

```bash
# 1) Hai bản build: bản đang chạy (main) và bản mới
git worktree add /tmp/base origin/main
(cd /tmp && JEKYLL_ENV=production jekyll build -s /tmp/base -d /tmp/site-base)
(cd /tmp && JEKYLL_ENV=production jekyll build -s "$OLDPWD" -d /tmp/site-new)   # chạy jekyll từ thư mục KHÔNG có _layouts

# 2) Bất biến SEO trên mọi trang (thoát 0 = giống hệt)
python3 scripts/theme/seo-invariance.py /tmp/site-base /tmp/site-new --json /tmp/invariance.json

# 3) QA hiển thị mọi bài theo lô ≤ 100, cập nhật Excel Master Matrix sau mỗi lô
node scripts/theme/post-design-qa.cjs --site /tmp/site-new --out /tmp/post-qa \
     --matrix reports/theme-upgrade/post-design-matrix.xlsx --invariance /tmp/invariance.json

# 4) Cổng của repo
python3 scripts/seo/check-regressions.py --site /tmp/site-new
python3 scripts/factory/check-built-links.py --site /tmp/site-new
python3 scripts/faq/faq_parity_check.py --site /tmp/site-new
python3 scripts/factory/check-slug-redirects.py --site /tmp/site-new
```

`post-design-qa.cjs` mở từng bài bằng Chromium ở 390 / 820 / 1440px và FAIL khi: tràn ngang, phần tử vượt khung, khác 1 H1,
bảng chưa bọc khung cuộn, accordion dựng thiếu, mục lục không thu gọn trên điện thoại, CLS > 0,05, lỗi JS/HTTP.
Master Matrix: `reports/theme-upgrade/post-design-matrix.xlsx` (mỗi bài một dòng: lô, thành phần, KEEP/FIX, QA).

## 7. Ngân sách hiệu năng

- Một stylesheet riêng cho bài (thay `editorial.css` trên trang bài), một script `defer`; không thêm request font/ảnh.
- Không dùng `backdrop-filter`, animation lặp, gradient động. Thẻ dùng nền phẳng + viền 1px.
- Không gây lệch bố cục: kích thước ảnh giữ nguyên từ include, mục lục thu gọn trước lần vẽ đầu, accordion chỉ mở câu đầu.
- Đo lại bằng PageSpeed/Lighthouse mỗi lần đổi `post-ds.css` hoặc `post-ds.js`; đổi file thì tăng tham số `?v=` trong layout.
