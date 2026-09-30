# SEO NỘI DUNG — quy tắc biên tập

Mục tiêu: mỗi bài phục vụ đúng một intent tìm kiếm, không tự cạnh tranh với hub của chính mình.

Nguồn chuẩn: manifest hàng (khi có matrix), taxonomy (`data/content-taxonomy.json`), `docs/SEO-OWNERSHIP.md`, `docs/ARTICLE-RULES.md`.

## Quy tắc

- Intent: mỗi bài đúng MỘT intent (informational/commercial) theo child hub; không viết bài trùm chặn hub.
- Title: giữ ý manifest; H2/H3 theo cấu trúc trả lời intent; một H1 duy nhất do layout render.
- Description: 140–160 ký tự, có primary keyword tự nhiên.
- Internal links: theo canonical docs/INTERNAL-LINKING.md (bài → child hub → parent hub → bài liên quan; chọn trong lúc viết bài); link thương mại chỉ khi có ngữ cảnh; mọi link nội bộ qua `relative_url`, không hardcode `/blog` hai lần.
- Cannibalization: đối chiếu tiêu đề chuẩn hóa + primary keyword + intent với bài đã xuất bản trong cùng child trước khi xuất bản; trùng mạnh → REVIEW. 10 cặp legacy REVIEW hiện đang chờ đọc nội dung (BLOCKED cho tự động hóa, danh sách trong `docs/SEO-OWNERSHIP.md`).
- Tác giả và nguồn: author "Nguyễn Tú"; claim pháp lý phải có nguồn chính thức (lớp nghiên cứu theo `docs/SOURCE-RESEARCH.md`, quy tắc bài viết: `docs/ARTICLE-RULES.md`); không bịa trích dẫn khách hàng.

## Kiểm tra trước xuất bản

Chấm theo `docs/QUALITY-RUBRIC.md` (SEO ≥ 70). Bằng chứng: outline, danh sách link render, kết quả đối chiếu cannibalization. Đánh giá "chất lượng thực sự" do AI/người đọc, không do script đếm từ khóa.

Xử lý lỗi: SEO < 75 → tối ưu an toàn, chấm lại; cannibalization → REVIEW, không xuất bản bài thứ ba cho intent đã có.
