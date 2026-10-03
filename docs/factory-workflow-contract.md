# Hợp đồng 6 workflow — thuexemayhanoi/blog

Ngày chốt: 2026-10-02 (port kiến trúc /vanchinh hoàn chỉnh). Lịch sử:
bản 4-workflow (quality-gate + factory-production + factory-liveness +
factory-publish-verify) và bản 5-workflow (tách factory-refill) đã
RETIRED — `factory-production.yml` và `factory-refill.yml` KHÔNG còn
tồn tại; publisher duy nhất hiện nay là `factory-publish.yml`
(push-driven, turbo queue ported từ /vanchinh), refill là op bảo trì
chạy LOCAL, KHÔNG còn workflow riêng. Nguyên tắc giữ nguyên: ít code,
ít luật hơn khi cả hai đều an toàn; sản xuất push draft `_drafts/` →
queue → pair claim/QA/publish → audit sâu on-demand. Kỹ thuật sâu:
docs/ADVANCED-FACTORY-RECOVERY.md.

## 1. Danh sách workflow (CHÍNH XÁC 6)

| Workflow | Trigger | Quyền | Phạm vi |
|---|---|---|---|
| `quality-gate.yml` | push main theo paths (matrix, `_drafts/**`, `_posts/**`, `scripts/**`, layouts/includes/data/config), pull_request cùng paths, workflow_dispatch | `contents: read` | Dual-mode READ-ONLY (port pattern /shop article-quality + `scripts/factory/gate-scope.py`, fail-closed). Content push (drafts/posts/matrix/QA evidence/state/reports): CHỈ `validate.py --scope chunk` — KHÔNG build + KHÔNG quét link toàn site mỗi cycle. Engine push (scripts/layouts/includes/data/config/workflow/docs/matrix-seed/production-control) hoặc dispatch: + Jekyll build (`actions/jekyll-build-pages@v1`) + built-link integrity + draft-leak + sitemap/schema/hub sanity. Luôn working-tree clean. KHÔNG commit, KHÔNG claim, KHÔNG publish. |
| `factory-publish.yml` | push main theo paths `_drafts/**` (và chính workflow file) | `contents: write` | Production publisher DUY NHẤT (mô hình /vanchinh): push writer chứa 2..10 draft (write-ahead queue) → selection EXACT ID qua canonical `scripts/factory/push-selection.py` (từ chối ID trùng, ID lạ, hàng PUBLISHED/EXISTING/BLOCKED, > 10 draft/push) → chia pair 2 deterministic theo thứ tự matrix → consume tuần tự: claim chỉ hàng PLANNED (`prepare-next --ids`), `qa --ids --scope fast`, `publish --ids` (hàng PASS) → checkpoint. Pair FAIL content = recoverable (REPAIR), KHÔNG rollback pair đã publish; engine resume-first — còn repair/unresolved thì KHÔNG claim pair mới (pair còn lại DEFERRED, lần kế). FATAL (claim/QA hạ tầng, non-FF sau 3 lần rebase retry) → fail run, KHÔNG commit, KHÔNG force push. Concurrency group `factory-publish`, `cancel-in-progress: false`. |
| `factory-liveness.yml` | cron `0 */6 * * *` (mỗi 6 giờ) + workflow_dispatch | `contents: read` | Liveness READ-ONLY: `watchdog.py` (unhealthy = run FAIL, KHÔNG chỉ warning) + `factory-operator.py status` + purity check working-tree sạch. KHÔNG recover, KHÔNG claim, KHÔNG publish, KHÔNG commit. |
| `factory-publish-verify.yml` | CHỈ workflow_dispatch (không cron) | `contents: read` | FULL audit READ-ONLY: watchdog + `factory-operator.py verify --scope full` + refill gate G1-G8 (pure selftest) + `sitemap-plan.py` + generator drift/idempotency + Jekyll build + built-link deep check + draft-leak + hub/pagination render + working-tree clean. KHÔNG commit, KHÔNG push. |
| `factory-soak.yml` | CHỈ workflow_dispatch | `contents: read` | Reliability/soak on-demand, HERMETIC đối với production: chạy `scripts/factory/tests/test_soak_recovery.py` trên fixture cô lập (multi-chunk + failure recovery) + purity check. KHÔNG mutation production state, KHÔNG commit. |
| `article-batch.yml` | CHỈ workflow_dispatch | `contents: read` | Batch planning/status DRY-RUN READ-ONLY: validate full scope (nền + inventory + taxonomy) + progress snapshot + queue stats (nhìn matrix) + assert không pending transaction/lock + purity check. KHÔNG claim, KHÔNG QA mutate, KHÔNG publish, KHÔNG commit/push. |

Pages deploy bằng cơ chế built-in của GitHub (branch main), không cần
workflow riêng.

## 2. Đã retire (KHÔNG quay lại)

- `.github/workflows/publish-drafts.yml` (publisher đơn giản bản
  4-workflow — thay bằng `factory-publish.yml` turbo queue ported từ
  /vanchinh)
- `.github/workflows/factory-production.yml` (đường nóng bản 4/5-workflow
  — thay bằng `factory-publish.yml` push-driven)
- `.github/workflows/factory-refill.yml` (refill tách riêng bản
  5-workflow — refill quay về là op bảo trì local
  `factory-operator.py refill`, KHÔNG còn cron/trigger sản xuất)
- `.github/workflows/factory-operator.yml` (mô hình file lệnh — thay
  bằng workflow_dispatch inputs)
- `.github/workflows/factory-validate.yml` (gộp vào quality-gate FAST)
- `.github/workflows/factory-capacity-validate.yml` (gộp vào verify full)
- `.github/workflows/factory-watchdog.yml` (watchdog chạy trong
  factory-liveness)
- `.github/workflows/publish-queue.yml` (campaign legacy đã tắt từ lâu;
  `_data/publishing.yml` giữ `enabled: false` vĩnh viễn)
- `.github/workflows/weekly-maintenance.yml` (bản 3-workflow; FULL audit
  dời thành `factory-publish-verify.yml`, liveness thành
  `factory-liveness.yml`)
- `.github/workflows/diag-factory-tests.yml` (diagnostic on-demand không
  còn cần thiết)
- `scripts/factory/tests/test_push_rebase_overlap.py` (đối tượng — file
  lệnh operator — không còn tồn tại)

`test_hardening.py` (S7 StaticContract) chặn việc các file trên quay lại
và chặn thêm workflow mới ngoài danh sách 6.

## 3. Bất biến giữ nguyên (KHÔNG giảm khi thay đổi workflow)

- `publish-gate.py` là cơ chế promote DUY NHẤT vào `_posts/`; publish
  đòi: hàng PASS, `quality >= 75`, `seo >= 70`, `business_fact = PASS`,
  `legal = PASS | NOT_REQUIRED`, không critical failure,
  `content_sha256` khớp draft, `matrix_row_sha256` khớp hàng matrix.
- Publisher concurrency = 1: CHỈ `factory-publish.yml` được
  `contents: write` và là đường nóng sản xuất duy nhất; mọi workflow
  khác READ-ONLY. External writer CHỈ push draft `_drafts/`, KHÔNG BAO
  GIỜ tự promote vào `_posts/`.
- KHÔNG force push ở mọi workflow (bounded rebase retry tối đa 3 lần;
  conflict → abort); transaction/writer-lock còn tồn tại → publisher
  guard FAIL-CLOSED trước khi mutate; stale lock KHÔNG bị force-delete
  bừa — recover là op local theo docs/RECOVERY.md.
- KHÔNG AI, không API key AI, không secret, không cron sản xuất ngoài
  factory-liveness (chỉ đọc).
- Refill KHÔNG chạy trong đường nóng publish: khi pool claimable cạn,
  writer/coordinator chạy op bảo trì local `factory-operator.py refill`
  (hoặc bảo trì qua môi trường có quyền), FETCH MAIN, rồi mới push cặp
  bài kế tiếp. Refill FAIL (hết pool STAGED → NEEDS_TOPIC_EXPANSION) chỉ
  dừng refill; writer chịu trách nhiệm mở rộng topic theo gate.
- Engine resume-first: còn hàng REPAIR/unresolved thì KHÔNG claim bài
  mới; repair push xử lý các ID đó trước (repair rows KHÔNG claim lại
  từ đầu), PLANNED còn lại DEFERRED lần kế.
- Bài nháp KHÔNG được deploy (draft-leak check ở cả quality-gate và
  factory-publish-verify).
