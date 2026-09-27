# Báo cáo đối chiếu dữ liệu kinh doanh (business fact audit)

Ngày audit: 2026-09-27. Phạm vi: `_data/business.yml`, `_data/pricing.yml`, trang chủ và các trang tĩnh (`bang-gia*.md`), 483 bài trong `_posts/`.

## Kết luận tổng thể

Không phát hiện mâu thuẫn về dữ liệu kinh doanh cốt lõi. Toàn bộ thông tin công khai nhất quán với một nguồn duy nhất (`_data/business.yml`, `_data/pricing.yml`).

## Sự thật đã xác minh (ghi vào `data/business-facts.json`)

- Thương hiệu: Nguyễn Tú — Thuê Xe Máy Hà Nội Nguyễn Tú.
- Địa chỉ: 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội.
- Điện thoại: 0942 467 674; Zalo/WhatsApp cùng số.
- Giờ hoạt động: 09:00–21:00 (không hỗ trợ 24/7; website ghi rõ "Không giao xe máy ngoài giờ hoạt động").
- Giá đã duyệt: Honda Wave 150k/ngày; Vision 200k/ngày; Air Blade 200k/ngày; Click/Mio 150k/ngày; tuần/tháng theo khoảng giá trong pricing.yml.
- Xe máy điện / xe đạp điện / xe 50cc: giá "liên hệ để xác nhận".
- Tiền đặt cọc: không có số cố định; toàn bộ ghi "cần xác nhận trực tiếp".
- Phí giao xe: KHÔNG có số cố định nào được công bố (đoạn delivery_fees trong pricing.yml bị comment).

## Ghi chú / điểm cần lưu ý (không phải mâu thuẫn)

1. Hạng mục xe 50cc trên trang chủ ghi "Giá thuê liên hệ trực tiếp" — nhất quán với pricing.yml (không có rate). Nội dung factory phải giữ nguyên cách diễn đạt này.
2. Trang chủ hiển thị trạng thái mở/cửa hàng theo khung giờ 09:00–21:00 — nội dung factory không được nói "giao xe ngoài giờ".
3. Các bài legacy dùng chung cách diễn đạt "liên hệ để xác nhận" cho xe điện và đặt cọc — giữ nguyên chuẩn này cho bài mới.

## Cấu trúc cấm (factory không được vi phạm)

Không bịa khuyến mại, phí giao cố định, số lượng khách, số năm kinh nghiệm, xếp hạng, cam kết, hỗ trợ 24/7, đánh giá khách hàng. Không đổi công thức máy tính giá.
