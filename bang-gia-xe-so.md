---
layout: page
title: "Bang gia xe so - Thue Xe May Ha Noi Nguyen Tu"
description: "Bang gia thue xe so (manual motorbike) tai Ha Noi. Honda Wave va cac mau xe khac."
lang: vi
translation_key: xe-so
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Bang Gia Xe So

Xe so (manual motorbike) la loai xe pho bien nhat tai Viet Nam, su dung hop so tay, yeu cau nguoi lai phai co ky nang dieu khien con.

### Cac Mau Xe So

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category.vi == 'Xe so' %}
    <div class="pricing-card glass-card">
      <h3>{{ vehicle.name.vi }}</h3>
      <p>{{ vehicle.description.vi }}</p>
      <div class="price-grid">
        {% if vehicle.rates.day.min %}
        <div class="price-item">
          <span class="price-label">Theo ngay:</span>
          <span class="price-value">{{ vehicle.rates.day.min }} VND</span>
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

- Truyen thong, su dung hop so tay
- De dieu khien
- Tiet kiem nhien lieu
- Phu hop cho nguoi co kinh nghiem

<div class="cta-group">
  <a href="{{ '/bang-gia/' | relative_url }}" class="btn btn-outline">Ve Bang Gia</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Go de Dat Xe</a>
</div>
