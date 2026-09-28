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
| `verify` | validate + capacity-audit + queue + tests theo mức | `--scope fast\|deep\|full` (mặc định full); fast = validate chunk + test gate/operator/refill-safety; deep thêm test link integrity + qa modes |
| `refill` | chỉ khi dưới ngưỡng, chạy refill-queue.py | lazy capacity 10K |
| `reports` | sinh reports/factory chuẩn | generate-reports.py |
| `release-chunk` | trả chunk WRITING chưa có draft về PLANNED | pause an toàn; hàng có draft/QA evidence được giữ nguyên |

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

1. Preflight (mỗi run): checkout main → đọc lệnh → `operator.py status` →
   `recover` TRƯỚC (nếu transaction treo; ownership không rõ → STOP).
   KHÔNG chạy validate toàn site trước recover — khi transaction đang treo,
   validate FAIL sẽ chặn recover mãi (deadlock). Mỗi op mutating tự
   preflight `validate.py` theo scope của lệnh (mặc định chunk).
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
   checkpoint; sau đó sinh reports + `verify` theo scope của lệnh
   (lệnh sản xuất mặc định fast — xem QA modes bên dưới).
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

## Ghi nhận pilot 2026-09-27 (5 bài, không bật hourly)

- Chuỗi lệnh chạy đúng luồng: `prepare-next` (5) -> writer ngoài viết
  draft -> `qa` (5/5 PASS: quality/seo >= 90, business_fact PASS,
  legal NOT_REQUIRED) -> `publish` (5/5 qua publish-gate, QA evidence
  được gate đồng bộ `source_path` + `matrix_row_sha256` sau promote).
- Bài xuất bản: BLG-00486..BLG-00490 (C-THUE-GIA). Checkpoint:
  last_completed BLG-00490, next_claimable BLG-00491. Transaction
  active=false, writer-lock sạch, lệnh đã xóa sau xử lý.
- CƠ CHẾ HOURLY CHƯA BẬT: không cron, publish-queue.yml (legacy) vẫn
  disabled. Bật hourly chỉ sau quyết định riêng của chủ xe.



## Một coordinator duy nhất & vòng đời lệnh (chống lệnh chồng nhau)

- Tại một thời điểm CHỈ MỘT coordinator được đẩy lệnh sản xuất vào
  `data/factory/operator-command.json`. KHÔNG ghi đè file lệnh khi lệnh
  trước chưa được tiêu thụ (run trước chưa commit xóa lệnh).
- Trước khi dispatch lệnh mới: xác nhận run trước đã completed và ĐỌC LẠI
  `data/state/checkpoint.json` (next_claimable_id, in_progress_chunk) —
  không suy diễn từ bộ nhớ hội thoại.
- Trường hợp `command_id` (tùy chọn, dạng `[A-Za-z0-9._-]{1,64}`) và
  `coordinator` (tùy chọn): ghi vào lệnh để truy vết; commit output mang
  theo command_id khi có.
- Workflow chỉ serialized theo concurrency group; nếu vẫn có lệnh mới đến
  giữa run, rebase CHỈ hòa giải conflict duy nhất trên chính file lệnh
  (giữ lệnh mới của origin để run của nó tiêu thụ); conflict file khác
  vẫn STOP, KHÔNG force push. Push chỉ fast-forward, rebase xong phải
  verify lại trên trạng thái đã rebase.

## QA modes — FAST / DEEP / FULL (sản xuất thủ công, không tự lặp)

Factory KHÔNG tự điều phối: không self-dispatch, không vòng lặp Actions
chạy tiếp, không scheduling. Người vận hành (chủ xe hoặc agent theo lệnh
tay "CONTINUE BLOG") tự quyết định khi nào chạy mức nào.

Lệnh chuẩn:

    python3 scripts/factory/qa.py --mode fast [--ids BLG-xxx,...]
    python3 scripts/factory/qa.py --mode deep
    python3 scripts/factory/qa.py --mode full

Tương đương qua operator: `{"op":"qa","ids":"...","scope":"fast"}` và
`python3 scripts/factory/validate.py --scope chunk|batch|full`.

### FAST (mặc định — QA sản xuất mỗi chunk 10 bài)

Mặc định FAST áp dụng NHẤT QUÁN cho lệnh sản xuất `prepare-next` / `qa` /
`publish` ở CẢ preflight lẫn verify cuối run của factory-operator.yml:
lệnh không chỉ định `scope` thì workflow tự đặt `scope=fast`. Chỉ khi
người vận hành chỉ định rõ `deep`/`full` trong lệnh thì mới chạy mức đó.
Op `verify` đứng riêng vẫn mặc định full. FULL giữ cho thay đổi
engine/workflow và kiểm tra cuối đợt sửa.

- QA deterministic TỪNG BÀI của chunk hiện tại: cấu trúc, frontmatter,
  H1/H2, title, meta description, canonical/permalink, taxonomy, link
  nội bộ (route thật + baseurl /blog), business facts (whitelist số tiền,
  claims cấm, phone), cannibalization, legal/source gate khi bắt buộc,
  quality/SEO theo rubric — KHÔNG đổi gì so với trước.
- validate.py `--scope chunk`: nền bắt buộc (taxonomy, state, cấu trúc
  matrix, đếm trạng thái) + bằng chứng QA của các bài trong chunk.
- KHÔNG làm sau mỗi 10 bài: quét 483 bài legacy, sitemap live (mạng),
  hash QA của MỌI bài PUBLISHED, crawl toàn site, graph cannibalization
  toàn matrix. Phát hiện dấu hiệu hệ thống ở fast -> nâng lên deep/full,
  KHÔNG hạ ngưỡng.
- Ngưỡng giữ nguyên: quality >= 90, seo >= 90, business_fact/legal
  PASS-FAIL, critical_failure = false.

### DEEP (thủ công, ~mỗi 50 bài)

Mọi thứ của fast + validate.py `--scope batch`: URL legacy, khớp
matrix-inventory, hash QA toàn bộ PUBLISHED, hub pages + test link
integrity. Không sitemap live.

### FULL (thủ công, định kỳ / final verification)

validate.py `--scope full`: toàn repository kèm đối chiếu sitemap
live + capacity-audit + toàn bộ test. KHÔNG phải điều kiện xuất bản
mỗi chunk.

### Pause an toàn (release-chunk)

    {"op":"release-chunk"}  hoặc  --ids BLG-xxx,...

Trả các hàng WRITING/QA/REPAIR/PASS CHƯA CÓ draft về PLANNED, xóa
in_progress_chunk, trả next_claimable_id về ID thấp nhất được nhả.
Hàng đã có draft hoặc bằng chứng QA được GIỮ NGUYÊN (không vứt việc
thật). PUBLISHED/EXISTING/REVIEW/BLOCKED luôn được bảo vệ.
