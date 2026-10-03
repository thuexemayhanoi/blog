# Cấp trúc nội dung (content hierarchy)

Sinh bởi `scripts/factory/generate-reports.py`. Mốc dữ liệu: 2026-10-02. Nguồn: `data/content-taxonomy.json`, `data/content-inventory.csv`, `data/content-matrix.csv`.

Tổng bài legacy: 483 | REVIEW: 10 | EXISTING: 473

Matrix: PRESENT_CREATED_NEW. Bảng dưới ghi số hàng PLANNED trong matrix MỚI (không phải chỉ tiêu).

| Parent | Child | Bài legacy | Hàng matrix (không legacy) | planned_target (seed) | Hub URL |
|---|---|---|---|---|---|
| P-THUE-XE | Giá thuê xe máy (C-THUE-GIA) | 6 | 22 | 220 | /blog/thue-xe/gia-thue/ |
| P-THUE-XE | Thủ tục thuê xe (C-THUE-THU-TUC) | 19 | 20 | 200 | /blog/thue-xe/thu-tuc/ |
| P-THUE-XE | Thuê xe theo ngày (C-THUE-NGAY) | 13 | 7 | 180 | /blog/thue-xe/thue-ngay/ |
| P-THUE-XE | Thuê xe theo tuần (C-THUE-TUAN) | 3 | 7 | 170 | /blog/thue-xe/thue-tuan/ |
| P-THUE-XE | Thuê xe theo tháng (C-THUE-THANG) | 13 | 8 | 200 | /blog/thue-xe/thue-thang/ |
| P-THUE-XE | Đặt cọc & giữ giấy tờ (C-THUE-DAT-COC) | 3 | 11 | 150 | /blog/thue-xe/dat-coc/ |
| P-THUE-XE | Thuê xe cho khách quốc tế (C-THUE-QUOC-TE) | 5 | 16 | 140 | /blog/thue-xe/khach-quoc-te/ |
| P-THUE-XE | Nhận xe & trả xe (C-THUE-NHAN-TRA) | 24 | 9 | 180 | /blog/thue-xe/nhan-tra-xe/ |
| P-THUE-XE | Sự cố khi thuê xe (C-THUE-SU-CO) | 31 | 11 | 180 | /blog/thue-xe/su-co/ |
| P-XE-MAY | Xe số (C-XE-SO) | 3 | 6 | 160 | /blog/xe-may/xe-so/ |
| P-XE-MAY | Xe tay ga (C-XE-GA) | 6 | 5 | 160 | /blog/xe-may/xe-ga/ |
| P-XE-MAY | Xe 50cc (C-XE-50CC) | 3 | 5 | 140 | /blog/xe-may/xe-50cc/ |
| P-XE-MAY | Xe máy điện (C-XE-DIEN) | 11 | 8 | 160 | /blog/xe-may/xe-dien/ |
| P-XE-MAY | Xe đạp điện (C-XE-DAP-DIEN) | 3 | 5 | 100 | /blog/xe-may/xe-dap-dien/ |
| P-XE-MAY | Honda Wave (C-HONDA-WAVE) | 1 | 6 | 120 | /blog/xe-may/honda-wave/ |
| P-XE-MAY | Honda Vision (C-HONDA-VISION) | 1 | 5 | 120 | /blog/xe-may/honda-vision/ |
| P-XE-MAY | Honda Air Blade (C-HONDA-AIR-BLADE) | 1 | 5 | 110 | /blog/xe-may/honda-air-blade/ |
| P-XE-MAY | Honda Click (C-HONDA-CLICK) | 1 | 4 | 100 | /blog/xe-may/honda-click/ |
| P-XE-MAY | Yamaha Sirius (C-YAMAHA-SIRIUS) | 0 | 4 | 100 | /blog/xe-may/yamaha-sirius/ |
| P-XE-MAY | Bảo dưỡng xe máy (C-BAO-DUONG) | 13 | 9 | 140 | /blog/xe-may/bao-duong-xe/ |
| P-PHAP-LY | Giấy phép lái xe (C-GPLX) | 2 | 10 | 150 | /blog/an-toan-phap-ly/giay-phep-lai-xe/ |
| P-PHAP-LY | Bảo hiểm xe máy (C-BAO-HIEM) | 10 | 8 | 130 | /blog/an-toan-phap-ly/bao-hiem/ |
| P-PHAP-LY | Nồng độ cồn (C-NOI-DO-CONG) | 2 | 6 | 120 | /blog/an-toan-phap-ly/noi-do-cong/ |
| P-PHAP-LY | Phạt nguội (C-PHAT-NGUOI) | 2 | 8 | 120 | /blog/an-toan-phap-ly/phat-nguoi/ |
| P-PHAP-LY | Biển báo giao thông (C-BIEN-BAO) | 1 | 6 | 100 | /blog/an-toan-phap-ly/bien-bao/ |
| P-PHAP-LY | Giấy tờ xe & cá nhân (C-GIAY-TO) | 8 | 5 | 110 | /blog/an-toan-phap-ly/giay-to/ |
| P-PHAP-LY | Quy định giao thông (C-QUY-DINH) | 13 | 10 | 150 | /blog/an-toan-phap-ly/quy-dinh-giao-thong/ |
| P-DU-LICH | Điểm đến Hà Nội (C-DIEM-DEN) | 11 | 69 | 170 | /blog/du-lich/diem-den/ |
| P-DU-LICH | Bảo tàng (C-BAO-TANG) | 0 | 28 | 90 | /blog/du-lich/bao-tang/ |
| P-DU-LICH | Phố cổ Hoàn Kiếm (C-PHO-CO) | 3 | 9 | 110 | /blog/du-lich/pho-co/ |
| P-DU-LICH | Hồ Tây & lân cận (C-HO-TAY) | 2 | 8 | 100 | /blog/du-lich/ho-tay/ |
| P-DU-LICH | Long Biên & Gia Lâm (C-LONG-BIEN) | 0 | 9 | 110 | /blog/du-lich/long-bien/ |
| P-DU-LICH | Ngoại thành Hà Nội (C-NGOAI-THANH) | 1 | 10 | 110 | /blog/du-lich/ngoai-thanh/ |
| P-CUNG-DUONG | Cung đường nội thành (C-CD-NOI-THANH) | 1 | 9 | 100 | /blog/cung-duong/cung-duong-noi-thanh/ |
| P-CUNG-DUONG | Cung đường cuối tuần (C-CD-CUOI-TUAN) | 10 | 32 | 130 | /blog/cung-duong/cung-duong-cuoi-tuan/ |
| P-CUNG-DUONG | Mai Châu (C-CD-MAI-CHAU) | 0 | 9 | 80 | /blog/cung-duong/mai-chau/ |
| P-CUNG-DUONG | Mộc Châu (C-CD-MOC-CHAU) | 0 | 9 | 80 | /blog/cung-duong/moc-chau/ |
| P-CUNG-DUONG | Hà Giang (C-CD-HA-GIANG) | 0 | 10 | 80 | /blog/cung-duong/ha-giang/ |
| P-CUNG-DUONG | Cung đường các tỉnh phía Bắc (C-CD-PHO-BAC) | 0 | 29 | 90 | /blog/cung-duong/cung-duong-pho-bac/ |
| P-KY-NANG | Kỹ năng lái cơ bản (C-KY-NANG-CO-BAN) | 35 | 14 | 180 | /blog/ky-nang/ky-nang-lai-co-ban/ |
| P-KY-NANG | Tình huống giao thông (C-KY-NANG-TINH-HUONG) | 97 | 10 | 180 | /blog/ky-nang/tinh-huong-giao-thong/ |
| P-KY-NANG | Thời tiết & đường sá (C-KY-NANG-THOI-TIET) | 41 | 12 | 150 | /blog/ky-nang/thoi-tiet-va-duong-sa/ |
| P-KY-NANG | Chở đồ & hành lý (C-KY-NANG-CHO-DO) | 23 | 8 | 130 | /blog/ky-nang/cho-do-va-hanh-ly/ |
| P-KY-NANG | Gửi xe & giữ xe (C-KY-NANG-GUI-XE) | 19 | 10 | 120 | /blog/ky-nang/gui-xe-va-giu-xe/ |
| P-KY-NANG | Sức khỏe khi lái xe (C-KY-NANG-SUC-KHOE) | 24 | 6 | 110 | /blog/ky-nang/suc-khoe-khi-lai-xe/ |
| P-HOI-DAP | Hỏi đáp về giá (C-HD-GIA) | 0 | 7 | 90 | /blog/hoi-dap/hoi-dap-gia/ |
| P-HOI-DAP | Hỏi đáp thủ tục (C-HD-THU-TUC) | 0 | 7 | 90 | /blog/hoi-dap/hoi-dap-thu-tuc/ |
| P-HOI-DAP | Hỏi đáp pháp lý (C-HD-PHAP-LY) | 0 | 8 | 90 | /blog/hoi-dap/hoi-dap-phap-ly/ |
| P-HOI-DAP | Hỏi đáp chọn xe (C-HD-CHON-XE) | 0 | 8 | 90 | /blog/hoi-dap/hoi-dap-chon-xe/ |
| P-HOI-DAP | Hỏi đáp sự cố (C-HD-SU-CO) | 0 | 6 | 90 | /blog/hoi-dap/hoi-dap-su-co/ |
| P-HOI-DAP | Hỏi đáp người mới (C-HD-NGUOI-MOI) | 18 | 9 | 90 | /blog/hoi-dap/hoi-dap-nguoi-moi/ |
| P-THUE-XE | Thuê xe theo đối tượng (C-THUE-DOI-TUONG) | 0 | 12 | 80 | /blog/thue-xe/thue-theo-doi-tuong/ |
| P-THUE-XE | Thuê xe theo địa điểm (C-THUE-DIA-DIEM) | 0 | 11 | 70 | /blog/thue-xe/thue-theo-dia-diem/ |
| P-XE-MAY | Chọn loại xe khi thuê (C-XE-LUA-CHON) | 0 | 13 | 80 | /blog/xe-may/chon-loai-xe/ |
| P-XE-MAY | Xử lý sự cố xe máy thuê (C-XE-KHAC-PHUC) | 0 | 15 | 90 | /blog/xe-may/xu-ly-su-co-xe/ |
| P-XE-MAY | So sánh khi thuê xe máy (C-XE-SO-SANH) | 0 | 13 | 90 | /blog/xe-may/so-sanh-xe/ |

## Cảnh báo

- REVIEW (cặp cannibalization legacy, cần đọc nội dung để xử lý): BLG-00005, BLG-00017, BLG-00018, BLG-00053, BLG-00227, BLG-00228, BLG-00410, BLG-00411, BLG-00423, BLG-00424
- Matrix TẠO MỚI có 626 hàng PLANNED so với planned_target tổng 6980 trong seed taxonomy — phần thiếu đã được báo trong `reports/factory/matrix-report.md`, không đệm hàng rỗng.
