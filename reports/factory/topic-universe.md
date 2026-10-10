# Báo cáo vũ trụ chủ đề (topic universe) — mở rộng 10K

Sinh bởi `scripts/factory/expand-topic-universe.py` (idempotent). 
Mọi ứng viên phải qua cổng scoring và chống trùng máy trước khi vào seed.

## Hiện trạng

| Khái niệm | Giá trị |
|---|---|
| HARD_CAPACITY | 10000 |
| CURRENT_ROWS (matrix trước mở rộng) | 1838 |
| CURRENT_SEEDED_ROWS (planned trước mở rộng) | 1355 |
| Legacy | 483 |
| EDITORIAL_TARGET sau mở rộng (tổng planned_target) | 6980 |
| RESERVED_CAPACITY sau mở rộng | 8162 |
| Ứng viên đề xuất | 121 |
| Hàng mở rộng hiện có trong seed | 109 |
| Ứng viên bị từ chối lần chạy gần nhất | 121 |
| Nhóm bị từ chối làm bằng chứng (luôn từ chối) | 8 |

Trung thực về con số: 483 legacy + EDITORIAL_TARGET 6980 = 7463 < HARD_CAPACITY 10000. Taxonomy vẫn không thể đạt 10.000 hàng một cách hợp lệ; phần thiếu tiếp tục là không gian dành cho chủ đề THẬT sau này. KHÔNG ĐỆM.

## Child mới (thêm vào taxonomy, append — không đổi child cũ)

| child_id | parent | title | slug | planned_target | legal_risk |
|---|---|---|---|---|---|
| C-THUE-DOI-TUONG | P-THUE-XE | Thuê xe theo đối tượng | thue-theo-doi-tuong | 80 | none |
| C-THUE-DIA-DIEM | P-THUE-XE | Thuê xe theo địa điểm | thue-theo-dia-diem | 70 | none |
| C-XE-LUA-CHON | P-XE-MAY | Chọn loại xe khi thuê | chon-loai-xe | 80 | none |
| C-XE-KHAC-PHUC | P-XE-MAY | Xử lý sự cố xe máy thuê | xu-ly-su-co-xe | 90 | low |
| C-XE-SO-SANH | P-XE-MAY | So sánh khi thuê xe máy | so-sanh-xe | 90 | none |

## Phân bổ hàng chấp nhận

### Theo parent

| Parent | Hàng nhận |
|---|---|
| P-CUNG-DUONG (Cung đường & hành trình) | 9 |
| P-DU-LICH (Du lịch Hà Nội) | 7 |
| P-HOI-DAP (Hỏi đáp thuê xe máy) | 6 |
| P-KY-NANG (Kỹ năng & tình huống) | 10 |
| P-PHAP-LY (An toàn & pháp lý) | 6 |
| P-THUE-XE (Thuê xe máy Hà Nội) | 35 |
| P-XE-MAY (Xe máy & dòng xe) | 36 |

### Theo child

| Child | Hàng nhận |
|---|---|
| C-BAO-HIEM | 1 |
| C-BAO-TANG | 1 |
| C-CD-CUOI-TUAN | 5 |
| C-CD-HA-GIANG | 1 |
| C-CD-MAI-CHAU | 1 |
| C-CD-MOC-CHAU | 1 |
| C-CD-PHO-BAC | 1 |
| C-DIEM-DEN | 2 |
| C-GPLX | 2 |
| C-HD-CHON-XE | 1 |
| C-HD-GIA | 1 |
| C-HD-NGUOI-MOI | 2 |
| C-HD-PHAP-LY | 1 |
| C-HD-THU-TUC | 1 |
| C-HO-TAY | 1 |
| C-HONDA-AIR-BLADE | 1 |
| C-HONDA-VISION | 1 |
| C-HONDA-WAVE | 1 |
| C-KY-NANG-CHO-DO | 1 |
| C-KY-NANG-CO-BAN | 3 |
| C-KY-NANG-GUI-XE | 1 |
| C-KY-NANG-THOI-TIET | 3 |
| C-KY-NANG-TINH-HUONG | 2 |
| C-LONG-BIEN | 1 |
| C-NGOAI-THANH | 1 |
| C-NOI-DO-CONG | 1 |
| C-PHAT-NGUOI | 1 |
| C-PHO-CO | 1 |
| C-QUY-DINH | 1 |
| C-THUE-DAT-COC | 2 |
| C-THUE-DIA-DIEM | 9 |
| C-THUE-DOI-TUONG | 8 |
| C-THUE-GIA | 3 |
| C-THUE-NHAN-TRA | 3 |
| C-THUE-QUOC-TE | 4 |
| C-THUE-SU-CO | 3 |
| C-THUE-THU-TUC | 3 |
| C-XE-50CC | 1 |
| C-XE-DIEN | 1 |
| C-XE-KHAC-PHUC | 10 |
| C-XE-LUA-CHON | 10 |
| C-XE-SO | 1 |
| C-XE-SO-SANH | 9 |
| C-YAMAHA-SIRIUS | 1 |

### Theo audience

| Audience | Hàng nhận |
|---|---|
| cặp đôi | 4 |
| gia đình | 1 |
| khách công tác | 5 |
| khách du lịch | 19 |
| khách quốc tế | 4 |
| khách vãng lai | 13 |
| khách vội | 1 |
| người cao tuổi | 1 |
| người mới | 24 |
| người nước ngoài | 2 |
| người đi làm | 24 |
| nhóm bạn | 1 |
| phượt thủ | 10 |

### Theo location_scope

| Location | Hàng nhận |
|---|---|
| ba vì | 1 |
| bến giáp bát | 1 |
| bến xe mỹ định | 1 |
| ga hà nội | 1 |
| gia lâm | 1 |
| hà giang | 1 |
| hà nội | 60 |
| hồ gươm | 1 |
| hồ tây | 2 |
| long biên | 2 |
| mai châu | 1 |
| miền bắc | 3 |
| mộc châu | 1 |
| mỹ đức | 1 |
| ngoại thành | 1 |
| ninh bình | 1 |
| nội bài | 1 |
| nội thành | 14 |
| phố cổ | 4 |
| sơn tây | 1 |
| việt nam | 9 |
| vĩnh phúc | 1 |

### Theo commercial_level (kế thừa child)

| Level | Hàng nhận |
|---|---|
| high | 41 |
| low | 35 |
| medium | 30 |
| none | 3 |

### Theo legal_risk (kế thừa child)

| legal_risk | Hàng nhận |
|---|---|
| high | 7 |
| low | 19 |
| medium | 18 |
| none | 65 |

### Theo feasibility (cổng pháp lý/nguồn)

| feasibility | Hàng nhận |
|---|---|
| PASS | 93 |
| REVIEW | 16 |

## Nhóm bị từ chối do trùng lặp cao nhất

- "Thuê xe máy cho sinh viên ở Hà Nội: cần lưu ý gì" — trùng bài legacy đã có (cannibalization — cấm)
- "Thuê xe máy dài hạn cho người đi làm trong nội thành" — intent trùng matrix/seed hiện có
- "Thuê xe máy cho cặp đôi đi chơi cuối tuần" — intent trùng matrix/seed hiện có
- "Thuê xe máy cho gia đình có trẻ nhỏ đi cùng" — intent trùng matrix/seed hiện có
- "Thuê xe máy cho người mới lấy bằng A1 lần đầu" — intent trùng matrix/seed hiện có
- "Người cao tuổi đi xe máy thuê: nên chọn xe như thế nào" — intent trùng matrix/seed hiện có
- "Thuê xe máy cho người từ tỉnh ra Hà Nội công tác" — intent trùng matrix/seed hiện có
- "Thuê xe máy dài hạn cho người nước ngoài ở Hà Nội" — trùng bài legacy đã có (cannibalization — cấm)
- "Thuê xe máy cho nhóm bạn đi phýt cuối tuần" — intent trùng matrix/seed hiện có
- "Cần xe gấp trong ngày: thuê xe máy ngay có khó không" — intent trùng matrix/seed hiện có
- "Thuê xe máy gần ga Hà Nội: lấy xe sớm nhất lúc nào" — intent trùng matrix/seed hiện có
- "Đi sân bay Nội Bài: nên thuê xe máy từ đâu và lúc nào" — intent trùng matrix/seed hiện có
- "Thuê xe máy gần bến xe Mỹ Đình: những điều cần biết" — intent trùng matrix/seed hiện có
- "Thuê xe máy gần bến xe Giáp Bát cho chuyến về tỉnh" — intent trùng matrix/seed hiện có
- "Thuê xe máy ở khu phố cổ: giữ xe và đường cấm cần biết" — intent trùng matrix/seed hiện có
- "Thuê xe máy quanh hồ Gươm dịp cuối tuần" — intent trùng matrix/seed hiện có
- "Chạy vòng hồ Tây bằng xe máy thuê: cung đường và điểm dừng" — intent trùng matrix/seed hiện có
- "Thuê xe máy ở khu Long Biên, ven sông Hồng" — intent trùng matrix/seed hiện có
- "Thuê xe máy khu vực Gia Lâm, phía Đông Hà Nội" — intent trùng matrix/seed hiện có
- "Xe số hay xe ga cho người mới biết lái khi thuê" — intent trùng matrix/seed hiện có

## Nhóm bị từ chối vĩnh viễn (luôn từ chối, không bao giờ vào matrix)

| Ứng viên mẫu | Lý do | usefulness | distinct | depth | cannibalization |
|---|---|---|---|---|---|
| Thuê xe máy giá rẻ quận Hoàn Kiếm / Ba Đình / Đống Đa ... (×12 quận) | Doorway theo tên quận: cùng bài chỉ đổi tên địa danh — cấm. | 40 | 25 | 30 | 85 |
| Thuê Honda Vision giá rẻ / Vision chất lượng / Vision tốt nhất | Hoán đổi tính từ quanh một ý định đã có trong child C-HONDA-VISION. | 45 | 20 | 35 | 90 |
| Cách thuê xe máy / cách mướn xe máy / cách đi thuê xe máy | Xoay từ đồng nghĩa quanh một ý định duy nhất. | 50 | 15 | 40 | 92 |
| Top 10 cửa hàng thuê xe máy tốt nhất Hà Nội | Template "best X in Y" mỏng + rủi ro bịa xếp hạng — cấm theo quy tắc số 2. | 60 | 55 | 25 | 60 |
| Thuê xe máy 24/7 ở Hà Nội | Bịa cam kết hoạt động: cửa hàng mở 09:00–21:00 — cấm theo quy tắc số 2. | 40 | 60 | 20 | 40 |
| Đặt cọc thuê xe máy chỉ 500.000 đồng | Bịa mức phí cố định — tiềm ủi/phí chưa được chủ xe phê duyệt. | 55 | 65 | 20 | 50 |
| Mức phạt cụ thể vi phạm nồng độ cồn hiện hành (số tiền chi tiết) | Số tiền phạt dễ lỗi thời — cần nguồn chính thống mới được viết; giữ hàng REVIEW chung quy định + yêu cầu nguồn. | 75 | 70 | 65 | 30 |
| Hàng loạt FAQ 1 câu hỏi - 1 đoạn trả lời dạng máy | Nghìn hàng FAQ gần giống nhau — cấm theo mục 4. | 35 | 30 | 15 | 80 |

## Cổng scoring (nội bộ, không phải điểm Google)

| Tiêu chí | Ngưỡng nhận |
|---|---|
| Search usefulness | >= 70 |
| Distinct intent | >= 80 |
| Content depth potential | >= 70 |
| Cannibalization risk (nghịch đảo) | <= 30 |
| Source/legal feasibility | PASS hoặc REVIEW (REVIEW = source_required khi viết) |

## Hàng đã vào seed — danh sách đầy đủ

| # | child | title | kw | audience | location | wt | feas |
|---|---|---|---|---|---|---|---|
| 1 | C-THUE-GIA | Dự toán chi phí thuê xe máy cho chuyến 3 ngày 2 đêm | chi phí thuê xe máy 3 ngày | khách du lịch | hà nội | 1200 | PASS |
| 2 | C-THUE-GIA | Giá thuê xe máy dịp lễ Tết thường thay đổi thế nào | giá thuê xe máy dịp tết | khách du lịch | hà nội | 1100 | PASS |
| 3 | C-THUE-GIA | Cách đọc báo giá thuê xe máy: con số nào là con số thật | cách đọc báo giá thuê xe máy | khách vãng lai | hà nội | 1200 | PASS |
| 4 | C-THUE-THU-TUC | Chuẩn bị giấy tờ gì trước khi đến cửa hàng thuê xe | giấy tờ cần khi thuê xe máy | khách vãng lai | hà nội | 1100 | PASS |
| 5 | C-THUE-THU-TUC | Quy trình đặt xe trước qua điện thoại: chốt trước điều gì | đặt xe máy thuê trước | khách công tác | hà nội | 1100 | PASS |
| 6 | C-THUE-THU-TUC | Nên thử xe như thế nào khi nhận xe máy thuê | chạy thử xe máy khi nhận xe | người mới | hà nội | 1100 | PASS |
| 7 | C-THUE-DAT-COC | Đặt cọc khi thuê xe máy: cần hỏi rõ điều gì | đặt cọc thuê xe máy hỏi gì | khách vãng lai | hà nội | 1100 | PASS |
| 8 | C-THUE-DAT-COC | Nhận lại tiền cọc khi trả xe: điều kiện thường gặp | nhận lại tiền cọc khi trả xe | khách vãng lai | hà nội | 1100 | PASS |
| 9 | C-THUE-QUOC-TE | Khách quốc tế thuê xe máy ở Hà Nội cần giấy tờ gì | khách quốc tế thuê xe máy cần gì | khách quốc tế | hà nội | 1400 | REVIEW |
| 10 | C-THUE-QUOC-TE | International Driving Permit ở Việt Nam: khách quốc tế cần biết gì | international driving permit việt nam | khách quốc tế | việt nam | 1400 | REVIEW |
| 11 | C-THUE-QUOC-TE | Khách quốc tế nên thuê xe số hay xe ga ở Hà Nội | khách quốc tế thuê xe số hay ga | khách quốc tế | hà nội | 1200 | PASS |
| 12 | C-THUE-QUOC-TE | Giao tiếp với cửa hàng khi không nói tiếng Việt | thuê xe máy khi không nói tiếng việt | khách quốc tế | hà nội | 1100 | PASS |
| 13 | C-THUE-NHAN-TRA | Checklist nhận xe máy thuê: kiểm tra gì trước khi rời cửa hàng | checklist nhận xe máy thuê | người mới | hà nội | 1300 | PASS |
| 14 | C-THUE-NHAN-TRA | Trả xe thuê sớm hơn dự kiến: hỏi trước điều gì | trả xe thuê sớm có hoàn tiền không | khách công tác | hà nội | 1000 | PASS |
| 15 | C-THUE-NHAN-TRA | Chụp lại tình trạng xe khi nhận và khi trả | chụp ảnh xe khi nhận và trả | khách vãng lai | hà nội | 1100 | PASS |
| 16 | C-THUE-SU-CO | Xe thuê hỏng giữa chuyến đi: trách nhiệm thuộc về ai | xe thuê hỏng giữa đường trách nhiệm | khách vãng lai | hà nội | 1300 | REVIEW |
| 17 | C-THUE-SU-CO | Tai nạn nhẹ với xe thuê: các bước xử lý ngay | tai nạn nhẹ với xe thuê | người mới | hà nội | 1300 | REVIEW |
| 18 | C-THUE-SU-CO | Xe thuê bị mất trộm: trình tự cần làm | xe thuê bị mất trộm làm gì | khách vãng lai | hà nội | 1200 | REVIEW |
| 19 | C-XE-SO | Ai nên thuê xe số và vì sao | ai nên thuê xe số | người mới | hà nội | 1100 | PASS |
| 20 | C-XE-50CC | Thuê xe 50cc khi chưa có bằng: lưu ý pháp lý | thuê xe 50cc chưa có bằng | người mới | việt nam | 1200 | REVIEW |
| 21 | C-XE-DIEN | Thuê xe điện trong nội đô Hà Nội: những điều cần biết | thuê xe điện hà nội cần biết | người đi làm | nội thành | 1300 | PASS |
| 22 | C-HONDA-WAVE | Thuê Honda Wave cho người mới: vì sao hay được chọn | thuê honda wave cho người mới | người mới | hà nội | 1100 | PASS |
| 23 | C-HONDA-VISION | Thuê Honda Vision đi làm nội đô: trải nghiệm thực tế | trải nghiệm thuê honda vision | người đi làm | nội thành | 1200 | PASS |
| 24 | C-HONDA-AIR-BLADE | Thuê Honda Air Blade chạy đường trường có đáng không | thuê air blade đường trường | phượt thủ | miền bắc | 1200 | PASS |
| 25 | C-YAMAHA-SIRIUS | Thuê Yamaha Sirius dài hạn: xe số bền cho người đi làm | thuê yamaha sirius dài hạn | người đi làm | hà nội | 1100 | PASS |
| 26 | C-GPLX | Bằng lái A1 điều khiển xe máy: phạm vi nào | bằng a1 lái được xe nào | người mới | việt nam | 1100 | REVIEW |
| 27 | C-GPLX | Đổi bằng lái nước ngoài sang bằng Việt Nam: hướng dẫn cơ bản | đổi bằng lái nước ngoài sang việt nam | người nước ngoài | việt nam | 1400 | REVIEW |
| 28 | C-BAO-HIEM | Bảo hiểm trách nhiệm dân sự với xe máy: khách thuê cần biết gì | bảo hiểm xe máy khi thuê | khách vãng lai | việt nam | 1300 | REVIEW |
| 29 | C-NOI-DO-CONG | Mũ bảo hiểm đạt chuẩn khi đi xe máy: chuẩn nào | mũ bảo hiểm đạt chuẩn | người mới | việt nam | 1200 | REVIEW |
| 30 | C-PHAT-NGUOI | Không mang bằng lái khi đang đi xe: có bị xử lý không | không mang bằng lái bị làm sao | người đi làm | việt nam | 1100 | REVIEW |
| 31 | C-QUY-DINH | Nồng độ cồn khi lái xe máy: quy định hiện hành cần nguồn chính thống | nồng độ cồn khi lái xe máy | người đi làm | việt nam | 1200 | REVIEW |
| 32 | C-DIEM-DEN | Lịch trình nửa ngày đi Hà Nội bằng xe máy: chọn lộ trình theo giờ | lịch trình nửa ngày hà nội xe máy | khách du lịch | nội thành | 1400 | PASS |
| 33 | C-DIEM-DEN | Ẩm thực Hà Nội theo cung đường xe máy: đi đâu ăn gì | ẩm thực hà nội theo cung đường | khách du lịch | nội thành | 1400 | PASS |
| 34 | C-BAO-TANG | Ghé bảo tàng Hà Nội bằng xe máy: giữ xe ở đâu | bảo tàng hà nội đi xe máy | khách du lịch | nội thành | 1100 | PASS |
| 35 | C-PHO-CO | Lái xe trong phố cổ giờ cấm: cần biết gì trước khi đi | đường phố cổ cấm xe máy | khách du lịch | phố cổ | 1200 | REVIEW |
| 36 | C-HO-TAY | Cung đường chạy quanh hồ Tây: điểm dừng và chỗ gửi xe | cung đường quanh hồ tây | khách du lịch | hồ tây | 1200 | PASS |
| 37 | C-LONG-BIEN | Cầu Long Biên và đường ven sông: trải nghiệm đi xe máy | cầu long biên đi xe máy | khách du lịch | long biên | 1200 | PASS |
| 38 | C-NGOAI-THANH | Đi xe máy ra ngoại thành Hà Nội cuối tuần: chọn hướng nào | đi ngoại thành hà nội bằng xe máy | cặp đôi | ngoại thành | 1300 | PASS |
| 39 | C-CD-CUOI-TUAN | Hà Nội đi Tam Cốc Tràng An bằng xe máy: cung đường và thời gian | hà nội đi tràng an bằng xe máy | phượt thủ | ninh bình | 1400 | PASS |
| 40 | C-CD-CUOI-TUAN | Hà Nội đi Tam Đảo bằng xe máy: lên dốc cần chuẩn bị gì | hà nội đi tam đảo bằng xe máy | phượt thủ | vĩnh phúc | 1400 | PASS |
| 41 | C-CD-CUOI-TUAN | Chùa Hương bằng xe máy từ Hà Nội: chuẩn bị trước khi đi | đi chùa hương bằng xe máy | phượt thủ | mỹ đức | 1300 | PASS |
| 42 | C-CD-CUOI-TUAN | Hà Nội đi Ba Vì cuối tuần bằng xe máy | hà nội đi ba vì bằng xe máy | phượt thủ | ba vì | 1300 | PASS |
| 43 | C-CD-CUOI-TUAN | Đường Lâm từ Hà Nội bằng xe máy | hà nội đi đường lâm bằng xe máy | cặp đôi | sơn tây | 1200 | PASS |
| 44 | C-CD-MAI-CHAU | Hà Nội đi Mai Châu bằng xe máy: chuẩn bị cung đường | hà nội đi mai châu bằng xe máy | phượt thủ | mai châu | 1400 | PASS |
| 45 | C-CD-MOC-CHAU | Hà Nội đi Mộc Châu bằng xe máy mùa hoa: lên đường lúc nào | hà nội đi mộc châu bằng xe máy | phượt thủ | mộc châu | 1400 | PASS |
| 46 | C-CD-HA-GIANG | Đi Hà Giang: thuê xe từ Hà Nội hay gửi xe lên rồi thuê tại chỗ | đi hà giang thuê xe ở đâu | phượt thủ | hà giang | 1400 | PASS |
| 47 | C-CD-PHO-BAC | Kinh nghiệm chạy các đèo phía Bắc khi thuê xe máy ở Hà Nội | chạy đèo phía bắc bằng xe máy | phượt thủ | miền bắc | 1500 | PASS |
| 48 | C-KY-NANG-CO-BAN | Đề xe và vào số 1: thao tác cơ bản cho người mới | cách đề xe số 1 | người mới | hà nội | 1100 | PASS |
| 49 | C-KY-NANG-CO-BAN | Lên dốc và xuống dốc bằng xe số khi mới lái | lên dốc xe số cách nào | người mới | hà nội | 1200 | PASS |
| 50 | C-KY-NANG-CO-BAN | Quay đầu xe trong ngõ phố cổ: mẹo cho xe máy | quay đầu xe trong ngõ nhỏ | người mới | phố cổ | 1000 | PASS |
| 51 | C-KY-NANG-TINH-HUONG | Kẹt xe giờ cao điểm nội thành: kỹ năng đi xe máy an toàn | đi xe máy giờ cao điểm | người đi làm | nội thành | 1200 | PASS |
| 52 | C-KY-NANG-TINH-HUONG | Đi xe máy qua đoạn ngập nước trong nội đô | đi xe máy qua đường ngập | người đi làm | nội thành | 1200 | PASS |
| 53 | C-KY-NANG-THOI-TIET | Mùa mưa Hà Nội: chuẩn bị gì khi đi xe máy thuê | đi xe máy mùa mưa chuẩn bị | người đi làm | hà nội | 1200 | PASS |
| 54 | C-KY-NANG-THOI-TIET | Nắng nóng mùa hè Hà Nội: đi xe máy cần chú ý gì | đi xe máy mùa hè nắng nóng | người đi làm | hà nội | 1100 | PASS |
| 55 | C-KY-NANG-THOI-TIET | Trời lạnh đi xe máy sáng sớm ở Hà Nội: chuẩn bị thế nào | đi xe máy trời lạnh | người đi làm | hà nội | 1100 | PASS |
| 56 | C-KY-NANG-CHO-DO | Gửi xe ở khu vực không có bãi giữ xe: phương án nào | gửi xe khi không có bãi | khách du lịch | nội thành | 1100 | PASS |
| 57 | C-KY-NANG-GUI-XE | Chống trộm xe máy khi thuê: khóa và cách đỗ xe | chống trộm xe máy thuê | khách vãng lai | hà nội | 1200 | PASS |
| 58 | C-HD-GIA | Thuê xe máy theo ngày: tiền xăng tính thế nào | thuê xe máy có bao gồm xăng không | khách vãng lai | hà nội | 1000 | PASS |
| 59 | C-HD-THU-TUC | Thuê xe máy cần bao nhiêu tuổi | thuê xe máy bao nhiêu tuổi | người mới | hà nội | 1000 | REVIEW |
| 60 | C-HD-PHAP-LY | Quên bằng lái khi đang đi xe thuê: làm gì ngay | quên bằng lái làm sao | người đi làm | việt nam | 1000 | REVIEW |
| 61 | C-HD-CHON-XE | Chỉ đi trong nội thành nên thuê xe máy loại nào | thuê xe máy đi nội thành | khách du lịch | nội thành | 1000 | PASS |
| 62 | C-HD-NGUOI-MOI | Lần đầu thuê xe máy: những lỗi người mới hay mắc | lỗi thường gặp khi thuê xe máy | người mới | hà nội | 1100 | PASS |
| 63 | C-HD-NGUOI-MOI | Chưa quen xe ga: làm quen trong 30 phút trước khi lên đường | làm quen xe ga nhanh | người mới | hà nội | 1100 | PASS |
| 64 | C-THUE-DOI-TUONG | Thuê xe máy dài hạn cho người đi làm trong nội thành | thuê xe máy dài hạn cho người đi làm | người đi làm | nội thành | 1300 | PASS |
| 65 | C-THUE-DOI-TUONG | Thuê xe máy cho cặp đôi đi chơi cuối tuần | thuê xe máy cho hai người đi chơi | cặp đôi | hà nội | 1200 | PASS |
| 66 | C-THUE-DOI-TUONG | Thuê xe máy cho gia đình có trẻ nhỏ đi cùng | thuê xe máy cho gia đình có trẻ nhỏ | gia đình | hà nội | 1300 | PASS |
| 67 | C-THUE-DOI-TUONG | Thuê xe máy cho người mới lấy bằng A1 lần đầu | thuê xe máy cho người mới có bằng a1 | người mới | hà nội | 1200 | PASS |
| 68 | C-THUE-DOI-TUONG | Người cao tuổi đi xe máy thuê: nên chọn xe như thế nào | người cao tuổi đi xe máy chọn xe nào | người cao tuổi | hà nội | 1200 | PASS |
| 69 | C-THUE-DOI-TUONG | Thuê xe máy cho người từ tỉnh ra Hà Nội công tác | thuê xe máy khi ra hà nội công tác | khách công tác | hà nội | 1200 | PASS |
| 70 | C-THUE-DOI-TUONG | Thuê xe máy cho nhóm bạn đi phýt cuối tuần | thuê xe máy cho nhóm đi phượt | nhóm bạn | hà nội | 1300 | PASS |
| 71 | C-THUE-DOI-TUONG | Cần xe gấp trong ngày: thuê xe máy ngay có khó không | thuê xe máy gấp trong ngày | khách vội | hà nội | 1000 | PASS |
| 72 | C-THUE-DIA-DIEM | Thuê xe máy gần ga Hà Nội: lấy xe sớm nhất lúc nào | thuê xe máy gần ga hà nội | khách du lịch | ga hà nội | 1100 | PASS |
| 73 | C-THUE-DIA-DIEM | Đi sân bay Nội Bài: nên thuê xe máy từ đâu và lúc nào | thuê xe máy đi sân bay nội bài | khách du lịch | nội bài | 1300 | PASS |
| 74 | C-THUE-DIA-DIEM | Thuê xe máy gần bến xe Mỹ Đình: những điều cần biết | thuê xe máy gần bến xe mỹ định | khách công tác | bến xe mỹ định | 1100 | PASS |
| 75 | C-THUE-DIA-DIEM | Thuê xe máy gần bến xe Giáp Bát cho chuyến về tỉnh | thuê xe máy gần bến xe giáp bát | khách công tác | bến giáp bát | 1000 | PASS |
| 76 | C-THUE-DIA-DIEM | Thuê xe máy ở khu phố cổ: giữ xe và đường cấm cần biết | thuê xe máy phố cổ hà nội | khách du lịch | phố cổ | 1300 | PASS |
| 77 | C-THUE-DIA-DIEM | Thuê xe máy quanh hồ Gươm dịp cuối tuần | thuê xe máy quanh hồ gươm | khách du lịch | hồ gươm | 1100 | PASS |
| 78 | C-THUE-DIA-DIEM | Chạy vòng hồ Tây bằng xe máy thuê: cung đường và điểm dừng | chạy vòng hồ tây bằng xe máy | khách du lịch | hồ tây | 1200 | PASS |
| 79 | C-THUE-DIA-DIEM | Thuê xe máy ở khu Long Biên, ven sông Hồng | thuê xe máy long biên | người đi làm | long biên | 1100 | PASS |
| 80 | C-THUE-DIA-DIEM | Thuê xe máy khu vực Gia Lâm, phía Đông Hà Nội | thuê xe máy gia lâm | người đi làm | gia lâm | 1000 | PASS |
| 81 | C-XE-LUA-CHON | Xe số hay xe ga cho người mới biết lái khi thuê | xe số hay xe ga cho người mới | người mới | hà nội | 1300 | PASS |
| 82 | C-XE-LUA-CHON | Thuê xe điện hay xe xăng khi đi trong nội đô Hà Nội | thuê xe điện hay xe xăng | người đi làm | nội thành | 1400 | PASS |
| 83 | C-XE-LUA-CHON | Chưa có bằng lái: thuê xe 50cc hay chờ lấy bằng A1 | chưa có bằng lái thuê xe gì | người mới | hà nội | 1200 | REVIEW |
| 84 | C-XE-LUA-CHON | Chọn xe theo chiều cao: yên xe bao nhiêu là vừa | chọn xe máy theo chiều cao | người mới | hà nội | 1100 | PASS |
| 85 | C-XE-LUA-CHON | Thuê xe máy chở người thứ hai cần lưu ý gì | thuê xe máy chở hai người | cặp đôi | hà nội | 1200 | PASS |
| 86 | C-XE-LUA-CHON | Đi chở hành lý cồng kềnh nên thuê loại xe nào | thuê xe máy chở hành lý | khách du lịch | hà nội | 1100 | PASS |
| 87 | C-XE-LUA-CHON | Xe ga tiết kiệm xăng khi đi nội đô là dòng nào | xe ga tiết kiệm xăng nội đô | người đi làm | nội thành | 1200 | PASS |
| 88 | C-XE-LUA-CHON | Đi đường trường: thuê xe số hay xe ga | đi đường trường thuê xe gì | phượt thủ | miền bắc | 1200 | PASS |
| 89 | C-XE-LUA-CHON | Có nên thuê xe cao cấp khi chỉ đi phố cổ | có nên thuê xe cao cấp sh | khách du lịch | phố cổ | 1100 | PASS |
| 90 | C-XE-LUA-CHON | Mùa mưa lớn nên thuê dòng xe máy nào | mùa mưa nên thuê xe gì | người đi làm | hà nội | 1100 | PASS |
| 91 | C-XE-KHAC-PHUC | Xe máy thuê không nổ máy: xử lý từng bước | xe máy thuê không nổ máy | người mới | hà nội | 1300 | PASS |
| 92 | C-XE-KHAC-PHUC | Đang đi xe thuê bị xịt lốp: làm gì ngay | xe máy bị xịt lốp giữa đường | người mới | hà nội | 1200 | PASS |
| 93 | C-XE-KHAC-PHUC | Mất chìa khóa xe máy thuê: các bước tiếp theo | mất chìa khóa xe máy thuê | khách vãng lai | hà nội | 1200 | PASS |
| 94 | C-XE-KHAC-PHUC | Ắc quy xe thuê yếu, đề không nổ: nhận biết và xử lý | ắc quy xe máy yếu đề không nổ | người đi làm | hà nội | 1200 | PASS |
| 95 | C-XE-KHAC-PHUC | Xe thuê chết máy khi trời mưa: nguyên nhân thường gặp | xe máy chết máy khi trời mưa | người đi làm | hà nội | 1200 | PASS |
| 96 | C-XE-KHAC-PHUC | Đèn pha xe thuê không sáng khi đi đêm: kiểm tra gì | đèn pha xe máy không sáng | người mới | hà nội | 1100 | PASS |
| 97 | C-XE-KHAC-PHUC | Xe thuê rung giật khi tăng tốc: có nên tiếp tục đi | xe máy rung giật khi tăng tốc | người đi làm | hà nội | 1100 | PASS |
| 98 | C-XE-KHAC-PHUC | Phanh xe thuê yếu và có tiếng kêu: xử lý thế nào | phanh xe máy yếu có tiếng kêu | người mới | hà nội | 1200 | PASS |
| 99 | C-XE-KHAC-PHUC | Nhận nhầm xe so với xe đã đặt: đổi xe thế nào | nhận nhầm xe thuê làm sao | khách vãng lai | hà nội | 1100 | PASS |
| 100 | C-XE-KHAC-PHUC | Báo cửa hàng ngay khi nào trong lúc thuê xe | khi nào cần báo cửa hàng thuê xe | người mới | hà nội | 1100 | PASS |
| 101 | C-XE-SO-SANH | Honda Wave và Yamaha Sirius: thuê dòng nào | so sánh wave và sirius | người mới | hà nội | 1300 | PASS |
| 102 | C-XE-SO-SANH | Honda Vision và Honda Air Blade: thuê dòng nào phù hợp | so sánh vision và air blade | người đi làm | hà nội | 1300 | PASS |
| 103 | C-XE-SO-SANH | Thuê theo ngày và thuê theo tuần: chi phí khác nhau thế nào | thuê xe ngày hay tuần rẻ hơn | khách du lịch | hà nội | 1200 | PASS |
| 104 | C-XE-SO-SANH | Thuê xe máy và đi taxi/ứng dụng: chi phí đi lại nội thành | thuê xe máy hay taxi rẻ hơn | người đi làm | nội thành | 1400 | PASS |
| 105 | C-XE-SO-SANH | Thuê theo tháng 3 tháng và 1 tháng: nên chọn kiểu nào | thuê xe 3 tháng hay 1 tháng | người nước ngoài | hà nội | 1200 | PASS |
| 106 | C-XE-SO-SANH | Mùa cao điểm và mùa thấp điểm: giá thuê khác nhau ra sao | giá thuê xe theo mùa | khách du lịch | hà nội | 1100 | PASS |
| 107 | C-XE-SO-SANH | Thuê xe tự lái hay đi xe ôm công nghệ trong nội đô | thuê tự lái hay xe ôm | người đi làm | nội thành | 1200 | PASS |
| 108 | C-XE-SO-SANH | So sánh đặt cọc giữa các hình thức thuê xe máy | đặt cọc thuê xe máy các hình thức | khách vãng lai | hà nội | 1100 | PASS |
| 109 | C-XE-SO-SANH | Chi phí chạy xe điện và xe xăng khi thuê theo tháng | chi phí xe điện và xe xăng | người đi làm | hà nội | 1300 | PASS |
