# AGENTS — thuexemayhanoi/blog (Hanoi motorbike rental, mục tiêu 10K bài)

Blog Jekyll trên GitHub Pages. Một chủ xe vận hành qua AI trên điện thoại.
Triết lý: sản xuất → QA nhanh → publish → audit sâu định kỳ. Kỹ thuật sâu
(chống double-spend, SHA evidence, 4 tầng test, soak): docs/ADVANCED-FACTORY-RECOVERY.md.

## Mô hình 3 workflow (docs/factory-workflow-contract.md)

- `quality-gate.yml` — CI FAST trên MỌI push main / PR: validate chunk + Jekyll
  build + link integrity + draft leak + sitemap/hub sanity. READ-ONLY.
- `factory-production.yml` — đường sản xuất DUY NHẤT. `workflow_dispatch` với
  action: `status | resume | next | qa | publish | refill` (+ count 1-10, ids).
  Không cron, không AI, không secret AI. Push chỉ fast-forward; rebase xong
  phải validate lại; KHÔNG force push.
- `weekly-maintenance.yml` — audit tuần READ-ONLY (cron 09:30 Hà Nội thứ Hai):
  watchdog + verify FULL + refill gates + sitemap plan + generator drift +
  build/links deep. KHÔNG commit.

Luồng chunk: `next` (claim PLANNED) → writer viết draft `_drafts/` → `qa`
(chấm + evidence hash) → sửa nếu REPAIR → `publish` (promote qua gate) →
chờ Quality gate xanh + Pages deploy + kiểm URL live. Hết PLANNED thì
`refill` (ledger STAGED → PLANNED, KHÔNG filler).

## 10 quy tắc

1. Engine là nguồn sự thật duy nhất: matrix + checkpoint + transaction +
   writer-lock. KHÔNG tin số đếm trong prose docs — đọc `data/state/` và
   reports sinh máy.
2. Xuất bản CHỈ qua `scripts/factory/publish-gate.py` (cổng duy nhất vào
   `_posts/`). KHÔNG promote tay, KHÔNG tạo URL trùng ID/slug/canonical.
3. Ngưỡng xuất bản: `quality >= 75`, `seo >= 75`, `business_fact = PASS`,
   `legal = PASS | NOT_REQUIRED`, không critical failure. 90+ = EXCELLENT;
   75-89 = PASS (cảnh báo QA — vấn đề polish defer cho weekly audit).
   KHÔNG hạ dưới mức chủ xe đã duyệt. KHÔNG tự hạ ngưỡng khi QA FAIL.
4. Số liệu kinh doanh/pháp lý chỉ từ `data/business-facts.json` và nguồn
   chính thức theo `docs/SOURCE-RESEARCH.md`. KHÔNG bịa giá, cọc, phí trễ,
   bảo hiểm, địa danh.
5. Bài viết tuân thủ `docs/ARTICLE-RULES.md` + `docs/QUALITY-RUBRIC.md`;
   draft nằm trong `_drafts/`, KHÔNG bao giờ vào `_posts/` tay.
6. Một writer tại một thời điểm: writer-lock O_EXCL + ownership token;
   transaction conflict → STOP theo `docs/RECOVERY.md`, KHÔNG force-unlock
   lock của chủ khác.
7. Sản xuất qua `factory-production.yml` (dispatch), KHÔNG chạy shell tùy
   ý trong Actions. `recover` TRƯỚC mọi op mutating. Op FAIL → DỪNG, giữ
   việc đã xong, resume từ repository truth.
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
