# Continuous Writer Contract — hợp đồng vòng lặp của external writer (/blog)

Tài liệu canonical cho cách writer (AI bên ngoài, BẤT KỲ nhà cung cấp nào) hoạt động ở chế độ continuous
đa-writer (tối đa 3 slot W1/W2/W3). Bản một trang: `docs/AI-WRITER-QUICKSTART.md`; kiến trúc và bất biến:
`docs/MULTI-WRITER-ARCHITECTURE.md`; công cụ: `scripts/factory/writer-session.py`.

## Mô hình canonical (turbo write-ahead queue + drain)

- Đơn vị QA/publish của factory = PAIR 2 bài. Một push xếp hàng 1..10 draft `_drafts/`;
  `factory-publish.yml` (publisher production DUY NHẤT, concurrency 1) tiêu thụ từng pair qua
  `scripts/factory/factory-queue.py`: claim (prepare-next, chỉ hàng PLANNED) → scoped QA fast (ngưỡng KHÔNG hạ:
  quality ≥ 75, SEO ≥ 70) → publish transactional (chỉ hàng PASS, canonical publish-gate.py) → checkpoint → pair kế.
  Mỗi run còn **drain** mọi draft đang xếp hàng (`push-selection.py --backlog`, tối đa 30 ID): run bị GitHub hủy
  không làm mất draft.
- Push = TỐI ĐA 10 draft một lần (hard invariant của push; vượt → selector refuse). Queue lẻ hợp lệ.
- MULTI-WRITER: tối đa 3 slot, mỗi slot MỘT phiên (session), mỗi ID một chủ, lease ≤10 ID/slot, TTL có heartbeat,
  registry `data/state/writer-claims.json` do `writer-claim.py`/`writer-session.py` quản lý (CAS, không force push).
- Writer KHÔNG PHẢI publisher: writer chỉ ghi draft của ID mình giữ (+ registry qua tool + batch refill). Mọi mutation
  production state (matrix, checkpoint, `_posts`, `data/qa`) thuộc factory-publish.yml.
- GitHub Actions KHÔNG viết prose, KHÔNG gọi AI/API/host ngoài GitHub, KHÔNG secrets, KHÔNG schedule writer.

## Writer identity (ownership enforcement)

- Registry TỒN TẠI = multi-writer mode ON (vắng = single-writer legacy; HỎNG = refuse fail-closed).
- Draft của hàng PLANNED PHẢI khai (dòng TRẦN, không comment cuối dòng) trong frontmatter:

```yaml
writer: W1             # W1 | W2 | W3 — đúng writer đang giữ lease của ID đó
writer_session: s-abc  # session của lease (writer-session.py check tự gắn)
```

- Selector REFUSE fail-closed exit 3 (draft của push) khi: ID PLANNED không có lease sống; sai/khuyết `writer:`;
  `writer_session:` có khai nhưng lệch session của lease; hàng in-flight đã đổi nội dung mà lease sống thuộc writer khác.
  Draft trong backlog (không thuộc push) hỏng thì bị CÁCH LY, không chặn draft khác.

## LOOP (mỗi writer)

```
begin (nhận/gia hạn slot + lease, nối việc dở; REPAIR của mình trước)
→ WRITE draft thật theo matrix + docs/ARTICLE-RULES.md (≤10, không bài đệm)
→ check (gắn identity, QA cục bộ cùng scorer: quality ≥ 75, SEO ≥ 70, không critical)
→ push (một commit CAS; chỉ draft QA PASS của ID mình giữ)
→ confirm (PUBLISHED | REPAIR + failed_checks | PENDING + nudge)
→ begin batch kế (KHÔNG dừng sau mỗi batch)
```

## Không được dừng vì

Một pair vừa publish, một workflow vừa xanh, một Pages deploy vừa xong, test vừa xanh: đó là checkpoint, không phải điểm kết thúc.

## Chỉ được dừng khi

1. Không còn hàng PLANNED claimable và refill không còn candidate hợp lệ, hoặc
2. runtime/session/quota buộc dừng — dừng ở điểm an toàn: đã `push` phần xong, lease để hết hạn hoặc `release`,
   không bỏ draft dở trong working copy không ai biết (ghi lại slot + session id để bàn giao), hoặc
3. blocker thật cần con người (lock của operator khác, txn mơ hồ, validation failure critical, FATAL hạ tầng lặp lại).

## Bất biến an toàn mỗi vòng

- Tối đa 3 slot; KHÔNG BAO GIỜ viết ID do writer khác giữ lease sống (selector refuse, engine fail-closed).
- KHÔNG force push; push bị từ chối → `writer-session.py` làm lại từ fetch (không rebase commit cũ).
- Mỗi pair là transaction riêng; pair FAIL không rollback pair đã publish; FAIL nội dung là RECOVERABLE
  (hàng REPAIR chờ chủ sửa, KHÔNG chặn writer khác); FAIL hạ tầng dừng queue run (draft còn xếp hàng, run kế drain lại).
- MATRIX là source of truth; checkpoint là derived state.

## Refill (coordinator)

Phát hiện: `python3 scripts/factory/queue.py --needs-refill` (claimable PLANNED < `min_ready_queue`=100). Gate G1–G8 của
`refill-queue.py` (child capacity, keyword/intent/title/slug duy nhất, word_target, candidate_id, taxonomy). Quy trình:

1. FETCH main; xác nhận transaction inactive, lock free, không Factory Publish đang chạy.
2. Chuẩn bị batch topic THẬT (không filler) tại `data/factory/refill-batches/<date>-<tag>.json`; kiểm tra trùng + route link thật
   cục bộ (`stage-refill-batch.py` trên bản sao).
3. Push batch + bump `data/factory/refill-request.json` → `factory-refill.yml` tự stage (G1–G8) và CHỈ materialize khi PLANNED
   claim được < `min_ready_queue` (nếu không: batch ở STAGED, run xanh, không lỗi) → commit đồng bộ ledger/seed/matrix/checkpoint/reports.
4. Run FAIL/NEEDS_TOPIC_EXPANSION: sửa/mở rộng topic thật; KHÔNG hạ gate, KHÔNG sửa tay `data/state/*`, `checkpoint lệch` → `repair-checkpoint`.
5. Sau refill xanh: FETCH main rồi `begin` lấy ID mới.

Chỉ dừng khi: G1–G8 FAIL thật, hết candidate hợp lệ, hết capacity, transaction/lock mơ hồ, publisher fatal lặp lại.

## Verify

`confirm` PUBLISHED + Factory Publish xanh + Pages deploy SUCCESS + URL live 200. Change engine/workflow/recovery → full regression + 4-tier
(`factory-operator.py verify --scope full`) trước khi coi là đã fix; KHÔNG tuyên bố fixed chỉ vì unit test xanh.
