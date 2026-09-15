---
layout: page
title: "Gioi thieu - Thue Xe May Ha Noi Nguyen Tu"
description: "Gioi thieu ve dich vu thue xe may uy tin tai Ha Noi. Xe chat luong, gia ca minh bach, giao nhan tan noi."
lang: vi
translation_key: about
permalink: /gioi-thieu/
---

{% assign business = site.data.business %}

## Gioi Thieu Nguyen Tu Motorcycle Rental

{{ business.display_name }} la don vi cung cap dich vu thue xe may uy tin tai Ha Noi, Viet Nam. Chung toi chuyen ve viec cung cap xe may chat luong cho du khach va nguoi dan dia phuong voi gia ca minh bach.

### Dich Vu Cua Chung Toi

- **Thue xe may:** Thue theo ngay, tuan, thang linh hoat
- **Da dang loai xe:** Xe so, xe tay ga, xe may dien, xe 50cc
- **Giao nhan xe:** Giao xe tan noi tai cac khu vuc phuc vu
- **Chat luong dam bao:** Tat ca xe duoc bao duong dinh ky
- **Gia ca minh bach:** Khong phat sinh phi an

### Vi Sao Chon Chung Toi?

1. **Xe Chat Luong**: Tat ca xe duoc bao duong dinh ky va kiem tra ky truoc khi cho thue
2. **Gia Ca Minh Bach**: Gia thue ro rang, khong co phi an nao
3. **Giao Nhan Tan Noi**: Tiet kiem thoi gian cho khach hang
4. **Ho Tro 24/7**: Luon san sang ho tro khach hang moi luc
5. **Thu Tuc Don Gian**: Nhan xe nhanh chong voi thu tuc don gian

### Thong Tin Lien He

{% include icon.html name="map-pin" size="16" %} **Dia chi**: {{ business.address.full }}

{% include icon.html name="phone" size="16" %} **Dien thoai**: [{{ business.contact.phone }}]({{ business.contact.phone_uri }})

{% include icon.html name="message" size="16" %} **Email**: [{{ business.contact.email }}](mailto:{{ business.contact.email }})

{% include icon.html name="info" size="16" %} **Gio hoat dong**: {{ business.hours }}

### Cac Loai Xe Chinh

Chung toi cung cap da dang loai xe de dap ung moi nhu cau:

{% for vehicle in business.vehicle_types %}
- **{{ vehicle.name }}**: {{ vehicle.description }}
  {% if vehicle.examples.size > 0 %}
  *Vi du: {{ vehicle.examples | join: ', ' }}*
  {% endif %}
{% endfor %}

### Khu Vuc Phuc Vu

Chung toi chinh phuc vu tai cac quan noi thanh Ha Noi:

{% for area in business.areas %}
- {{ area }}
{% endfor %}

**Luu y:** Thoi gian va chi phi giao nhan xe co the thay doi tuy theo khu vuc. Vui long xac nhan truoc khi dat xe.

### Cam Ket Cua Chung Toi

Chung toi cam ket mang den cho khach hang:

- Xe chat luong, duoc bao duong dinh ky
- Gia ca minh bach, khong phat sinh phi an
- Giao xe tan noi theo yeu cau
- Ho tro khach hang nhiet tinh

### Ban Can Thue Xe May?

Hay lien he voi chung toi de duoc tu van va ho tro tot nhat:

<div class="cta-group">
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Go {{ business.contact.phone }}</a>
  <a href="{{ business.contact.zalo }}" class="btn btn-secondary">Zalo</a>
  <a href="{{ business.contact.whatsapp }}" class="btn btn-outline">WhatsApp</a>
</div>
