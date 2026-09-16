---
layout: page
title: "Liên hệ - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Thông tin liên hệ để thuê xe máy tại Hà Nội. Điện thoại, Zalo, WhatsApp, Google Maps và giờ hoạt động của Nguyễn Tú."
lang: vi
translation_key: contact
permalink: /lien-he/
---

{% assign business = site.data.business %}

## Liên hệ với Nguyễn Tú

Cảm ơn bạn quan tâm đến dịch vụ thuê xe máy tại Hà Nội của Nguyễn Tú. Chúng tôi sẵn sàng hỗ trợ các nhu cầu thuê xe trong giờ hoạt động, từ thuê theo ngày, tuần đến tháng.

### Thông tin liên hệ

<div class="contact-grid">
  <div class="contact-card glass-card">
    <h3>{% include icon.html name="map-pin" size="20" %} Địa chỉ</h3>
    <p>{{ business.address.full }}</p>
    <p><a href="{{ business.contact.maps }}" target="_blank" rel="noopener noreferrer">Xem trên Google Maps</a></p>
  </div>

  <div class="contact-card glass-card">
    <h3>{% include icon.html name="phone" size="20" %} Điện thoại</h3>
    <p><a href="{{ business.contact.phone_uri }}">{{ business.contact.phone }}</a></p>
    <p>Giờ hoạt động: {{ business.hours }}</p>
  </div>

  <div class="contact-card glass-card">
    <h3>{% include icon.html name="message" size="20" %} Email</h3>
    <p><a href="mailto:{{ business.contact.email }}">{{ business.contact.email }}</a></p>
    <p>Vui lòng để lại số điện thoại để chúng tôi liên hệ lại trong giờ hoạt động.</p>
  </div>
</div>

### Kết nối với chúng tôi

<div class="social-grid">
  <a href="{{ business.contact.zalo }}" class="social-card glass-card" target="_blank" rel="noopener noreferrer">
    <h3>{% include icon.html name="message" size="20" %} Zalo</h3>
    <p>Nhắn tin trên Zalo</p>
  </a>

  <a href="{{ business.contact.whatsapp }}" class="social-card glass-card" target="_blank" rel="noopener noreferrer">
    <h3>{% include icon.html name="whatsapp" size="20" %} WhatsApp</h3>
    <p>Nhắn tin trên WhatsApp</p>
  </a>

  <a href="{{ business.url }}" class="social-card glass-card" target="_blank" rel="noopener noreferrer">
    <h3>{% include icon.html name="external-link" size="20" %} Website</h3>
    <p>Truy cập website chính</p>
  </a>
</div>

### Câu hỏi thường gặp

#### Tôi cần những giấy tờ nào để thuê xe máy?

Bạn cần xuất trình khi nhận xe:

- Chứng minh nhân dân hoặc căn cước công dân (khách Việt Nam)
- Hộ chiếu (khách nước ngoài)
- Giấy phép lái xe phù hợp nếu thuê xe trên 50cc

Người thuê cần đủ 18 tuổi trở lên.

#### Thời gian thuê tối thiểu là bao nhiêu?

Thời gian thuê tối thiểu là 1 ngày. Chúng tôi nhận thuê theo tuần và theo tháng, mức giá cho từng loại xe được niêm yết tại trang [bảng giá thuê xe máy]({{ '/bang-gia/' | relative_url }}).

#### Xe có bảo hiểm không?

Người thuê tự mua bảo hiểm cho bản thân khi cần. Nguyễn Tú không cung cấp bảo hiểm cho người thuê xe. Bạn nên cân nhắc mua bảo hiểm du lịch hoặc bảo hiểm tai nạn từ công ty bảo hiểm trước chuyến đi.

#### Có giao xe đến nơi tôi không?

Chúng tôi nhận giao xe trong khu vực phục vụ quanh Hà Nội. Thời gian và chi phí giao nhận cần được xác nhận trực tiếp với Nguyễn Tú trước khi đặt xe. Không giao xe máy ngoài giờ hoạt động {{ business.hours }}.

#### Tiền đặt cọc là bao nhiêu?

Tiền đặt cọc phổ biến trong khoảng 2.000.000–5.000.000đ tùy loại xe. Mức đặt cọc cụ thể được xác nhận trực tiếp khi đặt xe và hoàn trả khi bạn trả xe đúng hẹn, xe không có hư hỏng phát sinh.

#### Tôi có thể hủy hoặc thay đổi lịch đặt xe không?

Có. Vui lòng liên hệ với chúng tôi sớm nhất có thể nếu bạn cần hủy hoặc thay đổi lịch đặt xe. Điều kiện hoàn trả tiền đặt cọc được thỏa thuận rõ ràng khi nhận xe.

#### Phương thức thanh toán nào được chấp nhận?

Chúng tôi nhận thanh toán bằng tiền mặt (VND) và các hình thức thanh toán di động phổ biến. Vui lòng xác nhận phương thức thanh toán với chúng tôi khi đặt xe.

#### Trả xe trễ giờ thì sao?

Phí trả xe trễ là 20.000đ mỗi giờ trễ. Nếu trễ hơn 6 tiếng, có thể tính thêm một ngày thuê theo loại xe, khoảng 150.000–200.000đ/ngày. Hãy chủ động báo trước nếu có thay đổi lịch trình.

### Sẵn sàng đặt xe?

Liên hệ với chúng tôi trong giờ hoạt động để đặt xe:

<div class="cta-group">
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary btn-large">Gọi {{ business.contact.phone }}</a>
  <a href="{{ business.contact.zalo }}" class="btn btn-secondary btn-large">Nhắn tin trên Zalo</a>
  <a href="{{ business.contact.whatsapp }}" class="btn btn-outline btn-large">Nhắn tin trên WhatsApp</a>
</div>
