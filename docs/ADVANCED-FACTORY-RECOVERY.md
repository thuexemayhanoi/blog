# ADVANCED FACTORY RECOVERY — kỹ thuật sâu của engine /blog

Nơi hội tụ kỹ thuật đã dời khỏi AGENTS.md/PROC-PUBLISH.md sau hợp đồng 4
workflow (2026-09-30). KHÔNG cần đọc để sản xuất hàng ngày — chỉ cần khi
gỡ sự cố engine hoặc đổi workflow. Quy trình sự cố từng bước:
docs/RECOVERY.md. Vận hành module: docs/ENGINE-RUNBOOK.md.

## 1. Writer-lock (chống hai writer song song)

- Sentinel `data/state/writer-lock.active` tạo bằng O_CREAT|O_EXCL — atom
  ngay cả trên filesystem không đồng bộ.
- Mỗi lần acquire sinh ownership token UUID: sentinel chứa token,
  `writer-lock.json` lưu cùng token. Release chỉ thỏa khi token khớp.
- KHÔNG force-unlock lock của chủ khác/không rõ ownership. Mức override
  duy nhất: docs/RECOVERY.md mục lock treo, có bằng chứng quá hạn.
- Lock mồ côi (stale, kể cả 0 việc dở) là STALE_LOCK — watchdog báo,
  factory-operator preflight coi là held và chặn mutation tới khi dọn.

## 2. Transaction + checkpoint

- Mọi op mutating chạy trong transaction chuẩn: mở → mutate → hậu kiểm
  (reports + validate `--expect-txn-phase`) → CHỈ đóng sau hậu kiểm PASS
  (fail-closed). Crash giữa chừng → transaction treo, lần sau `recover`
  (action=resume) hòa giải theo đúng phase, KHÔNG suy luận trạng thái
  vật lý không đọc được → STOP.
- Checkpoint (`data/state/checkpoint.json`) là con trỏ sự thật:
  `next_claimable_id`, `in_progress_chunk`, `last_completed_article_id`.
  KHÔNG reset, KHÔNG nâng `updated_at` khi chỉ sinh reports.

## 3. SHA evidence (bằng chứng gắn nội dung)

- `content_sha256` (SHA-256 của draft tại lúc QA) và `matrix_row_sha256`
  (vân tay hàng matrix) được ghi vào `data/qa/<ID>.json`.
- publish-gate từ chối promote khi: hash nội dung lệch
  (STALE_QA_EVIDENCE — QA chấm phải nội dung khác), vân tay hàng lệch
  (MATRIX_ROW_MISMATCH — hàng bị đổi sau QA). Không có đường vòng.

## 4. Bảo vệ xuất bản (publish-gate.py — cổng duy nhất vào _posts/)

Hàng phải PASS; quality >= 75, seo >= 70 (90+ cả hai chỉ ghi nhãn
EXCELLENT — 75-89 là PASS hợp lệ, không cảnh báo band); business_fact
PASS; legal PASS|NOT_REQUIRED; không critical failure; không trùng
ID/slug/canonical/intent gần trùng; bài đã PUBLISHED không bao giờ bị
ghi đè. Gate tự giữ lock, mở transaction, promote, append history, nhả
lock.

## 5. Hợp đồng kiểm tra 4 tầng

1. Unit — suite theo module (watchdog, operator, publish gate).
2. Integration — hardening/qa-modes/publish-flow trên fixture hermetic
   (fresh_copy trong tmp, không đụng repo thật).
3. Production invariant — validate.py (chunk/batch/full) + quality-gate
   CI + Pages deploy.
4. Long-run/failure recovery — test_soak_recovery.py (20 vòng hermetic +
   failure injection), chạy trong `factory-operator.py verify --scope full`
   (factory-publish-verify.yml — theo yêu cầu; liveness 6h ở factory-liveness.yml).

FULL mạnh hơn DEEP, DEEP mạnh hơn FAST; KHÔNG hạ ngưỡng khi đổi mức.

## 6. Push safety (factory-publish.yml)

- Commit chỉ chứa output deterministic (một commit `[automated txn]` mỗi
  queue run); push fast-forward.
- Origin đổi giữa chừng (non-FF): fetch → rebase rồi push lại — bounded
  retry, tối đa 3 lần thử push; KHÔNG bao giờ force push.
- Rebase conflict → `git rebase --abort` + exit 1 ngay (KHÔNG force push,
  KHÔNG replay); state đã commit ở lại cho lần chạy sau resume từ
  repository truth. Không còn cơ chế hòa giải file lệnh (file lệnh
  operator-command.json đã retire cùng mô hình cũ).
- Bằng chứng cuối run: FINAL_PUSHED_HEAD / ORIGIN_HEAD_AFTER in ra log —
  báo cáo phải phân biệt HEAD đã chạy workflow nào.

## 7. Năng lực 10K

- Matrix 10.000 hàng = 483 legacy + 9.517 child theo taxonomy
  (capacity-audit.py kiểm). Queue là view trên matrix; refill là cách
  DUY NHẤT materialize candidate STAGED → PLANNED (refill-queue.py, gate
  G1-G8, semantic SUCCESS bắt buộc tạo work thật).
- Refill khi cần (lazy): op bảo trì local
  `python3 scripts/factory/factory-operator.py refill` (KHÔNG chạy trong
  đường nóng publish). Kiểm tra sức chứa/đúng đắn khi cần:
  factory-publish-verify.yml (refill --verify, --selftest,
  sitemap-plan.py).
- Không tự mở rộng topic khi hết candidate STAGED: op refill trả
  NEEDS_TOPIC_EXPANSION — mở rộng topic thật qua gate rồi mới refill.
