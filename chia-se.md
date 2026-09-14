---
layout: category
title: "Chia se - Blog Nguyen Tu"
description: "Cac loi khuyen va cam nang thu te cho viec thue xe may va di chuyen tai Ha Noi."
lang: vi
translation_key: sharing
category: Chia se
---

{% assign current_lang = page.lang | default: site.lang %}
{% assign posts = site.posts | where: "lang", "vi" %}

## Bai Viet Chia Se

Cac loi khuyen thu te cho viec thue xe may va di chuyen tai Ha Noi:

{% if posts.size > 0 %}
<div class="post-grid">
  {% for post in posts %}
  {% if post.categories contains 'Chia se' %}
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
<p>Chua co bai viet nao ve chia se. Hay quay lai sau!</p>
{% endif %}

<div class="cta-group">
  <a href="{{ '/blog/' | relative_url }}" class="btn btn-outline">Ve Blog</a>
</div>
