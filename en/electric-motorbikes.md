---
layout: page
title: "Electric Motorbikes - Pricing"
description: "Pricing for electric motorbikes (xe dien) rental in Hanoi. Eco-friendly transportation."
lang: en
translation_key: xe-dien
permalink: /en/electric-motorbikes/
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Electric Motorbikes Pricing

Electric motorbikes (Xe Dien) are environmentally friendly vehicles with zero emissions. Perfect for eco-conscious travelers.

### Available Models

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category.en == 'Electric motorbike' %}
    <div class="pricing-card glass-card">
      <h3>{{ vehicle.name.en }}</h3>
      <p>{{ vehicle.description.en }}</p>
      <div class="price-grid">
        {% if vehicle.rates.day.min %}
        <div class="price-item">
          <span class="price-label">Daily:</span>
          <span class="price-value">{{ vehicle.rates.day.min }} - {{ vehicle.rates.day.max | default: vehicle.rates.day.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.week.min %}
        <div class="price-item">
          <span class="price-label">Weekly:</span>
          <span class="price-value">{{ vehicle.rates.week.min }} - {{ vehicle.rates.week.max | default: vehicle.rates.week.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.month.min %}
        <div class="price-item">
          <span class="price-label">Monthly:</span>
          <span class="price-value">{{ vehicle.rates.month.min }} - {{ vehicle.rates.month.max | default: vehicle.rates.month.min }} VND</span>
        </div>
        {% endif %}
      </div>
      <p class="note"><em>Deposit: {{ vehicle.deposit.min }} - {{ vehicle.deposit.max }} VND</em></p>
      {% if vehicle.popular %}
      <span class="badge popular">Popular Choice</span>
      {% endif %}
    </div>
    {% endif %}
  {% endfor %}
</div>

### Features

- Zero emissions, eco-friendly
- Quiet operation
- Low running costs
- Suitable for short to medium distances

<div class="cta-group">
  <a href="{{ '/en/pricing/' | relative_url }}" class="btn btn-outline">Back to All Pricing</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Call to Book</a>
</div>
