# Kế hoạch xử lý trùng intent (cannibalization) — DỰ THẢO, chưa thực hiện

Nguồn: `data/content-matrix.csv` (`cannibalization_key` trùng — FACT) và heuristic tiêu đề gần trùng trong cùng cụm (INFERRED).
Sinh bởi `scripts/seo/build-matrix.py`. Mọi URL giữ nguyên; không xóa bài; không redirect khi chưa có quyết định của chủ.

Cách xử lý đề xuất: (1) giữ **URL chủ lực** chọn theo INTENT (sổ `scripts/seo/cannibalization-leads.json`, quy tắc Q/H/C/K, không theo độ dài bài;
nhóm chưa có trong sổ tạm lấy bài dài nhất và bị báo là LONGEST_FALLBACK); (2) bài còn lại làm bài bổ trợ, phân biệt intent rõ hơn
trong một đợt bảo trì nhỏ có QA (đổi góc nhìn ở phần mở đầu/heading, không đổi URL/slug); (3) thêm liên kết ngữ cảnh hai chiều
giữa các bài trong nhóm; (4) chỉ khi chủ duyệt mới xét gộp nội dung + `redirect_from` (plugin được GitHub Pages hỗ trợ),
kèm bằng chứng và cơ chế bảo toàn URL.

Tổng quan (FACT): **50** nhóm trùng khóa matrix, trong đó **0** nhóm nằm trong cùng một cụm
(công cụ sinh matrix chặn trùng trong cùng cụm; các nhóm trùng đều giữa HAI CỤM KHÁC NHAU, nên URL hai bài nằm ở hai hub khác nhau).
Cặp tiêu đề gần trùng trong cùng cụm (INFERRED): **82** dòng.

## A. Nhóm trùng khóa giữa các cụm (30 nhóm lớn nhất)

### `gia han thue xe may` (4 bài)
- **URL chủ lực đề xuất** — Gia hạn thời gian thuê xe máy thêm ngày xử lý thế nào (cụm `C-THUE-THU-TUC`, 1260 từ, `/thue-xe/2026/10/10/gia-han-thoi-gian-thue-xe-may-them-ngay-xu-ly-the-nao/`)
- bổ trợ — Gia hạn thời gian thuê xe máy khi kéo dài chuyến đi ở Hà Nội: báo chủ xe sớm thế nào (cụm `C-THUE-QUOC-TE`, 1252 từ, `/thue-xe/2026/10/14/gia-han-thoi-gian-thue-xe-may-khi-keo-dai-chuyen-di-o-ha-noi-bao-chu-xe-som-the/`)
- bổ trợ — Gia hạn hợp đồng thuê xe theo tháng (cụm `C-THUE-THANG`, 1141 từ, `/thue-xe/2026/09/27/gia-han-hop-dong-thue-xe-theo-thang/`)
- bổ trợ — Gia hạn thuê xe máy thêm ngày: thông báo đúng lúc (cụm `C-THUE-NHAN-TRA`, 1053 từ, `/thue-xe/2026/10/11/gia-han-thue-xe-may-them-ngay-thong-bao-dung-luc/`)

### `mat chia khoa xe may thue` (4 bài)
- bổ trợ — Mất chìa khóa xe máy thuê ở Hà Nội: khách quốc tế nên làm gì trước khi gọi chủ xe (cụm `C-THUE-QUOC-TE`, 1288 từ, `/thue-xe/2026/10/14/mat-chia-khoa-xe-may-thue-o-ha-noi-khach-quoc-te-nen-lam-gi-truoc-khi-goi-chu-xe/`)
- bổ trợ — Chìa khóa xe thuê: hỏi chìa phụ và cách báo khi lỡ làm mất (cụm `C-THUE-THU-TUC`, 1272 từ, `/thue-xe/2026/10/11/chia-khoa-xe-thue-hoi-chia-phu-va-cach-bao-khi-lo-lam-mat/`)
- bổ trợ — Làm mất chìa khóa xe thuê trước ngày trả: báo sớm, không tự đánh chìa và chuẩn bị gì (cụm `C-THUE-NHAN-TRA`, 1254 từ, `/thue-xe/2026/10/14/lam-mat-chia-khoa-xe-thue-truoc-ngay-tra-bao-som-khong-tu-danh-chia-va-chuan-bi/`)
- **URL chủ lực đề xuất** — Mất chìa khóa xe máy thuê: các bước tiếp theo (cụm `C-XE-KHAC-PHUC`, 1045 từ, `/xe-may/2026/09/29/mat-chia-khoa-xe-may-thue-cac-buoc-tiep-theo/`)

### `thue vision hay air blade` (4 bài)
- bổ trợ — Thuê Vision hay Air Blade ở Hà Nội: so sánh tư thế ngồi, cốp xe và cảm giác lái trong phố (cụm `C-XE-GA`, 1382 từ, `/xe-may/2026/10/14/thue-vision-hay-air-blade-o-ha-noi-so-sanh-tu-the-ngoi-cop-xe-va-cam-giac-lai-tr/`)
- **URL chủ lực đề xuất** — Vision hay Air Blade: thuê xe ga nào hợp đi phố Hà Nội hơn (cụm `C-XE-LUA-CHON`, 1363 từ, `/xe-may/2026/10/14/vision-hay-air-blade-thue-xe-ga-nao-hop-di-pho-ha-noi-hon/`)
- bổ trợ — Thuê Honda Vision hay Air Blade cho chuyến du lịch Hà Nội: chọn theo lộ trình và người ngồi sau (cụm `C-HONDA-VISION`, 1177 từ, `/xe-may/2026/10/14/thue-honda-vision-hay-air-blade-cho-chuyen-du-lich-ha-noi-chon-theo-lo-trinh-va/`)
- bổ trợ — Nên thuê Vision hay Air Blade khi đi phố (cụm `C-HD-CHON-XE`, 1124 từ, `/hoi-dap/2026/09/30/nen-thue-vision-hay-air-blade-khi-di-pho/`)

### `chuot can day ien xe may` (3 bài)
- bổ trợ — Chuột cắn dây điện xe thuê để trong ngõ hoặc nhà trọ: dấu hiệu và vì sao không nên tự nối (cụm `C-HD-SU-CO`, 1295 từ, `/hoi-dap/2026/10/16/chuot-can-day-dien-xe-thue-de-trong-ngo-hoac-nha-tro-dau-hieu-va-vi-sao-khong-ne/`)
- bổ trợ — Chuột cắn dây điện xe máy để qua đêm ở nhà trọ: dấu hiệu nhận biết và cách phòng khi đang thuê theo tháng (cụm `C-THUE-THANG`, 1275 từ, `/thue-xe/2026/10/15/chuot-can-day-dien-xe-may-de-qua-dem-o-nha-tro-dau-hieu-nhan-biet-va-cach-phong/`)
- **URL chủ lực đề xuất** — Chuột cắn dây điện xe thuê để qua đêm ở nhà trọ: dấu hiệu nhận biết và cách báo cửa hàng (cụm `C-THUE-SU-CO`, 1071 từ, `/thue-xe/2026/10/15/chuot-can-day-dien-xe-thue-de-qua-dem-o-nha-tro-dau-hieu-nhan-biet-va-cach-bao-c/`)

### `i thanh co loa bang xe may` (3 bài)
- **URL chủ lực đề xuất** — Thành Cổ Loa bằng xe máy từ nội thành: đường đi và nên ghé những điểm nào (cụm `C-DIEM-DEN`, 1240 từ, `/du-lich/2026/10/11/thanh-co-loa-bang-xe-may-tu-noi-thanh-duong-di-va-nen-ghe-nhung-diem-nao/`)
- bổ trợ — Cổ Loa bằng xe máy: từ nội thành tới khu di tích, đi đường nào và ghé điểm nào (cụm `C-BAO-TANG`, 1055 từ, `/du-lich/2026/10/13/co-loa-bang-xe-may-tu-noi-thanh-toi-khu-di-tich-di-duong-nao-va-ghe-diem-nao/`)
- bổ trợ — Đi thành Cổ Loa bằng xe máy: cung đường và lưu ý chạy xe (cụm `C-NGOAI-THANH`, 1034 từ, `/du-lich/2026/10/01/di-thanh-co-loa-bang-xe-may-cung-duong-va-luu-y-chay-xe/`)

### `mat chia khoa xe thue` (3 bài)
- bổ trợ — Mất chìa khóa xe thuê: các bước xử lý nhanh (cụm `C-HD-SU-CO`, 1219 từ, `/hoi-dap/2026/10/10/mat-chia-khoa-xe-thue-cac-buoc-xu-ly-nhanh/`)
- bổ trợ — Mất chìa khóa xe thuê: những việc cần làm ngay (cụm `C-XE-KHAC-PHUC`, 1166 từ, `/xe-may/2026/10/01/mat-chia-khoa-xe-thue-nhung-viec-can-lam-ngay/`)
- **URL chủ lực đề xuất** — Mất chìa khóa xe thuê nên làm gì (cụm `C-THUE-SU-CO`, 1141 từ, `/thue-xe/2026/10/07/mat-chia-khoa-xe-thue-nen-lam-gi/`)

### `bao tang ha noi i xe may` (2 bài)
- bổ trợ — Ghé bảo tàng trong trung tâm Hà Nội bằng xe máy (cụm `C-DIEM-DEN`, 1091 từ, `/du-lich/2026/10/10/ghe-bao-tang-trong-trung-tam-ha-noi-bang-xe-may/`)
- **URL chủ lực đề xuất** — Ghé bảo tàng Hà Nội bằng xe máy: giữ xe ở đâu (cụm `C-BAO-TANG`, 946 từ, `/du-lich/2026/09/28/ghe-bao-tang-ha-noi-bang-xe-may-giu-xe-o-dau/`)

### `cach tinh ngay thue xe may` (2 bài)
- bổ trợ — Một ngày thuê xe máy tính theo 24 giờ hay theo ngày lịch: nên hỏi gì (cụm `C-THUE-THU-TUC`, 1078 từ, `/thue-xe/2026/10/11/mot-ngay-thue-xe-may-tinh-theo-24-gio-hay-theo-ngay-lich-nen-hoi-gi/`)
- **URL chủ lực đề xuất** — Hỏi: cách tính ngày thuê xe máy như thế nào (cụm `C-HD-GIA`, 1022 từ, `/hoi-dap/2026/10/10/hoi-cach-tinh-ngay-thue-xe-may-nhu-the-nao/`)

### `cau long bien i xe may` (2 bài)
- bổ trợ — Từ phố cổ lên cầu Long Biên bằng xe máy: lối lên cầu, chợ Long Biên và chỗ dừng chụp ảnh (cụm `C-PHO-CO`, 1378 từ, `/du-lich/2026/10/15/tu-pho-co-len-cau-long-bien-bang-xe-may-loi-len-cau-cho-long-bien-va-cho-dung-ch/`)
- **URL chủ lực đề xuất** — Cầu Long Biên và đường ven sông: trải nghiệm đi xe máy (cụm `C-LONG-BIEN`, 1071 từ, `/du-lich/2026/09/28/cau-long-bien-va-duong-ven-song-trai-nghiem-di-xe-may/`)

### `chay xe quanh ho linh am` (2 bài)
- **URL chủ lực đề xuất** — Chạy xe quanh hồ Linh Đàm sáng sớm: cung đường ngắn trong thành phố (cụm `C-CD-NOI-THANH`, 1125 từ, `/cung-duong/2026/10/10/chay-xe-quanh-ho-linh-dam-sang-som-cung-duong-ngan-trong-thanh-pho/`)
- bổ trợ — Chạy xe quanh hồ Linh Đàm buổi chiều và chỗ để xe (cụm `C-DIEM-DEN`, 1042 từ, `/du-lich/2026/10/04/chay-xe-quanh-ho-linh-dam-buoi-chieu-va-cho-de-xe/`)

### `chup anh xe khi nhan thue` (2 bài)
- bổ trợ — Chụp ảnh và quay video xe khi nhận thuê tuần: những góc cần ghi lại để trả xe nhẹ nhàng (cụm `C-THUE-TUAN`, 1189 từ, `/thue-xe/2026/10/14/chup-anh-va-quay-video-xe-khi-nhan-thue-tuan-nhung-goc-can-ghi-lai-de-tra-xe-nhe/`)
- **URL chủ lực đề xuất** — Chụp lại tình trạng xe khi nhận: các góc ảnh nên có (cụm `C-THUE-THU-TUC`, 1099 từ, `/thue-xe/2026/10/04/chup-lai-tinh-trang-xe-khi-nhan-cac-goc-anh-nen-co/`)

### `chuyen tu xe so sang xe ga` (2 bài)
- **URL chủ lực đề xuất** — Chuyển từ xe số sang xe tay ga: những thói quen cũ cần bỏ để không phanh nhầm, ga nhầm (cụm `C-XE-GA`, 1282 từ, `/xe-may/2026/10/14/chuyen-tu-xe-so-sang-xe-tay-ga-nhung-thoi-quen-cu-can-bo-de-khong-phanh-nham-ga/`)
- bổ trợ — Từ xe số sang xe ga hoặc ngược lại: thói quen cần sửa trong tuần đầu (cụm `C-THUE-THANG`, 1157 từ, `/thue-xe/2026/10/11/tu-xe-so-sang-xe-ga-hoac-nguoc-lai-thoi-quen-can-sua-trong-tuan-dau/`)

### `coi xe may keu lien tuc` (2 bài)
- bổ trợ — Còi xe thuê kêu liên tục không tắt được giữa phố: ngắt tạm thế nào cho an toàn (cụm `C-HD-SU-CO`, 1268 từ, `/hoi-dap/2026/10/15/coi-xe-thue-keu-lien-tuc-khong-tat-duoc-giua-pho-ngat-tam-the-nao-cho-an-toan/`)
- **URL chủ lực đề xuất** — Còi xe thuê tự kêu liên tục không tắt được: tấp vào lề, tắt khóa điện và báo cửa hàng (cụm `C-THUE-SU-CO`, 1063 từ, `/thue-xe/2026/10/15/coi-xe-thue-tu-keu-lien-tuc-khong-tat-duoc-tap-vao-le-tat-khoa-dien-va-bao-cua-h/`)

### `cop xe ga khong mo uoc` (2 bài)
- **URL chủ lực đề xuất** — Cốp xe ga không mở được hoặc yên bị kẹt: nguyên nhân thường gặp và cách xử lý không làm hỏng khóa (cụm `C-BAO-DUONG`, 1243 từ, `/xe-may/2026/10/15/cop-xe-ga-khong-mo-duoc-hoac-yen-bi-ket-nguyen-nhan-thuong-gap-va-cach-xu-ly-kho/`)
- bổ trợ — Cốp xe ga không mở được lúc trả xe (cụm `C-THUE-SU-CO`, 1121 từ, `/thue-xe/2026/10/03/cop-xe-ga-khong-mo-duoc-luc-tra-xe/`)

### `en ba chua kho bang xe may` (2 bài)
- **URL chủ lực đề xuất** — Đền Bà Chúa Kho bằng xe máy đầu năm: chọn ngày vắng, gửi xe và giữ đồ lúc đông người (cụm `C-CD-CUOI-TUAN`, 1276 từ, `/cung-duong/2026/10/16/den-ba-chua-kho-bang-xe-may-dau-nam-chon-ngay-vang-gui-xe-va-giu-do-luc-dong-ngu/`)
- bổ trợ — Đi lễ đền Bà Chúa Kho tháng Giêng bằng Honda Air Blade thuê: giờ tránh đông, gửi xe và giữ đồ lễ (cụm `C-HONDA-AIR-BLADE`, 1159 từ, `/xe-may/2026/10/15/di-le-den-ba-chua-kho-thang-gieng-bang-honda-air-blade-thue-gio-tranh-dong-gui-x/`)

### `en o co uoc re phai` (2 bài)
- **URL chủ lực đề xuất** — Đèn đỏ có được rẽ phải bằng xe máy không: mũi tên xanh, biển phụ và vạch mắt võng ở ngã tư Hà Nội (cụm `C-QUY-DINH`, 1293 từ, `/an-toan-phap-ly/2026/10/16/den-do-co-duoc-re-phai-bang-xe-may-khong-mui-ten-xanh-bien-phu-va-vach-mat-vong/`)
- bổ trợ — Đèn đỏ có được rẽ phải không: khách quốc tế quen luật nước mình cần biết gì khi chạy xe máy ở Hà Nội (cụm `C-THUE-QUOC-TE`, 1202 từ, `/thue-xe/2026/10/15/den-do-co-duoc-re-phai-khong-khach-quoc-te-quen-luat-nuoc-minh-can-biet-gi-khi-c/`)

### `gia thue honda wave theo tuan` (2 bài)
- **URL chủ lực đề xuất** — Thuê Honda Wave theo ngày 150.000đ, tuần 700.000đ hay tháng 900.000–1.200.000đ: ở bao nhiêu ngày thì nên đổi gói (cụm `C-HONDA-WAVE`, 1244 từ, `/xe-may/2026/10/29/thue-honda-wave-theo-ngay-150000d-tuan-700000d-hay-thang-9000001200000d-o-bao-nh/`)
- bổ trợ — Honda Wave chỉ niêm yết giá ngày 150.000đ: muốn thuê Wave cả tuần hoặc cả tháng thì hỏi cửa hàng thế nào (cụm `C-THUE-GIA`, 1051 từ, `/thue-xe/2026/10/15/honda-wave-chi-niem-yet-gia-ngay-150000d-muon-thue-wave-ca-tuan-hoac-ca-thang-th/`)

### `giay to can khi thue xe may` (2 bài)
- **URL chủ lực đề xuất** — Cần mang giấy tờ gì khi thuê xe máy ở Hà Nội (cụm `C-HD-THU-TUC`, 1133 từ, `/hoi-dap/2026/10/10/can-mang-giay-to-gi-khi-thue-xe-may-o-ha-noi/`)
- bổ trợ — Chuẩn bị giấy tờ gì trước khi đến cửa hàng thuê xe (cụm `C-THUE-THU-TUC`, 952 từ, `/thue-xe/2026/09/27/chuan-bi-giay-to-gi-truoc-khi-den-cua-hang-thue-xe/`)

### `gui xe pho i bo ho guom` (2 bài)
- bổ trợ — Thuê xe máy buổi tối cuối tuần đi phố đi bộ Hồ Gươm: gửi xe ở đâu và tránh các tuyến cấm (cụm `C-THUE-NGAY`, 1256 từ, `/thue-xe/2026/10/14/thue-xe-may-buoi-toi-cuoi-tuan-di-pho-di-bo-ho-guom-gui-xe-o-dau-va-tranh-cac-tu/`)
- **URL chủ lực đề xuất** — Phố đi bộ Hồ Gươm cuối tuần xe máy gửi ở đâu (cụm `C-PHO-CO`, 1151 từ, `/du-lich/2026/10/09/pho-di-bo-ho-guom-cuoi-tuan-xe-may-gui-o-dau/`)

### `i ba vi bang xe may` (2 bài)
- **URL chủ lực đề xuất** — Ba Vì bằng xe máy: đèo lên cao và điểm nghỉ (cụm `C-DIEM-DEN`, 1115 từ, `/du-lich/2026/10/01/ba-vi-bang-xe-may-deo-len-cao-va-diem-nghi/`)
- bổ trợ — Ba Vì nửa ngày bằng xe máy từ Hà Nội (cụm `C-NGOAI-THANH`, 1088 từ, `/du-lich/2026/09/28/ba-vi-nua-ngay-bang-xe-may-tu-ha-noi/`)

### `i bat trang bang xe may` (2 bài)
- **URL chủ lực đề xuất** — Đi làng gốm Bát Tràng bằng xe máy nửa ngày: đường đi và lưu ý khi tham quan (cụm `C-THUE-QUOC-TE`, 1171 từ, `/thue-xe/2026/10/12/di-lang-gom-bat-trang-bang-xe-may-nua-ngay-duong-di-va-luu-y-khi-tham-quan/`)
- bổ trợ — Đi làng gốm Bát Tràng bằng xe ga: đường đi từ phố cổ và lúc nên về (cụm `C-HONDA-CLICK`, 1058 từ, `/xe-may/2026/10/13/di-lang-gom-bat-trang-bang-xe-ga-duong-di-tu-pho-co-va-luc-nen-ve/`)

### `i chua huong bang xe may` (2 bài)
- **URL chủ lực đề xuất** — Một ngày đi Chùa Hương bằng xe máy thuê: đường qua Hà Đông, Mỹ Đức, chỗ gửi xe và giờ xuất phát (cụm `C-THUE-NGAY`, 1374 từ, `/thue-xe/2026/10/14/mot-ngay-di-chua-huong-bang-xe-may-thue-duong-qua-ha-dong-my-duc-cho-gui-xe-va-g/`)
- bổ trợ — Chùa Hương bằng xe máy từ Hà Nội: chuẩn bị trước khi đi (cụm `C-CD-CUOI-TUAN`, 1127 từ, `/cung-duong/2026/09/28/chua-huong-bang-xe-may-tu-ha-noi-chuan-bi-truoc-khi-di/`)

### `i cong vien yen so bang xe may` (2 bài)
- **URL chủ lực đề xuất** — Đến Công viên Yên Sở bằng xe máy: gửi xe và đường đi (cụm `C-DIEM-DEN`, 1058 từ, `/du-lich/2026/10/04/den-cong-vien-yen-so-bang-xe-may-gui-xe-va-duong-di/`)
- bổ trợ — Đi công viên Yên Sở bằng xe máy: chỗ đỗ xe và đường vào (cụm `C-CD-NOI-THANH`, 1023 từ, `/cung-duong/2026/10/01/di-cong-vien-yen-so-bang-xe-may-cho-do-xe-va-duong-vao/`)

### `i o son bang xe may` (2 bài)
- **URL chủ lực đề xuất** — Đi Đồ Sơn bằng xe máy từ Hà Nội: cung đường ven biển (cụm `C-CD-PHO-BAC`, 1112 từ, `/cung-duong/2026/10/01/di-do-son-bang-xe-may-tu-ha-noi-cung-duong-ven-bien/`)
- bổ trợ — Đi biển Đồ Sơn bằng xe máy từ Hà Nội: cung đường và điểm nghỉ (cụm `C-CD-CUOI-TUAN`, 1065 từ, `/cung-duong/2026/10/04/di-bien-do-son-bang-xe-may-tu-ha-noi-cung-duong-va-diem-nghi/`)

### `i xe khong chinh chu` (2 bài)
- **URL chủ lực đề xuất** — Đi xe máy không chính chủ ở Hà Nội: người thuê, người mượn xe có bị xử phạt không (cụm `C-GIAY-TO`, 1292 từ, `/an-toan-phap-ly/2026/10/15/di-xe-may-khong-chinh-chu-o-ha-noi-nguoi-thue-nguoi-muon-xe-co-bi-xu-phat-khong/`)
- bổ trợ — Xe máy thuê đứng tên chủ xe, không phải tên mình: khách quốc tế có cần giấy ủy quyền khi bị kiểm tra (cụm `C-THUE-QUOC-TE`, 1224 từ, `/thue-xe/2026/10/15/xe-may-thue-dung-ten-chu-xe-khong-phai-ten-minh-khach-quoc-te-co-can-giay-uy-quy/`)

### `i xe may qua cau long bien` (2 bài)
- **URL chủ lực đề xuất** — Đi xe máy qua cầu Long Biên: mặt cầu hẹp, khe nối và giữ lái thẳng khi đông xe (cụm `C-KY-NANG-CO-BAN`, 1375 từ, `/ky-nang/2026/10/15/di-xe-may-qua-cau-long-bien-mat-cau-hep-khe-noi-va-giu-lai-thang-khi-dong-xe/`)
- bổ trợ — Đi xe máy qua cầu Long Biên lúc nào đẹp nhất (cụm `C-LONG-BIEN`, 1020 từ, `/du-lich/2026/09/30/di-xe-may-qua-cau-long-bien-luc-nao-dep-nhat/`)

### `i xe may qua uong ngap` (2 bài)
- **URL chủ lực đề xuất** — Đi xe máy qua đoạn đường ngập nước (cụm `C-KY-NANG-THOI-TIET`, 1048 từ, `/ky-nang/2026/10/10/di-xe-may-qua-doan-duong-ngap-nuoc/`)
- bổ trợ — Đi xe máy qua đoạn ngập nước trong nội đô (cụm `C-KY-NANG-TINH-HUONG`, 1041 từ, `/ky-nang/2026-09-29/di-xe-may-qua-doan-ngap-nuoc-trong-noi-do/`)

### `muon xe may hay thue xe` (2 bài)
- **URL chủ lực đề xuất** — Mượn xe máy của người quen hay tự thuê xe ở Hà Nội: giấy tờ, trách nhiệm và chi phí thật (cụm `C-XE-SO-SANH`, 1335 từ, `/xe-may/2026/10/15/muon-xe-may-cua-nguoi-quen-hay-tu-thue-xe-o-ha-noi-giay-to-trach-nhiem-va-chi-ph/`)
- bổ trợ — Mượn xe máy của người quen hay tự thuê xe khi ở Hà Nội vài ngày: những khoản cần tính cho sòng phẳng (cụm `C-THUE-GIA`, 1207 từ, `/thue-xe/2026/10/15/muon-xe-may-cua-nguoi-quen-hay-tu-thue-xe-khi-o-ha-noi-vai-ngay-nhung-khoan-can/`)

### `nha tu hoa lo i xe may` (2 bài)
- **URL chủ lực đề xuất** — Nhà tù Hỏa Lò bằng xe máy: đi từ phố cổ, gửi xe và nên dành bao lâu để tham quan (cụm `C-PHO-CO`, 1137 từ, `/du-lich/2026/10/15/nha-tu-hoa-lo-bang-xe-may-di-tu-pho-co-gui-xe-va-nen-danh-bao-lau-de-tham-quan/`)
- bổ trợ — Đến Di tích Nhà tù Hỏa Lò bằng xe máy: đường vào khu phố cũ và chỗ dừng xe (cụm `C-BAO-TANG`, 1019 từ, `/du-lich/2026/10/13/den-di-tich-nha-tu-hoa-lo-bang-xe-may-duong-vao-khu-pho-cu-va-cho-dung-xe/`)

### `nhan xe may thue buoi toi` (2 bài)
- **URL chủ lực đề xuất** — Nhận xe máy thuê buổi tối nên kiểm tra gì kỹ hơn (cụm `C-THUE-NHAN-TRA`, 1308 từ, `/thue-xe/2026/10/10/nhan-xe-may-thue-buoi-toi-nen-kiem-tra-gi-ky-hon/`)
- bổ trợ — Nhận xe thuê buổi tối hoặc đêm: hẹn giờ và kiểm tra xe khi thiếu sáng (cụm `C-THUE-THU-TUC`, 1044 từ, `/thue-xe/2026/10/11/nhan-xe-thue-buoi-toi-hoac-dem-hen-gio-va-kiem-tra-xe-khi-thieu-sang/`)

## B. Cặp tiêu đề gần trùng trong cùng cụm (30 dòng đầu, Jaccard >= 0.7)

- Bảo hiểm trách nhiệm dân sự với xe máy: khách thuê cần biết gì (`/an-toan-phap-ly/2026/09/28/bao-hiem-trach-nhiem-dan-su-voi-xe-may-khach-thue-can-biet-gi/`) — So khớp với /an-toan-phap-ly/2026/09/28/bao-hiem-trach-nhiem-dan-su-xe-may-la-gi/ (Jaccard=0.78); điều tra intent trước khi hành động
- Bảo hiểm tự nguyện xe máy: có đáng mua thêm không (`/an-toan-phap-ly/2026/10/10/bao-hiem-tu-nguyen-xe-may-co-dang-mua-them-khong/`) — So khớp với /an-toan-phap-ly/2026/10/10/mua-them-bao-hiem-tu-nguyen-khi-thue-xe-may/ (Jaccard=0.83); điều tra intent trước khi hành động
- Ghé Bảo tàng Hà Nội bằng xe máy: gửi xe và giờ mở cửa (`/du-lich/2026/09/28/ghe-bao-tang-ha-noi-bang-xe-may-gui-xe-va-gio-mo-cua/`) — So khớp với /du-lich/2026/09/28/ghe-bao-tang-khong-khi-khong-gian-sao-bang-xe-may-gui-xe-va-gio-mo-cua/ (Jaccard=0.75); điều tra intent trước khi hành động
- Ghé Bảo tàng Hà Nội bằng xe máy: gửi xe và giờ mở cửa (`/du-lich/2026/09/28/ghe-bao-tang-ha-noi-bang-xe-may-gui-xe-va-gio-mo-cua/`) — So khớp với /du-lich/2026/09/28/ghe-bao-tang-quan-y-bang-xe-may-gui-xe-va-gio-mo-cua/ (Jaccard=0.86); điều tra intent trước khi hành động
- Ghé Bảo tàng Hà Nội bằng xe máy: gửi xe và giờ mở cửa (`/du-lich/2026/09/28/ghe-bao-tang-ha-noi-bang-xe-may-gui-xe-va-gio-mo-cua/`) — So khớp với /du-lich/2026/10/04/ghe-bao-tang-phong-khong-khong-quan-bang-xe-may-gui-xe-va-gio-mo-cua/ (Jaccard=0.75); điều tra intent trước khi hành động
- Ghé Bảo tàng Quân y bằng xe máy: gửi xe và giờ mở cửa (`/du-lich/2026/09/28/ghe-bao-tang-quan-y-bang-xe-may-gui-xe-va-gio-mo-cua/`) — So khớp với /du-lich/2026/10/04/ghe-bao-tang-phong-khong-khong-quan-bang-xe-may-gui-xe-va-gio-mo-cua/ (Jaccard=0.88); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Con rối Việt Nam: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-con-roi-viet-nam-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/09/28/trai-nghiem-bao-tang-duong-sat-viet-nam-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.73); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Con rối Việt Nam: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-con-roi-viet-nam-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/09/28/trai-nghiem-bao-tang-my-thuat-viet-nam-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.73); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Con rối Việt Nam: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-con-roi-viet-nam-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/09/28/trai-nghiem-bao-tang-phu-nu-viet-nam-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.73); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Đường sắt Việt Nam: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-duong-sat-viet-nam-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/09/28/trai-nghiem-bao-tang-my-thuat-viet-nam-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.73); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Đường sắt Việt Nam: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-duong-sat-viet-nam-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/09/28/trai-nghiem-bao-tang-phu-nu-viet-nam-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.73); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Hà Nội: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-ha-noi-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/09/28/trai-nghiem-bao-tang-khong-khi-khong-gian-sao-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.82); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Hà Nội: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-ha-noi-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/09/28/trai-nghiem-bao-tang-quan-y-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.90); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Hà Nội: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-ha-noi-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/10/04/trai-nghiem-bao-tang-ho-chi-minh-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.75); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Hà Nội: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-ha-noi-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/10/04/trai-nghiem-bao-tang-phong-khong-khong-quan-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.82); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Không khí - Không gian Sao: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-khong-khi-khong-gian-sao-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/09/28/trai-nghiem-bao-tang-quan-y-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.75); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Mỹ thuật Việt Nam: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-my-thuat-viet-nam-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/09/28/trai-nghiem-bao-tang-phu-nu-viet-nam-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.73); điều tra intent trước khi hành động
- Trải nghiệm Bảo tàng Quân y: nên đi cùng ai và lúc nào (`/du-lich/2026/09/28/trai-nghiem-bao-tang-quan-y-nen-di-cung-ai-va-luc-nao/`) — So khớp với /du-lich/2026/10/04/trai-nghiem-bao-tang-phong-khong-khong-quan-nen-di-cung-ai-va-luc-nao/ (Jaccard=0.91); điều tra intent trước khi hành động
- Đi xe máy thăm Bảo tàng Dân tộc học Việt Nam (`/du-lich/2026/09/30/di-xe-may-tham-bao-tang-dan-toc-hoc-viet-nam/`) — So khớp với /du-lich/2026/10/10/den-bao-tang-dan-toc-hoc-viet-nam-bang-xe-may-duong-di-va-gui-xe/ (Jaccard=0.73); điều tra intent trước khi hành động
- Đến bảo tàng Văn học Việt Nam bằng xe máy: gửi xe và đường đi (`/du-lich/2026/10/01/den-bao-tang-van-hoc-viet-nam-bang-xe-may-gui-xe-va-duong-di/`) — So khớp với /du-lich/2026/10/10/den-bao-tang-dan-toc-hoc-viet-nam-bang-xe-may-duong-di-va-gui-xe/ (Jaccard=0.73); điều tra intent trước khi hành động
- Kinh nghiệm ghé thăm bảo tàng Địa chất Việt Nam nửa ngày (`/du-lich/2026/10/01/kinh-nghiem-ghe-tham-bao-tang-dia-chat-viet-nam-nua-ngay/`) — So khớp với /du-lich/2026/10/01/kinh-nghiem-ghe-tham-bao-tang-thien-nhien-viet-nam-nua-ngay/ (Jaccard=0.71); điều tra intent trước khi hành động
- Kinh nghiệm ghé thăm bảo tàng Địa chất Việt Nam nửa ngày (`/du-lich/2026/10/01/kinh-nghiem-ghe-tham-bao-tang-dia-chat-viet-nam-nua-ngay/`) — So khớp với /du-lich/2026/10/01/kinh-nghiem-ghe-tham-bao-tang-van-hoc-viet-nam-nua-ngay/ (Jaccard=0.71); điều tra intent trước khi hành động
- Kinh nghiệm ghé thăm bảo tàng Thiên nhiên Việt Nam nửa ngày (`/du-lich/2026/10/01/kinh-nghiem-ghe-tham-bao-tang-thien-nhien-viet-nam-nua-ngay/`) — So khớp với /du-lich/2026/10/01/kinh-nghiem-ghe-tham-bao-tang-van-hoc-viet-nam-nua-ngay/ (Jaccard=0.71); điều tra intent trước khi hành động
- Chạy xe từ Hà Nội đến Chùa Hương cuối tuần (`/cung-duong/2026/09/28/chay-xe-tu-ha-noi-den-chua-huong-cuoi-tuan/`) — So khớp với /cung-duong/2026/09/30/chay-xe-may-di-chua-huong-cuoi-tuan/ (Jaccard=0.83); điều tra intent trước khi hành động
- Hà Nội đi Ba Vì cuối tuần bằng xe máy (`/cung-duong/2026/09/28/ha-noi-di-ba-vi-cuoi-tuan-bang-xe-may/`) — So khớp với /cung-duong/2026/10/10/ha-noi-di-ba-vi-bang-xe-may-cung-duong-cuoi-tuan/ (Jaccard=0.71); điều tra intent trước khi hành động
- Hà Nội đi Đền Sóc bằng xe máy: cung đường và thời gian (`/cung-duong/2026/10/01/ha-noi-di-den-soc-bang-xe-may-cung-duong-va-thoi-gian/`) — So khớp với /cung-duong/2026/10/04/ha-noi-di-den-va-bang-xe-may-cung-duong-va-thoi-gian/ (Jaccard=0.83); điều tra intent trước khi hành động
- Hà Nội đi Suối Tơ bằng xe máy: cung đường và thời gian (`/cung-duong/2026/10/01/ha-noi-di-suoi-to-bang-xe-may-cung-duong-va-thoi-gian/`) — So khớp với /cung-duong/2026/10/04/ha-noi-di-den-va-bang-xe-may-cung-duong-va-thoi-gian/ (Jaccard=0.71); điều tra intent trước khi hành động
- Hà Nội đi Thác Bồ bằng xe máy: cung đường và thời gian (`/cung-duong/2026/10/01/ha-noi-di-thac-bo-bang-xe-may-cung-duong-va-thoi-gian/`) — So khớp với /cung-duong/2026/10/04/ha-noi-di-den-va-bang-xe-may-cung-duong-va-thoi-gian/ (Jaccard=0.71); điều tra intent trước khi hành động
- Hà Nội đi Thác Bồ bằng xe máy: cung đường và thời gian (`/cung-duong/2026/10/01/ha-noi-di-thac-bo-bang-xe-may-cung-duong-va-thoi-gian/`) — So khớp với /cung-duong/2026/10/04/ha-noi-di-thac-da-bang-xe-may-cung-duong-va-thoi-gian/ (Jaccard=0.75); điều tra intent trước khi hành động
- Hà Nội đi Thung Nai bằng xe máy: cung đường và thời gian (`/cung-duong/2026/10/01/ha-noi-di-thung-nai-bang-xe-may-cung-duong-va-thoi-gian/`) — So khớp với /cung-duong/2026/10/04/ha-noi-di-den-va-bang-xe-may-cung-duong-va-thoi-gian/ (Jaccard=0.71); điều tra intent trước khi hành động
