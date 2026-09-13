---
layout: category
title: "Guides - Nguyen Tu Blog"
description: "Comprehensive guides for motorcycle rental and exploring Hanoi."
lang: en
translation_key: guides
permalink: /en/guides/
category: Guides
---

{% assign en_posts = site.posts | where: "lang", "en" | where_exp: "post", "post.categories contains 'Guides' or post.categories contains 'Chia se'" | sort: "date", "desc" %}

## Guides

Comprehensive guides to help you navigate Hanoi:

{% if en_posts.size > 0 %}
<div class="post-grid">
  {% for post in en_posts %}
  <article class="post-card glass-card">
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    <p class="post-date">Posted on {{ post.date | date: "%B %d, %Y" }}</p>
    <p>{{ post.excerpt | strip_html | truncatewords:30 }}</p>
    <a href="{{ post.url | relative_url }}" class="read-more">Read more</a>
  </article>
  {% endfor %}
</div>
{% else %}
<p>No guide articles yet. Please check back soon!</p>
{% endif %}

<div class="cta-group">
  <a href="{{ '/en/blog/' | relative_url }}" class="btn btn-outline">Back to Blog</a>
</div>
