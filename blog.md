---
layout: page
title: "Blog"
description: "Tất cả bài viết chia sẻ kinh nghiệm thuê xe máy tại Hà Nội"
---

{% assign business = site.data.business %}
{% assign categories = site.data.categories %}

## Blog Thuê Xe Máy Hà Nội

Xin chào! Blog này chia sẻ những kinh nghiệm, kiến thức hữu ích về dịch vụ thuê xe máy tại Hà Nội. Chúng tôi mong muốn mang đến cho bạn đọc những thông tin chính xác, cập nhật và thiết thực nhất.

## Các chủ đề chính

<div class="categories-grid">
  {% for category in categories %}
  <a href="{{ category.url | relative_url }}" class="category-card glass-card">
    <h3>{{ category.name }}</h3>
    <p>{{ category.description }}</p>
    <p>
      {% assign category_posts = site.posts | where_exp: "post", "post.categories contains category.name" %}
      {{ category_posts.size }} bài viết
    </p>
  </a>
  {% endfor %}
</div>

## Bài viết mới nhất

{% if site.posts.size > 0 %}
<div class="post-grid">
  {% for post in site.posts limit:10 %}
  <article class="post-card glass-card">
    {% if post.categories %}
    <span class="post-category">{{ post.categories | first }}</span>
    {% endif %}
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    <p class="post-date">📅 {{ post.date | date: "%d/%m/%Y" }}</p>
    <p>{{ post.excerpt | strip_html | truncatewords:25 }}</p>
    <a href="{{ post.url | relative_url }}" class="read-more">Đọc tiếp →</a>
  </article>
  {% endfor %}
</div>

{% if site.posts.size > 10 %}
<div class="text-center" style="margin-top: 2rem;">
  <a href="#" class="btn btn-outline">Xem thêm bài viết</a>
</div>
{% endif %}
{% else %}
<p>Chưa có bài viết nào. Hãy quay lại sau!</p>
{% endif %}

## Bạn cần thuê xe máy?

<div class="cta-group" style="justify-content: center; margin-top: 2rem;">
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">
    Gọi ngay {{ business.contact.phone }}
  </a>
  <a href="{{ business.contact.zalo }}" class="btn btn-secondary" target="_blank" rel="noopener noreferrer">
    Nhắn Zalo
  </a>
  <a href="{{ business.url }}" class="btn btn-outline" target="_blank" rel="noopener noreferrer">
    Website chính
  </a>
</div>
