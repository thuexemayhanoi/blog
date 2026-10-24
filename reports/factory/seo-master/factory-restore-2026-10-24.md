# Phục hồi Content Factory — checkpoint ngày 24/10/2026

Tài liệu bàn giao để phiên sau tiếp tục, không phải khởi động lại. Số liệu lấy từ `data/content-matrix.csv`,
`scripts/factory/capacity-audit.py` và các run GitHub Actions tại thời điểm ghi; nếu lệch với engine thì engine là sự thật.

## 1. Chẩn đoán ban đầu (điểm nghẽn đã xác minh)

| Câu hỏi | Kết luận có bằng chứng |
|---|---|
| Vì sao `PLANNED = 65 < 100` | Hết ứng viên `STAGED`: nguồn chủ đề thật đã cạn. Engine khỏe (không giao dịch/khóa kẹt, lease cũ đã hết hạn, 12 slot trống). Run refill đỏ là thiết kế (`NEEDS_TOPIC_EXPANSION`). |
| Pool 12 slot nhưng tài liệu ghi 3 writer | `writer-pool.json` cho 12 slot, nhưng trần 10/push, 30/run và lease 10 nằm cứng ở 3 file kèm chú thích "3 writer × 10". Đã gom về một nguồn (PR #69). |
| Gate refill bắt trùng yếu | G2/G3/G8 chỉ bắt trùng khớp chuẩn hoá; biến thể từ vựng lọt qua. Đã thêm G9 (PR #69). |
| Timeout CI | Job `quality-gate` giới hạn 20 phút trong khi build đo được 10,5–14 phút ở ~6.100 bài; nâng lên 45 phút (PR #69). |

## 2. Thay đổi đã merge

- **#69** `fix(factory)`: G9 (token Jaccard, chặn bài gần trùng ở refill); `data/factory/writer-pool.json` là nguồn duy nhất cho `max_slots`, `max_ids_per_writer`, `max_queue_per_push` (10), `max_queue_per_run` (30); `writer-claim.parse_pool()` kiểm tra nhất quán; `push-selection.py`, `factory-queue.py`, `MAX_LEASE` đọc lại từ pool; docs/AGENTS/README/quickstart đồng bộ; test mới `test_refill_g9` (19 ca) và `test_writer_pool_contract` (6 ca), cả hai đã vào danh sách CI. Hành vi publisher giữ nguyên.
- **#74** `chore`: gỡ 4 tệp `.sass-cache` lỡ commit trong #69 và thêm vào `.gitignore` (lỗi của phiên này, đã sửa).
- **#78** `test(factory)`: fixture engine hermetic khi hàng đợi PLANNED cạn. Gate #1345 (FULL) đỏ 4/39 suite (`test_factory_queue`, `test_push_selection`, `test_multiwriter_sim`, `test_slugify_vi`) vì fixture phụ thuộc số hàng PLANNED thật: `borrow_planned_row` giữ ngày thật trong `output_path`/URL của hàng mượn, origin vàng của mô phỏng không có hàng tự do, fixture slugify đòi ≥ 5 hàng PLANNED có chữ đ. Chỉ sửa `scripts/factory/tests/`; chạy cục bộ trên cây còn 2 hàng PLANNED: 39/39 PASS.
- Rollback #69: revert commit; không có migration dữ liệu (`parse_pool` vẫn nhận `writer-pool.json` cũ, trường mới có mặc định 10/30).

## 3. Sản xuất thật trong phiên

- Tổng cộng **71 bài** đã PUBLISHED qua `writer-session.py` (begin → viết → check → push → confirm) bằng hai slot luân phiên W4/W5, mỗi push ≤ 10 ID; publisher chia pair 2. Batch cuối (BLG-06143–06150): publisher #1062, gate #1346 xanh, Pages #5561 thành công, đã mở thử 2 URL trên miền thật.
- Mọi bài qua QA cục bộ trước khi push (ngưỡng 75/70, business_fact, legal, không critical); không hạ ngưỡng, không sửa evidence.
- Nhóm pháp lý (06111–06128 và 06143–06150) chỉ dùng mệnh đề đã đối chiếu với văn bản đọc được (Luật 36/2024 bản hợp nhất 55/VBHN-VPQH, Luật XLVPHC bản hợp nhất 171/2026, NĐ 168/2024 và NĐ 238/2026, NĐ 67/2023 và NĐ 220/2026, TT 72/2024/TT-BCA trên Công báo, TT 79/2024 bản hợp nhất 41/VBHN-BCA, Luật Kinh doanh bảo hiểm). Nhiều giả thuyết trong đề bài đã bị văn bản bác và đã bỏ (ví dụ: không có mốc "10 ngày" để trình lại giấy tờ; người ngồi sau cũng bị cấm dùng ô; "bảo hiểm xe máy bắt buộc" chưa bị bãi bỏ).
- Hai lỗi nội dung bắt được khi đối chiếu lại trước khi push (không lọt ra ngoài): (1) bản nháp BLG-06147 trích Điều 39 khoản 5 điểm b mà bỏ sót vế loại trừ "trường hợp quy định tại Điều 55", đã viết lại để không khẳng định xe du lịch nước ngoài phải gắn biển số tạm; (2) BLG-06143 có hai đoạn dựa vào bản thứ cấp của TT 108/2026/TT-BCA (PDF chính thức quá lớn để đọc qua kênh hiện có), đã bỏ. Bài học: chỉ giữ mệnh đề đọc được từ văn bản chính thức; nếu không đọc được thì nói rõ là không đọc được.
- **Refill W4A** (chủ đề thật, qua gate G1–G9): 8 ứng viên `CAND-2026-10-24-W4A-001..008` (tích hợp nhiều hạng, số phôi, tịch thu phương tiện, trường hợp không bị xử phạt, xe biển số nước ngoài, khám người, va chạm nhẹ, lời khai của du khách nước ngoài). Commit 5818a88c1, run `factory-refill` #184 xanh sinh commit c60307c75, vật chất hoá BLG-06143–06150; cả 8 đã được viết và publish.
- Hai hàng **BLG-05709** và **BLG-05716** cố ý để `PLANNED`, không viết: gần như trùng ý định với bài đã đăng (BLG-02663 làng tăm hương Quảng Phú Cầu; BLG-03469, BLG-04751, BLG-01053, BLG-02999 về Đông Anh/Cổ Loa/Đào Thục/Lỗ Khê). Không có thao tác chuẩn để rút một hàng PLANNED; chủ site quyết định có giữ, đổi ý định hay chặn qua quy trình riêng.

## 4. Số liệu tại thời điểm ghi

| Chỉ số | Giá trị |
|---|---|
| Hàng trong matrix | 6.150 |
| PUBLISHED (factory) | 5.664 |
| EXISTING (legacy còn dùng) | 473 |
| REVIEW | 10 |
| BLOCKED | 1 |
| PLANNED (claimable) | 2 (BLG-05709, BLG-05716 — cố ý chưa viết) |
| Sức chứa kỹ thuật cứng (`hard_capacity`) | 10.000 (children 9.517 + legacy 483) |
| Capacity chưa vật chất hoá | 3.850 — đây là **sức chứa kỹ thuật**, không phải bài đã viết |

Phân biệt: *10.000* là trần kỹ thuật/biên tập; *5.664* là bài factory đã xuất bản; *483* là legacy (473 EXISTING + 10 REVIEW); *3.850* là chỗ trống chưa có chủ đề. Bài đang hiển thị trên site: 6.147 (`_posts`). Không được báo "đạt 10.000" bằng cách cộng capacity.

## 5. Bão hòa chủ đề (nói thẳng)

Quét lại ma trận cho thấy các hub pháp lý/giá/thủ tục đã phủ rất dày (mỗi chủ đề lớn thường có từ vài đến hàng chục bài). Các địa điểm nổi tiếng ở Hà Nội và lân cận hầu hết đã có ≥ 2 bài. Hướng "lấp đầy 10.000" bằng biến thể (đổi loại xe/địa danh/ví dụ) sẽ tạo bài gần trùng; G9 sẽ chặn phần lớn nên refill chỉ nhận chủ đề thực sự khác ý định. Một vòng khai thác khoảng trống có chủ đích (đối chiếu ma trận, nguồn pháp lý đọc được, câu hỏi thật) chỉ cho ra 8 chủ đề thực sự khác ý định, đủ minh hoạ mức bão hòa. Vì vậy mục tiêu 10.000 bài *hợp lệ và không loãng* chưa khả thi chỉ bằng nguồn hiện có; cần nguồn chủ đề mới có thật (câu hỏi thật từ khách, thay đổi pháp luật mới, sự kiện/mùa vụ có nguồn).

## 6. Rủi ro vận hành đã ghi nhận (chưa sửa, theo dõi)

- **Pages dạng hủy-khi-có-push**: mỗi push vào `main` hủy bản build đang chạy (~9–11 phút/lần). Push dồn dập (lease, draft, publish) có thể làm bản deploy chậm hàng chục phút. Cách giảm đã dùng: luân phiên W4/W5, gom lease + push trong một đợt rồi để yên ~12 phút.
- **Giới hạn kích thước Pages** (~1 GB): ước tính còn chỗ đến khoảng 7.800 bài; cần theo dõi trước khi vượt.
- **Backlog > 30 ID/run** phụ thuộc cron `17,47 * * * *` của publisher (lịch GitHub thực tế có thể giãn hàng giờ).
- **Công cụ nghiên cứu**: Firecrawl hết credit và Tavily MCP lỗi 503 trong phiên; kiểm chứng pháp lý dựa vào văn bản đã tải về và Nimble extract. PDF chính thức của TT 108/2026/TT-BCA quá lớn để đọc qua kênh hiện có, nên chưa trích dẫn điều khoản nào của thông tư này.
- **Hàng đợi cạn làm test đỏ** (đã sửa ở #78): các suite engine mượn hàng đã publish làm hàng PLANNED; hãy giữ nguyên cơ chế hermetic này khi thêm test mới, không đọc số hàng PLANNED thật làm điều kiện.
- **Nhãn session** đã dùng: W4 `s-claude-sonnet-w4`, W5 `s-claude-sonnet-w5` (đã ghi vào AGENTS.md và quickstart).

## 7. Cách tiếp tục (resume)

```bash
git pull --ff-only origin main
export FACTORY_WRITER_SESSION=s-claude-sonnet-w4   # hoặc nhãn riêng của AI mới
python3 scripts/factory/writer-session.py status
python3 scripts/factory/writer-session.py begin --slot auto --label <ten-ai> --count 10
```

- Chưa có hàng PLANNED nào để viết ngoài 2 hàng đã nêu (BLG-05709, BLG-05716): viết **batch chủ đề thật** vào `data/factory/refill-batches/<ngày>-<tag>.json` (qua gate G1–G9, kiểm bằng `refill-queue.py --verify`) rồi bump `data/factory/refill-request.json`; sau run refill xanh thì `git pull` trước khi viết.
- Nguyên tắc cố định: không hạ QA, không sửa evidence, không viết giá/cọc/phí trễ/bảo hiểm ngoài `data/business-facts.json`, pháp lý chỉ dùng mệnh đề đã xác minh.
