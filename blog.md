---
layout: default
title: "Bài viết - Blog Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Tất cả bài viết chia sẻ kinh nghiệm thuê xe máy tại Hà Nội"
---

<section class="section">
  <div class="container">
    <h1>{{ page.title }}</h1>
    <p class="subtitle">Chia sẻ kinh nghiệm, kiến thức hữu ích về thuê xe máy tại Hà Nội</p>
    
    {% if site.posts.size > 0 %}
    <div class="post-grid">
      {% for post in site.posts %}
      <article class="post-card">
        <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
        <p class="post-date">{{ post.date | date: "%d/%m/%Y" }}</p>
        <p>{{ post.excerpt | strip_html | truncatewords:30 }}</p>
        <a href="{{ post.url | relative_url }}" class="read-more">Đọc tiếp</a>
      </article>
      {% endfor %}
    </div>
    {% else %}
    <p>Chưa có bài viết nào. Hãy quay lại sau!</p>
    {% endif %}
    
    <div class="text-center mt-4">
      <a href="{{ '/' | relative_url }}" class="btn btn-outline">← Về trang chủ</a>
    </div>
  </div>
</section>