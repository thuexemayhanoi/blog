---
layout: home
title: "Nguyen Tu Motorcycle Rental Hanoi"
description: "Rent a motorcycle in Hanoi with Nguyen Tu. Quality bikes, transparent pricing, delivery service."
lang: en
translation_key: home
title_vi: "Thue Xe May Ha Noi Nguyen Tu"
url: /en/
permalink: /en/
---

{% assign business = site.data.business %}
{% assign pricing = site.data.pricing %}

<!-- Hero Section -->
<section class="hero">
  <div class="container">
    <div class="hero-content">
      <h1 class="hero-title">Nguyen Tu Motorcycle Rental</h1>
      <p class="hero-subtitle">Quality motorcycle rental service in Hanoi Old Quarter. Reliable, safe, and convenient.</p>
      
      <div class="hero-cta">
        <a href="{{ '/en/blog/' | relative_url }}" class="btn btn-primary">View Blog</a>
        <a href="{{ '/en/pricing/' | relative_url }}" class="btn btn-secondary">View Pricing</a>
        <a href="{{ business.contact.phone_uri }}" class="btn btn-outline">Call {{ business.contact.phone }}</a>
        <a href="{{ business.contact.zalo }}" class="btn btn-outline">Zalo</a>
      </div>
    </div>
    
    <!-- Premium Visual Card (CSS only) -->
    <div class="hero-visual">
      <div class="visual-card glass-card"></div>
    </div>
  </div>
</section>

<!-- Rental Calculator -->
{% include rental-calculator.html %}

<!-- Quick Introduction -->
<section class="section intro-section">
  <div class="container">
    <h2>About {{ business.brand }}</h2>
    <p class="intro-text">
      {{ business.display_name }} provides reliable motorcycle rental services in Hanoi. We are committed to delivering quality, safety, and convenience.
    </p>
    
    <div class="intro-features">
      <div class="intro-feature">
        <span class="feature-icon">OK</span>
        <span class="feature-text">Quality Bikes</span>
      </div>
      <div class="intro-feature">
        <span class="feature-icon">OK</span>
        <span class="feature-text">Transparent Pricing</span>
      </div>
      <div class="intro-fe

ature">
        <span class="feature-icon">OK</span>
        <span class="feature-text">Delivery Service</span>
      </div>
      <div class="intro-feature">
        <span class="feature-icon">OK</span>
        <span class="feature-text">Hours: {{ business.hours }}</span>
      </div>
    </div>
  </div>
</section>

<!-- Services Section -->
<section class="section services-section">
  <div class="container">
    <h2>Our Services</h2>
    <p>We offer a variety of motorcycles to meet all your needs:</p>
    
    <div class="services-grid">
      {% for vehicle in business.vehicle_types %}
      <div class="service-card glass-card">
        <h3>{{ vehicle.name }}</h3>
        <p>{{ vehicle.description }}</p>
        {% if vehicle.examples and vehicle.examples.size > 0 %}
        <p class="examples"><em>Examples: {{ vehicle.examples | join: ', ' }}</em></p>
        {% endif %}
      </div>
      {% endfor %}
    </div>
  </div>
</section>

<!-- Latest Posts -->
<section class="section posts-section">
  <div class="container">
    <h2>Latest Posts</h2>
    
    {% assign en_posts = site.posts | where: "lang", "en" %}
    {% if en_posts.size > 0 %}
    <div class="post-grid">
      {% for post in en_posts limit:4 %}
      <article class="post-card glass-card">
        {% if post.categories %}
        <span class="post-category">{{ post.categories | first }}</span>
        {% endif %}
        <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
        <p class="post-date">{{ post.date | date: "%d/%m/%Y" }}</p>
        <p>{{ post.excerpt | strip_html | truncatewords:25 }}</p>
        <a href="{{ post.url | relative_url }}" class="read-more">Read more</a>
      </article>
      {% endfor %}
    </div>
    
    <div class="text-center mt-4">
      <a href="{{ '/en/blog/' | relative_url }}" class="btn btn-outline">View all posts</a>
    </div>
    {% else %}
    <p>No posts yet. Please check back later!</p>
    {% endif %}
  </div>
</section>

<!-- Blog Ca
t
egories -->
<section class="section categories-section bg-light">
  <div class="container">
    <h2>Blog Categories</h2>
    
    <div class="categories-grid">
      {% assign nav = site.data.navigation.main %}
      {% for item in nav %}
        {% if item.id == 'blog' %}
          {% for child in item.children %}
          <a href="{{ '/en' | append: child.url | relative_url }}" class="category-card glass-card">
            <h3>{{ child.name }}</h3>
            <p>
              {% assign category = child.name %}
              {% assign category_posts = site.posts | where: "lang", "en" %}
              {% for post in category_posts %}
                {% if post.categories contains child.name %}
                  {{ forloop.index }}
                {% endif %}
              {% endfor %}
              posts
            </p>
          </a>
          {% endfor %}
        {% endif %}
      {% endfor %}
    </div>
  </div>
</section>

<!-- Pricing Preview -->
<section class="section pricing-preview">
  <div class="container">
    <h2>Pricing</h2>
    <p>Check out our motorcycle rental prices:</p>
    
    <div class="pricing-grid">
      {% assign nav = site.data.navigation.main %}
      {% for item in nav %}
        {% if item.id == 'pricing' %}
          {% for child in item.children %}
          <a href="{{ '/en' | append: child.url | relative_url }}" class="pricing-card glass-card">
            <h3>{{ child.name }}</h3>
            <p>View details</p>
          </a>
          {% endfor %}
        {% endif %}
      {% endfor %}
    </div>
    
    <div class="text-center mt-4">
      <a href="{{ '/en/pricing/' | relative_url }}" class="btn btn-outline">View all pricing</a>
    </div>
  </div>
</section>

<!-- Service Areas -->
<section class="section areas-section">
  <div class="container">
    <h2>Service Areas</h2>
    <p>We primarily serve the central districts of Hanoi:</p>
    
    <div class="areas-list">
      {% for area in business.areas %}
      <span cl
as
s="area-tag">{{ area }}</span>
      {% endfor %}
    </div>
    
    <p class="note"><em>Note: Delivery time and fees may vary depending on the area. Please confirm before booking.</em></p>
  </div>
</section>

<!-- About Nguyen Tu -->
<section class="section about-section bg-light">
  <div class="container">
    <h2>About {{ business.brand }}</h2>
    <div class="about-content">
      <div class="about-text">
        <p><strong>{{ business.display_name }}</strong> is a trusted motorcycle rental service provider in Hanoi. With dedication and professionalism, we always prioritize customer benefits.</p>
        <p>We commit to:</p>
        <ul class="commitments">
          <li>Providing quality motorcycles, regularly maintained</li>
          <li>Transparent pricing, no hidden fees</li>
          <li>Delivery to your location upon request</li>
        </ul>
      </div>
      
      <div class="about-contact">
        <h3>Contact Information</h3>
        <address>
          <p>{% include icon.html name="map-pin" %} {{ business.address.full }}</p>
          <p>{% include icon.html name="phone" %} <a href="{{ business.contact.phone_uri }}">{{ business.contact.phone }}</a></p>
          <p>{% include icon.html name="message" %} <a href="mailto:{{ business.contact.email }}">{{ business.contact.email }}</a></p>
          <p>🕒 {{ business.hours }}</p>
        </address>
      </div>
    </div>
  </div>
</section>

<!-- Final CTA -->
<section class="section cta-section">
  <div class="container text-center">
    <h2>Need to rent a motorcycle in Hanoi?</h2>
    <p>Contact {{ business.brand }} for the best advice and support.</p>
    <div class="cta-group">
      <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Call {{ business.contact.phone }}</a>
      <a href="{{ business.contact.zalo }}" class="btn btn-secondary">Zalo</a>
      <a href="{{ business.url }}" class="btn btn-outline" target="_blank" rel="noopener noreferrer">Main Website</a>
    </div>
 
 </div>
</section>
