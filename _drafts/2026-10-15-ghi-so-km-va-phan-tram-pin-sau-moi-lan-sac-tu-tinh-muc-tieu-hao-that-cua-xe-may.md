---
date: 2026-10-15 09:00:00 +0700
layout: post
title: "Ghi số km và phần trăm pin sau mỗi lần sạc: tự tính mức tiêu hao thật của xe máy điện đang thuê"
author: "Nguyễn Tú"
description: "Tự tính mức tiêu hao pin xe máy điện đang thuê: ghi ODO và phần trăm pin trước, sau mỗi lần sạc, chia ra km cho mỗi 1% pin rồi lên lịch sạc sát thực tế."
categories: [Kinh nghiệm]
lang: vi
tags: [mức tiêu hao pin xe máy điện, mỗi phần trăm pin đi bao nhiêu km, nhật ký sạc xe điện, xe máy điện]
permalink: /xe-may/2026/10/15/ghi-so-km-va-phan-tram-pin-sau-moi-lan-sac-tu-tinh-muc-tieu-hao-that-cua-xe-may/
parent_id: P-XE-MAY
child_id: C-XE-DIEN
article_id: BLG-03823
writer: W3
writer_session: s-claude-w3
---

Thuê xe điện theo tuần hay theo tháng, sớm muộn bạn cũng hỏi: với cách mình chạy, mức tiêu hao pin xe máy điện thật sự là bao nhiêu? Con số trên tờ giới thiệu được đo trong điều kiện lý tưởng, còn xe của bạn ngày nào cũng qua cầu, kẹt xe giờ tan tầm. Cách chắc nhất là ghi một cuốn sổ nhỏ trong vài ngày, rồi tự chia ra mỗi phần trăm pin đi được bao xa.

## Vì sao nên tự đo mức tiêu hao pin xe máy điện thay vì tin thông số

Thông số quãng đường của một mẫu xe thường ứng với điều kiện thuận lợi: người lái nhẹ, đường phẳng, tốc độ đều. Ở Hà Nội hiếm ngày nào được như vậy. Đi từ Long Biên sang Hoàn Kiếm giờ cao điểm, xe dừng đi liên tục; lên dốc cầu Vĩnh Tuy hay cầu Chương Dương, động cơ phải gắng sức; trưa hè đỗ ngoài nắng, pin nóng lên.

Xe thuê lại là xe đã qua sử dụng, pin có thể không còn giữ điện như lúc mới. Con số đáng tin nhất là con số đo trên chính chiếc xe đó, với chính cách bạn chạy. Các yếu tố làm quãng đường thay đổi được nói kỹ trong bài [quãng đường một lần sạc của xe máy điện](/xe-may/2026/09/27/quang-uong-mot-lan-sac-cua-xe-may-ien/).

## Cần ghi những gì: nhật ký sạc xe điện gồm sáu cột

Một nhật ký sạc xe điện chỉ cần sáu thông tin cho mỗi lượt đi giữa hai lần sạc:

- **Ngày**: để đối chiếu với thời tiết và lịch đi lại.
- **ODO lúc đi và lúc về**: số tổng km trên đồng hồ. Dùng ODO thay vì bộ đếm hành trình vì ODO không bị đặt lại nhầm.
- **Phần trăm pin trước**: đọc ngay khi rút sạc.
- **Phần trăm pin sau**: đọc khi chuẩn bị cắm sạc lại.
- **Quãng đường**: ODO lúc về trừ ODO lúc đi.
- **Điều kiện đường**: vài chữ như "phố đông, kẹt", "đê thoáng", "chở hai người", "trưa nắng".

Cột cuối nhiều người bỏ qua, nhưng chính nó giải thích vì sao có ngày xe đi xa, có ngày lại hụt hơi.

Ghi ở ghi chú điện thoại, bảng tính hay cuốn sổ trong cốp đều được. Mẹo tiện nhất là chụp ảnh đồng hồ mỗi lần rút sạc và cắm sạc: ảnh có sẵn giờ, ODO và phần trăm pin, tối về chép lại chỉ mất một phút.

## Đọc số cho đúng lúc để sổ không bị lệch

Phần trăm pin trên đồng hồ là con số ước tính, dao động theo tải. Đọc lúc đang vặn ga lên dốc, số sẽ thấp hơn thực tế; nghỉ vài phút, số lại nhích lên. Bài [đồng hồ pin xe điện nhảy không đều](/xe-may/2026/10/11/ong-ho-pin-xe-ien-nhay-khong-eu-cach-uoc-luong-km-con-lai-cho-ung/) giải thích hiện tượng này. Để sổ nhất quán:

1. **Đọc khi xe đứng yên**, đã bật nguồn và chờ màn hình ổn định.
2. **Đọc ở cùng thời điểm**: ngay sau khi rút sạc và ngay trước khi cắm sạc.
3. **Đánh dấu lần rút sạc giữa chừng**, vì mức đầu ngày khi đó không phải mức đầy.
4. **Gộp các chuyến ngắn.** Đi chợ vài km chỉ làm pin tụt vài phần trăm, sai số màn hình sẽ lấn át kết quả. Tính cả ngày thành một lượt, từ lúc rút sạc tới lúc cắm lại.

## Mỗi phần trăm pin đi bao nhiêu km: cách tính từ sổ

Lấy quãng đường chia cho số phần trăm pin đã dùng, tức phần trăm trước trừ phần trăm sau. Kết quả cho biết mỗi phần trăm pin đi bao nhiêu km trong điều kiện của lượt đó.

Dưới đây là **ví dụ giả định** để minh họa. Các con số được đặt ra cho dễ hiểu, không phải số đo của bất kỳ mẫu xe nào, kể cả xe ở tiệm.

| Ngày | ODO đi → về | Pin trước → sau | Quãng đường | Điều kiện đường | Km cho 1% pin |
|---|---|---|---|---|---|
| Thứ Hai | 2310 → 2346 | 100% → 58% | 36 km | Long Biên sang Hoàn Kiếm qua cầu Chương Dương, kẹt giờ tan tầm | khoảng 0,86 |
| Thứ Ba | 2346 → 2371 | 58% → 24% | 25 km | Chở thêm một người, lên dốc cầu Vĩnh Tuy | khoảng 0,74 |
| Thứ Tư | 2371 → 2410 | 100% → 60% | 39 km | Đường đê thoáng phía Gia Lâm, chạy đều | khoảng 0,98 |
| Thứ Năm | 2410 → 2442 | 60% → 22% | 32 km | Trưa nắng, phố đông quanh Cầu Giấy | khoảng 0,84 |

Trong ví dụ này, bốn ngày xe đi 132 km và dùng tổng cộng 154 phần trăm pin (có một lần sạc đầy tối thứ Ba). Chia ra, trung bình khoảng 0,86 km cho mỗi phần trăm. Đáng chú ý hơn là khoảng dao động: thấp nhất khoảng 0,74 khi chở hai người lên cầu, cao nhất gần 0,98 khi chạy một mình trên đường thoáng.

Khi tính trung bình, hãy cộng tổng km và tổng phần trăm rồi mới chia, đừng lấy trung bình bốn con số ở cột cuối, vì lượt dài phải nặng ký hơn lượt ngắn.

## Dùng kết quả để lên kế hoạch sạc sát thực tế

Nguyên tắc: ngày nào giống điều kiện xấu thì lấy mức thấp trong sổ, và luôn giữ một khoảng pin dự phòng không đụng tới.

Tiếp tục ví dụ giả định. Sáng nay pin còn 70%, bạn định đi từ Long Biên lên Tây Hồ rồi về, chừng 40 km, có chở thêm người. Giữ 20% dự phòng, phần dùng được là 50%; nhân với mức thấp khoảng 0,74 thì được chừng 37 km, tức là thiếu. Kết luận: sạc thêm trước khi đi, đừng đi rồi mới tính.

Sổ còn giúp bạn:

- **Chọn nhịp sạc trong tuần.** Biết mỗi ngày đi làm tốn bao nhiêu phần trăm, bạn tính được nên sạc mỗi tối hay cách một tối.
- **Nhận ra thói quen tốn pin.** Nếu ngày ghi "kẹt xe" luôn thấp hẳn, có thể bạn đang vặn ga gắt mỗi lần xe nhích lên. Đổi cách chạy rồi ghi tiếp để so.
- **Chuẩn bị chuyến xa.** Trước khi ra khỏi nội thành, đọc thêm bài [lo hết pin giữa đường: cách tính quãng đường trong ngày](/xe-may/2026/10/14/lo-het-pin-giua-duong-khi-thue-xe-dien-cach-tinh-quang-duong-trong-ngay/).

## Khi sổ cho thấy điều bất thường

Sau một hai tuần, các lượt cùng điều kiện thường cho kết quả khá gần nhau. Nếu km cho mỗi phần trăm bỗng tụt hẳn dù bạn vẫn đi cung đường cũ, chở như cũ, hoặc pin sạc mãi không lên đầy, đó là tín hiệu cần để ý.

Lúc đó đừng tự mở hộp pin hay thử bộ sạc lạ. Chụp vài trang sổ và báo cho tiệm: số liệu đều đặn giúp cửa hàng nhanh chóng khoanh vùng do pin, bộ sạc hay cách đi. Mẫu xe nào hợp nhu cầu, giá thuê ra sao, bạn nên hỏi trực tiếp; giá thuê xe máy điện ở tiệm là liên hệ để xác nhận.

## Gói gọn

Ghi ODO và phần trăm pin trước, sau mỗi lần sạc, thêm một dòng điều kiện đường; làm trong một tuần là có con số tiêu hao thật của chiếc xe mình thuê. Dùng mức thấp cho ngày khó, giữ dự phòng, sạc trước khi thiếu. Xem thêm chuyên mục [xe máy điện](/xe-may/xe-dien/) và trang tổng hợp [kinh nghiệm xe máy](/xe-may/).
