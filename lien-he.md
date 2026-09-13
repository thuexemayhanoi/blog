---
layout: page
title: "Liên hệ - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Thông tin liên hệ và hỗ trợ thuê xe máy tại Hà Nội từ Nguyễn Tú"
permalink: /lien-he/
---

{% assign business = site.data.business %}

<section class="section">
  <div class="container">
    <h1>{{ page.title | split: ' - ' | first }}</h1>
    <p class="page-description">{{ page.description }}</p>
    
    <div class="contact-grid">
      <div class="contact-card">
        <h2>📍 Địa chỉ</h2>
        <p>{{ business.address.full }}</p>
        <a href="{{ business.contact.maps }}" target="_blank" rel="noopener noreferrer" class="btn btn-outline">Xem trên Google Maps</a>
      </div>
      
      <div class="contact-card">
        <h2>📞 Điện thoại</h2>
        <p><a href="{{ business.contact.phone_uri }}">{{ business.contact.phone }}</a></p>
        <p><em>Giờ hoạt động: {{ business.hours }}</em></p>
      </div>
      
      <div class="contact-card">
        <h2>✉️ Email</h2>
        <p><a href="mailto:{{ business.contact.email }}">{{ business.contact.email }}</a></p>
      </div>
      
      <div class="contact-card">
        <h2>💬 Zalo</h2>
        <p><a href="{{ business.contact.zalo }}" target="_blank" rel="noopener noreferrer">Nhắn tin trên Zalo</a></p>
      </div>
    </div>
    
    <div class="map-section">
      <iframe 
        src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3724.56789!2d105.8589!3d21.02345!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x0%3A0x0!2zMjHCsDAxJzI0LjQiTiAxMDXCsDUxJzI0LjAiRQ!5e0!3m2!1svi!2s!4v1234567890!5m2!1svi!2s" 
        width="100%" 
        height="450" 
        style="border:0; border-radius: var(--radius);" 
        allowfullscreen="" 
        loading="lazy" 
        referrerpolicy="no-referrer-when-downgrade">
      </iframe>
    </div>
    
    <div class="services-section">
      <h2>Dịch vụ của chúng tôi</h2>
      <p>Chúng tôi cung cấp các loại xe sau:</p>
      
      <div class="vehicle-grid">
        {% for vehicle in business.vehicle_types %}
        <div class="vehicle-card">
          <h3>{{ vehicle.name }}</h3>
          <p>{{ vehicle.description }}</p>
          {% if vehicle.examples.size > 0 %}
          <p class="examples"><em>{{ vehicle.examples | join: ', ' }}</em></p>
          {% endif %}
        </div>
        {% endfor %}
      </div>
      
      <h2>Hình thức thuê</h2>
      <div class="rental-grid">
        {% for rental in business.rental_types %}
        <div class="rental-card">
          <h3>{{ rental.name }}</h3>
          <p>{{ rental.description }}</p>
        </div>
        {% endfor %}
      </div>
    </div>
    
    <div class="faq-section">
      <h2>Câu hỏi thường gặp</h2>
      <div class="faq-item">
        <h3>Tình trạng xe như thế nào?</h3>
        <p>Tất cả xe đều được bảo dưỡng định kỳ và kiểm tra kỹ lưỡng trước khi giao cho khách hàng.</p>
      </div>
      <div class="faq-item">
        <h3>Giá thuê có cố định không?</h3>
        <p>Giá có thể thay đổi tùy theo mùa, loại xe và thời gian thuê. Vui lòng liên hệ để biết giá hiện tại.</p>
      </div>
      <div class="faq-item">
        <h3>Tiền đặt cọc là bao nhiêu?</h3>
        <p>Tiền đặt cọc tùy thuộc vào loại xe và thời gian thuê. Chúng tôi sẽ thông báo rõ ràng trước khi bạn đặt xe.</p>
      </div>
      <div class="faq-item">
        <h3>Có giao xe ngoài giờ hành chính không?</h3>
        <p>Không. Chúng tôi chỉ giao xe trong giờ hành chính: {{ business.hours }}. Vui lòng liên hệ trước để đặt lịch.</p>
      </div>
    </div>
    
    <div class="cta-section">
      <h2>Sẵn sàng phục vụ bạn</h2>
      <p>Hãy liên hệ với chúng tôi để được tư vấn và hỗ trợ tốt nhất.</p>
      <div class="cta-group">
        <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Gọi ngay {{ business.contact.phone }}</a>
        <a href="{{ business.contact.zalo }}" class="btn btn-secondary">Nhắn Zalo</a>
        <a href="{{ business.url }}" class="btn btn-outline" target="_blank" rel="noopener noreferrer">Website chính</a>
      </div>
    </div>
  </div>
</section>