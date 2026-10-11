# Blog Thuê Xe Máy Hà Nội Nguyễn Tú

Jekyll/GitHub Pages. URL: https://blog.thuexemaynguyentu.com/ · Base URL: `/` (custom-domain root) · Ngôn ngữ công khai: chỉ tiếng Việt. Website doanh nghiệp chính: https://thuexemaynguyentu.com/

Agent làm việc trong repo đọc `AGENTS.md` TRƯỚC. Tài liệu vận hành chuẩn nằm trong `docs/` (bản đồ tài liệu ở cuối file này); report sinh từ dữ liệu thật trong `reports/factory/`.

## Repo /blog là gì

Blog nội dung SEO cho dịch vụ cho thuê xe máy tại Hà Nội, tách biệt với website kinh doanh chính. Chạy trên Jekyll, deploy bằng GitHub Pages, nội dung tiếng Việt 100%, kiến trúc hub theo taxonomy 7 nhóm cha. Phần vận hành dài hạn là một Content Factory: sinh chủ đề, viết, QA, promote qua publish gate, xuất bản có checkpoint.

## Kiến trúc & khái niệm 10K

- Content Factory hỗ trợ TỐI ĐA 10.000 bài hợp lệ (HARD CAPACITY — trần kỹ thuật). Quyết định chủ xe 2026-09-27: 10.000 bài hợp lệ PUBLISHED là CHỈ TIÊU sản xuất của một chiến dịch liên tục — không đệm, không hạ gate, đạt bằng chủ đề hợp lệ qua gate mở rộng.
- Chủ đề mở rộng LAZY: chỉ sinh candidate khi queue PLANNED tụt dưới ngưỡng, và chỉ nhận chủ đề có ý định tìm kiếm thật, qua các gate chống trùng (G1–G8). Chi tiết kiến trúc: `docs/ARCHITECTURE-10K.md`; chính sách biên tập/scale: `docs/CONTENT-POLICY-10K.md`.
- Bài xuất bản qua publish gate (quality ≥ 75, seo ≥ 70, business fact + legal PASS, hash bằng chứng khớp; điểm 90+ là EXCELLENT, không phải ngưỡng bắt buộc). Chi tiết: `docs/CONTENT-FACTORY.md`, `docs/QUALITY-RUBRIC.md`.

## Trạng thái động (dynamic state) — đọc tại nguồn, KHÔNG tin số trong prose docs

Số liệu matrix/queue/checkpoint thay đổi theo từng lần chạy. Tài liệu tĩnh (README, docs) KHÔNG hardcode các con số này. Luôn đọc trực tiếp:

- `data/state/checkpoint.json` — điểm resume, counts theo trạng thái.
- `data/state/transaction.json` + `data/state/writer-lock.json` — transaction và ownership-safe writer lock.
- `reports/factory/progress.json` — vân tay dữ liệu (data_fingerprint, matrix_sha256...).
- `reports/factory/matrix-report.md` — báo cáo năng lực matrix hiện hành (HARD_CAPACITY, EDITORIAL_TARGET, CURRENT_VALID_ROWS...).
- `reports/factory/latest.md` — nhật ký chạy gần n
hất.

## Dữ liệu kinh doanh (business facts) — nguồn chuẩn duy nhất

- `_data/business.yml`, `_data/pricing.yml` → kết xuất `data/business-facts.json`. Mọi con số trong bài phải truy về đây.
- Thương hiệu: Nguyễn Tú — Thuê Xe Máy Hà Nội Nguyễn Tú · 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội · 0942 467 674 · 09:00–21:00.
- Blog và `/shop` là hai bên kinh doanh khác nhau: khác biệt dữ liệu giữa hai site KHÔNG phải lỗi, KHÔNG đồng bộ.

## Cấu trúc chính

- `_posts/` — bài đã xuất bản (legacy giữ URL `/YYYY/MM/DD/slug/` nguyên vĩnh viễn; bài mới phẳng, permalink theo taxonomy).
- `_drafts/` — vùng nháp KHÔNG deploy; chỉ promote qua `scripts/factory/publish-gate.py`.
- `thue-xe/`, `xe-may/`, `an-toan-phap-ly/`, `du-lich/`, `cung-duong/`, `ky-nang/`, `hoi-dap/` — trang hub cha/hub con.
- `_data/` — cấu hình site + `factory-taxonomy.yml`, `factory-map.yml` (sinh tự động, không sửa tay).
- `data/` — taxonomy, inventory, business facts, matrix, state (checkpoint/lock/transaction), seed.
- `scripts/factory/` — công cụ factory; `docs/ENGINE-RUNBOOK.md` là danh mục lệnh chuẩn.
- `reports/factory/` — report sinh từ dữ liệu thật.
- `.github/workflows/` — production dùng `factory-publish.yml` (tối đa 10 draft/push, pair 2), `factory-refill.yml` (stage + materialize candidate), `quality-gate.yml` (CI FAST/FULL), `factory-publish-verify.yml` và các workflow kiểm tra/bảo trì theo `docs/factory-workflow-contract.md`. GitHub Pages deploy qua cơ chế của GitHub; không tạo publisher thứ hai.

## Mô hình vận hành factory (docs/PROC-PUBLISH.md)

EXTERNAL AI (writer/coordinator, chỉ cần GitHub read/write) → push draft `_drafts/` (2..10 ID/push) → `factory-publish.yml` tự chạy đường nóng (selection EXACT ID → pair 2 → claim/QA/publish — KHÔNG AI, KHÔNG secret AI, KHÔNG cron sản xuất) → `scripts/factory/factory-operator.py` → engine chuẩn (writer lock + transaction + checkpoint + publish-gate.py + refill-queue.py + matrix + QA evidence). Actions là deterministic hands; external AI là writer duy nhất; engine là nguồn sự thật duy nhất; không có cron — chạy theo lệnh.

## Chế độ viết nhanh có kiểm soát

- Hướng dẫn cho AI writer: [`docs/TURBO-WRITER-RUNBOOK.md`](docs/TURBO-WRITER-RUNBOOK.md). Mặc định gom tới 10 draft/push khi đủ hàng hợp lệ, publisher xử lý pair 2 và giữ nguyên QA. Refill chủ đề trước khi hết queue, không bịa nội dung để đạt số lượng.

## Lệnh kiểm tra cốt lõi (danh mục đầy đủ: docs/ENGINE-RUNBOOK.md)

```bash
python3 scripts/factory/validate.py             # 0=PASS 1=FAIL 2=BLOCKED
python3 scripts/factory/capacity-audit.py       # audit mo hinh nang luc
python3 scripts/factory/queue.py --stats        # queue (view tren matrix)
python3 scripts/factory/refill-queue.py --verify  # gate refill G1-G8 (read-only)
```

## Quy tắc bất di bất dịch (bản đầy đủ: AGENTS.md)

- Không đổi URL legacy, không xóa/đổi tên bài, không noindex hàng loạt.
- Không bịa khuyến mại, phí giao cố định, số lượng khách, số năm kinh nghiệm, xếp hạng, cam kết, 24/7.
- Không hạ gate/QA để PASS; không ghi kết quả khi chưa chạy thật.
- Hoàn thành một sửa lỗi phải có: tệp nguồn thay đổi, commit mới, Pages build + deploy thành công, kiểm tra runtime (mobile ~390px: menu/calculator/chatbot/footer).

## Bản đồ tài liệu chuẩn (mỗi mối quan tâm MỘT chủ sở hữu)

| Tài liệu | Sở hữu |
|---|---|
| `AGENTS.md` | hợp đồng bắt buộc cho mọi agent tự trị |
| `docs/ARCHITECTURE-10K.md` | kiến trúc/năng lực/mở rộng lazy |
| `docs/CONTENT-FACTORY.md` | state machine end-to-end |
| `docs/ARTICLE-RULES.md` | quy tắc dựng bài |
| `docs/CONTENT-POLICY-10K.md` | chính sách biên tập/scale/chống trùng |
| `docs/QUALITY-RUBRIC.md` | hợp đồng chấm QA |
| `docs/ENGINE-RUNBOOK.md` | lệnh thực thi/operator |
| `docs/TURBO-WRITER-RUNBOOK.md` | giao thức 10 draft/push, preflight/refill/multi-writer cho AI ngoài |
| `docs/RECOVERY.md` | crash/lỗi/phục hồi/resume |
| `docs/SOURCE-RESEARCH.md` | chính sách nghiên cứu/nguồn (A/B/C) |
| `docs/INTERNAL-LINKING.md` | chính sách liên kết nội bộ/reverse-link |
| `docs/factory-workflow-contract.md` | hợp đồng scheduler/run/chunk |
| `docs/PROC-PUBLISH.md` | vòng vận hành factory-operator (writer ngoài + Actions) |
| `docs/TAXONOMY.md` | cấu trúc chủ đề |
