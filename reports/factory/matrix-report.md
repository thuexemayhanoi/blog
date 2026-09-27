# Báo cáo matrix — TẠO MỚI (không phải khôi phục)

TẠO MỚI 2026-09-27 theo phê duyệt của chủ xe - không phải khôi phục nguyên bản.

Sinh bởi `scripts/factory/generate-matrix.py` từ `data/state/matrix-seed.json` (cấu hình do người biên soạn) + taxonomy + inventory. Idempotent.

## Tổng quan

- Tổng hàng: 833
- Legacy EXISTING: 473 (giữ nguyên URL/mapping, không đổi ID)
- Legacy REVIEW: 10 (giữ nguyên trạng thái, không tự PASS)
- PLANNED mới: 347
- Năng lực danh nghĩa cũ: 10.000 hàng; tổng planned_target trong taxonomy: 6570

## Chống trùng (đã kiểm máy, tất cả PASS)

- id, slug, output_path, canonical, expected_url duy nhất toàn matrix.
- Trong cùng child: primary_keyword và intent chuẩn hoá không trùng.
- 483 URL legacy đối chiếu inventory: 100% không đổi.

## Chênh lệch với chỉ tiêu — BÁO THIẾU, KHÔNG ĐỆM

Seed chỉ đăng ký được 347 hàng có giá trị riêng (mỗi hàng một ý định tìm kiếm khác nhau, không sinh bằng đổi vài từ). Không tự đệm hàng rỗng để đạt 10.000 vì làm vậy tạo hàng nghìn bài gần giống nhau — đúng điều cấm. Phần thiếu sẽ được bổ sung bằng cách mở rộng seed sau khi có chủ đề thật.

| Child | PLANNED đã có | planned_target (seed taxonomy) |
|---|---|---|
| C-THUE-GIA | 9 | 220 |
| C-THUE-THU-TUC | 11 | 200 |
| C-THUE-NGAY | 5 | 180 |
| C-THUE-TUAN | 4 | 170 |
| C-THUE-THANG | 5 | 200 |
| C-THUE-DAT-COC | 5 | 150 |
| C-THUE-QUOC-TE | 5 | 140 |
| C-THUE-NHAN-TRA | 5 | 180 |
| C-THUE-SU-CO | 6 | 180 |
| C-XE-SO | 5 | 160 |
| C-XE-GA | 5 | 160 |
| C-XE-50CC | 4 | 140 |
| C-XE-DIEN | 5 | 160 |
| C-XE-DAP-DIEN | 4 | 100 |
| C-HONDA-WAVE | 4 | 120 |
| C-HONDA-VISION | 4 | 120 |
| C-HONDA-AIR-BLADE | 3 | 110 |
| C-HONDA-CLICK | 3 | 100 |
| C-YAMAHA-SIRIUS | 3 | 100 |
| C-BAO-DUONG | 7 | 140 |
| C-GPLX | 7 | 150 |
| C-BAO-HIEM | 5 | 130 |
| C-NOI-DO-CONG | 5 | 120 |
| C-PHAT-NGUOI | 5 | 120 |
| C-BIEN-BAO | 6 | 100 |
| C-GIAY-TO | 5 | 110 |
| C-QUY-DINH | 7 | 150 |
| C-DIEM-DEN | 45 | 170 |
| C-BAO-TANG | 16 | 90 |
| C-PHO-CO | 6 | 110 |
| C-HO-TAY | 5 | 100 |
| C-LONG-BIEN | 5 | 110 |
| C-NGOAI-THANH | 6 | 110 |
| C-CD-NOI-THANH | 5 | 100 |
| C-CD-CUOI-TUAN | 14 | 130 |
| C-CD-MAI-CHAU | 4 | 80 |
| C-CD-MOC-CHAU | 5 | 80 |
| C-CD-HA-GIANG | 5 | 80 |
| C-CD-PHO-BAC | 18 | 90 |
| C-KY-NANG-CO-BAN | 7 | 180 |
| C-KY-NANG-TINH-HUONG | 7 | 180 |
| C-KY-NANG-THOI-TIET | 7 | 150 |
| C-KY-NANG-CHO-DO | 5 | 130 |
| C-KY-NANG-GUI-XE | 6 | 120 |
| C-KY-NANG-SUC-KHOE | 6 | 110 |
| C-HD-GIA | 5 | 90 |
| C-HD-THU-TUC | 5 | 90 |
| C-HD-PHAP-LY | 6 | 90 |
| C-HD-CHON-XE | 6 | 90 |
| C-HD-SU-CO | 5 | 90 |
| C-HD-NGUOI-MOI | 6 | 90 |
