# QUALITY RUBRIC — chấm điểm nội bộ QUALITY và SEO

Đây là điểm nội bộ để gate xuất bản, KHÔNG phải điểm Google và không tương đương thứ hạng. Chấm bằng AI/người đọc có bằng chứng; kiểm tra tự động (độ dài, từ khóa, link) chỉ là điều kiện cần, không chứng minh chất lượng hay tính đúng pháp lý.

## QUALITY (≥ 75/100 mới được xuất bản)

| Tiêu chí | Trọng số | Bằng chứng cần |
|---|---|---|
| Giải quyết đúng vấn đề người dùng (intent, mở bài nêu đúng vấn đề) | 25 | Trích đoạn mở bài + đối chiếu intent trong manifest/taxonomy |
| Thân bài từng bước, ví dụ Hà Nội thực tế | 25 | Ít nhất 1 ví dụ cụ thể có thật (địa điểm, tình huống) |
| Reads-naturally: đọc thành tiếng không vướng, không đệm rỗng, không lặp | 20 | Người/AI đọc và xác nhận; không chỉ đếm từ |
| Chính xác thực tế, không bịa số | 20 | Mọi con số truy về `data/business-facts.json` hoặc nguồn chính thức |
| Cấu trúc H2/H3, danh sách khi hữu ích, một H1 | 10 | Kiểm tra render |

Tổng < 75 → REPAIR, giữ `_drafts/`. 75–100 → PUBLISH ngay, KHÔNG ép 90/100. 90–100 → chỉ ghi nhãn EXCELLENT (không bắt tối ưu thêm). Critical failure (bịa dữ liệu kinh doanh, nhận định pháp lý sai nguồn, đạo văn/copy) → FAIL ngay bất kể điểm.

## SEO (≥ 70/100)

| Tiêu chí | Trọng số | Bằng chứng |
|---|---|---|
| Title đúng intent, không đổi ý so với manifest, ≤ 60 ký tự hiển thị hợp lý | 20 | Title render |
| Meta description 140–160 ký tự, chứa primary keyword tự nhiên | 15 | Meta render |
| Heading H2/H3 phủ intent + từ khóa phụ tự nhiên, không nhồi | 20 | Outline |
| Liên kết nội bộ theo canonical docs/INTERNAL-LINKING.md (child hub → parent hub → bài liên quan; thương mại chỉ khi có ngữ cảnh) | 15 | Danh sách link render + đích 200 |
| Không cannibalization: tiêu đề chuẩn hóa + intent không trùng bài đã xuất bản cùng child | 20 | Kết quả đối chiếu + `cannibalization_key` (khi có matrix) |
| URL/canonical đúng taxonomy, một H1, hình có alt khi có | 10 | Render + sitemap |

## BUSINESS FACT / LEGAL (riêng, PASS-FAIL, không cho điểm)

- BUSINESS FACT PASS: 100% con số/khẳng định kinh doanh truy được về `data/business-facts.json`. Có mục BLOCKED trong `reports/factory/policy-conflicts.md` dính tới bài → bắt buộc tránh nội dung đó.
- LEGAL PASS: mọi claim pháp lý theo cấu trúc 6 bước với nguồn chính thức, có chú thích "mức phạt/regulation có thể thay đổi". LEGAL NOT REQUIRED khi `source_required = false` và `legal_risk != high`.

## Xử lý lỗi

- Bài đã đạt 75/70 KHÔNG sửa chỉ để tăng điểm.
- SEO < 70: tối ưu an toàn (title/meta/link), không đổi ý tiêu đề.
- Không hạ trọng số, không bỏ tiêu chí để PASS. Không dùng kết quả "skipped" của validator cũ làm bằng chứng.

## HARD GATES (REPAIR ngay, không phụ thuộc điểm)

Bất kể điểm QUALITY/SEO, một bài QA dính các lỗi dưới đây là REPAIR ngay:

1. Bài rỗng/cụt nghiêm trọng, placeholder/rác (`no_placeholder`).
2. Trùng article ID, trùng title chuẩn hóa với hàng active khác (`duplicate_title`).
3. Trùng slug/canonical/expected_url/output_path với hàng active khác (`duplicate_slug`).
4. Intent gần trùng nguyên câu với hàng active khác (`intent_unique`, ngưỡng SequenceMatcher 0.97 — corpus long-tail hợp lệ có cặp 0.90–0.963 nên floor thấp hơn sẽ cầm nhầm bài thật).
5. Frontmatter/HTML hỏng khiến trang không render (cấu trúc draft, permalink/canonical).
6. Sai giá/số liệu/SDT/policy kinh doanh đã xác minh, claim cấm (`business_fact`).
7. Internal link trỏ route không tồn tại làm hỏng build/deploy (`links_routes_valid`).

Mọi lỗi SEO nhẹ khác KHÔNG chặn publish trong production loop; full-site audit chỉ chạy theo chế độ DEEP/FULL thủ công, không quét lại bài đã PUBLISHED trong chu kỳ sản xuất.
