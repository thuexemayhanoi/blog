# ARTICLE RULES — quy tắc viết bài

Áp dụng cho mọi bài factory. Vi phạm mức BLOCKED: không xuất bản.

## Ngôn ngữ và định dạng

- Tiếng Việt 100%, giữ nguyên dấu. Không đưa UI tiếng Anh vào bài.
- Frontmatter: `layout: post`, `title`, `date`, `author: "Nguyễn Tú"`, `description`, `categories` (Du lịch / Kinh nghiệm / Chia sẻ), `lang: vi`, `tags`, `parent_id`, `child_id`, `permalink` (đúng `output_path` trong ma trận), `article_id`.
- Một H1 duy nhất (layout render). Cấu trúc H2/H3 rõ ràng, đoạn ngắn, danh sách khi hữu ích.
- Độ dài theo `word_target` của hàng trong ma trận (±15%).
- Không emoji làm icon chức năng; dùng icon SVG sẵn có khi cần.
- Link nội bộ: các liên kết trong `internal_links`/`output_path` là đường dẫn gốc-tương-đối của site (không có tiền tố `/blog`). Khi nhúng vào bài phải dùng bộ lọc Liquid `relative_url` (ví dụ `{{ '/thue-xe/' | relative_url }}` ra `/blog/thue-xe/`). Không hardcode `/blog` hai lần, không dùng URL tuyệt đối nội bộ.

## Dữ liệu kinh doanh (business facts)

Chỉ dùng dữ liệu trong `data/business-facts.json` (nguồn `_data/business.yml`, `_data/pricing.yml`):

- Giờ hoạt động 09:00–21:00. Địa chỉ 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội.
- Giá chỉ theo bảng giá đã duyệt; xe điện / xe đạp điện: "liên hệ để xác nhận".
- Tiền đặt cọc: "cần xác nhận trực tiếp", không nêu con số.
- Không giao xe ngoài giờ hoạt động; thời gian và chi phí giao nhận phải xác nhận trước khi đặt xe.

Cấm bịa: khuyến mại, phí giao xe cố định, số lượng khách, số năm kinh nghiệm, xếp hạng, cam kết, hỗ trợ 24/7, đánh giá khách hàng.

## Pháp lý

Với hàng `source_required = true` (toàn bộ parent `an-toan-phap-ly` và các hàng `legal_risk = high`):

- Mỗi nhận định pháp lý: CLAIM → SUBJECT → CONDITION → QUY ĐỊNH HIỆN HÀNH → PHIÊN BẢN CÓ HIỆU LỰC → NGUỒN CHÍNH THỨC (văn bản pháp luật, cơ quan nhà nước).
- Không chắc chắn → REVIEW hoặc BLOCKED, không đoán số tiền phạt hay mốc thời gian.
- Luôn ghi chú "mức phạt/regulation có thể thay đổi, kiểm tra văn bản mới nhất".

## SEO

- Tiêu đề giữ nguyên `title` trong ma trận (chỉ cho phép thêm dấu câu nhẹ, không đổi ý).
- `primary_keyword` và `secondary_keywords` dùng đúng như manifest; không nhồi từ khóa.
- Meta description 140–160 ký tự, chứa primary keyword tự nhiên.
- Liên kết nội bộ: child hub → parent hub → 2–4 bài liên quan; liên kết thương mại (`/bang-gia/`, `/lien-he/`) chỉ khi có ngữ cảnh. Không link wheel, không anchor text khớp chính xác hàng loạt.
- Canonical: `canonical_url` trong ma trận. Không tạo URL trùng.

## Chất lượng (ngưỡng xuất bản 90/100)

- Mở bài nêu đúng vấn đề người dùng; thân bài giải quyết từng bước; có ví dụ Hà Nội thực tế.
- Không lặp câu, không đệm rỗng, không tóm tắt vô nghĩa ở cuối.
- Kiểm tra reads-naturally: đọc thành tiếng không vướng.

## Cannibalization

Trước khi viết: đối chiếu tiêu đề chuẩn hóa + primary keyword + intent với các bài đã xuất bản (dùng `cannibalization_key` trong ma trận). Trùng mạnh → REVIEW, không xuất bản bài mới chỉ để lấp đầy.
