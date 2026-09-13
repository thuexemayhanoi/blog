---
layout: default
title: "Blog - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Tất cả bài viết chia sẻ kinh nghiệm về thuê xe máy, du lịch và hướng dẫn tại Hà Nội"
permalink: /blog/
---

{% assign business = site.data.business %}

<section class="section">
  <div class="container">
    <h1>{{ page.title | split: ' - ' | first }}</h1>
    <p class="page-description">{{ page.description }}</p>
    
    <!-- Category Filter -->
    <div class="blog-filter">
      <span class="filter-label">Lọc theo chuyên mục:</span>
      <div class="filter-tags">
        <a href="{{ '/blog/' | relative_url }}" class="filter-tag {% if page.url == '/blog/' %}active{% endif %}">Tất cả</a>
        {% assign nav = site.data.navigation.main %}
        {% for item in nav %}
          {% if item.name == 'Blog' %}
            {% for child in item.children %}
            <a href="{{ child.url | relative_url }}" class="filter-tag">{{ child.name }}</a>
            {% endfor %}
          {% endif %}
        {% endfor %}
      </div>
    </div>
    
    <!-- Posts Grid -->
    {% if site.posts.size > 0 %}
    <div class="post-grid">
      {% for post in site.posts %}
      <article class="post-card glass-card">
        {% if post.categories %}
        <span class="post-category">{{ post.categories | first }}</span>
        {% endif %}
        <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
        <p class="post-date">📅 {{ post.date | date: "%d/%m/%Y" }}</p>
        <p>{{ post.excerpt | strip_html | truncatewords:30 }}</p>
        <div class="post-meta">
          {% if post.author %}
          <span class="post-author">✍️ {{ post.author }}</span>
          {% endif %}
          {% if post.tags.size > 0 %}
          <span class="post-tags">
            {% for tag in post.tags limit:3 %}
            <span class="tag">{{ tag }}</span>
            {% endfor %}
          </span>
          {% endif %}
        </div>
        <a href="{{ post.url | relative_url }}" class="read-more">Đọc tiếp →</a>
      </article>
      {% endfor %}
    </div>
    {% else %}
    <p>Chưa có bài viết nào. Hãy quay lại sau!</p>
    {% endif %}
  </div>
</section>