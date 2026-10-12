# FAQ dùng chung (`_includes/faq.html`)

Một nguồn dữ liệu → khối hỏi–đáp hiển thị **và** (tuỳ chọn) JSON-LD `FAQPage`, luôn khớp 1:1. Mặc định **không làm gì**: bài/trang không có file dữ liệu thì HTML không đổi.

## Thêm FAQ cho một trang

1. Tạo `_data/faq/<khoá>.json` (UTF-8):

```json
{
  "schema": true,
  "heading": "Câu hỏi thường gặp",
  "items": [
    {"q": "Câu hỏi hoàn chỉnh kết thúc bằng dấu hỏi?", "a": "Một hoặc vài câu TRÍCH NGUYÊN VĂN từ bài/trang.", "src": "body"}
  ]
}
```

- Bài viết: `khoá` = slug (tên file `_posts/YYYY-MM-DD-<slug>.md` bỏ ngày), `src` = `body`. Không sửa file bài (bài factory đã PUBLISHED bị khoá hash QA — FAQ nằm ngoài file bài nên không đụng hash).
- Trang tĩnh/hub/topic: thêm `faq_key: <khoá>` vào front matter, `src` = `page`. Layout `page` đã gọi component; layout khác thêm `{% include faq.html key=page.faq_key %}`.
- `heading` tuỳ chọn; `schema: true` mới phát `FAQPage` JSON-LD (khối hiển thị luôn có).

## Quy tắc (CI chặn — `scripts/faq/validate_faq.py`)

| # | Quy tắc |
|---|---------|
| F1 | JSON hợp lệ; khoá cấp 1 ⊆ `schema`, `heading`, `items`; `schema` là boolean |
| F2 | 2–8 mục; `q` 12–140 ký tự kết thúc `?`; `a` 30–700 ký tự, mỗi câu ≥ 3 từ và có ít nhất một câu ≥ 8 từ; văn bản thuần (không HTML/Liquid/markdown) |
| F3 | Có đích: đúng 1 bài `_posts/*-<khoá>.md` hoặc đúng 1 trang `faq_key: <khoá>`; không có file FAQ mồ côi; `src` khớp loại đích |
| F4 | **Nguyên văn**: mọi câu của `a` xuất hiện nguyên văn (bỏ dấu câu/hoa thường/markdown) trong nguồn của đích → FAQ không thêm sự thật mới |
| F5 | Không chạm chủ đề BLOCKED (cọc, phí trả trễ, bảo hiểm, giữ giấy tờ, mũ bảo hiểm, hoàn tiền — `reports/factory/policy-conflicts.md`): câu trả lời nhắc chủ đề này chỉ được là lời dặn "xác nhận trực tiếp / liên hệ", không kèm số; không dùng cụm cấm trong `data/business-facts.json`; mọi số tiền phải thuộc bảng giá đã duyệt |
| F6 | Không trùng/gần trùng câu hỏi (kể cả giữa các trang), không trùng câu trả lời dài giữa hai trang |

Sau build, `scripts/faq/faq_parity_check.py --site ./_site` kiểm: mọi JSON-LD parse được; `FAQPage` chỉ khi có khối hiển thị; `data-faq-schema="1"` ⇔ có `FAQPage`; câu hỏi/đáp trong JSON-LD == khối hiển thị (cùng thứ tự).

## Chạy cục bộ

```
python3 scripts/faq/validate_faq.py
python3 scripts/factory/tests/test_faq.py
# sau jekyll build:
python3 scripts/faq/faq_parity_check.py --site ./_site
```

## Vì sao ràng buộc chặt

Google đã ngừng hiển thị FAQ rich result (2026-05-07) và hướng dẫn AI features (2026-07-10) nói rõ: không cần structured data hay viết lại cho AI. FAQ ở đây phục vụ người đọc (câu hỏi quen thuộc, trả lời trực tiếp), dùng đúng lời đã duyệt của bài — không thêm số, chính sách hay cam kết mới; `FAQPage` chỉ là markup hợp lệ, không phải lời hứa về thứ hạng.
