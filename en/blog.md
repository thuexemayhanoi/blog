---
layout: page
title: "Blog - Nguyen Tu Motorcycle Rental Hanoi"
description: "Travel tips, motorcycle rental guides, and Hanoi experiences from Nguyen Tu."
lang: en
translation_key: blog
permalink: /en/blog/
---

{% assign business = site.data.business %}
{% assign current_lang = page.lang | default: site.lang %}

## Our Blog

Welcome to the Nguyen Tu Motorcycle Rental blog! Here you will find useful information about renting motorcycles in Hanoi, travel tips, and local experiences.

### Latest Posts

{% assign en_posts = site.posts | where: "lang", "en" %}

{% if en_posts.size > 0 %}
<div class="post-grid">
  {% for post in en_posts %}
  <article class="post-card glass-card">
    {% if post.categories %}
    <span class="post-category">{{ post.categories | first }}</span>
    {% endif %}
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    <p class="post-date">Posted on {{ post.date | date: "%B %d, %Y" }}</p>
    <p>{{ post.excerpt | strip_html | truncatewords:30 }}</p>
    <a href="{{ post.url | relative_url }}" class="read-more">Read more</a>
  </article>
  {% endfor %}
</div>
{% else %}
<p>No posts available yet. Please check back soon!</p>
{% endif %}

### Blog Categories

<div class="categories-grid">
  {% assign nav = site.data.navigation.main %}
  {% for item in nav %}
    {% if item.id == 'blog' %}
      {% for child in item.children %}
      <a href="{{ '/en' | append: child.url | relative_url }}" class="category-card glass-card">
        <h3>{{ child.name }}</h3>
        <p>
          {% assign category_posts = site.posts | where_exp: "post", "post.categories contains child.name" | where: "lang", "en" %}
          {{ category_posts.size }} posts
        </p>
      </a>
      {% endfor %}
    {% endif %}
  {% endfor %}
</div>

### About Our Blog

Our blog covers various topics to help you make the most of your Hanoi motorcycle rental experience:

- **Travel (Du Lich)**: Discover the best routes and destinations around Hanoi
- **Rental Tips (Kinh Nghiem)**: Learn how to rent a motorcycle safely and efficiently
- **Guides (Chia Se)**: Practical advice for exploring Hanoi by motorcycle

### Subscribe

Stay updated with our latest posts and rental tips. Bookmark this page and check back regularly!

### Need a Motorcycle?

Ready to explore Hanoi on two wheels? Contact us now:

<div class="cta-group">
  <a href="{{ '/en/pricing/' | relative_url }}" class="btn btn-primary">View Pricing</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-secondary">Call Now</a>
  <a href="{{ business.contact.zalo }}" class="btn btn-outline">Zalo</a>
</div>
