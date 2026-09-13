---
layout: default
title: "Liên hệ - Blog Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Thông tin liên hệ và hỗ trợ thuê xe máy tại Hà Nội từ Nguyễn Tú"
---

<section class="section">
  <div class="container">
    <h1>{{ page.title }}</h1>
    
    <div class="post-content">
      <p>Bạn có nhu cầu thuê xe máy tại Hà Nội? Hãy liên hệ với <strong>{{ site.business_display_name }}</strong> để được tư vấn và hỗ trợ tốt nhất.</p>
      
      <h2>Thông tin liên hệ</h2>
      
      <div class="contact-info">
        <p><strong>{{ site.business_display_name }}</strong></p>
        <p>📍 <strong>Địa chỉ:</strong> {{ site.business_address }}</p>
        <p>📞 <strong>Điện thoại:</strong> <a href="{{ site.business_phone_uri }}">{{ site.business_phone }}</a></p>
        <p>✉️ <strong>Email:</strong> <a href="mailto:{{ site.business_email }}">{{ site.business_email }}</a></p>
        <p>🕒 <strong>Giờ hoạt động:</strong> {{ site.business_hours }}</p>
        <p>📍 <strong>Google Maps:</strong> <a href="{{ site.business_maps }}" target="_blank" rel="noopener noreferrer">Xem trên bản đồ</a></p>
        <p>💬 <strong>Zalo:</strong> <a href="{{ site.business_zalo }}" target="_blank" rel="noopener noreferrer">Nhắn tin trên Zalo</a></p>
      </div>
      
      <div class="mt-4">
        <iframe 
          src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3724.5678912345678!2d105.85890123456789!3d21.023456789012345!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zMjHCsDAxJzI0LjQiTiAxMDXCsDUxJzI0LjAiRQ!5e0!3m2!1sen!2s!4v1234567890123!5m2!1sen!2s" 
          width="100%" 
          height="450" 
          style="border:0; border-radius: var(--radius);" 
          allowfullscreen="" 
          loading="lazy" 
          referrerpolicy="no-referrer-when-downgrade">
        </iframe>
      </div>
      
      <h2 class="mt-4">Khu vực phục vụ</h2>
      <p>Chúng tôi phục vụ giao xe tận nơi tại các khu vực sau:</p>
      <ul>
        <li>Long Biên</li>
        <li>Bồ Đề</li>
        <li>Gia Lâm</li>
        <li>Hoàn Kiếm</li>
        <li>Phố Cổ Hà Nội</li>
        <li>Ba Đình</li>
        <li>Tây Hồ</li>
        <li>Các quận nội thành Hà Nội</li>
        <li>Sân bay Nội Bài (theo yêu cầu)</li>
      </ul>
      
      <p class="mb-4"><em>Lưu ý: Thời gian và chi phí giao nhận xe có thể thay đổi tùy theo khu vực. Vui lòng liên hệ để xác nhận trước khi đặt xe.</em></p>
      
      <h2>Dịch vụ của chúng tôi</h2>
      <p>Chúng tôi cung cấp các loại xe sau:</p>
      
      <div class="feature-grid">
        <div class="feature-card">
          <h3>🏍️ Xe số</h3>
          <p>Honda Wave, Yamaha Sirius</p>
        </div>
        <div class="feature-card">
          <h3>🛵 Xe tay ga</h3>
          <p>Honda Vision, Air Blade, Click, Yamaha Mio</p>
        </div>
        <div class="feature-card">
          <h3>🚲 Xe 50cc</h3>
          <p>Honda Cub 50cc, xe ga 50cc</p>
        </div>
        <div class="feature-card">
          <h3>⚡ Xe điện</h3>
          <p>Xe máy điện, xe đạp điện</p>
        </div>
      </div>
      
      <h2 class="mt-4">Hình thức thuê</h2>
      <div class="feature-grid">
        <div class="feature-card">
          <h3>📅 Theo ngày</h3>
          <p>Linh hoạt cho nhu cầu ngắn hạn</p>
        </div>
        <div class="feature-card">
          <h3>📆 Theo tuần</h3>
          <p>Tiết kiệm cho chuyến đi dài ngày</p>
        </div>
        <div class="feature-card">
          <h3>📅 Theo tháng</h3>
          <p>Giá ưu đãi cho thuê dài hạn</p>
        </div>
      </div>
      
      <h2 class="mt-4">Câu hỏi thường gặp</h2>
      
      <h3>Tình trạng xe như thế nào?</h3>
      <p>Tất cả xe của chúng tôi đều được bảo dưỡng định kỳ, kiểm tra kỹ lưỡng trước khi giao cho khách hàng. Xe luôn trong tình trạng hoạt động tốt.</p>
      
      <h3>Giá thuê có cố định không?</h3>
      <p>Giá thuê có thể thay đổi tùy theo mùa, loại xe và thời gian thuê. Vui lòng liên hệ để biết giá hiện tại.</p>
      
      <h3>Tiền đặt cọc là bao nhiêu?</h3>
      <p>Tiền đặt cọc tùy thuộc vào loại xe và thời gian thuê. Chúng tôi sẽ thông báo rõ ràng trước khi bạn quyết định thuê.</p>
      
      <h3>Có giao xe ngoài giờ hành chính không?</h3>
      <p>Không. Chúng tôi chỉ giao xe trong giờ hành chính: {{ site.business_hours }}. Vui lòng liên hệ trước để đặt lịch.</p>
      
      <div class="cta-group mt-4">
        <a href="{{ site.business_phone_uri }}" class="btn btn-primary">Gọi ngay {{ site.business_phone }}</a>
        <a href="{{ site.business_zalo }}" class="btn btn-secondary">Nhắn Zalo</a>
        <a href="{{ site.business_url }}" class="btn btn-outline">Website chính</a>
      </div>
    </div>
  </div>
</section>