# TAXONOMY — kiến trúc chủ đề

## Mô hình

Blog → Parent hub → Child hub → Bài viết.

7 parent hub (ID ổn định):

| Parent | Slug | Hub | Mô tả |
|---|---|---|---|
| P-THUE-XE | `thue-xe` | /blog/thue-xe/ | Giá, thủ tục, đặt cọc, thuê ngày/tuần/tháng, nhận trả xe, sự cố |
| P-XE-MAY | `xe-may` | /blog/xe-may/ | Xe số, xe ga, 50cc, xe điện, các mẫu Honda/Yamaha, bảo dưỡng |
| P-PHAP-LY | `an-toan-phap-ly` | /blog/an-toan-phap-ly/ | GPLX, bảo hiểm, nồng độ cồn, phạt nguội, biển báo, giấy tờ, quy định |
| P-DU-LICH | `du-lich` | /blog/du-lich/ | Điểm đến, bảo tàng, phố cổ, Hồ Tây, Long Biên, ngoại thành |
| P-CUNG-DUONG | `cung-duong` | /blog/cung-duong/ | Nội thành, cuối tuần, Mai Châu, Mộc Châu, Hà Giang, các tỉnh phía Bắc |
| P-KY-NANG | `ky-nang` | /blog/ky-nang/ | Kỹ năng lái, tình huống, thời tiết, chở đồ, gửi xe, sức khỏe |
| P-HOI-DAP | `hoi-dap` | /blog/hoi-dap/ | Hỏi đáp giá, thủ tục, pháp lý, chọn xe, sự cố, người mới |

51 child hub: xem `data/content-taxonomy.json` (mục `children`, mỗi mục có `parent_id`, `slug`, `hub_url`, `description`, `planned_target`, `source_required`, `legal_risk`). Tệp được khôi phục từ seed `data/state/taxonomy-config.json` bằng `scripts/factory/restore-foundation.py`; không sửa tay.

## Quy tắc

- Mỗi hàng ma trận thuộc đúng MỘT parent và MỘT child. Không có hàng mồ côi, không child mồ côi.
- Child chưa có bài (status `hidden`) không có trang công khai cho tới khi có nội dung hữu ích. Trang hub hiện tại chỉ render child có bài đã xuất bản (39/51 child có trang công khai; 12 child chưa có bài nên chưa có trang).
- Kích thước cụm lành: ~30–400 bài. Ngưỡng rà soát: <10 = TOO_SMALL, >600 = TOO_LARGE. Hiện tại cụm nhỏ nhất 115, lớn nhất 357.
- Danh mục Jekyll legacy (Du lịch / Kinh nghiệm / Chia sẻ) vẫn giữ nguyên URL; bài legacy được ánh xạ logic vào taxonomy mới mà không đổi URL.

## URL công khai

- Bài mới: `/blog/{parent_slug}/{child_slug}/{article_slug}/` — viết bằng `permalink` trong frontmatter, tệp nguồn vẫn phẳng trong `_posts/`.
- Bài legacy: giữ nguyên URL `/blog/YYYY/MM/DD/slug/`.
- Trang hub: `/blog/{parent_slug}/`, trang child: `/blog/{parent_slug}/{child_slug}/`, trang tổng: `/blog/chu-de/`.

## Breadcrumb

Trang chủ → Cẩm nang (/blog/chu-de/) → Parent → Child → Bài. Trang mới dùng include `topic-breadcrumb.html`. Bài legacy có thể được làm giàu breadcrumb logic mà không đổi URL.

## Thêm/sửa taxonomy

Taxonomy là hợp đồng ổn định: không đổi ID, không đổi slug của hub đã công khai. Muốn thêm child mới: thêm vào `data/content-taxonomy.json` với ID mới, cập nhật validator, và không được vượt tổng 10.000 hàng.
