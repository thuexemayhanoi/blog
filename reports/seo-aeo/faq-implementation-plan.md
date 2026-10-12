# Kế hoạch triển khai FAQ / nội dung trả lời cho AI-search — CHỈ ĐỀ XUẤT, CHƯA TRIỂN KHAI

> **Trạng thái: giai đoạn AUDIT.** Tài liệu này KHÔNG thay đổi website. Mọi thay đổi bên dưới chỉ được làm SAU KHI chủ website duyệt matrix
> (`faq-matrix-first300.csv`, `faq-matrix-main-pages.csv`, `faq-matrix-master.csv`) và duyệt từng pha, mỗi pha một PR riêng có CI xanh + rollback.
> Số liệu cụ thể từng URL nằm trong matrix; tổng hợp nằm trong `faq-audit-summary.md`.

## 0. Điều cần chủ website biết trước khi duyệt (quan trọng nhất)

1. **Google đã gỡ FAQ rich result.** Nhật ký Google Search Central (cập nhật 2026-10-08): "This feature will no longer appear in Google Search
   starting May 7, 2026" và tháng 6/2026 gỡ luôn tài liệu ("The FAQ rich result feature is no longer shown in Google Search results").
   Hướng dẫn tối ưu cho tính năng AI của Google (cập nhật 2026-07-10) nói rõ: dữ liệu có cấu trúc **không bắt buộc** cho AI search, **không có
   schema đặc biệt nào cần thêm**, không cần "chunking" nội dung thành mảnh nhỏ, không cần viết riêng cho AI, không cần `llms.txt`, và tạo nội
   dung riêng cho từng biến thể câu hỏi chỉ để thao túng kết quả có thể vi phạm chính sách *scaled content abuse*
   (trích nguyên văn: `data/google-guidance-evidence.json`).
   → **Không nên đầu tư FAQ vì "schema" hay "rich result".** Giá trị còn lại của FAQ là **nội dung hiển thị giúp người đọc tìm đúng câu trả lời**
   (và là nội dung rõ ràng, có nguồn, nhất quán thông tin doanh nghiệp). JSON-LD `FAQPage` chỉ còn là tùy chọn rẻ, trung tính; tác dụng với
   công cụ khác (Bing, các hệ AI khác) **chưa được xác minh** trong lần audit này.
2. Vì vậy kế hoạch này **ưu tiên theo thứ tự**: (P0) sửa rủi ro độ chính xác trong FAQ đang hiển thị → (P1) làm rõ câu trả lời ở các trang quyết định
   (giá, cọc, giấy tờ, chọn xe, nhận/trả xe) → (P2) xử lý trùng ý định/cannibalization và trang chủ đề mỏng → (P3) hạ tầng FAQ dùng chung + schema tùy chọn.
3. **Không FAQ hàng loạt.** Chỉ những URL mà matrix ghi `ADD`/`IMPROVE` mới được đề xuất làm; phần lớn URL là `NO FAQ`.

## 1. Ràng buộc lấy từ chính repo (không phải giả định)

| Ràng buộc | Nguồn trong repo | Hệ quả cho thiết kế |
|---|---|---|
| Bài PUBLISHED/legacy bị ràng buộc bởi hash nội dung của evidence QA (`data/qa/<ID>.json` → `content_sha256`) | `AGENTS.md` quy tắc 8–9, `docs/LEGACY-QA-RE-ATTESTATION-PLAN.md` | **Không sửa `_posts/*.md`** (kể cả front matter) để thêm/đổi FAQ cho bài đã có. Thay đổi cho bài cũ chỉ nằm ở `_includes/`, `_layouts/`, `_data/`, hoặc là một quyết định riêng "đổi nội dung + chấm lại QA độc lập" do chủ duyệt. |
| GitHub Pages dựng bằng gem `github-pages` (Jekyll 3.10, safe mode, chỉ Liquid) | `_config.yml`, workflow `pages build and deployment` | Component viết bằng Liquid thuần; không plugin Ruby, không JS bắt buộc. |
| Build ~12 phút / 2.483 bài (đo cục bộ 708 s) vì `related-articles.html`, `hub.html`, `topic.html` lặp `site.posts` | `docs/CAPACITY-20K-FEASIBILITY.md`, đo trong audit | Component FAQ phải **O(1)** theo trang (tra khóa trong `site.data`), KHÔNG thêm vòng lặp `site.posts`. |
| Schema phải khớp nội dung thật, không bịa rating/review | `docs/SCHEMA-GEO.md` | Nếu có `FAQPage`, sinh từ **cùng biến dữ liệu** với phần hiển thị (một nguồn sự thật) + kiểm parity trong CI. |
| Dữ kiện kinh doanh chỉ từ `data/business-facts.json`; cọc / phí trễ / bảo hiểm / giữ giấy tờ / mũ bảo hiểm / hoàn tiền đang **BLOCKED** chờ chủ xe | `reports/factory/policy-conflicts.md` | FAQ về các chủ đề này KHÔNG được bật cho tới khi chủ xe quyết định; validator chặn số tiền ngoài danh sách duyệt. |
| "Không FAQ hàng loạt" | `docs/CONTENT-FACTORY.md` (nhóm bị cấm), yêu cầu của chủ website | Không dựng bộ câu hỏi giống nhau cho mọi bài; mỗi câu phải có đoạn nguồn thật trên chính trang đó. |
| Liên kết nội bộ làm lúc viết bài mới, không viết lại hàng loạt bài cũ | `docs/INTERNAL-LINKING.md` | Cải thiện liên kết cho bài cũ qua khối ở layout/dữ liệu, không sửa nội dung bài. |
| URL legacy chứa Unicode/khoảng trắng là URL thật, không đổi | `docs/INTERNAL-LINKING.md` mục "URL legacy" | Không đề xuất đổi URL/redirect trong kế hoạch này. |

## 2. Hiện trạng đã kiểm chứng (build cục bộ khớp live; JSON-LD giống hệt trên 6 trang đối chiếu)

* **Không có component FAQ** trong `_layouts/` và `_includes/` (chỉ có `<details>` của TOC trong `post.html`, menu trong `footer.html`/`topic-directory.html`,
  và widget trợ lý "Câu hỏi nhanh" trong `assistant.html` đọc `_data/assistant.yml`, 15 cặp, nhúng JSON `window.NGUYEN_TU_ASSISTANT`).
  **Không có `FAQPage` JSON-LD** ở bất kỳ trang nào trong 377 trang đã render.
* JSON-LD hiện có (`_includes/seo.html`, `_includes/article-breadcrumb.html`): `Organization`, `LocalBusiness`, `WebSite` trên MỌI trang; `BlogPosting` +
  `BreadcrumbList` trên bài. Hub/topic/category/page chỉ có breadcrumb hiển thị, **không có BreadcrumbList JSON-LD** (77/77).
  Cả 377 trang: JSON hợp lệ.
* Hạn chế template đã thấy (không sửa trong giai đoạn này): `BlogPosting` thiếu `image`, `mainEntityOfPage`, `inLanguage` (300/300), `dateModified` luôn bằng
  `datePublished`; `LocalBusiness.priceRange` cứng `"150000-200000 VND"` trong `_includes/seo.html:99` (không lấy từ `business-facts.json`); nội suy
  `"{{ page.title }}"` / `"{{ page.description }}"` trong JSON-LD **không escape** (hiện 0/2.483 bài có ký tự phá JSON, nhưng là rủi ro tiềm ẩn).
* FAQ đang có đều là **nội dung viết tay trong thân bài/trang** (heading `###`/`####`, hoặc đoạn văn "Hỏi … Trả lời …"), không có dữ liệu cấu trúc.

## 3. Kiến trúc đề xuất — "sửa một chỗ, trang đủ điều kiện tự đồng bộ"

### 3.1 Nguyên tắc
1. **Một nguồn sự thật** cho mỗi cặp hỏi–đáp: một biến dữ liệu duy nhất sinh ra khối hiển thị (và JSON-LD nếu bật).
2. **Hiển thị trước, schema sau**: không có hiển thị thì không có schema.
3. **Không chạm `_posts/`** của bài đã xuất bản (giữ hash evidence). FAQ cho bài cũ nằm trong `_data/faq/`.
4. **O(1) mỗi trang**, không vòng lặp `site.posts`.
5. **Mặc định không làm gì**: trang không có dữ liệu → HTML byte-identical với hiện tại.
6. **Không sinh FAQ tự động hàng loạt**: dữ liệu do người duyệt, mỗi câu trích từ đoạn có thật (có `source.quote`) hoặc do chủ viết cho trang tĩnh.

### 3.2 Thành phần
| Thành phần | Vai trò | Ghi chú |
|---|---|---|
| `_includes/faq.html` | Khối hiển thị `section.faq` + (tùy chọn) `FAQPage` JSON-LD từ cùng biến | Prototype đã chạy thử trong site Jekyll tạm ngoài repo: `reports/seo-aeo/prototype/` |
| `_data/faq/<khóa>.yml` | Dữ liệu FAQ theo trang. Khóa = `page.slug` (bài) hoặc `page.faq_key` (trang tĩnh) | Mỗi file một trang → diff nhỏ, ít xung đột |
| Hook trong `_layouts/post.html` (và `page.html`, có thể `topic.html`) | `{% assign faq_data = site.data.faq[page.slug] %}{% include faq.html items=faq_data %}` | Jekyll 3.10 **không** cho truyền `site.data.faq[page.slug]` trực tiếp làm tham số include (đã thử: `Invalid syntax for include tag`) → phải `assign` trước |
| `_config.yml` → `faq_schema: false/true` | Công tắc bật/tắt JSON-LD toàn site | Mặc định `false` (xem §0: Google đã gỡ rich result) |
| `scripts/faq/validate_faq.py` (CI) | Kiểm dữ liệu: ≥2 và ≤6 câu/trang; mỗi câu có `source.quote` tìm thấy nguyên văn trong bài (hoặc `source.type: editorial` cho trang tĩnh); mọi số tiền/giờ/thời hạn phải thuộc `data/business-facts.json`; chủ đề BLOCKED bị chặn; không trùng câu hỏi giữa các trang (Jaccard ≥ 0.6) trừ khi `shared: true` | Dùng lại bộ chuẩn hóa tiếng Việt của audit |
| `scripts/faq/faq_parity_check.py` (CI, sau build) | Parity hiển thị ↔ JSON-LD trên `_site`: đúng 1 `FAQPage`, cặp hỏi–đáp trùng khít, không có khối ẩn | Prototype đã thử cả hai chiều (pass khi đúng, exit 1 khi lệch) |
| Test | Unit test cho validator; test build trên site mẫu (không dữ liệu → output giống hệt; có dữ liệu → parity) | Thêm vào nhóm CI hiện có |

### 3.3 Mô hình dữ liệu (đề xuất)
```yaml
# _data/faq/<slug>.yml  — một file một trang
status: approved            # draft | approved  (chỉ approved mới hiển thị)
page: BLG-00049             # để đối chiếu matrix
items:
  - id: dat-coc-la-gi
    question: "Tiền đặt cọc khi thuê xe máy là gì?"
    answer: "Khoản bảo đảm để hai bên yên tâm thực hiện thỏa thuận; không phải chi phí thuê xe."   # văn bản thuần, ≤ 600 ký tự
    approved: true
    source: {type: body-quote, location: "H2 'Đặt cọc là gì…'", quote: "Khoản cọc không phải là chi phí thuê xe."}
    facts: []                 # khóa trong business-facts.json nếu câu trả lời nêu dữ kiện
    reviewed: {by: owner, date: "2026-10-xx"}
```
Câu trả lời là **văn bản thuần** (không HTML/Markdown) để hiển thị (`escape`) và JSON-LD (`jsonify`) cùng một chuỗi → parity tuyệt đối.

### 3.4 Chi tiết kỹ thuật đã được kiểm chứng trong prototype (Jekyll 3.10, cùng gem với production)
* Trang không có dữ liệu → không xuất gì (HTML không đổi).
* Mục chưa `approved` bị loại khỏi **cả** hiển thị lẫn JSON-LD.
* `jsonify` **không** escape `</` → câu trả lời chứa `</script>` sẽ thoát khỏi khối JSON-LD. Component phải thêm `replace: '</', '<\/'` (đã áp dụng và kiểm).
* Ký tự `"`, `\`, `&`, `<b>`, tiếng Việt: JSON hợp lệ; hiển thị được escape đúng; parity đúng.
* Thời gian dựng thêm ≈ 0 (tra khóa).

### 3.5 FAQ đang có sẵn trong thân bài
* Giữ nguyên hiển thị (không sửa `_posts/`). Component **không** vẽ khối thứ hai cho trang đã có FAQ trong thân bài (tránh trùng).
* Chỉnh câu chữ/độ chính xác của FAQ trong thân bài = **đổi nội dung bài đã xuất bản** → cần quyết định riêng của chủ + chấm lại QA độc lập; chưa làm trong kế hoạch này.
* Trang tĩnh (`bang-gia.md`, `lien-he.md`, `gioi-thieu.md`…) **không bị ràng buộc hash** → có thể sửa trực tiếp sau khi chủ duyệt nội dung.

### 3.6 Bài mới của factory
* Đề xuất (giai đoạn sau, cần duyệt riêng): front matter tùy chọn `faq:` cho bài mới, QA kiểm cùng bộ luật validator. Yêu cầu đổi scorer của Factory QA → **không** thực hiện trong giai đoạn này.

## 4. Phương án triển khai theo nhóm URL
(Số lượng từng nhóm lấy từ matrix; xem `faq-audit-summary.md` §8.)

| Phương án | Dùng cho | Ưu | Nhược / rủi ro |
|---|---|---|---|
| **Template** (layout/include dùng chung) | Sửa đồng loạt không đụng nội dung: breadcrumb JSON-LD cho hub/topic, `BlogPosting` bổ sung `image`/`mainEntityOfPage`/`inLanguage`, escape JSON-LD, `priceRange` lấy từ dữ liệu, khối "bài liên quan" theo ngữ cảnh | Một chỗ sửa, áp cho mọi trang | Đụng HTML của toàn site → cần build diff + kiểm sample; không phải FAQ |
| **Component** (`faq.html` + `_data/faq/`) | URL `ADD` (ý trả lời đã có nhưng bị vùi) và trang tĩnh/chủ đề | Một nguồn sự thật, không đụng `_posts/`, parity kiểm tự động | Cần người duyệt từng câu; tăng số file dữ liệu |
| **Generator** (script gợi ý từ matrix `Suggested Questions`/`Answer Source`) | Tạo bản nháp `_data/faq/*.yml` (status: draft) từ matrix đã duyệt | Nhanh, có truy vết đoạn nguồn | Chỉ ra bản nháp; không tự `approved` |
| **Content** (sửa tay nội dung) | FAQ đang hiển thị có rủi ro chính xác (P0); gộp/phân biệt ý định trùng; làm mỏng trùng lặp | Giải quyết gốc vấn đề | Đổi hash nội dung → chấm lại QA độc lập; làm từng trang, có chủ duyệt |

## 5. Lộ trình theo pha (mỗi pha: PR riêng, CI xanh, rollback = `git revert`)

| Pha | Nội dung | Tiêu chí vào/ra | Rollback |
|---|---|---|---|
| **0 — Audit (xong khi chủ duyệt)** | Matrix + báo cáo trên nhánh `claude/seo-aeo-faq-audit`; không đụng website | Chủ duyệt matrix và thứ tự ưu tiên | Xóa nhánh |
| **1 — Quyết định nội dung P0** | Chủ quyết định các mục BLOCKED (cọc, phí trễ, bảo hiểm, giữ giấy tờ, mũ, hoàn tiền); sửa/gỡ các khẳng định rủi ro trong FAQ đang hiển thị (đầu tiên `/bang-gia/`, rồi các bài P0 trong matrix) | Danh sách P0 = 0 mục tồn đọng | Revert từng PR nội dung |
| **2 — Hạ tầng, không đổi hiển thị** | `_includes/faq.html` + validator + parity check + test; không có dữ liệu → HTML giống hệt | `jekyll build` trước/sau giống byte-for-byte; CI xanh; chủ duyệt | `git revert` (không có dữ liệu thật) |
| **3 — Pilot 10 URL** | 10 URL P1 (mix bài + trang) với `_data/faq/*.yml` đã duyệt, `faq_schema: false` | Parity OK; không tăng thời gian build đáng kể; đọc thử bằng mắt; chủ duyệt từng câu | Xóa file dữ liệu |
| **4 — Mở rộng theo ưu tiên** | 25–50 URL/PR theo P1 → P2 | Cùng tiêu chí pha 3 + không trùng câu hỏi | Revert PR |
| **5 — Bài mới** | `faq:` cho factory (cần đổi QA scorer, duyệt riêng) | Riêng | Riêng |
| **Song song — Template** | Nhóm sửa template ở §4 (chỉ khi chủ duyệt), mỗi nhóm một PR, diff `_site` trên mẫu 30 trang | Không đổi canonical/title/meta | `git revert` |

## 6. Kế hoạch QA
1. **Trước mỗi pha**: build cục bộ (github-pages gem) trên commit nhánh; so `_site` trước/sau bằng diff có chủ đích; chạy `faq_parity_check.py`.
2. **Dữ liệu**: validator (nguồn nguyên văn, dữ kiện thuộc `business-facts.json`, không chủ đề BLOCKED, không trùng câu hỏi, 2–6 câu/trang).
3. **Giữ nguyên**: ngưỡng Factory QA 75/70, mọi gate khác; `data/qa/**`, `_posts/**`, matrix, checkpoint không bị đụng bởi các PR FAQ (kiểm bằng `git diff --stat`).
4. **Thủ công**: đọc thử trang trên điện thoại; kiểm link; nếu bật schema thì kiểm bằng công cụ kiểm tra dữ liệu có cấu trúc của Google (lần audit này **chưa chạy được** công cụ đó → NOT VERIFIED).
5. **Đo lường (cần chủ làm trước)**: kết nối property Search Console của `blog.thuexemaynguyentu.com` (hiện chỉ có `thuexemaynguyentu.com` và `chatbot.…` trong connector) để dùng *Generative AI performance report* và truy vấn theo URL; không có dữ liệu này thì không được tuyên bố tác động.

## 7. Rủi ro và giảm thiểu
| Rủi ro | Giảm thiểu |
|---|---|
| Khuếch đại thông tin chưa duyệt (cọc, phí trễ, pháp lý) | Validator chặn; chủ đề BLOCKED không có FAQ cho tới khi chủ quyết định; P0 làm trước |
| FAQ trùng nội dung đã có trong bài (thừa) | Chỉ `ADD` khi câu trả lời đang bị vùi; mặc định `NO FAQ` |
| *Scaled content* (nhiều trang FAQ gần giống nhau) | Không template chung; mỗi câu có nguồn riêng; giới hạn 2–6 câu; kiểm trùng toàn site |
| Hiển thị ≠ JSON-LD | Một biến dữ liệu + parity check trong CI; schema mặc định tắt |
| Làm chậm build | Component O(1); đo thời gian build trước/sau |
| Hỏng QA evidence của bài cũ | Không sửa `_posts/`; kiểm `git diff --stat` |
| Đổi HTML toàn site khi sửa template | Diff `_site` trên mẫu 30 trang + chủ duyệt từng nhóm template |

## 8. Kế hoạch tối ưu AI-search / AEO / GEO (bám hướng dẫn chính thức của Google, 2026-07-10)
Làm: (1) nội dung riêng, có trải nghiệm thật, nêu rõ nguồn cho khẳng định pháp lý; (2) đoạn mở đầu trả lời thẳng câu hỏi tiêu đề; (3) heading mô tả rõ, bớt
heading chung ("Tóm lại", "Kết lại"); (4) giảm trùng ý định (gộp/phân biệt các bài cùng ý); (5) trang chủ đề không mỏng (hiện median ≈ 40 từ biên tập, mô tả lặp
2 lần); (6) thông tin doanh nghiệp nhất quán (NAP, giá chỉ từ dữ liệu duyệt) + Google Business Profile; (7) đo bằng Search Console.
Không làm: `llms.txt`, "chunking", viết riêng cho AI, tạo hàng loạt trang theo biến thể truy vấn, tìm "mentions" không thật.

## 9. Quyết định cần chủ website
1. Duyệt/chỉnh matrix và thứ tự ưu tiên; xác nhận cách hiểu "300 bài PUBLISHED" (xem `faq-audit-summary.md` §3).
2. Quyết định các mục BLOCKED trong `reports/factory/policy-conflicts.md` (khoảng cọc, phí trễ, bảo hiểm, giữ giấy tờ, mũ, hoàn tiền) — cần để sửa P0.
3. Có triển khai hạ tầng FAQ dùng chung (pha 2) không, và có bật JSON-LD (`faq_schema`) không.
4. Kết nối Search Console của `blog.thuexemaynguyentu.com`.
5. Các phát hiện ngoài phạm vi FAQ (slug mất chữ "đ" của factory, 50 bài permalink dạng ngày-gạch…) có cần xử lý trước khi W2 tiếp tục không.

## 10. Chưa xác minh được trong audit này
Số liệu hiển thị/click/xếp hạng/trích dẫn AI của blog (không có Search Console của blog); công cụ kiểm tra dữ liệu có cấu trúc của Google; tác dụng của `FAQPage` với công cụ ngoài Google;
độ đúng pháp lý của các khẳng định trong bài (chỉ gắn cờ, không đối chiếu văn bản luật); hành vi thật của crawler với URL legacy có khoảng trắng/Unicode.
