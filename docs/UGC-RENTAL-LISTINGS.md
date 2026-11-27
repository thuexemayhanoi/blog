# Kiến trúc tin cho thuê xe máy miễn phí

GitHub Pages tiếp tục phục vụ blog và nội dung đã duyệt. Khi mở đăng ký, dùng dịch vụ xác thực và lưu trữ ở lớp riêng. Bản thử nghiệm chỉ chạy khi có lựa chọn miễn phí phù hợp với nhu cầu vận hành. Đợt này chỉ thiết kế kiến trúc.

1. Thành viên xác minh tài khoản trước khi gửi. Dữ liệu công khai của tin gồm nội dung văn bản, giá thuê kèm kỳ hạn, loại xe, địa chỉ nhận xe và thông tin liên hệ được người đăng đồng ý công khai.
2. Máy chủ kiểm tra quyền sở hữu, độ dài văn bản, giá hợp lệ, loại xe và giới hạn gửi. Chỉ nhận các trường đã định nghĩa qua biểu mẫu văn bản. Quản trị viên duyệt tin, xử lý báo cáo và gỡ tin hết hạn. Lưu thông tin tài khoản và lịch sử duyệt riêng với dữ liệu công khai.
3. Tin chờ duyệt chỉ hiển thị cho người gửi và người duyệt. Khi duyệt, xuất bản trang tĩnh bằng quy trình build riêng với ID ổn định. Chỉ đưa tin còn hiệu lực, có nội dung hữu ích và canonical tự trỏ vào sitemap. Chống trùng bằng đánh giá nội dung, loại xe, địa chỉ và liên hệ trước khi xuất bản.
4. Khi kết thúc thời hạn hoặc người đăng rút đồng ý công khai liên hệ, gỡ dữ liệu công khai, bỏ URL khỏi sitemap và trả trạng thái phù hợp. Nhật ký vận hành chỉ giữ dữ liệu cần thiết cho việc xử lý tranh chấp.
5. Chỉ mở trang danh sách theo khu vực khi có đủ tin thật. Giữ các trang dịch vụ hiện tại làm đích thương mại chính. Gắn `rel="ugc"` cho liên kết do người dùng cung cấp nếu sau này bổ sung trường liên kết.

Điều kiện mở thử nghiệm gồm kiểm thử quyền sửa tin, từ chối file tải lên, thoát HTML, giới hạn gửi, quy trình duyệt và thu hồi thông tin liên hệ. Dùng dữ liệu thử nghiệm nội bộ với trang công khai tắt.
