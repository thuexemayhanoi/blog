---
layout: page
title: "Bang gia xe dien - Thue Xe May Ha Noi Nguyen Tu"
description: "Bang gia thue xe dien (electric motorbike) tai Ha Noi. Than thien voi moi truong."
lang: vi
translation_key: xe-dien
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Bang Gia Xe Dien

Xe dien (electric motorbike) la phuong tien than thien voi moi truong, khong phat thai. Hoan hao cho nhung ai quan tam den moi truong hoac muon tiet kiem chi phi nhien lieu.

### Cac Mau Xe Dien

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category.vi == 'Xe may dien' %}
    <div class="pricing-card glass-card">
      <h3>{{ vehicle.name.vi }}</h3>
      <p>{{ vehicle.description.vi }}</p>
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

- Khong phat thai, than thien voi moi truong
- Yem ang, it tieng on
- Chi phi van hanh thap
- Phu hop cho cac chuyen di ngan va trung binh

<div class="cta-group">
  <a href="{{ '/bang-gia/' | relative_url }}" class="btn btn-outline">Ve Bang Gia</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Go de Dat Xe</a>
</div>
