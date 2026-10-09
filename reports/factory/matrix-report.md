# Báo cáo matrix — TẠO MỚI (không phải khôi phục)

## Ngữ nghĩa năng lực (báo đúng, không đệm)

| Khái niệm | Giá trị | Ý nghĩa |
|---|---|---|
| HARD_CAPACITY | 10000 | Trần kỹ thuật của factory, KHÔNG phải chỉ tiêu biên tập. |
| EDITORIAL_TARGET | 6980 | Tổng planned_target trong taxonomy — chỉ tiêu chủ đề đã kiểm chứng. |
| CURRENT_VALID_ROWS | 1790 | Số hàng hiện tại, tất cả là ý định hợp lệ (không hàng đệm). |
| CURRENT_SEEDED_ROWS | 1307 | Hàng planned mới đã có ý định riêng. |
| RESERVED_CAPACITY | 8210 | HARD_CAPACITY trừ legacy và seed — chỉ dành cho chủ đề MỚI thật. |
| MISSING_VALID_TOPIC_SPACE | 5673 | Thiếu so với EDITORIAL_TARGET — BÁO THIẾU, không đệm. |

Lưu ý trung thực: 483 (legacy) + 6980 (EDITORIAL_TARGET) = 7463 < HARD_CAPACITY 10000. Taxonomy hiện tại KHÔNG THỂ đạt 10.000 hàng. Muốn tăng phải mở rộng seed bằng chủ đề thật (khác biệt ý định, không hoán đổi tên/từ). Đạt HARD_CAPACITY không phải điều kiện hoàn thành của matrix; điều kiện là mọi hàng đều hợp lệ và chống trùng PASS.

TẠO MỚI 2026-09-27 theo phê duyệt của chủ xe - không phải khôi phục nguyên bản.

Sinh bởi `scripts/factory/generate-matrix.py` từ `data/state/matrix-seed.json` (cấu hình do người biên soạn) + taxonomy + inventory. Idempotent.

## Tổng quan

- Tổng hàng: 1790
- Legacy EXISTING: 473 (giữ nguyên URL/mapping, không đổi ID)
- Legacy REVIEW: 10 (giữ nguyên trạng thái, không tự PASS)
- PLANNED mới: 127
- Năng lực danh nghĩa cũ: 10.000 hàng; tổng planned_target trong taxonomy: 6980

## Chống trùng (đã kiểm máy, tất cả PASS)

- id, slug, output_path, canonical, expected_url duy nhất toàn matrix.
- Trong cùng child: primary_keyword và intent chuẩn hoá không trùng.
- 483 URL legacy đối chiếu inventory: 100% không đổi.

## Chênh lệch với chỉ tiêu — BÁO THIẾU, KHÔNG ĐỆM

Seed chỉ đăng ký được 127 hàng có giá trị riêng (mỗi hàng một ý định tìm kiếm khác nhau, không sinh bằng đổi vài từ). Không tự đệm hàng rỗng để đạt 10.000 vì làm vậy tạo hàng nghìn bài gần giống nhau — đúng điều cấm. Phần thiếu sẽ được bổ sung bằng cách mở rộng seed sau khi có chủ đề thật.

| Child | PLANNED đã có | planned_target (seed taxonomy) |
|---|---|---|
| C-THUE-GIA | 0 | 220 |
| C-THUE-THU-TUC | 0 | 200 |
| C-THUE-NGAY | 0 | 180 |
| C-THUE-TUAN | 0 | 170 |
| C-THUE-THANG | 0 | 200 |
| C-THUE-DAT-COC | 0 | 150 |
| C-THUE-QUOC-TE | 0 | 140 |
| C-THUE-NHAN-TRA | 0 | 180 |
| C-THUE-SU-CO | 0 | 180 |
| C-XE-SO | 0 | 160 |
| C-XE-GA | 0 | 160 |
| C-XE-50CC | 0 | 140 |
| C-XE-DIEN | 0 | 160 |
| C-XE-DAP-DIEN | 4 | 100 |
| C-HONDA-WAVE | 3 | 120 |
| C-HONDA-VISION | 3 | 120 |
| C-HONDA-AIR-BLADE | 3 | 110 |
| C-HONDA-CLICK | 2 | 100 |
| C-YAMAHA-SIRIUS | 3 | 100 |
| C-BAO-DUONG | 5 | 140 |
| C-GPLX | 3 | 150 |
| C-BAO-HIEM | 2 | 130 |
| C-NOI-DO-CONG | 2 | 120 |
| C-PHAT-NGUOI | 2 | 120 |
| C-BIEN-BAO | 2 | 100 |
| C-GIAY-TO | 3 | 110 |
| C-QUY-DINH | 3 | 150 |
| C-DIEM-DEN | 6 | 170 |
| C-BAO-TANG | 3 | 90 |
| C-PHO-CO | 3 | 110 |
| C-HO-TAY | 3 | 100 |
| C-LONG-BIEN | 3 | 110 |
| C-NGOAI-THANH | 3 | 110 |
| C-CD-NOI-THANH | 3 | 100 |
| C-CD-CUOI-TUAN | 4 | 130 |
| C-CD-MAI-CHAU | 2 | 80 |
| C-CD-MOC-CHAU | 2 | 80 |
| C-CD-HA-GIANG | 2 | 80 |
| C-CD-PHO-BAC | 3 | 90 |
| C-KY-NANG-CO-BAN | 4 | 180 |
| C-KY-NANG-TINH-HUONG | 4 | 180 |
| C-KY-NANG-THOI-TIET | 4 | 150 |
| C-KY-NANG-CHO-DO | 4 | 130 |
| C-KY-NANG-GUI-XE | 4 | 120 |
| C-KY-NANG-SUC-KHOE | 3 | 110 |
| C-HD-GIA | 2 | 90 |
| C-HD-THU-TUC | 2 | 90 |
| C-HD-PHAP-LY | 2 | 90 |
| C-HD-CHON-XE | 2 | 90 |
| C-HD-SU-CO | 2 | 90 |
| C-HD-NGUOI-MOI | 2 | 90 |
| C-THUE-DOI-TUONG | 3 | 80 |
| C-THUE-DIA-DIEM | 3 | 70 |
| C-XE-LUA-CHON | 3 | 80 |
| C-XE-KHAC-PHUC | 3 | 90 |
| C-XE-SO-SANH | 3 | 90 |
