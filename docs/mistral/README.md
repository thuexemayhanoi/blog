# Hướng dẫn cho agent Mistral (BLOG FACTORY)

Kho: `thuexemayhanoi/blog` · Trang: https://thuexemayhanoi.github.io/blog/ · Base URL: `/blog` · Ngôn ngữ công khai: chỉ tiếng Việt.

## Thứ tự đọc bắt buộc mỗi lần chạy

1. `README.md`
2. `docs/mistral/README.md` (file này)
3. `docs/CONTENT-FACTORY.md`
4. `docs/TAXONOMY.md`
5. `data/content-taxonomy.json`
6. `data/content-matrix.csv`
7. `data/business-facts.json`
8. `reports/factory/progress.json`
9. `data/state/checkpoint.json`
10. `data/state/writer-lock.json` và `data/state/transaction.json`

## Nguyên tắc bất di bất dịch

- Nền tảng đã bootstrap: ma trận canonical đúng 10.000 hàng (`BLG-00001` → `BLG-10000`). KHÔNG tạo hàng thứ 10.001, KHÔNG tạo ma trận mới, KHÔNG đổi ID.
- Luôn resume từ trạng thái repository: checkpoint → transaction → lock. Không restart factory.
- Mỗi chunk tối đa 10 bài. Ưu tiên self-healing: REPAIR → REVIEW → POST_AUDIT → LEGAL/FRESHNESS trước khi nhận hàng PLANNED mới.
- Xuất bản yêu cầu: QUALITY ≥ 90 VÀ SEO ≥ 90 VÀ BUSINESS FACT PASS VÀ (LEGAL PASS HOẶC NOT REQUIRED) VÀ KHÔNG critical failure.
- Không bịa: khuyến mại, phí giao xe cố định, số lượng khách, số năm kinh nghiệm, xếp hạng, cam kết, hỗ trợ 24/7.
- Bài legacy (trạng thái EXISTING): KHÔNG đổi URL, KHÔNG xóa, KHÔNG đổi tên tệp, KHÔNG viết lại trừ khi có lý do audit mới.
- Hoàn tất một task phải có: tệp nguồn thực sự thay đổi, commit SHA mới, GitHub Pages build + deploy thành công, kiểm tra runtime. Không tạo commit "verification" chỉ README.
- Kiểm tra mobile ~390px, giữ hệ thống icon SVG hiện có, không bỏ dấu tiếng Việt.

## Quy tắc ghi tệp bài mới

- Tệp nguồn: `_posts/` phẳng (KHÔNG tạo thư mục con trong `_posts`), tên `YYYY-MM-DD-slug.md`.
- Frontmatter bắt buộc: `layout: post`, `title`, `date`, `author: "Nguyễn Tú"`, `description`, `categories` (Du lịch / Kinh nghiệm / Chia sẻ), `lang: vi`, `tags`, `parent_id`, `child_id`, `permalink` lấy đúng `output_path` từ ma trận, `article_id: BLG-XXXXX`.
- Thư mục công khai `{parent}/{child}/slug/` được tạo bằng `permalink` trong frontmatter, không phụ thuộc cấu trúc thư mục vật lý.
- Nội dung: dùng đúng `title`, `primary_keyword`, `secondary_keywords`, `audience`, `location_scope`, `word_target` và `internal_links` từ manifest (`scripts/factory/manifest.py --id BLG-XXXXX`).
  Các đường dẫn link nội bộ là gốc-tương-đối (không có `/blog`): khi render phải qua `relative_url`.

## Trạng thái hợp lệ

`PLANNED → WRITING → QA → PASS → PUBLISHED` và `REVIEW`, `REPAIR`, `BLOCKED`, `FAIL`, `EXISTING`.

- `EXISTING`: bài legacy xuất bản trước khi factory bootstrap (không đụng vào).
- `PUBLISHED`: bài xuất bản qua factory mới.

## Báo cáo mỗi lần chạy

Xem `docs/CONTENT-FACTORY.md` mục "Báo cáo". Không bao giờ bịa kết quả PASS.
