# MASTER FIX MATRIX — theo dõi lỗi và trạng thái

Mỗi hàng: lỗi → nguyên nhân → tệp/commit sửa → kiểm thử → kết quả live → trạng thái. Trạng thái: VERIFIED / NOT VERIFIED / BLOCKED. Cập nhật sau mỗi lần chạy; không ghi PASS khi chưa kiểm tra.

GHI CHÚ LỊCH SỬ (2026-09-30): các hàng nhắc tới workflow `factory-operator.yml` / `factory-validate.yml` / `factory-capacity-validate.yml` / `factory-watchdog.yml` / `publish-queue.yml` / `test_push_rebase_overlap.py` là mô hình TRƯỚC hợp đồng 3 workflow; các tệp đó đã retire (docs/factory-workflow-contract.md) — không phải lỗi, không cần sửa lại.

| # | Lỗi | Nguyên nhân | Tệp/commit sửa | Kiểm thử | Kết quả live | Trạng thái |
|---|---|---|---|---|---|---|
| A1 | `data/content-matrix.csv` thiếu dù report cũ ghi "10.000 hàng" | Tệp sinh lúc bootstrap chưa bao giờ được commit; không có trong lịch sử git, nhánh, hay `data/state/foundation-seed/` (thư mục này cũng không tồn tại) | Không thể sửa bằng cách tạo matrix mới. Bằng chứng + phương án: `reports/factory/matrix-recovery-blocked.md` | `list_commits` đường dẫn: 0 kết quả; 20 ID ví dụ đối chiếu khớp ánh xạ tái tạo | N/A | BLOCKED (chờ chủ xe cấp bản gốc hoặc duyệt tái sinh matrix mới) |
| A2 | `data/content-taxonomy.json` thiếu | Chưa commit khi bootstrap | `scripts/factory/restore-foundation.py` sinh từ seed `data/state/taxonomy-config.json` | `validate.py`: 7 parent/51 child, ID/slug khớp seed 100% | Không ảnh hưởng giao diện | VERIFIED |
| A3 | `data/content-inventory.csv` thiếu | Chưa commit khi bootstrap | `restore-foundation.py` sinh từ `data/state/existing-map.json` + `_posts/` | 483/483 bài ánh xạ, URL giữ nguyên, counts theo parent khớp report cũ | Không ảnh hưởng giao diện | VERIFIED |
| A4 | `validate.py` crash `FileNotFoundError` khi thiếu file; report ghi số tay | Validator đọc thẳng không kiểm tra tồn tại | Viết lại `scripts/factory/validate.py`: báo thiếu rõ ràng, mã 0/1/2; `generate-reports.py` sinh report từ dữ liệu thật | Chạy thật: PASS các phần nền, BLOCKED matrix (exit 2), manifest.py exit 2 rõ ràng | N/A | VERIFIED |
| B1 | Hub cha/hub con trống bài (mapping không hoạt động) | `_data/factory-taxonomy.yml`, `_data/factory-map.yml` không tồn tại; layout đọc `site.data.factory-*` | Sinh 2 tệp `_data` từ seed; thêm bước CI kiểm tra | `validate.py` + build trong CI | Xem mục E cuối file | VERIFIED |
| B2 | Lookup mapping bài legacy luôn rỗng | `post.url | split: '/' | last` trả chuỗi rỗng với URL có dấu `/` cuối | `_layouts/hub.html`, `_layouts/topic.html`: dùng `post.slug` | CI build kiểm hub render số bài | Xem mục E cuối file | VERIFIED |
| B3 | 39 link trong `chu-de.md` thiếu baseurl → 404 ở domain gốc | Link viết cứng `/thue-xe/...` không qua `relative_url` | `chu-de.md`: toàn bộ link qua `relative_url`; thêm đúng một H1 | Đếm link qua `grep`; CI build kiểm tra `_site/chu-de/index.html` chứa `/blog/thue-xe/gia-thue` | Xem mục E cuối file | VERIFIED |
| B4 | Thiếu H1 ở `/blog/chu-de/` | Layout `default` không render H1, trang không tự có | `chu-de.md`: thêm `# Tất cả chủ đề cẩm nang` (duy nhất) | Render check trong CI build | Xem mục E cuối file | VERIFIED |
| B5 | 7 child hub có bài nhưng không có trang công khai (Honda Wave/Vision/Air Blade/Click, Biển báo, Ngoại thành, Cung đường nội thành) | Chưa tạo trang hub lúc bootstrap | Tạo 7 trang `layout: topic` đúng permalink taxonomy | `validate.py` WARN=0 | Xem mục E cuối file | VERIFIED |
| B6 | H1 parent hub hiển thị slug thô ("thue-xe") | Title frontmatter dùng slug làm tiền tố | Sửa title 6 trang hub cha thành tên chủ đề tiếng Việt | Đọc lại frontmatter | Xem mục E cuối file | VERIFIED |
| C1 | Validator queue cũ chỉ nhận `NNN-slug.md`; "skipped" bị hiểu là PASS toàn `_posts` | Hai campaign trộn lẫn | Tách trong `docs/CONTENT-FACTORY.md`, `AGENTS.md`, `reports/factory/policy-conflicts.md`; CI factory riêng | Đọc docs + CI | N/A | VERIFIED |
| C2 | Xung đột chính sách nội bộ (cọc 2–5 triệu, phí trễ 20k/giờ chỉ có trong validator cũ) | Hai nguồn fact khác nhau trong /blog | `reports/factory/policy-conflicts.md`: ghi từng nguồn, BLOCKED, không tự chọn | Đối chiếu 3 nguồn | N/A | BLOCKED (chờ chủ xe quyết định) |
| C3 | Không có vùng nháp không deploy | Chưa có `_drafts/` | Tạo `_drafts/` + mẫu; CI build chứng minh nháp không vào sitemap/output | CI build + grep | Xem mục E cuối file | VERIFIED |
| C4 | Gate chỉ dựa Pages build success | Thiếu CI validator | `.github/workflows/factory-validate.yml`: restore idempotent, report khớp dữ liệu, validate, build, nháp, hub | Chạy workflow thật trên GitHub | Run 36299837072 tại HEAD 1bb9f129c9: mọi bước bằng chứng SUCCESS; chỉ "Validate foundation" fail đúng chủ đích vì matrix BLOCKED | VERIFIED (đỏ có chủ đích, không bị che) |
| A5 | Audit cũ ghi sai định dạng URL legacy (`/blog/YYYY/MM/DD/slug/`) | URL thật do Jekyll sinh gồm tên danh mục có dấu + ngày frontmatter chuẩn hoá UTC: `/blog/kinh nghiệm/2026/09/17/...` | `restore-foundation.py` + `validate.py` ghi đúng quy tắc thật; inventory ghi URL thật | Đối chiếu 483/483 URL với `sitemap.xml` công khai: khớp 100% | Live: mọi URL inventory trả 200 | VERIFIED |
| D1 | Thiếu AGENTS.md; README lỗi thời; docs trùng lặp | Chưa chuẩn hóa | `AGENTS.md`, `README.md`, docs cập nhật; `docs/mistral/README.md` thành con trỏ | Đọc lại | N/A | VERIFIED |

## E. Kiểm tra live sau deploy — kết quả thật tại HEAD 1bb9f129c9

Pages deploy run 36299836303: success. Factory validate run 36299837072: các bước bằng chứng đều SUCCESS; chỉ bước "Validate foundation" thất bại đúng chủ đích (matrix BLOCKED, exit 2).

Kiểm tra live ngày 27/09/2026, tất cả trả 200:

- Trang chủ `/blog/`, `/blog/chu-de/` (H1 "Tất cả chủ đề cẩm nang" render đúng, link có tiền tố `/blog/`).
- 7 hub cha: thue-xe, kinh-nghiem, an-toan-phap-ly, cung-duong, du-lich và 2 hub còn lại — H1 hiển thị tên chủ đề tiếng Việt, không còn slug thô.
- Hub con mới tạo: `/blog/xe-may/honda-wave/` (H1 "Honda Wave", bài `2026/09/18/thue-honda-wave-o-ha-noi` render trong danh sách), `/blog/an-toan-phap-ly/bien-bao/`, `/blog/du-lich/ngoai-thanh/`, `/blog/cung-duong/cung-duong-noi-thanh/`.
- Bài legacy URL định dạng thật: `/blog/du%20l%E1%BB%8Bch/2026/09/13/goi-y-kham-pha-ha-noi-bang-xe-may-cho-nguoi-moi/` → 200.
- `sitemap.xml`: 544 loc, 483 URL bài, không có `_drafts` (grep `mau-nhap-bai-moi` = 0).

Không kiểm được trong lần này (không có môi trường): Safari/iPhone thực, Lighthouse/Core Web Vitals đo thật — NOT VERIFIED.

## F. Đợt sửa 2026-09-27 (matrix TẠO MỚI + UI/UX + publish gate + chunk chạy thật)

| ID | Lỗi | Nguyên nhân | Sửa | Kiểm thử | Kết quả live | Trạng thái |
|---|---|---|---|---|---|---|
| F1 | Matrix bị mất vĩnh viễn, không nhận được hàng nào | Bản gốc không từng commit, không khôi phục được | Chủ xe duyệt TẠO MỚI: 833 hàng = 473 EXISTING + 10 REVIEW (giữ nguyên) + 350 PLANNED; sinh từ `matrix-seed.json` + taxonomy + inventory; ghi rõ TẠO MỚI không phải khôi phục | `generate-matrix.py` chống trùng máy (id/slug/canonical/output_path/intent/keyword) tất cả PASS; CI bước matrix idempotent SUCCESS; chạy lại không mất trạng thái PUBLISHED | N/A (dữ liệu) | VERIFIED |
| F2 | Chênh chỉ tiêu: seed chỉ có 350 hàng có giá trị riêng so với planned_target 6.570 | Không đủ chủ đề thật | BÁO THIẾU 6.220 hàng, không đệm hàng rỗng/nhân bản (điều cấm) | `matrix-report.md` ghi rõ từng child | N/A | BÁO THIẾU (chủ động, đúng yêu cầu) |
| F3 | `generate-reports.py` ghi đè checkpoint, published=0, updated_at lấy ngày bài cũ | Script v1 không đọc matrix | v2: đếm trạng thái thật từ matrix, preserve chunk/last_completed/transaction/lock, updated_at tách riêng | `test_reports_resume.py` PASS; chạy thật: last_completed=BLG-00493, planned=347, published=3, không reset | N/A | VERIFIED |
| F4 | UI trang chủ đề: chữ sát mép, danh sách link dài, không H1 phân cấp | `chu-de.md` xuất markdown thô không có container; `topic-list` không có CSS | Viết lại `chu-de.md` + `_includes/topic-directory.html`: card theo nhóm cha với SVG, hàng bấm ≥44px, grid 1/2/3 cột, `details/summary` (không cần JS), số bài thật từ `factory-parents.yml`/bài đã đăng, "Chưa có bài" cho nhóm trống; CSS `components.css`/`responsive.css` đồng bộ dark/light; nút nổi: z-index chuẩn + `env(safe-area-inset-bottom)` + padding cuối trang | DOM live: `topic-card`=77, `topic-row`=204, `<details>`=14, H1 "Tất cả chủ đề cẩm nang" render, không tràn ngang theo CSS (max-width, margin 16-20px) | VERIFIED (phân tích DOM/CSS; ảnh chụp màn hình và trình duyệt thật KHÔNG làm được trong môi trường này — NOT VERIFIED) |
| F5 | Publish chỉ là hướng dẫn văn bản, không có gate cứng | Chưa có script | `scripts/factory/publish-gate.py`: kiểm matrix PASS + `data/qa/<id>.json` (quality≥75, seo≥75, business PASS, legal PASS/NOT_REQUIRED, không critical failure) + lock/transaction; tự chốt ngày thật vào URL, cập nhật checkpoint | Gate từ chối hàng PLANNED (chạy thật, exit 1); `test_publish_gate.py` PASS: từ chối thiếu bằng chứng/điểm thấp/business FAIL; dry-run không đổi gì | N/A | VERIFIED |
| F6 | Chưa chứng minh chu trình đầy đủ | Matrix trước đó BLOCKED | Chunk thật 3 bài (≤10): BLG-00484 (bảng giá theo loại xe), BLG-00485 (yếu tố ảnh hưởng giá), BLG-00493 (so sánh báo giá) — cùng C-THUE-GIA, không trùng intent, chỉ dùng số từ `_data/pricing.yml`; cọc/phí trễ/phí giao xe ghi "cần xác nhận trực tiếp" (policy BLOCKED) | 3 file `data/qa/*.json` đầy đủ; gate promote 3/3; checkpoint last_completed=BLG-00493, next_claimable=BLG-00486 | 3 URL /blog/thue-xe/2026/09/27/... trả 200; hub /blog/thue-xe/gia-thue/ hiển thị 3 bài; sitemap 547 loc (+3, không có draft); canonical đúng | VERIFIED |
| F7 | `_posts` factory làm lệch inventory/legacy check | Bài mới mang `article_id` không nằm trong existing-map | `restore-foundation.py` + `validate.py` tách legacy/factory; validate kiểm chứng bài factory = hàng matrix PUBLISHED (tệp, output_path, không còn `{date}`) | Validate exit 0; kiểm chứng âm: thêm `_posts` giả với `article_id` không hợp lệ → validate FAIL đúng, xóa đi → PASS | N/A | VERIFIED |
| F8 | CI đỏ ở bước Generate matrix sau promote | `generate-matrix.py` v1 đếm cả bài factory + reset trạng thái PUBLISHED | v2: bỏ bài factory khỏi đếm legacy; tái sinh giữ nguyên trạng thái runtime (PUBLISHED/ngày thật) | Matrix CSV tái sinh giống hệt tệp đã commit (byte-identical); CI run 36301726800 toàn bộ bước SUCCESS, validate exit 0 — XANH lần đầu | N/A | VERIFIED |

### Kiểm tra live tại HEAD 1849593f17 (đợt này)

- Factory validate run 36301726800: SUCCESS toàn bộ (validate exit 0). Pages build run 36301726576: success.
- 3 URL bài mới trả 200; sitemap 547 loc, +3 URL mới, không draft; hub C-THUE-GIA render 3 bài; chu-de render 77 topic-card / 204 topic-row / 14 details.
- KHÔNG kiểm được: Safari/iPhone thật, Lighthouse/CWV đo thật, ảnh chụp màn hình trước/sau — NOT VERIFIED (môi trường không có trình duyệt).

## Mục tiêu tiếp theo (không tự thực hiện khi chưa được giao)

1. Chủ xe quyết định 3 mục chính sách BLOCKED trong `reports/factory/policy-conflicts.md` (cọc/phí trễ/bảo hiểm).
2. Đọc nội dung 10 bài REVIEW theo cặp để xử lý cannibalization.
3. Mở rộng `matrix-seed.json` thêm chủ đề thật cho 6.220 hàng còn thiếu khi có yêu cầu.
4. GSC/post-publish tracking: TODO/NOT IMPLEMENTED (chưa có quyền truy cập).
5. Lighthouse/CWV, Safari/iPhone: chưa có môi trường đo.

## G. Đợt hardening cuối 2026-09-27 (BODY UI + capacity semantics + factory safety)

| ID | Lỗi | Sửa | Kiểm thử | Trạng thái |
|---|---|---|---|---|
| G1 | Matrix "10.000 hàng" nhưng taxonomy chỉ có planned_target 6.570 (483 legacy + 6.570 = 7.053 < 10.000) — ngữ nghĩa sai | Định nghĩa 6 khái niệm riêng trong `reports/factory/matrix-report.md`: HARD_CAPACITY 10.000, EDITORIAL_TARGET 6.570, CURRENT_VALID_ROWS 833, CURRENT_SEEDED_ROWS 350, RESERVED_CAPACITY 9.167, MISSING_VALID_TOPIC_SPACE 6.223. KHÔNG đệm; ghi rõ taxonomy hiện tại không thể đạt 10.000, muốn tăng phải chủ đề thật | generate-matrix idempotent, CI no-drift | VERIFIED |
| G2 | progress.json dùng ngày bài cũ làm generated_at; CI ép report byte-identical | Ba mốc tách bạch: generated_at = giờ chạy thật, data_through = mốc dữ liệu, checkpoint.updated_at = mốc state (report không nâng). Bằng chứng deterministic: data_fingerprint/matrix_sha256/taxonomy_sha256/inventory_sha256; CI so vân tay thay vì byte | test_reports_resume.py: generated_at đổi giữa 2 lần chạy, data_through + vân tay ổn định, checkpoint/lock/transaction không bị đụng | VERIFIED |
| G3 | Bằng chứng QA không gắn nội dung — QA cũ có thể duyệt bài đã sửa | data/qa/*.json thêm source_path, content_sha256 (SHA-256 nội dung sau sửa cuối), matrix_row_sha256 (vân tay hàng). validate.py kiểm lại hash của mọi bài PUBLISHED | validate PASS; kiểm chứng âm: sửa tệp/nội dung → validate FAIL | VERIFIED |
| G4 | Publish gate không giữ lock (chỉ đọc check — race 2 writer) | Gate v3: acquire O_EXCL sentinel `writer-lock.active` TRƯỚC mọi kiểm tra; từ chối STALE_QA_EVIDENCE (đổi nội dung sau QA) và MATRIX_ROW_MISMATCH (đổi hàng sau QA); APPEND transaction history (giới hạn 50, có commit_sha/rollback) thay vì reset | test_publish_gate.py: thêm 4 kịch bản âm — thiếu hash, stale content, row mismatch, lock bị giữ | VERIFIED |
| G5 | BODY bài viết chưa có hệ thống (483 bài legacy + factory chung một layout mộc) | `_layouts/post.html` mới: breadcrumb taxonomy (JSON-LD khớp hiển thị, legacy giải qua factory-map), H1/dek/meta, thời gian đọc TÍNH THẬT, TOC build-time (details/summary, chỉ hiện >=4 H2, không JS), prose max-width 760px, bảng cuộn trong khung, bài liên quan theo child→parent→category, CTA tiết chế không bịa | CI render checks + live HTML | VERIFIED (kiểm tra cấu trúc/DOM/CSS; trình duyệt thật xem mục dưới) |
| G6 | Kinh nghiệm (335 bài), Chia sẻ (112), Du lịch (39), topic tới 97 bài render hết trong MỘT trang | `scripts/factory/generate-listing-pages.py`: trang tĩnh 12 bài/trang (danh mục) + 24 bài/trang (chủ đề), `_listing/` + `_data/listing-index.yml`, link đánh số crawlable, không JS load-more. Trang gốc hiển thị trang 1 + nav | CI no-drift + build check + live 200 | VERIFIED |
| G7 | 10 hàng REVIEW legacy chưa có bằng chứng phân loại | `reports/factory/review-pairs.md`: 4 cặp SAFE_DISTINCT (8 bài), 1 cặp MERGE_CANDIDATE thật (đổi xe giữa kỳ) — chờ chủ xe chọn canonical + redirect. KHÔNG tự PASS, matrix giữ nguyên 10 REVIEW | Đọc nội dung từng cặp, đối chiếu heading/keyword | VERIFIED (phân tích xong; quyết định merge là của chủ xe) |
| G8 | Writer chưa có hợp đồng UI | docs/CONTENT-FACTORY.md mục "Hợp đồng writer": chỉ nội dung ngữ nghĩa, không CSS riêng, không markup thiết kế, layout sở hữu UI | Đọc docs | VERIFIED |

### Kiểm kê migration bài cũ (phần 17)

486 tệp _posts (483 legacy + 3 factory): quét inline `<style>`/`style=` = 0 tệp.
Phân loại: 486/486 INHERITS_CANONICAL_LAYOUT, 0 INLINE_STYLE_CONFLICT,
0 SPECIAL_LAYOUT, 0 MANUAL_REVIEW. Không bài nào bị sửa nội dung; URL legacy giữ nguyên (0 đổi).

### Visual QA — KHÔNG THỂ THỰC HIỆN TRONG MÔI TRƯỜNG NÀY

Môi trường sandbox không có trình duyệt thật (không cài được Chromium/Playwright —
package install bị chặn). Tất cả kiểm tra là DOM/HTML/CSS tĩnh + CI build engine
Jekyll (đúng họ engine với Pages). ẢNH CHỤP MÀN HÌNH trước/sau: KHÔNG CÓ.
Safari/iPhone: NOT VERIFIED. Lighthouse/CWV: NOT MEASURED. Mọi kết luận responsive
(375/390/430/768/1024/1440) là phân tích breakpoint CSS, không phải kiểm tra thị giác.

## H. Đợt mở rộng vũ trụ chủ đề 10K (2026-09-27, lượt 2)

- H1. Taxonomy 7 parent / 51 → 56 child (5 child mới, không đổi child gốc).
- H2. 110 ứng viên chủ đề thật qua cổng scoring; 11 bị từ chối (trùng
  intent/keyword/slug); 2 gỡ bỏ vì trùng bài legacy (cannibalization);
  các nhóm bị cấm vĩnh viễn (doorway quận, biến thể model, synonym spin,
  best-X-in-Y, 24/7, mức cọc bịa, FAQ hàng loạt) liệt kê trong
  `reports/factory/topic-universe.md`.
- H3. Matrix 833 → 942 hàng: 473 EXISTING + 10 REVIEW + 455 PLANNED +
  3 PUBLISHED + 1 BLOCKED (BLG-00507, lỗi slug trùng legacy đã chứng minh).
- H4. Schema v2: 16 cột kế hoạch/điều hành mới; batch_id 50 hàng/lô.
- H5. CI mới: bước expand idempotency + test_topic_universe.py.
- H6. Hợp đồng scheduler chốt tại `docs/factory-workflow-contract.md`;
  KHÔNG lập lịch trong lượt này; KHÔNG sản xuất hàng loạt.
- H7. Đánh giá trung thực: legacy 483 + EDITORIAL_TARGET 6.980 = 7.463 <
  10.000. Taxonomy vẫn không thể đạt 10.000 hợp lệ. RESERVED_CAPACITY
  9.057 chỉ dành cho chủ đề thật sau này — KHÔNG ĐỆM.
