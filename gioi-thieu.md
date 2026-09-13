---
layout: page
title: "Giới thiệu - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Giới thiệu về Nguyễn Tú - dịch vụ thuê xe máy uy tín tại Hà Nội"
permalink: /gioi-thieu/
---

{% assign business = site.data.business %}

<section class="section">
  <div class="container">
    <h1>{{ page.title | split: ' - ' | first }}</h1>
    
    <div class="intro-card">
      <h2>{{ business.display_name }}</h2>
      <p class="subtitle">{{ business.brand }} cung cấp dịch vụ thuê xe máy chuyên nghiệp tại Hà Nội, hỗ trợ khách hàng trong việc di chuyển thuận tiện và an toàn.</p>
      
      <div class="business-info">
        <div class="info-item">
          <span class="info-label">Thương hiệu:</span>
          <span class="info-value">{{ business.brand }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Địa chỉ:</span>
          <span class="info-value">{{ business.address.full }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Điện thoại:</span>
          <span class="info-value"><a href="{{ business.contact.phone_uri }}">{{ business.contact.phone }}</a></span>
        </div>
        <div class="info-item">
          <span class="info-label">Email:</span>
          <span class="info-value"><a href="mailto:{{ business.contact.email }}">{{ business.contact.email }}</a></span>
        </div>
        <div class="info-item">
          <span class="info-label">Giờ hoạt động:</span>
          <span class="info-value">{{ business.hours }}</span>
        </div>
      </div>
    </div>
    
    <div class="section-content">
      <h2>Dịch vụ của chúng tôi</h2>
      <p>{{ business.display_name }} cung cấp đa dạng các loại xe và hình thức thuê để đáp ứng mọi nhu cầu của khách hàng:</p>
      
      <div class="services-grid">
        {% for service in business.services %}
        <div class="service-card">
          <h3>{{ service }}</h3>
        </div>
        {% endfor %}
      </div>
      
      <h2>Các loại xe</h2>
      <div class="vehicle-grid">
        {% for vehicle in business.vehicle_types %}
        <div class="vehicle-card">
          <h3>{{ vehicle.name }}</h3>
          <p>{{ vehicle.description }}</p>
          {% if vehicle.examples.size > 0 %}
          <p class="examples">Ví dụ: {{ vehicle.examples | join: ', ' }}</p>
          {% endif %}
        </div>
        {% endfor %}
      </div>
      
      <h2>Khu vực phục vụ</h2>
      <p>Chúng tôi phục vụ chủ yếu tại các quận nội thành Hà Nội:</p>
      <div class="areas-list">
        {% for area in business.areas %}
        <span class="area-tag">{{ area }}</span>
        {% endfor %}
      </div>
      
      <p class="note"><em>Lưu ý: {{ business.notes | join: ' | ' }}</em></p>
      
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
  </div>
</section>