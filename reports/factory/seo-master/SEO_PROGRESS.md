# SEO PROGRESS — SEO Autopilot (đợt 5)

Cập nhật: 17/11/2026. Nguồn số liệu: `SEO_CHECKPOINT.json`, `MASTER_SEO_MATRIX.csv`, `autopilot/batch-log.csv`, `gsc/`.
Nhãn: **ĐÃ THỰC HIỆN** (có commit), **ĐÃ XÁC MINH** (có kiểm tra chạy được), **MỚI ĐỀ XUẤT**, **CHỜ DUYỆT**, **KHÔNG THỂ THỰC HIỆN**.

## 1. Kiểm kê (ĐÃ XÁC MINH trên build 17/11, main e3bf094c)

| Hạng mục | Số lượng |
|---|---|
| URL thật của site | 7.121 (6.319 bài, 721 trang danh sách, 56 hub, 7 pillar, 14 trang, 3 trang chuyển hướng, 1 trang chủ) |
| URL trong sitemap | 7.117 (không có noindex/404) |
| Bài nháp trong `_drafts/` | 5 (+1 mẫu) — thuộc nhà máy, không đụng |
| Hàng matrix | PUBLISHED 5.836 · EXISTING 473 · REVIEW 10 · PLANNED 92 · BLOCKED 1 |
| Evidence QA của bài PUBLISHED | nguyên vẹn 5.509 · lệch hash 327 (chỉ sửa được qua reattest có chủ duyệt) |
| Lỗi kỹ thuật đo được | 0 (canonical, noindex, H1, JSON-LD, liên kết nội bộ hỏng, sitemap) — `check-regressions.py` 10/10 |
| Hiệu năng trang chủ (Lighthouse, 17/11) | mobile LCP 1,2 s · CLS 0 · TBT 0 ms; CrUX: LCP/CLS FAST, FCP AVERAGE |

## 2. Search Console (ĐÃ XÁC MINH, 08/10–15/11/2026)

- 1.967 click · 105.973 lượt hiển thị · CTR 1,86% · vị trí TB 7,8. 3.273/7.121 URL có lượt hiển thị; 3.848 URL `NO_GSC_DATA`.
- Mobile chiếm 81% click (vị trí 6,7); desktop vị trí 11,9.
- 205 bài vị trí 5–20 với ≥ 100 lượt hiển thị (cộng URL cũ + mới).
- **Rủi ro lớn nhất (ISS-01):** URL cũ đ→d đã gỡ (404) vẫn nhận ~470–600 lượt hiển thị/ngày; URL mới mới ~80–110/ngày; mẫu 20 URL mới chủ lực chỉ 1 URL đã index.

## 3. Phân loại tự động (MASTER_SEO_MATRIX.csv)

| classification | URL | Ghi chú |
|---|---|---|
| KEEP | 6.594 | chưa có tín hiệu cần sửa (không có nghĩa là bài tốt hay kém) |
| OPTIMIZE | 179 | GSC vị trí 5–20, ≥ 100 lượt hiển thị, evidence nguyên vẹn |
| DUPLICATE_REVIEW | 124 | cùng khóa cannibalization hoặc chung ≥ 3 truy vấn GSC |
| LEGAL_REVIEW | 112 | pháp lý rủi ro cao, chưa đối chiếu văn bản |
| BLOCKED | 104 | content-fix-blocked hoặc evidence lệch hash |
| CONTENT_UPGRADE | 8 | ≥ 100 lượt hiển thị nhưng vị trí > 20, hoặc < 800 từ |
| TECHNICAL_FIX | 0 | |

## 4. Lô

| Lô | Phạm vi | Trạng thái |
|---|---|---|
| B01 | 20 bài GSC 5–20 + 5 chủ đề chủ chỉ định | ĐANG CHẠY (audit + phản biện) |
| B02 | 30 bài OPTIMIZE kế tiếp + cụm 50cc (ISS-03/04) | ĐANG CHẠY |
| L1 | 30 bài legacy chưa có liên kết trong thân bài (nhiều lượt hiển thị nhất) | ĐANG CHẠY |

## 5. Đã thực hiện (commit trên nhánh `claude/seo-autopilot-7000-articles-a4kjcy`, CHƯA vào main/CHƯA deploy)

- a5e5c241 — kiểm kê + GSC + MASTER_SEO_MATRIX + SEO_ISSUES + checkpoint.
- ae13e058 — trang 404 gợi ý tìm bài (86,9% đúng bài ở vị trí 1 theo mô phỏng).
- ed7b6fe7 — `check-link-patch.py` + changelog.

## 6. Chờ chủ quyết định (BLOCKED_OWNER_DECISION)

1. ISS-01 — khôi phục trang chuyển hướng HTTP 200 + meta refresh + canonical cho URL cũ đã gỡ (dry-run rollback OK).
2. ISS-02 — duyệt reattest 28 bài ELIGIBLE (có BLG-00614, BLG-00870 — hai bài nhiều lượt hiển thị nhất, vị trí 16,7 và 21,9).
3. Đưa nhánh vào `main` để deploy (PR + Quality gate).
4. ISS-07 seo_title ngắn (quy tắc cấm đổi title), ISS-08 công cụ thêm liên kết cho bài có evidence, ISS-11 ảnh thật.
