# Hợp đồng 5 workflow — thuexemayhanoi/blog

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

## 1. Danh sách workflow (CHÍNH XÁC 5)

| Workflow | Trigger | Quyền | Phạm vi |
|---|---|---|---|
| `quality-gate.yml` | push main theo paths (matrix, `_drafts/**`, `_posts/**`, `scripts/**`, layouts/includes/data/config), pull_request cùng paths, workflow_dispatch | `contents: read` | Dual-mode READ-ONLY (port pattern /shop article-quality + `scripts/factory/gate-scope.py`, fail-closed). Content push (drafts/posts/matrix/QA evidence/state/reports): CHỈ `validate.py --scope chunk` — KHÔNG build + KHÔNG quét link toàn site mỗi cycle. Engine push (scripts/layouts/includes/data/config/workflow/docs/matrix-seed/production-control) hoặc dispatch: + Jekyll build (`actions/jekyll-build-pages@v1`) + built-link integrity + draft-leak + sitemap/schema/hub sanity. Luôn working-tree clean. KHÔNG commit, KHÔNG claim, KHÔNG publish. |
| `factory-publish.yml` | push main theo paths `_drafts/**` (và chính workflow file) | `contents: write` | Production publisher DUY NHẤT (mô hình /vanchinh): push writer chứa 2..10 draft (write-ahead queue) → selection EXACT ID qua canonical `scripts/factory/push-selection.py` (từ chối ID trùng, ID lạ, hàng PUBLISHED/EXISTING/BLOCKED, > 10 draft/push) → chia pair 2 deterministic theo thứ tự matrix → consume tuần tự: claim chỉ hàng PLANNED (`prepare-next --ids`), `qa --ids --scope fast`, `publish --ids` (hàng PASS) → checkpoint. Pair FAIL content = recoverable (REPAIR), KHÔNG rollback pair đã publish; engine resume-first — còn repair/unresolved thì KHÔNG claim pair mới (pair còn lại DEFERRED, lần kế). FATAL (claim/QA hạ tầng, non-FF sau 3 lần rebase retry) → fail run, KHÔNG commit, KHÔNG force push. Concurrency group `factory-publish`, `cancel-in-progress: false`. |
| `factory-liveness.yml` | CHỈ workflow_dispatch (không cron) | `contents: read` | Liveness READ-ONLY: `watchdog.py` (unhealthy = run FAIL, KHÔNG chỉ warning) + `factory-operator.py status` + purity check working-tree sạch. KHÔNG recover, KHÔNG claim, KHÔNG publish, KHÔNG commit. |
| `factory-publish-verify.yml` | CHỈ workflow_dispatch (không cron) | `contents: read` | FULL audit READ-ONLY: watchdog + `factory-operator.py verify --scope full` + refill gate G1-G8 (pure selftest) + `sitemap-plan.py` + generator drift/idempotency + Jekyll build + built-link deep check + draft-leak + hub/pagination render + working-tree clean. KHÔNG commit, KHÔNG push. |
| `factory-soak.yml` | CHỈ workflow_dispatch | `contents: read` | Reliability/soak on-demand, HERMETIC đối với production: chạy `scripts/factory/tests/test_soak_recovery.py` trên fixture cô lập (multi-chunk + failure recovery) + purity check. KHÔNG mutation production state, KHÔNG commit. |

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
- `.github/workflows/article-batch.yml` (batch planning/status dry-run
  dư thừa: kế hoạch nằm ở factory-publish-verify.yml, trạng thái nhìn
  bằng factory-operator.py status — theo port no-scheduled-runs của /shop)
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

## 4. Agent vận hành: #4 repair, #5 supervisor, #6 watchdog

Ba agent vận hành (operator-run, KHÔNG phải AI viết bài) chia sẻ một
hợp đồng hạ tầng duy nhất — `scripts/factory/maintenance.py`:

- maintenance_lock toàn cục `data/state/maintenance-lock.json`
  (holder `agent-4` hoặc `agent-5`, TTL 6h). Khi lock active, MỌI op
  mutating của `factory-operator.py` (prepare-next/qa/publish/
  release-chunk/recover/requeue/refill) từ chối chạy — production
  pause thật, không tự khai. #4 và #5 KHÔNG BAO GIỜ giữ lock (mutate)
  đồng thời; stale takeover phải `--force-stale` rõ ràng và được ghi
  dấu vào lock (không âm thầm bypass).
- Incident registry `data/state/incidents/<INC-YYYYMMDD-slug>.json`:
  cùng một incident_id giữ nguyên xuyên suốt #4 -> #5; mỗi incident
  được tối đa 1 attempt #4 + 1 attempt #5 (tổng 2, cưỡng chế bằng
  counter trong record). KHÔNG có escalation tự trị nào khác.
- Vùng ghi của agent bị chặn cứng bởi `maintenance.assert_writable_rel`:
  CHỈ `data/state/**` và `reports/factory/incidents/**`. TUYỆT ĐỐI
  không `_posts/`, `_drafts/`, `_queue/`, `data/content-matrix.csv`,
  `_data/`, `_layouts/`, `_includes/`, `assets/` — agent vận hành
  KHÔNG BAO GIỜ viết/sửa bài viết, taxonomy, pricing, business facts.

### Agent #4 — first-line infrastructure repair (`repair-agent.py`)

- Trigger từ sự cố hạ tầng thật (watchdog STALE_*, incident của
  operator); bắt buộc `--trigger` — không tự bịa sự cố.
- `start` giành maintenance_lock + tạo/reuse incident (incident đã hết
  lượt #4 -> REFUSED). `repair --action` chỉ nhận whitelist action
  deterministic, tối thiểu, an toàn:
  `release-stale-writer-lock` (chỉ nhả lock hết hạn/thiếu metadata,
  lock tươi -> ESCALATE), `clear-inactive-transaction` (active=true +
  pending=null -> inactive; active + pending hợp lệ -> ESCALATE),
  `recompute-checkpoint-counts`, `prune-writer-claims`
  (qua `writer-claim.py prune`).
- Sau repair chạy regression focused (`validate.py --scope chunk`) và
  ghi vào record: incident_id, timestamps, trigger, diagnosis,
  files/actions, tests, result.
- Kết quả đúng MỘT trong hai: `SUCCESS` (chờ #5 verify) hoặc
  `ESCALATE` (bàn giao #5). Lock KHÔNG tự nhả — chỉ #5 sau verify
  mới nhả. One-shot: không loop, không polling, không retry tự trị.
- Test hợp đồng: `scripts/factory/tests/test_repair_agent.py`
  (hermetic fixture, KHÔNG đụng production state).

### Agent #5 — supervisor / second-line recovery (`supervisor-agent.py`)

- Tái dùng CÙNG incident_id + CÙNG maintenance_lock. Handoff qua
  `take`: chỉ chấp nhận khi #4 đã trả SUCCESS/ESCALATE cho đúng
  incident VÀ lock còn active, holder `agent-4` → ownership CHUYỂN
  sang `agent-5` (không nhả giữa chừng — không có khoảng trống cho
  mutation song song). #4 và #5 KHÔNG BAO GIỜ mutate đồng thời
  (cưỡng chế bởi holder).
- Khi #4 = SUCCESS: `verify` kiểm định ĐỘC LẬP (repo state, đủ 5
  workflow hợp đồng, writer-lock/txn không treo, lease trỏ đúng
  PLANNED, checkpoint counts khớp matrix, production-control nguyên
  vẹn, regression chunk). HEALTHY → nhả maintenance_lock, incident
  `recovered` — production resume qua entrypoint SINH THƯỜNG hiện có
  (agent không spawn cycle). UNHEALTHY → KHÔNG sửa thêm: giữ pause,
  giữ lock, incident `attention`, viết report
  `reports/factory/incidents/<id>.md`, STOP.
- Khi #4 = ESCALATE: `repair` được ĐÚNG MỘT attempt (cùng whitelist
  action của #4) → verify lại: HEALTHY → nhả lock, incident
  `resumable`. Vẫn hỏng → giữ pause, GIỮ NGUYÊN checkpoint + kết quả
  recoverable của writer, incident `stopped`, viết report, STOP.
  KHÔNG escalation lên Agent #6 (watchdog chỉ wake, không repair).
- Test hợp đồng: `scripts/factory/tests/test_supervisor_agent.py`
  (hermetic, KHÔNG đụng production state).
