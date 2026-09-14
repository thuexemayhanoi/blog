---
layout: category
title: "Travel - Nguyen Tu Blog"
description: "Travel guides and destination recommendations for exploring Hanoi and Vietnam by motorcycle."
lang: en
translation_key: travel
permalink: /en/travel/
category: Travel
---

{% assign en_posts = site.posts | where: "lang", "en" %}

## Travel Articles

Explore Hanoi and beyond with our travel guides:

{% if en_posts.size > 0 %}
<div class="post-grid">
  {% for post in en_posts %}
  {% if post.categories contains 'Travel' or post.categories contains 'Du lich' %}
  <article class="post-card glass-card">
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    <p class="post-date">Posted on {{ post.date | date: "%B %d, %Y" }}</p>
    <p>{{ post.excerpt | strip_html | truncatewords:30 }}</p>
    <a href="{{ post.url | relative_url }}" class="read-more">Read more</a>
  </article>
  {% endif %}
  {% endfor %}
</div>
{% else %}
<p>No travel articles yet. Please check back soon!</p>
{% endif %}

<div class="cta-group">
  <a href="{{ '/en/blog/' | relative_url }}" class="btn btn-outline">Back to Blog</a>
</div>
