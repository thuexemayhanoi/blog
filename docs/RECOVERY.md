# RECOVERY — phục hồi sự cố

## Chạy mới bắt đầu bằng

1. `git fetch` HEAD mới nhất; đọc AGENTS.md, README.md (writer: docs/AI-WRITER-QUICKSTART.md).
2. Đọc trạng thái theo thứ tự: `data/state/transaction.json` → `data/state/checkpoint.json` → `data/state/writer-lock.json` → `reports/factory/progress.json`.

## Transaction treo (`active: true`)

- Đọc `pending`: nêu rõ bước đang dở (VD: "đã push bài, chưa cập nhật matrix").
- Đối chiếu repository thật: bài đã tồn tại trên main chưa? Matrix đã cập nhật chưa?
- Hoàn tất đúng theo sự thật: nếu bài đã push mà matrix chưa cập nhật → cập nhật matrix/report/checkpoint rồi đóng transaction. Nếu chưa push gì → hủy transaction, trả hàng về PLANNED.
- Không bao giờ nhận chunk mới khi còn transaction treo.

## Lock treo (`locked: true` nhưng chủ không hoạt động)

Lock dùng sentinel `data/state/writer-lock.active` (O_CREAT|O_EXCL) + ownership token UUID (xem docs/ENGINE-RUNBOOK.md). Không bao giờ force-unlock ownership không rõ ràng.

Liveness watchdog phân loại MỌI lock đang giữ quá ngưỡng là `STALE_LOCK`
(exit 1) — kể cả lock mồ côi với 0 việc dở — vì factory-operator preflight
coi lock đang giữ là held và chặn mọi mutation. Watchdog READ-ONLY: không
tự xoá, không force-unlock; mọi dọn dẹp phải qua operator chuẩn bên dưới.

- Nếu có chủ lock rõ ràng (holder, token, started_at): liên hệ chủ lock trước; chỉ can thiệp khi `expires_at` đã quá hạn, chủ không còn commit/hoạt động, và có bằng chứng.
- Ghi đè lock chỉ khi sentinel không tồn tại nhưng `writer-lock.json` còn `locked: true` mồ côi (crash giữa acquire): đặt metadata về unlocked nhất quán, ghi rõ lý do + thời điểm vào `note`.
- Không xóa sentinel còn sống của writer khác; không gọi release với token không phải của mình (release là no-op an toàn khi token lệch).

## Chunk dở

- Dùng checkpoint `last_completed_article_id` + ma trận: các hàng `WRITING`/`QA` trong chunk → hoàn tất trước khi nhận chunk mới.

## Conflict Git / push bị từ chối

- Fetch lại, rebase phần việc của mình; nếu xung đột với matrix/state → lấy phiên bản remote làm chuẩn, việc mình đang làm đối chiếu lại theo ID. Không force push.

## Sai số ma trận

Chạy `python3 scripts/factory/validate.py` (từ gốc repository). Nếu ma trận thiếu/hỏng: KHÔNG tự sinh lại toàn bộ; khôi phục từ lịch sử git commit gần nhất còn hợp lệ. Ma trận đã được commit và có chủ sở hữu: mọi chỉnh sửa theo hợp đồng trong docs/factory-workflow-contract.md; nếu ma trận từng được đánh dấu BLOCKED, xem `reports/factory/matrix-recovery-blocked.md` và không tự tạo matrix mới rồi gọi là khôi phục.

## Checkpoint lệch matrix (sự cố BLG-01364, 2026-10-05)

Triệu chứng: `validate.py` FAIL với `checkpoint planned lệch matrix` —
số đếm trong `data/state/checkpoint.json` không khớp
`data/content-matrix.csv` (thường do push state dở dang: checkpoint lên
kịp mà matrix/seed chưa, hoặc ngược lại sau refill bị ngắt giữa chừng).

- KHÔNG BAO GIỜ sửa tay `counts` hay `next_claimable_id` trong
  `data/state/checkpoint.json` — mọi con số phải là output của tooling.
- KHÔNG reset checkpoint, KHÔNG đè theo ghi nhớ phiên trước.
- Cách sửa DUY NHẤT (canonical):
  `python3 scripts/factory/factory-operator.py repair-checkpoint`
  — op tái sinh toàn bộ `counts` + `next_claimable_id` từ sự thật
  matrix, chỉ chạy khi transaction inactive + lock sạch, KHÔNG đụng
  matrix/seed/ledger hay khoá khác của checkpoint, in rõ diff từng key
  vào log CI, và hậu kiểm validate PASS rồi mới trả SUCCESS. Op
  idempotent: chạy lại không đổi gì thêm.
- Sau repair: `validate.py --scope chunk` phải PASS, rồi mới tiếp tục
  refill/publish. Hợp đồng đầy đủ + kiểm thử hồi quy:
  `scripts/factory/tests/test_refill_drift.py`.


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


## Registry lease (writer-claims.json) — đa-writer

Mỗi session giữ tối đa một slot sống, kể cả khi gọi `writer-claim.py` trực tiếp
hoặc adopt lease legacy qua heartbeat. `SESSION_HOLDS_OTHER_SLOT` → resume
đúng slot hiện có; chỉ đổi slot sau release. `REGISTRY_CONFLICT` (ID/session
trùng giữa lease sống) → fail-closed, selector không publish, claim/heartbeat/
release không ghi gì. Không rollback về git history để tự chọn chủ và không
dùng timestamp từ registry ngoài để thay lease đang sống. Chờ TTL hoặc
coordinator hòa giải với bằng chứng; không tự reset/force/overwrite lease.
Registry sai cấu trúc (khóa slot ngoài W1..W3, lease sống > 10 ID, `epoch`/`ttl_hours`/`label` sai kiểu,
byte không phải UTF-8) là `REGISTRY_CORRUPT`, không phải conflict (nhưng nếu cùng lúc còn tranh chấp chủ sống thì `REGISTRY_CONFLICT` thắng, không rollback): `writer-session.py repair-registry`
(hoặc `writer-claim.py repair-registry --from-git`) khôi phục bản hợp lệ gần nhất và không lệnh nào
ghi đè lease sống trước đó. Một ID lặp TRONG CHÍNH một lease (`ids: [A, A]`) chỉ có một chủ nên KHÔNG phải
`REGISTRY_CONFLICT`: `check-registry` báo `ID lap`, `writer-claim.py prune` (và
mọi claim/heartbeat) tự bỏ bản lặp, giữ chủ và thứ tự. Release một phần lease
legacy cũng là nhận lease nên chịu cùng guard "một phiên một slot"
(`SESSION_HOLDS_OTHER_SLOT`, registry không đổi).

Evidence QA cũ lệch hash: chỉ audit theo `docs/LEGACY-QA-RE-ATTESTATION-PLAN.md`.
Không coi recovery registry hay domain migration là quyền re-attest bài cũ.

- Xem: `python3 scripts/factory/writer-claim.py show` / `status` (đọc, không ghi). Kiểm bất biến: `check-registry`.
- `REGISTRY_CORRUPT` (JSON hỏng/sai cấu trúc, `expires_at` không phân tích được, ID sai dạng): mọi tool và selector fail-closed, KHÔNG coi
  là rỗng. Phục hồi trên origin: `python3 scripts/factory/writer-session.py repair-registry` (CAS: lấy bản hợp lệ gần nhất trong git
  history, prune theo matrix hiện tại, commit thay file hỏng; không tạo lease mới, không force push; registry đang hợp lệ thì không làm
  gì). Chỉ sửa working copy: `writer-claim.py repair-registry --from-git` rồi tự commit/push fast-forward.
- `REGISTRY_CONFLICT` (registry đọc được nhưng một ID ở ≥ 2 lease sống, hoặc một phiên giữ ≥ 2 slot sống): MỌI công cụ (`writer-claim.py`, `writer-session.py`, `validate.py`, `writer-loop.py status`, selector) báo đúng mã này kèm `problems`, không ghi gì. KHÔNG chạy `repair-registry` / rollback git (sẽ làm mất lease sống; `repair-registry` cũng từ chối). Lối ra: chờ một trong các lease hết `expires_at`, hoặc coordinator hóa giải bằng chứng rồi CAS-commit registry đã sửa. `writer-claim.py merge`: lease v1 + bản đã nhận của cùng slot là cùng chủ (không xung đột).
- Writer chết giữ slot: KHÔNG chiếm lease còn hạn. Chờ `expires_at` (mặc định 12h với `writer-session.py begin`, 48h với claim cũ);
  ID PLANNED tự trả về pool, hàng in-flight (REPAIR/PASS…) thành orphan: `begin --ids BLG-… --adopt`.
- Hai phiên cùng một slot (SLOT_HELD): phiên đến sau dùng slot khác; không sửa tay registry để "giành" slot.
- Hàng REPAIR của writer đã chết KHÔNG chặn publisher (resume-first là per-writer). Muốn giải phóng sớm: chủ xe/coordinator cho
  một slot `--adopt` rồi sửa draft; hoặc `requeue --ids` (op local, tôn trọng budget).
- Run đỏ `upstream_overlap` (publisher-push.py): bình thường — writer sửa draft đúng lúc publisher chốt; main không đổi, run kế
  drain lại và QA nội dung mới. Không can thiệp.
