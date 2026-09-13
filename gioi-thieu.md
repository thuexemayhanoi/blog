---
layout: page
title: "Giới thiệu"
description: "Giới thiệu về dịch vụ thuê xe máy tại Hà Nội từ Nguyễn Tú"
---

{% assign business = site.data.business %}

## Về Nguyễn Tú

<strong>{{ business.display_name }}</strong> là đơn vị cung cấp dịch vụ thuê xe máy uy tín tại Hà Nội. Với sự tận tâm và chuyên nghiệp, chúng tôi luôn đặt lợi ích của khách hàng lên hàng đầu.

## Mục đích của blog

Blog được xây dựng với mục đích:

- **Chia sẻ kinh nghiệm:** Hướng dẫn cách chọn xe phù hợp, thủ tục thuê xe, và những lưu ý quan trọng khi thuê xe máy tại Hà Nội.
- **Hỗ trợ khách hàng:** Cung cấp thông tin chi tiết về các loại xe, khu vực phục vụ, và dịch vụ của Nguyễn Tú.
- **Tạo cộng đồng:** Kết nối những người có nhu cầu thuê xe máy, chia sẻ những câu chuyện và kinh nghiệm thực tế.

## Cam kết của chúng tôi

Chúng tôi cam kết:

- Cung cấp xe chất lượng, được bảo dưỡng định kỳ
- Giá cả minh bạch, không phát sinh phí ẩn
- Giao xe tận nơi theo yêu cầu
- Hỗ trợ khách hàng trong giờ hoạt động {{ business.hours }}

## Dịch vụ của chúng tôi

{{ business.display_name }} cung cấp đa dạng các loại xe và hình thức thuê:

### Loại xe

{% for vehicle in business.vehicle_types %}
- **{{ vehicle.name }}:** {{ vehicle.description }}
  {% if vehicle.examples.size > 0 %}
  *Ví dụ: {{ vehicle.examples | join: ', ' }}*
  {% endif %}
{% endfor %}

### Hình thức thuê

{% for rental in business.rental_types %}
- **{{ rental.name }}:** {{ rental.description }}
{% endfor %}

## Khu vực phục vụ

Chúng tôi phục vụ chủ yếu tại các quận nội thành Hà Nội:

{% for area in business.areas %}
- {{ area }}
{% endfor %}

## Thông tin liên hệ

- **Địa chỉ:** {{ business.address.full }}
- **Điện thoại:** [{{ business.contact.phone }}]({{ business.contact.phone_uri }})
- **Email:** [{{ business.contact.email }}](mailto:{{ business.contact.email }})
- **Zalo:** [Nhắn Zalo]({{ business.contact.zalo }})
- **Giờ hoạt động:** {{ business.hours }}
- **Website chính:** [{{ business.url }}]({{ business.url }})

## Lưu ý quan trọng

- Tình trạng xe, giá thuê, tiền đặt cọc và chi phí giao nhận có thể thay đổi
- Cần xác nhận trực tiếp với Nguyễn Tú trước khi đặt xe
- Không giao xe ngoài giờ hoạt động
