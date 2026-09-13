---
layout: category
title: "Kinh nghiệm"
description: "Kinh nghiệm thuê xe, chọn xe, kiểm tra xe và thủ tục cần biết"
---

{% assign business = site.data.business %}

## Bài viết về Kinh nghiệm

Dưới đây là các bài viết chia sẻ kinh nghiệm thuê xe máy, chọn xe phù hợp, kiểm tra xe trước khi nhận và các thủ tục cần thiết.

### Các bài viết mới nhất

{% assign category_posts = site.posts | where_exp: "post", "post.categories contains 'Kinh nghiệm'" %}

{% if category_posts.size > 0 %}
<div class="post-grid">
  {% for post in category_posts limit:10 %}
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
{% else %}
<p>Chưa có bài viết nào trong chủ đề này. Hãy quay lại sau!</p>
{% endif %}

### Chủ đề liên quan

- [Du lịch]({{ '/du-lich/' | relative_url }})
- [Chia sẻ]({{ '/chia-se/' | relative_url }})

### Bạn cần tư vấn về thuê xe?

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
