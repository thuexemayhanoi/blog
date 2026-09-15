---
layout: category
title: "Du lich - Blog Nguyen Tu"
description: "Cam nang du lich va dia diem noi bat de kham pha Ha Noi va Viet Nam bang xe may."
lang: vi
translation_key: travel
category: Du lich
permalink: /du-lich/
---

{% assign current_lang = page.lang | default: site.lang %}
{% assign posts = site.posts | where: "lang", "vi" %}

## Bai Viet Du Lich

Kham pha Ha Noi va nhung dia diem xung quanh voi nhung cam nang cua chung toi:

{% if posts.size > 0 %}
<div class="post-grid">
  {% for post in posts %}
  {% if post.categories contains 'Du lich' %}
  <article class="post-card glass-card">
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    <p class="post-date">Dang ngay {{ post.date | date: "%d/%m/%Y" }}</p>
    <p>{{ post.excerpt | strip_html | truncatewords:30 }}</p>
    <a href="{{ post.url | relative_url }}" class="read-more">Doc tiep</a>
  </article>
  {% endif %}
  {% endfor %}
</div>
{% else %}
<p>Chua co bai viet nao ve du lich. Hay quay lai sau!</p>
{% endif %}

<div class="cta-group">
  <a href="{{ '/blog/' | relative_url }}" class="btn btn-outline">Ve Blog</a>
</div>
