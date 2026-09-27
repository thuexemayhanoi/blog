# Blog Thuê Xe Máy Hà Nội Nguyễn Tú

Jekyll/GitHub Pages. URL: https://thuexemayhanoi.github.io/blog/ · Base URL: `/blog` · Ngôn ngữ công khai: chỉ tiếng Việt. Website doanh nghiệp chính: https://thuexemaynguyentu.com/

Agent làm việc trong repo đọc `AGENTS.md` trước. Tài liệu vận hành đầy đủ nằm trong `docs/`; report trong `reports/factory/`.

## Dữ liệu kinh doanh của blog (giữ nguyên, không đồng bộ từ /shop)

- Thuơng hiệu: Nguyễn Tú — Thuê Xe Máy Hà Nội Nguyễn Tú
- Địa chỉ: 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội
- Điện thoại/Zalo/WhatsApp: 0942 467 674
- Giờ hoạt động: 09:00–21:00
- Bảng giá: `_data/pricing.yml` (nguồn chuẩn), hiển thị qua trang `/bang-gia/`
- Blog và shop là hai bên kinh doanh khác nhau: KHÔNG coi khác biệt dữ liệu giữa hai site là lỗi, KHÔNG đồng bộ.

## Cấu trúc chính

- `_posts/` — 483 bài legacy (URL `/blog/YYYY/MM/DD/slug/`, giữ nguyên). Bài mới cũng phẳng ở đây, permalink theo taxonomy.
- `_drafts/` — vùng nháp KHÔNG deploy; chỉ promote sang `_posts` khi qua đủ gate.
- `thue-xe/`, `xe-may/`, `an-toan-phap-ly/`, `du-lich/`, `cung-duong/`, `ky-nang/`, `hoi-dap/` — trang hub cha và hub con (39 hub con có nội dung).
- `_data/` — cấu hình site + `factory-taxonomy.yml`, `factory-map.yml` (sinh tự động, không sửa tay).
- `data/` — dữ liệu nền factory: taxonomy, inventory, business facts, state (checkpoint/lock/transaction), seed.
- `scripts/factory/` — restore, sinh report, validator, manifest.
- `docs/` — tài liệu vận hành. `docs/mistral/README.md` chỉ trỏ về nguồn chuẩn.
- `reports/factory/` — report sinh từ dữ liệu thật + các báo cáo BLOCKED.
- `.github/workflows/` — `factory-validate.yml` (gate CI), `publish-queue.yml` (campaign cũ hanoi-seo-480, queue hiện rỗng bài).

## Lệnh kiểm tra bắt buộc

```bash
python3 scripts/factory/restore-foundation.py   # idempotent
python3 scripts/factory/generate-reports.py     # idempotent
python3 scripts/factory/validate.py             # 0=PASS 1=FAIL 2=BLOCKED(matrix)
```

Trạng thái hiện tại: nền đã khôi phục (taxonomy 7 cha/51 con, inventory 483 bài legacy, mapping hub hoạt động); ma trận 10.000 hàng BLOCKED — xem `reports/factory/matrix-recovery-blocked.md`. CI factory cố ý đỏ với lý do MATRIX BLOCKED cho tới khi matrix được giải quyết.

## Quy tắc bất di bất dịch

- Không đổi URL legacy, không xóa/đổi tên bài, không noindex hàng loạt.
- Không bịa khuyến mại, phí giao cố định, số lượng khách, số năm kinh nghiệm, xếp hạng, cam kết, 24/7.
- Không hạ gate để PASS; không ghi kết quả khi chưa chạy thật (NOT VERIFIED nếu chưa kiểm tra).
- Hoàn thành một sửa lỗi phải có: tệp nguồn thay đổi, commit mới, Pages build + deploy thành công, kiểm tra runtime (mobile ~390px gồm menu/calculator/chatbot/footer).
