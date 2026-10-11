# PROC-PUBLISH — Vòng viết & xuất bản qua Factory production

Mục tiêu: xuất bản liên tục từng cặp 2 bài (chunk_size trong `data/factory/production-control.json`, tối đa 10) qua đúng engine chuẩn của
/blog, KHÔNG để lộ bản nháp, KHÔNG AI trong Actions.

## Mô hình vận hành (bắt buộc hiểu đúng)

```
EXTERNAL AI (writer/coordinator)      ← viết prose, điều phối
   |  commit/push draft vào _drafts/ (1..10 ID/push — turbo queue
   |  write-ahead, consume theo pair 2) qua scripts/factory/writer-session.py
   |  (CAS, tối đa 3 slot W1/W2/W3, mỗi slot một phiên); cần git + Python 3
   v
GitHub Actions factory-publish.yml ← MÔI TRƯỜNG THỰC THI
   |  PUSH main paths _drafts/** TỰ ĐỘNG CHẠY ĐƯỜNG NÓNG:
   |  selection EXACT ID qua canonical push-selection.py (push: refuse >10 ID, ID trùng,
   |  ID lạ, ID đã EXISTING/BLOCKED/REVIEW, sai chủ lease; hàng PUBLISHED = race push trùng đã superseded → bỏ qua sạch exit 0)
   |  + DRAIN backlog (--backlog: mọi draft đang xếp hàng trong _drafts/, ≤30 ID/run, draft hỏng bị cách ly)
   |  → guard không transaction/lock (FAIL-CLOSED) → chia PAIR 2 (in-flight trước, PLANNED sau)
   |  → prepare-next --ids (chỉ hàng PLANNED) → qa --ids
   |  --scope fast → publish --ids (CHỈ hàng PASS) → light smoke →
   |  publisher-push.py: commit/push MỘT lần (guard giao-path, integrity sha256) → assert clean state
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
   EXISTING/BLOCKED/REVIEW (KHÔNG BAO GIỜ ghi đè; hàng PUBLISHED bị push trùng sau race → bỏ qua sạch published_edits exit 0, KHÔNG refuse),
   và draft "độc" không đi được qua engine (preflight engine-ready: không phải UTF-8, thiếu `date`/`title`/`categories`/`description`
   trong frontmatter, còn placeholder, `date:` sai dạng hoặc lệch tiền tố tên file, tên file khác `YYYY-MM-DD-<slug hàng>.md`, hai file
   cho một hàng). Push bị REFUSE vẫn DRAIN backlog hợp lệ của writer khác (run chờ của họ có thể đã bị run này thay) rồi mới làm ĐỎ run
   ở step cuối (`refused=true`); backlog rỗng thì đỏ ngay. Production-control
   `enabled=false` → bỏ ID PLANNED khỏi queue (không claim bài mới) nhưng vẫn xử lý hàng in-flight (repair/PASS). Mode:
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
5. Pair FAIL content → hàng đó recoverable (REPAIR, giữ QA evidence),
   KHÔNG rollback pair đã publish và KHÔNG chặn pair/writer khác; hàng
   REPAIR chờ CHỦ lease của nó sửa (resume-first là PER-WRITER, thực thi
   ở bước claim). FATAL (claim/QA hạ tầng) → run FAIL, KHÔNG commit,
   pair chưa chạy ghi `deferred`, run kế drain lại.
6. Light smoke: `validate.py --scope chunk` (KHÔNG verify
   full/soak/hardening trong hot loop — đó là của factory-publish-verify
   / factory-soak).
7. Refill KHÔNG chạy trong đường nóng: khi pool claimable cạn, writer/
   coordinator push batch chủ đề thật (`data/factory/refill-batches/`) +
   bump `data/factory/refill-request.json`; `factory-refill.yml` (CÙNG
   concurrency group với publisher) stage + materialize. CHỜ refill
   success, FETCH MAIN, rồi mới push bài kế tiếp.
8. Commit MỘT lần (`[automated txn]`) qua `publisher-push.py` + push
   fast-forward; non-FF → fetch, CHỈ rebase khi upstream không đụng path
   nào của commit này, tối đa 3 lần rebase (tức tối đa 4 lần push);
   rebase conflict/giao path → dừng, KHÔNG force push. Cuối run assert:
   không lock, không txn active.

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

0. Trước khi chọn pair kế tiếp: nếu hàng PLANNED còn claim được < 2, push
   batch chủ đề thật + bump `refill-request.json` (workflow
   `factory-refill.yml` chạy refill) rồi CHỜ refill success và FETCH MAIN. Refill SUCCESS (PLANNED thật tăng) → chọn pair từ
   `next_claimable_id`/manifest và làm tiếp; NEEDS_TOPIC_EXPANSION →
   refill STOP sạch; writer báo đúng blocker (hết candidate STAGED trong
   ledger — cần mở rộng topic qua gate), KHÔNG tự tạo filler.
1. Writer ngoài viết draft vào `_drafts/` (KHÔNG `_posts/`), tuân theo
   `docs/ARTICLE-RULES.md`, `docs/SOURCE-RESEARCH.md`,
   `docs/INTERNAL-LINKING.md`, `docs/QUALITY-RUBRIC.md`; frontmatter bắt
   buộc `article_id` đúng hàng matrix; tên file
   `<YYYY-MM-DD>-<slug>.md` đúng slug hàng; commit/push 1..10 draft
   (turbo queue, tối đa 10 ID mỗi push — consume theo pair 2).
2. Push tự kích hoạt đường nóng: selection → claim EXACT ID → QA chấm
   từng draft (cấu trúc, SEO on-page, link nội bộ, business facts,
   cannibalization, legal/source), ghi evidence SHA gắn với nội dung +
   hàng matrix. PASS → hàng PASS (90+ cả hai chỉ ghi nhãn EXCELLENT; 75-89 là PASS
   hợp lệ — KHÔNG ép 90/100, KHÔNG cảnh báo band, bài >= 75/70 không sửa
   chỉ để tăng điểm); thiếu điểm → REPAIR (CHỦ lease sửa rồi push lại);
   hard gate chống trùng (duplicate title/slug/canonical/intent gần
   trùng với hàng active) → REPAIR ngay bất kể điểm; hết budget repair
   → BLOCKED. QA không bao giờ tự hạ ngưỡng.
3. Repair (nếu cần): writer chỉ sửa draft dính lỗi rồi push lại —
   repair push chỉ QA/publish EXACT ID đã sửa, KHÔNG claim việc mới.
4. `publish --ids`: từng hàng PASS qua `publish-gate.py`
   (lock + hash + transaction chuẩn) promote `_drafts/` → `_posts/`, chốt
   ngày thật vào URL, cập nhật matrix + checkpoint; sinh reports +
   verify theo scope fast; workflow commit + push fast-forward.
5. Chờ Quality gate xanh trên đúng HEAD + Pages deploy SUCCESS + kiểm tra
   live URL 200 + sitemap.

## Pipeline chết giữa chừng / run bị hủy (DRAIN backlog)

Repo là hàng đợi, trigger chỉ là gợi ý. GitHub giữ một run chờ mỗi concurrency group và hủy run chờ cũ khi có run chờ mới
(kể cả bởi factory-refill.yml), nên MỖI run quét toàn bộ draft đang xếp hàng (`push-selection.py --backlog`, tối đa 30 ID):

- Run bị hủy / chết TRƯỚC commit: không đổi gì trên main; draft còn trong `_drafts/` và run kế publish chúng (không cần
  "touch" lại).
- Hàng đang dở (PASS còn chờ publish; WRITING/QA có draft): tự được nhặt lại. Hàng REPAIR chỉ vào queue khi draft ĐỔI so với
  bằng chứng QA cuối (sha256) — không QA lại vô hạn bản đã FAIL.
- Draft KHÔNG hợp lệ (thiếu `article_id`, ID lạ, hàng được bảo vệ, không có lease sống, sai chủ, nhiều file cùng ID, và draft "độc"
  theo preflight engine-ready: không UTF-8, thiếu `date`/`title`/`categories`/`description`, placeholder, tên file/`date:` sai) bị CÁCH LY
  (ghi trong log run) — không chặn draft khác, không bị âm thầm publish, không làm mọi run đỏ.
- Draft của ID đã PUBLISHED: bỏ qua sạch (no-op xanh), KHÔNG BAO GIỜ đụng lại bài đã publish.
- Re-run của một push cũ (draft đã chuyển sang `_posts/`): no-op xanh, idempotent.
- Run chờ bị run KHÁC workflow (refill) thay và không còn push nào sau đó: `writer-session.py confirm` tự nudge
  (`_drafts/.nudge-Wx`; path filter có pattern tường minh `_drafts/.nudge-*`), hoặc bất kỳ push draft kế tiếp sẽ drain.

## Bằng chứng PASS khi xuất bản (publish-gate kiểm tra, không tự khai)

`quality >= 75`, `seo >= 70`, `business_fact = PASS`,
`legal = PASS | NOT_REQUIRED`, `critical_failure = false`,
`content_sha256` khớp draft hiện tại, `matrix_row_sha256` khớp hàng matrix
hiện tại. Hàng phải đang PASS. Mọi lệch hash → từ chối
(STALE_QA_EVIDENCE / MATRIX_ROW_MISMATCH).

## Chính sách lỗi

- Op nào FAIL (FATAL hạ tầng) → workflow DỪNG, KHÔNG commit gì (phần pair
  đã publish TRONG run đó bị bỏ cùng workspace; draft vẫn trong `_drafts/`,
  run kế drain lại — chỉ tốn công làm lại, không mất bài). Content fail
  (QA FAIL → REPAIR, gate từ chối) thì KHÔNG phải FATAL: pair khác vẫn
  publish, hàng lỗi chờ chủ sửa. Ghi lại: ID lỗi, action lỗi, HEAD,
  checkpoint, transaction, lock, các ID chưa xong, lệnh resume chính xác.
- Lần chạy sau: chạy `recover` (op local) → hoàn tất việc dở → mới nhận
  việc mới. Hàng PASS còn treo (QA xong nhưng chưa publish) được backlog
  nhặt lại tự động; nếu draft không qua preflight/gate thì bị cách ly với
  lý do trong log — sửa draft rồi push. (Hợp đồng resume:
  `docs/RECOVERY.md`.)
- Push chỉ fast-forward; origin đổi giữa chừng → fetch, rebase CHỈ khi
  upstream không đụng path của commit (tối đa 3 lần rebase = 4 lần push);
  giao path/rebase conflict → dừng ngay, KHÔNG force push, KHÔNG replay.

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
suite engine (25 suite CI qua `scripts/factory/run-tests.py --suites ci`, gồm
hardening, watchdog, mô phỏng đồng thời 3 writer; + soak 20 vòng hermetic).
Job `engine-tests` của quality-gate.yml chạy nhóm CI ở FULL mode.
KHÔNG phải điều kiện xuất bản mỗi cặp. factory-publish-verify.yml chạy mức
này mỗi tuần (read-only).

## HEALTHY (liveness watchdog)

Sau mỗi run sản xuất, engine phải ở trạng thái HEALTHY
(`scripts/factory/watchdog.py` — READ-ONLY):

    python3 scripts/factory/watchdog.py    # HEALTHY_ACTIVE/HEALTHY_IDLE, exit 0

STALE_TXN/STALE_LOCK/STALE_CHECKPOINT/STALLED_ACTIVE (exit 1): xử lý theo
`docs/RECOVERY.md` rồi mới nhận việc mới. Watchdog READ-ONLY, KHÔNG tự
xoá/force-unlock. factory-liveness chạy watchdog theo yêu cầu (workflow_dispatch).
