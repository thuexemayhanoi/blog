---
layout: page
title: "Bảng giá xe 50cc"
description: "Thông tin chi tiết về thuê xe 50cc từ Nguyễn Tú"
---

{% assign business = site.data.business %}

## Xe 50cc - Thông tin chi tiết

Xe 50cc là loại xe công suất nhỏ, phù hợp cho du khách và những người mới bắt đầu làm quen với xe máy.

### Đặc điểm

- **Công suất nhỏ:** Dưới 50cc, phù hợp cho nhiều đối tượng
- **Dễ điều khiển:** Nhẹ nhàng, dễ làm chủ
- **Tiết kiệm nhiên liệu:** Tiêu hao xăng rất thấp
- **Phù hợp:** Cho du lịch, di chuyển trong thành phố

### Các mẫu xe tiêu biểu

{% for vehicle in business.vehicle_types %}
  {% if vehicle.name == "Xe 50cc" %}
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

### Lưu ý quan trọng

Yêu cầu về giấy phép và giấy tờ phụ thuộc loại phương tiện và quy định hiện hành. Người thuê cần tự kiểm tra điều kiện pháp lý áp dụng cho mình trước khi điều khiển phương tiện.

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
