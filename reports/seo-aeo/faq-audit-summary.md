# Báo cáo audit FAQ / SEO / AEO / GEO — 300 bài + 77 trang chính

| | |
|---|---|
| Repo | `thuexemayhanoi/blog` (chỉ repo này) — website `https://blog.thuexemaynguyentu.com/` |
| Nhánh audit | `claude/seo-aeo-faq-audit` (chỉ ghi vào `reports/seo-aeo/**`; thư mục này bị `exclude` khỏi build Jekyll nên **không thể lên production**) |
| Commit gốc | `c338333f` (main lúc bắt đầu audit) |
| Trạng thái | **AUDIT DONE** theo mục 10 của chỉ thị — kèm các hạn chế nêu rõ ở §13 (chưa kiểm chứng) |
| Deliverables | `faq-matrix-first300.csv` (300 dòng) · `faq-matrix-main-pages.csv` (77 dòng) · `faq-matrix-master.csv` (377 dòng) · `faq-audit-summary.md` (file này) · `faq-implementation-plan.md` · `data/*.json` (dữ liệu máy đọc) |

> Mọi nhận định bên dưới là **đánh giá chuyên môn có bằng chứng** (trích nguyên văn từ bài/trang, kiểm bằng validator cơ học), **không phải số đo lưu lượng**.
> Không có số hiển thị / click / xếp hạng / trích dẫn AI nào của blog được dùng hay suy diễn: connector Search Console **không có property của blog** (§13).

## 0. Kết luận ngắn

1. **Đủ phạm vi**: 300 bài thực tế đang live + 77 trang chính = **377 URL**, mỗi URL một dòng đủ 21 cột bắt buộc, kể cả những bài "không cần FAQ". Validator cơ học (`tools/validate_analysis.py`, `tools/verify_deliverables.py`) đạt 100%.
2. **Hiện không có FAQPage JSON-LD ở bất kỳ URL nào (0/377)**; toàn bộ JSON-LD (377/377) hợp lệ cú pháp. 23 URL có FAQ *hiển thị* (13 bài + 10 trang) — nhưng 22/23 cần sửa nội dung trước (IMPROVE/MERGE) vì chứa khẳng định chưa duyệt hoặc cấu trúc không tách được.
3. **Phần lớn URL KHÔNG nên thêm FAQ**: 336/377 là NO FAQ; chỉ **2 bài** là ADD (BLG-00049, BLG-00090). FAQ hàng loạt sẽ chỉ nhân bản nội dung trùng và nhân rủi ro (đúng cảnh báo *scaled content* của Google).
4. **Rủi ro lớn nhất là độ chính xác, không phải thiếu FAQ**: 37 URL ưu tiên P0 (26 bài + 11 trang). 72/300 bài mẫu (≈24%) và 30/77 trang có ít nhất một khẳng định mà phân tích gắn là chủ đề **BLOCKED** của chủ xe (cọc 2–5 triệu, phí trễ 20.000đ/giờ, bảo hiểm, giữ giấy tờ gốc, mũ bảo hiểm, hoàn tiền); ngoài ra còn khẳng định pháp lý không nguồn (88 bài, 20 trang có ít nhất một). Các mục BLOCKED **chỉ chủ xe quyết định được**; audit không tự sửa.
5. **Cannibalization / trùng ý định đáng kể**: 258 nhóm URL (103 mức HIGH, 155 MEDIUM) quanh 767 URL; 22 cụm câu hỏi trùng giữa các URL; 18 bài đề xuất MERGE. Gộp/redirect cần chính sách canonical của chủ — chưa đổi URL nào.
6. **Giải pháp tập trung đã được dựng, không sửa tay hàng loạt**: sửa template chung (JSON-LD an toàn, BreadcrumbList cho mọi loại trang, bỏ breadcrumb kép…), component FAQ dùng chung + validator + parity check (mặc định không đổi HTML), phân bố lại "bài liên quan" — xem §16.
7. **Google đã gỡ FAQ rich result (không còn hiển thị từ 2026-05-07)** và hướng dẫn AI của Google (2026-07-10) nói không cần schema đặc biệt/chunking/llms.txt. Vì vậy giá trị còn lại của FAQ là **nội dung hiển thị chính xác, dễ trích xuất**, không phải "schema để được hiện".

## 1. Phạm vi và phương pháp

* **Chỉ repo `thuexemayhanoi/blog`** (không WordPress, Hostinger hay repo khác).
* **Mẫu bài viết**: 300 bài *thực sự đang live* có ID nhỏ nhất theo thứ tự tăng dần (xem §3) — danh sách chính xác 300 ID + permalink: `sample-first300-ids.csv`. **Trang chính**: 77 trang (xem §4) — `main-pages-list.csv`.
* **Nguồn dữ liệu thật đã dùng**: (1) repo (matrix, `_posts`, `_data`, layout, tài liệu chính sách); (2) **sitemap live** (2.831 URL, đối chiếu từng URL mẫu); (3) **HTML đã render** từ build Jekyll cục bộ tại commit gốc (gem `github-pages` 232 = Jekyll 3.10, `JEKYLL_ENV=production`, 708 giây, 2.831 trang) — đối chiếu với **trang live** qua Firecrawl ở 6 trang đại diện (trang chủ, hub, topic, bảng giá, 1 bài legacy, 1 bài factory): JSON-LD **giống hệt** trên cả 6, title/canonical/meta/H1/H2/H3 giống; (4) tài liệu chính thức của Google Search Central (nhật ký cập nhật 2026-10-08 và hướng dẫn AI features 2026-07-10; trích nguyên văn ở `data/google-guidance-evidence.json`); (5) Search Console qua connector — **chỉ có `thuexemaynguyentu.com` (site chính) và `chatbot.…`; KHÔNG có property của blog** → không có số hiển thị/click/xếp hạng/trích dẫn AI cho bất kỳ URL blog nào; bảng truy vấn 90 ngày của site chính (46 truy vấn, ≥15 hiển thị) chỉ được lưu làm *ngữ cảnh chủ đề* (`data/gsc-main-site-queries-90d.json`), gắn nhãn rõ "không phải dữ liệu blog".
* **Phân tích xác định (script, tái lập được)**: `tools/extract_audit_data.py`, `extract_rendered.py`, `faq_index.py`, `faq_runin.py`, `inbound_graph.py`, `analyze_deterministic.py` — metadata, permalink, heading, JSON-LD, đồ thị link nội bộ, phát hiện FAQ dạng heading/run-in, trùng lặp văn bản.
* **Phân tích ngữ nghĩa** (ý định, từ khóa, FAQ hiện có/ẩn, chất lượng, rủi ro, ưu tiên): **40 lô agent chuyên trách** (30 lô × 10 bài và 10 lô × ≤8 trang) theo một rubric chung (`tools/agent-rubric.md`; một lô hiệu chuẩn CAL01 gồm 7 bài thuộc mẫu đã chạy trước để chốt rubric), sau đó **validator cơ học** bắt buộc *mọi trích dẫn phải tìm thấy nguyên văn trong bài/trang nguồn*, đúng enum, nhất quán trạng thái–hành động, link đề xuất chỉ thuộc danh sách cho phép. Một mẫu 27 URL được **chấm lại độc lập, mù** (4 agent mới, không thấy kết quả lần đầu) để đo độ tin cậy (§14).
* **Định nghĩa trạng thái FAQ** (đúng như chỉ thị): `Explicit` = đã có mục FAQ/hỏi–đáp rõ ràng; `Implicit` = nội dung đã trả lời nhu cầu nhưng chưa trình bày dạng hỏi–đáp; `None` = chưa đủ cơ sở tạo FAQ đáng tin cậy; `Not recommended` = FAQ không hợp ý định tìm kiếm hoặc chỉ làm bài dài và trùng.

## 2. Kết quả theo 10 chỉ tiêu bắt buộc

| # | Chỉ tiêu | Kết quả |
|---|---|---|
| 1 | Tổng 300 bài thực tế đã audit | **300/300** (BLG-00001…BLG-00306 trừ 6 bài REVIEW; danh sách: `sample-first300-ids.csv`) — cả 300 đều trong sitemap live |
| 2 | Số trang chính được audit | **77** (1 trang chủ, 6 hub, 3 chuyên mục, 11 trang tĩnh, 56 trang chủ đề) — `main-pages-list.csv` |
| 3 | URL đã có FAQ | **23** = 13 bài + 10 trang (Explicit): 1 KEEP (BLG-00009), 20 IMPROVE (10 bài + 10 trang), 2 MERGE (BLG-00207, BLG-00213). Chỉ 2 bài (BLG-00009, BLG-00037) đủ điều kiện đánh dấu ngay (§6, §11) |
| 4 | URL có nội dung trả lời nhưng chưa có FAQ | **231** = 230 bài + 1 trang (Implicit) — phần lớn đã nằm dưới heading mô tả rõ nên *không cần* FAQ (§7) |
| 5 | URL nên bổ sung/cải thiện FAQ | **23** (KEEP + IMPROVE + ADD): bài 13 (1 KEEP, 10 IMPROVE, **2 ADD**) + trang 10 (IMPROVE). Cần *thêm mới* chỉ 2 bài |
| 6 | URL không nên có FAQ | **336** (269 bài + 67 trang) |
| 7 | Schema hợp lệ / lỗi | JSON-LD parse **377/377 hợp lệ, 0 lỗi cú pháp**; `FAQPage` **0**; `BreadcrumbList` có ở 300/300 bài nhưng **0/77 trang**; `BlogPosting` thiếu `image`/`mainEntityOfPage`/`inLanguage` ở 300/300 bài; schema FAQ "Missing" 15 bài + 10 trang (§11) |
| 8 | Cụm câu hỏi trùng lặp / cannibalization | **258 nhóm** cannibalization (103 HIGH / 155 MEDIUM, 767 URL) và **22 cụm câu hỏi FAQ trùng** (§10) |
| 9 | Top 20 URL ưu tiên | §8 |
| 10 | Phương án triển khai | §12 và `faq-implementation-plan.md` |

Bảng chi tiết theo loại:

### Bài viết (n=300)

| Chỉ tiêu | Số lượng |
|---|---|
| FAQ status | EXPLICIT: 13 ; IMPLICIT: 230 ; NONE: 19 ; NOT_RECOMMENDED: 38 |
| Recommended action | KEEP: 1 ; IMPROVE: 10 ; ADD: 2 ; MERGE: 18 ; NO_FAQ: 269 |
| Priority | P0: 26 ; P1: 5 ; P2: 24 ; P3: 245 |
| AI-search opportunity (qualitative) | HIGH: 46 ; MEDIUM: 179 ; LOW: 75 |
| Risk (content/policy) | HIGH: 26 ; MEDIUM: 115 ; LOW: 159 |
| Implementation method | TEMPLATE: 0 ; COMPONENT: 6 ; GENERATOR: 0 ; CONTENT: 294 |

### Trang chính (n=77)

| Chỉ tiêu | Số lượng |
|---|---|
| FAQ status | EXPLICIT: 10 ; IMPLICIT: 1 ; NONE: 13 ; NOT_RECOMMENDED: 53 |
| Recommended action | KEEP: 0 ; IMPROVE: 10 ; ADD: 0 ; MERGE: 0 ; NO_FAQ: 67 |
| Priority | P0: 11 ; P1: 0 ; P2: 0 ; P3: 66 |
| AI-search opportunity (qualitative) | HIGH: 6 ; MEDIUM: 31 ; LOW: 40 |
| Risk (content/policy) | HIGH: 12 ; MEDIUM: 27 ; LOW: 38 |
| Implementation method | TEMPLATE: 7 ; COMPONENT: 2 ; GENERATOR: 0 ; CONTENT: 68 |

Chỉ tiêu cụ thể:

| # | Chỉ tiêu | Bài (300) | Trang (77) | Tổng (377) |
|---|---|---|---|---|
| 3 | URL đã có FAQ hiển thị (EXPLICIT) | 13 | 10 | 23 |
| 4 | Có nội dung trả lời nhưng chưa có FAQ (IMPLICIT) | 230 | 1 | 231 |
| 5 | Nên có FAQ (KEEP + IMPROVE + ADD) | 13 | 10 | 23 |
| 5a |   trong đó cần THÊM mới (ADD) | 2 | 0 | 2 |
| 5b |   trong đó cần CẢI THIỆN FAQ đang có (IMPROVE) | 10 | 10 | 20 |
| 6 | Không nên có FAQ (NO FAQ) | 269 | 67 | 336 |
| 6a | Cần GỘP/phân biệt ý định (MERGE) | 18 | 0 | 18 |

## 3. Mẫu 300 bài — cách hiểu "300 bài PUBLISHED đầu tiên"

* Trạng thái `PUBLISHED` trong matrix của factory chỉ gán cho bài do factory viết (BLG-00484 trở đi); 483 bài đầu (BLG-00001…BLG-00483) là bài **legacy** (`EXISTING`, + 10 `REVIEW`) đã live từ trước. Hiểu theo nghĩa hẹp ("PUBLISHED" = trạng thái factory) thì mẫu là **BLG-00484…BLG-00784**; hiểu theo nghĩa thực tế ("bài đang live, ID tăng dần, bỏ draft/REVIEW") thì mẫu là **BLG-00001…BLG-00306 trừ 6 bài REVIEW (5, 17, 18, 53, 227, 228)**.
* Audit dùng cách hiểu thứ hai vì chỉ thị nhấn mạnh "bài thực tế, không giả định BLG-00001…00300 đều tồn tại, không đưa draft/REVIEW/URL không tồn tại" và vì đó là 300 bài *đầu tiên* của blog. **Cả 300 ID đều thực sự live và có trong sitemap.** Nếu chủ muốn mẫu theo nghĩa hẹp, pipeline chạy lại được (`tools/`), chi phí tương đương.
* Hệ quả cần biết: cả 300 bài mẫu là bài legacy (không có evidence QA của factory; `data/qa/` chỉ có cho bài factory BLG-00484+); chất lượng/độ rủi ro **không đại diện** cho 2.000+ bài factory, vốn đi qua cổng QA 75/70.

## 4. Trang chính (77 trang)

Trang chủ 1 · hub 6 · chuyên mục 3 · trang tĩnh 11 · trang chủ đề (topic) 56 — lấy từ sitemap live + matrix, **không** lẫn với bài thường (261 URL phân trang `/trang/N/` được loại khỏi mẫu và ghi trong `data/site-url-accounting.json`: sitemap 2.831 = 2.493 bài + 77 trang chính + 261 phân trang).

| Loại | n | Explicit/Implicit/None/Not rec. | KEEP/IMPROVE/ADD/MERGE/NO FAQ |
|---|---|---|---|
| Trang chủ | 1 | 0/0/0/1 | 0/0/0/0/1 |
| Hub | 6 | 0/0/3/3 | 0/0/0/0/6 |
| Chuyên mục | 3 | 2/1/0/0 | 0/2/0/0/1 |
| Trang tĩnh | 11 | 8/0/0/3 | 0/8/0/0/3 |
| Chủ đề (topic) | 56 | 0/0/10/46 | 0/0/0/0/56 |

Trang chủ đề mỏng (trung vị ≈ 40 từ biên tập; hub ≈ 71 từ) và mô tả bị lặp hai lần trên 53/77 trang — không phải vấn đề FAQ (nên NO FAQ) mà là vấn đề template/nội dung (đã xử lý một phần ở §16).

## 5. Phát hiện chính (kèm bằng chứng)

1. **FAQ đang hiển thị có chất lượng "vừa phải", cấu trúc yếu, nội dung rủi ro.** 23 URL có FAQ: 1 chất lượng GOOD (BLG-00009), 17 FAIR, 5 WEAK. 9/13 bài (BLG-00003, 00036, 00064, 00081, 00125, 00132, 00184, 00207, 00213) viết FAQ dạng *run-in* ("Hỏi: … Trả lời: …", "Câu hỏi đầu tiên: …") trong 1–2 đoạn văn → không tách được thành cặp hỏi–đáp rời, không đánh dấu được; chỉ 4 bài (00009, 00037, 00050, 00051) có heading + đáp án tách rời. **10/10 trang có FAQ và 3/13 bài (BLG-00081, BLG-00207, BLG-00213) kéo theo khẳng định BLOCKED** (trong đáp án FAQ hoặc cùng trang) (§6, §9).
2. **Trang `/bang-gia/` (và `/bang-gia-xe-*/`, `/gioi-thieu/`, `/lien-he/`, `/kinh-nghiem/`, `/chia-se/`, `/bai-viet/`, `/dieu-khoan/`) nêu cọc 2–5 triệu, hoàn cọc, phí trễ 20.000đ/giờ (+1 ngày sau 6 giờ), bảo hiểm, mũ bảo hiểm.** Đây là chủ đề `BLOCKED` trong `reports/factory/policy-conflicts.md` (chủ xe chưa quyết định) và đang **mâu thuẫn** với `data/business-facts.json` ("mức cọc: xác nhận trực tiếp"). Thêm `FAQPage` lên các trang này ở hiện trạng sẽ *khuếch đại* thông tin chưa duyệt → ưu tiên P0, chưa động vào.
3. **Một số khẳng định pháp lý không nguồn nằm trong FAQ và thân bài** (ví dụ BLG-00003: "Theo luật Việt Nam, du khách nước ngoài có thể thuê xe 50cc mà không cần giấy phép lái xe…"; BLG-00064 về người ngồi sau/giấy tờ bắt buộc; BLG-00132 về ghế/mũ trẻ em). Cùng một câu hỏi pháp lý được trả lời ở nhiều bài với mức chắc chắn khác nhau.
4. **Khẳng định bị cấm** (`forbidden_claims` trong `data/business-facts.json`): BLG-00003 viết "kinh nghiệm phục vụ hàng nghìn khách hàng" (nhóm "số lượng khách đã phục vụ" — bằng chứng bịa; đã sửa, §16). Bộ lọc `forbidden_claims` của scorer còn khớp 3 bài khác (BLG-00037, BLG-00211: "bảo hành" theo nghĩa bảo hành của hãng xe/điện thoại; BLG-00265: "thứ hạng ưu tiên") — đọc ngữ cảnh đó là cách dùng thông thường, không phải cam kết của cửa hàng nên chỉ ghi nhận, không sửa. Ngoài ra 25/300 bài nêu số tiền không có trong danh mục dữ kiện đã duyệt; 0/300 bài dẫn nguồn ngoài.
5. **Bài đã trả lời trực tiếp nhưng nằm dưới heading mô tả tốt nên không cần FAQ**: 180/300 bài heading GOOD, 120 OK, 0 WEAK; 90/300 trả lời trực tiếp ngay đầu bài, 205 một phần. FAQ chỉ có giá trị khi câu trả lời đang bị "vùi" (2 bài ADD).
6. **Liên kết nội bộ lệch**: "bài liên quan" của layout dùng 4 bài **mới nhất** cùng cụm → 288/300 bài mẫu có *cùng một bộ* liên quan; 100% trong 1.200 link liên quan trỏ tới bài đăng 2026-10-07…12; 225/300 bài mẫu không nhận link nào từ thân bài khác lẫn từ khối liên quan (chỉ prev/next). Trụ cột BLG-00002 nhận 283 link thân bài (157 bài trong số đó dùng URL dạng `//`, trả 200 nhưng khác canonical), BLG-00001 nhận 70. 297/300 bài có 2–5 link thân bài dạng mẫu (`/lien-he/`, `/kinh-nghiem/`, `/bang-gia/`) — không có link ngữ cảnh tới bài cùng chủ đề (ví dụ BLG-00002: "body x0").
7. **Title/meta**: title hiển thị (gồm hậu tố thương hiệu) > 60 ký tự ở 289/300 bài (trung vị 82, tối đa 116); mô tả > 160 ký tự ở 128/300 (tài liệu chính sách nội bộ ghi 140–160). Không trùng title/description trong mẫu; canonical khớp 300/300; không có `robots` chặn. **Chưa thay title/meta** (ngoài phạm vi matrix FAQ, chờ chủ quyết định).
8. **Permalink legacy chứa dấu cách + ký tự Unicode ở 300/300 bài** (`/kinh nghiệm/2026/09/13/…`) — URL thật đã live, tài liệu nội bộ ghi nhận là chấp nhận; không đề xuất đổi URL.
9. **Lỗi slug của factory (ngoài mẫu nhưng ảnh hưởng lớn)**: hàm `slugify` bỏ chữ "đ" (đ→"", "xe đạp điện" → `xe-ap-ien`): tại commit gốc, trong 2.010 bài factory PUBLISHED có 1.371 bài có "đ" trong tiêu đề và **cả 1.371 bài** đều mất "đ" trong slug; 388/468 hàng PLANNED sắp bị ảnh hưởng. Chỉ chặn được cho bài chưa viết (§16); bài đã xuất bản giữ URL (không có quyền redirect).
10. **Template/JSON-LD**: không có component FAQ; `BlogPosting` thiếu `image`/`mainEntityOfPage`/`inLanguage` (300/300) và `dateModified` luôn bằng `datePublished` (300/300); `LocalBusiness.priceRange` cố định `"150000-200000 VND"` trong `_includes/seo.html`; chuỗi title/description nội suy vào JSON-LD không escape (0/2.483 bài hiện hỏng, nhưng là rủi ro); 24 bài có **hai** thanh breadcrumb; 77/77 trang chính không có `BreadcrumbList` JSON-LD; hai trang (Trang chủ và `/bai-viet/`) trùng meta description.

## 6. FAQ hiện có (23 URL)

| ID | Loại | # cặp Q&A | Chất lượng | Hành động | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|
| BLG-00003 | Post | 5 | FAIR | IMPROVE | P0 | Câu hỏi đánh số 1-5, đáp án mở đầu bằng nhãn 'Trả lời:'; Q3 nêu luật chưa dẫn nguồn, Q4 có số % không nguồn, Q5 không t… |
| BLG-00009 | Post | 3 | GOOD | KEEP | P3 | Câu hỏi tự nhiên, không đánh số, đáp án 2-3 câu tự đứng độc lập, không có giá/cọc/pháp lý. Nhỏ: tiêu đề câu hỏi chưa có… |
| BLG-00036 | Post | 5 | FAIR | IMPROVE | P2 | Năm cặp ngắn, đúng chủ đề nhưng dồn trong một đoạn nên không tách/markup-ready; câu đầu chỉ trả lời chung; thiếu câu 's… |
| BLG-00037 | Post | 4 | FAIR | IMPROVE | P2 | Cấu trúc tốt nhưng 4 câu thiên về người tự bảo dưỡng xe riêng, thiếu câu chính của bài 'ai chịu thay nhớt khi thuê xe';… |
| BLG-00050 | Post | 3 | FAIR | IMPROVE | P1 | 3 cặp H3 + đoạn trả lời tách rời (tốt). Câu 1 né câu hỏi và nêu quy trình giấy tờ chưa duyệt; câu 3 không nêu giá; câu… |
| BLG-00051 | Post | 3 | FAIR | IMPROVE | P2 | 3 cặp H3 + đoạn trả lời ngắn, tách rời; câu giá khớp danh mục duyệt. Câu 1 đặt điều kiện thuê theo kinh nghiệm lái và c… |
| BLG-00064 | Post | 4 | FAIR | IMPROVE | P0 | 4 cặp thật nhưng viết liền trong hai đoạn văn, không tách rời nên không đánh dấu được. Câu 1 hứa cửa hàng 'sẽ hướng dẫn… |
| BLG-00081 | Post | 20 | WEAK | IMPROVE | P0 | Q&A run-in 'Hỏi:/Trả lời:' (chưa là khối chuẩn); 4 cặp đặt sau mục liên hệ. Nội dung WEAK vì nêu cọc 2-5 triệu, phí trễ… |
| BLG-00125 | Post | 3 | FAIR | IMPROVE | P3 | Run-in trong một đoạn, câu hỏi không có dấu '?' và không phải heading nên không tách/đánh dấu được. Đáp án ngắn, dễ hiể… |
| BLG-00132 | Post | 3 | FAIR | IMPROVE | P0 | Run-in với nhãn 'Câu hỏi đầu tiên:' nằm sau 'Tóm lại', không phải heading. Câu 1 không nêu tuổi cụ thể nhưng khẳng định… |
| BLG-00184 | Post | 2 | FAIR | IMPROVE | P2 | Chỉ 2 cặp, viết run-in ('Nhiều người hỏi...', 'Câu hỏi nữa là...') nên không tách/markup-ready; thiếu câu chính (xử lý… |
| BLG-00207 | Post | 3 | FAIR | MERGE | P2 | Câu hỏi rõ và thật, nhưng 3 cặp dồn trong một đoạn ~190 từ, nhãn 'Câu thứ nhất/hai/ba', chưa tách được; ngưỡng 'nửa bán… |
| BLG-00213 | Post | 3 | FAIR | MERGE | P0 | Ba câu hỏi thật, trả lời ngắn; nhưng viết run-in trong một đoạn (không tách được), nhãn 'Hỏi một/hai/ba', và đáp án 1-2… |
| PG-CHIA-SE | Category | 4 | FAIR | IMPROVE | P0 | Cấu trúc tốt (4 cặp H3 + đáp án ngắn). Nội dung yếu: Đ1 'ưu đãi', Đ2 cam kết ghi nhận mọi vết trầy, Đ3 cam kết chi phí… |
| PG-KINH-NGHIEM | Category | 6 | WEAK | IMPROVE | P0 | 2/6 câu trả lời nêu số BLOCKED (cọc 2–5 triệu, phí trễ), 1 câu cam kết 'hỗ trợ thay xe', câu đầu chung chung; thiếu câu… |
| PG-BAI-VIET | Page | 6 | WEAK | IMPROVE | P0 | Câu hỏi về blog, ít giá trị cho người thuê; câu 4 trỏ tới danh sách 'mới nhất' không có bài đó và không có link; câu 1… |
| PG-BANG-GIA-XE-50CC | Page | 6 | FAIR | IMPROVE | P0 | Ngắn, đúng ý định; câu giá 'liên hệ' khớp dữ kiện duyệt. Yếu: câu giấy phép là khẳng định pháp lý không nguồn, câu tốc… |
| PG-BANG-GIA-XE-DIEN | Page | 7 | FAIR | IMPROVE | P0 | Phủ các lo ngại chính (quãng đường, sạc, giá, mưa, pin) với câu trả lời ngắn, không bịa số. Yếu: câu giấy phép nêu phân… |
| PG-BANG-GIA-XE-GA | Page | 7 | FAIR | IMPROVE | P0 | Câu hỏi sát nhu cầu, trả lời ngắn. Yếu: 2 câu nêu giấy phép/giấy tờ 'bắt buộc theo quy định' không nguồn (LEGAL); câu s… |
| PG-BANG-GIA-XE-SO | Page | 4 | FAIR | IMPROVE | P0 | Câu 2 và 4 khớp dữ kiện duyệt (liên hệ; giao nhận xác nhận trước). Yếu: câu 1 chứa quy tắc giấy phép (LEGAL) không nguồ… |
| PG-BANG-GIA | Page | 5 | WEAK | IMPROVE | P0 | 2/5 câu (cọc, trả muộn) nêu số BLOCKED và cam kết hoàn cọc; câu 5 coi như chỉ có hai khoản phát sinh; thiếu câu 'giá mộ… |
| PG-GIOI-THIEU | Page | 6 | FAIR | IMPROVE | P0 | Câu hỏi tự nhiên, đáp ngắn. Nhưng 'Tiền đặt cọc' nêu khoảng 2–5 triệu và 'Xe có bảo hiểm không?' nêu 'không cung cấp bả… |
| PG-LIEN-HE | Page | 8 | WEAK | IMPROVE | P0 | Hỏi–đáp tự nhiên, ngắn, đúng định dạng; nhưng 3/8 đáp án nêu nội dung BLOCKED (cọc 2–5 triệu, phí trễ, không bảo hiểm),… |

* Chỉ **BLG-00009** (KEEP) có cấu trúc và nội dung tốt: 3 câu tự nhiên, đáp án 2–3 câu tự đứng, không giá/cọc/pháp lý.
* **BLG-00036 và BLG-00051** (rủi ro LOW) chỉ cần sửa **cách trình bày** (tách cặp thành khối rời, giữ nguyên nghĩa). **BLG-00037, 00050, 00184** có cấu trúc/chủ đề đúng nhưng cần xác nhận hoặc diễn đạt lại vài câu (giấy phép 50cc không nguồn, cam kết bảo dưỡng, khẳng định y học/ắc quy, cụm bị cấm). **BLG-00064, 00125, 00132, 00207, 00213** viết run-in trong một đoạn (không tách được); 00064, 00132, 00213 mang khẳng định pháp lý không nguồn; **BLG-00003 và BLG-00081 là P0** (luật 50cc, "hàng nghìn khách hàng", cọc/phí trễ).
* **10 trang** có FAQ (heading + đoạn ngắn — cấu trúc tốt) nhưng **10/10 liên quan khẳng định BLOCKED** (trong FAQ hoặc cùng trang): cần chủ xe quyết định trước khi đánh dấu hoặc mở rộng.

## 7. Nội dung đã trả lời nhưng chưa có FAQ (231 URL Implicit) — vì sao phần lớn KHÔNG thêm FAQ

* Trong 230 bài Implicit: **223 NO FAQ**, **5 MERGE**, **2 ADD**. Lý do chính được ghi từng dòng trong matrix: (a) câu trả lời đã đứng trực tiếp dưới heading mô tả (FAQ thêm sẽ trùng); (b) cùng ý định đã có ở bài chuẩn khác (cannibalization — FAQ chỉ nên đặt ở một bản chính); (c) đáp án chứa dữ kiện chưa duyệt nên FAQ sẽ khuếch đại rủi ro.
* Danh sách các bài Implicit **có hành động khác NO FAQ hoặc ưu tiên ≥ P2** (toàn bộ 230 dòng nằm trong matrix):

| ID | Hành động | Ưu tiên | Rủi ro | # câu đề xuất | Lý do (rút gọn) |
|---|---|---|---|---|---|
| BLG-00048 | NO_FAQ | P0 | HIGH | 0 | Không có FAQ hiển thị. Thân bài có >=2 đáp án tách rời (ai nên thuê xe ga, khác xe số, giá tham khảo) nhưng đã rõ dưới H2 mô tả và trùng BLG-00566; mục chi phí chứa khoản… |
| BLG-00146 | NO_FAQ | P0 | HIGH | 0 | Không có Q&A hiển thị; thân bài có đoạn trả lời được câu hỏi thật ('bắt đầu vào ngày nào', 'nhận xe ga kiểm tra gì', 'có khó không'). H2 đã rõ nên không cần khối FAQ; phầ… |
| BLG-00049 | ADD | P1 | MEDIUM | 5 | Mục 'Những câu hỏi nên hỏi trước khi đặt cọc' chỉ liệt kê câu khách nên hỏi cửa hàng (không có đáp án) nên không phải FAQ; thân bài có >=2 đáp án độc lập (cọc là gì, mức … |
| BLG-00100 | MERGE | P1 | MEDIUM | 4 | Không có mục hỏi-đáp. Có câu trả lời tự đứng được cho các câu hỏi trả xe thực tế nhưng cùng ý định với BLG-00544, nên FAQ (nếu làm) chỉ đặt ở một bản chính; các câu về cọ… |
| BLG-00283 | MERGE | P1 | MEDIUM | 0 | Không có Q&A hiển thị. Câu trả lời cốt lõi ('Chọn xe điện nếu / Chọn xe xăng nếu', L58) tự đứng được, nhưng bộ câu hỏi điện-xăng đã có ở BLG-00579/00915/01966; FAQ sẽ nhâ… |
| BLG-00013 | NO_FAQ | P2 | MEDIUM | 0 | Không có Q&A. Thân bài có vài đoạn trả lời riêng (giờ mở cửa/trả muộn, quãng đường một ngày, nghỉ, đổ xăng) nhưng bố cục từng bước đã dễ quét; thêm FAQ chỉ lặp lại nội du… |
| BLG-00030 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục Q&A; thân bài trả lời được ≥2 câu (chặng một chiều bao xa, xuất phát giờ nào, mưa có nên đi, đi nhóm mấy xe) trong đoạn/dòng ngắn. Các H2 'Bước…' đã dẫn đườn… |
| BLG-00058 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục hỏi-đáp. Thân bài trả lời được >=2 câu thật (ai làm bảo dưỡng định kỳ, dấu hiệu nào báo ngay, sự cố giữa kỳ làm gì) dưới H2 rõ; 'ai chịu chi phí' chưa lập Q&… |
| BLG-00060 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục hỏi-đáp. Đoạn 'Nói trước kết luận' (L16) và các H2 trả lời được >=2 câu thật (vì sao xe lún sau mưa, kiểm giảm xóc/lốp thế nào, phanh ướt có gây lún không); … |
| BLG-00061 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục hỏi-đáp. Thân bài trả lời được >=2 câu thật (đỗ xe thuê ở đâu khi vắng mặt, sạc pin xe điện bao nhiêu trước khi để lâu, xe xăng có cần đổ đầy bình) dưới H2 r… |
| BLG-00063 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục hỏi-đáp. Thân bài trả lời được >=2 câu thật (báo vị trí gồm những gì, gửi định vị có đủ không, có nên tự kéo xe đi sửa tiệm ngoài) dưới H2 mô tả rõ nên không… |
| BLG-00090 | ADD | P2 | LOW | 3 | Chỉ 1 câu hỏi nội tuyến ('Một câu hỏi thường gặp: xe ga hay xe số dễ chạy dốc hơn?') nên chưa phải FAQ. Thân bài còn >=2 câu trả lời tách được cho người thuê nhưng nằm ch… |
| BLG-00130 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục hỏi-đáp; thân bài trả lời được ít nhất 2 câu thật (dấu hiệu chở quá sức, cách sắp xếp đồ, nói gì với nơi cho thuê) bằng 1-3 câu. H2 đã rõ nên không cần FAQ; … |
| BLG-00131 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục hỏi-đáp; thân bài trả lời được ít nhất 2 câu thật (dùng túi/lồng nào, làm quen từng bước, đặt túi ở đâu) trong 1-3 câu. H2 đã rõ nên không cần FAQ; câu pháp … |
| BLG-00237 | MERGE | P2 | MEDIUM | 0 | Có ≥3 câu hỏi thật được trả lời bằng đoạn ngắn tách được (xe số không có cốp, kiểm tra cốp khi nhận xe, chọn xe ga/xe số theo nhu cầu) nhưng đã nằm dưới heading mô tả; th… |
| BLG-00282 | MERGE | P2 | LOW | 0 | Không có Q&A hiển thị (chỉ câu 'Nhiều nhóm cũng hỏi về việc ăn sáng' ở L44, đơn lẻ). Có >=2 câu trả lời tự đứng (khoảng cách, giờ đi, chở quà) nhưng cùng bộ câu hỏi đã nằ… |
| BLG-00288 | MERGE | P2 | LOW | 0 | Không có mục Hỏi-Đáp hiển thị; thân bài có ≥2 đoạn trả lời câu hỏi thật (dự phòng gì, ứng dụng dẫn sai thì làm gì), nhưng bộ câu hỏi trùng BLG-00234 nên không tạo FAQ riê… |
| BLG-00289 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục Hỏi-Đáp hiển thị; ≥2 đoạn trả lời câu hỏi thật (nên thuê thử ngắn trước không, chi phí gồm gì). Đáp án đã rõ dưới H2 mô tả; Q&A về hoàn tiền/cọc phải tránh.… |
| BLG-00292 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục Hỏi-Đáp hiển thị; thân bài có nhiều đoạn 1-3 câu trả lời câu hỏi thật (vì sao mờ, làm gì khi đang chạy, mẹo dân gian có nên dùng). H2 đã mô tả đúng các câu h… |
| BLG-00293 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục Hỏi-Đáp hiển thị; thân bài có nhiều đoạn 1-3 câu trả lời câu hỏi thật (vì sao loe, đánh bóng hay thay, lau đúng cách). H2 đã dạng câu hỏi nên FAQ lặp lại ít … |
| BLG-00295 | NO_FAQ | P2 | MEDIUM | 0 | Không có mục Hỏi-Đáp hiển thị; thân bài có nhiều đoạn 1-2 câu trả lời câu hỏi thật (đi đê lúc nào, nên mang gì, có nên đi đêm). H2 đã mô tả đúng các câu hỏi này nên FAQ l… |

(21 / 230 bài Implicit được liệt kê ở trên; 209 bài còn lại là NO FAQ, ưu tiên P3, không có đề xuất.)

* 2 bài **ADD** (câu trả lời đã có nhưng bị vùi dưới heading chung): **BLG-00049** (Tiền đặt cọc khi thuê xe máy ở Hà Nội: cần biết gì trước khi đưa tiền; ưu tiên P1, rủi ro medium) — câu hỏi đề xuất: "Tiền đặt cọc khi thuê xe máy là gì?" ¦ "Tiền cọc có phải là chi phí thuê xe không?" ¦ "Đặt cọc thuê xe máy ở Nguyễn Tú là bao nhiêu?"; **BLG-00090** (Chạy xe máy trên đường dốc và cầu vượt ở Hà Nội: kỹ năng cần tập; ưu tiên P2, rủi ro low) — câu hỏi đề xuất: "Xe ga hay xe số dễ chạy dốc hơn?" ¦ "Người mới đến hoặc du khách có nên chạy qua cầu ngay những ngày đầu không?" ¦ "Xe thuê thấy phanh khác lạ sau khi xuống dốc dài thì nên làm gì?". Câu hỏi đề xuất và đoạn nguồn của từng bài có trong cột *Suggested Questions* / *Answer Source*.

## 8. Top 20 URL ưu tiên tối ưu nhất

Khóa xếp hạng (`tools/build_matrix.py::top20`): ưu tiên (P0 trước) → cơ hội AI-search → mức rủi ro → *ý định giai đoạn quyết định* (giao dịch/thương mại/địa phương trước thông tin) → số khẳng định chưa xác minh về cọc/giá/pháp lý (nhiều hơn = xếp trước) → số link thân bài trỏ tới URL (mức khuếch đại; chỉ có cho bài) → ID. Đây là **xếp hạng biên tập**, không dựa trên lưu lượng; 37 URL P0 gần như hòa nhau ở ba khóa đầu nên danh sách đầy đủ ở §9.

| # | ID | Ưu tiên | Hành động | FAQ | Cơ hội | Rủi ro | Lý do cơ hội | Lý do rủi ro |
|---|---|---|---|---|---|---|---|---|
| 1 | BLG-00042 | P0 | NO FAQ | Not recommended | HIGH | HIGH | Chọn xe, giá, giấy tờ, cọc là câu hỏi cốt lõi của người thuê và bài đã có đáp án trực tiế… | Bài nêu khoảng cọc 2-5 triệu (BLOCKED), cam kết hoàn cọc và điều kiện bằng lái/tuổi như q… |
| 2 | BLG-00044 | P0 | MERGE | Not recommended | HIGH | HIGH | Giá, chọn xe, giấy tờ cho sinh viên là câu hỏi thật và trang có đáp án; nhưng đáp án chín… | Nêu khoảng cọc 2-5 triệu kèm cam kết hoàn cọc (BLOCKED) và điều kiện tuổi/CCCD/GPLX không… |
| 3 | BLG-00102 | P0 | NO FAQ | Not recommended | HIGH | HIGH | Câu hỏi cốt lõi về chi phí thuê; bài có câu trả lời trực tiếp cho giá đã duyệt, nhưng chỉ… | Bài nêu như sự thật khoảng cọc 2-5 triệu, hoàn cọc có điều kiện và phí trễ 20.000đ/giờ (B… |
| 4 | PG-GIOI-THIEU | P0 | IMPROVE | Explicit | HIGH | HIGH | Có đáp án trực tiếp cho câu hỏi người thuê thật (loại xe, quy trình, giao nhận, giờ, giá… | FAQ và thân bài nêu cọc 2–5 triệu, phí trễ, 'không cung cấp bảo hiểm' (BLOCKED), cộng giấ… |
| 5 | BLG-00003 | P0 | IMPROVE | Explicit | HIGH | HIGH | Chọn loại xe là quyết định cốt lõi của người thuê và bài đã có câu trả lời trực tiếp (bản… | FAQ nêu luật 50cc/GPLX như sự thật không nguồn, số % nhiên liệu không nguồn và 'hàng nghì… |
| 6 | BLG-00031 | P0 | NO FAQ | Not recommended | HIGH | HIGH | Câu hỏi 'thuê hay mua' là quyết định thực tế của người ở Hà Nội một thời gian và trang có… | Trang nêu khoảng cọc 2–5 triệu và cam kết hoàn cọc đầy đủ — chủ đề BLOCKED, vượt dữ liệu… |
| 7 | PG-BANG-GIA | P0 | IMPROVE | Explicit | HIGH | HIGH | Trang giá là ý định quyết định cao nhất (giá, cọc, giao nhận, trả muộn) và đã có câu trả… | Trang giá chính nêu cọc 2–5 triệu, hoàn cọc, phí trễ, bảo hiểm, mũ (BLOCKED) ngay trong F… |
| 8 | PG-BANG-GIA-XE-50CC | P0 | IMPROVE | Explicit | HIGH | HIGH | Người thuê hỏi nhiều về bằng lái, giá và độ phù hợp của xe 50cc; trang đã có câu trả lời… | Câu trả lời giấy phép lái xe (LEGAL) nằm trong FAQ sẽ bị đánh dấu; thân trang còn nêu phí… |
| 9 | PG-BANG-GIA-XE-GA | P0 | IMPROVE | Explicit | HIGH | HIGH | Ý định giá/chọn xe của người thuê, trang có giá duyệt kèm câu trả lời trực tiếp; cơ hội c… | FAQ có khẳng định pháp lý 'bắt buộc theo quy định giao thông' không nguồn; thân trang nêu… |
| 10 | BLG-00032 | P0 | MERGE | Not recommended | HIGH | HIGH | Câu hỏi quyết định thực tế (tự lái hay gọi xe) có đáp án trực tiếp theo tần suất; nhưng c… | Câu bảo hiểm nêu như sự thật thuộc chủ đề BLOCKED, cộng khẳng định pháp lý không nguồn; g… |
| 11 | BLG-00007 | P0 | NO FAQ | Not recommended | HIGH | HIGH | Cách đặt xe và giờ nhận là nhu cầu cốt lõi của người thuê; bài đã có hướng dẫn trực tiếp… | Nêu phí trả trễ 20.000đ/giờ và 150.000-200.000đ như sự thật (chủ đề BLOCKED chưa duyệt);… |
| 12 | BLG-00048 | P0 | NO FAQ | Implicit | HIGH | HIGH | Chọn xe ga hay xe số và giá thuê xe ga là câu hỏi cốt lõi; trang có đáp án và giá khớp da… | Nêu khoảng cọc 2-5 triệu và 'quy trình hoàn cọc' (BLOCKED) trên trang giá/chọn xe có ý đị… |
| 13 | PG-LIEN-HE | P0 | IMPROVE | Explicit | HIGH | HIGH | Ý định địa phương/đặt xe rõ, có sẵn đáp án ngắn cho câu hỏi người thuê thật và dữ liệu đị… | FAQ nêu cọc 2–5 triệu, phí trả xe trễ, 'không cung cấp bảo hiểm' (BLOCKED) cùng thanh toá… |
| 14 | BLG-00020 | P0 | NO FAQ | Not recommended | HIGH | HIGH | Giấy tờ là câu hỏi cốt lõi trước khi thuê và trang có nhiều câu trả lời trực tiếp, nhưng… | Trang ý định cao (giấy tờ) nêu khoảng cọc 2-5 triệu (BLOCKED), ngụ ý giữ giấy tờ và nhiều… |
| 15 | BLG-00035 | P0 | NO FAQ | Not recommended | HIGH | HIGH | Trả xe/hoàn cọc là câu hỏi cốt lõi của người thuê và bài có hướng dẫn trực tiếp; chỉ khai… | Bài nêu phí trễ 20.000đ/giờ, +1 ngày thuê 150-200k và cam kết hoàn cọc (BLOCKED, chưa có… |
| 16 | BLG-00221 | P0 | NO FAQ | Not recommended | HIGH | HIGH | Ý định cốt lõi của người thuê (hợp đồng, cọc, phí trễ) nhưng đáp án trực tiếp phần lớn th… | Khẳng định như sự thật các mục BLOCKED (bên cho thuê không có bảo hiểm cho người thuê, kh… |
| 17 | BLG-00046 | P0 | MERGE | Not recommended | HIGH | HIGH | Giấy tờ và giấy phép lái xe cho khách nước ngoài là câu hỏi cốt lõi, trang có đáp án trực… | Nhiều khẳng định pháp lý (GPLX, IDP, xe 50cc không cần bằng) và bảo hiểm (BLOCKED) nêu nh… |
| 18 | BLG-00127 | P0 | MERGE | Not recommended | HIGH | HIGH | Câu hỏi quyết định thực tế của người thuê (cho bạn mượn xe, ai chịu cọc/hư hỏng) và bài c… | Bài nêu khoảng cọc 2-5 triệu và 'cửa hàng không cung cấp bảo hiểm' như sự thật (BLOCKED,… |
| 19 | BLG-00132 | P0 | IMPROVE | Explicit | HIGH | HIGH | Câu hỏi thật của phụ huynh thuê xe (tuổi chở trẻ, mũ trẻ em, chọn xe) và bài đã có khối h… | FAQ và thân bài nêu nghĩa vụ pháp lý về ghế/mũ trẻ em như chắc chắn nhưng không dẫn nguồn… |
| 20 | BLG-00213 | P0 | MERGE | Explicit | HIGH | HIGH | Câu hỏi tuổi/giấy phép khi thuê là ý định thật của người thuê và phụ huynh, bài có đáp án… | Nêu khoảng cọc 2-5 triệu (BLOCKED) và các khẳng định pháp lý về tuổi/giấy phép như sự thậ… |

## 9. Danh sách P0 (37 URL) — khẳng định chưa xác minh, trích nguyên văn

P0 = vấn đề phải giải quyết TRƯỚC mọi việc FAQ: khẳng định pháp lý/giá/cọc chưa xác minh nằm trong FAQ đang hiển thị, đáp án sai hoặc mâu thuẫn, dữ liệu có cấu trúc không khớp, hoặc trang ý định cao (giá, cọc, giấy tờ, cách thuê) mà lỗi/khoảng trống trực tiếp làm khách hiểu sai (`tools/agent-rubric.md` §3). Cột cuối trích đúng chữ trong bài/trang (đã kiểm nguyên văn bằng validator).

| ID | Loại | Hành động | Lý do rủi ro | Khẳng định chưa xác minh (trích nguyên văn) |
|---|---|---|---|---|
| BLG-00002 | Post | NO FAQ | Cọc 2-5 triệu và 1-2 lần giá trị xe mâu thuẫn nhau và vượt chính sách BLOCKED; khẳng định luật GPLX 50cc không nguồn; c… | [DEPOSIT] "Tiền đặt cọc: Tùy theo loại xe (thường từ 2-5 triệu đồng)"; [DEPOSIT] "Tiền đặt cọc thường bằng 1-2 lần giá trị của xe." |
| BLG-00003 | Post | IMPROVE | FAQ nêu luật 50cc/GPLX như sự thật không nguồn, số % nhiên liệu không nguồn và 'hàng nghìn khách hàng' (claim bị cấm);… | [LEGAL] "Theo luật Việt Nam, du khách nước ngoài có thể thuê xe 50cc mà không…"; [LEGAL] "Theo luật giao thông Việt Nam, du khách nước ngoài không cần có giấy…" |
| BLG-00007 | Post | NO FAQ | Nêu phí trả trễ 20.000đ/giờ và 150.000-200.000đ như sự thật (chủ đề BLOCKED chưa duyệt); trang đặt xe có ý định cao nên… | [PRICE] "trả xe trễ được tính 20.000đ mỗi giờ, và quá sáu tiếng có thể tính th…"; [OTHER] "người thực tế nhận xe phải là người đứng tên thuê và mang giấy tờ của…" |
| BLG-00020 | Post | NO FAQ | Trang ý định cao (giấy tờ) nêu khoảng cọc 2-5 triệu (BLOCKED), ngụ ý giữ giấy tờ và nhiều khẳng định pháp lý chưa xác m… | [DEPOSIT] "Mức tham khảo phổ biến từ 2.000.000 đến 5.000.000 đồng tùy loại xe và…"; [DEPOSIT] "cách an toàn và phổ biến hơn vẫn là cọc bằng tiền để bạn giữ hết giấy…" |
| BLG-00031 | Post | NO FAQ | Trang nêu khoảng cọc 2–5 triệu và cam kết hoàn cọc đầy đủ — chủ đề BLOCKED, vượt dữ liệu đã duyệt (không nêu số cọc); k… | [DEPOSIT] "mức phổ biến dao động từ hai đến năm triệu đồng tùy dòng xe và thời g…"; [DEPOSIT] "Đây là khoản bạn nhận lại đầy đủ khi trả xe đúng hiện trạng" |
| BLG-00032 | Post | MERGE | Câu bảo hiểm nêu như sự thật thuộc chủ đề BLOCKED, cộng khẳng định pháp lý không nguồn; gộp bài mà không xử lý sẽ nhân… | [OTHER] "bảo hiểm thương mại cho người ngồi trên xe không được cửa hàng cung c…"; [LEGAL] "Với xe trên 50cc, người lái cần có giấy phép lái xe hợp lệ, kể cả ngư…" |
| BLG-00035 | Post | NO FAQ | Bài nêu phí trễ 20.000đ/giờ, +1 ngày thuê 150-200k và cam kết hoàn cọc (BLOCKED, chưa có trong business-facts) nên có t… | [PRICE] "Phí trễ được tính 20.000 đồng cho mỗi giờ muộn."; [PRICE] "Nếu trễ quá 6 tiếng, có thể tính thêm một ngày thuê theo loại xe, kho…" |
| BLG-00042 | Post | NO FAQ | Bài nêu khoảng cọc 2-5 triệu (BLOCKED), cam kết hoàn cọc và điều kiện bằng lái/tuổi như quy định chưa kiểm chứng; mâu t… | [DEPOSIT] "Mức đặt cọc tham khảo từ 2.000.000đ đến 5.000.000đ tùy dòng xe, được…"; [LEGAL] "Wave là xe số trên 50cc, vì vậy người thuê cần giấy phép lái xe hợp l…" |
| BLG-00044 | Post | MERGE | Nêu khoảng cọc 2-5 triệu kèm cam kết hoàn cọc (BLOCKED) và điều kiện tuổi/CCCD/GPLX không nguồn; sinh viên có thể chuẩn… | [DEPOSIT] "Mức đặt cọc tham khảo dao động từ 2.000.000đ đến 5.000.000đ tùy loại…"; [LEGAL] "theo quy định hiện hành xe trên 50cc cần giấy phép lái xe hợp lệ, còn…" |
| BLG-00046 | Post | MERGE | Nhiều khẳng định pháp lý (GPLX, IDP, xe 50cc không cần bằng) và bảo hiểm (BLOCKED) nêu như sự thật; khách nước ngoài có… | [LEGAL] "nhóm xe 50cc là lựa chọn phù hợp, vì dòng xe này không yêu cầu giấy p…"; [LEGAL] "IDP chỉ có hiệu lực khi quốc gia cấp phép và Việt Nam cùng tham gia c…" |
| BLG-00048 | Post | NO FAQ | Nêu khoảng cọc 2-5 triệu và 'quy trình hoàn cọc' (BLOCKED) trên trang giá/chọn xe có ý định cao; khách có thể hiểu sai… | [DEPOSIT] "hãy hỏi thêm về điều kiện đặt cọc, thường tham khảo từ 2.000.000đ đến…"; [STATISTIC] "Xe tay ga chiếm tỷ lệ lớn trong số xe được thuê tại Hà Nội" |
| BLG-00059 | Post | NO FAQ | Bài nêu khoảng cọc 2-5 triệu, cách khấu trừ/hoàn cọc và khẳng định cửa hàng không bảo hiểm (BLOCKED, chưa có trong busi… | [OTHER] "Nguyễn Tú không cung cấp bảo hiểm cá nhân, bảo hiểm du lịch hoặc gói…"; [DEPOSIT] "Khoản cọc thông thường dao động từ 2.000.000đ đến 5.000.000đ tùy dòng…" |
| BLG-00064 | Post | IMPROVE | FAQ nêu khẳng định pháp lý (người ngồi sau không cần giấy phép, giấy tờ bắt buộc, cách nộp phạt) không nguồn và lời hứa… | [LEGAL] "Người ngồi sau không cần giấy phép lái, nhưng các vi phạm của người đ…"; [LEGAL] "bộ giấy tờ pháp lý cần có gồm giấy phép lái xe hợp lệ cho loại xe đan…" |
| BLG-00073 | Post | NO FAQ | Nêu khoảng cọc 2.000.000-5.000.000đ như mức thông thường (BLOCKED, trái business-facts) và 'bản gốc giấy tờ tùy thân vẫ… | [DEPOSIT] "mức thông thường dao động từ 2.000.000đ đến 5.000.000đ tùy dòng xe và…"; [OTHER] "quy trình bài bản chỉ ghi nhận thông tin giấy tờ vào hợp đồng, còn bả…" |
| BLG-00081 | Post | IMPROVE | Nêu cọc 2-5 triệu, phí trễ 20.000đ/giờ, hoàn cọc, không hoàn ngày thừa, giữ bản gốc giấy tờ: chủ đề BLOCKED, mâu thuẫn… | [DEPOSIT] "Mức đặt cọc thông thường dao động từ 2.000.000đ đến 5.000.000đ tùy dò…"; [PRICE] "Phí tính thêm khi trả quá giờ thường rơi vào khoảng 20.000đ mỗi giờ,…" |
| BLG-00102 | Post | NO FAQ | Bài nêu như sự thật khoảng cọc 2-5 triệu, hoàn cọc có điều kiện và phí trễ 20.000đ/giờ (BLOCKED); có thể làm người thuê… | [DEPOSIT] "Mức đặt cọc thông thường dao động từ 2.000.000đ đến 5.000.000đ tùy dò…"; [DEPOSIT] "được hoàn lại khi bạn trả xe đúng hẹn, xe nguyên trạng theo biên bản" |
| BLG-00127 | Post | MERGE | Bài nêu khoảng cọc 2-5 triệu và 'cửa hàng không cung cấp bảo hiểm' như sự thật (BLOCKED, mâu thuẫn business-facts: cọc… | [DEPOSIT] "thường từ 2.000.000đ đến 5.000.000đ tùy dòng xe và từng trường hợp"; [OTHER] "Còn phía cửa hàng cho thuê thì không cung cấp bảo hiểm cá nhân, bảo h…" |
| BLG-00132 | Post | IMPROVE | FAQ và thân bài nêu nghĩa vụ pháp lý về ghế/mũ trẻ em như chắc chắn nhưng không dẫn nguồn; câu 1 không nêu tuổi cụ thể;… | [LEGAL] "Trước độ tuổi và cân nặng nhất định, trẻ phải ngồi trong ghế chuyên d…"; [LEGAL] "và trước ngưỡng đó, ghế chuyên dụng gắn chắc là bắt buộc" |
| BLG-00146 | Post | NO FAQ | Hướng dẫn phanh/vị trí chân là nội dung an toàn nhưng có vẻ sai và mâu thuẫn với BLG-02126; người thuê có thể làm theo… | [OTHER] "Xe ga có phanh sau bằng bàn chân như xe số"; [OTHER] "bàn chân phải bận với cần sang số và bàn chân trái bận với cần chuyển…" |
| BLG-00213 | Post | MERGE | Nêu khoảng cọc 2-5 triệu (BLOCKED) và các khẳng định pháp lý về tuổi/giấy phép như sự thật, kể cả trong cặp Q&A; dễ khi… | [DEPOSIT] "Đi cùng hợp đồng là khoản đặt cọc, thường từ 2.000.000đ đến 5.000.000…"; [LEGAL] "nhóm này không yêu cầu giấy phép lái xe theo quy định hiện hành" |
| BLG-00221 | Post | NO FAQ | Khẳng định như sự thật các mục BLOCKED (bên cho thuê không có bảo hiểm cho người thuê, không hoàn tiền thời gian chưa d… | [OTHER] "bên cho thuê không cung cấp bảo hiểm cho người thuê, và người thuê tự…"; [LEGAL] "xe lưu hành ở Việt Nam có loại bảo hiểm trách nhiệm dân sự bắt buộc đ…" |
| BLG-00231 | Post | NO FAQ | Nêu khoảng cọc 2-5 triệu và cam kết hoàn cọc (BLOCKED, trái dữ liệu đã duyệt); trang được 32 bài khác link tới nên lỗi… | [DEPOSIT] "khoản cọc thông thường dao động từ 2.000.000đ đến 5.000.000đ tùy dòng…"; [DEPOSIT] "và sẽ được hoàn khi trả xe đúng trạng thái" |
| BLG-00249 | Post | MERGE | Nêu khoảng cọc 2-5 triệu, điều kiện hoàn cọc và quy tắc trễ >6 giờ như sự thật (chủ đề BLOCKED); trang ý định cao nên d… | [DEPOSIT] "Khoản đặt cọc thông thường dao động từ 2.000.000đ đến 5.000.000đ tùy…"; [DEPOSIT] "việc trả xe đúng hạn mới là điều kiện cơ bản để hoàn cọc suôn sẻ" |
| BLG-00250 | Post | NO FAQ | Nêu khoảng cọc 2-5 triệu và cam kết hoàn phần cọc còn lại như sự thật (BLOCKED), cùng khẳng định 'bạn có quyền' chưa ng… | [DEPOSIT] "Khoản đặt cọc thông thường dao động từ 2.000.000đ đến 5.000.000đ tùy…"; [DEPOSIT] "các khoản khấu trừ từ cọc cần có căn cứ đi kèm, phần còn lại được hoà…" |
| BLG-00276 | Post | NO FAQ | Trang nêu như sự thật khoảng cọc 2-5 triệu, giữ giấy tờ, phí trễ 20.000đ/giờ, không hoàn tiền, không bảo hiểm: đều BLOC… | [DEPOSIT] "thường từ 2.000.000đ đến 5.000.000đ tùy dòng xe và từng trường hợp, v…"; [OTHER] "còn bản gốc giấy tờ vẫn do bạn giữ" |
| BLG-00280 | Post | MERGE | Nêu cọc 2-5 triệu, phí trễ 20.000đ/giờ (+1 ngày sau 6 giờ), 'giấy tờ gốc do bạn giữ', 'mũ bảo hiểm giao kèm': đều BLOCK… | [DEPOSIT] "Khoản đặt cọc thông thường khi thuê xe máy dao động từ 2.000.000đ đến…"; [PRICE] "Phí trễ giờ thường được tính 20.000đ một giờ cho các giờ đầu, và nếu…" |
| PG-CHIA-SE | Category | IMPROVE | Trang nêu phí trả xe trễ (BLOCKED) như cam kết; FAQ chứa cam kết 'ưu đãi', ghi nhận vết trầy, xác nhận chi phí chưa duy… | [PRICE] "Trường hợp trả xe trễ, mức phí phát sinh được tính theo thỏa thuận ba…"; [PRICE] "thuê theo tháng thường có mức giá ưu đãi hơn so với cộng dồn từng ngày" |
| PG-KINH-NGHIEM | Category | IMPROVE | Số cọc 2–5 triệu và phí trễ 20.000đ/giờ (BLOCKED) nằm ngay trong FAQ; đánh dấu FAQPage sẽ khuếch đại số liệu chưa duyệt. | [DEPOSIT] "Tiền đặt cọc (mức tham khảo 2.000.000 – 5.000.000đ tùy loại xe)"; [PRICE] "Phí trễ 20.000đ mỗi giờ nếu trả muộn; trễ quá 6 tiếng có thể tính thê…" |
| PG-BAI-VIET | Page | IMPROVE | FAQ có câu trả lời sai về vị trí bài; 'Tóm tắt nhanh' nêu số cọc và bảo hiểm (BLOCKED) ngay dưới FAQ; đánh dấu FAQPage… | [DEPOSIT] "Tiền đặt cọc tham khảo: 2.000.000 – 5.000.000đ tùy loại xe."; [OTHER] "Bảo hiểm do người thuê tự mua; Nguyễn Tú không cung cấp bảo hiểm." |
| PG-BANG-GIA-XE-50CC | Page | IMPROVE | Câu trả lời giấy phép lái xe (LEGAL) nằm trong FAQ sẽ bị đánh dấu; thân trang còn nêu phí trễ và mũ đi kèm (BLOCKED). | [LEGAL] "xe có dung tích xi-lanh dưới 50cc được phân loại là xe gắn máy và khô…"; [OTHER] "Mũ bảo hiểm: đi kèm xe khi nhận; đội mũ là bắt buộc theo luật." |
| PG-BANG-GIA-XE-DIEN | Page | IMPROVE | Câu giấy phép xe điện (LEGAL) nằm trong FAQ và phí trễ BLOCKED nằm trong thân trang; đánh dấu FAQPage ở hiện trạng khuế… | [PRICE] "Trả xe đúng giờ: phí trễ 20.000đ/giờ; trễ quá 6 tiếng có thể tính thê…"; [LEGAL] "Một số mẫu xe điện được phân loại như xe gắn máy (không cần giấy phép…" |
| PG-BANG-GIA-XE-GA | Page | IMPROVE | FAQ có khẳng định pháp lý 'bắt buộc theo quy định giao thông' không nguồn; thân trang nêu cọc 2–5 triệu, phí trễ, mũ đi… | [DEPOSIT] "Tiền đặt cọc: 2.000.000 - 5.000.000 VND (xác nhận trực tiếp)"; [PRICE] "phí trễ 20.000đ/giờ, trễ quá 6 tiếng có thể tính thêm một ngày thuê k…" |
| PG-BANG-GIA-XE-SO | Page | IMPROVE | Thân trang nêu cọc 2–5 triệu, phí trễ, mũ đi kèm (BLOCKED); FAQ có quy tắc giấy phép chưa nguồn; cần sửa trước khi đánh… | [DEPOSIT] "Tiền đặt cọc tham khảo từ 2.000.000đ đến 5.000.000đ tùy mẫu xe và thờ…"; [PRICE] "phí trễ 20.000đ/giờ; trễ quá 6 tiếng có thể tính thêm một ngày thuê,…" |
| PG-BANG-GIA | Page | IMPROVE | Trang giá chính nêu cọc 2–5 triệu, hoàn cọc, phí trễ, bảo hiểm, mũ (BLOCKED) ngay trong FAQ; đánh dấu FAQPage sẽ khuếch… | [DEPOSIT] "Mức tham khảo từ 2.000.000đ đến 5.000.000đ tùy loại xe và thời gian t…"; [DEPOSIT] "Tiền cọc được hoàn trả đầy đủ sau khi bạn trả xe đúng thời gian thỏa…" |
| PG-DIEU-KHOAN | Page | NO FAQ | Nêu số cọc, phí trễ, bảo hiểm thuộc nhóm BLOCKED và là nguồn các trang khác sao chép; chủ xe phải quyết định trước mọi… | [DEPOSIT] "phổ biến trong khoảng 2.000.000–5.000.000đ tùy loại xe"; [PRICE] "Phí trả xe trễ: 20.000đ mỗi giờ trễ; nếu trễ hơn 6 tiếng, có thể tính…" |
| PG-GIOI-THIEU | Page | IMPROVE | FAQ và thân bài nêu cọc 2–5 triệu, phí trễ, 'không cung cấp bảo hiểm' (BLOCKED), cộng giấy tờ/tuổi chưa duyệt; đánh dấu… | [DEPOSIT] "Mức đặt cọc tham khảo dao động từ 2.000.000đ đến 5.000.000đ tùy loại…"; [PRICE] "phí trễ được tính 20.000đ mỗi giờ; nếu trễ quá 6 tiếng, có thể tính t…" |
| PG-LIEN-HE | Page | IMPROVE | FAQ nêu cọc 2–5 triệu, phí trả xe trễ, 'không cung cấp bảo hiểm' (BLOCKED) cùng thanh toán/giấy phép chưa duyệt; đánh d… | [DEPOSIT] "Tiền đặt cọc phổ biến trong khoảng 2.000.000–5.000.000đ tùy loại xe."; [PRICE] "Phí trả xe trễ là 20.000đ mỗi giờ trễ." |

**Nhóm nguyên nhân P0** (một URL có thể thuộc nhiều nhóm): cọc 2–5 triệu / hoàn cọc / giữ giấy tờ; phí trễ 20.000đ/giờ và quy tắc +1 ngày sau 6 giờ; "bên cho thuê không cung cấp bảo hiểm"; khẳng định pháp lý về giấy phép lái xe/IDP/xe 50cc/trẻ em không nguồn; mẹo an toàn sai hoặc mâu thuẫn (BLG-00146: "Xe ga có phanh sau bằng bàn chân như xe số" — mâu thuẫn với BLG-02126).

## 10. Cannibalization và trùng lặp câu hỏi

* **258 nhóm URL cùng ý định** (103 mức HIGH, 155 MEDIUM) bao quanh **767 URL** (699 bài, 68 trang; gồm cả bài ngoài mẫu 300 là đối thủ nội bộ). Trong 300 bài mẫu: cannibalization HIGH 88, MEDIUM 103, LOW 96, NONE 13; **18 bài đề xuất MERGE**. Trang chính: HIGH 15, MEDIUM 52, LOW 9, NONE 1.
* **Quy tắc đã dùng**: chỉ coi là cannibalization khi *câu hỏi chính* (không chỉ chủ đề) trùng; mỗi nhóm có **bài chuẩn đề xuất** (ghi trong cột *Cannibalization* của matrix). **Chưa gộp, xóa hay redirect** bài nào — cần chính sách canonical/301 của chủ.
* 40 nhóm lớn nhất:

| # URL | Mức | IDs | Ghi chú |
|---|---|---|---|
| 7 | MEDIUM | BLG-00049, BLG-00864, BLG-00974, BLG-00989, PG-BANG-GIA, PG-GIOI-THIEU, PG-LIEN-HE | Trùng ở câu con: FAQ giấy tờ/cọc/giao xe/hủy trùng PG-LIEN-HE; giá, cọc, phí trễ trùng PG-BANG-GIA; cọc: BLG-00049, BLG-00989; giấy tờ: BLG… |
| 7 | MEDIUM | BLG-00614, BLG-01381, BLG-01480, BLG-01559, BLG-01688, BLG-01903, PG-AN-TOAN-PHAP-LY-GIAY-PHEP-LAI-XE | Từ khóa đầu trùng bài tổng quan BLG-00614 'Các hạng bằng lái xe máy tại Việt Nam'; trong cụm có 4 bài 'A1 chạy được xe nào' và 4 bài 'thi A… |
| 7 | MEDIUM | BLG-00374, BLG-00652, BLG-00653, BLG-00658, BLG-00659, PG-AN-TOAN-PHAP-LY-QUY-DINH-GIAO-THONG, PG-HOI-DAP-HOI-DAP-PHAP-LY | BLG-00374, 00652, 00658 nhắm cùng từ khóa 'quy định giao thông xe máy'; mũ bảo hiểm (BLG-00653) và nồng độ cồn (BLG-00659) lặp với cụm Nồng… |
| 7 | MEDIUM | BLG-00033, BLG-00582, BLG-00584, BLG-01553, PG-BANG-GIA-XE-DIEN, PG-XE-MAY-XE-DAP-DIEN, PG-XE-MAY-XE-DIEN | BLG-00033 và BLG-00582 cùng 'xe đạp điện khác xe máy điện'; BLG-01553 và BLG-00584 cùng 'thuê xe đạp điện ở Hà Nội'; PG-BANG-GIA-XE-DIEN ph… |
| 6 | MEDIUM | BLG-00003, BLG-01355, BLG-01532, BLG-01826, BLG-01965, BLG-02285 | Các bài hỏi-đáp chuyên biệt (lần đầu thuê, đi làm, dài hạn, Ba Vì, phố cổ) trả lời cùng câu hỏi chọn số hay ga theo từng tình huống; bài nà… |
| 6 | HIGH | BLG-00003, BLG-00012, BLG-00569, BLG-00921, BLG-01532, BLG-02285 | BLG-00921 và BLG-00569 cùng câu hỏi chính (xe số hay xe ga đường trường); BLG-00012 dài và đủ hơn nên là bản chính đề xuất. BLG-02285 (Ba V… |
| 6 | HIGH | BLG-00015, BLG-00220, BLG-00933, BLG-01773, BLG-02395, BLG-02402 | BLG-00933 cùng câu hỏi chính (khi nào báo cửa hàng); BLG-00015 dài, chi tiết hơn nên là bản chính đề xuất. BLG-01773 (phanh yếu), BLG-00220… |
| 6 | HIGH | BLG-00020, BLG-00500, BLG-00510, BLG-00534, BLG-00539, BLG-01993 | BLG-01993, BLG-00500, BLG-00510 cùng câu hỏi chính (giấy tờ cần mang); BLG-00539, BLG-00534 là ý định con (khách nước ngoài). BLG-00020 là… |
| 6 | MEDIUM | BLG-00028, BLG-00794, BLG-00796, BLG-00802, BLG-00804, BLG-00806 | Năm bài 'Kinh nghiệm đường đến Cửa Lò/Yên Tử/Ba Bể/Thiên Cầm/Sầm Sơn: xăng và nghỉ' cùng khuôn 'xăng và nghỉ' nhưng gắn điểm đến riêng (đối… |
| 6 | HIGH | BLG-00056, BLG-00298, BLG-00313, BLG-01339, BLG-01743, BLG-01854 | BLG-00298 (kỹ năng vào ngõ hẹp) cùng câu hỏi chính; BLG-01854/01743/00313 chuyên quay đầu trong ngõ; BLG-01339 là xe ngược chiều. Theo tiêu… |
| 6 | HIGH | BLG-00106, BLG-00273, BLG-01446, BLG-01641, BLG-02023, BLG-02423 | Theo tiêu đề/H2: 01446 cùng câu hỏi chính (chỉnh gương đúng, có kiểm tra gương xe thuê); 02423 trùng phần làm quen xe; 00273/01641/02023 tr… |
| 6 | HIGH | BLG-00109, BLG-00122, BLG-01299, BLG-01345, BLG-01507, BLG-01581 | Theo tiêu đề/H2: câu hỏi chính 'chở cây cảnh bằng xe máy' đã có ≥4 URL (00122 tổng quát; 01581/01299 bản ngắn; 01507 chậu cây; 01345 chậu l… |
| 6 | HIGH | BLG-00138, BLG-00917, BLG-01210, BLG-01460, BLG-01782, BLG-02116 | BLG-00917 và BLG-01782 trả lời cùng câu hỏi chính (chọn xe theo chiều cao/yên); BLG-02116, BLG-01210, BLG-01460 là biến thể người cao to/tr… |
| 6 | HIGH | BLG-00140, BLG-00546, BLG-00550, BLG-01224, BLG-01526, BLG-01639 | BLG-00550 và BLG-00546 trả lời cùng câu hỏi (chụp/ghi hình khi nhận và trả); BLG-01224 (các góc ảnh) và BLG-01526 (để làm gì) là ý con; BLG… |
| 6 | HIGH | BLG-00201, BLG-00389, BLG-01295, BLG-01342, BLG-01906, BLG-02091 | ≥5 bài cùng truy vấn 'đi xe máy khi sương mù buổi sáng'. BLG-00389 gần như trùng dàn ý và độ dài; 02091 (vành đai), 01342/01906/01295 ngắn… |
| 6 | HIGH | BLG-00017, BLG-00184, BLG-00206, BLG-00838, BLG-01751, BLG-01824 | Cùng câu hỏi 'đi xe máy khi trời lạnh ở Hà Nội': BLG-00017 tổng quan mùa đông (cũ nhất), BLG-00184 gió lạnh về đêm, BLG-00838 sáng sớm, BLG… |
| 6 | HIGH | BLG-00207, BLG-00828, BLG-01340, BLG-01642, BLG-01979, BLG-02428 | 5 bài cùng câu hỏi 'qua đường ngập'. Đề xuất BLG-02428 làm bài chuẩn (tiêu đề dạng câu hỏi, H2 gần trùng, hub thuê xe, URL không dấu); giữ… |
| 6 | HIGH | BLG-00059, BLG-00221, BLG-00980, BLG-01223, BLG-01453, BLG-02036 | BLG-01223 (đọc kỹ hợp đồng) và BLG-01453 (hợp đồng cần ghi rõ gì) trả lời cùng câu hỏi chính; BLG-02036 (theo tháng), BLG-00980 (bồi thường… |
| 6 | HIGH | BLG-00260, BLG-00815, BLG-01035, BLG-01741, BLG-01978, BLG-02450 | BLG-00815 và BLG-01741 (H2 gần như trùng) trả lời đúng câu hỏi này; BLG-01978 chỉ đường hẹp, BLG-02450 xe buýt/taxi, BLG-01035 xe nói chung… |
| 6 | HIGH | BLG-00180, BLG-00264, BLG-01106, BLG-01583, BLG-02103, BLG-02112 | BLG-01583, BLG-01106, BLG-02103 (cùng cụm 'Gửi xe & giữ xe') trả lời cùng câu 'gửi xe qua đêm thế nào'; BLG-02112, BLG-00180 khác ý định (t… |
| 6 | HIGH | BLG-00283, BLG-00579, BLG-00580, BLG-00915, BLG-01462, BLG-01966 | Nhiều bài cùng 'thuê xe điện hay xe xăng'. BLG-00579 cùng cụm Xe máy điện, có H2 'nên chọn xe điện hay xe xăng khi thuê' nên làm bài chuẩn;… |
| 6 | MEDIUM | BLG-00289, BLG-00371, BLG-00396, BLG-00525, BLG-01532, BLG-01617 | Bài khung chồng ý định phụ của bài cùng cụm: chọn xe số/ga (BLG-01532), chi phí kỳ thuê (BLG-01617, BLG-00371), kiểm tra định kỳ (BLG-00396… |
| 6 | HIGH | BLG-00490, BLG-00572, BLG-00870, BLG-01548, PG-BANG-GIA-XE-50CC, PG-XE-MAY-XE-50CC | BLG-00490 'Giá thuê xe 50cc ở Hà Nội' cùng câu hỏi chính (giá); BLG-00572/00870/01548 cùng câu hỏi bằng lái của FAQ; PG-XE-MAY-XE-50CC là t… |
| 6 | MEDIUM | BLG-00040, BLG-00489, BLG-02158, BLG-02421, PG-BANG-GIA-XE-GA, PG-XE-MAY-XE-GA | Bài từng mẫu (BLG-00040 Click/Mio, BLG-02158 giá Vision) và bài so sánh (BLG-00489 giá xe số/xe ga, BLG-02421 chọn xe ga theo tháng) trùng… |
| 6 | MEDIUM | BLG-00042, BLG-00484, BLG-00489, BLG-00560, PG-BANG-GIA-XE-SO, PG-XE-MAY-XE-SO | BLG-00484 (bảng giá theo loại xe) và BLG-00489 (so sánh giá xe số/xe ga) chung ý định giá; BLG-00560/BLG-00042 phục vụ 'xe số là gì/ai nên… |
| 6 | HIGH | BLG-00484, BLG-00989, BLG-01601, PG-BANG-GIA, PG-THUE-XE-DAT-COC, PG-THUE-XE-GIA-THUE | BLG-00484 có cùng từ khóa chính 'bảng giá thuê xe máy Hà Nội'; BLG-01601 (so sánh giá theo ngày) và BLG-00989 (đặt cọc) trùng ý định phụ; h… |
| 6 | MEDIUM | BLG-00007, BLG-00502, BLG-00864, PG-BANG-GIA, PG-GIOI-THIEU, PG-LIEN-HE | Trùng FAQ giấy tờ/cọc/giao xe với PG-GIOI-THIEU và PG-BANG-GIA; BLG-00007/BLG-00502 (đặt xe qua Zalo/điện thoại) cùng ý định liên hệ đặt xe… |
| 6 | MEDIUM | BLG-00623, BLG-00628, BLG-01428, BLG-01690, BLG-01904, PG-AN-TOAN-PHAP-LY-BAO-HIEM | Từ khóa đầu 'bảo hiểm xe máy' bị nhiều bài cùng ý trong cụm: BLG-00623/BLG-01904/BLG-00628 (TNDS là gì/gồm gì), BLG-01428/BLG-01690 (xe thu… |
| 6 | MEDIUM | BLG-00629, BLG-00630, BLG-00659, BLG-01563, BLG-01692, PG-AN-TOAN-PHAP-LY-NOI-DO-CONG | BLG-00629 (quy định) và BLG-00630 (mức phạt) trả lời thẳng ý định chính; BLG-00659 ở cụm Quy định giao thông trùng chủ đề; trong cụm 'uống… |
| 6 | MEDIUM | BLG-00635, BLG-00636, BLG-00637, BLG-00951, BLG-01430, PG-AN-TOAN-PHAP-LY-PHAT-NGUOI | BLG-00635 (phạt nguội là gì) và BLG-00636 (tra cứu) trả lời thẳng ý định chính; trong cụm trùng ý: nhóm tra cứu/kiểm tra (5 bài) và nhóm 'a… |
| 6 | MEDIUM | BLG-00030, BLG-00407, BLG-01335, PG-CUNG-DUONG-CUNG-DUONG-CUOI-TUAN, PG-CUNG-DUONG-CUNG-DUONG-PHO-BAC, PG-DU-LICH-NGOAI-THANH | 'Cung đường cuối tuần' trùng tiêu đề BLG-01335 và ý định BLG-00407/00030; điểm đến trùng trang phố Bắc (Tam Đảo, Bái Đính/Ninh Bình) và tra… |
| 6 | MEDIUM | BLG-00750, BLG-00754, BLG-01333, PG-CUNG-DUONG-CUNG-DUONG-NOI-THANH, PG-DU-LICH-HO-TAY, PG-DU-LICH-PHO-CO | Nhiều bài trùng tuyến (vòng Hồ Gươm/Hồ Tây: BLG-00751, 01333, 01891); BLG-00750 và BLG-00754 là bài đầu mối nội thành. Trang Hồ Tây & lân c… |
| 6 | MEDIUM | BLG-00412, BLG-00809, BLG-01284, PG-CUNG-DUONG-CUNG-DUONG-CUOI-TUAN, PG-CUNG-DUONG-CUNG-DUONG-PHO-BAC, PG-CUNG-DUONG-HA-GIANG | BLG-00809 và BLG-00412 trả lời thẳng ý định 'chạy xe đi tỉnh xa từ Hà Nội'; Đồng Văn (BLG-01574) trùng trang Hà Giang; Tam Đảo, Bái Đính/Ni… |
| 6 | MEDIUM | BLG-00412, BLG-00790, BLG-01444, BLG-01737, PG-CUNG-DUONG-CUNG-DUONG-PHO-BAC, PG-CUNG-DUONG-HA-GIANG | Trong cụm có 3 bài cùng ý định 'thuê xe đi Hà Giang' (BLG-01737, 01444, 00790) cạnh tranh với trang; BLG-00412 (thuê xe đi liên tỉnh) trùng… |
| 6 | HIGH | BLG-00081, BLG-00499, PG-AN-TOAN-PHAP-LY-GIAY-TO, PG-HOI-DAP-HOI-DAP-THU-TUC, PG-THUE-XE-DAT-COC, PG-THUE-XE-THU-TUC | Hub /thue-xe/thu-tuc/, /thue-xe/dat-coc/ và /an-toan-phap-ly/giay-to/ cùng ý 'thủ tục, giấy tờ, cọc'; BLG-00499 (thủ tục lần đầu) và BLG-00… |
| 6 | MEDIUM | BLG-00049, BLG-00941, BLG-01469, PG-BANG-GIA, PG-LIEN-HE, PG-THUE-XE-DAT-COC | Tiêu đề trang nhắm đúng 'đặt cọc thuê xe máy' nhưng không có câu trả lời; BLG-00049 (tổng quan), BLG-00941 (so sánh hình thức), BLG-01469 (… |
| 6 | HIGH | BLG-00004, BLG-00499, PG-AN-TOAN-PHAP-LY-GIAY-TO, PG-HOI-DAP-HOI-DAP-THU-TUC, PG-THUE-XE-DAT-COC, PG-THUE-XE-THU-TUC | Cùng ý định 'thủ tục thuê xe máy lần đầu': BLG-00004 và BLG-00499 (trùng nhau, trùng đúng ý định trang), PG-HOI-DAP-HOI-DAP-THU-TUC (hỏi đá… |
| 6 | HIGH | BLG-00518, BLG-01088, BLG-01936, PG-THUE-XE-THUE-NGAY, PG-THUE-XE-THUE-THANG, PG-THUE-XE-THUE-TUAN | Cùng ý định 'thuê xe máy theo tuần': BLG-00518 (phù hợp nhu cầu nào), BLG-01936 (ở dài ngày), BLG-01088 (công tác). PG-THUE-XE-THUE-NGAY/TH… |
| 6 | MEDIUM | BLG-00468, BLG-00937, BLG-01411, BLG-01788, PG-THUE-XE-GIA-THUE, PG-XE-MAY-SO-SANH-XE | 3 bài cùng ý 'thuê xe máy hay taxi rẻ hơn' (BLG-00937, BLG-01411, BLG-01788) nằm trong trang; BLG-00468 (bài cũ) so với phương tiện khác; P… |
| 6 | HIGH | BLG-00045, BLG-00577, BLG-02066, BLG-02068, PG-BANG-GIA-XE-DIEN, PG-XE-MAY-XE-DIEN | BLG-00045 (cùng chủ đề 'quãng đường, sạc pin') và PG-BANG-GIA-XE-DIEN (giá + FAQ) cùng nhắm 'thuê xe máy điện Hà Nội'; BLG-00577/02066/0206… |

* **22 cụm câu hỏi FAQ trùng** (chủ yếu giữa các trang chính, dùng chung một "nguồn sự thật" thì tránh lệch):

| # URL | URLs | Ví dụ câu hỏi |
|---|---|---|
| 7 | BLG-00081, PG-BANG-GIA-XE-50CC, PG-BANG-GIA-XE-DIEN, PG-BANG-GIA-XE-SO, PG-GIOI-THIEU, PG-KINH-NGHIEM | Tôi cần mang giấy tờ gì khi thuê xe? ¦ Cần giấy tờ gì để thuê xe máy ở Hà Nội? ¦ Thuê xe 50cc cần mang giấy tờ gì? |
| 5 | BLG-00051, PG-BANG-GIA, PG-BANG-GIA-XE-50CC, PG-BANG-GIA-XE-DIEN, PG-BANG-GIA-XE-SO | Giá thuê xe số bao nhiêu? ¦ Giá thuê xe 50cc là bao nhiêu? ¦ Giá thuê xe điện là bao nhiêu? |
| 4 | PG-BAI-VIET, PG-BANG-GIA, PG-BANG-GIA-XE-SO, PG-GIOI-THIEU | Có giao xe ngoài giờ hoạt động không? ¦ Có giao xe số ngoài giờ hoạt động không? ¦ Nguyễn Tú có giao xe ngoài giờ hoạt động không? |
| 4 | PG-BANG-GIA-XE-50CC, PG-BANG-GIA-XE-DIEN, PG-BANG-GIA-XE-GA, PG-BANG-GIA-XE-SO | Nhận xe 50cc ở đâu và trong khung giờ nào? ¦ Nhận xe điện ở đâu và trong khung giờ nào? ¦ Nhận xe ga ở đâu và trong khung giờ nào? |
| 3 | BLG-00003, BLG-00051, PG-BANG-GIA-XE-GA | Xe ga có tốn xăng hơn xe số không? ¦ Xe số có tiết kiệm xăng hơn xe ga không? ¦ Xe ga tốn xăng hơn xe số không? |
| 3 | BLG-00050, PG-BANG-GIA-XE-50CC, PG-BANG-GIA-XE-DIEN | Xe 50cc có cần bằng lái không? ¦ Xe 50cc có cần giấy phép lái xe không? ¦ Xe điện có cần giấy phép lái xe không? |
| 3 | BLG-00081, PG-GIOI-THIEU, PG-LIEN-HE | Tiền cọc bao nhiêu? ¦ Tiền cọc khi thuê xe là bao nhiêu? ¦ Tiền đặt cọc là bao nhiêu? |
| 3 | BLG-00081, PG-GIOI-THIEU, PG-LIEN-HE | Xe có đi kèm mũ bảo hiểm không? ¦ Xe có bảo hiểm không? ¦ Xe có bảo hiểm không? |
| 3 | BLG-00081, PG-GIOI-THIEU, PG-LIEN-HE | Cửa hàng có giao xe tận nơi không? ¦ Có giao xe tận nơi không? ¦ Có giao xe đến nơi tôi không? |
| 3 | PG-BANG-GIA, PG-GIOI-THIEU, PG-LIEN-HE | Mức đặt cọc được xác nhận như thế nào? ¦ Tiền đặt cọc khi thuê xe được xác nhận như thế nào? ¦ Tiền đặt cọc khi thuê xe được xác nhận như thế nào? |
| 2 | BLG-00003, BLG-00050 | Xe 50cc có đi đường dài hoặc lên đồi núi được không? ¦ Xe 50cc có đi đường dài được không? |
| 2 | BLG-00050, PG-BANG-GIA-XE-50CC | Khi nào không nên chọn xe 50cc? ¦ Khi nào không nên thuê xe 50cc? |
| 2 | BLG-00081, PG-KINH-NGHIEM | Xe hỏng giữa đường thì sao? ¦ Xe hỏng giữa đường thì sao? |
| 2 | BLG-00081, PG-BANG-GIA-XE-DIEN | Mưa to có chạy xe tiếp được không? ¦ Xe điện có chạy được khi trời mưa không? |
| 2 | BLG-00081, BLG-00100 | Trả xe trễ thì nên làm gì? ¦ Nếu có nguy cơ trả xe trễ thì nên làm gì? |
| 2 | PG-BANG-GIA-XE-50CC, PG-BANG-GIA-XE-GA | Xe 50cc có chỗ chứa đồ không? ¦ Xe ga có hộc chứa đồ không? |
| 2 | PG-BANG-GIA, PG-BANG-GIA-XE-GA | Giá thuê Honda Vision theo ngày, tuần, tháng là bao nhiêu? ¦ Giá thuê Honda Vision theo ngày, tuần, tháng là bao nhiêu? |
| 2 | PG-BANG-GIA, PG-BANG-GIA-XE-SO | Giá thuê Honda Wave một ngày là bao nhiêu? ¦ Giá thuê Honda Wave một ngày là bao nhiêu? |
| 2 | PG-GIOI-THIEU, PG-LIEN-HE | Thời gian thuê tối thiểu là bao lâu? ¦ Thời gian thuê tối thiểu là bao nhiêu? |
| 2 | PG-GIOI-THIEU, PG-LIEN-HE | Tôi có thể hủy lịch đặt xe không? ¦ Tôi có thể hủy hoặc thay đổi lịch đặt xe không? ¦ Tôi có thể hủy hoặc thay đổi lịch đặt xe không? |
| 2 | PG-GIOI-THIEU, PG-LIEN-HE | Cửa hàng thuê xe máy Nguyễn Tú ở đâu? ¦ Cửa hàng thuê xe máy Nguyễn Tú ở đâu? |
| 2 | PG-GIOI-THIEU, PG-LIEN-HE | Nguyễn Tú làm việc từ mấy giờ đến mấy giờ? ¦ Giờ làm việc của Nguyễn Tú là mấy giờ? |

## 11. Schema / JSON-LD

| Chỉ tiêu | Bài (300) | Trang (77) |
|---|---|---|
| JSON-LD parse được (hợp lệ cú pháp) | 300/300 | 77/77 |
| Có FAQPage JSON-LD | 0 | 0 |
| Có BreadcrumbList JSON-LD | 300 | 0 |
| BlogPosting thiếu image / mainEntityOfPage / inLanguage | 300 / 300 / 300 | n/a |
| Schema FAQ "Missing" (URL nên có FAQ nhưng chưa có markup) | 15 | 10 |
| Schema FAQ "Existing / Invalid" | 0 / 0 | 0 / 0 |
| Schema FAQ "Not applicable" | 285 | 67 |

* "Missing" nghĩa là URL *nên có* FAQ hiển thị nhưng chưa có markup — **không** có nghĩa là phải thêm `FAQPage` ngay: Google không còn hiển thị FAQ rich result; markup chỉ nên bật sau khi nội dung hỏi–đáp đã được sửa (P0) và **chỉ khi hỏi–đáp xuất hiện trên trang** (parity). Hiện chỉ 2 bài (BLG-00009, BLG-00037) đủ điều kiện đánh dấu ngay mà không sửa nội dung.
* Loại JSON-LD đang phát: bài = `BlogPosting` + `BreadcrumbList` + `LocalBusiness` + `Organization` + `WebSite` (2 khối); trang chính = `LocalBusiness` + `Organization` + `WebSite` (1 khối). `<title>` khớp H1 và canonical khớp URL ở 300/300 bài (BLG-00238 có thêm một H1 thứ hai trong thân bài); không có `robots` chặn index; `dateModified` luôn bằng `datePublished` (300/300).

## 12. Phương án triển khai (chi tiết: `faq-implementation-plan.md`)

| Phương án | Dùng cho | Số URL theo matrix |
|---|---|---|
| **Template** (layout/include dùng chung) | Sửa đồng loạt không đụng nội dung: escape JSON-LD, `BlogPosting` đủ trường, `BreadcrumbList` cho mọi loại trang, bỏ breadcrumb/lead lặp, `priceRange` từ dữ liệu, phân bố lại "bài liên quan" | 7 trang (+ toàn bộ bài/trang hưởng lợi khi sửa 1 chỗ) |
| **Component** (`_includes/faq.html` + `_data/faq/<khóa>.json`) | FAQ có nguồn thật, hiển thị = JSON-LD từ cùng biến dữ liệu, mặc định không đổi HTML | 6 bài (BLG-00036, BLG-00049, BLG-00081, BLG-00090, BLG-00125, BLG-00184) + 2 trang (PG-GIOI-THIEU, PG-LIEN-HE) |
| **Generator** | Sinh bản *nháp* dữ liệu FAQ từ cột *Suggested Questions*/*Answer Source* của matrix (status draft, không tự duyệt) | — |
| **Content** (sửa nội dung có kiểm soát) | P0 (BLOCKED/pháp lý), MERGE/cannibalization, bỏ khẳng định bị cấm | 294 bài + 68 trang (đa số là NO FAQ/không đổi; P0/MERGE cần chủ quyết định) |

Nguyên tắc: **không FAQ hàng loạt**; mỗi câu phải có đoạn nguồn thật trên chính trang đó; chủ đề BLOCKED không được bật cho tới khi chủ xe quyết định; schema tắt mặc định (`faq_schema: false`).

## 13. Chưa kiểm chứng được / hạn chế

* **Số liệu hiển thị, click, xếp hạng, trích dẫn AI (Google AI Overviews/AI Mode, Bing, ChatGPT…) của blog**: *NOT VERIFIED* — connector Search Console không có property `blog.thuexemaynguyentu.com`; không có công cụ đo AI citation. Không có con số nào được suy diễn.
* **Công cụ kiểm tra dữ liệu có cấu trúc / Rich Results Test của Google**: chưa chạy được (parity kiểm bằng JSON-LD parse + so sánh hiển thị).
* **Độ đúng pháp lý** của các khẳng định trong bài: chỉ *gắn cờ* khi không dẫn nguồn, **không đối chiếu văn bản luật**.
* **Live vs local**: toàn bộ 377 URL kiểm trên HTML dựng cục bộ từ đúng commit gốc; đối chiếu trực tiếp với trang live chỉ ở 6 URL đại diện (JSON-LD giống hệt) + toàn bộ 300 bài đối chiếu với sitemap live. Firecrawl có thể trả bản cache.
* **Hành vi thật của crawler** với URL legacy có dấu cách/Unicode: chưa xác minh.
* **Tác dụng của `FAQPage` với công cụ ngoài Google**: chưa xác minh.
* **Đánh giá ngữ nghĩa là của agent** (có validator cơ học cho trích dẫn/enum/nhất quán và một mẫu chấm lại mù — §14), không thay thế được quyết định biên tập của chủ cho các mục BLOCKED.

## 14. Độ tin cậy (chấm lại mù, 27 URL)

Mẫu phân tầng theo trạng thái FAQ lần đầu: 21 bài + 6 trang; 4 agent mới chấm lại từ dữ liệu thô, không thấy kết quả lần đầu (`data/blind-recheck.json`).

| Chỉ tiêu | Đồng thuận tuyệt đối |
|---|---|
| Hành động khuyến nghị (KEEP/IMPROVE/ADD/MERGE/NO FAQ) | 25/27 (93%) |
| Ưu tiên (P0–P3) | 25/27 (93%); lệch ≤ 1 mức: **27/27** |
| Rủi ro / cơ hội AI-search / cannibalization | 22/27 (81%) / 22/27 (81%) / 22/27 (81%) |
| Trạng thái FAQ (Explicit/Implicit/None/Not rec.) | 20/27 (74%) — lệch ở ranh giới *None ↔ Implicit ↔ Not recommended*, không có ca Explicit bị chấm sai |
| **Tập P0** | **trùng khớp 6/6** (không URL P0 nào chỉ một bên thấy) |

Kết luận: danh sách P0 và hành động (thứ phục vụ quyết định) ổn định; ranh giới giữa *None/Implicit/Not recommended* mang tính biên tập — con số 231 Implicit nên đọc là "xấp xỉ", không phải số đo chính xác.

## 15. Phát hiện ngoài phạm vi FAQ (cần chú ý)

1. **GitHub Pages bị hủy build liên tục**: trong 12 lần "pages build and deployment" gần nhất có 11 lần bị hủy vì factory đẩy commit mỗi vài phút; build thành công mất ≈ 10,4 phút (đo của `docs/CAPACITY-20K-FEASIBILITY.md`) → nội dung mới chỉ lên production khi các writer dừng. Nguyên nhân kỹ thuật cục bộ: `related-articles.html` quét toàn bộ `site.posts` cho từng bài (O(N²)) — phần lớn thời gian build (đo bằng `jekyll build --profile`). Đã xử lý ở §16.
2. **Capacity 10K vs 20K**: chỉ tiêu biên tập đã kiểm chứng 7.463 bài (6.980 + 483 legacy); trần engine 10.000; mục tiêu 20.000 cần sửa cấu hình + giải bài toán build. Đề xuất ở `docs/CAPACITY-20K-FEASIBILITY.md`.
3. **7 bài PUBLISHED có `parent_id`/`child_id` sai trong front matter** (ràng buộc hash của evidence → chỉ sửa được qua quy trình re-attest đã duyệt).
4. **Một số bài legacy bị xếp sai cụm** (ví dụ BLG-00002 vào "Kỹ năng lái cơ bản", BLG-00060 vào "Bảo hiểm xe máy") → khối liên quan lệch ý định; dữ liệu `existing-map.json` là seed không chỉnh tay.
5. **Hai trang trùng meta description** (Trang chủ và `/bai-viet/`) — đã sửa: `/bai-viet/` có mô tả riêng (§16).

## 16. Tối ưu đã triển khai sau khi chủ ủy quyền (cập nhật sau audit)

Các sửa dưới đây **không thay đổi URL, canonical, title, meta, nội dung bài, QA, engine gate hay evidence** và mỗi PR có CI xanh + rollback bằng `git revert`:

| PR | Nội dung | Trạng thái |
|---|---|---|
| #14 | Template SEO an toàn: mọi chuỗi trong JSON-LD qua `jsonify` + escape `</`; `BlogPosting` thêm `mainEntityOfPage`/`inLanguage`/`image`; `BreadcrumbList` JSON-LD cho hub/topic/chuyên mục/trang (khớp 1:1 breadcrumb hiển thị); bỏ breadcrumb kép và đoạn mô tả lặp; chuẩn hóa link trụ cột `//` → `/`; `priceRange` lấy từ `_data/pricing.yml` (giá trị render không đổi) | Đã merge (2026-10-12); đã kiểm trên trang live `/bang-gia/` (BreadcrumbList có mặt) |
| #15 | Hạ tầng FAQ dùng chung: `_includes/faq.html` + `_data/faq/<khóa>.json` (một nguồn cho hiển thị và JSON-LD), `scripts/faq/validate_faq.py` (đáp án trích nguyên văn, chặn BLOCKED/số tiền ngoài danh mục/trùng câu hỏi), `faq_parity_check.py` (CI sau build), 38 test mới, tài liệu `docs/FAQ-COMPONENT.md`; **mặc định không đổi HTML** | Đã merge (2026-10-12) |
| #17 | Hiển thị: giá VND dễ đọc (`150.000 VND`), link chủ đề con có `/` cuối, nhãn breadcrumb chuyên mục có dấu, CTA giá/liên hệ trên 62 trang hub/topic | Đã merge (2026-10-12); đã kiểm trên trang live `/bang-gia/` (giá định dạng mới) |
| #19 | `slugify` giữ chữ "đ" cho hàng mới và **giữ nguyên mọi URL đã sinh** (4 cột URL cho mọi trạng thái), công cụ `--reslug-planned-after` fail-closed, 14 test (do phiên Master Matrix port từ PR #16 cùng nội dung) | Đã merge (2026-10-12) |
| #21 | Dữ liệu: re-slug 349 hàng PLANNED chưa viết (BLG-02553…02961), chỉ 4 cột URL, ngoài vùng đệm 40 hàng quanh lease đang giữ; bài đã xuất bản không đổi URL | Đã merge (2026-10-13) |
| #22 | "Bài viết liên quan" xoay vòng theo cụm: mỗi bài trong cụm ≥ 5 bài nhận đúng 4 link liên quan khác nhau (trước: 2.253/2.535 bài không nhận link nào, một bài nhận 159; sau: 1 bài, tối đa 6); chi phí ~ O(cụm) — build Jekyll cục bộ 8 phút 29 giây → 4 phút 24 giây; A/B toàn site (bỏ khối liên quan) 0 thay đổi head/nội dung/JSON-LD; đối chiếu độc lập 2.532/2.532 bài khớp từng link. Kèm sửa fixture `test_slugify_vi` (đỏ trên main sau #21) | Đã merge (2026-10-13), CI xanh (engine 30/30 suite) |
| #23 | Nội dung legacy không cần quyết định của chủ: 2 FAQ pilot (BLG-00090, BLG-00049 — đáp án trích nguyên văn, chủ đề cọc chỉ "xác nhận trực tiếp", JSON-LD tắt); tách FAQ run-in của BLG-00036 thành Q&A rời (chữ giống hệt); bỏ claim "hàng nghìn khách hàng" và số % nhiên liệu không nguồn ở BLG-00003; mô tả riêng cho `/bai-viet/` | CI đang chạy |

## 17. Việc chờ quyết định của chủ website (gộp một danh sách)

Các mục dưới đây **không thuộc quyền tự quyết của AI** (dữ kiện kinh doanh, pháp lý, chính sách URL, quyền hạn hệ thống). Nội dung liên quan được **giữ nguyên, không sửa, không khuếch đại bằng FAQ** cho tới khi có quyết định.

1. **Chủ đề BLOCKED** (`reports/factory/policy-conflicts.md`): mức cọc, hoàn cọc/khấu trừ, phí trả trễ (20.000đ/giờ và +1 ngày sau 6 giờ), bảo hiểm, giữ giấy tờ gốc, mũ bảo hiểm kèm xe, hoàn tiền trả sớm. Có mặt ở 68/300 bài mẫu và 30/77 trang (gồm toàn bộ 10 trang có FAQ) — đây là nguyên nhân của hầu hết 37 URL P0. Cần **một quyết định chính sách** (hoặc xác nhận "xác nhận trực tiếp, không nêu số") để sửa đồng bộ qua dữ liệu, không sửa tay từng bài.
2. **Khẳng định pháp lý** (giấy phép lái xe 50cc/xe điện, IDP, trẻ em/ghế/mũ, giấy tờ bắt buộc…): cần nguồn chính thức hoặc người có thẩm quyền xác nhận; hiện chỉ được hedge/gắn cờ.
3. **Cannibalization / MERGE** (261 nhóm, 16 bài MERGE trong mẫu): chọn bài chuẩn cho từng cụm và **chính sách canonical/301**. Chưa có quyền đổi URL hay redirect nên chưa gộp bài nào.
4. **1.371 bài factory đã xuất bản có slug mất chữ "đ"** (URL thật đang live; số này chỉ tính các bài đã xuất bản tại thời điểm audit, các bài W1/W2 xuất bản sau đó trước khi có bản sửa cũng bị): giữ nguyên hay chuyển hướng 301? Hàng PLANNED chưa viết: 349 hàng (BLG-02553…02961) đã được sửa slug (PR #21); còn 7 hàng (BLG-02505…02512) nằm trong vùng đệm 40 hàng quanh lease đang hoạt động của W1 nên công cụ từ chối sửa (fail-closed) — làm ở đợt sau khi không còn lease gần. Bài đã xuất bản không đụng tới khi chưa có quyết định.
5. **7 bài PUBLISHED có `parent_id`/`child_id` sai trong front matter** (bị ràng buộc hash evidence QA): chỉ sửa được qua quy trình re-attest đã dựng (PR-B/C đang chờ chủ nghiệm thu).
6. **Search Console của `blog.thuexemaynguyentu.com`** chưa kết nối vào connector → không đo được tác động (hiển thị, click, xếp hạng, báo cáo AI). Cần kết nối trước khi tuyên bố bất kỳ hiệu quả nào.
7. **Cách hiểu "300 bài PUBLISHED đầu tiên"** (§3): mẫu hiện tại = 300 bài live đầu tiên (đều là bài legacy). Nếu muốn mẫu theo nghĩa hẹp (BLG-00484…BLG-00784, bài của factory), chạy lại pipeline.
8. **Title/meta**: 289/300 title > 60 ký tự, 128/300 mô tả > 160 ký tự (chưa đổi vì thuộc quyết định SEO riêng, không nằm trong matrix FAQ). Trùng meta description giữa Trang chủ và `/bai-viet/` đã được sửa (mô tả riêng cho `/bai-viet/`, §16).
9. **JSON-LD `FAQPage` có nên bật không**: Google đã ngừng FAQ rich result và hướng dẫn AI không yêu cầu schema, nên giá trị chủ yếu là nội dung hiển thị rõ ràng. Hai bài pilot (BLG-00049, BLG-00090) hiển thị khối FAQ nhưng để `"schema": false` (JSON-LD tắt); hạ tầng đã sẵn sàng và đã qua parity check — muốn bật chỉ cần đổi một dòng trong file dữ liệu. Chỉ nên mở rộng FAQ/schema sang trang khác sau khi các mục BLOCKED/pháp lý của trang đó được chủ quyết định.
10. **Capacity 10K vs 20K** (`docs/CAPACITY-20K-FEASIBILITY.md`): chỉ tiêu biên tập đã kiểm chứng 7.463 bài; vượt 10.000 cần sửa cấu hình + code + test và giải bài toán build.
11. **Triển khai/build của GitHub Pages**: build thành công mất ≈ 10 phút và bị hủy khi factory đẩy commit mỗi vài phút (11/12 lần gần nhất bị hủy) → nội dung mới chỉ lên production khi writer dừng. Cần quyết định kiến trúc (ví dụ gom push, deploy bằng workflow riêng, giảm thời gian build); đã giảm chi phí build một phần bằng tối ưu "bài liên quan" (§16).
