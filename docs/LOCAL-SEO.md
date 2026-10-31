# LOCAL SEO và BUSINESS FACTS của blog

Blog và shop là hai bên kinh doanh khác nhau. Tài liệu này CHỈ dùng dữ liệu kinh doanh của /blog.

## Nguồn chuẩn (giữ nguyên)

- `_data/business.yml` (NAP) → kết xuất `data/business-facts.json`.
- `_data/pricing.yml` → bảng giá + máy tính giá. KHÔNG đổi công thức máy tính trừ khi có yêu cầu.

## Sự thật đã xác minh của /blog

- Thương hiệu: Nguyễn Tú — Thuê Xe Máy Hà Nội Nguyễn Tú.
- Địa chỉ: 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội, Việt Nam.
- Điện thoại: 0942 467 674 (Zalo/WhatsApp cùng số). Giờ hoạt động: 09:00–21:00, không 24/7.
- Giá đã duyệt: KHÔNG chép số vào tài liệu này (bản chép cũ đã lệch). Nguồn duy nhất: `data/business-facts.json` → `approved_pricing` và `_data/pricing.yml` (bảng giá, máy tính giá). Xe điện/xe đạp điện: "liên hệ để xác nhận".
- Đặt cọc: chỉ dùng mức đã duyệt theo từng dòng xe trong `data/business-facts.json` (`approved_pricing.*.deposit`, `deposit_policy`); xe điện xác nhận theo mẫu xe. Phí giao xe: không có số cố định.

## Cấm trong nội dung và schema

Không bịa: khuyến mại, phí giao cố định, số lượng khách, số năm kinh nghiệm, xếp hạng, cam kết, 24/7, đánh giá khách hàng. Mọi xung đột nội bộ (khoảng cọc, phí trễ...) đang BLOCKED: `reports/factory/policy-conflicts.md`.

## Kiểm tra

- Mỗi bài/trang chạm dữ liệu kinh doanh: BUSINESS FACT PASS (truy được về nguồn chuẩn) trước khi promote.
- Đối chiếu định kỳ `_data/business.yml` ↔ hiển thị trang chủ/footer/bảng giá. Lệch → sửa theo `_data/business.yml`, không sửa theo bài viết.
