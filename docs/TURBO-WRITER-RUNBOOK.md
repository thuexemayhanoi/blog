# TURBO WRITER — tăng sản lượng /blog mà giữ nguyên gate (multi-writer, provider-neutral)

Phê duyệt: 2026-10-11; cập nhật multi-writer 2026-10-11. Áp dụng cho EXTERNAL AI WRITER/COORDINATOR (bất kỳ AI nào) có quyền GitHub của `thuexemayhanoi/blog`. Hướng dẫn vận hành, KHÔNG mở AI/API trong GitHub Actions và KHÔNG thay hợp đồng publish. Bản một trang: `docs/AI-WRITER-QUICKSTART.md`. Kiến trúc: `docs/MULTI-WRITER-ARCHITECTURE.md`.

## 0. Quy tắc quan trọng

- **Writer push tối đa 10 draft một lượt** vào `_drafts/**` (lease ≤10 ID/slot, tối đa 3 slot = 30 ID đang làm). `factory-publish.yml` nhận đúng ID, chia **cặp x 2**, QA và publish tuần tự trong cùng một workflow run, và **drain** mọi draft đang xếp hàng (run bị GitHub hủy không làm mất draft).
- **Giữ `data/factory/production-control.json` với `chunk_size=2`**. Đây là mức commit/claim có transaction, KHÔNG phải kích thước một lần writer push. Không thay `MAX_QUEUE_PER_PUSH=10` hoặc `MAX_LEASE=10`.
- Chỉ publish qua `scripts/factory/publish-gate.py`; writer KHÔNG sửa `_posts/`, checkpoint, matrix, SHA evidence, writer-lock, transaction hay reports. Không force push.
- QA vẫn `quality >= 75`, `seo >= 70`, business facts PASS, legal PASS hoặc NOT_REQUIRED, không critical failure. Không tạo thêm bài kém chất lượng để đầy 10.
- Chỉ có **một publisher** ghi vào production tại một thời điểm; 1–3 writer soạn song song, mỗi slot một phiên, mỗi ID một chủ.

## 1. Vào việc: nhận slot + lease (MỘT lệnh)

```bash
git fetch origin main && git checkout main && git pull --ff-only origin main
python3 scripts/factory/writer-session.py begin --slot auto --label <ten-ai>     # nhận slot + ≤10 ID
python3 scripts/factory/writer-session.py status                                  # slot, ai giữ, hạn, việc kế tiếp
```
`begin` là CAS (fetch → tính lại claim trên truth mới nhất → push; bị từ chối thì làm lại, không bao giờ force push). Gọi lại = gia hạn + nối việc dở. Mặc định TTL 12h (`--ttl-hours` 0.25..48). Lỗi: `SLOT_HELD` (slot đang của phiên khác), `NO_FREE_SLOT`, `REGISTRY_CORRUPT` (xem `docs/RECOVERY.md`). Còn REPAIR của bạn → `begin` chỉ nối việc (sửa REPAIR trước, `--allow-new-with-repair` để ép nhận thêm).

Đối chiếu `data/state/checkpoint.json`, `reports/factory/progress.json`, `data/state/transaction.json`, `reports/factory/factory-queue-last-run.json`. Nếu transaction/maintenance lock đang tồn tại, xử lý theo `docs/RECOVERY.md` **trước**. Công cụ cũ vẫn chạy (`writer-claim.py claim --writer Wn --ids …`, `writer-loop.py`) nhưng KHÔNG tự viết git để đẩy registry.

## 2. Refill trước khi queue rỗng

`data/factory-capacity.json` quy định `min_ready_queue=100` và `refill_target=300` (ngưỡng vận hành, KHÔNG đảm bảo luôn có 300 chủ đề đủ chuẩn). Khi PLANNED xuống dưới 100, coordinator chuẩn bị ứng viên SEO thực, phân loại taxonomy và độc lập search intent.

1. Chia candidate thành batch khoảng 20–50 hàng/file tại `data/factory/refill-batches/*.json`. Mỗi hàng đủ `candidate_id,child_id,title,intent,kw,kw2,links,subtopic,audience,location_scope,word_target>=1200`. `links` phải là route THẬT (QA coi `links_routes_valid` là lỗi critical).
2. Trước khi push, kiểm tra trùng keyword/intent/title/slug, link thực và chính sách nguồn (`stage-refill-batch.py` trên bản sao). Không tự sửa ledger production.
3. Commit/push **chỉ refill-batches** (+ bump `refill-request.json`) để kích hoạt `factory-refill.yml`; workflow chạy G1–G8, stage, và CHỈ materialize khi PLANNED claim được < `min_ready_queue` (trên ngưỡng: batch ở trạng thái STAGED, không lỗi). Không gửi draft chưa có ID cùng commit refill.
4. Run FAIL: lấy *chính xác candidate_id và gate*, sửa ứng viên, push lại; không tắt validator. Run PASS: `git pull --ff-only`, lấy ID mới từ main. Một candidate trùng làm cả stage FAIL + rollback — kiểm tra trước. Không thêm hàng giả cho đủ 100/300.

## 3. Writer batch 10 — một push

```bash
# viết draft cho các ID trong lease (xem AI-WRITER-QUICKSTART mục 2), rồi:
python3 scripts/factory/writer-session.py check      # gắn writer/writer_session, xác minh lease, QA cục bộ cùng scorer
python3 scripts/factory/writer-session.py push       # một commit CAS: chỉ draft QA PASS của ID bạn giữ + gia hạn lease
python3 scripts/factory/writer-session.py confirm --ids BLG-…,BLG-…
```
- Tối đa 10 bài có search intent riêng, đúng `data/content-matrix.csv`. Áp dụng `docs/ARTICLE-RULES.md`, `docs/QUALITY-RUBRIC.md`, `docs/SOURCE-RESEARCH.md`, `docs/INTERNAL-LINKING.md`. Số tiền dạng `1.400.000` chỉ dùng mức đã duyệt (QA cục bộ nay dùng CÙNG whitelist với publisher).
- Frontmatter: `article_id:` và `writer: Wn` phải là dòng TRẦN (không dấu nháy, không comment cuối dòng) trong 2000 ký tự đầu; `check` tự gắn `writer`/`writer_session`.
- Commit **một lần cho toàn bộ nhóm ≤10 draft**; không tách thành 5 push 2 bài nếu cả 10 đã sẵn sàng. (Drain nhặt cả draft của commit trước, nhưng rule "một commit" giữ push gọn.)
- Factory tự claim/QA/promote theo cặp 2. Kết quả `confirm`: **PUBLISHED** → `begin` tiếp; **REPAIR** (exit 3, kèm `failed_checks`) → sửa đúng draft/ID rồi `push` lại (mode repair không claim lại từ đầu; không hạ ngưỡng); **PENDING** (exit 4) → factory đang xếp hàng, tool tự nudge publisher tối đa 3 lần.
- Hàng REPAIR chờ CHỦ của nó và KHÔNG chặn writer khác (trước đây một hàng REPAIR của writer đã chết làm mọi push khác FATAL). Hàng BLOCKED: không tự mở, báo chủ xe. `DEFERRED` trong log chỉ nghĩa "pair chưa xử lý do FATAL — run kế drain lại".
- Sau khi run hoàn tất, kiểm tra `reports/factory/factory-queue-last-run.json` và checkpoint. Lease các ID đã PUBLISHED tự prune ở lần `begin` kế; muốn nhả sớm: `release --ids …`/`release --all`.

### Multi-writer

2–3 AI ngoài cùng hoạt động: mỗi AI `begin --slot auto` → slot khác nhau, ID rời nhau. Mỗi slot một phiên (session ngẫu nhiên lưu trong `.git/` của working copy; sống sót qua container mới / bàn giao AI→AI: `FACTORY_WRITER_SESSION=<token riêng>` hoặc `begin --slot W2 --session s-…`). Push qua CAS nên không bao giờ ghi đè nhau; publisher vẫn serial qua `concurrency: factory-publish`. Nếu chỉ có 1 AI thì chỉ dùng 1 slot; KHÔNG khai AI ảo.

### Hết quota / mất kết nối

Push phần đã xong (≤10) rồi dừng; phần chưa push ở lại trong lease đến khi hết hạn rồi AI khác nhận. Draft ĐÃ push không mất (publisher vẫn publish, kể cả khi lease hết hạn sau đó — selector chỉ cách ly rồi `begin` lại + `confirm` kích lại). Quay lại cùng working copy: `begin --slot <slot cũ>`; bị mất slot: `begin --slot auto` và viết lại phần chưa publish.

## 4. Giảm deploy lãng phí

- Mỗi nhóm 10 bài chỉ push một commit bản nháp: giảm số push/CI/Pages build so với 5 lần push 2 bài.
- Trong lúc GitHub Pages build, AI có thể nghiên cứu/viết batch sau; nhưng **không** tự tuyên bố URL live cho đến khi Pages SUCCESS trên đúng commit chứa bài.
- Không sửa cấu hình Pages built-in hoặc tự tạo workflow deploy khác.

## 5. Báo cáo từng run

Ghi: số draft đã push, ID/lease (slot + session), run Factory, số PUBLISHED thật, REPAIR, checkpoint/next_claimable_id, số PLANNED sau publish, link commit và Pages status. Tổng bài qua factory và bài legacy là số khác nhau. Đạt 10.000 chỉ khi các bài hợp lệ đã qua cổng xuất bản; không tính unmaterialized capacity.

**Khi vắng AI writer:** không có mã nào trong Actions tự soạn bài. Coordinator phải kích hoạt writer ngoài ở phiên có quyền GitHub; watchdog chỉ dry-run/read-only, không tự viết và không tự restart.
