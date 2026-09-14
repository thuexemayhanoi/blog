---
layout: page
title: "About - Nguyen Tu Motorcycle Rental Hanoi"
description: "Learn about Nguyen Tu motorcycle rental service in Hanoi. Quality bikes, transparent pricing, delivery service."
lang: en
translation_key: about
permalink: /en/about/
---

{% assign business = site.data.business %}

## About Nguyen Tu Motorcycle Rental

{{ business.display_name }} is a trusted motorcycle rental service provider in Hanoi, Vietnam. We specialize in providing quality motorcycles for tourists and locals at competitive prices.

### Our Services

- **Motorcycle Rental**: Daily, weekly, and monthly rental options
- **Variety of Bikes**: Manual motorbikes (xe so), automatic scooters (xe ga), electric motorbikes, and 50cc bikes
- **Delivery Service**: We deliver bikes to your location in Hanoi
- **Quality Assurance**: All our motorcycles are regularly maintained and in excellent condition
- **Transparent Pricing**: No hidden fees, clear pricing structure

### Why Choose Us?

1. **Reliable Service**: We have been serving customers in Hanoi with dedication
2. **Quality Motorcycles**: Our fleet includes popular models like Honda Wave, Honda Vision, Honda Air Blade, and more
3. **Flexible Rental Terms**: Rent by day, week, or month according to your needs
4. **Convenient Delivery**: We bring the bike to you, saving you time and effort
5. **24/7 Support**: We are available to assist you during your rental period

### Our Location

{% include icon.html name="map-pin" size="16" %} **Address**: {{ business.address.full }}

{% include icon.html name="phone" size="16" %} **Phone**: [{{ business.contact.phone }}]({{ business.contact.phone_uri }})

{% include icon.html name="message" size="16" %} **Email**: [{{ business.contact.email }}](mailto:{{ business.contact.email }})

{% include icon.html name="info" size="16" %} **Hours**: {{ business.hours }}

### Contact Us

For inquiries and bookings, please contact us through:

- [Call us]({{ business.contact.phone_uri }})
- [Zalo]({{ business.contact.zalo }})
- [WhatsApp]({{ business.contact.whatsapp }})
- [View on Google Maps]({{ business.contact.maps }})

We look forward to serving you!
