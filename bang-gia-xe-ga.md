---
layout: page
title: "Bảng giá xe ga"
description: "Thông tin chi tiết về thuê xe ga (xe tay ga) từ Nguyễn Tú"
---

{% assign business = site.data.business %}

## Xe ga (Xe tay ga) - Thông tin chi tiết

Xe ga (xe tay ga) là loại xe hiện đại, thoải mái và dễ điều khiển, phù hợp cho cả nam và nữ.

### Đặc điểm

- **Thoải mái:** Tư thế lái thẳng lưng, dễ chịu
- **Dễ điều khiển:** Không cần sử dụng côn, phù hợp cho người mới
- **Hiện đại:** Thiết kế trẻ trung, động cơ mạnh mẽ
- **Phù hợp:** Cho thành phố và đường dài

### Các mẫu xe tiêu biểu

{% for vehicle in business.vehicle_types %}
  {% if vehicle.name == "Xe tay ga" %}
    {% if vehicle.examples.size > 0 %}
- {{ vehicle.examples | join: '
- ' }}
    {% endif %}
  {% endif %}
{% endfor %}

### Hình thức thuê

{% for rental in business.rental_types %}
- **{{ rental.name }}:** {{ rental.description }}
{% endfor %}

### Khu vực phục vụ

Chúng tôi phục vụ chủ yếu tại các quận:

{% for area in business.areas %}
- {{ area }}
{% endfor %}

### Lưu ý

- Giá thuê, tiền đặt cọc và chi phí giao nhận có thể thay đổi
- Vui lòng liên hệ để kiểm tra tình trạng xe hiện tại
- Không giao xe ngoài giờ hoạt động ({{ business.hours }})

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
