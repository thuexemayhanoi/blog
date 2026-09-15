---
layout: page
title: "Bang gia xe ga - Thue Xe May Ha Noi Nguyen Tu"
description: "Bang gia thue xe ga (automatic scooter) tai Ha Noi. Honda Vision, Air Blade, Click, Mio."
lang: vi
translation_key: xe-ga
permalink: /bang-gia-xe-ga/
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Bang Gia Xe Ga

Xe ga (automatic scooter) la loai xe su dung hop so tu dong, nguoi lai chi can van ga la xe se di chuyen. Loai xe nay ngan cay pho bien do su tien loi.

### Cac Mau Xe Ga

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

### Dac Diem

- Hien dai, su dung hop so tu dong
- Tu the lai thang lung, thoai mai
- De dieu khien
- Phu hop cho nguoi moi hoac di trong pho

<div class="cta-group">
  <a href="{{ '/bang-gia/' | relative_url }}" class="btn btn-outline">Ve Bang Gia</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Go de Dat Xe</a>
</div>
