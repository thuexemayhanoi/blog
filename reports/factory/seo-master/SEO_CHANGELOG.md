# SEO CHANGELOG — chương trình SEO Autopilot (đợt 5, từ 17/11/2026)

Nhật ký mọi thay đổi do chương trình Autopilot thực hiện, mới nhất ở trên. Mỗi mục: commit, phạm vi, bằng chứng QA,
trạng thái deploy. "Đã deploy" chỉ ghi khi commit đã vào `main`, Pages deploy SUCCESS và URL live đã kiểm.
Lịch sử đợt 1–4: `fix-log.csv`, `deployment-verification.md`, `checkpoint.json`.

## 2026-11-17

### ae13e058 — ux(404): gợi ý tìm bài cho người vào URL cũ đã gỡ
- `404.html`: hiện liên kết `/tim-kiem/?q=<các từ trong đường dẫn>` khi đoạn cuối URL có ≥ 2 từ. Trang vẫn trả HTTP 404, không bảng ánh xạ, không tự chuyển trang.
- Đo: mô phỏng bằng chính `assets/js/site-search.js` trên chỉ mục build → bài đúng đứng đầu ở 1.223/1.408 URL cũ (86,9%), top 3 ở 1.304 (92,6%).
- QA: build cục bộ chỉ đổi `/404.html`; `check-regressions.py` 10/10 PASS; `check-built-links.py` PASS.
- Deploy: CHƯA (nằm trên nhánh `claude/seo-autopilot-7000-articles-a4kjcy`).

### a5e5c241 — kiểm kê 7.121 URL + dữ liệu Search Console + MASTER_SEO_MATRIX
- Công cụ mới: `scripts/seo/import-gsc-snapshot.py`, `scripts/seo/build-seo-master-matrix.py` (chỉ đọc nguồn, đầu ra xác định).
- Dữ liệu: `gsc/*.csv` (08/10–15/11/2026), `MASTER_SEO_MATRIX.csv` (7.121 hàng), `autopilot/index-inspection.csv` (90 URL), `SEO_ISSUES.csv` (13 vấn đề).
- Không đổi bài, template, URL, title/meta. QA: `validate.py --scope chunk` PASS; 4 bộ test liên quan OK; chạy lại cho byte giống nhau.
- Deploy: không áp dụng (thư mục `reports/` không được Jekyll xuất bản).
