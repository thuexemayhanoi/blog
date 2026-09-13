---
layout: page
title: "Liên hệ"
description: "Thông tin liên hệ và cách thức liên lạc với Nguyễn Tú"
---

{% assign business = site.data.business %}

## Thông tin liên hệ

### Nguyễn Tú - Thuê Xe Máy Hà Nội

<div class="contact-grid">
  <div class="contact-card glass-card">
    <h3>📍 Địa chỉ</h3>
    <p>{{ business.address.full }}</p>
    <a href="{{ business.contact.maps }}" target="_blank" rel="noopener noreferrer" class="btn btn-outline">
      Mở Google Maps
    </a>
  </div>
  
  <div class="contact-card glass-card">
    <h3>📞 Điện thoại</h3>
    <p>
      <a href="{{ business.contact.phone_uri }}">{{ business.contact.phone }}</a>
    </p>
    <p><strong>Giờ hoạt động:</strong> {{ business.hours }}</p>
    <p><em>Lưu ý: Không giao xe ngoài giờ hoạt động</em></p>
    <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">
      Gọi ngay
    </a>
  </div>
  
  <div class="contact-card glass-card">
    <h3>💬 Zalo</h3>
    <p>
      <a href="{{ business.contact.zalo }}" target="_blank" rel="noopener noreferrer">
        Nhắn Zalo
      </a>
    </p>
    <a href="{{ business.contact.zalo }}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">
      Nhắn Zalo
    </a>
  </div>
  
  <div class="contact-card glass-card">
    <h3>✉️ Email</h3>
    <p>
      <a href="mailto:{{ business.contact.email }}">{{ business.contact.email }}</a>
    </p>
    <a href="mailto:{{ business.contact.email }}" class="btn btn-outline">
      Gửi email
    </a>
  </div>
</div>

## Website chính

Bạn có thể truy cập website doanh nghiệp chính của chúng tôi:

<div class="text-center" style="margin: 2rem 0;">
  <a href="{{ business.url }}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
    Truy cập {{ business.url | replace: 'https://', '' | replace: 'http://', '' }}
  </a>
</div>

## Hướng dẫn liên hệ

1. **Gọi điện thoại:** Sử dụng số điện thoại trên để gọi trực tiếp
2. **Nhắn Zalo:** Bấm vào nút Zalo để nhắn tin nhanh chóng
3. **Gửi email:** Sử dụng địa chỉ email để gửi thư
4. **Xem vị trí:** Sử dụng Google Maps để tìm đường đến địa chỉ của chúng tôi

## Ghi chú

- Chúng tôi sẽ phản hồi sớm nhất có thể trong giờ hoạt động
- Vui lòng xác nhận thông tin xe, giá cả và tình trạng trước khi đặt
- Mọi thắc mắc vui lòng liên hệ trực tiếp
