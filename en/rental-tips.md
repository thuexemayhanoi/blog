---
layout: category
title: "Rental Tips - Nguyen Tu Blog"
description: "Practical tips and advice for renting motorcycles in Hanoi safely and efficiently."
lang: en
translation_key: rental-tips
permalink: /en/rental-tips/
category: Rental Tips
---

{% assign en_posts = site.posts | where: "lang", "en" %}

## Rental Tips

Learn how to rent a motorcycle safely and get the most value:

{% if en_posts.size > 0 %}
<div class="post-grid">
  {% for post in en_posts %}
  {% if post.categories contains 'Rental Tips' or post.categories contains 'Kinh nghiem' %}
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
<p>No rental tips articles yet. Please check back soon!</p>
{% endif %}

<div class="cta-group">
  <a href="{{ '/en/blog/' | relative_url }}" class="btn btn-outline">Back to Blog</a>
</div>
