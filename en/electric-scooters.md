---
layout: page
title: "Electric Scooters - Pricing"
description: "Pricing for electric scooters (xe dap dien) rental in Hanoi. Lightweight for short distances."
lang: en
translation_key: xe-50cc
permalink: /en/electric-scooters/
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Electric Scooters Pricing

Electric scooters (Xe Dap Dien) are lightweight vehicles suitable for short distances. Please contact us for current pricing.

### Features

- Lightweight and easy to maneuver
- Perfect for short trips
- Environmentally friendly
- Low maintenance

<div class="pricing-card glass-card">
  <p>{{ pricing.vehicles | where: "id", "electric-scooter" | first | property: "note.en" | default: "Please contact Nguyen Tu to check current pricing" }}</p>
</div>

<div class="cta-group">
  <a href="{{ '/en/pricing/' | relative_url }}" class="btn btn-outline">Back to All Pricing</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Call to Inquire</a>
</div>
