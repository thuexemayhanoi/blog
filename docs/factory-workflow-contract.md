# Hợp đồng 4 workflow — thuexemayhanoi/blog

Ngày chốt: 2026-09-30 (thay mô hình 5 workflow cũ; bản 4-workflow thay
weekly-maintenance bằng factory-liveness + factory-publish-verify). Nguyên tắc: ít code,
ít luật hơn khi cả hai đều an toàn; sản xuất → QA nhanh → publish → audit
sâu định kỳ. Kỹ thuật sâu: docs/ADVANCED-FACTORY-RECOVERY.md.

## 1. Danh sách workflow (CHÍNH XÁC 4)

| Workflow | Trigger | Quyền | Phạm vi |
|---|---|---|---|
| `quality-gate.yml` | push main, pull_request, workflow_dispatch | `contents: read` | FAST: `validate.py --scope chunk` + Jekyll build (`actions/jekyll-build-pages@v1`) + `check-built-links.py` + draft-leak + sitemap/schema/hub sanity. READ-ONLY, KHÔNG commit. |
| `factory-production.yml` | CHỈ workflow_dispatch (action `status\|resume\|next\|qa\|publish\|refill`, count 1-10 mặc định 2 theo `data/factory/production-control.json`, ids tùy chọn) | `contents: write` | Đường sản xuất DUY NHẤT: chạy `factory-operator.py` với `--scope fast`; recover trước mọi op mutating; push fast-forward, rebase xong validate chunk lại, conflict/FAIL → STOP, KHÔNG force push, tối đa 2 lần thử lại. |
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
và chặn thêm workflow mới ngoài danh sách 4.

## 3. Bất biến giữ nguyên (KHÔNG giảm khi thay đổi workflow)

- `publish-gate.py` là cơ chế promote DUY NHẤT vào `_posts/`; publish
  đòi: hàng PASS, `quality >= 75`, `seo >= 70`, `business_fact = PASS`,
  `legal = PASS | NOT_REQUIRED`, không critical failure,
  `content_sha256` khớp draft, `matrix_row_sha256` khớp hàng matrix.
- KHÔNG force push ở mọi workflow; transaction/writer-lock conflict vẫn
  STOP; bảo vệ ghi đè bài đã PUBLISHED giữ nguyên.
- KHÔNG AI, không secret AI, không cron sản xuất trong bất kỳ workflow.
- Chỉ `factory-production.yml` được `contents: write`, và chỉ commit
  output deterministic của tooling chuẩn.
- Bài nháp KHÔNG được deploy (draft-leak check ở cả quality-gate và weekly).
