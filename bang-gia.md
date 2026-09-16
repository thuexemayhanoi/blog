---
layout: page
title: "Bảng giá thuê xe máy Hà Nội - Thuê Xe Máy Hà Nội Nguyễn Tú"
description: "Bảng giá thuê xe máy tại Hà Nội theo ngày, tuần và tháng. Giá tham khảo các dòng xe số, xe ga và hướng dẫn đặt cọc, giao nhận từ Nguyễn Tú."
lang: vi
translation_key: pricing
permalink: /bang-gia/
---

{% assign pricing = site.data.pricing %}
{% assign business = site.data.business %}

## Bảng giá thuê xe máy tại Hà Nội

Tất cả mức giá trong trang này được niêm yết bằng Đồng Việt Nam (VND). Đây là bảng giá tham khảo. Giá thực tế, tình trạng xe, tiền đặt cọc và chi phí giao nhận cần được xác nhận trực tiếp với Nguyễn Tú trước khi đặt xe.

Bảng giá được chia theo ba hình thức thuê chính:

- **Theo ngày:** tính cho một chu kỳ 24 giờ kể từ thời điểm nhận xe, phù hợp với chuyến đi ngắn hoặc nhu cầu tạm thời.
- **Theo tuần:** tính cho 7 ngày liên tiếp, phù hợp với khách công tác hoặc du lịch dài ngày.
- **Theo tháng:** tính cho 30 ngày, dành cho người sinh sống và làm việc dài hạn tại Hà Nội.

Thời gian thuê tối thiểu là 1 ngày. Mức giá theo tuần và theo tháng thấp hơn so với giá ngày nhân số ngày tương ứng.

## Tính giá thuê nhanh

Sử dụng công cụ tính giá bên dưới để ước tính chi phí thuê theo loại xe và thời gian. Kết quả chỉ mang tính tham khảo; giá cuối cùng luôn được xác nhận trực tiếp khi đặt xe.

{% include rental-calculator.html %}

## Bảng giá theo loại xe

### Xe số

Xe số là nhóm xe vận hành bằng hộp số tay, phổ biến nhất tại Việt Nam, tiết kiệm xăng và bền bỉ. Đây là lựa chọn của phần lớn người đã quen lái xe máy tại Việt Nam.

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category == 'Xe số' %}
    <div class="pricing-card glass-card">
      <h3>{{ vehicle.name }}</h3>
      <p>{{ vehicle.description }}</p>
      <div class="price-grid">
        {% if vehicle.rates.day.min %}
        <div class="price-item">
          <span class="price-label">Theo ngày:</span>
          <span class="price-value">{{ vehicle.rates.day.min }} - {{ vehicle.rates.day.max | default: vehicle.rates.day.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.week.min %}
        <div class="price-item">
          <span class="price-label">Theo tuần:</span>
          <span class="price-value">{{ vehicle.rates.week.min }} - {{ vehicle.rates.week.max | default: vehicle.rates.week.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.month.min %}
        <div class="price-item">
          <span class="price-label">Theo tháng:</span>
          <span class="price-value">{{ vehicle.rates.month.min }} - {{ vehicle.rates.month.max | default: vehicle.rates.month.min }} VND</span>
        </div>
        {% endif %}
      </div>
      <p class="note"><em>Tiền đặt cọc: 2.000.000 - 5.000.000 VND (xác nhận trực tiếp)</em></p>
      {% if vehicle.popular %}
      <span class="badge popular">Lựa chọn phổ biến</span>
      {% endif %}
    </div>
    {% endif %}
  {% endfor %}
</div>

Chi tiết giá thuê xe số từng mẫu xe được cập nhật tại trang [giá thuê xe số Hà Nội]({{ '/bang-gia-xe-so/' | relative_url }}).

### Xe tay ga

Xe tay ga sử dụng hộp số tự động, chỉ cần vặn ga là xe chạy. Tư thế ngồi thẳng, thoải mái, dễ điều khiển nên rất phù hợp với người mới lái hoặc di chuyển trong phố cổ.

<div class="pricing-table">
  {% for vehicle in pricing.vehicles %}
    {% if vehicle.category == 'Xe ga' %}
    <div class="pricing-card glass-card">
      <h3>{{ vehicle.name }}</h3>
      <p>{{ vehicle.description }}</p>
      <div class="price-grid">
        {% if vehicle.rates.day.min %}
        <div class="price-item">
          <span class="price-label">Theo ngày:</span>
          <span class="price-value">{{ vehicle.rates.day.min }} - {{ vehicle.rates.day.max | default: vehicle.rates.day.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.week.min %}
        <div class="price-item">
          <span class="price-label">Theo tuần:</span>
          <span class="price-value">{{ vehicle.rates.week.min }} - {{ vehicle.rates.week.max | default: vehicle.rates.week.min }} VND</span>
        </div>
        {% endif %}
        {% if vehicle.rates.month.min %}
        <div class="price-item">
          <span class="price-label">Theo tháng:</span>
          <span class="price-value">{{ vehicle.rates.month.min }} - {{ vehicle.rates.month.max | default: vehicle.rates.month.min }} VND</span>
        </div>
        {% endif %}
      </div>
      <p class="note"><em>Tiền đặt cọc: 2.000.000 - 5.000.000 VND (xác nhận trực tiếp)</em></p>
      {% if vehicle.popular %}
      <span class="badge popular">Lựa chọn phổ biến</span>
      {% endif %}
    </div>
    {% endif %}
  {% endfor %}
</div>

Chi tiết từng dòng xe ga được cập nhật tại trang [giá thuê xe tay ga Hà Nội]({{ '/bang-gia-xe-ga/' | relative_url }}).

### Xe 50cc

Xe 50cc nhẹ nhàng, dung tích xi-lanh nhỏ, dễ điều khiển, thường được du khách nước ngoài lựa chọn cho các chuyến đi ngắn trong nội thành. Vui lòng liên hệ Nguyễn Tú để biết giá thuê xe 50cc hiện tại, vì mức giá phụ thuộc vào mẫu xe sẵn có.

Chi tiết tại trang [thuê xe 50cc Hà Nội]({{ '/bang-gia-xe-50cc/' | relative_url }}).

### Xe máy điện và xe đạp điện

Xe máy điện và xe đạp điện chạy bằng pin, không phát thải, vận hành êm ái và chi phí năng lượng thấp. Mức giá thuê xe điện thay đổi theo mẫu xe và tình trạng pin hiện có. Vui lòng liên hệ Nguyễn Tú để kiểm tra giá hiện tại trước khi đặt xe.

Chi tiết tại trang [thuê xe máy điện Hà Nội]({{ '/bang-gia-xe-dien/' | relative_url }}).

## Loại hình thuê

<div class="rental-types">
  {% for rental in pricing.rental_types %}
  <div class="rental-type">
    <h4>{{ rental.name }}</h4>
    <p>{{ rental.description }}</p>
  </div>
  {% endfor %}
</div>

## Tiền đặt cọc

Mọi hợp đồng thuê xe đều có tiền đặt cọc. Mức tham khảo từ 2.000.000đ đến 5.000.000đ tùy loại xe và thời gian thuê. Tiền cọc được hoàn trả đầy đủ sau khi bạn trả xe đúng thời gian thỏa thuận và xe không có hư hỏng ngoài mức hao mòn thông thường.

Lưu ý về tiền đặt cọc:

- Mức cọc chính xác được xác nhận trực tiếp với Nguyễn Tú khi đặt xe.
- Khi nhận xe, bạn và Nguyễn Tú cùng kiểm tra tình trạng xe trước khi ký kết nhận xe.
- Khi trả xe, tiền cọc được hoàn trả sau khi kiểm tra xe.

## Phí giao nhận xe

Bạn có thể nhận xe trực tiếp tại địa chỉ 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội, hoặc yêu cầu giao xe đến địa điểm trong khu vực phục vụ, bao gồm Long Biên, Bồ Đề, Gia Lâm, Hoàn Kiếm, Phố Cổ, Ba Đình, Tây Hồ và các khu vực nội thành khác.

Hai nguyên tắc về giao nhận:

- Thời gian và chi phí giao nhận phải được xác nhận trước khi đặt xe.
- Không giao xe máy ngoài giờ hoạt động (09:00 – 21:00).

## Trả xe và phí trả muộn

Vui lòng trả xe đúng thời gian đã thỏa thuận. Trường hợp trả muộn:

- Phí trễ được tính 20.000đ cho mỗi giờ muộn.
- Nếu trễ quá 6 tiếng, có thể tính thêm một ngày thuê theo loại xe, khoảng 150.000 – 200.000đ/ngày.

Nếu bạn cần kéo dài thời gian thuê, hãy thông báo sớm nhất có thể để sắp xếp lịch xe.

## Bảo hiểm

Bảo hiểm xe máy do người thuê tự mua. Nguyễn Tú không cung cấp bảo hiểm cho người thuê. Bạn nên cân nhắc mua bảo hiểm du lịch hoặc bảo hiểm tai nạn phù hợp trước khi sử dụng dịch vụ.

## Lưu ý quan trọng

- Tất cả giá đều là giá tham khảo và có thể thay đổi tùy theo tình trạng xe.
- Giấy tờ cần thiết: chứng minh nhân dân hoặc căn cước công dân (khách Việt Nam), hộ chiếu (khách nước ngoài); giấy phép lái xe phù hợp với xe trên 50cc.
- Người thuê đủ 18 tuổi trở lên.
- Không sử dụng xe vào mục đích trái pháp luật, không cho người khác điều khiển xe trong thời gian thuê.
- Vui lòng xác nhận giá cuối cùng và tình trạng xe trực tiếp với Nguyễn Tú trước khi đặt xe.
- Mũ bảo hiểm đi kèm xe khi nhận.

## Câu hỏi thường gặp

#### Giá trong bảng giá có phải giá cuối cùng không?

Không. Đây là giá tham khảo. Giá thực tế, tình trạng xe, tiền đặt cọc và chi phí giao nhận cần được xác nhận trực tiếp với Nguyễn Tú trước khi đặt xe.

#### Tôi nên thuê theo ngày hay theo tuần?

Nếu thuê từ 5 – 7 ngày trở lên, giá theo tuần thường rẻ hơn thuê lẻ từng ngày. Với nhu cầu trên một tháng, giá theo tháng là mức kinh tế nhất. Hãy liên hệ để được báo giá theo thời gian cụ thể.

#### Tiền đặt cọc bao nhiêu và khi nào được hoàn?

Mức tham khảo 2.000.000 – 5.000.000đ tùy loại xe. Tiền cọc được hoàn trả sau khi bạn trả xe đúng thời gian thỏa thuận và xe không có hư hỏng ngoài hao mòn thông thường.

#### Trả xe muộn bị tính thế nào?

Phí trễ 20.000đ cho mỗi giờ muộn. Nếu trễ quá 6 tiếng, có thể tính thêm một ngày thuê theo loại xe, khoảng 150.000 – 200.000đ/ngày. Nếu cần kéo dài thời gian thuê, hãy báo sớm.

#### Có phát sinh chi phí khác không?

Chi phí giao nhận (nếu yêu cầu giao tận nơi) và phí trễ giờ trả xe là hai khoản có thể phát sinh. Cả hai đều được xác nhận trước khi đặt xe hoặc tính theo thỏa thuận.

## Hướng dẫn đặt xe

1. **Chọn xe:** Xem bảng giá ở trên hoặc dùng công cụ tính giá để chọn loại xe phù hợp.
2. **Kiểm tra giá:** Xác nhận mức giá hiện hành cho loại xe và thời gian bạn cần.
3. **Liên hệ:** Gọi điện, Zalo hoặc WhatsApp để hỏi tình trạng xe sẵn có.
4. **Xác nhận chi tiết:** Thỏa thuận địa điểm nhận xe, thời gian nhận và trả xe.
5. **Đặt cọc:** Thực hiện đặt cọc theo mức đã thỏa thuận.
6. **Nhận xe:** Kiểm tra xe cùng Nguyễn Tú và bắt đầu hành trình.

Nếu bạn mới thuê xe máy lần đầu, hãy đọc thêm [kinh nghiệm thuê xe máy tại Hà Nội]({{ '/kinh-nghiem/' | relative_url }}) hoặc tìm hiểu thêm về [Nguyễn Tú]({{ '/gioi-thieu/' | relative_url }}) trước khi đặt xe.

<div class="cta-group">
  <a href="{{ business.contact.phone_uri }}" class="btn btn-primary">Gọi ngay</a>
  <a href="{{ business.contact.zalo }}" class="btn btn-secondary">Zalo</a>
  <a href="{{ business.contact.whatsapp }}" class="btn btn-outline">WhatsApp</a>
</div>
