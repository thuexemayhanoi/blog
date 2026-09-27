# AGENTS.md — hợp đồng bắt buộc cho agent tự trị trong thuexemayhanoi/blog

Kho: `thuexemayhanoi/blog` · Nhánh: `main` · Site: https://thuexemayhanoi.github.io/blog/ · Base URL: `/blog` · Ngôn ngữ công khai: chỉ tiếng Việt.

Mọi agent tự trị (AI, scheduler tương lai, operator) PHẢI đọc file này trước. Vi phạm hợp đồng này là lỗi vận hành, không phải tối ưu.

## 1. Thứ bậc nguồn chân lý (authority hierarchy)

Khi các nguồn mâu thuẫn, tin theo thứ tự ưu tiên giảm dần:

1. Repository/runtime truth (git HEAD, dữ liệu thật tại thời điểm chạy).
2. `data/state/*` (checkpoint, transaction, writer-lock) — trạng thái factory duy nhất.
3. Report sinh bằng máy: `reports/factory/progress.json`, `matrix-report.md`, `latest.md`.
4. Hợp đồng/tài liệu chuẩn: `AGENTS.md`, `docs/*` (mỗi mối quan tâm một chủ sở hữu — bảng trong README.md).
5. Report lịch sử (báo cáo chạy cũ).
6. Trí nhớ hội thoại (conversation memory) — KHÔNG BAO GIỜ là nguồn chân lý.

Tuyến chiến:
- Dữ liệu kinh doanh: `_data/business.yml`, `_data/pricing.yml` → kết xuất `data/business-facts.json`. Chỉ những file này là chuẩn giá/giờ/địa chỉ/chính sách.
- Trạng thái factory: checkpoint + transaction + ownership-safe writer lock là chuẩn. Số liệu runtime (hàng matrix, PLANNED, PUBLISHED...) KHÔNG tin từ prose docs — đọc `data/state/checkpoint.json`, `reports/factory/matrix-report.md`, `reports/factory/progress.json`.

## 2. Vòng đời bắt buộc mỗi lần chạy

```
RECOVER (hòa giải transaction/lock treo nếu có)
→ READ CURRENT STATE (checkpoint, matrix, queue)
→ RESEARCH WHEN REQUIRED (theo docs/SOURCE-RESEARCH.md: lớp B/C bắt buộc tra cứu)
→ RESUME EXISTING WORK (chunk dở trước khi nhận việc mới)
→ CLAIM SAFE CHUNK (3–5, tối đa 10; theo next_claimable_id)
→ PLAN INTERNAL LINKS (theo docs/INTERNAL-LINKING.md, TRƯỚC KHI viết)
→ WRITE (trong _drafts/, KHÔNG đụng _posts/)
→ FACT CHECK (business facts → data/business-facts.json)
→ SOURCE VERIFY (legal/hiện hành → nguồn chính thức, docs/SOURCE-RESEARCH.md)
→ QA (rubric docs/QUALITY-RUBRIC.md, bằng chứng hash)
→ REPAIR (nếu < 90: sửa rồi chấm lại, không cộng bù)
→ PUBLISH GATE (scripts/factory/publish-gate.py — cổng duy nhất vào _posts/)
→ CHECKPOINT (cập nhật checkpoint/report)
→ COMMIT → CI/PAGES VERIFY (Factory validate + Factory capacity validate + Pages đều SUCCESS + kiểm tra live)
```

Mỗi lần scheduler tương lai được gọi chỉ là MỘT sự tiếp diễn của MỘT factory duy nhất — không phải lần chạy mới. Lỗi ở bài 2.437 không quay lại bài 1: RECOVER → RESUME → REPAIR → VERIFY → NEW WORK (`docs/RECOVERY.md`).

## 3. Quy tắc cứng (vi phạm = dừng)

- KHÔNG restart factory từ đầu; KHÔNG dựng lại matrix từ đầu.
- KHÔNG tin số đếm stale trong prose docs — luôn đọc data/state + report sinh máy.
- KHÔNG claim quá giới hạn chunk chuẩn (3–5, tối đa 10 bài/chunk).
- KHÔNG chạy hai writer song song: lock sentinel `data/state/writer-lock.active` tạo bằng O_CREAT|O_EXCL, mỗi lần acquire sinh ownership token UUID (sentinel chứa token, `writer-lock.json` lưu cùng token); release chỉ thao khi token khớp — KHÔNG force-unlock lock của chủ khác/không rõ ownership (mức override duy nhất: `docs/RECOVERY.md` mục lock treo có bằng chứng quá hạn).
- KHÔNG hạ ngưỡng QA (quality ≥ 90, seo ≥ 90, business_fact/legal PASS-FAIL).
- KHÔNG bịa dữ liệu kinh doanh/pháp lý/địa phương — nguồn chuẩn: `data/business-facts.json`; pháp lý: nguồn chính thức theo `docs/SOURCE-RESEARCH.md`.
- KHÔNG tự đổi trạng thái REVIEW/BLOCKED.
- KHÔNG publish thẳng vào `_posts/` ngoài publish gate.
- Vận hành qua factory operator (docs/PROC-PUBLISH.md): writer ngoài chỉ đẩy lệnh whitelist vào `data/factory/operator-command.json`; GitHub Actions `factory-operator.yml` là deterministic hands — KHÔNG AI trong Actions, KHÔNG gọi API AI, KHÔNG secret AI, KHÔNG viết prose. External AI vẫn là writer duy nhất; engine chuẩn là nguồn sự thật duy nhất.
- KHÔNG sinh bài đệm để tiến gần 10.000. QUYẾT ĐỊNH CHỦ XE 2026-09-27: 10.000 bài HỢP LỆ PUBLISHED là CHỈ TIÊU sản xuất của một chiến dịch liên tục duy nhất (không chỉ là trần kỹ thuật). Chỉ bài đạt đủ gate mới tính vào chỉ tiêu; KHÔNG hạ gate, KHÔNG sinh bài đệm để chạy theo chỉ tiêu. Khi hàng PLANNED cạn, mở rộng vũ trụ chủ đề qua gate chuẩn.
- KHÔNG tuyên bố có scheduler khi chưa có — hiện CHƯA có scheduler factory (không cron, không hourly); vận hành theo LỆNH operator (docs/PROC-PUBLISH.md); `publish-queue.yml` là campaign LEGACY đã tắt, không phải scheduler.
- Không push file truncate; kiểm tra tính toàn vẹn trước push.
- Không ghi PASS/VERIFIED khi chưa chạy thật; mục chưa kiểm tra ghi NOT VERIFIED.

## 4. Phạm vi: CHỈ repo blog này

- Blog và `/shop` là hai bên kinh doanh khác nhau. KHÔNG đồng bộ dữ liệu từ `thuexemayhanoi/shop`; khác biệt dữ liệu giữa hai site KHÔNG phải lỗi.
- Xung đột dữ liệu bên trong chính /blog: ghi từng nguồn vào `reports/factory/policy-conflicts.md`, đánh dấu BLOCKED, KHÔNG tự chọn nguồn, KHÔNG bịa chính sách. Chỉ chủ xe quyết định.

## 5. Trạng thái, lock, transaction, checkpoint

Đọc theo thứ tự: `data/state/transaction.json` → `data/state/checkpoint.json` → `data/state/writer-lock.json` → `reports/factory/progress.json`.

- Transaction `active: true` → recover/hoàn tất GIAO DỊCH ĐÓ trước (`docs/RECOVERY.md`).
- Writer-lock `locked: true` hoặc sentinel tồn tại → KHÔNG chạy writer thứ hai. Lấy lock trước khi mutate, nhả lock trong finally có kiểm ownership token.
- Checkpoint là điểm resume duy nhất (`next_claimable_id`, `last_completed_article_id`).

## 6. Lệnh kiểm tra bắt buộc (chạy thật, không khai báo — danh mục đầy đủ: docs/ENGINE-RUNBOOK.md)

- `python3 scripts/factory/validate.py` — 0 PASS / 1 FAIL / 2 BLOCKED.
- `python3 scripts/factory/capacity-audit.py`, `queue.py --stats`, `refill-queue.py --verify` — audit read-only.
- `python3 scripts/factory/generate-matrix.py` — tái sinh matrix idempotent, bảo toàn trạng thái runtime.
- `python3 scripts/factory/publish-gate.py --draft _drafts/<file>.md --id BLG-XXXXX` — cổng promote v3: hàng PASS + bằng chứng `data/qa/<id>.json` (quality ≥ 90, seo ≥ 90, business_fact PASS, legal PASS|NOT_REQUIRED, không critical failure, `content_sha256` khớp draft, `matrix_row_sha256` khớp vân tay hàng). Gate tự giữ ownership-safe writer lock, mở transaction, promote, APPEND history, nhả lock.
- CI: `factory-validate.yml` + `factory-capacity-validate.yml` (read-only, không bao giờ commit về main) + Pages. CI XANH + Pages deploy là điều kiện cần; kiểm tra runtime live là điều kiện đủ trước khi tuyên bố hoàn thành.

## 7. Điều kiện xuất bản (gate)

Xuất bản một bài yêu cầu TẤT CẢ: QUALITY ≥ 90/100 VÀ SEO ≥ 90/100 (rubric `docs/QUALITY-RUBRIC.md` — điểm nội bộ, không phải điểm Google); BUSINESS FACT PASS (truy về `data/business-facts.json`); LEGAL PASS hoặc NOT_REQUIRED (theo `source_required`/`legal_risk`); KHÔNG critical failure. Kiểm tra tự động KHÔNG thay thế đánh giá nội dung bởi AI/người đọc có bằng chứng. Nội dung chạm khoảng đặt cọc/phí trễ/bảo hiểm đang BLOCKED: xem `reports/factory/policy-conflicts.md` — không nêu con số cho tới khi chủ xe quyết định.

## 8. Nội dung hiện có

- KHÔNG viết lại bài EXISTING/PUBLISHED trừ khi có yêu cầu audit mới; KHÔNG đổi URL legacy, KHÔNG xóa/đổi tên `_posts/`, KHÔNG noindex hàng loạt; legacy phải còn nguyên sau mỗi lần chạy (validator kiểm).
- Bài mới: `_posts/` phẳng, `YYYY-MM-DD-slug.md`, permalink theo taxonomy, frontmatter đủ (`docs/ARTICLE-RULES.md`).
- Mở rộng chủ đề CHỈ qua `scripts/factory/expand-topic-universe.py` hoặc refill qua gate G1–G8 (`docs/ENGINE-RUNBOOK.md`). KHÔNG thêm tay vào matrix-seed/taxonomy-config.
- BLG-00507 BLOCKED (trùng slug legacy) — KHÔNG claim.
- 10 hàng legacy REVIEW: cần đọc từng cặp, không tự động hóa (`docs/SEO-OWNERSHIP.md`, `reports/factory/review-pairs.md`).

## 9. Bàn giao mỗi lần chạy

Bắt buộc trong báo cáo cuối: MAIN HEAD (SHA), GitHub Pages run ID, BUILD/DEPLOY status, tệp thực sự thay đổi, các kiểm tra runtime đã làm (URL công khai, mobile ~390px: menu/footer/breadcrumb/calculator/chatbot), trạng thái các mục BLOCKED. Không ghi Safari/iPhone khi chưa thật sự test trên đó.

## 10. Ngữ nghĩa thời gian & năng lực

Ba mốc KHÔNG dùng lẫn: `generated_at` (giờ chạy report — đổi mỗi lần chạy); `data_through` (ngày bài mới nhất — chỉ đổi khi nội dung đổi); `checkpoint.updated_at` (giờ state factory đổi vật lý — report KHÔNG nâng). Bằng chứng deterministic: `data_fingerprint`, `matrix_sha256`, `taxonomy_sha256`, `inventory_sha256` trong progress.json.

Năng lực (báo đúng, không đệm — số hiện hành LUÔN đọc `reports/factory/matrix-report.md`): HARD_CAPACITY 10.000 là TRẦN kỹ thuật VÀ, theo quyết định chủ xe 2026-09-27, là CHỈ TIÊU sản xuất: chiến dịch hoàn thành khi đạt 10.000 bài hợp lệ PUBLISHED (không phải khi matrix đầy). EDITORIAL_TARGET (tổng planned_target taxonomy) luôn nhỏ hơn trần; phần chênh chỉ dành cho chủ đề MỚI thật qua gate. KHÔNG hạ gate để đạt chỉ tiêu; không đạt do hết chủ đề hợp lệ → mở rộng vũ trụ chủ đề qua gate chuẩn rồi tiếp tục.
