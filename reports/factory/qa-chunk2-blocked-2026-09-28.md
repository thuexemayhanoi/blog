# QA chunk 2/2 (BLG-00645..BLG-00654) — đã xử lý xong (bản ghi cập nhật 2026-09-28)

Người ghi: writer ngoài (external AI). File này cập nhật bản ghi trước đó
("BLOCKED sau 3 dispatch fail") — bản ghi đó phản ánh đúng trạng thái tại
khoảng 08:28–09:01 nhưng đã lỗi thời ngay sau đó.

## Diễn biến thực tế (đọc từ repository truth)

- Runs #133/#134/#135 (qa chunk 2/2, head c8abfa1/fe5ee36/02fe9fc) đều
  FAILURE trước commit, KHÔNG mutation nào được ghi. Tại thời điểm phân tích
  (HEAD 02fe9fc) writer ngoài không truy cập được log chi tiết (cần đăng
  nhập GitHub) nên ghi nhận BLOCKED theo giới hạn 3 lượt repair.
- 09:01:56 (d70dd88): writer đã sửa 10 draft chunk 2/2 (internal links,
  keyword placement, descriptions).
- 09:03:24 (2c464be): dispatch qa scope fast.
- 09:04:03 (7747584, factory-operator): op qa THÀNH CÔNG —
  reports/factory/qa-outcome.json: 10/10 PASS (BLG-00645..BLG-00654),
  checkpoint counts pass=10, writing=0; bằng chứng data/qa/<ID>.json đủ.
- Kết luận: lỗi của #133–#135 nằm ở nội dung draft (đã được sửa), KHÔNG
  phải gate/engine; ngưỡng QA giữ nguyên, không có gì bị hạ.

## Bước tiếp theo (cùng commit này)

Dispatch op publish cho 10 hàng PASS BLG-00645..BLG-00654 qua
publish-gate.py (cơ chế promote duy nhất). Sau promote: verify CI
(Factory validate + Factory capacity validate) + Pages trên FINAL HEAD,
kiểm live URL + sitemap.

## Ghi chú hệ thống cần chủ xe xem xét (không tự sửa)

Matrix TẠO MỚI 2026-09-27 sinh slug bị mất ký tự "d" (ví dụ
"vach-ke-uong", "co-bi-khong", "phai-i-the-nao"). Nhất quán giữa
matrix/draft/URL live nên engine không lỗi, nhưng URL công khai khó đọc.
Việc sửa slug = đổi URL = cần quyết định riêng của chủ xe (redirect,
chuẩn hoá slugify, làm mới matrix theo seed đã kiểm chứng).
