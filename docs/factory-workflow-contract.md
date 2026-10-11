# Hợp đồng 7 workflow (+1 helper) — thuexemayhanoi/blog

Delta hardening 2026-10-12: ownership enforced ở lõi registry và CAS — mỗi
session một slot sống; registry ID/session mơ hồ fail-closed, recovery không
rollback lease sống để chọn chủ. Merge offline không chuyển chủ lease sống.
CI hiện có 26 suite (thêm audit QA provenance). Audit-only helper
`audit-legacy-qa.py` không thuộc đường mutate/publish hoặc workflow tự chạy.
FULL build mode dùng validate scope chunk; không phải FULL evidence audit.

Ngày chốt: 2026-10-02 (port kiến trúc /vanchinh hoàn chỉnh). Lịch sử:
bản 4-workflow (quality-gate + factory-production + factory-liveness +
factory-publish-verify) và bản 6-workflow (refill chỉ local) đã
RETIRED — `factory-production.yml` KHÔNG còn tồn tại; publisher duy nhất
là `factory-publish.yml` (push-driven, turbo queue ported từ
/vanchinh). Cập nhật 2026-10-05 theo lệnh chủ xe (55598ac1):
`factory-refill.yml` được PHỤC HỒI như workflow thứ 7 — refill đẩy lên
CI để ledger/seed/matrix/checkpoint/reports commit đồng bộ trong MỘT
commit đã validate (chặn tái diễn drift checkpoint/matrix như sự cố
BLG-01364), cùng concurrency group `factory-publish` với publisher. Nguyên tắc giữ nguyên: ít code,
ít luật hơn khi cả hai đều an toàn; sản xuất push draft `_drafts/` →
queue → pair claim/QA/publish → audit sâu on-demand. Kỹ thuật sâu:
docs/ADVANCED-FACTORY-RECOVERY.md.

Cập nhật 2026-10-11 (audit đa-writer, docs/MULTI-WRITER-ARCHITECTURE.md): publisher DRAIN backlog (run bị GitHub hủy không
mất draft), resume-first PER-WRITER thay cho resume-first toàn cục (một hàng REPAIR không còn deadlock cả nhà máy),
commit/push qua `scripts/factory/publisher-push.py` (chặn rebase ghép sửa đổi chưa QA vào bài đã publish), registry lease v2 gắn
session; retire `custom-domain-migration.yml` (migration đã xong); ghi nhận helper `factory-extract-rows.yml`.

## 1. Danh sách workflow (CHÍNH XÁC 7 hợp đồng + 1 helper)

| Workflow | Trigger | Quyền | Phạm vi |
|---|---|---|---|
| `quality-gate.yml` | push main theo paths (matrix, `_drafts/**`, `_posts/**`, `scripts/**`, `.github/workflows/**`, layouts/includes/data/config), pull_request cùng paths, workflow_dispatch | `contents: read` | Dual-mode READ-ONLY (port pattern /shop article-quality + `scripts/factory/gate-scope.py`, fail-closed). Content push (drafts/posts/matrix/QA evidence/state/reports): CHỈ `validate.py --scope chunk` — KHÔNG build + KHÔNG quét link toàn site mỗi cycle. Engine push (scripts/layouts/includes/data/config/workflow/docs/matrix-seed/production-control) hoặc dispatch: + Jekyll build (`actions/jekyll-build-pages@v1`) + built-link integrity + draft-leak + sitemap/schema/hub sanity. Luôn working-tree clean. Job `engine-tests` (chỉ FULL mode, độc lập với job gate đỏ): `scripts/factory/run-tests.py --suites ci` — unit + hợp đồng workflow + mô phỏng đồng thời đa-writer, OFFLINE. Trigger gồm MỌI thay đổi `.github/workflows/**`; concurrency group RIÊNG theo PR/commit (không run nào hủy run khác). KHÔNG commit, KHÔNG claim, KHÔNG publish. |
| `factory-publish.yml` | push main theo paths `_drafts/**`, `_drafts/.nudge-*` (nudge tường minh vì wildcard có thể không khớp dotfile) và chính workflow file | `contents: write` | Production publisher DUY NHẤT (mô hình /vanchinh): push writer chứa 1..10 draft (write-ahead queue) → selection EXACT ID qua canonical `scripts/factory/push-selection.py`: draft của push bị kiểm STRICT (từ chối ID trùng, ID lạ, hàng EXISTING/BLOCKED/REVIEW, > 10 draft/push, sai chủ lease/session; hàng PUBLISHED = race push trùng/re-run đã superseded → bỏ qua sạch published_edits exit 0, run GREEN no-op, KHÔNG sửa lại bài đã publish) **và DRAIN** mọi draft đang xếp hàng trong `_drafts/` (`--backlog`, ≤ 30 ID/run; draft hỏng bị CÁCH LY không chặn draft khác; REPAIR chỉ vào queue khi draft đổi so với evidence) → chia pair 2 deterministic (hàng in-flight trước, PLANNED sau) → consume tuần tự: claim chỉ hàng PLANNED (`prepare-next --ids`, KHÔNG bị chặn bởi hàng dở của writer khác), `qa --ids --scope fast`, `publish --ids` (CHỈ hàng PASS) → checkpoint. Pair FAIL content = recoverable (REPAIR, chờ chủ lease), KHÔNG rollback pair đã publish, KHÔNG chặn pair/writer khác. FATAL (claim/QA hạ tầng) → fail run, KHÔNG commit, pair chưa chạy ghi `deferred`, run kế drain lại. Commit + push qua `publisher-push.py` (một commit/run; integrity sha256 bài == QA content_sha256; non-FF → rebase CHỈ khi upstream không đụng path của commit; tối đa 3 rebase; KHÔNG force push). Concurrency group `factory-publish`, `cancel-in-progress: false` (GitHub giữ 1 run chờ và HỦY run chờ cũ — drain bù lại). |
| `factory-liveness.yml` | CHỈ workflow_dispatch (không cron) | `contents: read` | Liveness READ-ONLY: `watchdog.py` (unhealthy = run FAIL, KHÔNG chỉ warning) + `factory-operator.py status` + purity check working-tree sạch. KHÔNG recover, KHÔNG claim, KHÔNG publish, KHÔNG commit. |
| `factory-publish-verify.yml` | CHỈ workflow_dispatch (không cron) | `contents: read` | FULL audit READ-ONLY: watchdog + `factory-operator.py verify --scope full` + refill gate G1-G8 (pure selftest) + `sitemap-plan.py` + generator drift/idempotency + Jekyll build + built-link deep check + draft-leak + hub/pagination render + working-tree clean. KHÔNG commit, KHÔNG push. |
| `production-watchdog.yml` | schedule cron `*/30 * * * *` + workflow_dispatch | `contents: read` | AGENT #6 wake-watchdog LIGHTWEIGHT read-mostly: `production-watchdog.py --dry-run` — đọc timestamp progress (checkpoint/txn PUBLISHED/writer-claims/QA evidence), khi >= 2h không valid progress và MỌI guard idle (#4/#5 idle, không maintenance-lock, không pause/blocked chủ động, không incident mở, không writer cycle active, không publisher active, không build/deploy active) thì báo WOULD WAKE; ship dry-run KHÔNG tự kích hoạt — wake thật là quyết định người vận hành. KHÔNG build, KHÔNG quét link, KHÔNG repair, KHÔNG commit/push. |
| `factory-refill.yml` | push main theo paths `data/factory/refill-request.json`, `data/factory/refill-batches/**`; workflow_dispatch action=refill | `contents: write` | Refill DEDICATED (phục hồi 2026-10-05, 55598ac1): recover transaction FAIL-CLOSED → stage batch đã duyệt qua gate G1-G8 (`stage-refill-batch.py --all`, idempotent, FAIL = rollback) → `factory-operator.py refill` (materialize work thật, SUCCESS bắt buộc planned tăng) → validate chunk read-only → commit + push fast-forward MỘT LẦN (đồng bộ ledger, seed, matrix, checkpoint, reports) → watchdog + status. Refill FAIL = run FAIL (tín hiệu rõ cho writer: sửa batch hoặc mở rộng topic thật) — KHÔNG filler, KHÔNG SUCCESS giả. Concurrency group `factory-publish`, `cancel-in-progress: false` — xếp hàng với publisher, KHÔNG mutate state cùng lúc. KHÔNG claim, KHÔNG QA, KHÔNG publish bài. |
| `factory-soak.yml` | CHỈ workflow_dispatch | `contents: read` | Reliability/soak on-demand, HERMETIC đối với production: chạy `scripts/factory/tests/test_soak_recovery.py` trên fixture cô lập (multi-chunk + failure recovery) + purity check. KHÔNG mutation production state, KHÔNG commit. |

| `factory-extract-rows.yml` (helper) | push main theo paths `data/factory/extract-request.json`, `data/factory/extract-request-W*.json` | `contents: write` | Helper cho writer không đọc được matrix CSV >1MB: đọc matrix, ghi `reports/factory/extracted-rows[-Wn].json` (mỗi slot một file riêng để 3 writer không đè nhau); chỉ commit các file `extracted-rows*.json`, push có bounded rebase retry, KHÔNG force, KHÔNG chạm state sản xuất, KHÔNG API ngoài. Không thuộc đường publish. |

Pages deploy bằng cơ chế built-in của GitHub (branch main), không cần
workflow riêng.

## 2. Đã retire (KHÔNG quay lại)

- `.github/workflows/publish-drafts.yml` (publisher đơn giản bản
  4-workflow — thay bằng `factory-publish.yml` turbo queue ported từ
  /vanchinh)
- `.github/workflows/factory-production.yml` (đường nóng bản 4/5-workflow
  — thay bằng `factory-publish.yml` push-driven)
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
- `.github/workflows/custom-domain-migration.yml` (migration sang custom
  domain đã xong; workflow một-lần có `contents: write` không còn cần)
- `scripts/factory/tests/test_push_rebase_overlap.py` (đối tượng — file
  lệnh operator — không còn tồn tại)

`test_hardening.py` (S7 StaticContract) chặn việc các file trên quay lại
và chặn thêm workflow mới ngoài danh sách (7 hợp đồng + helper
factory-extract-rows.yml; factory-refill.yml nằm TRONG danh sách — phục
hồi theo lệnh chủ xe 2026-10-05).

## 3. Bất biến giữ nguyên (KHÔNG giảm khi thay đổi workflow)

- `publish-gate.py` là cơ chế promote DUY NHẤT vào `_posts/`; publish
  đòi: hàng PASS, `quality >= 75`, `seo >= 70`, `business_fact = PASS`,
  `legal = PASS | NOT_REQUIRED`, không critical failure,
  `content_sha256` khớp draft, `matrix_row_sha256` khớp hàng matrix.
- Publisher concurrency = 1: `factory-publish.yml` là đường nóng sản xuất
  DUY NHẤT (mutator duy nhất đi vào `_posts/`); `factory-refill.yml` mutate
  state refill (ledger/seed/matrix/checkpoint/reports) cùng concurrency group;
  helper `factory-extract-rows.yml` chỉ commit `reports/factory/extracted-rows*.json`;
  mọi workflow khác READ-ONLY. External writer CHỈ push draft `_drafts/` của ID
  mình giữ (+ registry qua tool, + batch refill), KHÔNG BAO GIỜ tự promote vào
  `_posts/`.
- KHÔNG force push ở mọi workflow (bounded rebase retry tối đa 3 lần;
  publisher chỉ rebase khi upstream không đụng path của commit; conflict →
  abort); transaction/writer-lock còn tồn tại → publisher
  guard FAIL-CLOSED trước khi mutate; stale lock KHÔNG bị force-delete
  bừa — recover là op local theo docs/RECOVERY.md.
- KHÔNG AI (kể cả mã nguồn mở), không API key AI, không secret, không gọi host
  ngoài GitHub từ workflow; không cron sản xuất (cron duy nhất:
  `production-watchdog.yml`, read-only dry-run).
- Refill KHÔNG chạy trong đường nóng publish: writer/coordinator push batch
  `data/factory/refill-batches/**` (+ bump `refill-request.json`), `factory-refill.yml`
  stage G1-G8 và materialize khi claimable PLANNED < min_ready_queue, FETCH MAIN,
  rồi mới `begin` ID mới. Refill FAIL (hết pool STAGED → NEEDS_TOPIC_EXPANSION) chỉ
  dừng refill; writer chịu trách nhiệm mở rộng topic theo gate.
- Resume-first PER-WRITER: hàng REPAIR chờ CHỦ lease sửa (repair rows KHÔNG claim
  lại từ đầu) và KHÔNG chặn writer khác; `writer-session.py begin` không cấp ID mới
  cho chủ còn REPAIR (trừ `--allow-new-with-repair`). `DEFERRED` = pair chưa xử lý do
  FATAL, run kế drain lại.
- Ownership: mỗi ID một chủ, mỗi slot một phiên, lease có TTL/heartbeat; không chiếm
  lease còn hạn; registry hỏng ⇒ fail-closed (docs/RECOVERY.md).
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

### Agent #6 — director / production watchdog (`production-watchdog.py`)

- TRÁCH NHIỆM DUY NHẤT: đánh thức production bình thường khi KHÔNG có
  valid progress liên tục 2 giờ. KHÔNG repair, KHÔNG recovery — đó là
  việc của #4/#5.
- `last_valid_progress_at` = timestamp mới nhất của progress THẬT:
  checkpoint.updated_at, transaction history result=PUBLISHED,
  writer-claims claimed_at/updated_at, QA evidence scored_at.
  Log/heartbeat/status check/polling/run FAIL/lần chạy watchdog
  KHÔNG reset đồng hồ.
- Trước khi wake kiểm tra TOÀN BỘ guard; MỘT điều kiện còn hoạt động
  → DO NOTHING (fail-safe). Wake idempotent qua marker
  `data/state/watchdog-wake.json` + cooldown 2h — hai lần chạy
  watchdog KHÔNG tạo duplicate cycle.
- Wake = kích hoạt ĐÚNG MỘT entrypoint production bình thường hiện có
  (`factory-operator.py prepare-next` — hệ thống tự allocate/fan-out;
  operator tự refuse khi maintenance-lock/pause: double safety).
  KHÔNG trực tiếp khởi động Writer #1/#2/#3, KHÔNG sửa queue/manifest,
  KHÔNG cancel run.
- Ship mặc định dry-run: workflow chỉ báo WOULD WAKE, KHÔNG BAO GIỜ
  tự kích hoạt production. Bật wake thật = người vận hành thêm cờ
  wake vào workflow.
- Test hợp đồng: `scripts/factory/tests/test_production_watchdog.py`
  (27 test hermetic với stub operator).
