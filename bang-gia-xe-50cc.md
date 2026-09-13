---
layout: page
title: "Bảng giá Xe 50cc - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Bảng giá thuê xe 50cc tại Nguyễn Tú. Phù hợp cho du khách nước ngoài. Vui lòng liên hệ để xác nhận."
permalink: /bang-gia-xe-50cc/
vehicle_type: "Xe 50cc"
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
      {% if vehicle.examples.size > 0 %}
      <p><strong>Mẫu xe ví dụ:</strong> {{ vehicle.examples | join: ', ' }}</p>
      {% endif %}
      
      <h2>Đặc điểm</h2>
      <ul class="features-list">
        <li>Công suất thấp, phù hợp cho du khách nước ngoài</li>
        <li>Không yêu cầu giấy phép lái xe máy (theo luật Việt Nam đối với du khách)</li>
        <li>Tiết kiệm nhiên liệu</li>
        <li>Dễ điều khiển</li>
      </ul>
      
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
      
      <p class="note"><em>Lưu ý: {{ business.notes | join: ' | ' }}</em></p>
      
      <div class="cta-section">
        <h2>Liên hệ để biết giá</h2>
        <p>Giá thuê xe 50cc có thể thay đổi. Vui lòng liên hệ để được báo giá chính xác nhất.</p>
        <div class="cta-group">
          <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Gọi {{ business.contact.phone }}</a>
          <a href="{{ business.contact.zalo }}" class="btn btn-secondary">Nhắn Zalo</a>
          <a href="{{ business.url }}" class="btn btn-outline" target="_blank" rel="noopener noreferrer">Website chính</a>
        </div>
      </div>
    </div>
  </div>
</section>