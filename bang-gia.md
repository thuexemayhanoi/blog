---
layout: page
title: "Bảng giá - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Tham khảo bảng giá thuê xe máy tại Nguyễn Tú. Vui lòng liên hệ để xác nhận giá hiện tại."
permalink: /bang-gia/
---

{% assign business = site.data.business %}

<section class="section">
  <div class="container">
    <h1>{{ page.title | split: ' - ' | first }}</h1>
    <p class="page-description">{{ page.description }}</p>
    
    <div class="pricing-intro">
      <p><strong>{{ business.display_name }}</strong> cung cấp đa dạng các loại xe và hình thức thuê với mức giá cạnh tranh. Giá thuê có thể thay đổi tùy theo mùa, tình trạng xe và thời gian thuê.</p>
      <p><strong>Lưu ý:</strong> {{ business.notes | join: ' | ' }}</p>
    </div>
    
    <div class="vehicle-types-grid">
      {% for vehicle in business.vehicle_types %}
      <div class="vehicle-type-card">
        <h3>{{ vehicle.name }}</h3>
        <p>{{ vehicle.description }}</p>
        {% if vehicle.examples.size > 0 %}
        <p class="examples"><em>Ví dụ: {{ vehicle.examples | join: ', ' }}</em></p>
        {% endif %}
        <a href="{{ '/bang-gia-xe-' | append: vehicle.name | slugify | append: '/' | relative_url }}" class="btn btn-outline">Xem chi tiết</a>
      </div>
      {% endfor %}
    </div>
    
    <div class="rental-types-section">
      <h2>Hình thức thuê</h2>
      <div class="rental-types-grid">
        {% for rental in business.rental_types %}
        <div class="rental-type-card">
          <h3>{{ rental.name }}</h3>
          <p>{{ rental.description }}</p>
        </div>
        {% endfor %}
      </div>
    </div>
    
    <div class="cta-section">
      <h2>Cần biết giá chính xác?</h2>
      <p>Hãy liên hệ trực tiếp với chúng tôi để được tư vấn và báo giá mới nhất.</p>
      <div class="cta-group">
        <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Gọi kiểm tra giá</a>
        <a href="{{ business.contact.zalo }}" class="btn btn-secondary">Nhắn Zalo</a>
        <a href="{{ business.url }}" class="btn btn-outline" target="_blank" rel="noopener noreferrer">Xem website chính</a>
      </div>
    </div>
  </div>
</section>