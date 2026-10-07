# Báo cáo matrix — TẠO MỚI (không phải khôi phục)

## Ngữ nghĩa năng lực (báo đúng, không đệm)

| Khái niệm | Giá trị | Ý nghĩa |
|---|---|---|
| HARD_CAPACITY | 10000 | Trần kỹ thuật của factory, KHÔNG phải chỉ tiêu biên tập. |
| EDITORIAL_TARGET | 6980 | Tổng planned_target trong taxonomy — chỉ tiêu chủ đề đã kiểm chứng. |
| CURRENT_VALID_ROWS | 1594 | Số hàng hiện tại, tất cả là ý định hợp lệ (không hàng đệm). |
| CURRENT_SEEDED_ROWS | 1111 | Hàng planned mới đã có ý định riêng. |
| RESERVED_CAPACITY | 8406 | HARD_CAPACITY trừ legacy và seed — chỉ dành cho chủ đề MỚI thật. |
| MISSING_VALID_TOPIC_SPACE | 5869 | Thiếu so với EDITORIAL_TARGET — BÁO THIẾU, không đệm. |

Lưu ý trung thực: 483 (legacy) + 6980 (EDITORIAL_TARGET) = 7463 < HARD_CAPACITY 10000. Taxonomy hiện tại KHÔNG THỂ đạt 10.000 hàng. Muốn tăng phải mở rộng seed bằng chủ đề thật (khác biệt ý định, không hoán đổi tên/từ). Đạt HARD_CAPACITY không phải điều kiện hoàn thành của matrix; điều kiện là mọi hàng đều hợp lệ và chống trùng PASS.

TẠO MỚI 2026-09-27 theo phê duyệt của chủ xe - không phải khôi phục nguyên bản.

Sinh bởi `scripts/factory/generate-matrix.py` từ `data/state/matrix-seed.json` (cấu hình do người biên soạn) + taxonomy + inventory. Idempotent.

## Tổng quan

- Tổng hàng: 1594
- Legacy EXISTING: 473 (giữ nguyên URL/mapping, không đổi ID)
- Legacy REVIEW: 10 (giữ nguyên trạng thái, không tự PASS)
- PLANNED mới: 87
- Năng lực danh nghĩa cũ: 10.000 hàng; tổng planned_target trong taxonomy: 6980

## Chống trùng (đã kiểm máy, tất cả PASS)

- id, slug, output_path, canonical, expected_url duy nhất toàn matrix.
- Trong cùng child: primary_keyword và intent chuẩn hoá không trùng.
- 483 URL legacy đối chiếu inventory: 100% không đổi.

## Chênh lệch với chỉ tiêu — BÁO THIẾU, KHÔNG ĐỆM

Seed chỉ đăng ký được 87 hàng có giá trị riêng (mỗi hàng một ý định tìm kiếm khác nhau, không sinh bằng đổi vài từ). Không tự đệm hàng rỗng để đạt 10.000 vì làm vậy tạo hàng nghìn bài gần giống nhau — đúng điều cấm. Phần thiếu sẽ được bổ sung bằng cách mở rộng seed sau khi có chủ đề thật.

| Child | PLANNED đã có | planned_target (seed taxonomy) |
|---|---|---|
| C-THUE-GIA | 3 | 220 |
| C-THUE-THU-TUC | 3 | 200 |
| C-THUE-NGAY | 3 | 180 |
| C-THUE-TUAN | 2 | 170 |
| C-THUE-THANG | 2 | 200 |
| C-THUE-DAT-COC | 3 | 150 |
| C-THUE-QUOC-TE | 1 | 140 |
| C-THUE-NHAN-TRA | 3 | 180 |
| C-THUE-SU-CO | 3 | 180 |
| C-XE-SO | 2 | 160 |
| C-XE-GA | 2 | 160 |
| C-XE-50CC | 2 | 140 |
| C-XE-DIEN | 3 | 160 |
| C-XE-DAP-DIEN | 1 | 100 |
| C-HONDA-WAVE | 0 | 120 |
| C-HONDA-VISION | 1 | 120 |
| C-HONDA-AIR-BLADE | 1 | 110 |
| C-HONDA-CLICK | 1 | 100 |
| C-YAMAHA-SIRIUS | 1 | 100 |
| C-BAO-DUONG | 1 | 140 |
| C-GPLX | 3 | 150 |
| C-BAO-HIEM | 1 | 130 |
| C-NOI-DO-CONG | 2 | 120 |
| C-PHAT-NGUOI | 1 | 120 |
| C-BIEN-BAO | 0 | 100 |
| C-GIAY-TO | 1 | 110 |
| C-QUY-DINH | 2 | 150 |
| C-DIEM-DEN | 0 | 170 |
| C-BAO-TANG | 0 | 90 |
| C-PHO-CO | 0 | 110 |
| C-HO-TAY | 0 | 100 |
| C-LONG-BIEN | 0 | 110 |
| C-NGOAI-THANH | 0 | 110 |
| C-CD-NOI-THANH | 0 | 100 |
| C-CD-CUOI-TUAN | 2 | 130 |
| C-CD-MAI-CHAU | 1 | 80 |
| C-CD-MOC-CHAU | 1 | 80 |
| C-CD-HA-GIANG | 1 | 80 |
| C-CD-PHO-BAC | 1 | 90 |
| C-KY-NANG-CO-BAN | 2 | 180 |
| C-KY-NANG-TINH-HUONG | 2 | 180 |
| C-KY-NANG-THOI-TIET | 2 | 150 |
| C-KY-NANG-CHO-DO | 2 | 130 |
| C-KY-NANG-GUI-XE | 3 | 120 |
| C-KY-NANG-SUC-KHOE | 2 | 110 |
| C-HD-GIA | 2 | 90 |
| C-HD-THU-TUC | 2 | 90 |
| C-HD-PHAP-LY | 2 | 90 |
| C-HD-CHON-XE | 2 | 90 |
| C-HD-SU-CO | 2 | 90 |
| C-HD-NGUOI-MOI | 2 | 90 |
| C-THUE-DOI-TUONG | 2 | 80 |
| C-THUE-DIA-DIEM | 2 | 70 |
| C-XE-LUA-CHON | 1 | 80 |
| C-XE-KHAC-PHUC | 2 | 90 |
| C-XE-SO-SANH | 1 | 90 |
