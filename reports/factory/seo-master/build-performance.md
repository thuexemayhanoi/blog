# Hiệu năng build Jekyll — đo thật, nguyên nhân, sửa, và phần còn lại

Ngày đo: 2026-10-22. Nhãn: **FACT** = đo/đọc trực tiếp; **INFERRED** = suy luận có căn cứ.

## 1. Vấn đề (FACT, nguồn GitHub Actions)

Commit trang chủ đã duyệt `4f61156e` (HEAD trước đợt này):

| Hạng mục | Kết quả | Nguồn |
|---|---|---|
| Bước "Build with Jekyll" của Pages | 18 phút 05 giây (13:13:29 → 13:31:34Z) | run "pages build and deployment" #5493, job `build` |
| Job `deploy` chờ trước khi chạy | 36 phút 54 giây (13:31:53 → 14:08:47Z), chạy 28 giây | cùng run, job `deploy` |
| Từ push tới deploy xong | khoảng 57 phút (13:12:06 → 14:09:15Z) | cùng run |
| Quality gate, job `gate` | build mất 18 phút 54 giây, rồi job bị hủy lúc 13:33:41Z do `timeout-minutes: 20`; 7 bước kiểm tra sau bước link bị bỏ qua | run Quality gate #1275 |
| Pages deploy ngày 2026-10-21 | 9 run liên tiếp (#5482–#5490) bị hủy trước khi run #5491 thành công sau 20 phút 53 giây | `list_workflow_runs` |

Hệ quả: mọi thay đổi engine/template đều không thể qua đủ các bước của cổng chất lượng (build đã gần hết hạn mức 20 phút),
và mỗi push của publisher kích hoạt một build ~18–21 phút nên các lần deploy liên tục bị hủy bởi push mới hơn.

## 2. Nguyên nhân (FACT, profile `jekyll build --profile`, 1.500 bài mới nhất, Jekyll 3.10.0)

| Template | Thời gian | Ghi chú |
|---|---:|---|
| `_layouts/post.html` | 117,3 s | gồm khối "bài trước/sau" |
| `_includes/related-articles.html` | 42,8 s | quét theo cụm |
| `_layouts/listing.html` | 39,0 s | danh sách danh mục phân trang |
| `_includes/pagination-nav.html` | 17,9 s | 748 lần render |

- Khối "bài trước/sau" ở `post.html` lọc + sắp xếp + duyệt **toàn bộ `site.posts` cho từng bài** → O(N²).
  Đo trực tiếp bằng Ruby ở quy mô 6.076 bài: lọc theo `lang` ≈ 82 ms/trang, sắp xếp theo ngày ≈ 108 ms/trang (cả hai chưa gồm
  vòng tìm vị trí). Ngoại suy từ 1.500 bài: khối này tốn khoảng 53 giây ở 1.500 bài và khoảng 14 phút ở 6.076 bài (INFERRED).
- `listing.html` duyệt toàn bộ `site.posts` cho mỗi trong 689 trang danh sách (không dừng khi đủ bài của trang).
- `pagination-nav.html` liệt kê **mọi** số trang trên mỗi trang: danh mục "Kinh nghiệm" có 382 trang, nên mỗi trang
  phát ra 382 liên kết (FACT, đếm từ `listing/kinh-nghiem/*.md`).

## 3. Sửa (template dùng chung, không đổi URL/nội dung/canonical)

1. `post.html`: dùng `page.previous` / `page.next` do Jekyll cấp sẵn (O(1)/trang, thứ tự ổn định theo ngày rồi đường dẫn).
   Cách cũ còn lỗi biên: bài mới nhất có `next_index = -1` nên liên kết "bài sau" quay vòng về bài cũ nhất; 1.496/1.500 bài mới
   nhất có `date` giống hệt nhau nên thứ tự cũ vốn không ổn định.
2. `listing.html`: lấy bài bằng `site.categories[...]` với `limit/offset` (O(page_size)).
3. `topic.html`, `topic-listing.html`: dừng vòng lặp khi đã đủ bài của trang.
4. `pagination-nav.html`: cửa sổ trang (trang 1, trang cuối, trang hiện tại ±2, bội số của 10); nhóm ≤ 15 trang vẫn liệt kê đủ.
   Số liên kết/trang giảm từ 382 xuống khoảng 45; mọi trang vẫn cách nhau tối đa vài bước bằng liên kết `<a href>` thật.

## 4. Kết quả

Profile 1.500 bài (cùng cấu hình, cùng máy):

| Template | Trước | Sau |
|---|---:|---:|
| `post.html` | 117,3 s | 63,2 s |
| `listing.html` | 39,0 s | 22,1 s |
| `pagination-nav.html` | 17,9 s | 12,0 s |

Build đầy đủ 6.076 bài trên sandbox (Jekyll 3.10.0, không có gem `github-pages`; số tuyệt đối không so được với GitHub):

| Phiên bản | Thời gian | Điều kiện |
|---|---:|---|
| Trước (HEAD 4f61156e) | 1.769 s | chạy song song 1–3 build khác |
| Sau (V1+V2) | 864 s | chạy song song 1–2 build khác |
| Sau, bản ứng viên | 771 s | chạy một mình, có `--profile` |

Kiểm tra tương đương HTML (so toàn bộ 6.844 trang giữa trước và sau): 6.843 trang chỉ khác ở các khối dự kiến
(khối bài trước/sau, thanh phân trang, `<link rel="icon">` trùng, hai liên kết chủ đề nổi bật mới, khối "Bài nên đọc trước",
`&` → `&amp;` trong `<title>`/meta); 1 trang khác do hạ H1 trùng trong thân bài. Không trang nào bị mất hoặc thêm.
`check-built-links.py` PASS (0 liên kết nội bộ hỏng), `faq_parity_check.py` PASS.

### Kết quả đo trên GitHub sau khi đẩy commit `ba59ea27` (FACT)

| Hạng mục | Trước (`4f61156e`) | Sau (`ba59ea27`) |
|---|---:|---:|
| Pages: bước "Build with Jekyll" | 18 phút 05 giây | 5 phút 51 giây (20:29:33 → 20:35:24Z) |
| Pages: job `deploy` chờ + chạy | chờ 36 phút 54 giây, chạy 28 giây | chờ 5 giây, chạy 19 giây |
| Pages: từ push tới deploy xong | khoảng 57 phút | 6 phút 55 giây |
| Quality gate: bước build | 18 phút 54 giây | 8 phút 02 giây |
| Quality gate: job `gate` | hủy ở 20 phút (7 bước bị bỏ qua) | THÀNH CÔNG, 10 phút 43 giây, đủ 19 bước |

Mẫu đo thứ hai cho cùng nội dung site (commit báo cáo `94d2cb49`, chỉ thêm tệp ngoài `_site`): bước "Build with Jekyll" của Pages mất
9 phút 59 giây (21:00:14 → 21:10:13Z), bước build của job `gate` mất 9 phút 39 giây, job `gate` xanh sau 13 phút 16 giây (đủ 19 bước),
Pages deploy 19 giây, tổng push → deploy 11 phút 03 giây.

Kết luận thận trọng: thời gian build trên runner GitHub dao động theo lần chạy (5 phút 51 giây và 9 phút 59 giây cho cùng nội dung site).
Hai mẫu sau sửa đều thấp hơn mẫu trước sửa (18 phút 05 giây, một mẫu), tức giảm khoảng 45–68%, nhưng chưa đủ mẫu để nêu trung bình.
Biên an toàn của `gate` so với `timeout-minutes: 20` vẫn hẹp ở lần chậm (13 phút 16 giây); cần theo dõi thêm và xử lý hạng mục SEO-103
(`related-articles`) nếu các lần chạy sau tiến gần mốc 20 phút.

## 5. Còn lại (chưa sửa, có thiết kế)

Profile bản đầy đủ sau sửa (6.076 bài): `related-articles.html` 267 s (≈ 30% thời gian), `header.html` 146 s, `footer.html` 103 s,
icon 138 s (lồng trong header/footer).

- **`related-articles`**: phép lọc `where: "child_id"` quét 6.076 bài cho mỗi trang (bộ nhớ đệm của Jekyll chỉ sống trong một lần render trang).
  Cách dứt điểm cần dữ liệu cụm dựng sẵn (ảnh chụp thứ tự cụm trong `_data`), làm mới có kiểm soát; cần quyết định về việc
  đưa bước này vào luồng publisher hay chạy bảo trì định kỳ. Trạng thái: **DEFERRED** (chạm vùng publisher, cần chủ duyệt).
  → **Cập nhật 01/11/2026: DONE** bằng `include_cached` theo cụm, không cần dữ liệu dựng sẵn hay đổi publisher — xem mục 6.
- **header/footer**: chi phí tuyến tính (~21 ms/trang), có thể giảm bằng cách dựng sẵn HTML tĩnh từ `navigation.yml`;
  lợi ích ≈ 15% build, rủi ro đổi giao diện. Trạng thái: **DEFERRED**.
  → **Cập nhật 01/11/2026: DONE** bằng `include_cached` (HTML giữ nguyên byte, không dựng sẵn HTML) — xem mục 6.
- **Hàng đợi deploy**: job `deploy` chờ 37 phút ở run #5493 là hành vi của GitHub Pages (một deploy tại một thời điểm), không sửa được ở repo.

## 6. Đợt 6 SEO wave 4 (01/11/2026) — `include_cached`, đầu ra giữ nguyên từng byte

Bối cảnh (FACT, profile `--profile` bản gốc commit 17bf875d, 6.289 bài, 648 s; thời gian lồng nhau):
`post.html` 269 s (trong đó `related-articles.html` 188 s), `default.html` 265 s (header 106 s, footer 77 s, seo 49 s),
`icon.html` 103 s / 13.922 lần render. `related-articles` tăng gần O(N²) theo số bài (mỗi trang lọc `where: "child_id"` trên toàn bộ bài).

Đính chính: `quality-gate.yml` dùng `timeout-minutes: 45` từ commit 7810b6d6 (31/10/2026 04:46 UTC), không còn 20 phút như mục 1–5
và báo cáo đợt 5 (`wave4-2026-10-31.md` mục 11.2) đã ghi. Lợi ích chính của mục này là thời gian push → deploy và dư địa tới 10.000 bài,
không phải tránh timeout trước mắt.

Thay đổi (chỉ template + `_config.yml`; plugin `jekyll-include-cache` 0.2.1 có trong `PLUGIN_WHITELIST` của github-pages 232 và Gemfile
`actions/jekyll-build-pages@v1` → image v1.0.13; thiếu plugin thì build dừng với "Unknown tag", không xuất HTML sai):
1. Mọi `{% include icon.html … %}` → `include_cached` (63 chỗ; icon chỉ phụ thuộc tham số).
2. Khung trang chung: header (cache theo tham số `current` = URL trang nếu là URL menu, ngược lại `(none)` → 18 khóa), footer, quick-contact,
   assistant render 1 lần/build; `seo.html` tính `absolute_url`/logo/mô tả một lần mỗi trang, phần JSON-LD dùng chung toàn site
   (Organization, LocalBusiness, WebSite) tách ra `_includes/seo-site.html` (cache theo `price_range`).
3. `related-articles.html`: vòng bài của mỗi cụm dựng 1 lần/build trong `_includes/related-ring.html` (khóa `child_id`), thẻ bài ở
   `_includes/related-card.html`; trang chỉ tìm vị trí của mình và lấy 4 thẻ kế tiếp. Dòng cuối tệp gán `nil` cho biến chứa chuỗi vòng
   (nếu không, Liquid giữ context từng trang tới hết build → RAM đỉnh 3,36 GB).
Quy tắc bảo trì: tệp gọi qua `include_cached` KHÔNG được đọc `page.*` hay biến gán theo trang (chú thích ở đầu từng tệp).

Kiểm chứng (FACT):
- 14 agent (5 thiết kế + 9 phản biện độc lập, workflow wf_dcfd1389-234): site con 716–1.058 bài với ca biên tổng hợp, chế độ `--safe`,
  build toàn site; mọi lần so đều giống từng byte (chỉ `<updated>` của feed.xml = thời điểm build).
- Bản cuối trên main a3a675b8 (6.319 bài, build song song với bản gốc cùng máy): 7.122 trang HTML; khác bản gốc đúng 2 tệp có chủ đích
  (`sitemap.xml` 254 dòng `<lastmod>`, `/lien-he/` 1 dòng) — xem mục 12 báo cáo wave 4.
- CPU build 793 s → 384 s (−52%); thời gian chạy 822 s → 394 s; RAM đỉnh 1,03 → 1,84 GB (runner GitHub: 7 GB repo private / 16 GB public).
- Ước tính ở 10.000 bài (harness tổng hợp, phản biện RELATED #2): `related-articles` 495 s → 90 s.

Không làm (phản biện bác vì lợi < 10 s mà thêm 4 tệp): tách breadcrumb (`article-breadcrumb`), tách head-assets/site-data-js.
SEO-103: **DONE** không cần đổi publisher (mục 5 ở trên giữ để tham khảo lịch sử).

Kết quả trên GitHub (FACT, commit 41b4b193, 6.319 bài; so với đợt 5 commit 2ea6120b, 6.289 bài):

| Hạng mục | Trước | Sau |
|---|---:|---:|
| Quality gate: bước "Build site (Jekyll…)" | 10 phút 16 giây (run #1736) | 4 phút 05 giây (run #1742) |
| Quality gate: job `gate` | 14 phút 11 giây | 7 phút 34 giây |
| Pages: bước "Build with Jekyll" | 10 phút 57 giây (run #5837) | 3 phút 18 giây (run #5854) |
| Pages: job `build` + `deploy` | 11 phút 34 giây + 29 giây | 3 phút 52 giây + 17 giây |
| Engine tests | 20 phút 40 giây, SUCCESS | 20 phút 34 giây, SUCCESS |
