# PROC-PUBLISH — Vòng viết & xuất bản qua Factory production

Mục tiêu: xuất bản liên tục từng cặp 2 bài (chunk_size trong `data/factory/production-control.json`, tối đa 10) qua đúng engine chuẩn của
/blog, KHÔNG để lộ bản nháp, KHÔNG AI trong Actions.

## Mô hình vận hành (bắt buộc hiểu đúng)

```
EXTERNAL AI (writer/coordinator)      ← viết prose, điều phối
   |  chỉ cần GitHub read/write, KHÔNG cần git/Python/Node
   v
GitHub Actions factory-production.yml ← MÔI TRƯỜNG THỰC THI
   |  workflow_dispatch: action + count + ids (KHÔNG còn file lệnh
   |  operator-command.json — dispatch input là kênh lệnh duy nhất)
   v
scripts/factory/factory-operator.py    ← TAY DETERMINISTIC
   v
ENGINE CHUẨN (nguồn sự thật duy nhất)
   writer-lock (O_EXCL + ownership token)
   + transaction + checkpoint
   + publish-gate.py (cơ chế promote DUY NHẤT)
   + refill-queue.py (refill DUY NHẤT)
   + matrix + QA evidence (data/qa/<ID>.json)
```

- EXTERNAL AI = writer/coordinator: viết draft trong `_drafts/`, đọc
  manifest, quyết định editorial, KHÔNG tự promote, KHÔNG sửa matrix tay.
- GITHUB ACTIONS = deterministic hands: KHÔNG gọi API AI, KHÔNG chứa
  secret AI, KHÔNG viết prose, KHÔNG bịa факт. Chỉ chạy tooling chuẩn.
- ENGINE = nguồn sự thật: mọi mutation qua lock/transaction/gate chuẩn.

## Actions của factory-production.yml (workflow_dispatch)

| Action | Lệnh engine | Ghi chú |
|---|---|---|
| `status` | `factory-operator.py status` | read-only; in checkpoint/txn/lock/matrix |
| `resume` | `factory-operator.py recover` | phục hồi transaction treo; ownership không rõ → STOP |
| `next` | `factory-operator.py prepare-next --count N --scope fast` | claim N hàng PLANNED → WRITING + manifest; N 1-10, mặc định 2 theo production-control |
| `qa` | `factory-operator.py qa [--ids ...] --scope fast` | QA deterministic; ghi evidence `data/qa/<ID>.json` |
| `publish` | `factory-operator.py publish --ids ... --scope fast` | promote HÀNG PASS qua publish-gate.py; ids BẮT BUỘC |
| `refill` | `factory-operator.py refill` | materialize hàng PLANNED từ refill ledger khi dưới ngưỡng; semantic: SUCCESS bắt buộc tạo work thật; hết candidate STAGED → NEEDS_TOPIC_EXPANSION, KHÔNG filler |

Các op khác của `factory-operator.py` (requeue, release-chunk, verify,
reports) giữ nguyên cho chạy cục bộ/chẩn đoán; luồng sản xuất chuẩn chỉ
dùng 6 action trên. Workflow tự chạy `recover` trước mọi op mutating.

## Manifest writer (export bởi prepare-next)

Path: `reports/factory/rows/<BLG-ID>.json`. Writer ngoài đọc manifest và
viết draft đúng `draft_path`. Manifest chứa: title/intent/keyword,
URL/canonical/permalink, taxonomy + hub, business facts (chỉ nguồn
`data/business-facts.json`), source_required/legal_risk/research_class
(theo `docs/SOURCE-RESEARCH.md`), ứng viên liên kết nội bộ (theo
`docs/INTERNAL-LINKING.md`), ngưỡng QA, vân tay hàng matrix
(`matrix_row_sha256`).

## Quy trình một chunk

1. Preflight (mỗi run): checkout main → kiểm tra input → `status` →
   `recover` TRƯỚC (transaction treo; ownership không rõ → STOP).
   KHÔNG chạy validate toàn site trước recover — transaction treo sẽ
   khiến validate FAIL chặn recover mãi (deadlock).
2. `next` (count=5): engine từ chối nếu còn hàng WRITING/QA/REPAIR/PASS
   chưa xong; claim đúng từ `checkpoint.next_claimable_id`; chỉ nhận
   PLANNED; REVIEW/BLOCKED luôn được bảo vệ.
3. Writer ngoài viết draft vào `_drafts/` (KHÔNG `_posts/`), tuân theo
   `docs/ARTICLE-RULES.md`, `docs/SOURCE-RESEARCH.md`,
   `docs/INTERNAL-LINKING.md`, `docs/QUALITY-RUBRIC.md`, rồi push draft.
4. `qa --ids ...`: QA chấm từng draft (cấu trúc, SEO on-page, link nội
   bộ, business facts, cannibalization, legal/source), ghi evidence SHA
   gắn với nội dung + hàng matrix. PASS → hàng PASS (90+ = EXCELLENT,
   75-89 = PASS + cảnh báo QA — polish defer cho weekly audit); thiếu
   điểm → REPAIR (writer sửa rồi qa lại); hết budget repair → BLOCKED.
   QA không bao giờ tự hạ ngưỡng.
5. Repair (nếu cần): writer chỉ sửa draft dính lỗi, push, chạy `qa` lại.
6. `publish --ids ...`: từng hàng PASS qua `publish-gate.py`
   (lock + hash + transaction chuẩn) promote `_drafts/` → `_posts/`, chốt
   ngày thật vào URL, cập nhật matrix + checkpoint; sinh reports +
   verify theo scope fast; workflow commit + push fast-forward.
7. Chờ Quality gate xanh trên đúng HEAD + Pages deploy SUCCESS + kiểm tra
   live URL 200 + sitemap. Hết PLANNED → `refill` rồi tiếp tục.

## Bằng chứng PASS khi xuất bản (publish-gate kiểm tra, không tự khai)

`quality >= 75`, `seo >= 70`, `business_fact = PASS`,
`legal = PASS | NOT_REQUIRED`, `critical_failure = false`,
`content_sha256` khớp draft hiện tại, `matrix_row_sha256` khớp hàng matrix
hiện tại. Hàng phải đang PASS. Mọi lệch hash → từ chối
(STALE_QA_EVIDENCE / MATRIX_ROW_MISMATCH).

## Chính sách lỗi

- Op nào FAIL → workflow DỪNG, KHÔNG claim hàng mới; phần việc đã xong
  an toàn được giữ. Ghi lại: ID lỗi, action lỗi, HEAD, checkpoint,
  transaction, lock, các ID chưa xong, lệnh resume chính xác.
- Lần chạy sau: `resume` (recover) → hoàn tất việc dở → mới nhận việc mới.
  (Hợp đồng resume: `docs/RECOVERY.md`.)
- Push chỉ fast-forward; origin đổi giữa chừng → fetch + rebase + validate
  chunk lại rồi push (tối đa 2 lần); rebase conflict hoặc validate FAIL →
  STOP, KHÔNG force push, KHÔNG replay.

## QA modes — FAST / DEEP / FULL (sản xuất thủ công, không tự lặp)

Factory KHÔNG tự điều phối: không self-dispatch, không vòng lặp Actions
chạy tiếp, không scheduling sản xuất. Người vận hành (chủ xe hoặc agent
theo lệnh tay) tự quyết định khi nào chạy mức nào.

Lệnh chuẩn (local / chẩn đoán):

    python3 scripts/factory/qa.py --mode fast [--ids BLG-xxx,...]
    python3 scripts/factory/qa.py --mode deep
    python3 scripts/factory/qa.py --mode full
    python3 scripts/factory/validate.py --scope chunk|batch|full

### FAST (mặc định — QA sản xuất mỗi cặp 2 bài)

Mặc định FAST cho `next` / `qa` / `publish` ở CẢ preflight lẫn verify cuối
run: action không chỉ định scope khác thì workflow chạy `--scope fast`.
FULL giữ cho thay đổi engine/workflow và kiểm tra cuối đợt
(factory-publish-verify.yml chạy verify FULL theo yêu cầu).

- QA deterministic TỪNG BÀI của chunk hiện tại: cấu trúc, frontmatter,
  H1/H2, title, meta description, canonical/permalink, taxonomy, link
  nội bộ (route thật + baseurl /blog), business facts, cannibalization,
  legal/source gate khi bắt buộc, quality/SEO theo rubric.
- validate.py `--scope chunk`: nền bắt buộc + bằng chứng QA của chunk.
- KHÔNG làm sau mỗi 10 bài: quét 483 bài legacy, sitemap live, hash QA
  của MỌI bài PUBLISHED, crawl toàn site. Phát hiện dấu hiệu hệ thống ở
  fast → nâng lên deep/full, KHÔNG hạ ngưỡng.
- Ngưỡng: quality >= 75, seo >= 70, business_fact/legal PASS-FAIL,
  critical_failure = false.

### DEEP (thủ công, ~mỗi 50 bài)

Mọi thứ của fast + validate.py `--scope batch`: URL legacy, khớp
matrix-inventory, hash QA toàn bộ PUBLISHED, hub pages + test link
integrity. Không sitemap live.

### FULL (weekly + trước/sau đổi engine)

validate.py `--scope full`: toàn repository + capacity-audit + toàn bộ
suite engine (12 suite, gồm hardening, watchdog, soak 20 vòng hermetic).
KHÔNG phải điều kiện xuất bản mỗi cặp. factory-publish-verify.yml chạy mức
này mỗi tuần (read-only).

## HEALTHY (liveness watchdog)

Sau mỗi run sản xuất, engine phải ở trạng thái HEALTHY
(`scripts/factory/watchdog.py` — READ-ONLY):

    python3 scripts/factory/watchdog.py    # HEALTHY_ACTIVE/HEALTHY_IDLE, exit 0

STALE_TXN/STALE_LOCK/STALE_CHECKPOINT/STALLED_ACTIVE (exit 1): xử lý theo
`docs/RECOVERY.md` rồi mới nhận việc mới. Watchdog READ-ONLY, KHÔNG tự
xoá/force-unlock. factory-liveness chạy watchdog mỗi 6 giờ.
