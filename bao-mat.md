---
layout: page
title: "Chính sách bảo mật - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Chính sách bảo mật thông tin cá nhân của Nguyễn Tú"
permalink: /bao-mat/
---

{% assign business = site.data.business %}

<section class="section">
  <div class="container">
    <h1>{{ page.title | split: ' - ' | first }}</h1>
    <p class="page-description">{{ page.description }}</p>
    
    <div class="policy-content">
      <p><strong>{{ business.display_name }}</strong> tôn trọng quyền riêng tư của bạn và cam kết bảo vệ thông tin cá nhân của bạn. Chính sách bảo mật này giải thích cách chúng tôi thu thập, sử dụng và bảo vệ thông tin của bạn.</p>
      
      <h2>Thông tin chúng tôi thu thập</h2>
      <p>Chúng tôi có thể thu thập các thông tin sau khi bạn liên hệ hoặc sử dụng dịch vụ:</p>
      <ul>
        <li><strong>Thông tin cá nhân:</strong> Tên, số điện thoại, địa chỉ email mà bạn cung cấp khi liên hệ</li>
        <li><strong>Thông tin liên lạc:</strong> Thông tin bạn cung cấp thông qua biểu mẫu liên hệ hoặc cuộc gọi</li>
      </ul>
      
      <h2>Cách chúng tôi sử dụng thông tin</h2>
      <p>Thông tin thu thập được sử dụng để:</p>
      <ul>
        <li>Cung cấp dịch vụ thuê xe máy cho bạn</li>
        <li>Liên lạc với bạn về dịch vụ và hỗ trợ</li>
        <li>Cải thiện chất lượng dịch vụ</li>
        <li>Gửi thông báo quan trọng về dịch vụ</li>
      </ul>
      
      <h2>Chia sẻ thông tin</h2>
      <p>Chúng tôi <strong>không bán, trao đổi hoặc cho thuê</strong> thông tin cá nhân của bạn cho bên thứ ba. Thông tin của bạn chỉ được chia sẻ trong các trường hợp sau:</p>
      <ul>
        <li>Khi có yêu cầu của pháp luật</li>
        <li>Để bảo vệ quyền lợi hợp pháp của chúng tôi</li>
        <li>Với sự đồng ý của bạn</li>
      </ul>
      
      <h2>Bảo vệ thông tin</h2>
      <p>Chúng tôi sử dụng các biện pháp bảo mật phù hợp để bảo vệ thông tin cá nhân của bạn khỏi truy cập, sửa đổi, tiết lộ hoặc phá hủy trái phép.</p>
      
      <h2>Liên kết bên ngoài</h2>
      <p>Website của chúng tôi có thể chứa liên kết đến các website bên ngoài như:</p>
      <ul>
        <li><a href="{{ business.url }}" target="_blank" rel="noopener noreferrer">{{ business.url }}</a> (Website chính)</li>
        <li><a href="{{ business.contact.zalo }}" target="_blank" rel="noopener noreferrer">Zalo</a></li>
        <li><a href="{{ business.contact.maps }}" target="_blank" rel="noopener noreferrer">Google Maps</a></li>
      </ul>
      <p>Chúng tôi không kiểm soát các website bên ngoài và không chịu trách nhiệm về chính sách bảo mật của họ.</p>
      
      <h2>Cookie</h2>
      <p>Website hiện tại không sử dụng cookie để theo dõi người dùng. Chúng tôi chỉ sử dụng các công cụ phân tích cơ bản của GitHub Pages.</p>
      
      <h2>Quyền của bạn</h2>
      <p>Bạn có quyền:</p>
      <ul>
        <li>Truy cập vào thông tin cá nhân của mình</li>
        <li>Yêu cầu sửa đổi thông tin không chính xác</li>
        <li>Yêu cầu xóa thông tin cá nhân</li>
        <li>Từ chối nhận thông tin quảng cáo</li>
      </ul>
      
      <h2>Thay đổi chính sách</h2>
      <p>Chúng tôi có thể cập nhật chính sách bảo mật này theo thời gian. Bất kỳ thay đổi nào cũng sẽ được đăng tải trên trang này.</p>
      
      <h2>Liên hệ</h2>
      <p>Nếu bạn có câu hỏi về chính sách bảo mật, vui lòng liên hệ:</p>
      <div class="cta-group">
        <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Gọi {{ business.contact.phone }}</a>
        <a href="mailto:{{ business.contact.email }}" class="btn btn-secondary">Email</a>
      </div>
    </div>
  </div>
</section>