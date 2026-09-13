---
layout: page
title: "Automatic Scooters - Pricing"
description: "Pricing for automatic scooters (xe ga) rental in Hanoi. Honda Vision, Air Blade, Click, Mio."
lang: en
translation_key: xe-ga
permalink: /en/automatic-scooters/
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Automatic Scooters Pricing

Automatic scooters (Xe Ga) are modern, comfortable motorcycles with automatic transmission. Perfect for city riding and beginners.

### Available Models

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category.en == 'Automatic scooter' or vehicle.category.en == 'Budget automatic scooter' %}
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

- Modern automatic transmission
- Comfortable riding position
- Easy to use for beginners
- Great for city traffic

<div class="cta-group">
  <a href="{{ '/en/pricing/' | relative_url }}" class="btn btn-outline">Back to All Pricing</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Call to Book</a>
</div>
