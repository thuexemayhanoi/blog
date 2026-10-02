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
→ FETCH FRESH MAIN
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
- Refill: operator-only (`scripts/factory/refill-queue.py --dry-run`/
  `--refill --yes` KHÔNG tự chạy trong loop; writer chỉ đọc trạng thái
  read-only `scripts/factory/queue.py --needs-refill`).

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
- Trong đợt migration này KHÔNG chạy refill thật.

## Verify (gates theo scope)

- Loop VERIFY = workflow green + Pages deploy + no lock/txn + queue
  report (`reports/factory/factory-queue-last-run.json`) không fatal
  của đúng SHA vừa merge.
- Change engine/workflow/recovery → full regression + 4-tier trước khi
  coi là đã fix; KHÔNG tuyên bố fixed chỉ vì unit test xanh.
