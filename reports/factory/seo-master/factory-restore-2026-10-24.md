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
- Rollback #69: revert commit; không có migration dữ liệu (`parse_pool` vẫn nhận `writer-pool.json` cũ, trường mới có mặc định 10/30).

## 3. Sản xuất thật trong phiên

- Tổng cộng **63 bài** đã PUBLISHED qua `writer-session.py` (begin → viết → check → push → confirm) bằng hai slot luân phiên W4/W5, mỗi push ≤ 10 ID; publisher chia pair 2.
- Mọi bài qua QA cục bộ trước khi push (ngưỡng 75/70, business_fact, legal, không critical); không hạ ngưỡng, không sửa evidence.
- Nhóm pháp lý (06111–06128) chỉ dùng mệnh đề đã đối chiếu với văn bản đọc được (Luật 36/2024 bản hợp nhất 55/VBHN-VPQH, Luật XLVPHC bản hợp nhất 171/2026, NĐ 168/2024 và NĐ 238/2026, NĐ 67/2023 và NĐ 220/2026, Luật Kinh doanh bảo hiểm). Nhiều giả thuyết trong đề bài đã bị văn bản bác và đã bỏ (ví dụ: không có mốc "10 ngày" để trình lại giấy tờ; người ngồi sau cũng bị cấm dùng ô; "bảo hiểm xe máy bắt buộc" chưa bị bãi bỏ).
- Hai hàng **BLG-05709** và **BLG-05716** cố ý để `PLANNED`, không viết: gần như trùng ý định với bài đã đăng (BLG-02663 làng tăm hương Quảng Phú Cầu; BLG-03469, BLG-04751, BLG-01053, BLG-02999 về Đông Anh/Cổ Loa/Đào Thục/Lỗ Khê). Không có thao tác chuẩn để rút một hàng PLANNED; chủ site quyết định có giữ, đổi ý định hay chặn qua quy trình riêng.

## 4. Số liệu tại thời điểm ghi

| Chỉ số | Giá trị |
|---|---|
| Hàng trong matrix | 6.142 |
| PUBLISHED (factory) | 5.656 |
| EXISTING (legacy còn dùng) | 473 |
| REVIEW | 10 |
| BLOCKED | 1 |
| PLANNED (claimable) | 2 (BLG-05709, BLG-05716 — cố ý chưa viết) |
| Sức chứa kỹ thuật cứng (`hard_capacity`) | 10.000 (children 9.517 + legacy 483) |
| Capacity chưa vật chất hoá | 3.858 — đây là **sức chứa kỹ thuật**, không phải bài đã viết |

Phân biệt: *10.000* là trần kỹ thuật/biên tập; *5.656* là bài factory đã xuất bản; *483* là legacy; *3.858* là chỗ trống chưa có chủ đề. Không được báo "đạt 10.000" bằng cách cộng capacity.

## 5. Bão hòa chủ đề (nói thẳng)

Quét lại ma trận cho thấy các hub pháp lý/giá/thủ tục đã phủ rất dày (mỗi chủ đề lớn thường có từ vài đến hàng chục bài). Các địa điểm nổi tiếng ở Hà Nội và lân cận hầu hết đã có ≥ 2 bài. Hướng "lấp đầy 10.000" bằng biến thể (đổi loại xe/địa danh/ví dụ) sẽ tạo bài gần trùng; G9 sẽ chặn phần lớn nên refill chỉ nhận chủ đề thực sự khác ý định. Vì vậy mục tiêu 10.000 bài *hợp lệ và không loãng* chưa khả thi chỉ bằng nguồn hiện có; cần nguồn chủ đề mới có thật (câu hỏi thật từ khách, thay đổi pháp luật mới, sự kiện/mùa vụ có nguồn).

## 6. Rủi ro vận hành đã ghi nhận (chưa sửa, theo dõi)

- **Pages dạng hủy-khi-có-push**: mỗi push vào `main` hủy bản build đang chạy (~9–11 phút/lần). Push dồn dập (lease, draft, publish) có thể làm bản deploy chậm hàng chục phút. Cách giảm đã dùng: luân phiên W4/W5, gom lease + push trong một đợt rồi để yên ~12 phút.
- **Giới hạn kích thước Pages** (~1 GB): ước tính còn chỗ đến khoảng 7.800 bài; cần theo dõi trước khi vượt.
- **Backlog > 30 ID/run** phụ thuộc cron `17,47 * * * *` của publisher (lịch GitHub thực tế có thể giãn hàng giờ).
- **Nhãn session** đã dùng: W4 `s-claude-sonnet-w4`, W5 `s-claude-sonnet-w5` (đã ghi vào AGENTS.md và quickstart).

## 7. Cách tiếp tục (resume)

```bash
git pull --ff-only origin main
export FACTORY_WRITER_SESSION=s-claude-sonnet-w4   # hoặc nhãn riêng của AI mới
python3 scripts/factory/writer-session.py status
python3 scripts/factory/writer-session.py begin --slot auto --label <ten-ai> --count 10
```

- Chưa có hàng PLANNED nào để viết ngoài 2 hàng đã nêu: viết **batch chủ đề thật** vào `data/factory/refill-batches/<ngày>-<tag>.json` (qua gate G1–G9, kiểm bằng `refill-queue.py --verify`) rồi bump `data/factory/refill-request.json`; sau run refill xanh thì `git pull` trước khi viết.
- Nguyên tắc cố định: không hạ QA, không sửa evidence, không viết giá/cọc/phí trễ/bảo hiểm ngoài `data/business-facts.json`, pháp lý chỉ dùng mệnh đề đã xác minh.
