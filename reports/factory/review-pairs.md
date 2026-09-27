# Phân tích 10 hàng legacy REVIEW (cặp nghi cannibalization)

Ngày phân tích: 2026-09-27. Phương pháp: đối chiếu trực tiếp nội dung hai bài
trong mỗi cặp — tiêu đề, description, cấu trúc H2, từ khóa, ý định tìm kiếm,
child hub. KHÔNG tự động chuyển PASS; mọi hàng giữ nguyên REVIEW trong matrix
cho tới khi chủ xe quyết định. Không xóa bài nào.

## Cặp 1 — An toàn đường trường vs tổng quan an toàn (C-KY-NANG-TINH-HUONG)

- BLG-00005 "An toàn khi chạy xe đường trường" (1.618 từ): tốc độ/khoảng cách
  đường trường, vượt xe, mặt đường xấu, mệt mỏi chặng dài, xe hỏng giữa đường.
- BLG-00053 "An toàn khi chạy xe máy ở Hà Nội: tổng quan" (1.614 từ): bảo hộ
  cá nhân, đọc dòng giao thông Hà Nội, lái phòng thủ, tình huống phố.
- Kết luận: **SAFE_DISTINCT** — một bài về ngữ cảnh đường trường ngoài thành,
  một bài về tổng quan trong phố. Mục "tình huống" giao nhau nhẹ nhưng trọng
  tâm khác. Nên cross-link hai bài cho nhau.

## Cặp 2 — Mùa đông vs ngày mưa (C-KY-NANG-THOI-TIET)

- BLG-00017 "Đi xe máy ở Hà Nội mùa đông": giữ ấm theo lớp, gió mùa bắc,
  thời điểm xuất phát.
- BLG-00018 "Đi xe máy ở Hà Nội ngày mưa": đồ mưa, phanh/lốp ướt, phanh trên
  đường ướt, vùng ngập.
- Kết luận: **SAFE_DISTINCT** — hai điều kiện thời tiết khác nhau, từ khóa
  khác nhau, không cạnh tranh nhau.

## Cặp 3 — Đổi xe giữa kỳ thuê (C-THUE-THU-TUC) — TRÙNG Ý ĐỊNH THẬT

- BLG-00227 "Đổi xe giữa kỳ thuê khi có việc đổi" (1.611 từ).
- BLG-00228 "Đổi xe giữa kỳ thuê ở Hà Nội: khi nào cần và cách làm đúng" (1.659 từ).
- Bằng chứng trùng: cùng ý định ("cách đổi xe giữa kỳ thuê"), cấu trúc H2 gần
  trùng nhau (tình huống cần đổi, trao đổi với nơi cho thuê, kiểm tra xe mới,
  khi không nên đổi), cùng child, cùng từ khóa chính.
- Kết luận: **MERGE_CANDIDATE** — hai bài cạnh tranh từ khóa và vị trí.
  Đề xuất: chọn một làm **CANONICAL_OWNER** (bài mới hơn 00228 vì mô tả đầy đủ
  hợp đồng/cọc), hợp nhất phần giá trị của 00227 vào 00228 rồi redirect 00227.
  CẦN CHỦ XE DUYỆT — không tự gộp, không tự xóa. Cho tới khi đó: **KEEP_REVIEW**
  cả hai.

## Cặp 4 — Ảnh cưới dã ngoại vs ảnh kỷ yếu nhóm (C-DIEM-DEN)

- BLG-00410 "Thuê xe máy đi chụp ảnh cưới dã ngoại": váy cưới, thỏa thuận
  studio, lịch nhiều điểm.
- BLG-00411 "Thuê xe máy đi chụp ảnh kỷ yếu nhóm bạn": xe đồng bộ, xếp đoàn,
  đạo cụ.
- Kết luận: **SAFE_DISTINCT** — hai kịch bản chụp ảnh khác đối tượng và khác
  yêu cầu xe.

## Cặp 5 — Nhóm/gia đình vs nữ (C-KY-NANG-CO-BAN)

- BLG-00423 "Thuê xe máy ở Hà Nội cho nhóm bạn và gia đình": số xe, người lớn
  tuổi/trẻ nhỏ.
- BLG-00424 "Thuê xe máy ở Hà Nội cho nữ": dòng xe nhẹ, tuyến thân thiện, giữ đồ.
- Kết luận: **SAFE_DISTINCT** — hai nhóm độc giả khác nhau.

## Tổng kết

| Cặp | Hàng | Kết luận | Hành động |
|---|---|---|---|
| 1 | BLG-00005, BLG-00053 | SAFE_DISTINCT | giữ REVIEW chờ chủ xe duyệt chuyển EXISTING; cross-link |
| 2 | BLG-00017, BLG-00018 | SAFE_DISTINCT | như trên |
| 3 | BLG-00227, BLG-00228 | MERGE_CANDIDATE | **owner decision** chọn canonical + redirect; trước đó KEEP_REVIEW |
| 4 | BLG-00410, BLG-00411 | SAFE_DISTINCT | như cặp 1 |
| 5 | BLG-00423, BLG-00424 | SAFE_DISTINCT | như cặp 1 |

8/10 hàng có bằng chứng phân biệt rõ (SAFE_DISTINCT) — sẵn sàng chuyển EXISTING
khi chủ xe duyệt. 2/10 (cặp đổi xe) là ứng viên gộp thật, cần quyết định chủ xe.
Matrix giữ nguyên 10 hàng REVIEW — validator tiếp tục kiểm đúng 10 hàng này.
