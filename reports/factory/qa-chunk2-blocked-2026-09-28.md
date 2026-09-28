# QA chunk 2/2 (BLG-00645..BLG-00654) — BLOCKED sau 3 lần dispatch thất bại

Ngày: 2026-09-28. Người ghi: writer ngoài (external AI), theo giới hạn repair
tối đa 3 lần mỗi vấn đề (docs/PROC-PUBLISH.md, docs/RECOVERY.md).

## Trạng thái repository tại lúc ghi (đọc từ nguồn, không suy đoán)

- HEAD lúc phân tích: 02fe9fc233d769d51864e907736060b719821ab4.
- Checkpoint: last_completed_article_id BLG-00644, next_claimable_id
  BLG-00655, in_progress_chunk BLG-00645..BLG-00654 (10 hàng WRITING).
- Writer-lock: locked=false. Transaction: active=false.
- data/qa/: có bằng chứng đến BLG-00644; KHÔNG có bằng chứng cho
  BLG-00645..BLG-00654 (op qa chưa từng commit output).
- Drafts _drafts/2026-09-28-*: đủ 10 file cho chunk, tên trùng slug matrix
  (matrix TẠO MỚI 2026-09-27; slug hệ thống bị mất ký tự "d", ví dụ
  "vach-ke-uong", "co-bi-khong" — nhất quán matrix/draft/live, ghi nhận để
  chủ xe xem xét, không tự sửa matrix).

## Chuỗi dispatch qa chunk 2/2 (cả 3 lần FAIL, không có mutation nào được commit)

1. Run #133 (id 3639755xxxx, head c8abfa1) — qa scope full. Kết quả:
   FAILURE. Nhận định khi đó: bước verify (scope full) hỏng.
2. Run #134 (head fe5ee36) — qa scope fast. Kết quả: FAILURE.
3. Run #135 (id 36397553131, head 02fe9fc) — qa scope fast. Kết quả:
   FAILURE sau 50s, annotation duy nhất "operate: Process completed with
   exit code 1". Logs chi tiết yêu cầu đăng nhập GitHub — writer ngoài
   KHÔNG truy cập được để xác định bước fail cụ thể.

CI đối chứng tại cùng HEAD 02fe9fc: Factory validate #380 SUCCESS,
Factory capacity validate #360 SUCCESS (nền repository xanh).

## Kết luận theo giới hạn repair 3 lần

- Vấn đề "op qa chunk 2/2 fail trước commit" đã dùng hết 3 lượt repair.
- Theo hợp đồng RECOVERY/PROC-PUBLISH: DỪNG, không dispatch lần 4 mù,
  không hạ gate, không tự promote, không claim hàng mới (engine cũng từ
  chối khi còn 10 hàng WRITING).
- Chunk 2/2 giữ nguyên WRITING, draft an toàn trong _drafts/, KHÔNG lộ.

## Resume chính xác cho lần chạy sau

1. Người có quyền truy cập logs (chủ xe) tải log run #135
   (github.com/thuexemayhanoi/blog/actions/runs/36397553131), xác định
   bước fail: (a) preflight validate.py --scope chunk, (b) op qa, hay
   (c) run_reports_checked/validate_or_stop.
2. Sửa nguyên nhân gốc ở đúng chỗ (script hoặc dữ liệu), KHÔNG hạ ngưỡng.
3. Đẩy lại lệnh {"op":"qa","scope":"fast","ids":"BLG-00645..BLG-00654"}
   vào data/factory/operator-command.json; PASS hết mới dispatch publish
   10 bài, sau đó verify CI + Pages trên FINAL HEAD.

## Bài đã xuất bản của cycle BLG-00635..BLG-00654 (chunk 1/2, đã kiểm live)

BLG-00635..BLG-00644: 10/10 PUBLISHED. Kiểm tra live 2026-09-28:
2 URL đại diện 200, hub /blog/an-toan-phap-ly/bien-bao/ 200, sitemap.xml OK.
