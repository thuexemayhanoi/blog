# Slug thiếu chữ đ — audit và bản đồ OLD → NEW

Sinh bởi `scripts/seo/slug-d-audit.py` (đọc-only). Bản đồ đầy đủ: `slug-d-migration-map.csv`. **Trạng thái: BLOCKED_INFRA_301 + BLOCKED_NO_EVIDENCE_REVISION_PATH.
Chưa đổi URL nào; không có URL nào được sửa thật.**

## 1. Số liệu (FACT, đọc từ repo)

| Hạng mục | Giá trị |
|---|---:|
| URL đã xuất bản bị mất chữ đ (khớp tuyệt đối với slug cũ tính từ tiêu đề matrix) | 1410 |
| Bài PUBLISHED trong matrix | 5593 |
| Hàng PLANNED (chưa xuất bản) / trong đó tiêu đề có chữ đ | 65 / 56 |
| Hàng PLANNED có slug sai | 0 |
| Va chạm của URL mới | không có |
| Bằng chứng QA của các URL này: khớp / lệch sẵn (xem ghi chú) | {"DRIFT_CONTENT_SHA": 686, "yes": 724} |
| Bằng chứng QA của toàn bộ bài PUBLISHED | {"DRIFT_CONTENT_SHA": 1068, "yes": 4525} |
| Bài thuộc lease writer đang giữ | 0 |
| URL cũ còn được bài khác trỏ tới (số URL / tổng liên kết / số bài khác phải sửa nếu cập nhật link) | 1031 / 3818 / 2223 |
| URL cũ còn nằm trong dữ liệu/mẫu giao diện (_data, _includes, _layouts, trang gốc) | 85 |
| Phân bố theo parent | {"P-CUNG-DUONG": 187, "P-DU-LICH": 222, "P-HOI-DAP": 91, "P-KY-NANG": 218, "P-PHAP-LY": 71, "P-THUE-XE": 299, "P-XE-MAY": 322} |

Ghi chú về `DRIFT_CONTENT_SHA`: đây là tình trạng **có sẵn, không do audit này**. `content_sha256` trong evidence lệch byte bài hiện tại ở ~1.068 bài PUBLISHED chủ yếu vì đợt migrate domain
(phân tích và kế hoạch: `docs/LEGACY-QA-RE-ATTESTATION-PLAN.md`, `reports/qa-audit/legacy-evidence-2026-10-12.json`); chờ chủ duyệt `reattest-legacy-qa.py apply --approval-ref`. Gate hàng ngày chỉ kiểm scope chunk nên không đỏ.
Việc di trú URL phải đi sau (hoặc cùng) đường bảo trì đó.

Hàng PLANNED đã đúng: slugify của generator và refill đã sửa chữ đ (đ → d trước khi bỏ dấu); không hàng PLANNED nào sai slug, nên bài **mới** không tái diễn lỗi.

## 2. Vì sao chưa thể di trú 1.410 URL đã xuất bản

Hai điều kiện bắt buộc đều chưa đạt, mỗi điều kiện đủ để chặn một mình.

**A. BLOCKED_INFRA_301 — không có chuyển hướng HTTP 301/308 thật.**
- Site chạy trên GitHub Pages (tệp `CNAME` = `blog.thuexemaynguyentu.com`; build bằng `actions/jekyll-build-pages`; plugin trong `_config.yml`: `jekyll-sitemap`, `jekyll-feed`).
  GitHub Pages không hỗ trợ cấu hình chuyển hướng phía máy chủ (không có `_redirects`, không đặt được header/status). Plugin `jekyll-redirect-from` chỉ sinh trang HTML trả **HTTP 200**
  chứa meta refresh + JavaScript, không phải 301; yêu cầu của chủ website là không coi đó là chuyển hướng.
- Không có hạ tầng edge nào được xác minh: tài khoản Vercel đang kết nối có 0 domain và 0 project (FACT, truy vấn 2026-10-23); repo không có cấu hình Cloudflare/Netlify/Vercel
  (`grep` không thấy `_redirects`, `vercel.json`, `netlify.toml`). Không thể dò header production từ môi trường chạy (proxy chặn tên miền, HTTP 403) nên không xác minh được có CDN đứng trước hay không (UNKNOWN).

**B. BLOCKED_NO_EVIDENCE_REVISION_PATH — đổi URL làm vỡ ba ràng buộc toàn vẹn của factory, và chưa có công cụ chính thức cập nhật chúng.**
Mỗi bài có `permalink` nằm trong front matter, nên đổi slug là đổi byte bài. Phải đổi đồng thời: front matter permalink (đổi byte bài => content_sha256); matrix expected_url + output_path + canonical_url (=> matrix_row_sha256); data/qa/<ID>.json source_path + content_sha256 + matrix_row_sha256; tên tệp _posts.
`scripts/factory/validate.py` (scope batch/full) báo đỏ ngay khi `content_sha256`, `matrix_row_sha256` hoặc `source_path` lệch. Công cụ ghi evidence duy nhất, `reattest-legacy-qa.py`, chỉ cho
trường hợp chỉ đổi domain đối chiếu baseline `1b55bd81`; không có đường chính thức cho "đổi nội dung/URL rồi chấm lại". Sửa tay `data/qa/` bị cấm (AGENTS.md quy tắc 9).
Ngoài ra, nếu cập nhật liên kết nội bộ cho đúng URL mới thì thêm 2223 bài khác bị đổi byte và rơi vào cùng vấn đề.

## 3. Việc đã làm an toàn và việc chặn tái diễn

- Bài mới: generator (`generate-matrix.py`) và refill (`refill-queue.py`) dùng slugify đã sửa (đ → d trước khi bỏ dấu), `TestSeoSlugForms` và `TestSlugify` trong
  `scripts/factory/tests/test_slugify_vi.py` khóa hành vi (so với toàn bộ tiêu đề matrix, và không hàng PLANNED nào mang slug thiếu chữ đ).
  Ghi nhận không cần sửa: `expand-topic-universe.py` chỉ dùng `norm()` để kiểm trùng (không sinh slug); dòng kiểm trùng slug trong đó là mã chết (regex thoát sai nên không bao giờ thay khoảng trắng bằng gạch ngang) nhưng vô hại vì công cụ chạy một lần
  (chạy lại trên dữ liệu đã commit: 121/121 ứng viên bị từ chối vì trùng chính hàng đã nhận, seed và báo cáo không đổi) và tính duy nhất slug/output_path/canonical được ép ở `generate-matrix.py` cùng test của nó.
- Bản đồ OLD → NEW đã sẵn (không va chạm theo bảng trên), kèm số liên kết nội bộ và ràng buộc phải đổi cho từng URL.

Năm ví dụ trong bản đồ (URL cũ chưa có liên kết nội bộ trỏ tới):

| OLD | NEW | ID |
|---|---|---|
| `/an-toan-phap-ly/2026/09/28/bao-hiem-tu-nguyen-cho-xe-may-co-ang-khong/` | `/an-toan-phap-ly/2026/09/28/bao-hiem-tu-nguyen-cho-xe-may-co-dang-khong/` | BLG-00626 |
| `/an-toan-phap-ly/2026/09/28/oi-bang-lai-nuoc-ngoai-sang-bang-viet-nam-huong-dan-co-ban/` | `/an-toan-phap-ly/2026/09/28/doi-bang-lai-nuoc-ngoai-sang-bang-viet-nam-huong-dan-co-ban/` | BLG-00622 |
| `/an-toan-phap-ly/2026/09/28/quy-inh-moi-ve-xe-may-can-biet/` | `/an-toan-phap-ly/2026/09/28/quy-dinh-moi-ve-xe-may-can-biet/` | BLG-00652 |
| `/an-toan-phap-ly/2026/09/28/tem-kiem-inh-xe-may-con-hieu-luc-ra-sao/` | `/an-toan-phap-ly/2026/09/28/tem-kiem-dinh-xe-may-con-hieu-luc-ra-sao/` | BLG-00649 |
| `/an-toan-phap-ly/2026/10/05/mat-cccd-khi-ang-giu-ho-ky-qua-thue-xe-lam-gi/` | `/an-toan-phap-ly/2026/10/05/mat-cccd-khi-dang-giu-ho-ky-qua-thue-xe-lam-gi/` | BLG-01383 |

## 4. Quy trình di trú khi đủ điều kiện (chưa thực hiện)

Chỉ bắt đầu khi **cả hai** điều kiện sau đều có bằng chứng: (1) có chuyển hướng HTTP 301/308 thật cho từng đường dẫn cũ, kiểm bằng `curl -I` trên production
(ví dụ chuyển site sang nền tảng hỗ trợ redirect, hoặc đặt lớp edge có quy tắc chuyển hướng theo ánh xạ OLD → NEW); (2) chủ website duyệt một công cụ bảo trì chính thức cho "đổi URL/nội dung bài đã xuất bản":
sao lưu evidence cũ, chấm lại độc lập bằng scorer chuẩn (ngưỡng 75/70 không đổi), ghi provenance, rollback theo lô.

Mỗi lô tối đa 50 bài, một commit: (a) đổi tên tệp + `permalink`, (b) cập nhật hàng matrix, (c) ghi evidence mới bằng công cụ ở (2), (d) cập nhật liên kết nội bộ chỉ trong lô đó và dữ liệu `_data`,
(e) thêm quy tắc 301 OLD → NEW, (f) build + `check-built-links.py` + validate FULL, (g) sau deploy: kiểm 301 cho mọi OLD trong lô (một bước, không chuỗi), kiểm NEW trả 200, canonical/sitemap/breadcrumb mới, OLD không còn trong sitemap,
(h) giữ nguyên lô trước nếu lô sau lỗi; rollback = revert đúng commit lô và gỡ quy tắc 301 của lô.
Không bao giờ chuyển hướng hàng loạt về trang chủ, không tạo chuỗi hay vòng chuyển hướng.
