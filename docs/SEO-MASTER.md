# SEO MASTER — bộ dữ liệu và quy trình SEO toàn site

Tài liệu này mô tả bộ SEO Master (kiểm kê URL, ma trận từ khóa–intent, ánh xạ chủ đề, rủi ro cannibalization,
lỗi kỹ thuật, nhật ký sửa, checkpoint) nằm ở `reports/factory/seo-master/`. Đây là **bản chụp có ngày**, không phải nguồn
sự thật vận hành: số bài, trạng thái, QA vẫn đọc từ `data/content-matrix.csv`, `data/state/` và `data/qa/`
(xem `AGENTS.md`). Bộ SEO Master chỉ ĐỌC các nguồn đó, không ghi vào chúng.

## Quy tắc bất biến (chủ website duyệt)

- Trang chủ: giữ nguyên H1, SEO Title, Meta Description, mô tả hero đã duyệt ở commit `4f61156e`.
  Thứ tự từ khóa: (1) dịch vụ cho thuê xe máy 50cc–125cc tại Hà Nội, (2) thuê xe máy Hà Nội dùng tự nhiên.
- Không đổi URL, slug, permalink, canonical hàng loạt; không xóa bài; không noindex hàng loạt; không redirect về trang chủ.
- Không sửa dữ liệu kinh doanh (NAP, giá, cọc, chính sách): nguồn duy nhất `data/business-facts.json`, `_data/business.yml`, `_data/pricing.yml`.
- Không tạo hub/trang rỗng, doorway, nội dung AI trùng lặp. Không đụng workflow writer/QA/publisher.

## Nhãn bằng chứng

- **FACT** — đo được từ tệp, build cục bộ hoặc GitHub Actions (ghi rõ nguồn).
- **INFERRED** — suy luận có căn cứ (regex, heuristic, hành vi công cụ tìm kiếm).
- **UNKNOWN** — chưa có dữ liệu (ví dụ: chưa có Search Console cho `blog.thuexemaynguyentu.com`; môi trường chạy
  không truy cập được domain live nên xác minh live đi qua GitHub Actions/Pages API).

## Tệp trong `reports/factory/seo-master/`

| Tệp | Nội dung | Sinh bởi |
|---|---|---|
| `url-inventory.csv` | một hàng/URL: loại trang, intent, chủ đề, metadata, canonical, heading, JSON-LD, liên kết vào/ra, orphan risk; cuối hàng là 9 cột vai trò/hành động (xem dưới) | `build-inventory.py --site <_site>`, rồi `enrich-inventory.py` thêm 9 cột cuối |
| `technical-issues.csv` | mỗi lỗi: mã, ưu tiên, URL/tệp, bằng chứng, nguyên nhân, cách xử lý, trạng thái | cùng script |
| `inventory-summary.json` | số liệu tổng hợp của lần quét | cùng script |
| `keyword-intent-map.csv` | 12 nhóm từ khóa thương mại: URL chủ lực, bổ trợ, xung đột với website chính, ưu tiên | `scripts/seo/build-matrix.py` |
| `pillar-topic-mapping.csv` | 34 nhóm chủ đề → 7 pillar / hub con hiện có (không tạo hub mới) | cùng script |
| `cannibalization-risk.csv` | nhóm trùng khóa matrix + cặp tiêu đề gần trùng, URL chủ lực đề xuất | cùng script |
| `internal-link-recommendations.csv` | khoảng trống liên kết về URL chủ lực (từ đồ thị HTML đã render) | cùng script |
| `internal-link-candidates.csv` | tối đa 25 bài/nhóm khớp từ khóa nhưng chưa liên kết về URL chủ lực (danh sách bảo trì nhỏ, trạng thái OPEN) | cùng script |
| `cannibalization-plan.md` | kế hoạch đọc được cho chủ: nhóm trùng khóa, URL chủ lực đề xuất, cặp tiêu đề gần trùng (chưa thực hiện) | cùng script |
| `build-performance.md` | đo thời gian build Jekyll trước/sau và nguyên nhân | tay (có số đo) |
| `fix-log.csv`, `qa-results.md`, `deployment-verification.md` | nhật ký sửa, kết quả kiểm thử, xác minh deploy | tay, đối chiếu commit |
| `checkpoint.json` | trạng thái DONE / IN_PROGRESS / BLOCKED và điểm tiếp tục | tay |

Cấu hình duy nhất cho ma trận: `scripts/seo/seo-matrix-config.yml` (URL chủ lực, regex nhóm). Sửa ở đó rồi chạy lại.

## Công cụ và dữ liệu dùng chung (`scripts/seo/`)

| Tệp | Vai trò |
|---|---|
| `build-inventory.py` | kiểm kê + audit từ `_posts`, matrix, taxonomy và HTML đã render (đọc-only) |
| `build-matrix.py` | Keyword–Intent Map (12 nhóm), ánh xạ 34 nhóm, cannibalization, gợi ý liên kết |
| `enrich-inventory.py` | thêm vào `url-inventory.csv`: `seo_role`, `cannibalization_role`, `keyword_groups`, `secondary_keywords`, `needs_action`, `fix_priority`, `action_status`, `staleness_risk`, `stale_signals` |
| `build-leads.py` | chọn bài chủ lực cho từng hub con → `_data/seo-leads.yml` (sinh tự động, không sửa tay) |
| `validate-hub-intros.py` | kiểm phần giới thiệu pillar/hub (không chữ số, không từ cấm, liên kết hợp lệ, không trùng) và ghi vào `.md` khi PASS |
| `seo-matrix-config.yml` | cấu hình duy nhất: URL chủ lực, regex nhóm từ khóa/chủ đề |
| `check-regressions.py` | kiểm tra hồi quy SEO trên `_site` đã build (9 bất biến: trang chủ đóng băng, canonical/H1, favicon, phân trang, hub không rỗng, khối bài chủ lực, breadcrumb, sitemap) |
| `frozen-homepage.json` | chuỗi H1/title/meta/hero/canonical trang chủ đã duyệt ở `4f61156e`; chỉ đổi khi chủ duyệt phiên bản mới |

Kiểm tra hồi quy sau mỗi build cục bộ: `python3 scripts/seo/check-regressions.py --site /tmp/site` (thoát 0 chỉ khi PASS).

`_data/seo-leads.yml` được `_layouts/topic.html` đọc để in khối "Bài nên đọc trước". Chạy lại `build-leads.py` (sau khi làm mới
`url-inventory.csv`) khi muốn cập nhật; script cho kết quả giống hệt nếu dữ liệu nguồn không đổi.

Báo cáo nằm dưới `reports/factory/` có chủ đích: đường dẫn này thuộc nhóm "content" của `scripts/factory/gate-scope.py`,
nên commit chỉ cập nhật báo cáo không kích hoạt build đầy đủ của Quality gate.

## Cột vai trò và hành động trong `url-inventory.csv`

Mỗi URL có đúng một `seo_role` và một `fix_priority`; URL không có lỗi đã biết mang `needs_action` rỗng, `fix_priority = P4`, `action_status = NONE`.

| Cột | Giá trị | Nhãn |
|---|---|---|
| `seo_role` | HOME, PILLAR, HUB, LISTING, PAGE, LEAD_POST (nằm trong `_data/seo-leads.yml`), CANNIBALIZATION_LEAD, SUPPORT_POST, TOPIC_POST | FACT |
| `cannibalization_role` | LEAD (URL chủ lực đề xuất của nhóm trùng khóa), SUPPORT (bài bổ trợ), NEAR_TITLE (tiêu đề gần trùng, Jaccard ≥ 0,7 trong cụm); ưu tiên LEAD > SUPPORT > NEAR_TITLE | FACT (tiêu đề) + INFERRED (intent) |
| `needs_action` | CANONICAL_OR_H1_BROKEN, NOT_IN_SITEMAP (P0); ORPHAN_NO_INBOUND (P1); H1_IN_BODY, CANNIBALIZATION_SUPPORT, SLUG_D_STRIPPED (P2); DESC_TOO_LONG, LOW_INBOUND, NEAR_TITLE_PAIR, FRESHNESS_REVIEW (P3); NOINDEX_INTENTIONAL (P4) | FACT, riêng FRESHNESS_REVIEW là INFERRED |
| `action_status` | OPEN; BLOCKED_URL_CONTRACT (đổi URL bị cấm); BLOCKED_EVIDENCE_SHA (sửa bài đã xuất bản làm lệch SHA bằng chứng QA); DEFERRED_OWNER_PLAN (chờ kế hoạch cannibalization); EXPECTED; NONE | FACT |
| `staleness_risk`, `stale_signals` | HIGH = nội dung có cả con số (tiền, %, km/h) lẫn từ ngữ pháp lý (nghị định, luật, mức phạt…); MEDIUM = có một trong ba tín hiệu AMOUNT/LEGAL/TIME; LOW = không có | INFERRED (regex trên nội dung bài, không kết luận sai/đúng) |

`SLUG_D_STRIPPED` là phép khớp tuyệt đối: slug URL thật bằng slug cũ (đ bị xóa) tính từ tiêu đề trong matrix và khác slug đúng. `FRESHNESS_REVIEW`
chỉ là gợi ý rà soát theo nguồn chính thức (`docs/SOURCE-RESEARCH.md`); không sửa số liệu kinh doanh/pháp lý ngoài `data/business-facts.json`.

## Chạy lại (cục bộ, không cần mạng ngoài)

```bash
# 1) build Jekyll ra thư mục ngoài repo (ví dụ /tmp/site)
jekyll build --destination /tmp/site
# 2) kiểm kê + audit (nguồn + HTML render)
python3 scripts/seo/build-inventory.py --site /tmp/site --graph-out /tmp/graph.json
# 3) ma trận từ khóa, ánh xạ 34 nhóm, cannibalization, gợi ý liên kết
python3 scripts/seo/build-matrix.py --graph /tmp/graph.json
# 4) thêm cột vai trò/hành động/ưu tiên vào url-inventory.csv (luôn chạy SAU hai bước trên, vì bước 2 ghi lại tệp)
python3 scripts/seo/enrich-inventory.py
```

## Giao thức tiếp tục sau gián đoạn

1. `git pull --ff-only origin main`, đối chiếu HEAD với `checkpoint.json` (`head_at_checkpoint`).
2. Đọc mục `items` trong checkpoint: chỉ làm tiếp hạng mục `IN_PROGRESS`/`OPEN`, không làm lại hạng mục `DONE`.
3. Trước khi push thay đổi engine (`_layouts`, `_includes`, `_data`, `scripts`): chạy `validate.py --scope chunk`,
   build cục bộ, `check-built-links.py`, và kiểm tra HTML khác biệt chỉ nằm ở khối dự kiến.
4. Không công bố hoàn thành khi Pages deploy chưa SUCCESS (đọc job `deploy` của run "pages build and deployment").

## Ghi chú vận hành quan trọng (FACT, 2026-10-22)

- Job `gate` của `quality-gate.yml` có `timeout-minutes: 20`; bước Jekyll build trên GitHub mất ~18 phút trước tối ưu
  template, nên mọi thay đổi engine có nguy cơ bị hủy. Xem `reports/factory/seo-master/build-performance.md`.
- Mỗi push của publisher kích hoạt một build Pages; các build bị hủy khi có push mới hơn. Giảm thời gian build
  là điều kiện để các lần deploy hoàn tất thay vì bị hủy hàng loạt.
