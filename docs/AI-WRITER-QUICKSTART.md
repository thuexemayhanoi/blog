# AI-WRITER-QUICKSTART — viết bài cho nhà máy SEO (BẤT KỲ AI nào, tối đa 3 người cùng lúc)

Một trang, đủ để một AI mới vào làm ngay. Chi tiết engine: `AGENTS.md`,
`docs/TURBO-WRITER-RUNBOOK.md`, `docs/MULTI-WRITER-ARCHITECTURE.md`.
Mọi lệnh chỉ dùng **git + Python 3 stdlib** — không API ngoài, không khoá, không AI trong Actions.

## 0. Mô hình (3 dòng)

```
W1 ─┐
W2 ─┼─► main (CAS, không force push) ─► factory-publish.yml (MỘT publisher, QA 75/70) ─► website
W3 ─┘
```
- Có **3 slot** `W1/W2/W3`; **mỗi slot thuộc đúng MỘT phiên (session) tại một thời điểm**. Mỗi slot giữ tối đa **10 ID** (lease), tổng tối đa 30 ID đang làm.
- Bạn chỉ **viết draft** vào `_drafts/`. KHÔNG bao giờ tự publish, tự đổi matrix/QA/checkpoint, tự đánh PASS.
- Hai AI không bao giờ giữ cùng một ID hay cùng một slot còn hạn; lease hết hạn thì AI khác nhận hợp lệ.

## 1. Vào làm — nhận slot (1 lệnh)

```bash
git clone <repo> && cd <repo>
python3 scripts/factory/writer-session.py begin --slot auto --label ten-ai-cua-ban
```
In ra `SLOT W2 | session s-… | hạn … | ID: BLG-…` (và dòng JSON `BLOG_WRITER_SESSION {…}`).
- Ghi lại **slot + session id**. Gọi lại `begin` = **nối việc dở + bù cho đủ N ID** (mặc định N=10; `--count N` là **tổng** số ID bạn muốn giữ nên lặp lại lệnh không làm lease phình). Chỉ gia hạn, không nhận ID mới: `heartbeat`. Lease mới có TTL 12h; gia hạn giữ TTL cũ (không bao giờ rút ngắn).
- Mỗi phiên (mỗi working copy hoặc token) chỉ giữ **MỘT** slot: đòi slot thứ hai → `SESSION_HOLDS_OTHER_SLOT`. Slot **legacy** (lease cũ không có session) chỉ nhận bằng `begin --slot Wn` tường minh; `--slot auto` không nhận.
- Container của bạn có thể bị tạo lại (routine, restart)? Đặt **token phiên cố định, riêng của bạn** ở đầu mỗi lần chạy: `export FACTORY_WRITER_SESSION=s-<ten-ban>-<slot>` (chỉ `A-Za-z0-9._-`, tối đa 64 ký tự) — không dùng chung với AI khác. Không có token thì mỗi container là một phiên mới và slot cũ của bạn bị giữ đến khi hết hạn.
- **Session ổn định theo slot** (nhãn CÔNG KHAI trong registry — không phải bí mật; không bao giờ dùng token GitHub/API làm session id):

  | Slot | `FACTORY_WRITER_SESSION` | Trạng thái |
  |---|---|---|
  | W1 | `s-mistral-w1` | đang dùng |
  | W2 | `s-claude-w2` | đang dùng |
  | W3 | `s-<ai>-w3` (ví dụ `s-codex-w3`) | trống — AI mới tự chọn nhãn theo mẫu này và giữ nguyên mãi |

  Resume sau hết quota/đổi container: `git pull` → export lại ĐÚNG nhãn → `status` → `begin --slot <slot>`. Không dùng nhãn của slot khác.
- `NO_FREE_SLOT` → cả 3 slot đang có người; xem `status` để biết giờ hết hạn. `SLOT_HELD` → slot đó đang của phiên khác: chọn slot khác, **đừng chiếm**.
- Còn hàng **REPAIR** của bạn → `begin` chỉ nối việc, **sửa REPAIR trước** (resume-first của riêng bạn).
- Xem trạng thái: `python3 scripts/factory/writer-session.py status`.

## 2. Viết draft (mỗi ID một file)

- Đọc hàng ID trong `data/content-matrix.csv` (title, intent, từ khóa, `internal_links`, `word_target`) hoặc `python3 scripts/factory/writer-loop.py next` KHÔNG cần (lease đã có ở bước 1).
- File: `_drafts/<YYYY-MM-DD>-<slug>.md`, slug = slug của `output_path` trong hàng matrix. Frontmatter bắt buộc: `title, date, description (140–160 ký tự), permalink, article_id, parent_id, child_id, categories`. `date:` dạng `YYYY-MM-DD…` và **trùng tiền tố tên file**; file UTF-8; không placeholder; **chỉ MỘT file cho mỗi ID** (`check` từ chối `DUPLICATE_DRAFT`; `push` xóa bản cũ của chính ID bạn đang giữ trên main). Draft vi phạm bị REFUSE/cách ly ở publisher (không làm kẹt người khác) và bạn sẽ thấy lý do trong log run.
- Luật nội dung: `docs/ARTICLE-RULES.md`, `docs/QUALITY-RUBRIC.md`. Số tiền chỉ dùng mức đã duyệt (`data/business-facts.json`); không bịa giá/cọc/ưu đãi; nguồn pháp lý chính thống cho hàng `source_required`; link nội bộ phải tồn tại. **Không hạ chuẩn để đủ số lượng.**

## 3. Kiểm tra cục bộ (cùng scorer với publisher)

```bash
python3 scripts/factory/writer-session.py check
```
Tự gắn `writer: Wx` + `writer_session: s-…` vào draft của bạn, xác minh bạn vẫn giữ lease, chạy QA cục bộ. ID `FAIL` → sửa rồi chạy lại (không push bài chưa đạt).

## 4. Push (một commit, an toàn khi nhiều AI cùng đẩy)

```bash
python3 scripts/factory/writer-session.py push        # chỉ draft QA PASS của ID BẠN GIỮ (≤10) + gia hạn lease
```
Tool tự: fetch → tính lại ownership trên main mới nhất → commit → push; bị từ chối (non-FF/409/422/5xx) thì **làm lại từ fetch** có giới hạn, **không bao giờ force push**. Mất lease giữa chừng → **exit 5, không push gì** (draft vẫn ở máy bạn).

## 5. Xác nhận publish

```bash
python3 scripts/factory/writer-session.py confirm --ids BLG-…,BLG-…
```
| kết quả | ý nghĩa | làm gì |
|---|---|---|
| exit 0 `published` | đã promote qua factory; chưa chứng minh URL live | `begin` batch kế; xác nhận Pages SUCCESS và URL HTTP 200 trước khi báo live |
| exit 3 `REPAIR` + `failed_checks` | QA FAIL, bài chờ **bạn** sửa | sửa đúng draft đó rồi `push` lại (không hạ ngưỡng, không đổi slug/ID) |
| exit 4 `PENDING` | factory đang xếp hàng | chờ/chạy lại `confirm`; tool tự nudge publisher tối đa 3 lần |
| `DEFERRED`/FATAL trong log run | run dừng vì hạ tầng | không mất draft: run kế tự nhặt lại; liên hệ chủ xe nếu lặp |
| exit 1 `BLOCKED` | hàng bị khóa/đã có/đang review | không tự mở; báo chủ xe |

## 6. Hết quota / mất kết nối / bàn giao AI → AI

- **Hết quota giữa batch**: `push` phần đã xong (≤10), rồi dừng. Phần chưa push nằm trong lease đến khi hết hạn (mặc định 12h với `begin`), sau đó AI khác nhận được. Muốn nhả sớm: `release --ids … ` hoặc `release --all` (trả luôn slot). **Đừng release ID đã push mà chưa PUBLISHED**: tool chặn (`DRAFT_QUEUED`; chờ `confirm`, hoặc `--even-if-queued` nếu chắc chắn) vì draft mất chủ sẽ bị publisher cách ly.
- **Quay lại sau khi bị ngắt**: chạy `begin --slot <slot cũ>` trên **cùng working copy** (session lưu trong `.git/`) hoặc với **cùng `FACTORY_WRITER_SESSION`** trên container mới. Slot còn hạn → nối việc tiếp; hết hạn và bị người khác lấy → `begin --slot auto` nhận slot khác. Phiên mặc định là ngẫu nhiên (KHÔNG suy từ danh tính git — nhiều AI cùng nhà cung cấp dùng chung danh tính): không token + container mới = phiên mới = `SLOT_HELD` với chính lease cũ cho đến khi hết hạn.
- **Bàn giao cho AI khác (cùng slot, cùng lease)**: gửi cho AI kia `slot + session id`; nó chạy `begin --slot W2 --session s-…` (lệnh này **lưu phiên** vào working copy nên `status/check/push/confirm` sau đó nhận ra cùng phiên). Chủ mới phải `check` + `push` lại draft để gắn `writer_session` của mình. Chỉ làm khi bạn chắc đã dừng.
- **Nhận việc orphan** (REPAIR của writer đã hết hạn; danh sách: `status` → `orphan_inflight`): `begin --ids BLG-… --adopt`.
- Không bao giờ sửa draft thuộc lease còn hạn của AI khác; selector sẽ từ chối (exit 3) và run đỏ.

## 7. Phối hợp với writer khác — quy tắc cứng

1. Mỗi ID chỉ một chủ; mỗi slot chỉ một phiên; không chiếm lease còn hạn.
2. Bạn **chỉ được ghi**: `_drafts/**` của ID mình giữ, `data/state/writer-claims.json` (qua tool), batch chủ đề refill `data/factory/refill-batches/**` + `data/factory/refill-request.json`. **Chỉ publisher/CI** ghi: `_posts/`, `data/content-matrix.csv`, `data/qa/**`, `data/state/{checkpoint,transaction,writer-lock}.json`, `reports/**`, `listing/**`.
3. Không force push, không xóa/ghi đè checkpoint/matrix/evidence, không sửa bài đã PUBLISHED, không viết bài đệm.
4. QA là cổng cứng (quality ≥75, SEO ≥70, business_fact PASS, legal PASS/NOT_REQUIRED, không lỗi critical). Draft FAIL → REPAIR → chờ bạn sửa; **không** tự PASS.
5. Hết topic (`PLANNED` < 100): chỉ đẩy batch chủ đề THẬT (`docs/TURBO-WRITER-RUNBOOK.md` mục refill) — không filler.

## 8. Sự cố thường gặp

| thông báo / exit | nguyên nhân | xử lý |
|---|---|---|
| `SLOT_HELD` | slot của phiên khác còn hạn | dùng slot khác / chờ hết hạn |
| `NO_FREE_SLOT` | đủ 3 phiên | chờ / báo chủ xe |
| `LEASE_LOST` (exit 5) | lease hết hạn hoặc phiên khác đã nhận | `begin` lại (slot mới), viết lại phần chưa publish |
| `NOT_MY_IDS` | ID không thuộc lease của bạn | chỉ push ID bạn giữ |
| `CAS_EXHAUSTED` | push bị từ chối liên tục | chạy lại `push` (idempotent); nếu mạng/GitHub lỗi kéo dài thì chờ |
| `REGISTRY_CONFLICT` | registry đọc được nhưng mơ hồ chủ (một ID hoặc một session ở ≥ 2 lease sống) | KHÔNG `repair-registry`/rollback; chờ lease hết hạn hoặc chủ xe/coordinator hóa giải; mọi lệnh từ chối và không ghi gì (`problems` liệt kê chi tiết) |
| `REGISTRY_CORRUPT` | `writer-claims.json` hỏng/timestamp sai | `python3 scripts/factory/writer-session.py repair-registry` (CAS, lấy bản hợp lệ gần nhất) |
| `GIT_READ_FAILED` | object git đọc lỗi (clone hỏng/partial) | `git fetch` lại hoặc clone mới; tool KHÔNG ghi gì khi gặp lỗi này |
| `SESSION_HOLDS_OTHER_SLOT` | phiên này đã giữ slot khác | dùng slot đang giữ (`--slot auto`) hoặc `release` trước |
| `DUPLICATE_DRAFT` | hai file draft cho một ID | giữ MỘT file, xóa bản thừa |
| `DRAFT_QUEUED` | release ID đã push nhưng chưa publish | chờ `confirm` (hoặc `--even-if-queued`) |
| `BAD_SESSION` / `BAD_SLOT` | token/slot sai định dạng | token chỉ `A-Za-z0-9._-` ≤64 ký tự; slot W1/W2/W3 |
| run đỏ `REFUSED …` | draft sai chủ / thiếu article_id / ID lạ | sửa theo thông báo; không bypass |

Kiểm tra nhanh trước khi báo xong: `confirm` exit 0 → Factory Publish xanh → Pages deploy xanh.
