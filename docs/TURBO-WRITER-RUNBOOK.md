# TURBO WRITER — tăng sản lượng /blog mà giữ nguyên gate

Phê duyệt: 2026-10-11. Áp dụng cho EXTERNAL AI WRITER/COORDINATOR có quyền GitHub của `thuexemayhanoi/blog`. Đây là hướng dẫn vận hành, KHÔNG mở AI/API trong GitHub Actions và KHÔNG thay hợp đồng publish.

## 0. Quy tắc quan trọng

- **Writer push tối đa 10 draft một lượt** vào `_drafts/**`. `factory-publish.yml` nhận đúng ID, phân thành **5 cặp x 2**, QA và publish tuần tự trong cùng một workflow run.
- **Giữ `data/factory/production-control.json` với `chunk_size=2`**. Giá trị này là mức commit/claim có transaction, KHÔNG phải kích thước một lần writer push. Không thay `MAX_QUEUE_PER_PUSH=10` hoặc `MAX_LEASE=10` nếu chưa có audit sâu.
- Chỉ publish qua `scripts/factory/publish-gate.py`; writer KHÔNG sửa `_posts/`, checkpoint, matrix, SHA evidence, writer-lock, transaction hay reports. Không force push.
- QA vẫn `quality >= 75`, `seo >= 70`, business facts PASS, legal PASS hoặc NOT_REQUIRED, không critical failure. Không tạo thêm bài kém chất lượng để đầy 10.
- Chỉ có **một publisher** ghi vào production tại một thời điểm. Có thể có 1–3 writer soạn song song nếu mỗi writer có lease ID riêng.

## 1. Preflight đọc nguồn sự thật TRƯỚC mỗi batch

```bash
git fetch origin main
git checkout main
git pull --ff-only origin main
python3 scripts/factory/queue.py --stats
python3 scripts/factory/writer-claim.py show
python3 scripts/factory/refill-queue.py --plan
```

Đối chiếu `data/state/checkpoint.json`, `reports/factory/progress.json`, `data/state/transaction.json`, `data/state/writer-claims.json`, `reports/factory/factory-queue-last-run.json` và logs Actions mới nhất. Nếu transaction/maintenance lock/REPAIR đang tồn tại, xử lý theo `docs/RECOVERY.md` **trước** khi nhận ID mới. `show` có thể tự prune registry; commit registry đã prune theo quy trình fast-forward nếu file thực sự thay đổi, không ghi đè lease writer khác.

## 2. Refill trước khi queue rỗng

`data/factory-capacity.json` quy định `min_ready_queue=100` và `refill_target=300` (ngưỡng vận hành, KHÔNG đảm bảo luôn có 300 chủ đề đủ chuẩn). Khi PLANNED xuống dưới 100, coordinator chuẩn bị ứng viên SEO thực, ưu tiên cơ hội được xác minh từ GSC/Ubersuggest, phân loại taxonomy và độc lập search intent.

1. Chia candidate thành batch khoảng 20–50 hàng/file tại `data/factory/refill-batches/*.json`. Mỗi hàng đủ `candidate_id,child_id,title,intent,kw,kw2,links,subtopic,audience,location_scope,word_target>=1200`.
2. Trước khi push, kiểm tra trùng keyword/intent/title/slug, link thực và chính sách nguồn. Nếu có local checkout, kiểm tra bằng `stage-refill-batch.py` trên bản sao hoặc môi trường tạm; không tự sửa ledger production.
3. Commit/push **chỉ refill-batches** để kích hoạt `factory-refill.yml`; workflow tự chạy G1–G8, stage, materialize, validate, commit matrix/checkpoint đồng bộ. Không gửi draft chưa có ID cùng commit refill.
4. Nếu run FAIL: lấy *chính xác candidate_id và gate*, sửa ứng viên, push lại; không tắt validator. Nếu run PASS: `git pull --ff-only`, xác minh `PLANNED` thực tăng và lấy ID mới từ main.

Chú ý: batch có **một candidate trùng** có thể làm toàn bộ stage FAIL và rollback; kiểm tra trước giúp tiết kiệm nhiều lần chạy. Không thêm hàng giả cho đủ 100/300.

## 3. Writer batch 10 — một push, năm cặp

```bash
git pull --ff-only origin main
python3 scripts/factory/writer-claim.py claim --writer W1 --count 10
```

Commit/push registry lease riêng lên main theo quy trình ownership/rebase trong `scripts/factory/writer-claim.py` và `docs/PROC-PUBLISH.md` **trước** khi bắt đầu viết. Chỉ sử dụng danh sách ID đã xác nhận thuộc W1; W2/W3 tuyệt đối không chạm các ID này.

- Viết tối đa 10 bài có search intent riêng, đúng `data/content-matrix.csv` và manifest. Áp dụng `docs/ARTICLE-RULES.md`, `docs/QUALITY-RUBRIC.md`, `docs/SOURCE-RESEARCH.md`, `docs/INTERNAL-LINKING.md`.
- Mỗi bài đủ cấu trúc, >= word_target, tên file/frontmatter chính xác, nội dung hữu ích, link nội bộ thật, business facts từ `_data/`. Không bịa địa danh, pháp lý, giá hay chính sách.
- Chạy các bước writer-side preflight/QA được tài liệu hiện có hỗ trợ, sửa lỗi trước push.
- Commit **một lần cho toàn bộ nhóm tối đa 10 draft**, push main fast-forward. Không tách thành 5 push 2 bài nếu cả 10 đã sẵn sàng.
- Factory tự claim/QA/promote *theo 5 cặp*. Nếu pair REPAIR, sửa đúng draft/ID rồi push repair-only; các pair sau DEFERRED sẽ chạy lại theo cơ chế resume-first, không mất bài đã publish.
- Sau khi run hoàn tất, kiểm tra `reports/factory/factory-queue-last-run.json` và checkpoint. Nhả các lease hoàn thành bằng `writer-claim.py release`/prune đúng ownership; không xoá thẳng JSON.

### Multi-writer

Nếu có 2–3 AI ngoài đang hoạt động: W1, W2, W3 mỗi agent claim tối đa 10 ID **không trùng**; soạn song song nhưng push qua fast-forward/rebase có kiểm tra và không overwrite `_drafts/` của người khác. Publisher vẫn serial qua `concurrency: factory-publish`. Nếu chỉ có 1 AI thì chỉ dùng W1; KHÔNG khai 3 agent ảo.

## 4. Giảm deploy lãng phí

- Mỗi nhóm 10 bài chỉ push một commit bản nháp: giảm số push/CI/Pages build so với 5 lần push 2 bài.
- Trong lúc GitHub Pages build, AI có thể nghiên cứu/viết batch sau trên bản làm việc riêng; nhưng **không** tự tuyên bố URL live cho đến khi Pages SUCCESS trên đúng commit chứa bài.
- Không sửa cấu hình Pages built-in hoặc tự tạo workflow deploy khác trong giai đoạn này. Chỉ đổi deploy khi có benchmark, nhánh thử và xác nhận tương thích custom domain, URL, sitemap.

## 5. Báo cáo từng run

Ghi: số draft đã push, ID/lease, run Factory, số PUBLISHED thật, REPAIR/DEFERRED, checkpoint/next_claimable_id, số PLANNED sau publish, link commit và Pages status. Tổng bài qua factory và bài legacy là số khác nhau. Đạt 10.000 chỉ khi các bài hợp lệ đã qua cổng xuất bản; không tính unmaterialized capacity.

**Ưu tiên khi vắng AI writer:** Không có mã nào trong Actions tự soạn bài. Coordinator phải kích hoạt writer ngoài ở phiên làm việc có quyền GitHub; watchdog chỉ dry-run/read-only, không tự viết và không tự restart.
