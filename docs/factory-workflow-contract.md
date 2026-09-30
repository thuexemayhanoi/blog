# Hợp đồng 3 workflow — thuexemayhanoi/blog

Ngày chốt: 2026-09-30 (thay mô hình 5 workflow cũ). Nguyên tắc: ít code,
ít luật hơn khi cả hai đều an toàn; sản xuất → QA nhanh → publish → audit
sâu định kỳ. Kỹ thuật sâu: docs/ADVANCED-FACTORY-RECOVERY.md.

## 1. Danh sách workflow (CHÍNH XÁC 3)

| Workflow | Trigger | Quyền | Phạm vi |
|---|---|---|---|
| `quality-gate.yml` | push main, pull_request, workflow_dispatch | `contents: read` | FAST: `validate.py --scope chunk` + Jekyll build (`actions/jekyll-build-pages@v1`) + `check-built-links.py` + draft-leak + sitemap/schema/hub sanity. READ-ONLY, KHÔNG commit. |
| `factory-production.yml` | CHỈ workflow_dispatch (action `status\|resume\|next\|qa\|publish\|refill`, count 1-10 mặc định 5, ids tùy chọn) | `contents: write` | Đường sản xuất DUY NHẤT: chạy `factory-operator.py` với `--scope fast`; recover trước mọi op mutating; push fast-forward, rebase xong validate chunk lại, conflict/FAIL → STOP, KHÔNG force push, tối đa 2 lần thử lại. |
| `weekly-maintenance.yml` | cron `30 2 * * 1` (09:30 Hà Nội thứ Hai) + workflow_dispatch | `contents: read` | FULL audit READ-ONLY: watchdog + `factory-operator.py verify --scope full` + refill-queue `--verify/--selftest` + `sitemap-plan.py` + generator drift + build/links deep + hub/pagination render. KHÔNG commit. |

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

`test_hardening.py` (S7 StaticContract) chặn việc các file trên quay lại
và chặn thêm workflow mới ngoài danh sách 3.

## 3. Bất biến giữ nguyên (KHÔNG giảm khi thay đổi workflow)

- `publish-gate.py` là cơ chế promote DUY NHẤT vào `_posts/`; publish
  đòi: hàng PASS, `quality >= 75`, `seo >= 75`, `business_fact = PASS`,
  `legal = PASS | NOT_REQUIRED`, không critical failure,
  `content_sha256` khớp draft, `matrix_row_sha256` khớp hàng matrix.
- KHÔNG force push ở mọi workflow; transaction/writer-lock conflict vẫn
  STOP; bảo vệ ghi đè bài đã PUBLISHED giữ nguyên.
- KHÔNG AI, không secret AI, không cron sản xuất trong bất kỳ workflow.
- Chỉ `factory-production.yml` được `contents: write`, và chỉ commit
  output deterministic của tooling chuẩn.
- Bài nháp KHÔNG được deploy (draft-leak check ở cả quality-gate và weekly).
