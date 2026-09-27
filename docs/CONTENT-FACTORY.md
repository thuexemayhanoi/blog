# CONTENT FACTORY — quy trình vận hành

Mục tiêu: sản xuất nội dung chất lượng có kiểm chứng cho blog, không phá nội dung legacy.

Đầu vào: taxonomy, inventory, business facts, state. Nguồn chuẩn: xem `AGENTS.md` mục 1.

## Kiến trúc dữ liệu

- `data/content-taxonomy.json` — 7 parent hub, 51 child hub. KHÔI PHỤC từ seed `data/state/taxonomy-config.json` (commit gốc), bằng `scripts/factory/restore-foundation.py`. Không sửa tay.
- `data/content-inventory.csv` — 483 bài legacy, 100% ánh xạ taxonomy, URL giữ nguyên. Khôi phục từ `data/state/existing-map.json` + `_posts/`.
- `_data/factory-taxonomy.yml`, `_data/factory-map.yml` — sinh cho layout hub (`hub.html`, `topic.html`). Không sửa tay.
- `data/content-matrix.csv` — BLOCKED: chưa từng được commit, không khôi phục được. Bằng chứng: `reports/factory/matrix-recovery-blocked.md`. Không nhận hàng PLANNED, không tự sinh matrix mới rồi gọi là khôi phục.
- `data/state/` — `checkpoint.json`, `writer-lock.json`, `transaction.json`.
- `reports/factory/` — sinh từ dữ liệu thật bằng `scripts/factory/generate-reports.py`, không ghi tay.

## Trạng thái hợp lệ hàng (khi có matrix)

`PLANNED → WRITING → QA → PASS → PUBLISHED`, và `REVIEW`, `REPAIR`, `BLOCKED`, `FAIL`, `EXISTING`. Batch 50 hàng/batch, ID tăng dần.

## Vòng đời một bài (quy trình bắt buộc, có bằng chứng từng bước)

1. Viết trong `_drafts/` (KHÔNG deploy, không vào sitemap, không vào danh sách bài — CI kiểm chứng bằng build).
2. Kiểm tra nội dung/nguồn: đọc lại, kiểm tra nguồn trích dẫn khi `source_required`.
3. Chấm QUALITY và SEO theo `docs/QUALITY-RUBRIC.md` (≥90/≥90). Điểm nội bộ, không phải điểm Google. Đánh giá nội dung cần AI/người đọc — kiểm tra tự động chỉ là điều kiện cần.
3b. GHI BẰNG CHỨNG GẮNG VỚI NỘI DUNG (bắt buộc từ 2026-09-27): `data/qa/<id>.json` phải có `source_path`, `content_sha256` (SHA-256 tệp draft SAU SỬA ĐỔI CUỐI), `matrix_row_sha256` (vân tay hàng matrix: title/intent/keyword/URL/path). Gate tái tính cả hai hash trước promote: đổi nội dung sau QA → STALE_QA_EVIDENCE, đổi hàng matrix → MATRIX_ROW_MISMATCH. Công thức vân tay hàng: SHA-256 của JSON sort-keys các trường `title, intent, primary_keyword, expected_url, output_path, canonical_url`.
4. Tối ưu an toàn (không nhồi từ khóa, không đổi ý tiêu đề).
5. BUSINESS FACT CHECK: mọi con số khớp `data/business-facts.json`; xung đột chính sách xem `reports/factory/policy-conflicts.md` (BLOCKED thì không viết).
6. LEGAL/SOURCE CHECK theo `docs/ARTICLE-RULES.md` mục Pháp lý (CLAIM → SUBJECT → CONDITION → QUY ĐỊNH HIỆN HÀNH → PHIÊN BẢN CÓ HIỆU LỰC → NGUỒN CHÍNH THỨC). Không chắc chắn → REVIEW/BLOCKED.
7. Chống trùng (cannibalization): đối chiếu tiêu đề chuẩn hóa + intent với bài đã xuất bản trong cùng child.
8. PUBLISH QUA CỔNG CỨNG: `python3 scripts/factory/publish-gate.py --draft _drafts/<file>.md --id BLG-XXXXX`. Gate kiểm tra máy: hàng matrix phải PASS, bằng chứng `data/qa/<id>.json` (quality ≥90, seo ≥90, business_fact PASS, legal PASS|NOT_REQUIRED, critical_failure false), lock tự do, transaction không treo, slug khớp output_path. Đạt: gate tự chuyển draft → `_posts/`, chốt ngày thật vào URL (bỏ placeholder `{date}`), chuyển matrix → PUBLISHED, cập nhật checkpoint. Không đạt: giữ nguyên trong `_drafts/`, exit 1, không đổi gì. Đã kiểm chứng gate từ chối trạng thái PLANNED/WRITING/QA, thiếu bằng chứng, điểm thấp, business FAIL (xem `scripts/factory/tests/test_publish_gate.py`). Một commit có thể rollback sạch.
9. BUILD/DEPLOY: Pages build, CI factory-validate xanh (matrix đã được duyệt TẠO MỚI — validate phải exit 0).
10. Kiểm tra live: URL thật trả 200, title/meta/canonical đúng, có trong sitemap, hiển thị đúng ở hub cha/hub con.

Kết quả mong đợi mỗi bài: đủ 5 điều kiện gate (xem `AGENTS.md` mục 5). FAIL bất kỳ → giữ trong `_drafts/`, ghi REPAIR, không hạ gate.

## Chunk

Một chunk tối đa 10 bài. Chỉ nhận chunk khi: transaction inactive, lock tự do, checkpoint cho phép, matrix có hàng claimable (hiện CÓ — checkpoint `next_claimable_id` tính từ matrix thật). Chunk chạy thật 2026-09-27: BLG-00484/00485/00493 (3 bài, cùng C-THUE-GIA, không trùng intent) qua toàn chu trình write → QA evidence → gate → PUBLISHED → deploy → live 200 + sitemap. Kiểm chứng bài factory trong `_posts` phải khớp hàng matrix PUBLISHED: `validate.py` tự FAIL khi có `_posts` mang article_id không hợp lệ. Self-healing theo thứ tự: pending transaction → chunk dở → REPAIR → REVIEW (cần đọc nội dung, không tự động) → POST_AUDIT/FRESHNESS quá hạn → PLANNED mới.

## Transaction + lock (an toàn)

1. Trước khi mutate: ghi `transaction.json` `active: true`, mô tả bước.
2. Xong: cập nhật report/checkpoint rồi đóng transaction.
3. Chạy sau thấy `active: true`: recover trước khi làm việc mới.
4. Lock giữ trong suốt chunk, nhả khi checkpoint an toàn. Không hai writer trên cùng bài.

## Dừng an toàn và rollback

Điều kiện dừng và rollback: xem `AGENTS.md` mục 6 và `docs/RECOVERY.md`. Checkpoint luôn ghi sau mỗi chunk; resume từ checkpoint, không restart.

## CI/CD

- `.github/workflows/factory-validate.yml`: restore idempotent + report khớp dữ liệu + validate.py + build Jekyll + nháp không deploy + hub render. CI đỏ với "MATRIX BLOCKED" là có chủ đích.
- `.github/workflows/publish-queue.yml`: CHỈ campaign cũ hanoi-seo-480 (tệp `NNN-slug.md` trong `_queue/`). Queue hiện rỗng bài → không xuất bản gì. Kết quả "skipped" của validator cũ KHÔNG dùng để tuyên bố `_posts` PASS.
- Pages build success KHÔNG đủ để tuyên bố hoàn thành; phải kiểm tra runtime.

## Scheduler

TODO/NOT IMPLEMENTED: chưa có scheduler cho factory. Không tuyên bố "chạy nền 09:00 hằng ngày" khi chưa có scheduler thật trong repo này.

## Báo cáo mỗi lần chạy

MAIN HEAD, Pages run ID, BUILD/DEPLOY status, tệp thay đổi, kiểm tra runtime, trạng thái BLOCKED. Ghi vào `reports/factory/latest.md` bằng `generate-reports.py` + phần chạy tay có bằng chứng.

## Vòng đời đầy đủ (đã chạy thật 2026-09-27)

claim (từ `next_claimable_id` trong checkpoint, tối đa 10 bài/chunk) → viết `_drafts/YYYY-MM-DD-slug.md` (frontmatter đủ, `article_id`, permalink đúng taxonomy) → QA + chấm điểm, ghi `data/qa/<id>.json` → set hàng matrix PASS → `publish-gate.py` promote → chạy `restore-foundation.py` + `generate-reports.py` → commit theo nhóm → CI xanh → Pages deploy → kiểm tra live (200, sitemap, hub, canonical). Resume: checkpoint giữ `last_completed_article_id` + `in_progress_chunk`; `generate-reports.py` không bao giờ reset tiến độ (kiểm chứng trong `scripts/factory/tests/test_reports_resume.py`). Rollback: revert commit promote, chạy lại `generate-reports.py`; KHÔNG force push.

## Hợp đồng writer bài factory (bắt buộc từ 2026-09-27)

Writer CHỈ sản xuất NỘI DUNG ngữ nghĩa của bài. Layout sở hữu toàn bộ UI:

- KHÔNG tự viết CSS toàn cục hoặc inline style.
- KHÔNG lặp markup thiết kế (card/grid/breadcrumb/TOC đã có trong layout).
- KHÔNG nhúng ảnh trang trí tùy tiện — chỉ ảnh thật có trong repo và có alt.
- KHÔNG tự cài điều hướng bài viết (layout có sẵn bài trước/sau + liên quan).
- Frontmatter bắt buộc: title, date, categories, description, lang, permalink
  đúng taxonomy, parent_id, child_id, article_id.
- Bài thừa hưởng tự động: header + breadcrumb taxonomy, TOC, bảng responsive,
  typography, bài viết liên quan, CTA, footer — từ `_layouts/post.html` + CSS
  dùng chung. Markup bài chỉ là Markdown ngữ nghĩa: h2/h3, p, ul/ol, table,
  blockquote.