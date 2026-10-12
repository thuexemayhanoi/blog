# AGENTS — thuexemayhanoi/blog (Hanoi motorbike rental, mục tiêu 10K bài)

Blog Jekyll trên GitHub Pages. Một chủ xe vận hành qua AI trên điện thoại.
Triết lý: sản xuất → QA nhanh → publish → audit sâu định kỳ. Kỹ thuật sâu
(chống double-spend, SHA evidence, 4 tầng test, soak): docs/ADVANCED-FACTORY-RECOVERY.md.

**AI writer mới vào việc? Đọc `docs/AI-WRITER-QUICKSTART.md` (một trang). Kiến trúc đa-writer:
`docs/MULTI-WRITER-ARCHITECTURE.md`.** Provider-neutral: tối đa 3 AI bất kỳ cùng viết (slot W1/W2/W3).

## Mô hình workflow (docs/factory-workflow-contract.md) — 7 hợp đồng + 1 helper

- `quality-gate.yml` — cổng READ-ONLY dual-mode, trigger push main / PR **theo paths**
  (matrix, `_drafts/**`, `_posts/**`, `scripts/**`, `.github/workflows/**`, layouts/includes/data/config). Content push:
  CHỈ `validate.py --scope chunk`. Engine push (scripts/layouts/…): + Jekyll build + link
  integrity + draft leak + sitemap/hub sanity (mode `full`).
- `factory-publish.yml` — production publisher DUY NHẤT, PUSH-DRIVEN + **DRAIN**: writer push
  draft `_drafts/` (1..10 ID/push) → selection EXACT ID qua CANONICAL
  `scripts/factory/push-selection.py` (push: REFUSE ID trùng, ID lạ, hàng EXISTING/BLOCKED/REVIEW,
  >10, sai chủ lease; hàng PUBLISHED = bỏ qua sạch, run xanh no-op) **và quét toàn bộ draft đang
  xếp hàng** (`--backlog`: run bị GitHub hủy KHÔNG làm mất draft; draft hỏng bị cách ly, không
  chặn draft khác; tối đa 30 ID/run) → chia pair 2 theo thứ tự matrix (hàng in-flight trước,
  PLANNED sau) → consume tuần tự claim (chỉ hàng PLANNED)/QA/publish (chỉ hàng PASS) từng pair.
  Pair FAIL content = recoverable (REPAIR), KHÔNG rollback pair đã publish và KHÔNG chặn writer
  khác (resume-first là PER-WRITER, thực thi ở bước claim). FATAL → fail run, KHÔNG commit, run
  kế drain lại. Commit/push qua `scripts/factory/publisher-push.py` (một commit/run, guard
  giao-path chống rebase ghép sửa đổi vào bài đã publish, integrity sha256, tối đa 3 rebase,
  KHÔNG force push). Không cron, không AI, không secret, không API ngoài, không workflow_dispatch.
- `factory-liveness.yml` — liveness READ-ONLY (CHỈ workflow_dispatch, không cron): watchdog
  (unhealthy = FAIL run) + status + purity. KHÔNG bao giờ recover/delete/claim/publish.
- `factory-publish-verify.yml` — FULL audit READ-ONLY (CHỈ workflow_dispatch, không cron):
  watchdog + verify FULL + refill gates + sitemap plan + generator drift + build/links deep + draft
  leak + hub render. KHÔNG commit, KHÔNG gọi host ngoài GitHub (đối chiếu sitemap live là opt-in tay
  `FACTORY_LIVE_SITEMAP=1`).
- `factory-soak.yml` — reliability/soak HERMETIC on-demand (CHỈ workflow_dispatch): KHÔNG mutation
  production state, KHÔNG commit.
- `production-watchdog.yml` — cron `*/30`, READ-ONLY `--dry-run` (báo WOULD WAKE, không tự kích hoạt).
- `factory-refill.yml` — refill DEDICATED, PUSH-DRIVEN + dispatch: khi writer đẩy batch chủ đề thật
  `data/factory/refill-batches/**` hoặc bump `data/factory/refill-request.json` thì workflow tự stage
  (gate G1-G8) → `factory-operator.py refill` (chỉ materialize khi claimable PLANNED < min_ready_queue)
  → commit ĐỒNG BỘ ledger, seed, matrix, checkpoint, reports trong MỘT commit đã validate; CÙNG
  concurrency group `factory-publish` với publisher (hai run xếp hàng, KHÔNG mutate state cùng
  lúc). KHÔNG claim, KHÔNG publish bài.
- (helper) `factory-extract-rows.yml` — trích hàng matrix cho writer không đọc được CSV >1MB: push
  `data/factory/extract-request[-Wn].json` → commit `reports/factory/extracted-rows[-Wn].json`. Chỉ
  đọc matrix; mỗi slot dùng file RIÊNG để 3 writer không đè nhau.

## Multi-writer (tối đa 3 slot, 1 publisher)

`3 writers (W1/W2/W3) → hàng đợi draft dùng chung → 1 publisher canonical → website`.
- Slot gắn **session**: một slot thuộc đúng MỘT phiên và mỗi phiên chỉ giữ MỘT slot sống tại một thời điểm; lease tối đa 10 ID/slot, 30 ID
  đang làm; TTL + heartbeat; hết hạn mới được phiên khác nhận (`writer-claim.py`, `writer-session.py`).
- Writer dùng **một công cụ**: `python3 scripts/factory/writer-session.py begin|status|check|push|confirm|release`
  (CAS: fetch → tính lại → push, bounded retry, không force). Đừng tự viết git để claim/push registry.
  Phiên mặc định ngẫu nhiên theo working copy (KHÔNG suy từ danh tính git — nhiều AI cùng nhà cung cấp
  dùng chung một danh tính) và MẤT khi container bị tạo lại. AI chạy lặp/có thể hết quota PHẢI dùng **session
  ổn định, riêng cho từng slot**: `export FACTORY_WRITER_SESSION=s-<ai>-w<N>` — hiện dùng: W1 `s-mistral-w1`,
  W2 `s-claude-w2`, W3 dành sẵn dạng `s-<ai>-w3`. Đó là NHÃN công khai (hiện trong registry và frontmatter draft),
  KHÔNG phải credential: không bao giờ dùng token GitHub/API làm session id, không commit secret, không dùng nhãn
  của slot khác. Resume sau hết quota/đổi container: `git pull` → export lại ĐÚNG nhãn → `writer-session.py status`
  (mục `me`) → `begin --slot <slot>` nhận lại lease/REPAIR của chính mình (lease đã hết hạn thì cùng phiên nối lại
  ID/REPAIR của nó); lease còn hạn của AI khác không bao giờ bị chiếm.
- Writer chỉ ghi `_drafts/**` của ID mình giữ, `data/state/writer-claims.json` (qua tool) và batch refill.
  `_posts/`, matrix, `data/qa/**`, checkpoint, transaction, writer-lock, `reports/**` chỉ publisher/CI ghi.
- Mỗi draft khai `writer: Wn` (+ `writer_session: s-…`, `check` tự gắn) — selector refuse (exit 3) nếu
  không khớp lease sống. Không writer nào sửa draft thuộc lease sống của writer khác.

Chế độ TURBO mặc định cho external AI writer: khi có đủ hàng PLANNED hợp lệ và lease riêng, chuẩn bị đủ 10 draft rồi push trong MỘT commit; publisher vẫn chia 5 pair x 2. Không tăng production-control.chunk_size (giữ 2), không tự promote, không giảm QA. Ít hơn 10 bài khi thiếu hàng hợp lệ hoặc cần sửa REPAIR; không tạo bài đệm. Quy trình chi tiết: `docs/TURBO-WRITER-RUNBOOK.md`.

Luồng pair bài (push-driven): writer `begin` (lease) → viết draft → `check` (QA cục bộ cùng scorer) →
`push` → workflow TỰ claim EXACT ID (pair 2) → QA (chấm + evidence hash) → publish hàng PASS qua
gate → `confirm`: PUBLISHED / REPAIR (sửa đúng draft rồi `push` lại, mode repair KHÔNG claim lại) /
PENDING (tool tự nudge) → chờ Pages deploy + kiểm URL live. Hết quota/mất kết nối: lease tự hết hạn,
phần đã push vẫn được publish, AI khác `begin` nhận tiếp.

Refill theo ngưỡng vận hành `min_ready_queue=100`, mục tiêu `refill_target=300` trong `data/factory-capacity.json`: AI coordinator chuẩn bị và lọc chủ đề sớm khi PLANNED < 100; tuyệt đối không coi capacity là bài đã viết. Khi cần refill, writer CHỈ push (1) batch chủ đề thật
`data/factory/refill-batches/<date>-<tag>.json` (đã qua gate G1-G8) và
(2) bump `data/factory/refill-request.json`. Workflow
`factory-refill.yml` (CÙNG concurrency group `factory-publish` với
publisher — hai run xếp hàng, không mutate state cùng lúc) tự
stage + materialize (khi PLANNED còn claim được < min_ready_queue) và commit ĐỒNG BỘ ledger, seed, matrix, checkpoint,
reports trong MỘT commit đã validate. Writer KHÔNG bao giờ tự
commit/sửa `data/state/*` (NGOẠI LỆ duy nhất: `data/state/writer-claims.json` qua `writer-session.py`/`writer-claim.py`) hay số đếm checkpoint; nếu `validate` báo
`checkpoint lệch matrix` thì chạy op canonical
`factory-operator.py repair-checkpoint` (tái sinh counts +
next_claimable_id từ matrix truth — xem docs/RECOVERY.md), KHÔNG sửa
tay. Sau refill SUCCESS (run xanh): FETCH MAIN rồi mới viết cặp kế
tiếp. Hết candidate STAGED → NEEDS_TOPIC_EXPANSION: viết batch chủ đề
thật mới, KHÔNG filler, KHÔNG báo SUCCESS giả. Hồi quy:
`scripts/factory/tests/test_refill_drift.py`.

## 10 quy tắc (+3 đa-writer)

1. Engine là nguồn sự thật duy nhất: matrix + checkpoint + transaction +
   writer-lock. KHÔNG tin số đếm trong prose docs — đọc `data/state/` và
   reports sinh máy.
2. Xuất bản CHỈ qua `scripts/factory/publish-gate.py` (cổng duy nhất vào
   `_posts/`). KHÔNG promote tay, KHÔNG tạo URL trùng ID/slug/canonical.
3. Ngưỡng xuất bản: `quality >= 75`, `seo >= 70`, `business_fact = PASS`,
   `legal = PASS | NOT_REQUIRED`, không critical failure. 90+ = EXCELLENT (nhãn);
   75+ là đạt và publish thẳng. KHÔNG hạ dưới mức chủ xe đã duyệt. KHÔNG tự hạ
   ngưỡng khi QA FAIL, KHÔNG nới luật để tăng số lượng.
4. Số liệu kinh doanh/pháp lý chỉ từ `data/business-facts.json` và nguồn
   chính thức theo `docs/SOURCE-RESEARCH.md`. KHÔNG bịa giá, cọc, phí trễ,
   bảo hiểm, địa danh.
5. Bài viết tuân thủ `docs/ARTICLE-RULES.md` + `docs/QUALITY-RUBRIC.md`;
   draft nằm trong `_drafts/`, KHÔNG bao giờ vào `_posts/` tay.
6. Chỉ MỘT publisher được mutate production mỗi lúc (writer-lock O_EXCL + ownership token + concurrency group); tối đa 3 external writer soạn song song, mỗi ID một chủ, mỗi slot một phiên, mỗi phiên một slot (`writer-claim.py`, thực thi cả ở lõi và CAS). Registry mơ hồ ID/session → fail-closed, không chọn chủ bằng timestamp hoặc rollback lease sống. Transaction conflict → STOP theo `docs/RECOVERY.md`, KHÔNG force-unlock lock của chủ khác.
7. Sản xuất qua `factory-publish.yml` (push `_drafts/` tự động; op bảo trì
   chạy local qua `factory-operator.py`), KHÔNG chạy shell tùy ý trong
   Actions. `recover` TRƯỚC mọi op mutating. Op FAIL → DỪNG, giữ việc đã
   xong, resume từ repository truth.
8. Mọi commit sản xuất là output deterministic của tooling chuẩn
   (`factory-operator.py`, `publisher-push.py`) — KHÔNG AI trong Actions, KHÔNG viết prose trong
   workflow, KHÔNG sửa nội dung đã PUBLISHED, KHÔNG gọi API/host ngoài GitHub từ workflow, KHÔNG dùng AI mã nguồn mở.
9. KHÔNG force push, KHÔNG reset checkpoint/matrix/lease đang hoạt động, KHÔNG xóa evidence
   `data/qa/<ID>.json`. `content_sha256`/`matrix_row_sha256` phải khớp. KHÔNG làm giả evidence, KHÔNG PASS/PUBLISHED thủ công.
   Evidence cũ lệch hash vì migrate domain CHỈ được thay bằng bản chấm lại ĐỘC LẬP qua
   `scripts/factory/reattest-legacy-qa.py` (chủ duyệt, backup byte-exact, verify, rollback) — không bao giờ sửa tay.
10. Trước khi tuyên bố xong: Quality gate XANH trên đúng HEAD của push (commit bot dùng GITHUB_TOKEN không kích hoạt gate — kiểm
    bằng run publish xanh) + Pages deploy SUCCESS + URL live 200. Báo cáo phân biệt HEAD đã chạy vs HEAD đã push.
11. Không chiếm lease còn hạn; không sửa draft thuộc lease sống của writer khác; nhận việc orphan chỉ qua `--adopt`.
12. Hết quota/mất kết nối: không mất draft đã push (publisher vẫn publish); bàn giao bằng `slot + session id`.
13. Tên nhà cung cấp AI không xuất hiện trong logic production; `docs/mistral/README.md` chỉ còn là con trỏ tương thích.

## QA modes (docs/PROC-PUBLISH.md)

Audit evidence cũ chỉ đọc: `scripts/factory/audit-legacy-qa.py`. Re-attest có kiểm soát (đường GHI
duy nhất cho evidence cũ): `scripts/factory/reattest-legacy-qa.py plan|apply|verify|rollback`, quy trình +
số liệu: `docs/LEGACY-QA-RE-ATTESTATION-PLAN.md`. Domain-only không đồng nghĩa QA PASS: chỉ bài có hash cũ
buộc đúng byte/hàng baseline VÀ chấm lại độc lập (ngưỡng 75/70, business_fact, legal, critical) đạt mới được
thay evidence, cần `--approval-ref` của chủ xe, batch ≤ 300, backup `reports/qa-audit/reattest/<batch>.json`.
Chỉ áp dụng lên evidence thật SAU KHI chủ website đã nghiệm thu quy trình (chỉ thị MASTER 2026-10-12): writer/Routine KHÔNG tự chạy `apply`.
Ca không đạt / nội dung đổi thật GIỮ NGUYÊN để xử lý riêng. Không sửa `_posts/`, matrix, checkpoint, lease và
không sửa tay `data/qa/` để làm audit xanh.

FAST (mặc định mỗi chunk): validate `--scope chunk` + suite gate/operator/
refill-safety/workflow-syntax. DEEP (~mỗi 50 bài): + link integrity, qa
modes, publish flow, refill semantics (scope batch). FULL (weekly / trước
đổi engine): validate full + 27 suite CI (`scripts/factory/run-tests.py --suites ci`,
job `engine-tests` của quality-gate ở FULL mode) + soak (scope full). Ngưỡng KHÔNG đổi
giữa các mức.
