# AGENTS — thuexemayhanoi/blog (Hanoi motorbike rental, mục tiêu 10K bài)

Blog Jekyll trên GitHub Pages. Một chủ xe vận hành qua AI trên điện thoại.
Triết lý: sản xuất → QA nhanh → publish → audit sâu định kỳ. Kỹ thuật sâu
(chống double-spend, SHA evidence, 4 tầng test, soak): docs/ADVANCED-FACTORY-RECOVERY.md.

## Mô hình 7 workflow (docs/factory-workflow-contract.md)

- `quality-gate.yml` — CI FAST trên MỌI push main / PR: validate chunk + Jekyll
  build + link integrity + draft leak + sitemap/hub sanity. READ-ONLY.
- `factory-publish.yml` — production publisher DUY NHẤT, PUSH-DRIVEN:
  writer push draft `_drafts/` (turbo queue 2..10 ID/push) → workflow
  selection EXACT ID qua CANONICAL scripts/factory/push-selection.py
  (REFUSE ID trùng, ID lạ, hàng
  PUBLISHED/EXISTING/BLOCKED, >10) → chia pair 2 theo thứ tự matrix →
  consume tuần tự claim (chỉ hàng PLANNED)/QA/publish từng pair.
  Pair FAIL content = recoverable (REPAIR), KHÔNG rollback pair đã
  publish; engine resume-first — còn repair/unresolved thì KHÔNG claim
  pair mới (DEFERRED lần kế). FATAL → fail run, KHÔNG commit. Push chỉ
  fast-forward; non-FF → bounded rebase retry (tối đa 3 lần thử);
  KHÔNG force push. Không cron, không AI, không secret AI, không
  workflow_dispatch.
- `factory-liveness.yml` — liveness READ-ONLY mỗi 6 giờ (cron): watchdog
  (unhealthy = FAIL run) + status + purity. KHÔNG bao giờ
  recover/delete/claim/publish.
- `factory-publish-verify.yml` — FULL audit READ-ONLY (CHỈ
  workflow_dispatch, không cron): watchdog + verify FULL + refill gates
  + sitemap plan + generator drift + build/links deep + draft leak +
  hub render. KHÔNG commit. Thay cho weekly-maintenance.yml đã retire.
- `factory-soak.yml` — reliability/soak HERMETIC on-demand (CHỈ
  workflow_dispatch): test soak recovery trên fixture cô lập, KHÔNG
  mutation production state, KHÔNG commit.
- `article-batch.yml` — batch planning/status DRY-RUN READ-ONLY (CHỈ
  workflow_dispatch): validate full + progress snapshot + queue stats.
  KHÔNG claim, KHÔNG publish, KHÔNG commit.
- `factory-refill.yml` — refill DEDICATED, PUSH-DRIVEN + dispatch: khi
  writer đẩy batch chủ đề thật `data/factory/refill-batches/**` hoặc bump
  `data/factory/refill-request.json` thì workflow tự stage (gate
  G1-G8) → `factory-operator.py refill` → commit ĐỒNG BỘ ledger, seed,
  matrix, checkpoint, reports trong MỘT commit đã validate; CÙNG
  concurrency group `factory-publish` với publisher (hai run xếp hàng,
  KHÔNG mutate state cùng lúc). KHÔNG claim, KHÔNG publish bài.

Chế độ TURBO mặc định cho external AI writer: khi có đủ hàng PLANNED hợp lệ và lease riêng, chuẩn bị đủ 10 draft rồi push trong MỘT commit; publisher vẫn chia 5 pair x 2. Không tăng production-control.chunk_size (giữ 2), không tự promote, không giảm QA. Ít hơn 10 bài khi thiếu hàng hợp lệ hoặc cần sửa REPAIR; không tạo bài đệm. Quy trình chi tiết: `docs/TURBO-WRITER-RUNBOOK.md`.

Luồng pair bài (push-driven): writer đọc status/manifests → viết 2..10
draft `_drafts/` → push → workflow TỰ claim EXACT ID (pair 2) → QA
(chấm + evidence hash) → publish hàng PASS qua gate → sửa REPAIR thì chỉ
cần push lại draft đã sửa (repair push, mode repair KHÔNG claim lại từ
đầu) → chờ Quality gate xanh + Pages deploy + kiểm URL live.

Refill theo ngưỡng vận hành `min_ready_queue=100`, mục tiêu `refill_target=300` trong `data/factory-capacity.json`: AI coordinator chuẩn bị và lọc chủ đề sớm khi PLANNED < 100; tuyệt đối không coi capacity là bài đã viết. Khi cần refill, writer CHỈ push (1) batch chủ đề thật
`data/factory/refill-batches/<date>-<tag>.json` (đã qua gate G1-G8) và
(2) bump `data/factory/refill-request.json`. Workflow
`factory-refill.yml` (CÙNG concurrency group `factory-publish` với
publisher — hai run xếp hàng, không mutate state cùng lúc) tự
stage + materialize và commit ĐỒNG BỘ ledger, seed, matrix, checkpoint,
reports trong MỘT commit đã validate. Writer KHÔNG bao giờ tự
commit/sửa `data/state/*` hay số đếm checkpoint; nếu `validate` báo
`checkpoint lệch matrix` thì chạy op canonical
`factory-operator.py repair-checkpoint` (tái sinh counts +
next_claimable_id từ matrix truth — xem docs/RECOVERY.md), KHÔNG sửa
tay. Sau refill SUCCESS (run xanh): FETCH MAIN rồi mới viết cặp kế
tiếp. Hết candidate STAGED → NEEDS_TOPIC_EXPANSION: viết batch chủ đề
thật mới, KHÔNG filler, KHÔNG báo SUCCESS giả. Hồi quy:
`scripts/factory/tests/test_refill_drift.py`.

## 10 quy tắc

1. Engine là nguồn sự thật duy nhất: matrix + checkpoint + transaction +
   writer-lock. KHÔNG tin số đếm trong prose docs — đọc `data/state/` và
   reports sinh máy.
2. Xuất bản CHỈ qua `scripts/factory/publish-gate.py` (cổng duy nhất vào
   `_posts/`). KHÔNG promote tay, KHÔNG tạo URL trùng ID/slug/canonical.
3. Ngưỡng xuất bản: `quality >= 75`, `seo >= 70`, `business_fact = PASS`,
   `legal = PASS | NOT_REQUIRED`, không critical failure. 90+ = EXCELLENT;
   75-89 = PASS (cảnh báo QA — vấn đề polish defer cho weekly audit).
   KHÔNG hạ dưới mức chủ xe đã duyệt. KHÔNG tự hạ ngưỡng khi QA FAIL.
4. Số liệu kinh doanh/pháp lý chỉ từ `data/business-facts.json` và nguồn
   chính thức theo `docs/SOURCE-RESEARCH.md`. KHÔNG bịa giá, cọc, phí trễ,
   bảo hiểm, địa danh.
5. Bài viết tuân thủ `docs/ARTICLE-RULES.md` + `docs/QUALITY-RUBRIC.md`;
   draft nằm trong `_drafts/`, KHÔNG bao giờ vào `_posts/` tay.
6. Chỉ MỘT publisher được mutate production mỗi lúc (writer-lock O_EXCL + ownership token); tối đa 3 external writer có thể soạn song song nếu lease ID không trùng (`writer-claim.py`). Transaction conflict → STOP theo `docs/RECOVERY.md`, KHÔNG force-unlock lock của chủ khác.
7. Sản xuất qua `factory-publish.yml` (push `_drafts/` tự động; op bảo trì
   chạy local qua `factory-operator.py`), KHÔNG chạy shell tùy ý trong
   Actions. `recover` TRƯỚC mọi op mutating. Op FAIL → DỪNG, giữ việc đã
   xong, resume từ repository truth.
8. Mọi commit sản xuất là output deterministic của tooling chuẩn
   (`factory-operator.py`) — KHÔNG AI trong Actions, KHÔNG viết prose trong
   workflow, KHÔNG sửa nội dung đã PUBLISHED.
9. KHÔNG force push, KHÔNG reset checkpoint/matrix, KHÔNG xóa evidence
   `data/qa/<ID>.json`. `content_sha256`/`matrix_row_sha256` phải khớp.
10. Trước khi tuyên bố xong: Quality gate XANH trên đúng HEAD + Pages deploy
    SUCCESS + URL live 200. Báo cáo phân biệt HEAD đã chạy vs HEAD đã push.

## QA modes (docs/PROC-PUBLISH.md)

FAST (mặc định mỗi chunk): validate `--scope chunk` + suite gate/operator/
refill-safety/workflow-syntax. DEEP (~mỗi 50 bài): + link integrity, qa
modes, publish flow, refill semantics (scope batch). FULL (weekly / trước
đổi engine): validate full + 12 suite + soak (scope full). Ngưỡng KHÔNG đổi
giữa các mức.
