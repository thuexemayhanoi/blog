# PROC-PUBLISH — Vòng viết & xuất bản qua Factory Operator

Mục tiêu: xuất bản một chunk 3–5 bài (tối đa 10) qua đúng engine chuẩn của
/blog, KHÔNG để lộ bản nháp, KHÔNG AI trong Actions.

## Mô hình vận hành (bắt buộc hiểu đúng)

```
EXTERNAL AI (writer/coordinator)      ← viết prose, điều phối
   |  chỉ cần GitHub read/write, KHÔNG cần git/Python/Node
   v
data/factory/operator-command.json    ← KÊNH LỆNH (whitelist op duy nhất)
   v
GitHub Actions factory-operator.yml   ← MÔI TRƯỜNG THỰC THI
   |  checkout + Python + Node + tooling chuẩn
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
- Legacy `publish-queue.yml` giữ disabled — KHÔNG phải scheduler của
  factory và KHÔNG được bật song song.

## Ops whitelist (định nghĩa trong factory-operator.py)

| Op | Ý nghĩa | Ghi chú |
|---|---|---|
| `status` | in trạng thái engine (read-only) | checkpoint/txn/lock/matrix |
| `prepare-next` | claim N hàng PLANNED → WRITING + manifest | N mặc định 5, tối đa 10 |
| `qa` | QA deterministic cho hàng WRITING/QA/REPAIR | ghi evidence `data/qa/<ID>.json` |
| `publish` | promote HÀNG PASS qua publish-gate.py | KHÔNG cơ chế promote thứ hai |
| `recover` | phục hồi transaction treo | ownership không rõ → STOP |
| `requeue` | REPAIR/FAIL → WRITING | tôn trọng budget repair (3) |
| `verify` | validate + capacity-audit + queue + tests | không mutate |
| `refill` | chỉ khi dưới ngưỡng, chạy refill-queue.py | lazy capacity 10K |
| `reports` | sinh reports/factory chuẩn | generate-reports.py |

Mọi op khác bị từ chối. KHÔNG bao giờ chạy shell tùy ý từ JSON.

Lệnh đẩy dạng: push file `data/factory/operator-command.json`
`{"op":"prepare-next","count":5}` — workflow trigger theo `paths` của đúng
file này, xử lý xong TỰ XÓA file lệnh trong cùng commit output.

## Manifest writer (export bởi prepare-next)

Path: `reports/factory/rows/<BLG-ID>.json`. Writer ngoài đọc manifest này
và viết draft đúng `draft_path`. Manifest chứa: title/intent/keyword,
URL/canonical/permalink, taxonomy + hub, business facts (chỉ nguồn
`data/business-facts.json`), source_required/legal_risk/research_class
(A/B/C theo `docs/SOURCE-RESEARCH.md`), ứng viên liên kết nội bộ (theo
`docs/INTERNAL-LINKING.md`), ngưỡng QA, vân tay hàng matrix
(`matrix_row_sha256`).

## Quy trình một chunk

1. Preflight (mỗi run): checkout main → đọc lệnh → `validate.py` →
   `operator.py status` → `recover` (nếu transaction treo; ownership không
   rõ → STOP).
2. `prepare-next` (count=5): engine từ chối nếu còn hàng WRITING/QA/
   REPAIR/PASS chưa xong; claim đúng từ `checkpoint.next_claimable_id`;
   chỉ nhận PLANNED; REVIEW/BLOCKED luôn được bảo vệ.
3. Writer ngoài viết 5 draft vào `_drafts/` (KHÔNG `_posts/`), tuân theo
   `docs/ARTICLE-RULES.md`, `docs/SOURCE-RESEARCH.md`,
   `docs/INTERNAL-LINKING.md`, `docs/QUALITY-RUBRIC.md`, rồi push draft.
4. Push lệnh `{"op":"qa","ids":"..."}`: QA deterministic chấm từng draft
   (cấu trúc, SEO on-page, link nội bộ, business facts, cannibalization,
   legal/source), ghi evidence SHA gắn với nội dung + hàng matrix. PASS
   thì hàng thành PASS; thiếu điểm → REPAIR (writer sửa rồi qa lại);
   hết budget repair → BLOCKED. QA không bao giờ tự hạ ngưỡng.
5. Repair (nếu cần): writer chỉ sửa draft dính lỗi, push, chạy `qa` lại.
6. Push lệnh `{"op":"publish","ids":"..."}`: từng hàng PASS qua
   `publish-gate.py` (lock + hash + transaction chuẩn) promote
   `_drafts/` → `_posts/`, chốt ngày thật vào URL, cập nhật matrix +
   checkpoint; sau đó sinh reports + `verify`.
7. Chờ CI xanh trên đúng HEAD (Factory validate + Factory capacity
   validate + Pages) và kiểm tra live URL 200 + sitemap.

## Bằng chứng PASS khi xuất bản (publish-gate kiểm tra, không tự khai)

`quality >= 90`, `seo >= 90`, `business_fact = PASS`,
`legal = PASS | NOT_REQUIRED`, `critical_failure = false`,
`content_sha256` khớp draft hiện tại, `matrix_row_sha256` khớp hàng
matrix hiện tại. Hàng phải đang PASS. Mọi lệch hash → từ chối
(STALE_QA_EVIDENCE / MATRIX_ROW_MISMATCH).

## Chính sách lỗi

- Op nào FAIL → workflow DỪNG, KHÔNG claim hàng mới; phần việc đã xong
  an toàn được giữ. Ghi lại: ID lỗi, op lỗi, HEAD, checkpoint,
  transaction, lock, các ID chưa xong, lệnh resume chính xác.
- Lần chạy sau: `recover` → resume việc dở → verify → mới nhận việc mới.
  (Hợp đồng resume: `docs/RECOVERY.md`.)
- KHÔNG force push; push chỉ fast-forward, conflict thì fetch/rebase
  bounded 5 lần, vẫn conflict → STOP.
