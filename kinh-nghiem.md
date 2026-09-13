---
layout: category
title: "Kinh nghiem - Blog Nguyen Tu"
description: "Kinh nghiem thue xe may tai Ha Noi, tu chon xe den su dung an toan va hieu qua."
lang: vi
translation_key: experience
category: Kinh nghiem
---

{% assign posts = site.posts | where_exp: "post", "post.categories contains 'Kinh nghiem'" | sort: "date", "desc" %}

## Kinh Nghiem Thue Xe May

Hoc cach thue xe may an toan va hieu qua tai Ha Noi:

{% if posts.size > 0 %}
<div class="post-grid">
  {% for post in posts %}
  <article class="post-card glass-card">
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    <p class="post-date">Dang ngay {{ post.date | date: "%d/%m/%Y" }}</p>
    <p>{{ post.excerpt | strip_html | truncatewords:30 }}</p>
    <a href="{{ post.url | relative_url }}" class="read-more">Doc tiep</a>
  </article>
  {% endfor %}
</div>
{% else %}
<p>Chua co bai viet nao ve kinh nghiem. Hay quay lai sau!</p>
{% endif %}

<div class="cta-group">
  <a href="{{ '/blog/' | relative_url }}" class="btn btn-outline">Ve Blog</a>
</div>
