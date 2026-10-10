# Cấp trúc nội dung (content hierarchy)

Sinh bởi `scripts/factory/generate-reports.py`. Mốc dữ liệu: 2026-10-10. Nguồn: `data/content-taxonomy.json`, `data/content-inventory.csv`, `data/content-matrix.csv`.

Tổng bài legacy: 483 | REVIEW: 10 | EXISTING: 473

Matrix: PRESENT_CREATED_NEW. Bảng dưới ghi số hàng PLANNED trong matrix MỚI (không phải chỉ tiêu).

| Parent | Child | Bài legacy | Hàng matrix (không legacy) | planned_target (seed) | Hub URL |
|---|---|---|---|---|---|
| P-THUE-XE | Giá thuê xe máy (C-THUE-GIA) | 6 | 45 | 220 | /thue-xe/gia-thue/ |
| P-THUE-XE | Thủ tục thuê xe (C-THUE-THU-TUC) | 19 | 45 | 200 | /thue-xe/thu-tuc/ |
| P-THUE-XE | Thuê xe theo ngày (C-THUE-NGAY) | 13 | 19 | 180 | /thue-xe/thue-ngay/ |
| P-THUE-XE | Thuê xe theo tuần (C-THUE-TUAN) | 3 | 17 | 170 | /thue-xe/thue-tuan/ |
| P-THUE-XE | Thuê xe theo tháng (C-THUE-THANG) | 13 | 21 | 200 | /thue-xe/thue-thang/ |
| P-THUE-XE | Đặt cọc & giữ giấy tờ (C-THUE-DAT-COC) | 3 | 21 | 150 | /thue-xe/dat-coc/ |
| P-THUE-XE | Thuê xe cho khách quốc tế (C-THUE-QUOC-TE) | 5 | 27 | 140 | /thue-xe/khach-quoc-te/ |
| P-THUE-XE | Nhận xe & trả xe (C-THUE-NHAN-TRA) | 24 | 34 | 180 | /thue-xe/nhan-tra-xe/ |
| P-THUE-XE | Sự cố khi thuê xe (C-THUE-SU-CO) | 31 | 33 | 180 | /thue-xe/su-co/ |
| P-XE-MAY | Xe số (C-XE-SO) | 3 | 20 | 160 | /xe-may/xe-so/ |
| P-XE-MAY | Xe tay ga (C-XE-GA) | 6 | 17 | 160 | /xe-may/xe-ga/ |
| P-XE-MAY | Xe 50cc (C-XE-50CC) | 3 | 11 | 140 | /xe-may/xe-50cc/ |
| P-XE-MAY | Xe máy điện (C-XE-DIEN) | 11 | 28 | 160 | /xe-may/xe-dien/ |
| P-XE-MAY | Xe đạp điện (C-XE-DAP-DIEN) | 3 | 14 | 100 | /xe-may/xe-dap-dien/ |
| P-XE-MAY | Honda Wave (C-HONDA-WAVE) | 1 | 13 | 120 | /xe-may/honda-wave/ |
| P-XE-MAY | Honda Vision (C-HONDA-VISION) | 1 | 12 | 120 | /xe-may/honda-vision/ |
| P-XE-MAY | Honda Air Blade (C-HONDA-AIR-BLADE) | 1 | 10 | 110 | /xe-may/honda-air-blade/ |
| P-XE-MAY | Honda Click (C-HONDA-CLICK) | 1 | 10 | 100 | /xe-may/honda-click/ |
| P-XE-MAY | Yamaha Sirius (C-YAMAHA-SIRIUS) | 0 | 11 | 100 | /xe-may/yamaha-sirius/ |
| P-XE-MAY | Bảo dưỡng xe máy (C-BAO-DUONG) | 13 | 37 | 140 | /xe-may/bao-duong-xe/ |
| P-PHAP-LY | Giấy phép lái xe (C-GPLX) | 2 | 20 | 150 | /an-toan-phap-ly/giay-phep-lai-xe/ |
| P-PHAP-LY | Bảo hiểm xe máy (C-BAO-HIEM) | 10 | 15 | 130 | /an-toan-phap-ly/bao-hiem/ |
| P-PHAP-LY | Nồng độ cồn (C-NOI-DO-CONG) | 2 | 12 | 120 | /an-toan-phap-ly/noi-do-cong/ |
| P-PHAP-LY | Phạt nguội (C-PHAT-NGUOI) | 2 | 13 | 120 | /an-toan-phap-ly/phat-nguoi/ |
| P-PHAP-LY | Biển báo giao thông (C-BIEN-BAO) | 1 | 11 | 100 | /an-toan-phap-ly/bien-bao/ |
| P-PHAP-LY | Giấy tờ xe & cá nhân (C-GIAY-TO) | 8 | 13 | 110 | /an-toan-phap-ly/giay-to/ |
| P-PHAP-LY | Quy định giao thông (C-QUY-DINH) | 13 | 19 | 150 | /an-toan-phap-ly/quy-dinh-giao-thong/ |
| P-DU-LICH | Điểm đến Hà Nội (C-DIEM-DEN) | 11 | 124 | 170 | /du-lich/diem-den/ |
| P-DU-LICH | Bảo tàng (C-BAO-TANG) | 0 | 41 | 90 | /du-lich/bao-tang/ |
| P-DU-LICH | Phố cổ Hoàn Kiếm (C-PHO-CO) | 3 | 19 | 110 | /du-lich/pho-co/ |
| P-DU-LICH | Hồ Tây & lân cận (C-HO-TAY) | 2 | 24 | 100 | /du-lich/ho-tay/ |
| P-DU-LICH | Long Biên & Gia Lâm (C-LONG-BIEN) | 0 | 28 | 110 | /du-lich/long-bien/ |
| P-DU-LICH | Ngoại thành Hà Nội (C-NGOAI-THANH) | 1 | 24 | 110 | /du-lich/ngoai-thanh/ |
| P-CUNG-DUONG | Cung đường nội thành (C-CD-NOI-THANH) | 1 | 27 | 100 | /cung-duong/cung-duong-noi-thanh/ |
| P-CUNG-DUONG | Cung đường cuối tuần (C-CD-CUOI-TUAN) | 10 | 74 | 130 | /cung-duong/cung-duong-cuoi-tuan/ |
| P-CUNG-DUONG | Mai Châu (C-CD-MAI-CHAU) | 0 | 14 | 80 | /cung-duong/mai-chau/ |
| P-CUNG-DUONG | Mộc Châu (C-CD-MOC-CHAU) | 0 | 15 | 80 | /cung-duong/moc-chau/ |
| P-CUNG-DUONG | Hà Giang (C-CD-HA-GIANG) | 0 | 15 | 80 | /cung-duong/ha-giang/ |
| P-CUNG-DUONG | Cung đường các tỉnh phía Bắc (C-CD-PHO-BAC) | 0 | 38 | 90 | /cung-duong/cung-duong-pho-bac/ |
| P-KY-NANG | Kỹ năng lái cơ bản (C-KY-NANG-CO-BAN) | 35 | 34 | 180 | /ky-nang/ky-nang-lai-co-ban/ |
| P-KY-NANG | Tình huống giao thông (C-KY-NANG-TINH-HUONG) | 97 | 40 | 180 | /ky-nang/tinh-huong-giao-thong/ |
| P-KY-NANG | Thời tiết & đường sá (C-KY-NANG-THOI-TIET) | 41 | 37 | 150 | /ky-nang/thoi-tiet-va-duong-sa/ |
| P-KY-NANG | Chở đồ & hành lý (C-KY-NANG-CHO-DO) | 23 | 42 | 130 | /ky-nang/cho-do-va-hanh-ly/ |
| P-KY-NANG | Gửi xe & giữ xe (C-KY-NANG-GUI-XE) | 19 | 44 | 120 | /ky-nang/gui-xe-va-giu-xe/ |
| P-KY-NANG | Sức khỏe khi lái xe (C-KY-NANG-SUC-KHOE) | 24 | 19 | 110 | /ky-nang/suc-khoe-khi-lai-xe/ |
| P-HOI-DAP | Hỏi đáp về giá (C-HD-GIA) | 0 | 16 | 90 | /hoi-dap/hoi-dap-gia/ |
| P-HOI-DAP | Hỏi đáp thủ tục (C-HD-THU-TUC) | 0 | 15 | 90 | /hoi-dap/hoi-dap-thu-tuc/ |
| P-HOI-DAP | Hỏi đáp pháp lý (C-HD-PHAP-LY) | 0 | 13 | 90 | /hoi-dap/hoi-dap-phap-ly/ |
| P-HOI-DAP | Hỏi đáp chọn xe (C-HD-CHON-XE) | 0 | 18 | 90 | /hoi-dap/hoi-dap-chon-xe/ |
| P-HOI-DAP | Hỏi đáp sự cố (C-HD-SU-CO) | 0 | 17 | 90 | /hoi-dap/hoi-dap-su-co/ |
| P-HOI-DAP | Hỏi đáp người mới (C-HD-NGUOI-MOI) | 18 | 25 | 90 | /hoi-dap/hoi-dap-nguoi-moi/ |
| P-THUE-XE | Thuê xe theo đối tượng (C-THUE-DOI-TUONG) | 0 | 26 | 80 | /thue-xe/thue-theo-doi-tuong/ |
| P-THUE-XE | Thuê xe theo địa điểm (C-THUE-DIA-DIEM) | 0 | 18 | 70 | /thue-xe/thue-theo-dia-diem/ |
| P-XE-MAY | Chọn loại xe khi thuê (C-XE-LUA-CHON) | 0 | 19 | 80 | /xe-may/chon-loai-xe/ |
| P-XE-MAY | Xử lý sự cố xe máy thuê (C-XE-KHAC-PHUC) | 0 | 31 | 90 | /xe-may/xu-ly-su-co-xe/ |
| P-XE-MAY | So sánh khi thuê xe máy (C-XE-SO-SANH) | 0 | 22 | 90 | /xe-may/so-sanh-xe/ |

## Cảnh báo

- REVIEW (cặp cannibalization legacy, cần đọc nội dung để xử lý): BLG-00005, BLG-00017, BLG-00018, BLG-00053, BLG-00227, BLG-00228, BLG-00410, BLG-00411, BLG-00423, BLG-00424
- Matrix TẠO MỚI có 1427 hàng PLANNED so với planned_target tổng 6980 trong seed taxonomy — phần thiếu đã được báo trong `reports/factory/matrix-report.md`, không đệm hàng rỗng.
