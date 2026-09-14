---
layout: page
title: "Blog - Thue Xe May Ha Noi Nguyen Tu"
description: "Kinh nghiem thue xe may Ha Noi, huong dan di chuyen, bang gia va cac bai viet huu ich tu Nguyen Tu."
lang: vi
translation_key: blog
---

{% assign business = site.data.business %}
{% assign current_lang = page.lang | default: site.lang %}

## Blog Cua Chung Toi

Chao mung den voi blog cua Nguyen Tu Motorcycle Rental! Tai day, ban se tim thay nhung thong tin huu ich ve viec thue xe may tai Ha Noi, nhung kinh nghiem di chuyen va cac cam nang du lich.

### Bai Viet Moi Nhat

{% if site.posts.size > 0 %}
<div class="post-grid">
  {% for post in site.posts limit:6 %}
  <article class="post-card glass-card">
    {% if post.categories %}
    <span class="post-category">{{ post.categories | first }}</span>
    {% endif %}
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    <p class="post-date">Dang ngay {{ post.date | date: "%d/%m/%Y" }}</p>
    <p>{{ post.excerpt | strip_html | truncatewords:25 }}</p>
    <a href="{{ post.url | relative_url }}" class="read-more">Doc tiep</a>
  </article>
  {% endfor %}
</div>
{% else %}
<p>Chua co bai viet nao. Hay quay lai sau!</p>
{% endif %}

### Chu De Blog

<div class="categories-grid">
  {% assign nav = site.data.navigation.main %}
  {% for item in nav %}
    {% if item.id == 'blog' %}
      {% for child in item.children %}
      <a href="{{ child.url | relative_url }}" class="category-card glass-card">
        <h3>{{ child.name }}</h3>
        <p>
          {% assign category_posts = site.posts | where_exp: "post", "post.categories contains child.name" %}
          {{ category_posts.size }} bai viet
        </p>
      </a>
      {% endfor %}
    {% endif %}
  {% endfor %}
</div>

### Ve Blog Cua Chung Toi

Blog cua chung toi bao gom cac chu de da dang de giup ban tai su dung toi da trai nghiem thue xe may tai Ha Noi:

- **Du Lich**: Kham pha nhung tuyen duong va dia diem noi bat xung quanh Ha Noi
- **Kinh Nghiem**: Hoc cach thue xe may an toan va hieu qua
- **Chia Se**: Cac loi khuyen thu te cho viec di chuyen bang xe may

### Dang Ky

Hay luu lai trang nay va tham ghi thong tin moi nhat tu Nguyen Tu!

### Ban Can Thue Xe May?

San sang kham pha Ha Noi tren hai banh? Lien he voi chung toi:

<div class="cta-group">
  <a href="{{ '/bang-gia/' | relative_url }}" class="btn btn-primary">Xem Bang Gia</a>
  <a href="{{ business.contact.phone_uri }}" class="btn btn-secondary">Go Ngay</a>
  <a href="{{ business.contact.zalo }}" class="btn btn-outline">Zalo</a>
</div>
