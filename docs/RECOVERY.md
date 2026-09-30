# RECOVERY — phục hồi sự cố

## Chạy mới bắt đầu bằng

1. `git fetch` HEAD mới nhất; đọc README.md, docs/mistral/README.md.
2. Đọc trạng thái theo thứ tự: `data/state/transaction.json` → `data/state/checkpoint.json` → `data/state/writer-lock.json` → `reports/factory/progress.json`.

## Transaction treo (`active: true`)

- Đọc `pending`: nêu rõ bước đang dở (VD: "đã push bài, chưa cập nhật matrix").
- Đối chiếu repository thật: bài đã tồn tại trên main chưa? Matrix đã cập nhật chưa?
- Hoàn tất đúng theo sự thật: nếu bài đã push mà matrix chưa cập nhật → cập nhật matrix/report/checkpoint rồi đóng transaction. Nếu chưa push gì → hủy transaction, trả hàng về PLANNED.
- Không bao giờ nhận chunk mới khi còn transaction treo.

## Lock treo (`locked: true` nhưng chủ không hoạt động)

Lock dùng sentinel `data/state/writer-lock.active` (O_CREAT|O_EXCL) + ownership token UUID (xem docs/ENGINE-RUNBOOK.md). Không bao giờ force-unlock ownership không rõ ràng.

- Nếu có chủ lock rõ ràng (holder, token, started_at): liên hệ chủ lock trước; chỉ can thiệp khi `expires_at` đã quá hạn, chủ không còn commit/hoạt động, và có bằng chứng.
- Ghi đè lock chỉ khi sentinel không tồn tại nhưng `writer-lock.json` còn `locked: true` mồ côi (crash giữa acquire): đặt metadata về unlocked nhất quán, ghi rõ lý do + thời điểm vào `note`.
- Không xóa sentinel còn sống của writer khác; không gọi release với token không phải của mình (release là no-op an toàn khi token lệch).

## Chunk dở

- Dùng checkpoint `last_completed_article_id` + ma trận: các hàng `WRITING`/`QA` trong chunk → hoàn tất trước khi nhận chunk mới.

## Conflict Git / push bị từ chối

- Fetch lại, rebase phần việc của mình; nếu xung đột với matrix/state → lấy phiên bản remote làm chuẩn, việc mình đang làm đối chiếu lại theo ID. Không force push.

## Sai số ma trận

Chạy `python3 scripts/factory/validate.py` (từ gốc repository). Nếu ma trận thiếu/hỏng: KHÔNG tự sinh lại toàn bộ; khôi phục từ lịch sử git commit gần nhất còn hợp lệ. Ma trận đã được commit và có chủ sở hữu: mọi chỉnh sửa theo hợp đồng trong docs/factory-workflow-contract.md; nếu ma trận từng được đánh dấu BLOCKED, xem `reports/factory/matrix-recovery-blocked.md` và không tự tạo matrix mới rồi gọi là khôi phục.

## Hợp đồng fail-closed của recover (phase RECOVERY_VERIFYING)

`factory-operator.py recover` là op FAIL-CLOSED — không bao giờ đóng
transaction trước khi hậu kiểm PASS:

1. Đọc transaction; lock đang giữ (ownership không rõ) → STOP rc=1.
2. Suy luận trạng thái vật lý: đích tồn tại → hoàn tất (hàng → PUBLISHED);
   draft còn → rollback (hàng PASS/QA/PUBLISHED → QA). Không suy luận được
   → STOP rc=1, KHÔNG mutate gì.
3. Hòa giải idempotent: chạy lại không mutate thêm (note guard `recover `,
   trạng thái đã đúng thì giữ nguyên).
4. MỞ phase `RECOVERY_VERIFYING` — transaction VẪN active (chưa đóng).
5. Hậu kiểm: `run_reports_checked` (reports bắt buộc) + `validate.py
   --scope chunk --expect-txn-phase RECOVERY_VERIFYING` (hợp đồng chặt:
   active=true VÀ phase khớp; inactive/mismatch đều FAIL).
6. CHỈ khi hậu kiểm PASS mới đóng transaction (history ghi
   `RECOVERED_COMPLETED`/`RECOVERED_ROLLED_BACK`).

Hậu kiểm FAIL → rc=1, transaction GIỮ NGUYÊN active + phase
`RECOVERY_VERIFYING`; lần chạy sau chạy `recover` lại (idempotent), KHÔNG
nhận việc mới khi còn transaction treo. Mọi op mutating khác chạy
preflight validate không có `--expect-txn-phase` nên tự động bị chặn khi
transaction còn treo — deadlock là chủ đích cho tới khi recover xanh.

## Hợp đồng resume (tiếp tục một factory duy nhất)

Mọi lần chạy — dù bởi agent hay scheduler trong tương lai — đều chỉ là một lần tiếp tục của MỘT factory tồn tại dai dẳng. Không khởi động lại từ đầu.

Nếu lỗi xảy ra tại bài thứ N (ví dụ bài 2.437): không quay lại bài 1. Thứ tự xử lý lỗi:

```
RECOVER -> RESUME -> REPAIR -> VERIFY -> NEW WORK
```

- Phục hồi transaction/lock an toàn theo các mục trên.
- Đọc checkpoint, resume đúng item/chunk dang dở.
- Không bỏ qua transaction hỏng để giữ throughput; không nhận chunk mới khi còn transaction treo.

## Bài đã push nhưng Pages build lỗi

- Không tạo commit README-only. Sửa đúng tệp nguồn gây lỗi (frontmatter, Liquid, permalink) và push lại; xác nhận build/deploy thật.

## Báo cáo sau khi phục hồi

Ghi vào `reports/factory/latest.md`: nguyên nhân, hành động, HEAD mới, trạng thái build/deploy, các kiểm tra runtime đã làm.
