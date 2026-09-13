---
layout: page
title: "Bảng giá Xe điện - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Bảng giá thuê xe máy điện tại Nguyễn Tú. Vui lòng liên hệ để xác nhận giá và tình trạng xe hiện tại."
permalink: /bang-gia-xe-dien/
vehicle_type: "Xe máy điện"
---

{% assign business = site.data.business %}
{% assign vehicle = site.data.business.vehicle_types | where: "name", page.vehicle_type | first %}

<section class="section">
  <div class="container">
    <h1>{{ page.title | split: ' - ' | first }}</h1>
    <p class="page-description">{{ page.description }}</p>
    
    <div class="vehicle-detail">
      <h2>Thông tin loại xe</h2>
      <p><strong>Mô tả:</strong> {{ vehicle.description }}</p>
      
      <h2>Hình thức thuê</h2>
      <div class="pricing-table">
        <div class="pricing-row header">
          <span>Hình thức</span>
          <span>Mô tả</span>
        </div>
        {% for rental in business.rental_types %}
        <div class="pricing-row">
          <span>{{ rental.name }}</span>
          <span>{{ rental.description }}</span>
        </div>
        {% endfor %}
      </div>
      
      <h2>Lợi ích của xe điện</h2>
      <ul class="benefits-list">
        <li>Thân thiện với môi trường, không phát thải</li>
        <li>Chi phí vận hành thấp (không cần xăng)</li>
        <li>Ít tiếng ồn, êm ái</li>
        <li>Dễ dàng sử dụng</li>
      </ul>
      
      <p class="note"><em>Lưu ý: {{ business.notes | join: ' | ' }}</em></p>
      
      <div class="cta-section">
        <h2>Liên hệ để biết giá</h2>
        <p>Giá thuê xe điện có thể thay đổi. Vui lòng liên hệ để được báo giá chính xác nhất.</p>
        <div class="cta-group">
          <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Gọi {{ business.contact.phone }}</a>
          <a href="{{ business.contact.zalo }}" class="btn btn-secondary">Nhắn Zalo</a>
          <a href="{{ business.url }}" class="btn btn-outline" target="_blank" rel="noopener noreferrer">Website chính</a>
        </div>
      </div>
    </div>
  </div>
</section>