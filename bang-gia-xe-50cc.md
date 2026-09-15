---
layout: page
title: "Bang gia xe 50cc - Thue Xe May Ha Noi Nguyen Tu"
description: "Bang gia thue xe 50cc tai Ha Noi. Phu hop cho du khach nuoc ngoai."
lang: vi
translation_key: xe-50cc
permalink: /bang-gia-xe-50cc/
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Bang Gia Xe 50cc

Xe 50cc la loai xe co dong co nho, cong suat duoi 50cc. Loai xe nay dac biet phu hop cho du khach nuoc ngoai.

### Dac Diem

- Cong suat thap, de dieu khien
- Tiet kiem nhien lieu toi da
- Nhe nhang, phu hop cho nguoi co voc dang nho
- Khong yeu cau giay phep lai xe (cho du khach nuoc ngoai theo luat Viet Nam)

### Gia Thue

<div class="pricing-card glass-card">
  <p>{{ pricing.vehicles | where: "id", "electric-scooter" | first | property: "note" | default: "Vui long lien he Nguyen Tu de kiem tra gia hien tai" }}</p>
</div>

### Luu Y

- Xe 50cc co toc do toi da thap, khong phu hop cho duong dai hoac dia hinh doi nui
- Toc do toi da cua xe 50cc thuong duoi 50 km/h
- Khong phu hop cho nhung chuyen di xa

<div class="cta-group">
  <a href="{{ '/bang-gia/' | relative_url }}" class="btn btn-outline">Ve Bang Gia</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Go de Hoi Gia</a>
</div>
