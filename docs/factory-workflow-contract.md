# Hợp đồng 5 workflow — thuexemayhanoi/blog

Ngày chốt: 2026-09-30 (thay mô hình 5 workflow cũ; bản 4-workflow thay
weekly-maintenance bằng factory-liveness + factory-publish-verify). Cập
nhật Phase 1 cùng ngày: factory-production chuyển từ dispatch-only sang
PUSH-DRIVEN theo mô hình /vanchinh (writer push draft `_drafts/` →
workflow tự claim/QA/publish EXACT ID; dispatch chỉ còn op bảo trì).
Cập nhật 2026-10-01 (mô hình /vanchinh hoàn chỉnh): (i) tách refill khỏi
đường nóng publish thành workflow riêng `factory-refill.yml` (cùng
concurrency group — refill và publish KHÔNG BAO GIỜ mutate state cùng
luc); (ii) thêm BACKLOG recovery — draft hợp lệ sót trong `_drafts/`
do pipeline trước chết được nhận diện EXACT ID và hoàn tất trước khi nhận
việc mới. Nguyên tắc: ít code, ít luật hơn khi cả hai đều an toàn; sản
xuất → QA nhanh → publish → audit sâu định kỳ. Kỹ thuật sâu:
docs/ADVANCED-FACTORY-RECOVERY.md.

## 1. Danh sách workflow (CHÍNH XÁC 5)

| Workflow | Trigger | Quyền | Phạm vi |
|---|---|---|---|
| `quality-gate.yml` | push main, pull_request, workflow_dispatch | `contents: read` | FAST: `validate.py --scope chunk` + Jekyll build (`actions/jekyll-build-pages@v1`) + `check-built-links.py` + draft-leak + sitemap/schema/hub sanity. READ-ONLY, KHÔNG commit. |
| `factory-production.yml` | push main theo paths `_drafts/**` HOẶC push rỗng sau commit promote (backlog) + workflow_dispatch CHỈ op bảo trì `status\|recover\|diagnostics` (refill thuộc factory-refill.yml) | `contents: write` | Đường sản xuất DUY NHẤT (Phase 1, mô hình /vanchinh): push-selection.py chọn EXACT ID — draft vừa push, hoặc BACKLOG (draft hợp lệ sót trong `_drafts/` do pipeline trước chết; REPAIRABLE trước, engine resume-first; tối đa chunk_size; draft vừa push bị hoãn tự thành backlog lần kế tiếp) → claim `claim_ids` (`prepare-next --ids`) → `qa --ids --scope fast` → `publish --ids` (hàng PASS) → light smoke; selection báo `refill_advised` (claimable PLANNED < chunk_size) → CHỈ `::warning` nhắc writer/coordinator kích hoạt `factory-refill.yml`, KHÔNG tự refill trong hot path; production-control enabled=false → exit sạch trước claim; recover trước mọi op mutating; push fast-forward, rebase xong validate chunk lại, conflict/FAIL → STOP, KHÔNG force push, tối đa 2 lần thử lại. KHÔNG verify full/soak/hardening trong hot path (đó là của factory-publish-verify). |
| `factory-refill.yml` | push main theo paths `data/factory/refill-request.json` hoặc `data/factory/refill-batches/**` + workflow_dispatch `refill` | `contents: write` | Refill DUY NHẤT, TÁCH khỏi đường nóng publish: recover → stage batch refill đã duyệt qua gate G1-G8 (`stage-refill-batch.py --all`; gate FAIL → ROLLBACK + exit 1, KHÔNG đụng publish) → `factory-operator.py refill` (canonical) → validate chunk + queue stats → commit deterministic; CÙNG concurrency group `blog-factory-production` với factory-production nên refill và publish KHÔNG BAO GIỜ mutate state cùng lúc. Batch refill sai KHÔNG BAO GIỜ làm hỏng publish bài vừa chạy. |
| `factory-liveness.yml` | cron `0 */6 * * *` (mỗi 6 giờ) + workflow_dispatch | `contents: read` | Liveness READ-ONLY: `watchdog.py` + `factory-operator.py status` + purity check. CHỈ BÁO cáo sản xuất đâm ruồi; KHÔNG BAO GIỜ recover/delete/claim/publish. KHÔNG commit. |
| `factory-publish-verify.yml` | CHỈ workflow_dispatch | `contents: read` | FULL audit READ-ONLY (theo yêu cầu, không cron): watchdog + `factory-operator.py verify --scope full` + refill-queue `--verify/--selftest` + `sitemap-plan.py` + generator drift + build/links deep + hub/pagination render. KHÔNG commit. |

Pages deploy bằng cơ chế built-in của GitHub (branch main), không cần
workflow riêng.

## 2. Đã retire (KHÔNG quay lại)

- `.github/workflows/factory-operator.yml` (mô hình file lệnh
  `data/factory/operator-command.json` bị thay bằng workflow_dispatch
  inputs — không còn file lệnh, không còn lock lệnh chồng nhau)
- `.github/workflows/factory-validate.yml` (gộp vào quality-gate FAST)
- `.github/workflows/factory-capacity-validate.yml` (gộp vào weekly FULL)
- `.github/workflows/factory-watchdog.yml` (watchdog chạy trong weekly)
- `.github/workflows/publish-queue.yml` (campaign legacy đã tắt từ lâu;
  `_data/publishing.yml` giữ `enabled: false` vĩnh viễn)
- `scripts/factory/tests/test_push_rebase_overlap.py` (đối tượng — file
  lệnh operator — không còn tồn tại)

- `.github/workflows/weekly-maintenance.yml` (bản 3-workflow; FULL audit
  dời thành `factory-publish-verify.yml` dispatch-only, liveness tách
  thành `factory-liveness.yml` cron 6 giờ)

`test_hardening.py` (S7 StaticContract) chặn việc các file trên quay lại
và chặn thêm workflow mới ngoài danh sách 5.

## 3. Bất biến giữ nguyên (KHÔNG giảm khi thay đổi workflow)

- `publish-gate.py` là cơ chế promote DUY NHẤT vào `_posts/`; publish
  đòi: hàng PASS, `quality >= 75`, `seo >= 70`, `business_fact = PASS`,
  `legal = PASS | NOT_REQUIRED`, không critical failure,
  `content_sha256` khớp draft, `matrix_row_sha256` khớp hàng matrix.
- KHÔNG force push ở mọi workflow; transaction/writer-lock conflict vẫn
  STOP; bảo vệ ghi đè bài đã PUBLISHED giữ nguyên.
- KHÔNG AI, không secret AI, không cron sản xuất trong bất kỳ workflow.
- Chỉ `factory-production.yml` và `factory-refill.yml` được
  `contents: write`, và chỉ commit output deterministic của tooling
  chuẩn.
- Refill DUY NHẤT qua `factory-refill.yml` (từ 2026-10-01, tách khỏi
  đường nóng publish): khi push-selection báo `refill_advised` (claimable
  PLANNED < chunk_size) và production-control enabled, writer/coordinator
  KÍCH HOẠT factory-refill (workflow_dispatch `refill` hoặc push
  `data/factory/refill-request.json` / `data/factory/refill-batches/**`),
  CHỜ refill success, FETCH MAIN, rồi mới push cặp bài kế tiếp. Refill
  chạy recover trước, stage batch qua gate G1-G8 (gate FAIL → ROLLBACK
  ledger nguyên vẹn + exit 1), op `refill` chuẩn (khóa atomic O_EXCL),
  commit deterministic; một batch refill sai KHÔNG BAO GIỜ làm hỏng một
  lần publish bài vừa chạy. Refill FAIL (hết pool STAGED →
  NEEDS_TOPIC_EXPANSION) chỉ dừng refill; writer chịu trách nhiệm mở
  rộng topic theo gate.
- BACKLOG recovery (mô hình /vanchinh, từ 2026-10-01): draft HỢP LỆ sót
  trong `_drafts/` cho hàng chưa xong (PLANNED/WRITING/QA/REPAIR/PASS) —
  dấu hiệu pipeline trước chết trước claim/QA/publish — được nhận diện
  EXACT ID và CÓ ƯU TIÊN trước bài mới: claim/QA tối đa chunk_size ID có
  draft thật, hàng dở REPAIRABLE xử lý trước (engine resume-first: còn
  việc dở thì KHÔNG claim mới), draft vừa push bị hoãn KHÔNG mất và tự
  thành backlog lần kế tiếp (commit promote re-trigger, chuỗi tự lành).
  Draft sót KHÔNG hợp lệ (sai tên, thiếu article_id, ID lạ, hàng
  PUBLISHED/bảo vệ) bị BỎ QUA, KHÔNG chặn publish; KHÔNG BAO GIỜ đụng
  hàng PUBLISHED. Repair có ưu tiên trước việc mới.
- Bài nháp KHÔNG được deploy (draft-leak check ở cả quality-gate và weekly).
