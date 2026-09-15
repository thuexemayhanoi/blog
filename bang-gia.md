---
layout: page
title: "Bang gia thue xe may Ha Noi"
description: "Bang gia thue xe may tai Ha Noi. Gia ca minh bach, cap nhat moi nhat tu Nguyen Tu."
lang: vi
translation_key: pricing
permalink: /bang-gia/
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Bang Gia Thue Xe May

Tat ca gia deu duoc niem yet bang Dong Viet Nam (VND). Luu y: day la gia tham khao, gia thuc te can thay doi va can duoc xac nhan truc tiep voi Nguyen Tu truoc khi dat xe.

<!-- Rental Calculator -->
{% include rental-calculator.html %}

### Bang Gia Theo Loai Xe

#### Xe So (Manual Motorbike)

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category == 'Xe so' %}
    <div class="pricing-card glass-card">
      <h3>{{ vehicle.name }}</h3>
      <p>{{ vehicle.description }}</p>
      <div class="price-grid">
        {% if vehicle.rates.day.min %}
        <div class="price-item">
          <span class="price-label">Theo ngay:</span>
          <span class="price-value">{{ vehicle.rates.day.min }} - {{ vehicle.rates.day.max | default: vehicle.rates.day.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.week.min %}
        <div class="price-item">
          <span class="price-label">Theo tuan:</span>
          <span class="price-value">{{ vehicle.rates.week.min }} - {{ vehicle.rates.week.max | default: vehicle.rates.week.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.month.min %}
        <div class="price-item">
          <span class="price-label">Theo thang:</span>
          <span class="price-value">{{ vehicle.rates.month.min }} - {{ vehicle.rates.month.max | default: vehicle.rates.month.min }} VND</span>
        </div>
        {% endif %}
      </div>
      <p class="note"><em>Tien dat coc: {{ vehicle.deposit.min }} - {{ vehicle.deposit.max }} VND</em></p>
      {% if vehicle.popular %}
      <span class="badge popular">Lua chon pho bien</span>
      {% endif %}
    </div>
    {% endif %}
  {% endfor %}
</div>

#### Xe Ga (Automatic Scooter)

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category == 'Xe ga' %}
    <div class="pricing-card glass-card">
      <h3>{{ vehicle.name }}</h3>
      <p>{{ vehicle.description }}</p>
      <div class="price-grid">
        {% if vehicle.rates.day.min %}
        <div class="price-item">
          <span class="price-label">Theo ngay:</span>
          <span class="price-value">{{ vehicle.rates.day.min }} - {{ vehicle.rates.day.max | default: vehicle.rates.day.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.week.min %}
        <div class="price-item">
          <span class="price-label">Theo tuan:</span>
          <span class="price-value">{{ vehicle.rates.week.min }} - {{ vehicle.rates.week.max | default: vehicle.rates.week.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.month.min %}
        <div class="price-item">
          <span class="price-label">Theo thang:</span>
          <span class="price-value">{{ vehicle.rates.month.min }} - {{ vehicle.rates.month.max | default: vehicle.rates.month.min }} VND</span>
        </div>
        {% endif %}
      </div>
      <p class="note"><em>Tien dat coc: {{ vehicle.deposit.min }} - {{ vehicle.deposit.max }} VND</em></p>
      {% if vehicle.popular %}
      <span class="badge popular">Lua chon pho bien</span>
      {% endif %}
    </div>
    {% endif %}
  {% endfor %}
</div>

#### Xe Dien (Electric Motorbike)

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category == 'Xe may dien' %}
    <div class="pricing-card glass-card">
      <h3>{{ vehicle.name }}</h3>
      <p>{{ vehicle.description }}</p>
      <div class="price-grid">
        {% if vehicle.rates.day.min %}
        <div class="price-item">
          <span class="price-label">Theo ngay:</span>
          <span class="price-value">{{ vehicle.rates.day.min }} - {{ vehicle.rates.day.max | default: vehicle.rates.day.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.week.min %}
        <div class="price-item">
          <span class="price-label">Theo tuan:</span>
          <span class="price-value">{{ vehicle.rates.week.min }} - {{ vehicle.rates.week.max | default: vehicle.rates.week.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.month.min %}
        <div class="price-item">
          <span class="price-label">Theo thang:</span>
          <span class="price-value">{{ vehicle.rates.month.min }} - {{ vehicle.rates.month.max | default: vehicle.rates.month.min }} VND</span>
        </div>
        {% endif %}
      </div>
      <p class="note"><em>Tien dat coc: {{ vehicle.deposit.min }} - {{ vehicle.deposit.max }} VND</em></p>
      {% if vehicle.popular %}
      <span class="badge popular">Lua chon pho bien</span>
      {% endif %}
    </div>
    {% endif %}
  {% endfor %}
</div>

#### Xe Dap Dien (Electric Scooter)

<div class="pricing-card glass-card">
  <h3>Xe Dap Dien</h3>
  <p>Nhe nhang, phu hop cho khoang cach ngan. Vui long lien he de biet gia hien tai.</p>
  <p class="note"><em>{{ pricing.vehicles | where: "id", "electric-scooter" | first | property: "note" | default: "Vui long lien he Nguyen Tu de kiem tra gia hien tai" }}</em></p>
</div>

### Loai Hinh Thue

<div class="rental-types">
  {% for rental in pricing.rental_types %}
  <div class="rental-type">
    <h4>{{ rental.name }}</h4>
    <p>{{ rental.description }}</p>
  </div>
  {% endfor %}
</div>

### Luu Y Quan Trong

- Tat ca gia deu la gia tham khao va co the thay doi tuy theo tinh hinh xe
- Tien dat coc bat buoc cho tat ca cac hop dong thue va se duoc hoan tra sau khi tra xe dung hen va xe khong bi hu hong
- Phi giao nhan xe co the ap dung tuy thuoc vao vi tri
- Vui long xac nhan gia cuoi cung va tinh trang xe truc tiep voi Nguyen Tu truoc khi dat xe
- Thoi han thue: Toi thieu 1 ngay, toi da 365 ngay
- Tat ca cac xe deu di kem mu bao hiem co ban

### Huong Dan Dat Xe

1. **Chon Xe**: Chon xe phu hop voi nhu cau cua ban
2. **Kiem Tra Gia**: Su dung cong cu tinh gia hoac xem bang gia o tren
3. **Lien He**: Goi dien, Zalo, hoac WhatsApp de xac nhan tinh trang xe
4. **Xac Nhan Chi Tiet**: Dong y cho diem lay/tra xe va thoi gian
5. **Dat Coc**: Bao dam hop dong thue bang tien dat coc
6. **Nhan Xe**: Bat dau hanh trinh cua ban!

<div class="cta-group">
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Go Ngay</a>
  <a href="{{ business.contact.zalo }}" class="btn btn-secondary">Zalo</a>
  <a href="{{ business.contact.whatsapp }}" class="btn btn-outline">WhatsApp</a>
</div>
