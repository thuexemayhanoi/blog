# QA — đợt 1 (templates + hub/pillar + dữ liệu SEO Master)

Ngày: 2026-10-22. Cơ sở so sánh: HEAD `4f61156e` (trang chủ đã duyệt). Mọi số liệu dưới đây là **FACT** đo cục bộ trên bản build
của đúng trạng thái commit; kết quả CI/Pages sau khi đẩy ghi ở `deployment-verification.md`.

## Kiểm thử cục bộ

| Kiểm tra | Kết quả |
|---|---|
| Jekyll build đầy đủ 6.076 bài (3.10.0 + minima 2.5.1 + sitemap + feed) | BUILD_EXIT=0, 688 s (một mình, có `--profile`) |
| Số trang HTML | 6.844 (trước: 6.844; không trang nào mất hoặc thêm) |
| So HTML trước/sau, toàn bộ 6.844 trang | 6.781 trang chỉ khác ở khối dự kiến; 63 trang khác có chủ đích = 62 pillar/hub (nội dung giới thiệu mới) + 1 bài hạ H1; 0 khác biệt ngoài dự kiến |
| `scripts/factory/validate.py --scope chunk` | PASS, 0 cảnh báo |
| `check-built-links.py` trên `_site` | PASS, 0 liên kết nội bộ hỏng |
| `faq_parity_check.py` | PASS: 6.844 trang, 2 trang có FAQ, 0 lỗi |
| `validate_faq.py` | 0 lỗi |
| Canonical + host cũ | OK: mọi trang đúng 1 canonical về `https://blog.thuexemaynguyentu.com/`; 0 trang chứa host github.io |
| Sitemap | 6.842 URL, 0 URL thiếu tệp build, không chứa 404/draft/github.io |
| Suite engine liên quan template/gate (`test_gate_scope`, `test_related_cluster_data`, `test_faq`, `test_repair_agent`, `test_topic_universe`) | 5/5 PASS |
| `test_built_links` (dữ liệu) | 26 test OK |
| `test-pricing-table.cjs` | PASS |
| `validate-hub-intros.py` trên 62 tệp | PASS, 12.789 từ, front matter giữ nguyên 62/62 |

## Trang chủ đã đóng băng (so `site-baseline` và bản build cuối)

Title, `meta name=title`, meta description, H1 duy nhất (`Dịch vụ cho thuê xe máy 50cc–125cc tại Hà Nội`), mô tả hero và canonical:
**giống hệt từng ký tự**. Dữ liệu NAP và giá không bị sửa (không chạm `_data/business.yml`, `_data/pricing.yml`, `data/business-facts.json`).

## Số liệu kiểm kê (build cuối)

- 6.843 hàng trong `url-inventory.csv` (Home 1, Pillar 7, Hub 56, Listing 689, Page 14, Post 6.076; trang 404 không tính).
- 6.076/6.076 bài: tiêu đề HTML khớp nguồn, canonical đúng, H1 khớp tiêu đề, có breadcrumb, có trong sitemap.
- Liên kết nội bộ: 0 đích hỏng. Phân phối liên kết vào của bài trong HTML đã render: 0 bài không có liên kết vào; 1 bài 2–4 liên kết;
  3.909 bài 5–9; 2.166 bài ≥ 10 (INFERRED: không bài nào là orphan theo đồ thị render; chưa phải bằng chứng Google đã index).
- Meta description: 6.074/6.076 khớp nguồn; 2 bài bị `truncatewords: 50` cắt (mô tả ≥ 50 từ).
- Lỗi/rủi ro còn lại: xem `technical-issues.csv` (DESC_TOO_LONG 4, H1_IN_BODY 1 đã giảm nhẹ khi render, NOINDEX 1 = `/tim-kiem/` chủ đích,
  nhóm trùng khóa cannibalization 49/107 bài) và `fix-log.csv` (SEO-101 … SEO-109).

## Không đo được trong môi trường này (UNKNOWN / NOT VERIFIED)

- Trang live `blog.thuexemaynguyentu.com`: sandbox bị chính sách mạng từ chối (403 ở bước CONNECT); xác minh live đi qua GitHub Actions/Pages.
- Search Console của blog: chưa kết nối (xem `reports/seo-aeo/data/gsc-main-site-queries-90d.json`). Không có số liệu hiển thị/nhấp/xếp hạng của blog.
- Lighthouse/Core Web Vitals, Safari/iPhone thật.

## Kiểm tra đỏ sẵn trên `main` (không do đợt này)

Job `engine-tests` của Quality gate đã đỏ ở HEAD `4f61156e` (log run #1275): `test_hardening` 3 test
(`factory-publish.yml` có `schedule`/`workflow_dispatch` trái hợp đồng test; chuỗi `sk-` khớp nhầm trong `webmcp-ask-site.js`)
và `test_slugify_vi` (fixture cần ≥ 10 hàng PLANNED có chữ đ, hiện có 0). Không sửa vì ngoài phạm vi SEO và chạm hợp đồng
workflow writer/publisher. Ghi ở `fix-log.csv` mục SEO-104.


---

# QA — đợt 2 (2026-10-23): nội dung, lớp hiển thị, công cụ bảo trì

| Kiểm tra | Kết quả |
|---|---|
| `validate.py --scope chunk` trên từng worktree lô revise | PASS, 0 cảnh báo (6 lô) |
| `revise-published.py verify --backup` | OK cho cả 6 sao lưu (lô pháp lý + 5 lô giá), 0 vấn đề |
| `build-price-notices.py --check` trên cây đã gộp | OK (71 bài) |
| `check-price-consistency.py` sau đợt | FACT (main d794f64b, price-consistency.csv): factory MISMATCH 155 cụm/56 tệp, REVIEW 26/19, UNBOUND_STALE 36/24 — toàn bộ nằm trong 217 cụm của 74 tệp: 68 bài NOTICE_LAYER (có khối giá hiện hành) + 6 bài REVIEWED_FALSE_POSITIVE đã đọc tay; 0 cụm OPEN; trang tĩnh và legacy 0 |
| `check-regressions.py` trên build đã gộp | PASS 9/9 (H1 trang chủ khớp bản duyệt, canonical/H1 mỗi trang, favicon, phân trang ≤ 60 liên kết, breadcrumb, hub/pillar, lead block, sitemap 6.842 URL không noindex/404) |
| Quality gate / engine-tests | xanh ở mọi PR đã merge (bảng ở `deployment-verification.md`); lỗi đỏ sẵn của `engine-tests` (SEO-104) đã được commit `b96f69f7` sửa |
| Test mới | test_revise_published 17, test_price_phrases 19, test_legal_notices 6, test_topic_links 11, test_price_notices 9 |

Đã cập nhật so với đợt 1: mục "Kiểm tra đỏ sẵn trên `main`" của đợt 1 không còn đúng (SEO-104 → DONE).


---

# QA — đợt 3 (2026-10-23)

| Kiểm tra | Kết quả |
|---|---|
| `revise-published.py plan` lô legal-02 | 10/10 ELIGIBLE sau khi thu hẹp 3 bản vá (2 bài vượt 20% thay đổi, 1 bài tụt `word_count`; không nới ngưỡng); lô legal-04: 3/3 ELIGIBLE sau khi thu hẹp 2 bản vá (1 tụt `word_count`, 1 vượt 20%) |
| `revise-published.py verify --backup` | OK cho legal-02 (10 bài), legal-03 (BLG-05045), legal-04 (3 bài lệ phí) và deposit-02 (3 bài hoàn cọc), 0 vấn đề |
| `validate.py --scope chunk` | PASS, 0 cảnh báo trên từng nhánh |
| Test mới | test_cannibalization_leads 9 (đăng ký trong run-tests.py) |
| Quality gate / engine-tests | xanh ở mọi PR có gate (bảng ở `deployment-verification.md`) |
| `build-topic-links.py --check`, `build-price-notices.py --check` | OK |
| Jekyll build đầy đủ, cây trùng main 067bbdd2 | BUILD_EXIT=0, 662 s; 6.844 trang HTML; `check-built-links.py` PASS (0 liên kết nội bộ hỏng); `faq_parity_check.py`: 6.844 trang, 2 trang có FAQ, 0 lỗi; `check-regressions.py` PASS 9/9; sitemap 6.842 URL duy nhất |
| Kiểm kê lại từ bản build đó | `build-inventory` → `build-matrix` → `build-leads` → `enrich-inventory`: chỉ `url-inventory.csv` (42 hàng) và `inventory-summary.json` đổi; `_data/seo-leads.yml`, `_data/seo-topic-links.json`, `cannibalization-classification.csv` không đổi; BLG-05973 vào diện FRESHNESS_REVIEW vì có chính sách hết hạn 28/02/2027 (đúng chủ ý) |
| Đối chiếu pháp luật | 120 văn bản (legal-verification.json): 104 khớp, 16 có claim lệch; 33 bài: 12 sửa gốc, 19 khối đính chính, 2 chờ chủ duyệt |
