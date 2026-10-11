# MULTI-WRITER SEO FACTORY — kiến trúc, bất biến, phục hồi

Cập nhật: 2026-10-11 (audit + hardening đa-writer). Provider-neutral: slot `W1/W2/W3` do BẤT KỲ AI nào giữ.
Writer chỉ cần: git + Python 3 stdlib (`docs/AI-WRITER-QUICKSTART.md`). Actions: deterministic, KHÔNG API ngoài, KHÔNG AI, KHÔNG secret.

```
W1 ─┐  writer-session.py (CAS: fetch → tính lại → push, không force)
W2 ─┼─►  main ──► factory-publish.yml  (MỘT publisher, group factory-publish)
W3 ─┘        │       push-selection.py --backlog  (strict cho push, lenient cho backlog)
             │       factory-queue.py            (pair 2: in-flight trước, PLANNED sau; QA 75/70)
             │       publisher-push.py           (1 commit/run, guard giao-path, không force)
             └──►  Pages (built-in)
```

## 1. Trước / sau

| | Trước (audit 268e8e5) | Sau |
|---|---|---|
| Danh tính slot | chỉ là TÊN (`--writer W1`); hai phiên cùng tên dùng chung lease | slot gắn **session id**; phiên khác bị `SLOT_HELD`; hết hạn mới được chiếm (`epoch+1`) |
| Hạn lease | `mktime` theo múi giờ MÁY (±7h), `claimed_at` bị reset khi renew | UTC (`timegm`), `heartbeat_at/expires_at`, `claimed_at` giữ nguyên |
| Registry hỏng/vắng | hỏng ⇒ coi là rỗng; vắng ⇒ ownership TẮT | hỏng ⇒ **fail-closed**; `repair-registry --from-git`; ghi nguyên tử |
| Claim | writer tự viết git; registry nằm lẫn trong commit draft | `writer-session.py` CAS (plumbing, không đụng working tree) |
| Trigger | chỉ diff của push (HEAD~1) ⇒ run bị GitHub hủy làm mất draft | **drain**: mỗi run quét toàn bộ `_drafts/` trên main mới nhất |
| REPAIR | MỘT hàng REPAIR của writer chết ⇒ `prepare-next` bail ⇒ mọi push FATAL (deadlock) | REPAIR chờ chủ; không chặn ai; resume-first là **per-writer** (ở bước claim) |
| Pair hỗn hợp | `[PASS, REPAIR]` ⇒ cả pair recoverable, PASS kẹt | chỉ publish phần PASS; pair đồng nhất (in-flight trước) |
| Push publisher | `git rebase` ghép ÂM THẦM sửa đổi draft của writer vào bài vừa publish (đi vòng QA) | `publisher-push.py`: guard giao-path + sha256(bài) == `content_sha256` |
| Sở hữu draft | REPAIR không cần lease ⇒ writer khác sửa được | lease sống của writer khác ⇒ refuse; orphan (hết hạn) mà draft bị SỬA sau lần QA ⇒ phải nhận (`--adopt`) trước (refuse ở push, cách ly ở drain); ai nhận cũng được |
| Queue/run | 10 ID | 30 ID (3×10), pair vẫn 2 |

QA KHÔNG đổi: `quality ≥ 75`, `seo ≥ 70`, business_fact PASS, legal PASS/NOT_REQUIRED, không critical, hard gate trùng title/slug/intent, evidence `content_sha256` + `matrix_row_sha256`, publish-gate.

## 2. Vòng đời slot (state machine)

```
FREE ──begin──► HELD(session S, epoch e, expires_at) ──begin/push/heartbeat──► HELD (gia hạn)
HELD ──release --all──► FREE            HELD ──hết hạn──► EXPIRED ──begin(phiên khác)──► HELD(S', e+1)
```
- ID: `PLANNED` ──lease──► giữ trong lease; engine claim ⇒ `WRITING/QA/PASS/REPAIR` VẪN thuộc lease chủ; `PUBLISHED/EXISTING/BLOCKED` ⇒ prune.
- Lease hết hạn: ID PLANNED trả về pool; hàng in-flight thành **orphan** (nhận bằng `begin --ids … --adopt`). CÙNG phiên quay lại trước khi ai nhận slot thì nối lại ID + REPAIR của chính mình (`resumed_after_lapse`).
- Lease không còn ID (publish hết) bị prune ngay: slot KHÔNG đặt chỗ giữa hai batch (lease rỗng không bảo vệ ID nào mà khóa slot tới TTL nếu container bị tạo lại). Mỗi phiên chỉ giữ MỘT slot; lease legacy chỉ nhận bằng `begin --slot Wn`.
- Registry đọc lỗi KHÔNG phải "vắng": `GIT_READ_FAILED` (không ghi gì); timestamp/ID sai dạng ⇒ `REGISTRY_CORRUPT` (fail-closed; sửa: `writer-session.py repair-registry`).
- Phiên mặc định = NGẪU NHIÊN theo working copy (lưu trong `.git/`), KHÔNG suy từ danh tính git: nhiều AI cùng nhà cung cấp dùng chung một danh tính git, suy phiên từ đó sẽ gộp chúng thành MỘT phiên. Muốn một AI sống sót qua việc tạo lại container, hoặc bàn giao AI→AI: đặt `FACTORY_WRITER_SESSION=<token riêng>` (hoặc `--session <id>`); id là công khai, không bí mật, nhưng chỉ AI nào được trao nó mới nối được phiên đó.
- Tuyệt đối không chiếm lease còn hạn; vượt `MAX_WRITERS` ⇒ người đến sau thua (không đá lease cũ).

## 3. Bất biến và cách cưỡng chế

| Bất biến | Cưỡng chế | Bằng chứng test |
|---|---|---|
| ≤3 slot, ≤10 ID/slot, mỗi ID một chủ | `writer-claim.py` (`apply_claim`, `prune_registry`, `check_invariants`), `validate.py` | `test_writer_claim`, `test_writer_session` T01–T05 |
| Một slot — một phiên; một phiên — một slot | session id + `SLOT_HELD/NOT_OWNER/SESSION_HOLDS_OTHER_SLOT`, `check_invariants` | `test_writer_session` T03, T22, T26, T51 |
| Registry đọc lỗi không bị coi là rỗng | `Git.read` (ls-tree) ⇒ `GIT_READ_FAILED`; parse strict timestamp/ID | `test_writer_session` T50, T65 |
| Draft "độc" không làm kẹt run | `push-selection.py` `engine_problem` (UTF-8, `date`/title/categories/description, placeholder, tên file, MỘT file/ID) | `test_selector_drain` T40–T48, sim S12 |
| Registry mơ hồ chủ (một ID ở ≥ 2 lease sống) ⇒ fail-closed | `push-selection.py` `claim_registry` (`writer-claim.py live_conflicts`) | `test_selector_drain` T16, T16b |
| Hàng in-flight không bị đói khi backlog > 30 hoặc production paused | selector cắt trần SAU lọc paused, in-flight trước PLANNED | `test_selector_drain` T17, T18 |
| Orphan bị sửa phải được nhận trước | `ownership_problem` (`modified` so với bằng chứng QA) | `test_selector_drain` T13, T13b |
| Phiên quay lại slot của chính mình sau khi hết hạn | `writer-session.py pick_slot` (nối lại ID + REPAIR) | `test_writer_session` T55, T71 |
| Push hỏng không làm mất draft người khác | selector VẪN drain backlog khi push bị REFUSE; run đỏ ở step cuối | `test_selector_drain` T49–T50, sim S13 |
| Không mất bài khi run bị hủy | `push-selection.py --backlog` | `test_selector_drain` T01–T02, `test_multiwriter_sim` S1, S4 |
| Không deadlock vì REPAIR | `factory-operator.py prepare-next --ids` không chặn bởi hàng dở của writer khác | `test_factory_queue` 15b, `test_multiwriter_sim` S2 |
| Không lọt nội dung chưa QA | `publisher-push.py` (guard giao-path + integrity sha256) | `test_publisher_push` T03–T06, `test_multiwriter_sim` S6 |
| Bài PUBLISHED bất biến | selector `published_edits` (no-op xanh) | `test_selector_drain` T20, `test_multiwriter_sim` S5 |
| Không force push | origin `receive.denyNonFastForwards` trong sim; code không có `--force` (test tĩnh) | `test_hardening` S6, mọi sim |
| Một publisher ghi production | concurrency group `factory-publish` + engine lock O_EXCL + queue lock | `test_multiwriter_sim` (mô hình 1 chạy + 1 chờ) |
| Idempotent | re-run trigger cũ ⇒ no-op xanh; push lặp ⇒ không commit mới | `test_selector_drain` T20, `test_writer_session` T14, sim S7 |
| Fail-closed | registry hỏng, lock/txn treo, checkpoint lệch ⇒ run đỏ, không đổi gì | `test_selector_drain` T10, sim S8, S9 |

## 4. GitHub concurrency — vì sao cần drain

`concurrency: group: factory-publish, cancel-in-progress: false` giữ **một** run đang chạy + **một** run chờ; run chờ cũ bị **hủy** khi có run chờ mới (kể cả bởi `factory-refill.yml` cùng group). Trigger chỉ là gợi ý; **repo là hàng đợi**:
1. mỗi run quét mọi draft trong `_drafts/` trên main mới nhất (tối đa 30 ID/run; draft không hợp lệ hoặc "độc" bị **cách ly**, không chặn draft khác; REPAIR chưa sửa được bỏ qua); push bị REFUSE vẫn drain backlog hợp lệ rồi mới làm đỏ run;
2. run chờ bị hủy không mất gì — run sống sau sẽ publish draft của nó;
3. nếu run chờ bị refill thay và không còn push nào sau đó, writer chạy `writer-session.py confirm` — tự **nudge** (`_drafts/.nudge-Wx`, không phải `.md`) để kích lại publisher; path filter của workflow liệt kê `_drafts/.nudge-*` tường minh (không dựa vào việc `**` của GitHub có khớp dotfile) và test/mô phỏng dùng bộ lọc *thận trọng* nên pattern đó là bắt buộc.
Không cron, không `workflow_dispatch` mới (giữ hợp đồng).

## 5. Phục hồi

| Tình huống | Hành động |
|---|---|
| Writer hết quota/mất kết nối | push phần đã xong; lease tự hết hạn (mặc định 12h với `begin`); AI khác `begin`; phần đã push vẫn được publish |
| Lease hết hạn khi draft đã push chưa publish | selector cách ly (không lease sống); chủ cũ/mới `begin --ids …`, `check` + `push` (gắn lại `writer_session`; bản draft cũ của cùng ID bị xóa trong cùng commit) ⇒ `confirm` nudge ⇒ publish. `release` bị chặn (`DRAFT_QUEUED`) khi draft đã push còn chờ |
| Hàng REPAIR orphan | `begin --ids BLG-… --adopt`, sửa draft, `push` |
| `REGISTRY_CORRUPT` | `python3 scripts/factory/writer-session.py repair-registry` (CAS: lấy bản hợp lệ gần nhất trong git history, prune, commit; không tạo lease mới) |
| Run đỏ `upstream_overlap` | không cần làm gì: main không đổi, run kế drain từ truth mới |
| Run đỏ stale lock/txn | `docs/RECOVERY.md` (op `recover`); không force-unlock |
| Checkpoint lệch | `factory-operator.py repair-checkpoint` (chỉ op này sửa số đếm) |

## 6. Tương thích ngược / rollback

- Lease v1 (không session) hợp lệ; phiên đầu tiên chạm vào sẽ nhận (adopt). `writer-claim.py claim --writer W2 --ids …` (cũ) vẫn chạy; phiên mặc định theo working copy.
- Draft không khai `writer_session:` vẫn được nhận (cảnh báo) — chỉ kiểm khi có khai. Registry vắng ⇒ chế độ single-writer cũ.
- Rollback: revert commit merge; không có migration dữ liệu (registry v2 đọc được bởi v1 — trường thừa bị bỏ qua).

## 7. Giới hạn đã biết (không che giấu)

- Danh tính phiên là **cộng tác** (cùng một token GitHub): chống nhầm lẫn/đua, không chống kẻ cố tình giả `writer_session`.
- Lease dựa trên ĐỒNG HỒ máy writer (`expires_at` ghi bằng đồng hồ máy này, so bằng đồng hồ máy kia): đồng hồ lệch quá TTL có thể làm lease sống bị coi hết hạn (hoặc ngược lại). Giữ NTP đúng; TTL mặc định 12h/48h đủ rộng cho lệch phút. Không có nguồn thời gian tin cậy từ git.
- Tên file draft trùng hậu tố với slug của hàng khác (`*-<slug>.md` khớp `thue-<slug>.md`) làm `factory-operator.find_draft` (glob đầu tiên) có thể chọn nhầm file: selector cách ly cả hai — đặt slug không là hậu tố của nhau.
- `writer-claim.py merge` (công cụ legacy gộp registry offline) chọn lease claim SỚM hơn khi hai phiên cùng đòi một slot — không dùng cho luồng thường (CAS tránh phải gộp).
- Container bị tạo lại mà AI không giữ token phiên (`FACTORY_WRITER_SESSION`/`--session`): lease cũ vẫn là của phiên cũ cho đến `expires_at` (12h với `begin`, 48h với claim cũ) — hệ thống KHÔNG chiếm lease còn hạn. Writer chạy lặp (routine) nên đặt token cố định.
- Run chờ bị hủy bởi run KHÁC workflow chỉ được kích lại bởi push kế tiếp hoặc `confirm --nudge`.
- Dữ liệu cũ (ngoài phạm vi): 1069 bằng chứng QA của bài đã publish lệch hash sau đợt migrate domain (`validate.py --scope batch|full` đỏ; `chunk` xanh) (hàng BLG-02021 có `internal_links` sai đã được sửa bằng PR #6 — một ô dữ liệu, không đổi vân tay QA). Việc re-attest 1069 bằng chứng cần chủ xe duyệt (xem báo cáo audit).

## 8. Audit đã sửa (P0–P3) và bằng chứng kiểm thử

| # | Lỗi thật (đã repro offline) | Sửa ở | Chặn hồi quy bằng |
|---|---|---|---|
| P0-1 | một hàng REPAIR/WRITING/QA/PASS **bất kỳ** làm `prepare-next` bail ⇒ MỌI run đỏ, cả nhà máy đứng | `factory-operator.py` (`prepare-next --ids`), `factory-queue.py` (pair đồng nhất, chỉ publish tập PASS), resume-first PER-WRITER ở `writer-session.py begin` | sim S2, `test_factory_queue`, `test_writer_session` T27 |
| P0-2 | run chờ bị hủy (kể cả bởi workflow refill) ⇒ draft nằm mãi trong `_drafts/` | `push-selection.py --backlog` (drain ≤30 ID/run), nudge `_drafts/.nudge-<slot>` (+ pattern path filter tường minh) | sim S1, S4, S7, `test_selector_drain`, `test_writer_session` T42, `test_hardening` (nudge trigger contract) |
| P0-3 | `git rebase` của publisher mang sửa đổi của writer qua rename `_drafts→_posts` ⇒ nội dung ≠ nội dung đã QA | `publisher-push.py` (guard giao path, sha256 trước/sau rebase, ≤3 rebase) | sim S6, `test_publisher_push` |
| P1 | slot chỉ là tên; registry hỏng = rỗng; `mktime` lệch ±7h; REPAIR mất chủ; cap đá lease cũ nhất; không có CAS client; push không giới hạn path | `writer-claim.py` v2, `writer-session.py`, `validate.py` (check registry) | `test_writer_claim`, `test_writer_session` T01–T36 |
| P2 | `writer-loop qa` thiếu whitelist số tiền; `txn_append(None)`; test không chạy trong CI; tên nhà cung cấp trong workflow/docs | `writer-loop.py`, `publish-gate.py`, job `engine-tests`, docs trung lập | `test_writer_loop`, `test_hardening` |
| P3 | `__pycache__` không ignore; BLG-02021 sai route trong matrix (PR #6, một ô, không đổi vân tay QA) | `.gitignore`, `data/content-matrix.csv` | `check-built-links.py` (FULL gate) |

Kịch bản bắt buộc → test (toàn bộ offline, origin bare cục bộ, `receive.denyNonFastForwards=true` ⇒ force push làm test hỏng):

| Kịch bản | Test |
|---|---|
| nhiều writer claim đồng thời | `test_writer_session` T01, T04, T05 |
| 3 writer push gần như cùng lúc | T10, sim S1, S11 (3x10 ID) |
| 2 writer cùng một ID | T02, T15 |
| 2 phiên cùng một slot | T03, T26, T35, T36 |
| hết quota giữa batch / mất kết nối giữ lease | T20, T21, sim S3 |
| lease hết hạn / reclaim / không chiếm lease sống | T21, T22, T23, sim S10 |
| push bị HTTP 409/422/503 | T11, T12, T13 (hook pre-receive chèn lỗi) |
| QA FAIL → REPAIR (không chặn người khác) | sim S2, T27, T41 |
| publisher restart / retry / lock mồ côi | sim S7, S8 |
| Factory Refill chạy giữa lúc publish | sim S4 |
| push lặp / checkpoint cũ | T14, sim S7, S9 |
| Actions bị hủy / lỗi | sim S1, S7, S8 |
| sửa bài đã PUBLISHED | sim S5, S6 |
