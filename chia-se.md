---
layout: category
title: "Chia sẻ - Blog Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Chia sẻ kiến thức, mẹo hay và câu chuyện về thuê xe máy tại Hà Nội"
permalink: /chia-se/
category: "Chia sẻ"
---

{% assign business = site.data.business %}

<section class="section">
  <div class="container">
    <h1>{{ page.title | split: ' - ' | first }}</h1>
    <p class="page-description">{{ page.description }}</p>
    
    {% assign category_posts = site.posts | where_exp: "post", "post.categories contains page.category" %}
    
    {% if category_posts.size > 0 %}
    <div class="post-grid">
      {% for post in category_posts %}
      <article class="post-card">
        <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
        <p class="post-date">{{ post.date | date: "%d/%m/%Y" }}</p>
        <p>{{ post.excerpt | strip_html | truncatewords:30 }}</p>
        <a href="{{ post.url | relative_url }}" class="read-more">Đọc tiếp</a>
      </article>
      {% endfor %}
    </div>
    {% else %}
    <p>Chưa có bài viết nào trong chuyên mục này. Hãy quay lại sau!</p>
    {% endif %}
    
    <div class="cta-section text-center">
      <a href="{{ '/blog/' | relative_url }}" class="btn btn-outline">← Quay lại Blog</a>
    </div>
  </div>
</section>