---
layout: page
title: "Lien he - Thue Xe May Ha Noi Nguyen Tu"
description: "Thong tin lien he de thue xe may tai Ha Noi. Dien thoai, Zalo, WhatsApp, Google Maps."
lang: vi
translation_key: contact
---

{% assign business = site.data.business %}

## Lien He Voi Chung Toi

Cam on ban da quan tam den dich vu thue xe may tai Ha Noi cua Nguyen Tu. Chung toi o day de ho tro ban voi tat ca nhu cau thue xe may.

### Thong Tin Lien He

<div class="contact-grid">
  <div class="contact-card glass-card">
    <h3>{% include icon.html name="map-pin" size="20" %} Dia Chi</h3>
    <p>{{ business.address.full }}</p>
    <p><a href="{{ business.contact.maps }}" target="_blank" rel="noopener noreferrer">Xem tren Google Maps</a></p>
  </div>
  
  <div class="contact-card glass-card">
    <h3>{% include icon.html name="phone" size="20" %} Dien Thoai</h3>
    <p><a href="{{ business.contact.phone_uri }}">{{ business.contact.phone }}</a></p>
    <p>Gio lam viec: {{ business.hours }}</p>
  </div>
  
  <div class="contact-card glass-card">
    <h3>{% include icon.html name="message" size="20" %} Email</h3>
    <p><a href="mailto:{{ business.contact.email }}">{{ business.contact.email }}</a></p>
    <p>Tra loi trong vòng 24 gio</p>
  </div>
</div>

### Ket Noi Voi Chung Toi

<div class="social-grid">
  <a href="{{ business.contact.zalo }}" class="social-card glass-card" target="_blank" rel="noopener noreferrer">
    <h3>{% include icon.html name="message" size="20" %} Zalo</h3>
    <p>Nhan tin tren Zalo</p>
  </a>
  
  <a href="{{ business.contact.whatsapp }}" class="social-card glass-card" target="_blank" rel="noopener noreferrer">
    <h3>{% include icon.html name="whatsapp" size="20" %} WhatsApp</h3>
    <p>Nhan tin tren WhatsApp</p>
  </a>
  
  <a href="{{ business.url }}" class="social-card glass-card" target="_blank" rel="noopener noreferrer">
    <h3>{% include icon.html name="external-link" size="20" %} Website</h3>
    <p>Truy cap website chinh</p>
  </a>
</div>

### Cau Hoi Thuong Gap

#### Toi can nhung giay to nao de thue xe may?

Ban can su dung:
- Chung minh nhan dan / Can cuoc cong dan (cho nguoi Viet Nam)
- Ho chieu (cho du khach nuoc ngoai)
- Giay phep lai xe (neu thue xe tren 50cc)

#### Thoi gian thue toi thieu la bao nhieu?

Thoi gian thue toi thieu
 la 1 ngay. Chung toi cung cap thue theo tuan va thang voi nhung uu dai ve gia.

#### Xe co bao hiem khong?

Co. Tat ca cac xe deu di kem bao hiem co ban. Ban nen kiem tra ky pham vi bao hiem truoc khi thue.

#### Ban co giao xe den noi toi khong?

Co. Chung toi co dich vu giao xe tan noi tai cac khu vuc phuc vu. Phi giao xe co the ap dung tuy thuoc vao khoang cach.

#### Toi co the huy dat xe khong?

Co. Vui long lien he voi chung toi cach som nhat neu ban can huy ho thay doi lich dat xe.

#### Phuong thuc thanh toan nao duoc chap nhan?

Chung toi chap nhan tien mat (VND) va cac hinh thuc thanh toan di dong. Vui long xac nhan phuong thuc thanh toan khi dat xe.

### San Sang Dat Xe?

Lien he voi chung toi ngay de dat xe:

<div class="cta-group">
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary btn-large">Go {{ business.contact.phone }}</a>
  <a href="{{ business.contact.zalo }}" class="btn btn-secondary btn-large">Nhan tin tren Zalo</a>
  <a href="{{ business.contact.whatsapp }}" class="btn btn-outline btn-large">Nhan tin tren WhatsApp</a>
</div>
