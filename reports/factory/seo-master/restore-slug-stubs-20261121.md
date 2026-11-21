# Khôi phục trang chuyển hướng URL cũ (slug đ→d) — 2026-11-21

**Phê duyệt:** chủ website, 2026-11-21 (phiên làm việc với Claude): "duyệt — fix toàn bộ lỗi này, cứ làm, push và hợp nhất".
Đảo lại quyết định 2026-10-27 (pha 3: gỡ trang chuyển hướng, URL cũ trả 404).

## Vì sao

Dữ liệu Google Search Console, property `https://blog.thuexemaynguyentu.com/`, 22/8–19/11/2026:

- Google vẫn hiển thị URL cũ đã gỡ (404) hằng ngày. Riêng nhóm bài thương mại (matrix `commercial_intent` = high/medium):
  254 bài còn hiển thị trên URL cũ 404, tổng 5.883 lượt hiển thị và 100 lượt nhấp; 245 bài trong số đó chưa có lượt hiển thị nào trên URL mới.
  Trong 14 ngày gần nhất (6/11–19/11), 1.679 lượt hiển thị của nhóm này vẫn rơi vào URL cũ 404.
- URL Inspection API (21/11/2026), mẫu:
  - `/xe-may/2026/10/11/che-o-lai-eco-normal-sport-tren-xe-may-ien-khi-nao-dung-che-o-nao/` (cũ): Not found (404), crawl gần nhất 2026-11-21.
  - `/xe-may/2026/10/11/che-do-lai-eco-normal-sport-tren-xe-may-dien-khi-nao-dung-che-do-nao/` (mới): Discovered – currently not indexed, chưa crawl.
  - `/thue-xe/2026/10/11/gio-cao-iem-ha-noi-khung-gio-va-huong-uong-nen-tranh-khi-moi-chay-xe-may/` (cũ): Not found (404), crawl gần nhất 2026-11-17.
  - `/thue-xe/2026/10/11/gio-cao-diem-ha-noi-khung-gio-va-huong-duong-nen-tranh-khi-moi-chay-xe-may/` (mới): Discovered – currently not indexed, chưa crawl.
  - `/xe-may/2026/10/11/xe-50cc-binh-xang-nho-doc-dong-ho-xang-do-khi-nao-va-het-xang-thi-lam-gi/` (mới): Discovered – currently not indexed, chưa crawl.
  - `/thue-xe/2026/09/30/co-shop-nao-cho-thue-xe-may-khong-can-dat-coc-o-ha-noi-khong/` (mới, BLG-00944 — URL cũ đã có lại trang chuyển hướng từ #210): Submitted and indexed.

Kết luận: trang 404 không chuyển tín hiệu xếp hạng sang URL mới; trang chuyển hướng (HTTP 200 + meta refresh 0s + canonical về URL mới) thì có.

## Đã làm

```
python3 scripts/factory/retire-slug-stubs.py rollback --backup reports/qa-audit/retire/retire-20261028-r01.json   # restored 468, already_restored 1 (BLG-00944)
python3 scripts/factory/retire-slug-stubs.py rollback --backup reports/qa-audit/retire/retire-20261028-r02.json   # restored 468
python3 scripts/factory/retire-slug-stubs.py rollback --backup reports/qa-audit/retire/retire-20261028-r03.json   # restored 468
```

- 1.404 trang `redirects/slug-d/<ID>.html` sinh lại byte-exact từ sao lưu pha 3; registry: 1.408 dòng `MIGRATED`, 0 `RETIRED`.
- Không đụng bài viết, evidence QA, matrix, sitemap; sao lưu pha 3 giữ nguyên.
- Ratchet liên kết vào trang chuyển hướng giữ nguyên = 4 (không bài nào link tới các URL vừa khôi phục).

## Kiểm tra cục bộ trước khi push

- `slug_redirects.source_errors()`: 0 lỗi. `check-slug-redirects.py --from-source`: registry=1408, liên kết tới trang chuyển hướng=4, đã gỡ=0.
- `validate.py --scope full`: 654 lỗi, giống hệt từng dòng với `origin/main` 150966be (lỗi evidence QA lệch hash có sẵn, không do thay đổi này).
- `run-tests.py --suites ci` (xem PR).
