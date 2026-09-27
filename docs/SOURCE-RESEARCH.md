# SOURCE-RESEARCH — chính sách tra cứu và kiểm chứng nguồn (canonical)

Tài liệu này là nguồn chuẩn duy nhất (canonical) cho yêu cầu nghiên cứu/kiểm chứng nguồn khi viết bài. Các tài liệu khác chỉ được liên kết về đây, không viết lại luật khác đi.

Nội dung bài viết phải dùng tiếng Việt tự nhiên. Luật trong tài liệu này áp cho toàn bộ pipeline Content Factory.

## Nguyên tắc chung

- Mọi tuyên bố sự kiện trong bài phải truy được về nguồn: kiến thức phổ thông ổn định, nguồn đã kiểm chứng, hoặc bằng chứng lưu trong ledger/notes của bài.
- Không bài viết phụ (secondary blog) nào được override nguồn sơ cấp (primary/official).
- Lưu đủ bằng chứng nguồn (URL, ngày truy cập, trích dẫn ngắn, phiên bản văn bản pháp luật nếu có) để QA về sau xác định tuyên bố nào đến từ nguồn nào.
- Không bịa: giá, cọc, phí trễ, bảo hiểm, địa điểm, giờ mở cửa, thống kê, khuyến mãi, số năm kinh nghiệm, thứ hạng.

## Ba lớp nghiên cứu

### Lớp A — TĨNH / RỦI RO THẤP

Nội dung: kỹ năng xe máy phổ quát, giải thích thường trực (cách bảo dưỡng, kỹ thuật lái cơ bản, cấu tạo xe…).

Yêu cầu:

- Được dùng kiến thức repository + tài liệu tham khảo có uy tín khi hữu ích.
- Không bắt buộc tra cứu mới trước khi viết, nhưng vẫn cấm bịa chi tiết cụ thể (con số thông số, giá).

### Lớp B — HIỆN TẠI / PHỤ THUỘC ĐỊA ĐIỂM

Nội dung: điểm đến, cung đường, bãi đỗ xe, đường vào, giờ mở cửa, hạ tầng giao thông, quy định địa phương, thông tin dịch vụ hiện hành.

Yêu cầu:

- PHẢI tra cứu và kiểm chứng thông tin hiện hành trước khi viết tuyên bố cụ thể.
- Ưu tiên nguồn chính thức của địa điểm/cơ quan (website chính thức, trang thông tin của cơ quan quản lý); nguồn báo chí/UGC chỉ mang tính hỗ trợ.
- Ghi ngày kiểm chứng; nếu thông tin dễ thay đổi (giờ mở cửa, tuyến đường), dùng ngôn ngữ thận trọng hoặc cập nhật định kỳ.

### Lớp C — PHÁP LÝ / RỦI RO CAO

Nội dung: bằng lái xe, mức phạt, luật giao thông, phân loại pháp lý phương tiện, trang bị bắt buộc.

Yêu cầu:

- PHẢI kiểm chứng phiên bản luật/thông tư đang hiệu lực; ưu tiên nguồn sơ cấp/chính thức (cơ quan nhà nước, văn bản pháp luật gốc).
- Trích rõ số văn bản, ngày hiệu lực.
- Không suy diễn mức phạt/sank hụt bằng bài báo cũ hoặc bài blog khi văn bản đã sửa đổi.

## Tích hợp vào pipeline

- Trong lifecycle của agent (xem AGENTS.md): bước RESEARCH WHEN REQUIRED và SOURCE VERIFY dùng lớp A/B/C để quyết định có cần tra cứu và lưu bằng chứng hay không.
- Bước FACT CHECK/QA có quyền yêu cầu lại bằng chứng nguồn cho bất kỳ tuyên bố lớp B/C nào.
- Thiếu bằng chứng ở lớp B/C → trả bài về REPAIR, không hạ ngưỡng QA.
