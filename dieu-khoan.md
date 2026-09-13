---
layout: page
title: "Điều khoản sử dụng - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Điều khoản và điều kiện sử dụng website blog của Nguyễn Tú"
permalink: /dieu-khoan/
---

{% assign business = site.data.business %}

<section class="section">
  <div class="container">
    <h1>{{ page.title | split: ' - ' | first }}</h1>
    <p class="page-description">{{ page.description }}</p>
    
    <div class="terms-content">
      <p>Chào mừng bạn đến với <strong>{{ business.display_name }}</strong>. Bằng việc truy cập và sử dụng website này, bạn đồng ý tuân thủ các điều khoản và điều kiện sau đây.</p>
      
      <h2>Nội dung website</h2>
      <p>Nội dung trên blog này chỉ mang tính chất <strong>tham khảo</strong> và <strong>chia sẻ kinh nghiệm</strong>. Chúng tôi không đảm bảo rằng tất cả thông tin đều chính xác, đầy đủ hoặc cập nhật.</p>
      <p>Bạn nên tự kiểm tra và xác nhận thông tin trước khi đưa ra quyết định thuê xe.</p>
      
      <h2>Bảng giá và tình trạng xe</h2>
      <p>Bảng giá và tình trạng xe được đề cập trên website có thể thay đổi mà không cần thông báo trước. Giá thuê, tiền đặt cọc, chi phí giao nhận và tình trạng xe có thể khác nhau tùy theo thời điểm.</p>
      <p><strong>Bạn phải liên hệ trực tiếp với {{ business.brand }} để xác nhận thông tin trước khi đặt xe.</strong></p>
      
      <h2>Liên kết bên ngoài</h2>
      <p>Website có thể chứa liên kết đến các website bên ngoài. Chúng tôi không kiểm soát và không chịu trách nhiệm về nội dung, chính sách bảo mật hoặc hoạt động của các website đó.</p>
      
      <h2>Sử dụng thông tin</h2>
      <p>Bạn có thể sử dụng thông tin trên website này cho mục đích cá nhân. Không được sao chép, phân phối hoặc sử dụng thông tin cho mục đích thương mại mà không có sự cho phép bằng văn bản.</p>
      
      <h2>Trách nhiệm</h2>
      <p><strong>{{ business.display_name }}</strong> không chịu trách nhiệm về bất kỳ thiệt hại nào phát sinh từ việc sử dụng hoặc không thể sử dụng website này, bao gồm nhưng không giới hạn:</p>
      <ul>
        <li>Thiệt hại gián tiếp, ngẫu nhiên hoặc đặc biệt</li>
        <li>Thiệt hại dữ liệu hoặc lợi nhuận</li>
        <li>Thiệt hại do ngưng gián dịch vụ</li>
      </ul>
      
      <h2>Thay đổi nội dung</h2>
      <p>Chúng tôi có quyền thay đổi, sửa đổi, tạm ngừng hoặc ngưng cung cấp bất kỳ phần nào của website này mà không cần thông báo trước.</p>
      
      <h2>Luật áp dụng</h2>
      <p>Các điều khoản này được điều chỉnh bởi luật pháp Việt Nam.</p>
      
      <h2>Liên hệ</h2>
      <p>Nếu bạn có câu hỏi về điều khoản sử dụng, vui lòng liên hệ:</p>
      <div class="cta-group">
        <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Gọi {{ business.contact.phone }}</a>
        <a href="mailto:{{ business.contact.email }}" class="btn btn-secondary">Email</a>
      </div>
    </div>
  </div>
</section>