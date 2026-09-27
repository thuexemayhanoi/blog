# AGENTS.md — hợp đồng vận hành cho agent làm việc trong thuexemayhanoi/blog

Kho: `thuexemayhanoi/blog` · Nhánh: `main` · Site: https://thuexemayhanoi.github.io/blog/ · Base URL: `/blog` · Ngôn ngữ công khai: chỉ tiếng Việt.

## 1. Thứ tự đọc bắt buộc mỗi lần chạy

1. `AGENTS.md` (file này)
2. `README.md`
3. `docs/CONTENT-FACTORY.md` — quy trình vận hành factory, gate xuất bản
4. `docs/TAXONOMY.md` — kiến trúc chủ đề 7 cha / 51 con
5. `docs/ARTICLE-RULES.md` — quy tắc viết bài
6. `data/content-taxonomy.json` — taxonomy máy đọc được
7. `data/content-inventory.csv` — kiểm kê 483 bài legacy
8. `data/business-facts.json` — nguồn chuẩn dữ liệu kinh doanh
9. `reports/factory/policy-conflicts.md` — xung đột chính sách đang BLOCKED
10. `reports/factory/progress.json` → `data/state/checkpoint.json`
11. `data/state/transaction.json` → `data/state/writer-lock.json`
12. `reports/factory/matrix-recovery-blocked.md` — lịch sử matrix: đã giải quyết bằng TẠO MỚI được chủ xe duyệt
13. `docs/RECOVERY.md` — phục hồi sự cố; `docs/SEO-*.md` khi làm SEO

Nguồn dữ liệu chuẩn (source of truth), theo thứ tự ưu tiên:
- Dữ liệu kinh doanh: `_data/business.yml`, `_data/pricing.yml` → kết xuất `data/business-facts.json`.
- Taxonomy: `data/state/taxonomy-config.json` (seed, không chỉnh sửa) → `data/content-taxonomy.json` (khôi phục từ seed).
- Ánh xạ bài legacy: `data/state/existing-map.json` → `data/content-inventory.csv`.
- Ma trận nội dung: ĐÃ ĐƯỢC CHỦ XE DUYỆT TẠO MỚI (2026-09-27, KHÔNG PHẢI KHÔI PHỤC NGUYÊN BẢN): 833 hàng = 473 EXISTING + 10 REVIEW + 350 planned ban đầu (3 đã PUBLISHED). Chênh 6.220 hàng so với tổng planned_target 6.570 trong seed taxonomy: BÁO THIẾU, không đệm hàng rỗng. Sinh lại bằng `scripts/factory/generate-matrix.py` (idempotent, giữ trạng thái runtime).

## 2. Phạm vi: CHỈ repo blog này

- Blog và shop là hai bên kinh doanh khác nhau trong gia đình. KHÔNG đồng bộ dữ liệu từ `thuexemayhanoi/shop` (hoặc website /shop). Khác biệt dữ liệu giữa blog và shop KHÔNG phải lỗi.
- Dữ liệu kinh doanh hiện tại của /blog (điện thoại 0942 467 674, 112 Nguyễn Văn Cừ Bồ Đề Long Biên Hà Nội, giờ 09:00–21:00, bảng giá `_data/pricing.yml`, chính sách) được GIỮ NGUYÊN.
- Nếu dữ liệu bên trong chính /blog mâu thuẫn với nhau: ghi rõ từng nguồn trong `reports/factory/policy-conflicts.md`, đánh dấu BLOCKED, KHÔNG tự chọn nguồn, KHÔNG bịa chính sách. Chỉ chủ xe quyết định.

## 3. Lấy trạng thái, lock, transaction, checkpoint

Thứ tự đọc khi bắt đầu: `data/state/transaction.json` → `data/state/checkpoint.json` → `data/state/writer-lock.json` → `reports/factory/progress.json`.

Quy tắc:
- Transaction `active: true` → recover/hoàn tất GIAO DỊCH ĐÓ trước, không nhận việc mới (xem `docs/RECOVERY.md`).
- Writer-lock `locked: true` → không chạy writer thứ hai trên cùng bài/chunk. Lấy lock trước khi nhận chunk, nhả lock sau khi checkpoint an toàn.
- Checkpoint là điểm resume duy nhất. KHÔNG restart factory, KHÔNG dựng lại ma trận từ đầu.
- Không chạy hai writer trên cùng một bài bất kể hoàn cảnh.

## 4. Lệnh kiểm tra bắt buộc (phải chạy thật, không khai báo)

Từ gốc repository:
- `python3 scripts/factory/restore-foundation.py` — khôi phục/sinh taxonomy, inventory, `_data/factory-*`. Idempotent: chạy hai lần cho kết quả giống hệt.
- `python3 scripts/factory/generate-reports.py` — sinh report + checkpoint từ dữ liệu thật. Idempotent.
- `python3 scripts/factory/validate.py` — mã 0 PASS, 1 FAIL, 2 BLOCKED (thiếu matrix).
- `python3 scripts/factory/manifest.py --id BLG-XXXXX` — sinh manifest một hàng (yêu cầu matrix).
- `node scripts/validate-queue.js _queue` — CHỈ cho campaign cũ hanoi-seo-480 (tệp `NNN-slug.md`). "skipped" khi queue rỗng KHÔNG nghĩa là `_posts` PASS.

CI (`.github/workflows/factory-validate.yml`) chạy restore + reports + matrix idempotent + tests + build Jekyll + kiểm tra nháp không deploy + validate. Từ khi matrix được duyệt TẠO MỚI, CI phải XANH (validate exit 0). Không chỉ dựa vào Pages build success để tuyên bố hoàn thành.
- `python3 scripts/factory/publish-gate.py --draft _drafts/<file>.md --id BLG-XXXXX` — cổng promote: chỉ nhận hàng PASS + bằng chứng `data/qa/<id>.json` (quality ≥90, seo ≥90, business_fact PASS, legal PASS|NOT_REQUIRED, không critical failure). Từ chối mọi trạng thái khác, tự chốt ngày thật vào URL, cập nhật checkpoint.

## 5. Tiêu chí xuất bản (gate)

Xuất bản một bài qua factory yêu cầu TẤT CẢ:
- QUALITY ≥ 90/100 VÀ SEO ≥ 90/100 (rubric trong `docs/QUALITY-RUBRIC.md`; đây là điểm nội bộ, không phải điểm Google).
- BUSINESS FACT PASS: mọi con số/khẳng định kinh doanh truy được về `data/business-facts.json`.
- LEGAL PASS hoặc NOT REQUIRED (theo `source_required`/`legal_risk` của child trong taxonomy).
- KHÔNG critical failure. Không hạ ngưỡng, không hạ gate để lấy PASS.
- Kiểm tra tự động (validator, độ dài, từ khóa) KHÔNG thay thế đánh giá nội dung: chất lượng và tính đúng pháp lý phải do AI/người đọc xác nhận, có bằng chứng.

Vòng đời một bài: viết trong `_drafts/` (KHÔNG deploy) → kiểm tra nội dung/nguồn → chấm QUALITY + SEO → tối ưu an toàn → business facts → legal/source → chống trùng (cannibalization) → promote sang `_posts/` → build/deploy → kiểm tra live (URL thật, title/meta/canonical, sitemap).

## 6. Điều kiện dừng an toàn và rollback

Dừng ngay khi: transaction không thể hòa giải, conflict Git, CI đỏ không phải lý do đã biết, business fact/legal claim không kiểm chứng được, QA hỏng hệ thống. Hoàn tất bước an toàn hiện tại → cập nhật checkpoint/report → nhả lock (nếu an toàn) → chỉ push phần xanh.

Rollback: không force push. Revert commit qua commit mới; khôi phục report/checkpoint bằng cách chạy lại `generate-reports.py`; bài đã promote nhầm → đưa về `_drafts/` bằng commit revert. Chi tiết: `docs/RECOVERY.md`.

## 7. Quy tắc cứng với nội dung hiện có

- KHÔNG viết lại bài EXISTING/PUBLISHED trừ khi có yêu cầu audit mới.
- KHÔNG đổi URL legacy (`/blog/YYYY/MM/DD/slug/`), KHÔNG xóa, KHÔNG đổi tên tệp `_posts/`, KHÔNG noindex hàng loạt.
- KHÔNG tự tăng lịch xuất bản, không bật lại campaign cũ, không tạo lịch trùng.
- 483 bài legacy phải còn nguyên sau mỗi lần chạy (validator kiểm tra).
- Bài mới: `_posts/` phẳng, tên `YYYY-MM-DD-slug.md`, permalink theo taxonomy, frontmatter đủ (xem `docs/ARTICLE-RULES.md`).
- Không push file bị cắt (truncate): dùng checkout/blob đầy đủ, kiểm tra tính toàn vẹn trước push.
- KHÔNG tuyên bố chạy nền/scheduler khi chưa có scheduler thật. Hiện KHÔNG có scheduler riêng cho factory; workflow `publish-queue.yml` chỉ thuộc campaign cũ (queue rỗng bài thì không xuất bản gì).
- Không bịa: khuyến mại, phí giao xe cố định, số lượng khách, số năm kinh nghiệm, xếp hạng, cam kết, hỗ trợ 24/7, đánh giá khách hàng, review/rating trong schema, hứa thứ hạng.
- Không ghi PASS/VERIFIED khi chưa chạy thật. Mục chưa kiểm tra ghi NOT VERIFIED; phần chưa triển khai ghi TODO/NOT IMPLEMENTED.

## 8. Trạng thái BLOCKED hiện tại (phải đọc)

- `data/content-matrix.csv`: ĐÃ GIẢI QUYẾT — chủ xe duyệt TẠO MỚI ngày 2026-09-27 (không tìm được bản gốc). Đây là ma trận MỚI, không phải khôi phục. Chi tiết sinh/tái sinh: `reports/factory/matrix-report.md` và `scripts/factory/generate-matrix.py`. Gọi matrix mới là "khôi phục nguyên bản" vẫn là BỊ CẤM.
- Xung đột chính sách (khoảng đặt cọc, phí trễ, bảo hiểm/mũ bảo hiểm): BLOCKED — `reports/factory/policy-conflicts.md`.
- 10 hàng legacy REVIEW (cặp cannibalization): cần đọc nội dung từng cặp để xử lý, không tự động hóa được: danh sách trong `docs/SEO-OWNERSHIP.md`.

## 9. Bàn giao mỗi lần chạy

Bắt buộc trong báo cáo cuối: MAIN HEAD (SHA), GitHub Pages run ID, BUILD/DEPLOY status, tệp thực sự thay đổi, các kiểm tra runtime đã làm (URL công khai, mobile ~390px, menu/footer/breadcrumb, calculator/chatbot), và trạng thái các mục BLOCKED. Không ghi Safari/iPhone khi chưa thật sự test trên đó.
