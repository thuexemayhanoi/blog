# Writer Loop — runbook MỘT writer ngoài chạy liên tục (single-writer)

Driver: `scripts/factory/writer-loop.py`. Mục tiêu: một writer ngoài
(agent AI có bash + python3 + GitHub push) đọc main, nối việc dang dở,
viết từng cặp 2 bài, QA scoped, push, xác nhận publish rồi lấy cặp
tiếp — mỗi bước MỘT lệnh, không mổ xẻ JSON tay. KHÔNG dựng thêm hệ
thống 3 writer; multi-writer tooling cũ giữ nguyên, driver này CHỈ dùng
writer W1.

## Bất biến

- Engine/QA KHÔNG bị đụng: driver KHÔNG sửa workflow, KHÔNG hạ gate
  (quality ≥ 75, SEO ≥ 70, business/legal sạch, không critical).
- MATRIX là source of truth; checkpoint là derived state.
- Writer KHÔNG PHẢI publisher: writer chỉ push draft `_drafts/` +
  registry `data/state/writer-claims.json` (path NGOÀI filter của
  factory-publish.yml nên registry một mình KHÔNG kích production run;
  draft `_drafts/` mới kích). Mọi promote sang `_posts/`, matrix
  WRITING/QA/PASS/PUBLISHED, checkpoint thuộc về factory-publish.yml.
- KHÔNG force push, KHÔNG PR; luôn fetch fresh main trước cycle mới.
- Registry self-heal: ID hết PLANNED (đã publish) tự bị prune khỏi
  lease ở lệnh claim/release kế tiếp.

## Vòng lặp chuẩn

```
# 0. Fetch fresh main về cây làm việc (writer chịu trách nhiệm fetch)
python3 scripts/factory/writer-loop.py status
    # → counts, claimable_planned, needs_refill, unfinished_ids,
    #   leases, next_pairs, head_checkpoint

# 1. Nối việc dang dở TRƯỚC khi claim mới:
#    - unfinished_ids không rỗng → viết/QA tiếp chính ID đó
#      (resume-first), KHÔNG bỏ qua.
#    - lease W1 đã có sẵn ID → dùng lease hiện tại, KHÔNG claim thêm
#      (MAX_LEASE 10 ID/writer; lease đầy thì claim sẽ tự FAIL).

# 2. Claim cặp mới (khi lease còn chỗ):
python3 scripts/factory/writer-loop.py next --writer W1 --count 2
    # → in title, slug, output_path, canonical, keywords, links,
    #   word_target đủ để viết draft. Draft filename:
    #   _drafts/{date}-{slug}.md (output_path đổi _posts→_drafts).

# 3. Viết 2 draft THẬT theo data/content-matrix.csv +
#    docs/ARTICLE-RULES.md + docs/SEO-CONTENT.md (frontmatter:
#    date, layout, title ĐÚNG matrix, description, categories,
#    lang, tags, permalink = canonical_url, parent_id, child_id,
#    article_id, writer: W1).

# 4. QA scoped (pre-check bằng CHÍNH scorer của engine, read-only,
#    KHÔNG ghi evidence, KHÔNG mutate matrix/checkpoint):
python3 scripts/factory/writer-loop.py qa --ids BLG-xxx,BLG-yyy
    # exit 0 + "WRITER_QA PASS" mới được push; FAIL → sửa draft rồi
    # chạy lại (fail-closed).

# 5. Push MỘT commit chứa: data/state/writer-claims.json (lease W1)
#    + 2 draft _drafts/. CI (validate + factory-publish) chạy trên
#    commit này; factory tiêu thụ từng pair.

# 6. Chờ Factory Publish PASS, fetch lại main về cây làm việc, rồi:
python3 scripts/factory/writer-loop.py verify --ids BLG-xxx,BLG-yyy
    # → hàng PUBLISHED + checkpoint nhích + transaction inactive +
    #   writer-lock free + queue report không fatal. Kèm runtime URL
    #   check từng bài (must 200).

# 7. Nhả lease cặp vừa xong rồi lấy cặp kế:
python3 scripts/factory/writer-loop.py release --writer W1 \
    --ids BLG-xxx,BLG-yyy
python3 scripts/factory/writer-loop.py next --writer W1 --count 2
    # → lặp từ bước 3. KHÔNG dừng sau mỗi pair.
```

## Refill (khi PLANNED thấp)

`status.needs_refill = true` (claimable PLANNED < min_ready_queue
100) → dùng tooling chuẩn, KHÔNG chỉ đổi số đếm:

1. Author batch topic THẬT theo `docs/TAXONOMY.md` + capacity
   child cluster (file batch như `data/planned/_refill-batch-*.json`).
2. Chống trùng local trước (norm title/keyword/intent vs matrix).
3. `scripts/factory/stage-refill-batch.py` — gate G1–G8 phải PASS.
4. `scripts/factory/refill-queue.py --refill --yes` →
   `generate-reports.py` → `validate.py` full PASS → push refill.
5. Mục tiêu ~300 claimable PLANNED, chia nhiều commit CI-green.

## Điểm dừng hợp lệ

- Pair fail content là RECOVERABLE: sửa draft đúng lỗi, push lại —
  không hạ QA, không đổi engine.
- Chỉ dừng khi: hết hàng PLANNED hợp lệ + refill hết capacity, có
  blocker thật ngoài quyền, hoặc runtime/session hết. Khi dừng: lưu
  checkpoint sạch (main đã push, lease còn sống hợp lệ, không lock,
  không txn dở) + lệnh tiếp tục rõ ràng. KHÔNG tuyên bố chạy nền khi
  không có runtime thật.

## Test

`python3 scripts/factory/tests/test_writer_loop.py` — status
read-only, qa fail-closed thiếu draft, verify PASS/FAIL đúng chiều,
next/release claim-nhã lease 2 ID đầu deterministic, không đụng
matrix/checkpoint.
