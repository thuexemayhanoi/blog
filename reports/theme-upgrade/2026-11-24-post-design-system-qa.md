# Post Design System — báo cáo QA (2026-11-24)

Phạm vi: layout `post` (6.319 bài). Baseline: `main` @ `098377f6`. Tài liệu: `docs/POST-DESIGN-SYSTEM.md`.
Master Matrix: `reports/theme-upgrade/post-design-matrix.xlsx` (mỗi bài một dòng, 64 lô ≤ 100 bài).

## 1. Bất biến SEO (bản build production đầy đủ, 8.527 trang)

`python3 scripts/theme/seo-invariance.py <build main> <build mới>` → thoát 0.

| Hạng mục | Trang khác biệt |
|---|---|
| `<html lang>`, title, meta, link canonical/alternate, JSON-LD | 0 |
| Heading (h1–h6), liên kết (href + chữ), ảnh (src + alt), chữ hiển thị, aria-label | 0 |
| Stylesheet/script (thông tin) | 6.319 — chỉ trang bài viết |

- 2.208 trang HTML không phải bài viết (trang chủ, trang tĩnh, hub, danh mục, trang chuyển hướng): **giống hệt từng byte**.
- Header và footer trên 6.319 trang bài: giống hệt từng byte.
- File ngoài HTML: chỉ `feed.xml` khác (dấu thời gian build); `sitemap.xml`, chỉ mục tìm kiếm, ảnh không đổi.
- Không file nào trong `_posts/`, `_drafts/`, `data/` thay đổi.

## 2. QA hiển thị từng bài (`scripts/theme/post-design-qa.cjs`, Chromium, 390 / 820 / 1440px)

| Chỉ số | Kết quả |
|---|---|
| Bài đã QA | 6.319 / 6.319 (64 lô) |
| PASS / FAIL | 6.319 / 0 |
| Tràn ngang trang (3 bề rộng) | 0 bài |
| Phần tử vượt khung ngoài khung cuộn | 0 |
| CLS lớn nhất | 0 |
| Lỗi JS / HTTP | 0 |
| Đúng 1 H1 | 6.319 |
| Mục lục thu gọn trên điện thoại | 6.235 / 6.235 bài có mục lục |
| FAQ accordion dựng đủ | 99 bài, 298 câu hỏi |
| Bảng bọc khung cuộn | 59 / 59 bài có bảng |

Quyết định: **KEEP 2.244** (giữ cấu trúc, typography chung) · **FIX 4.075** (nâng cấp bằng ≥ 1 thành phần).

Thành phần theo số bài: Summary 2.708 · Warning 874 (542 dạng thẻ) · Local Service 741 · Checklist 377 · Comparison 360 ·
Timeline 304 · Quote 299 · Expert Tips 166 (87 dạng thẻ) · FAQ Accordion 99 · Pricing Table 59 · Pros & Cons 15 ·
nguồn đối chiếu 790 · ảnh thực tế 1.286 · lưu ý pháp lý 24 · lưu ý bảng giá 13.
Số thẻ mỗi bài: 0 thẻ 2.848 bài · 1 thẻ 2.267 · 2 thẻ 863 · 3 thẻ 323 · 4 thẻ 18 (không bài nào quá 4).

Pilot 15 bài đại diện (trước khi chạy toàn bộ): 15/15 PASS; phát hiện và sửa một lỗi — bảng giá trong "Lưu ý bảng giá"
bị cắt cột Tiền cọc ở máy tính bảng (nay hiện đủ 5 cột, không cuộn).

## 3. Trợ năng

- axe-core (WCAG 2.0/2.1/2.2 A+AA, best-practice): 0 vi phạm trên 15 bài đại diện × điện thoại/máy tính × sáng/tối (60 lượt).
- Không JS: đủ mọi câu trả lời FAQ, mục lục mở. Bàn phím: Enter/Space mở–đóng accordion, có viền focus.
- `prefers-reduced-motion`: tắt transition.

## 4. Hiệu năng

Lab cục bộ (Chromium, 390×844, RTT 150 ms, 1,6 Mbps, CPU ×4, gzip như GitHub Pages, trung vị 7 lượt × 2 vòng):

| Trang | FCP trước → sau | LCP trước → sau | CLS | TBT | CSS nén |
|---|---|---|---|---|---|
| Bài A (pháp lý, ảnh) | 540–560 → 560–580 ms | 620–636 → 632–652 ms | 0 → 0 | ~25 → ~25 ms | 17,9 → 22,1 KB |
| Bài B (bảng, FAQ, ảnh) | 540–544 → 564–572 ms | 660 → 704–708 ms | 0 → 0 | ~21 → ~30 ms | 17,9 → 22,1 KB |
| Bài C (trích dẫn, thẻ) | 540–544 → 560–572 ms | 620–632 → 684–688 ms | 0 → 0 | ~22 → ~25 ms | 17,9 → 22,1 KB |
| Trang chủ (không đổi, đo nhiễu) | 528–536 → 540–544 ms | 616–620 → 628–636 ms | 0 → 0 | ~30 → ~33 ms | 17,9 → 17,9 KB |

- Chi phí thật: +4,2 KB CSS nén và +1,8 KB JS `defer` trên trang bài; FCP +~20 ms (nhiễu đo ±12 ms), không thêm request,
  không font, không ảnh. `post-ds.css` tự bỏ chú thích và gộp khoảng trắng lúc build (7,4 → 5,4 KB nén; kết xuất giống hệt
  từng điểm ảnh trên 48 lượt so sánh).
- PageSpeed trên site đang chạy **trước** khi triển khai (Lighthouse lab): bài viết di động FCP 1,2–1,4 s, LCP 1,2–1,4 s,
  TBT 0, CLS 0; máy tính FCP/LCP 371 ms. Số **sau** triển khai ghi trong PR.
- Thời gian build Jekyll cùng máy: 285 s → 307 s (+7,6%).

## 5. Cổng của repo trên bản build mới

`check-regressions.py` 10/10 · `check-built-links.py` PASS · `faq_parity_check.py` 0 lỗi · `check-slug-redirects.py` OK ·
`check-site-urls.py` OK · `validate.py --scope chunk` PASS · `validate_faq.py` 0 lỗi · node tests (pricing table, pricing data,
site search, WebMCP) PASS.

## 6. Việc để chủ website quyết định (không tự sửa)

- 7.363 đoạn văn trong 5.373 bài hiện có sẵn > 1 liên kết nội bộ. Quy tắc "mỗi đoạn tối đa 1 liên kết" và quy tắc
  "giữ nguyên toàn bộ liên kết hiện có" mâu thuẫn ở các bài này; hệ này không đụng liên kết nào. Muốn giảm phải sửa nội
  dung bài PUBLISHED qua `scripts/factory/revise-published.py` (cần `--approval-ref`).
- Title, meta description và trang chủ: không thay đổi, không có đề xuất mới trong đợt này.
