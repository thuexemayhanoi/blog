# Hợp đồng quy trình sản xuất (production workflow contract)

Áp dụng cho factory content của thuexemayhanoi/blog. Tài liệu này là hợp đồng
cho BẤT KỲ trình điều phối ngoài nào (scheduler) sau này. Lượt chạy này KHÔNG
lập lịch — chỉ chốt hợp đồng.

Quy tắc so huu engine: engine 10K (writer lock + transaction + publish gate
+ lazy refill) la engine duy nhat so huu production. Workflow cu
publish-queue.yml + _data/publishing.yml la LEGACY-SUPERSEDED, giu
enabled: false, KHONG duoc bat lai song song. CI validation
(factory-capacity-validate.yml) la READ-ONLY: khong bao gio commit/push
ve main; bao cao trong repo chi sinh boi lenh operator chu dong.

Trinh dieu phoi hien tai: FACTORY OPERATOR (docs/PROC-PUBLISH.md).
Writer ngoai (AI hoac nguoi, chi can GitHub read/write) day lenh
whitelist vao data/factory/operator-command.json; workflow
factory-operator.yml (concurrency group blog-factory-production,
cancel-in-progress: false) thuc thi qua
scripts/factory/factory-operator.py + engine chuan. Actions la
deterministic hands: KHONG AI, KHONG API AI, KHONG secret AI,
KHONG viet prose. Van KHONG co cron — chay theo lenh; hourly
production chi khi pilot 5/5 PASS va duoc phe duyet rieng.

## 1. Vòng đời một RUN (bắt buộc theo thứ tự)

```
START
→ fetch HEAD main mới nhất
→ recover transaction nếu treo (TRƯ�C validate — validate FAIL khi
  transaction treo sẽ chặn recover, tạo deadlock)
→ chạy validate.py theo scope lệnh (lệnh sản xuất mặc định fast/chunk;
  exit 0 mới được tiếp tục)
→ mua khóa ghi (writer lock, O_EXCL: data/state/writer-lock.active)
→ phục hồi transaction nếu active (recover)
→ đọc checkpoint (next_claimable_id) + matrix
→ claim 3–5 hàng PLANNED (tối đa 10)
→ viết draft (_drafts/, KHÔNG đụng _posts/)
→ pre-QA deterministic (business facts từ _data/business.yml + _data/pricing.yml)
→ QA + bằng chứng SHA (data/qa/<ID>.json)
→ repair → QA lại (QA → REPAIR → QA)
→ publish gate (khóa + hash + lịch sử transaction)
→ cập nhật matrix/checkpoint
→ commit/push
→ chờ CI xanh (Factory validate + Pages)
→ chunk tiếp nếu an toàn
→ nhả khóa
→ báo cáo
```

## 1b. Mức kiểm tra theo lệnh (FAST/DEEP/FULL)

- Lệnh sản xuất prepare-next/qa/publish mặc định FAST ở CẢ preflight và
  verify cuối run; người vận hành chỉ định rõ deep/full khi cần soát rộng.
- FAST vẫn giữ nguyên mọi ngưỡng và bằng chứng (quality/seo >= 90,
  business_fact/legal PASS-FAIL, hash QA gắn nội dung, publish gate,
  lock, transaction) — chỉ PHẠM VI validate nền tảng hẹp theo chunk.
- FULL dùng cho: thay đổi engine/workflow, kiểm tra cuối đợt sửa, kiểm tra
  định kỳ. KHÔNG bỏ publish gate, KHÔNG bỏ kiểm tra hash/transaction/lock.
- Một coordinator duy nhất mỗi thời điểm; KHÔNG ghi đè operator-command.json
  khi lệnh trước chưa được tiêu thụ (chi tiết: docs/PROC-PUBLISH.md).

## 2. Kích thước

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| Chunk mặc định (một transaction) | 3–5 bài | dễ QA, dễ rollback |
| Tối đa một transaction | 10 bài | KHÔNG vượt |
| Mục tiêu mềm một RUN (đã PUBLISH) | 20–50 bài | KHÔNG phải 50 bản nháp |
| Lô kế hoạch (batch_id) | 50 hàng | gán deterministic theo thứ tự id (B001…) |

## 3. Điều kiện dừng sớm (stop conditions)

Dừng RUN ngay khi xuất hiện BẤT KỲ điều kiện nào:

- chất lượng ngữ cảnh giảm rõ (model tự đánh giá repair rate tăng)
- repair rate tăng bất thường
- xuất hiện blocker pháp lý/nguồn (hàng legal_risk cao thiếu nguồn)
- xung đột khóa ghi (writer lock bị người khác giữ)
- CI đỏ hoặc publish gate từ chối
- HEAD main đổi bất thường giữa RUN
- hàng nguồn cần (source_required=true) chưa có nguồn chính thống

## 4. Trạng thái hợp lệ

PLANNED → WRITING → QA → PASS → PUBLISHED (qua publish gate, không promote tay).

Lỗi: QA → REPAIR → QA; hoặc → REVIEW / BLOCKED / FAIL.

BLOCKED chỉ được đặt khi có lỗi dữ liệu đã chứng minh hoặc blocker pháp lý;
ghi rõ lý do trong cột notes. Ví dụ đã có: BLG-00507 (trùng slug legacy).

## 5. Tự lành (self-healing) đầu RUN

1. transaction active → phục hồi trước (hoàn tác promote dở hoặc continue).
2. draft tồn tại → tiếp tục draft đó, không claim mới đè lên.
3. bằng chứng QA cũ (SHA lệch draft hiện tại) → QA lại, không tái sử dụng.
4. matrix lệch filesystem (hàng PUBLISHED thiếu tệp _posts) → validate.py chặn;
   sửa an toàn trước khi claim.
5. HEAD đổi → fetch lại và đối chiếu trước khi mutate.

## 6. Bằng chứng QA (bắt buộc với mọi bài PUBLISHED)

quality >= 90, seo >= 90, business_fact PASS, legal PASS hoặc NOT_REQUIRED,
critical_failure false; content_sha256 (SHA-256 tệp draft/_posts) và
matrix_row_sha256 (SHA-256 JSON sort-keys của
{title,intent,primary_keyword,expected_url,output_path,canonical_url}) phải khớp.
Bằng chứng cũ (nội dung đổi sau QA) → STALE_QA_EVIDENCE, gate từ chối.

## 7. Sự thật kinh doanh

Chỉ dùng nguồn /blog: _data/business.yml, _data/pricing.yml, tệp chính sách
được duyệt. Cấm nhập số điện thoại/địa chỉ/giá từ /shop. Ba vấn đề chưa chốt
(tiền cọc mức cụ thể, phí trả trễ, bảo hiểm) giữ trung lập:
"Liên hệ để xác nhận." Không bịa khuyến mãi, con số khách hàng, số năm kinh
nghiệm, xếp hạng, cam kết, hỗ trợ 24/7.

## 8. Pháp lý / nguồn

traffic law, mức phạt, giấy phép, bảo hiểm, mũ bảo hiểm, quy định quốc tế:
hàng source_required=true phải đối chiếu nguồn chính thống khi viết; không có
nguồn → REVIEW/BLOCKED, KHÔNG bịa mức phạt hiện hành.

## 9. Liên kết nội bộ (editorial)

Mỗi bài mới 3–5 liên kết ngữ cảnh: child hub → parent hub → bài cùng cụm.
Breadcrumb/TOC/related/footer KHÔNG tính vào hạn mức editorial.

## 10. Điều hướng công khai

Không đổ 10.000 link vào menu/footer. Chỉ dùng: parent hub (7), child hub,
topic pages, phân trang tĩnh 12–24 thẻ/trang, related, discovery. Child mới
chỉ được thêm hub khi chuẩn bị xuất bản bài đầu tiên trong child đó (5 child
mở rộng đã có hub sẵn).
