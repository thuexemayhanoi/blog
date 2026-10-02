# PROC-PUBLISH — Vòng viết & xuất bản qua Factory production

Mục tiêu: xuất bản liên tục từng cặp 2 bài (chunk_size trong `data/factory/production-control.json`, tối đa 10) qua đúng engine chuẩn của
/blog, KHÔNG để lộ bản nháp, KHÔNG AI trong Actions.

## Mô hình vận hành (bắt buộc hiểu đúng)

```
EXTERNAL AI (writer/coordinator)      ← viết prose, điều phối
   |  commit/push draft vào _drafts/ (2..10 ID/push — turbo queue
   |  write-ahead, consume theo pair 2), chỉ cần GitHub read/write,
   |  KHÔNG cần git/Python/Node
   v
GitHub Actions factory-publish.yml ← MÔI TRƯỜNG THỰC THI
   |  PUSH main paths _drafts/** TỰ ĐỘNG CHẠY ĐƯỜNG NÓNG:
   |  selection EXACT ID qua canonical push-selection.py (refuse >10 ID, ID trùng,
   |  ID lạ, ID đã PUBLISHED/EXISTING/BLOCKED) → guard không
   |  transaction/lock (FAIL-CLOSED) → chia PAIR 2 theo thứ tự
   |  matrix → prepare-next --ids (chỉ hàng PLANNED) → qa --ids
   |  --scope fast → publish --ids (hàng PASS) → light smoke →
   |  commit/push MỘT lần → assert clean state
   |  KHÔNG workflow_dispatch — op bảo trì chạy LOCAL
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

## Đường nóng PUSH (sản xuất các bài thường — KHÔNG cần dispatch)

Writer push draft vào `_drafts/` → factory-publish.yml tự động trên push
main (paths `_drafts/**`):

1. Selection (CANONICAL selector `scripts/factory/push-selection.py`,
   đọc truth tươi sau fetch origin):
   EXACT ID theo `article_id` của các file draft ADDED/MODIFIED trong
   push. REFUSE (fail-closed): >10 draft/push (turbo queue), ID trùng
   trong cùng push, thiếu `article_id`, ID không có trong matrix, ID đã
   PUBLISHED/EXISTING/BLOCKED (KHÔNG BAO GIỜ ghi đè). Production-control
   `enabled=false` + push cần claim → exit sạch TRƯỚC khi claim. Mode:
   `new` (có hàng PLANNED cần claim) hoặc `repair` (chỉ QA/publish ID
   sửa, KHÔNG claim lại từ đầu).
2. Guard FAIL-CLOSED: còn `data/state/writer-lock.active` hoặc
   transaction `active` → run FAIL trước mọi mutation (stale lock
   KHÔNG bị force-delete bừa — recover trước).
3. Queue chia PAIR 2 deterministic theo thứ tự matrix, consume tuần tự
   trong CÙNG run: `prepare-next --ids` claim CHỈ hàng PLANNED của pair
   (KHÔNG claim hàng PLANNED khác, KHÔNG claim lại hàng đang dở).
4. `qa --ids --scope fast` + `publish --ids` từng pair (ngưỡng 75/70
   KHÔNG đổi; publish QUA publish-gate.py — cơ chế promote DUY NHẤT,
   mọi hard gate giữ nguyên).
5. Pair FAIL content → pair đó recoverable (REPAIR, giữ QA evidence),
   KHÔNG rollback pair đã publish; engine resume-first — từ đó pair còn
   lại chỉ DEFERRED (không claim mới khi còn việc dở). FATAL (claim/QA
   hạ tầng) → run FAIL, KHÔNG commit.
6. Light smoke: `validate.py --scope chunk` (KHÔNG verify
   full/soak/hardening trong hot loop — đó là của factory-publish-verify
   / factory-soak).
7. Refill KHÔNG chạy trong đường nóng: khi pool claimable cạn, writer/
   coordinator chạy op bảo trì LOCAL `factory-operator.py refill`,
   CHỜ refill success, FETCH MAIN, rồi mới push cặp bài kế tiếp.
8. Commit MỘT lần (`[automated txn]`) + push fast-forward; non-FF →
   fetch + rebase, bounded retry tối đa 3 lần thử push; rebase conflict
   → abort ngay, KHÔNG force push. Cuối run assert: không lock, không
   txn active.

## Op bảo trì (chạy LOCAL — factory-publish.yml KHÔNG có workflow_dispatch)

factory-publish.yml chỉ chạy trên push main `_drafts/**`. Mọi op bảo trì
chạy cục bộ qua `scripts/factory/factory-operator.py` (môi trường có
quền GitHub) hoặc theo docs/RECOVERY.md:

| Op | Lệnh engine | Ghi chú |
|---|---|---|
| `status` | `factory-operator.py status` | read-only; in checkpoint/txn/lock/matrix |
| `recover` | `factory-operator.py recover` | phục hồi transaction treo; ownership không rõ → STOP |
| `refill` | `factory-operator.py refill` | refill canonical (gate G1-G8; semantic SUCCESS bắt buộc tạo work thật; hết candidate STAGED → NEEDS_TOPIC_EXPANSION, KHÔNG filler) |
| `diagnostics` | `validate.py --scope chunk` + `queue.py --stats` | chẩn đoán read-only |

Các op `next`/`qa`/`publish` KHÔNG còn là action dispatch — các bài
thường chạy qua đường nóng push của factory-publish.yml; các op khác
của `factory-operator.py` (requeue, release-chunk, verify, reports)
giữ nguyên cho chạy cục bộ/chẩn đoán.

## Manifest writer (export bởi prepare-next)

Path: `reports/factory/rows/<BLG-ID>.json`. Writer ngoài đọc manifest và
viết draft đúng `draft_path`. Manifest chứa: title/intent/keyword,
URL/canonical/permalink, taxonomy + hub, business facts (chỉ nguồn
`data/business-facts.json`), source_required/legal_risk/research_class
(theo `docs/SOURCE-RESEARCH.md`), ứng viên liên kết nội bộ (theo
`docs/INTERNAL-LINKING.md`), ngưỡng QA, vân tay hàng matrix
(`matrix_row_sha256`).

## Quy trình một pair bài (push-driven)

0. Trước khi chọn pair kế tiếp: nếu hàng PLANNED còn claim được < 2, chạy
   op bảo trì local `factory-operator.py refill` rồi CHỜ refill success
   và FETCH MAIN. Refill SUCCESS (PLANNED thật tăng) → chọn pair từ
   `next_claimable_id`/manifest và làm tiếp; NEEDS_TOPIC_EXPANSION →
   refill STOP sạch; writer báo đúng blocker (hết candidate STAGED trong
   ledger — cần mở rộng topic qua gate), KHÔNG tự tạo filler.
1. Writer ngoài viết draft vào `_drafts/` (KHÔNG `_posts/`), tuân theo
   `docs/ARTICLE-RULES.md`, `docs/SOURCE-RESEARCH.md`,
   `docs/INTERNAL-LINKING.md`, `docs/QUALITY-RUBRIC.md`; frontmatter bắt
   buộc `article_id` đúng hàng matrix; tên file
   `<YYYY-MM-DD>-<slug>.md` đúng slug hàng; commit/push 2..10 draft
   (turbo queue, tối đa 10 ID mỗi push — consume theo pair 2).
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

## Pipeline chết giữa chừng (resume-first, KHÔNG quét backlog tự động)

Nếu một queue run chết SAU khi draft đã vào `_drafts/` nhưng TRƯỚC
claim/QA/publish hoàn tất, các hàng liên quan KHÔNG bị mất — engine là
resume-first và selection của factory-publish.yml CHỈ đọc các file
draft ADDED/MODIFIED trong push hiện tại (không quét backlog toàn
`_drafts/`):

- Hàng đang dở (WRITING/QA/REPAIR/PASS): writer push lại draft của ID
  đó (repair push — touch/modify file) để ID vào lại queue; mode
  `repair` CHỈ QA/publish EXACT ID đã sửa, KHÔNG claim lại từ đầu.
- Engine resume-first: còn hàng REPAIR/unresolved thì KHÔNG claim bài
  mới — các pair PLANNED còn lại trong cùng queue bị DEFERRED, lần
  publish kế tiếp xử lý sau khi repair xong (prepare-next TỪ CHỐI claim
  mới khi còn việc dở).
- Draft sót hợp lệ chưa từng claim: push lại (touch/modify) draft đó
  trong push kế — nó trở thành queue của push mới và được claim đúng
  EXACT ID. KHÔNG BAO GIỜ claim hàng PLANNED không có draft trong push;
  KHÔNG BAO GIỜ đụng hàng PUBLISHED (kể cả khi draft sót trỏ ID đã xuất
  bản — selection REFUSE).
- Draft KHÔNG hợp lệ (mẫu nháp, thiếu `article_id`, ID lạ, hàng được
  bảo vệ) bị selection REFUSE/bo qua một cách fail-closed — KHÔNG âm
  thầm publish.
- Repair có ưu tiên trước việc mới; KHÔNG yêu cầu writer tạo lại draft
  đã push.

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
- Lần chạy sau: chạy `recover` (op local) → hoàn tất việc dở → mới nhận
  việc mới. Hàng PASS còn treo (QA xong nhưng chưa publish): push lại
  draft của ID đó (repair push) — đường nóng QA lại rồi publish EXACT
  ID. (Hợp đồng resume: `docs/RECOVERY.md`.)
- Push chỉ fast-forward; origin đổi giữa chừng → fetch + rebase rồi
  push lại (bounded, tối đa 3 lần thử push); rebase conflict → abort
  ngay, KHÔNG force push, KHÔNG replay.

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

Mặc định FAST cho `prepare-next` / `qa` / `publish` trên đường nóng:
factory-publish.yml chạy `qa --ids` / `publish --ids` với `--scope fast`
cho từng pair.
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
