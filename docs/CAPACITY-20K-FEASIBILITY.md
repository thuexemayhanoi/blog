# CAPACITY 10K → 20K — điều kiện kỹ thuật và biên tập (ĐỀ XUẤT, chờ chủ website duyệt)

Ngày lập: 2026-10-12. Nguồn: `data/factory-capacity.json`, `scripts/factory/capacity-audit.py`,
`refill-queue.py`, `sitemap-plan.py`, `data/content-matrix.csv`, lịch sử GitHub Actions.
Tài liệu này KHÔNG đổi engine, cấu hình hay trần nào; mọi bước ở mục 5 cần chủ duyệt.

## 1. Bối cảnh

- Quyết định chủ xe 2026-09-27 (`docs/ARCHITECTURE-10K.md`): chiến dịch hoàn thành khi đạt 10.000 bài HỢP LỆ
  PUBLISHED; không hạ gate, không đếm giả.
- Chỉ thị MASTER 2026-10-12: mục tiêu dài hạn 20.000 bài hợp lệ đã xuất bản (bài factory + bài legacy hợp lệ),
  không chấp nhận nội dung rác/trùng để đạt chỉ tiêu; hết chủ đề hữu ích thì ghi nhận giới hạn và báo cáo.

## 2. Số liệu hiện tại (`capacity-audit.py`, 2026-10-12)

| Mục | Giá trị |
|---|---|
| `hard_capacity` = `editorial_capacity_total` | 10.000 (56 child 9.517 + legacy 483) |
| Chỉ tiêu biên tập ĐÃ KIỂM CHỨNG (`planned_target`, 56 child) | 6.980 (+ 483 legacy = 7.463) |
| Hệ số mở rộng khi cấp `child_editorial_capacity` | 9.517 / 6.980 ≈ 1,36 (≈ 2.537 slot nằm NGOÀI chỉ tiêu kiểm chứng) |
| Đã materialize (hàng matrix) | 2.962: PUBLISHED 1.998, PLANNED 480, EXISTING 473, REVIEW 10, BLOCKED 1 |
| Unmaterialized capacity | 7.038 — là SLOT, không phải chủ đề thật |

Tổng bài sống = PUBLISHED (factory) + EXISTING (legacy). Hai số này luôn báo riêng.

## 3. Rào cản kỹ thuật (đọc từ code)

- `refill-queue.py` từ chối materialize khi `materialized + candidates > hard_capacity`; `capacity-audit.py`
  bắt buộc `editorial_capacity_total == hard_capacity`; `sitemap-plan.py` chia shard theo `hard_capacity`
  (1.000 URL/shard, 10 shard ở 10K). Vượt 10.000 cần sửa cấu hình + code + test, không phải chỉ thêm hàng.
- Cổng G1–G8 của refill buộc `kw`, `intent`, `slug`, tiêu đề chuẩn hóa DUY NHẤT trong child: số chủ đề tối đa mỗi
  child bị chặn bởi số ý định tìm kiếm thật, không bởi số slot còn trống.

## 4. Rào cản vận hành (đo thật, ước lượng ghi rõ)

- Build "pages build and deployment" thành công: 9,4' (1.820 PUBLISHED) → 10,2' (1.908) → 10,4' (1.998); gate FULL
  (Jekyll) ~7'49" ở 2.962 hàng. Ngoại suy tuyến tính thô từ 3 mẫu có nhiễu: khoảng 35–55' mỗi build ở 10.000 bài và
  70–110' ở 20.000 bài — CHƯA đo thật; còn phải kiểm tra RAM runner, kích thước site và giới hạn triển khai của Pages.
- Mỗi PR chạm engine chạy Jekyll full build: thời gian CI tăng cùng đường.

## 5. Lộ trình đề xuất (mỗi bước cần chủ duyệt)

1. Làm tới ~7.463 (toàn bộ chỉ tiêu đã kiểm chứng) trong kiến trúc hiện tại: refill chủ đề THẬT theo child, không filler.
2. Khi PUBLISHED đạt ~6.000: đo thời gian build thật và chốt hướng giảm thời gian build (ngoài phạm vi writer; PR
   riêng + kiểm thử + chủ duyệt).
3. Chỉ sau bước 2 và khi chủ duyệt: nâng `hard_capacity` + `child_editorial_capacity`
   (`data/factory-capacity.json`, `capacity-audit.py`, `sitemap-plan.py`, test) và lập vũ trụ chủ đề mới có nhu cầu
   tìm kiếm thật (cụm mới/ngách mới, không hoán vị cụm cũ).
4. Nếu số ý định thật cạn trước 20.000: DỪNG ở mức hợp lệ, ghi nhận giới hạn, báo chủ — không tạo bài đệm.

## 6. Quyết định cần từ chủ website

- Đồng ý lộ trình trên (đặc biệt: dừng ở mức hợp lệ nếu không đủ ý định thật; không nâng trần trước khi giải quyết build)?
- Có chấp nhận mốc "xong" thực tế là 10.000 (quyết định 2026-09-27) và coi 20.000 là mục tiêu mở rộng có điều kiện?
