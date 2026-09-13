---
layout: page
title: "Manual Motorbikes - Pricing"
description: "Pricing for manual motorbikes (xe so) rental in Hanoi. Honda Wave and similar models."
lang: en
translation_key: xe-so
permalink: /en/manual-motorbikes/
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Manual Motorbikes Pricing

Manual motorbikes (Xe So) are traditional motorcycles with manual transmission. They are easy to control and popular among experienced riders.

### Available Models

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category.en == 'Manual motorbike' %}
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

- Traditional manual transmission
- Easy to control
- Fuel efficient
- Suitable for experienced riders

<div class="cta-group">
  <a href="{{ '/en/pricing/' | relative_url }}" class="btn btn-outline">Back to All Pricing</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Call to Book</a>
</div>
