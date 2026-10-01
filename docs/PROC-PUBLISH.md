# PROC-PUBLISH — Vòng viết & xuất bản qua Factory production

Mục tiêu: xuất bản liên tục từng cặp 2 bài (chunk_size trong `data/factory/production-control.json`, tối đa 10) qua đúng engine chuẩn của
/blog, KHÔNG để lộ bản nháp, KHÔNG AI trong Actions.

## Mô hình vận hành (bắt buộc hiểu đúng)

```
EXTERNAL AI (writer/coordinator)      ← viết prose, điều phối
   |  commit/push draft vào _drafts/ (tối đa chunk_size = 2 ID/push),
   |  chỉ cần GitHub read/write, KHÔNG cần git/Python/Node
   v
GitHub Actions factory-production.yml ← MÔI TRƯỜNG THỰC THI
   |  PUSH main paths _drafts/** TỰ ĐỘNG CHẠY ĐƯỜNG NÓNG:
   |  push-selection.py chọn EXACT ID (mới/repair/no-op; refuse >2 ID,
   |  ID trùng, ID lạ, ID đã PUBLISHED) → production-control
   |  enabled=false → exit sạch TRƯƠC khi claim → recover →
   |  prepare-next --ids → qa --ids → publish --ids (hàng PASS)
   |  → light smoke → commit/push một lần → watchdog
   |  workflow_dispatch CHỈ còn op bảo trì (không còn next/qa/publish
   |  dispatch cho cặp bài thường)
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

## Đường nóng PUSH (sản xuất cặp bài thường — KHÔNG cần dispatch)

Writer push draft vào `_drafts/` → workflow tự động trên push main
(paths `_drafts/**`, hoặc `data/factory/refill-request.json` khi cần
refill — xem bước 0):

1. `scripts/factory/push-selection.py` chọn EXACT ID từ file draft
   ADDED/MODIFIED của push: mode NEW (hàng PLANNED có draft) → claim đúng
   ID đó; mode REPAIR (hàng WRITING/QA/REPAIR/PASS) → chỉ QA/publish ID
   sửa; mode SKIP (no-op) → exit 0. REFUSE (exit 3, fail-closed):
   >2 ID (chunk_size), ID trùng, thiếu/sai `article_id`, ID không có
   trong matrix, ID đã PUBLISHED/EXISTING (KHÔNG BAO GIỜ ghi đè), hàng
   REVIEW/BLOCKED/FAIL, tên draft sai slug matrix, push trộn mới + repair.
2. production-control `enabled=false` → exit SẠCH trước khi claim.
3. `recover` trước mọi op mutating (FAIL-CLOSED).
4. `prepare-next --ids` claim EXACT ID vừa push (KHÔNG claim hàng
   PLANNED khác).
5. `qa --ids --scope fast` (ngưỡng 75/70 KHÔNG đổi).
6. `publish --ids` — chỉ hàng PASS của vòng QA đó, QUA publish-gate.py
   (publish-gate vẫn là cơ chế promote DUY NHẤT; mọi hard gate giữ nguyên).
7. Light smoke: `validate.py --scope chunk` + `queue.py --stats`
   (KHÔNG verify full/soak/hardening).
8. Khi selection báo `refill_advised` (claimable PLANNED < chunk_size):
   op `refill` chuẩn tự chạy trong cùng lần push (sau light smoke, trước
   commit — KHÔNG cần dispatch).
9. Commit + push fast-forward MỘT lần; watchdog xác nhận txn inactive,
   lock sạch, checkpoint ổn định.

## Actions bảo trì của factory-production.yml (workflow_dispatch)

| Action | Lệnh engine | Ghi chú |
|---|---|---|
| `status` | `factory-operator.py status` | read-only; in checkpoint/txn/lock/matrix |
| `recover` | `factory-operator.py recover` | phục hồi transaction treo; ownership không rõ → STOP |
| `refill` | `factory-operator.py refill` | materialize hàng PLANNED từ refill ledger khi dưới ngưỡng; semantic: SUCCESS bắt buộc tạo work thật; hết candidate STAGED → NEEDS_TOPIC_EXPANSION, KHÔNG filler |
| `diagnostics` | `validate.py --scope chunk` + `queue.py --stats` | chẩn đoán read-only |

Các op `next`/`qa`/`publish` KHÔNG còn là action dispatch — cặp bài
thường chạy qua đường nóng push; các op khác của `factory-operator.py`
(requeue, release-chunk, verify, reports) giữ nguyên cho chạy cục bộ/
chẩn đoán. Workflow tự chạy `recover` trước mọi op mutating.

## Manifest writer (export bởi prepare-next)

Path: `reports/factory/rows/<BLG-ID>.json`. Writer ngoài đọc manifest và
viết draft đúng `draft_path`. Manifest chứa: title/intent/keyword,
URL/canonical/permalink, taxonomy + hub, business facts (chỉ nguồn
`data/business-facts.json`), source_required/legal_risk/research_class
(theo `docs/SOURCE-RESEARCH.md`), ứng viên liên kết nội bộ (theo
`docs/INTERNAL-LINKING.md`), ngưỡng QA, vân tay hàng matrix
(`matrix_row_sha256`).

## Quy trình một cặp bài (push-driven)

0. Trước khi chọn cặp tiếp theo: nếu hàng PLANNED còn claim được < 2,
   push cập nhật `data/factory/refill-request.json` (hoặc push cặp draft
   kế tiếp — khi push-selection báo `refill_advised`, workflow tự chạy op
   `refill` chuẩn trong cùng lần push, KHÔNG cần dispatch tay). Refill
   SUCCESS (PLANNED thật tăng) → chọn cặp từ `next_claimable_id`/manifest
   và làm tiếp; NEEDS_TOPIC_EXPANSION → workflow chỉ cảnh báo; writer
   STOP, báo đúng blocker (hết candidate STAGED trong ledger — cần mở
   rộng topic qua gate), KHÔNG tự tạo filler.
1. Writer ngoài viết draft vào `_drafts/` (KHÔNG `_posts/`), tuân theo
   `docs/ARTICLE-RULES.md`, `docs/SOURCE-RESEARCH.md`,
   `docs/INTERNAL-LINKING.md`, `docs/QUALITY-RUBRIC.md`; frontmatter bắt
   buộc `article_id` đúng hàng matrix; tên file
   `<YYYY-MM-DD>-<slug>.md` đúng slug hàng; commit/push 1-2 draft
   (tối đa chunk_size = 2 ID mỗi push).
2. Push tự kích hoạt đường nóng: selection → claim EXACT ID → QA chấm
   từng draft (cấu trúc, SEO on-page, link nội bộ, business facts,
   cannibalization, legal/source), ghi evidence SHA gắn với nội dung +
   hàng matrix. PASS → hàng PASS (90+ = EXCELLENT, 75-89 = PASS + cảnh
   báo QA — polish defer cho weekly audit); thiếu điểm → REPAIR (writer
   sửa rồi push lại); hết budget repair → BLOCKED. QA không bao giờ tự
   hạ ngưỡng.
3. Repair (nếu cần): writer chỉ sửa draft dính lỗi rồi push lại —
   repair push chỉ QA/publish EXACT ID đã sửa, KHÔNG claim việc mới.
4. `publish --ids`: từng hàng PASS qua `publish-gate.py`
   (lock + hash + transaction chuẩn) promote `_drafts/` → `_posts/`, chốt
   ngày thật vào URL, cập nhật matrix + checkpoint; sinh reports +
   verify theo scope fast; workflow commit + push fast-forward.
5. Chờ Quality gate xanh trên đúng HEAD + Pages deploy SUCCESS + kiểm tra
   live URL 200 + sitemap.

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
- Lần chạy sau: dispatch `recover` → hoàn tất việc dở → mới nhận việc mới.
  Hàng PASS còn treo (QA xong nhưng chưa publish): push lại draft của ID
  đó (repair push) — đường nóng QA lại rồi publish EXACT ID.
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
