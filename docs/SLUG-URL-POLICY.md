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

### Quy trình MỘT lô (≤ 50 bài) — thứ tự bắt buộc

1. Cây sạch trên `main` mới nhất → `plan` (manifest gắn một commit sạch) → `apply --dry-run` → `apply`.
2. `refresh-data` (dữ liệu khóa theo URL: `_data/legal-notices.json`, `_data/seo-leads.yml`; sinh lại `seo-topic-links.json`, `price-notices.json` — cần PyYAML).
3. `verify --backup reports/qa-audit/migrate/<batch>.json` và `validate.py --scope chunk`.
4. Ghi ngưỡng ratchet: `check-slug-redirects.py --from-source --write-ratchet --allow-raise` (đếm liên kết vào URL cũ ngay từ nguồn, không cần build; đã đối chiếu
   bằng số đo trên output build thật: 4/10 bài, 124/50 bài) — hoặc `--site <site> --write-ratchet --allow-raise` sau một bản build cục bộ. Gate FULL luôn kiểm lại trên output build thật.
   (`apply`/`rollback` KHÔNG đọc/ghi ratchet; thiếu ngưỡng khi registry không rỗng là LỖI của gate.)
5. Một commit/lô → PR → gate FULL xanh → merge → Pages deploy → `factory-liveness.yml` (`live_audit=true`, `stub_check=start:limit` cho đúng các mục của lô) → lô kế tiếp.

### Kiểm tra

- Nguồn (mọi scope của `validate.py`): registry ↔ matrix ↔ bài ↔ evidence ↔ trang chuyển hướng khớp byte (`slug_redirects.source_errors`).
- Output build (gate FULL, trước deploy): `scripts/factory/check-slug-redirects.py --site ./_site` — mỗi trang cũ có đúng một meta refresh 0s tới URL mới, canonical mới,
  không trong sitemap; trang mới hợp lệ và trong sitemap; không trang chuyển hướng lạ; liên kết nội bộ vào trang chuyển hướng không vượt ngưỡng ratchet
  `reports/factory/seo-master/slug-stub-link-ratchet.json` (chỉ giảm — bài mới không được link vào URL cũ).
- Production (sau deploy): `factory-liveness.yml` với `live_audit=true` và `stub_check=all` hoặc `start:limit` (xem `docs/LIVE-SITEMAP-404-AUDIT.md`).

### Pha 2: trỏ liên kết nội bộ thẳng tới URL mới

Sau khi một bài được di trú, các bài khác còn trỏ tới URL cũ vẫn chạy (qua trang chuyển hướng) nhưng nên trỏ thẳng. `migrate-slug-urls.py links-plan/links-apply/links-verify/links-rollback`
đổi **chỉ đích** của `](ĐÍCH)` / `href="ĐÍCH"` theo ánh xạ: mặc định registry OLD → NEW, **cả dạng thiếu `/` cuối của URL cũ** (đi thẳng tới URL mới); `--mapping FILE` thêm đích khác (ví dụ 16 đích thiếu
dấu `/` mà GitHub Pages phải 301). Ánh xạ luôn được **gập chuỗi** (`A→B` và `B→C` thành `A→C`; vòng/tự trỏ bị từ chối `MAPPING_LOOP`) nên liên kết không bao giờ đáp xuống một URL sắp thành trang chuyển hướng.
Chữ liên kết, tiêu đề `"..."`, `#đoạn` và mọi byte khác giữ nguyên (`mask_links` so sánh phần ngoài các cụm `](...)`; không thay cho kiểm byte của khung `difflib` trong test). Bài phải có evidence nguyên vẹn;
chấm lại độc lập 75/70, không tiêu chí nào tụt; khối `revision` kind `link-retarget` (khối cũ — kể cả `permalink-migration` — nằm trong `revision.history`); sao lưu `reports/qa-audit/links/<batch>.json`
(gate verify lại); lô ≤ 50; không đụng matrix/registry; `links-apply` KHÔNG coi một bài là "đã xong" nếu evidence không khớp byte bài mới (`EVIDENCE_NOT_BOUND_TO_NEW_POST`).

**Thứ tự (kết quả phân tích trên kho thật, 2026-10-25):** chạy pha 2 **MỘT lượt sau lô di trú cuối** (đã merge và xác minh live). Mỗi bài chỉ ghi lại evidence một lần (1.395 bài/28–29 PR ≤ 50); chạy sau mỗi lô tốn thêm
~400 lượt ghi (346 bài ghi lại ≥ 2 lần) và 43 PR. Các PR pha 2 không đụng tệp dùng chung (chỉ `_posts/<id>.md`, `data/qa/<id>.json`, một sao lưu riêng) nên có thể mở/gate SONG SONG và merge tuần tự;
**không sửa ratchet trong từng PR pha 2** (một số nguyên dùng chung ⇒ xung đột); sau PR cuối đo một lần `check-slug-redirects.py --from-source --write-ratchet` (giảm). Liên kết nằm trong bài không sửa được
(evidence lệch hash, có draft) giữ nguyên trỏ vào trang chuyển hướng (HTTP 200 + canonical về URL mới) — chấp nhận được về SEO; xử lý tiếp sau khi chủ duyệt reattest.

## Pha 3: gỡ URL cũ (quyết định chủ 2026-10-27) — URL cũ trả 404

Sau khi di trú xong, chủ repo quyết định **không giữ chuyển hướng lịch sử**: trang chuyển hướng của URL cũ được gỡ, URL cũ trả **404 (đúng kỳ vọng)**, bài ở URL mới
giữ nguyên. Không xóa bài thật, không đụng evidence QA/matrix/sitemap. Công cụ duy nhất: `scripts/factory/retire-slug-stubs.py`:
```
python3 scripts/factory/retire-slug-stubs.py plan [--ids BLG-…] --out /tmp/retire-plan.json
python3 scripts/factory/retire-slug-stubs.py apply --approval-ref "<chủ duyệt>" --live-ref "<run factory-liveness stub_check all_ok>" (--ids … | --all-eligible) --batch-id retire-YYYYMMDD-NN
python3 scripts/factory/retire-slug-stubs.py verify --backup reports/qa-audit/retire/<batch>.json
python3 scripts/factory/retire-slug-stubs.py rollback --backup reports/qa-audit/retire/<batch>.json [--dry-run]
python3 scripts/factory/check-slug-redirects.py --from-source --write-ratchet      # hạ ratchet theo số trang chuyển hướng còn lại
```
Điều kiện (tool tự kiểm từ byte hiện tại): nguồn di trú sạch; dòng registry `MIGRATED`, trang chuyển hướng khớp byte `stub_source()`; bài URL mới có permalink đúng;
**không còn liên kết nào trong nguồn site tới URL cũ** (kể cả thiếu `/` cuối — nếu còn: `BLOCKED_STILL_LINKED`, trỏ thẳng bằng `links-apply` trước); `--approval-ref` + `--live-ref`
(audit live xác nhận URL mới HTTP 200, canonical tự trỏ, trong sitemap — môi trường agent không gọi được production). Kết quả: xóa `redirects/slug-d/<ID>.html`, dòng registry giữ nguyên
ánh xạ cũ → mới với status **`RETIRED`**, sao lưu `reports/qa-audit/retire/<batch>.json` (gate verify lại). Lô ≤ 700 (không đổi nội dung bài nên không chấm lại).

Chặn tái phát: `validate.py` (`slug_redirects.source_errors`) và gate FULL (`check-slug-redirects.py`) báo lỗi với MỌI liên kết tới URL `RETIRED` (ngưỡng cứng 0, không ratchet) và mọi trang còn
phục vụ ở URL đã gỡ; `check-site-urls.py` chặn permalink trùng/không ASCII, `<loc>` trùng/sai host/không ASCII, URL sitemap không tự canonical/meta refresh/noindex, hai trang cùng canonical.
Audit live `stub_check` kiểm dòng `RETIRED`: URL cũ phải 404/410 và không trong sitemap, URL mới 200 + canonical tự trỏ + trong sitemap.

## Hàng matrix lệch permalink thật (50 URL BLG-00820…00869)

Trên 5.664 bài PUBLISHED, đúng **50 hàng** ghi `expected_url`/`canonical_url` dạng `/<cm>/YYYY/MM/DD/<slug>/` trong khi permalink thật trong bài (URL Jekyll xuất bản, sitemap và live) là
`/<cm>/YYYY-MM-DD/<slug>/` (BLG-00820…00854) hoặc `/<cm>/YYYY-MM-DD-<slug>/` (BLG-00855…00869); 5.614 hàng còn lại khớp. **Không đổi permalink** (URL đang hoạt động, đã được index): sửa matrix cho khớp URL thật.

- **36 hàng thuộc baseline đ→d**: `migrate-slug-urls.py` sửa matrix cùng lúc đổi URL (`matrix_url_drift`, `matrix_url_drift_fixed` trong provenance) sau khi evidence được reattest.
- **14 hàng ngoài baseline** (BLG-00822, 00832, 00844, 00845, 00847, 00853, 00857, 00858, 00859, 00860, 00861, 00863, 00864, 00869; slug không mất chữ đ): công cụ `scripts/factory/sync-matrix-urls.py`:
  ```
  python3 scripts/factory/sync-matrix-urls.py plan --ids BLG-…,BLG-… --out /tmp/sync-manifest.json
  python3 scripts/factory/sync-matrix-urls.py apply --manifest /tmp/sync-manifest.json --approval-ref "<người duyệt/ngày>" --ids BLG-…,BLG-… --batch-id matrix-sync-YYYYMMDD-NN
  python3 scripts/factory/sync-matrix-urls.py verify --backup reports/qa-audit/matrix-sync/<batch>.json
  python3 scripts/factory/sync-matrix-urls.py rollback --backup reports/qa-audit/matrix-sync/<batch>.json [--ids …] [--dry-run]
  ```
  Điều kiện bắt buộc, tool tự kiểm: hàng PUBLISHED, evidence NGUYÊN VẸN, không lease/draft, đúng dạng lỗi đã biết (dạng khác ⇒ `MATRIX_URL_UNKNOWN_SHAPE`, không đoán), front matter có ĐÚNG một khoá `permalink` (`PERMALINK_LINE`),
  permalink thật là của đúng bài này (hàng matrix/bài/registry khác dùng ⇒ `URL_COLLISION`), chấm lại độc lập ≥ 75/70, scorer xác nhận `permalink_canonical` (`PERMALINK_NOT_CANONICAL`), không tiêu chí nào tụt.
- **Evidence lệch hash (cả 36 hàng baseline lẫn 12/14 hàng ngoài baseline)**: chạy `reattest-legacy-qa.py` thành **PR chỉ-evidence riêng, merge (gate xanh) TRƯỚC**, rồi mới `plan/apply` di trú hoặc đồng bộ matrix ở PR sau.
  Không gộp hai bước trong một PR/push: bước sau ghi lại evidence mà sao lưu reattest đã ghi nhận, nên bước gate `reattest-legacy-qa.py verify` của PR gộp sẽ đỏ (`evidence khac ban da ghi`).
  Chỉ ghi 2 cột matrix + evidence (khối `revision` kind `matrix-url-sync`, history giữ khối cũ) + sao lưu `reports/qa-audit/matrix-sync/<batch>.json` (Quality gate verify lại); bài/redirects/registry không đổi byte.

## Rollback

- Lô ĐÃ commit/merge: **revert commit của lô** (GitHub Pages deploy lại trạng thái cũ; mọi tệp phái sinh — `refresh-data`, ratchet — quay lại cùng lúc). URL cũ trả 200 với nội dung bài đầy đủ ngay khi rollback.
- Cây chưa commit: `migrate-slug-urls.py rollback --backup ...`. Công cụ KIỂM TRA toàn bộ điều kiện (tệp, hàng matrix, registry) rồi mới ghi; từ chối mà không ghi gì nếu một hàng matrix đã bị sửa tay
  sau apply (`MATRIX_CHANGED_SINCE_APPLY`); bị ngắt giữa chừng thì chạy lại để hoàn tất phần matrix/registry. Thoát mã 1 nếu còn ID bị bỏ qua vì bài đã đổi sau apply.
  Công cụ KHÔNG hoàn tác `refresh-data` và ratchet (không có ảnh trước trong sao lưu) — dùng `git checkout -- _data reports/factory/seo-master` cho phần đó.
- Thứ tự: nếu pha 2 (`links-apply`) ghi lại bài SAU khi di trú: `links-rollback` pha 2 TRƯỚC rồi mới `rollback` pha 1 — công cụ từ chối (`INBOUND_LINKS_TO_NEW_URL`, chưa ghi gì) khi còn bài khác liên kết tới URL mới sắp biến mất.
  Nếu pha 2 ghi lại bài TRƯỚC khi nó được di trú (bài là nguồn liên kết): rollback pha 1 trước, rồi `links-rollback` (đường dẫn bài đã đổi nên `links-rollback` chỉ chạy được sau khi bài về chỗ cũ).
