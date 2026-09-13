---
layout: page
title: "Bảng giá"
description: "Tham khảo bảng giá thuê xe máy các loại từ Nguyễn Tú"
---

{% assign business = site.data.business %}

## Bảng giá thuê xe máy

Dưới đây là thông tin về các loại xe mà chúng tôi cung cấp. Mức giá và tình trạng xe có thể thay đổi tùy theo thời điểm và loại xe cụ thể.

## Các loại xe

<div class="pricing-grid">
  {% for vehicle in business.vehicle_types %}
  <div class="pricing-card glass-card">
    <h3>{{ vehicle.name }}</h3>
    <p>{{ vehicle.description }}</p>
    {% if vehicle.examples.size > 0 %}
    <p><em>Ví dụ: {{ vehicle.examples | join: ', ' }}</em></p>
    {% endif %}
    <a href="{{ vehicle.pricing_url | relative_url }}" class="btn btn-outline">
      Xem chi tiết
    </a>
  </div>
  {% endfor %}
</div>

## Hình thức thuê

<div class="rental-grid">
  {% for rental in business.rental_types %}
  <div class="rental-card glass-card">
    <h3>{{ rental.name }}</h3>
    <p>{{ rental.description }}</p>
  </div>
  {% endfor %}
</div>

## Lưu ý quan trọng

<div class="feature-card glass-card" style="margin-top: 2rem;">
  <h3>⚠️ Thông tin cần biết</h3>
  <ul>
    <li><strong>Giá thuê:</strong> Mức giá phụ thuộc vào loại xe, thời gian thuê và tình trạng xe hiện tại</li>
    <li><strong>Tiền đặt cọc:</strong> Phụ thuộc vào loại xe và thời gian thuê</li>
    <li><strong>Chi phí giao nhận:</strong> Có thể thay đổi tùy theo khu vực</li>
    <li><strong>Xác nhận trước:</strong> Vui lòng liên hệ Nguyễn Tú để kiểm tra giá và tình trạng xe hiện tại trước khi đặt</li>
  </ul>
</div>

<div class="cta-group" style="justify-content: center; margin-top: 2rem;">
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">
    Gọi kiểm tra giá
  </a>
  <a href="{{ business.contact.zalo }}" class="btn btn-secondary" target="_blank" rel="noopener noreferrer">
    Nhắn Zalo
  </a>
  <a href="{{ business.url }}" class="btn btn-outline" target="_blank" rel="noopener noreferrer">
    Xem website chính
  </a>
</div>
