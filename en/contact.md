---
layout: page
title: "Contact - Nguyen Tu Motorcycle Rental Hanoi"
description: "Contact Nguyen Tu for motorcycle rental in Hanoi. Phone, Zalo, WhatsApp, Google Maps."
lang: en
translation_key: contact
permalink: /en/contact/
---

{% assign business = site.data.business %}

## Contact Us

Thank you for your interest in Nguyen Tu Motorcycle Rental. We are here to help you with all your motorcycle rental needs in Hanoi.

### Contact Information

<div class="contact-grid">
  <div class="contact-card glass-card">
    <h3>📍 Address</h3>
    <p>{{ business.address.full }}</p>
    <p><a href="{{ business.contact.maps }}" target="_blank" rel="noopener noreferrer">View on Google Maps</a></p>
  </div>
  
  <div class="contact-card glass-card">
    <h3>📞 Phone</h3>
    <p><a href="{{ business.contact.phone_uri }}">{{ business.contact.phone }}</a></p>
    <p>Available: {{ business.hours }}</p>
  </div>
  
  <div class="contact-card glass-card">
    <h3>✉️ Email</h3>
    <p><a href="mailto:{{ business.contact.email }}">{{ business.contact.email }}</a></p>
    <p>Response within 24 hours</p>
  </div>
</div>

### Connect With Us

<div class="social-grid">
  <a href="{{ business.contact.zalo }}" class="social-card glass-card" target="_blank" rel="noopener noreferrer">
    <h3>💬 Zalo</h3>
    <p>Message us on Zalo</p>
  </a>
  
  <a href="{{ business.contact.whatsapp }}" class="social-card glass-card" target="_blank" rel="noopener noreferrer">
    <h3>📱 WhatsApp</h3>
    <p>Message us on WhatsApp</p>
  </a>
  
  <a href="{{ business.url }}" class="social-card glass-card" target="_blank" rel="noopener noreferrer">
    <h3>🌐 Website</h3>
    <p>Visit our main website</p>
  </a>
</div>

### Frequently Asked Questions

#### What documents do I need to rent a motorcycle?

You will need your passport or Vietnamese ID card. An international driving permit is recommended but not always required.

#### What is the minimum rental period?

The minimum rental period is 1 day. We also offer weekly and monthly rates with discounts.

#### Is insurance included?

Yes, basic insurance is included with all rentals. We recommend checking the coverage details with us.

#### Do you provide helmets?

Yes, we provide helmets with every rental at no additional cost.

#### Can you deliver the motorcycle to my location?

Yes, we offer delivery service within Hanoi. Delivery fees may apply depending on the distance.

#### What is your cancellation policy?

Please contact us as soon as possible if you need to cancel or modify your booking. Cancellation fees may apply depending on how much notice you give.

#### What payment methods do you accept?

We accept cash (VND) and mobile payments. Please confirm payment methods when booking.

### Ready to Book?

Contact us now to reserve your motorcycle:

<div class="cta-group">
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary btn-large">Call {{ business.contact.phone }}</a>
  <a href="{{ business.contact.zalo }}" class="btn btn-secondary btn-large">Message on Zalo</a>
  <a href="{{ business.contact.whatsapp }}" class="btn btn-outline btn-large">Message on WhatsApp</a>
</div>
