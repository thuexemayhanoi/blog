# Continuous Writer Contract — hợp đồng vòng lặp của external writer (/blog)

Tài liệu canonical cho cách writer (agent AI bên ngoài) PHẢI hoạt động
khi chế độ continuous 3-writer được bật. ĐÂY LÀ CONTRACT — trong đợt
migration multi-writer (port từ `thuexemayhanoi/vanchinh`) KHÔNG writer
nào được khởi chạy, KHÔNG bài nào được viết, KHÔNG refill production.

## Mô hình canonical (Simple Production Mode — turbo write-ahead queue)

- Đơn vị QA/publish của factory = PAIR 2 bài. Writer dùng WRITE-AHEAD
  QUEUE: một push xếp hàng 2..10 draft `_drafts/`, `factory-publish.yml`
  (publisher production DUY NHẤT, concurrency 1) tiêu thụ từng pair qua
  `scripts/factory/factory-queue.py`: claim (prepare-next, chỉ hàng
  PLANNED) → scoped QA fast (ngưỡng KHÔNG hạ: quality ≥ 75, SEO ≥ 70)
  → publish transactional (PASS only, canonical publish-gate.py)
  → checkpoint → pair kế.
- Push = TỐI ĐA 10 draft MỚI một lần (hard invariant; vượt → selector
  refuse). Queue lẻ hợp lệ (pair cuối 1 ID).
- MULTI-WRITER: tối đa 3 writer (W1/W2/W3) chạy song song, KHÔNG BAO
  GIỜ trùng ID, qua lease registry `scripts/factory/writer-claim.py`
  (registry `data/state/writer-claims.json`, MAX_WRITERS=3,
  MAX_LEASE=10 ID/writer, TTL 48h, self-heal prune, merge non-FF race
  theo claimed_at sớm-hơn-thắng; KHÔNG bao giờ force push).
- Writer KHÔNG PHẢI publisher: writer chỉ push draft vào `_drafts/`
  (và staging branch của mình trước khi coordinator merge SERIALIZED
  vào main). Mọi mutation production state (matrix WRITING/QA/PASS/
  PUBLISHED, checkpoint, _posts) thuộc về factory-publish.yml chạy
  scripts/factory/factory-queue.py + factory-operator.py.
- GitHub Actions KHÔNG viết prose, KHÔNG gọi AI/API, KHÔNG secrets,
  KHÔNG schedule writer.

## Writer identity (ownership enforcement)

- Registry `data/state/writer-claims.json` TỒN TẠI = multi-writer mode
  ON. Vắng = single-writer legacy (selector không enforce ownership).
- Mọi draft của hàng PLANNED PHẢI khai trong frontmatter:

```yaml
writer: W1   # W1 | W2 | W3 — đúng writer đang giữ lease của ID đó
```

- CANONICAL selector `scripts/factory/push-selection.py` (multi-writer
  mode ON) REFUSE fail-closed exit 3 khi: ID PLANNED không có lease
  sống, hoặc draft khai sai/khuyết `writer:` so với lease holder.
  Identity từ frontmatter — deterministic, theo draft vào git history
  sau merge, KHÔNG dựa vào branch name. Repair rows không claim lại từ
  đầu nên không cần lease.

## LOOP (bắt buộc mỗi writer run)

```
FETCH FRESH MAIN
→ RECOVER/RESUME IF NEEDED (transaction marker; repair-first khi còn
  REPAIR/QA/PASS dở — KHÔNG claim bài mới khi engine còn việc dở)
→ CLAIM LEASE (writer-claim.py claim --writer Wx --count 2..10)
→ WRITE 2..10 (draft thật theo matrix + docs/ARTICLE-RULES.md)
→ LOCAL QA (quality ≥ 75 + SEO ≥ 70, không hạ threshold, không critical)
→ PUSH STAGING/WRITER-BRANCH (staging/writer-x; KHÔNG merge trực tiếp)
→ SERIALIZED PRODUCTION MERGE (coordinator merge MỘT writer một lần,
  chỉ các file _drafts/ của đúng lease — rồi dừng chờ factory xong)
→ WAIT factory-publish.yml + CI GREEN (factory tự tiêu thụ từng pair 2)
→ VERIFY (workflow green, Pages deploy, no lock/txn, queue report
  không fatal, đúng ID PUBLISHED/REPAIR)
→ RELEASE LEASE (writer-claim.py release --writer Wx --ids ...)
→ CHECK QUEUE (queue.py --needs-refill, read-only)
→ AUTO-REFILL NẾU THIẾU (coordinator chạy quy trình refill bên dưới,
  không dừng chờ phê duyệt tay khi còn candidate/capacity hợp lệ)
→ FETCH FRESH MAIN
→ writer-claim.py prune → CLAIM W1/W2/W3 lease mới
→ NEXT (KHÔNG dừng sau mỗi queue)
```

## Không được dừng vì

- một pair vừa publish; một workflow vừa xanh; một Pages deploy vừa
  xong; tests vừa xanh. Đó là checkpoint, KHÔNG phải điểm kết thúc.

## Chỉ được dừng khi

1. Không còn hàng PLANNED claimable và refill không còn capacity, hoặc
2. runtime/session/tool limit buộc dừng — dừng tại điểm an toàn:
   workflow đã xong, fresh main đã fetch, không lock, không txn, lease
   đã release; và
3. blocker thật cần con người (lock của operator khác, txn mơ hồ,
   validation failure critical, queue report fatal hạ tầng).

## Bất biến an toàn mỗi vòng

- Tối đa 3 writer; ID phân phối qua lease registry; KHÔNG BAO GIỜ viết
  ID do writer khác giữ lease (selector refuse, engine fail-closed).
- KHÔNG force push; push registry thua race → fetch fresh main →
  `writer-claim.py merge --file` registry remote → claim lại phần còn
  tự do → push lại.
- Mỗi pair là transaction riêng của engine; pair FAIL không rollback
  pair đã publish; pair FAIL content là RECOVERABLE (repair push lần
  kế), pair PLANNED sau bị DEFERRED (resume-first); FAIL hạ tầng dừng
  cả queue run (draft còn xếp hàng trên main, push sau retry).
- MATRIX là source of truth; checkpoint là derived state.
- Refill: COORDINATOR AUTO-REFILL (chính sách 2026-10-03): khi
  `scripts/factory/queue.py --needs-refill` báo claimable PLANNED <
  min_ready_queue, coordinator PHẢI tự xử lý refill theo quy trình
  ở mục "Auto-refill procedure", không dừng chờ phê duyệt tay.
  Writer vẫn chỉ đọc trạng thái read-only.

## Refill readiness (audit Phase 5 — đã sẵn sàng, chưa chạy)

- Gate G1–G8 của `scripts/factory/refill-queue.py` còn đúng: child
  capacity/headroom (G1), keyword (G2)/intent (G3) chuẩn hóa duy nhất,
  slug (G4)/output_path/canonical (G4b) không trùng, word_target
  (G5), candidate_id (G6), taxonomy (G7), title (G8) — KHÔNG sinh
  filler, KHÔNG trùng lặp.
- Mutation vẫn operator-only + atomic lock (O_EXCL) + fresh HEAD
  re-check + transaction inactive trước mutation.
- Trạng thái read-only cho continuous writer:
  `python3 scripts/factory/queue.py --stats | --needs-refill`
  (claimable PLANNED < min_ready_queue → cần refill).
- Auto-refill chỉ nạp candidate THẬT đã qua gate; ledger hết
  candidate STAGED và không batch/pool hợp lệ nào còn → coi là hết
  candidate hợp lệ (điểm dừng, KHÔNG tạo filler).

## Auto-refill procedure (coordinator — chạy khi queue thiếu)

Thứ tự bắt buộc, sai điều kiện an toàn nào thì DỪNG ở checkpoint an
toàn và báo, không sửa workflow, không hạ gate:

1. FETCH FRESH origin/main.
2. Xác nhận: transaction inactive; production lock free; không có
   hàng REPAIR/QA/PASS unfinished; không có Factory Publish đang chạy.
3. `python3 scripts/factory/refill-queue.py --dry-run` — gate G1-G8
   phải PASS (không rejection thật).
4. Ledger hết candidate STAGED nhưng còn candidate/capacity hợp lệ:
   stage topic THẬT qua đúng cung
   (`stage-refill-batch.py --batch ...` với batch qua gate G1-G8);
   KHÔNG tạo filler, KHÔNG đệm số.
5. PASS hết → `python3 scripts/factory/refill-queue.py --refill --yes`
   (lock atomic O_EXCL + START_HEAD + transaction inactive được script
   tự kiểm; môi trường không có git binary thì HEAD pin là remote main
   SHA đã fetch và xác minh ngay trước khi chạy).
6. `python3 scripts/factory/validate.py` (full) — FAIL checkpoint lệch
   thì chạy `generate-reports.py` rồi validate lại; vẫn FAIL → dừng.
7. COMMIT + PUSH fast-forward lên main (KHÔNG force push).
8. FETCH FRESH main → `writer-claim.py prune` → W1/W2/W3 claim lease
   mới → tiếp tục WRITE bình thường.

Chỉ dừng khi: refill G1-G8 FAIL thật; hết candidate hợp lệ; hết
capacity; transaction/lock mơ hồ; publisher fatal; cần force/reset.

## Verify (gates theo scope)

- Loop VERIFY = workflow green + Pages deploy + no lock/txn + queue
  report (`reports/factory/factory-queue-last-run.json`) không fatal
  của đúng SHA vừa merge.
- Change engine/workflow/recovery → full regression + 4-tier trước khi
  coi là đã fix; KHÔNG tuyên bố fixed chỉ vì unit test xanh.
