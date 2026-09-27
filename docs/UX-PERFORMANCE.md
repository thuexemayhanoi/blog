# UX / MOBILE / ACCESSIBILITY / PERFORMANCE

Mục tiêu: trang dùng được trên điện thoại (~390px), accessible, nhanh; không tự tuyên bố "performance cao" khi chưa đo.

## Kiểm tra bắt buộc sau mỗi thay đổi giao diện

- Mobile ~390px: không tràn ngang; menu mở/đóng được; calculator, chatbot, footer dùng được. Kiểm tra bằng devtools emulator hoặc máy thật. Ghi rõ đã test trên gì; KHÔNG ghi Safari/iPhone khi chưa test trên đó.
- Dark/light: cả hai chế độ hiển thị đúng (site có toggle theme qua `localStorage`, đặt trong `_layouts/default.html`).
- Keyboard: menu điều hướng bằng bàn phím được, focus visible (hỗ trợ có sẵn trong `assets/js/main.js`).
- SVG: giữ nguyên hệ thống icon `_includes/icon.html`; không emoji làm icon chức năng; không thêm icon CDN ngoài.
- Dấu tiếng Việt: giữ nguyên toàn bộ trong text hiển thị.

## Performance

- Không framework, không font ngoài không cần — giữ nguyên.
- Lighthouse là đo trong phòng thí nghiệm; Core Web Vitals thực tế lấy từ dữ liệu người dùng thật (CrUX/GSC khi có quyền truy cập). KHÔNG lấy điểm Lighthouse làm bằng chứng "Core Web Vitals tốt".
- Trạng thái hiện tại: NOT VERIFIED — chưa đo Lighthouse/CWV trong lần chạy này.

## Xử lý lỗi

Sai ở giao diện → sửa đúng tệp (layout/include/CSS), không thiết kế lại vùng không liên quan; build, kiểm tra live mobile + dark/light, ghi vào Master Fix Matrix.
