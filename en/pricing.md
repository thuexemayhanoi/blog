---
layout: page
title: "Pricing - Nguyen Tu Motorcycle Rental Hanoi"
description: "Transparent pricing for motorcycle rental in Hanoi. Daily, weekly, monthly rates for all bike types."
lang: en
translation_key: pricing
permalink: /en/pricing/
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Motorcycle Rental Pricing

All prices are in Vietnamese Dong (VND). Please note that these are reference prices and the final price should be confirmed directly with Nguyen Tu before booking.

<!-- Rental Calculator -->
{% include rental-calculator.html %}

### Price List by Vehicle Type

#### Manual Motorbikes (Xe So)

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
          <span class="price-value">{{ vehicle.rates.day.min | default: 0 }} - {{ vehicle.rates.day.max | default: vehicle.rates.day.min }} VND</span>
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
      <p class="note"><em>Deposit: {{ vehicle.deposit.min | default: 0 }} - {{ vehicle.deposit.max | default: vehicle.deposit.min }} VND</em></p>
    </div>
    {% endif %}
  {% endfor %}
</div>

#### Automatic Scooters (Xe Ga)

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
      <p class="note"><em>Deposit: {{ vehicle.deposit.min | default: 0 }} - {{ vehicle.deposit.max | default: vehicle.deposit.min }} VND</em></p>
    </div>
    {% endif %}
  {% endfor %}
</div>

#### Electric Motorbikes (Xe Dien)

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
      <p class="note"><em>Deposit: {{ vehicle.deposit.min | default: 0 }} - {{ vehicle.deposit.max | default: vehicle.deposit.min }} VND</em></p>
    </div>
    {% endif %}
  {% endfor %}
</div>

#### Electric Scooters (Xe Dap Dien)

<div class="pricing-card glass-card">
  <h3>Electric Scooter</h3>
  <p>Lightweight, suitable for short distances. Please contact for current pricing.</p>
  <p class="note"><em>{{ pricing.vehicles | where: "id", "electric-scooter" | first | property: "note.en" | default: "Please contact Nguyen Tu to check current pricing" }}</em></p>
</div>

### Rental Types

<div class="rental-types">
  {% for rental in pricing.rental_types %}
  <div class="rental-type">
    <h4>{{ rental.name.en }}</h4>
    <p>{{ rental.description }}</p>
  </div>
  {% endfor %}
</div>

### Important Notes

- All prices are approximate and may change based on availability
- Deposit is required for all rentals
- Delivery fees may apply depending on location
- Please confirm final price and availability directly with Nguyen Tu before booking
- Rental period: Minimum 1 day, maximum 365 days
- All bikes come with helmet and basic insurance

### How to Book

1. **Choose Your Bike**: Select from our variety of motorcycles
2. **Check Pricing**: Use our calculator or view the price list above
3. **Contact Us**: Call, Zalo, or WhatsApp to confirm availability
4. **Confirm Details**: Agree on pickup/delivery location and time
5. **Pay Deposit**: Secure your booking with a deposit
6. **Enjoy Your Ride**: Start your Hanoi adventure!

<div class="cta-group">
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Call Now</a>
  <a href="{{ business.contact.zalo }}" class="btn btn-secondary">Zalo</a>
  <a href="{{ business.contact.whatsapp }}" class="btn btn-outline">WhatsApp</a>
</div>
