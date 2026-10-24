# Chính sách slug/URL và di trú slug đ → d (Issue #77)

## Một quy tắc duy nhất

`scripts/factory/slugkit.py` là nơi DUY NHẤT sinh slug/URL của bài. Mọi thành phần phải dùng nó, không tự viết lại:
`generate-matrix.py`, `refill-queue.py`, `expand-topic-universe.py` (khoá trùng), `scripts/seo/slugs.py`, `migrate-slug-urls.py`, `validate.py`.

```
python3 scripts/factory/slugkit.py "Đặt xe trước bao lâu"     # -> dat-xe-truoc-bao-lau
```

Quy tắc: NFC → đổi `đ`/`Đ` thành `d`/`D` (chữ duy nhất của tiếng Việt không phân rã NFD) → NFD bỏ dấu → chữ thường → chỉ giữ `a-z0-9` và khoảng
trắng → khoảng trắng thành gạch ngang → cắt 80 ký tự → bỏ gạch ngang đầu/cuối. `norm()` (khoá trùng/cannibalization) giữ NGUYÊN hành vi cũ.
URL bài factory: chỉ ASCII thường, số, gạch ngang và `/`; hình dạng `/<danh mục>/<yyyy>/<mm>/<dd>/<slug>/` (hai dạng legacy `/<cat>/<yyyy-mm-dd>/<slug>/` và
`/<cat>/<yyyy-mm-dd>-<slug>/` chỉ còn ở 36 bài cũ, được giữ nguyên hình dạng khi di trú).

Khoá hồi quy: `scripts/factory/tests/test_slug_policy.py` (so với công thức lịch sử đóng băng trên mọi tiêu đề của matrix, NFC/NFD, quét mã nguồn không có bản
sao thứ hai) và `validate.py` mục `slug_policy` (mọi scope): mọi hàng factory phải có `slug == slugify(title)`, URL ASCII đúng hình dạng, `output_path` khớp slug,
không trùng slug.

## Ngoại lệ lịch sử có kiểm soát

1.410 bài đã xuất bản trước khi sửa lỗi mang slug thiếu chữ d. Danh sách ĐÓNG BĂNG: `reports/factory/seo-master/slug-d-baseline.csv` (sha256 ghim trong
`slug_redirects.BASELINE_SHA256`). Một bài trong danh sách được giữ slug lỗi chỉ khi CHƯA di trú và slug đúng bằng slug lỗi cũ của tiêu đề. Danh sách chỉ co lại
(khi bài được di trú), không bao giờ thêm.

## Di trú URL: HTTP 200 + meta refresh 0 giây + canonical (KHÔNG phải 301)

GitHub Pages không có HTTP 301 theo đường dẫn (runner: `server: GitHub.com`, không lớp edge). Chủ repo đã chọn không dùng Cloudflare/dịch vụ ngoài. Mỗi bài di trú có:

| | URL cũ | URL mới |
|---|---|---|
| Trả về | HTTP **200**, trang `redirects/slug-d/<ID>.html` (layout `_layouts/redirect-stub.html`) | HTTP 200, bài thật |
| Chuyển hướng | `<meta http-equiv="refresh" content="0; url=MỚI">` | — |
| canonical | trỏ URL mới | tự trỏ |
| sitemap | KHÔNG có (`sitemap: false`) | có |

Báo cáo và công cụ luôn gọi đúng tên "HTTP 200 + meta refresh"; không ghi "301".

### Công cụ chính thức: `scripts/factory/migrate-slug-urls.py`

```
python3 scripts/factory/migrate-slug-urls.py plan --jobs 4 --out /tmp/migrate-manifest.json
python3 scripts/factory/migrate-slug-urls.py apply --manifest /tmp/migrate-manifest.json --approval-ref "<người duyệt/ngày>" --limit 50 --offset 0 --batch-id migrate-YYYYMMDD-NN
python3 scripts/factory/migrate-slug-urls.py refresh-data          # dữ liệu phái sinh theo URL mới
python3 scripts/factory/migrate-slug-urls.py verify --backup reports/qa-audit/migrate/<batch>.json
python3 scripts/factory/migrate-slug-urls.py rollback --backup reports/qa-audit/migrate/<batch>.json
```

Điều kiện mỗi bài (tool tự kiểm, không có cờ ép): thuộc baseline; PUBLISHED; **evidence nguyên vẹn** (nếu lệch hash vì migrate domain → phải qua
`reattest-legacy-qa.py` do chủ duyệt trước); không lease/draft; slug/URL/đường dẫn mới không trùng; bài mới = bài cũ khác đúng dòng `permalink:`; chấm lại độc lập
≥ 75/70, business_fact PASS, legal PASS|NOT_REQUIRED, không critical, không tiêu chí nào tụt. Lô ≤ 50, mỗi lô một commit, `--approval-ref` bắt buộc, sao lưu
byte-exact `reports/qa-audit/migrate/<batch>.json` (gate `verify` lại mọi sao lưu được thêm/sửa).

Mỗi bài ghi: đổi tên `_posts/` + dòng permalink; `data/qa/<ID>.json` (scorer mới + khối `revision` kind `permalink-migration`); 4 cột URL của hàng matrix;
trang chuyển hướng; dòng registry `reports/factory/seo-master/slug-redirect-registry.csv`.

### Kiểm tra

- Nguồn (mọi scope của `validate.py`): registry ↔ matrix ↔ bài ↔ evidence ↔ trang chuyển hướng khớp byte (`slug_redirects.source_errors`).
- Output build (gate FULL, trước deploy): `scripts/factory/check-slug-redirects.py --site ./_site` — mỗi trang cũ có đúng một meta refresh 0s tới URL mới, canonical mới,
  không trong sitemap; trang mới hợp lệ và trong sitemap; không trang chuyển hướng lạ; liên kết nội bộ vào trang chuyển hướng không vượt ngưỡng ratchet
  `reports/factory/seo-master/slug-stub-link-ratchet.json` (chỉ giảm — bài mới không được link vào URL cũ).
- Production (sau deploy): `factory-liveness.yml` với `live_audit=true` và `stub_check=all` hoặc `start:limit` (xem `docs/LIVE-SITEMAP-404-AUDIT.md`).

## Rollback

Revert commit của lô (GitHub Pages deploy lại trạng thái cũ), hoặc `migrate-slug-urls.py rollback --backup ...` rồi commit. URL cũ trả 200 với nội dung bài đầy đủ ngay khi rollback.
