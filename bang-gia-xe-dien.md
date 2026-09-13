---
layout: page
title: "Bảng giá xe điện"
description: "Thông tin chi tiết về thuê xe máy điện từ Nguyễn Tú"
---

{% assign business = site.data.business %}

## Xe máy điện - Thông tin chi tiết

Xe máy điện là loại xe thân thiện với môi trường, không phát thải và tiết kiệm chi phí vận hành.

### Đặc điểm

- **Thân thiện môi trường:** Không phát thải CO2
- **Tiết kiệm:** Chi phí vận hành thấp, không cần xăng
- **Yên tĩnh:** Hoạt động êm ái, không gây ồn
- **Dễ sử dụng:** Đơn giản, phù hợp cho mọi đối tượng

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
