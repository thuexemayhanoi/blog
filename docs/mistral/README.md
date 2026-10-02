# Hướng dẫn cho agent Mistral (BLOG FACTORY)

File này là tương thích ngược. NGUỒN CHUẨN hiện tại là `AGENTS.md` ở gốc repository — đọc file đó trước. Không dùng file này như bộ hướng dẫn riêng để tránh hai bộ quy tắc mâu thuẫn.

## Thứ tự đọc

1. `AGENTS.md` (gốc) — hợp đồng vận hành đầy đủ
2. `README.md`
3. `docs/CONTENT-FACTORY.md` và các tài liệu `docs/` liên quan

## Thay đổi quan trọng so với bản cũ của file này

- Ma trận 10.000 hàng: BLOCKED (chưa từng được commit, không khôi phục được). KHÔNG tạo ma trận mới rồi gọi là khôi phục. Chi tiết: `reports/factory/matrix-recovery-blocked.md`.
- `data/content-taxonomy.json` và `data/content-inventory.csv` đã khôi phục từ seed bằng `scripts/factory/restore-foundation.py`.
- Bài mới viết trong `_drafts/` (không deploy) trước khi promote sang `_posts/`.
- CI: `.github/workflows/quality-gate.yml` (FAST mọi push/PR). Audit FULL: `factory-publish-verify.yml` (dispatch); liveness 6h: `factory-liveness.yml`. Sản xuất: `factory-publish.yml` (docs/factory-workflow-contract.md).
- Xung đột chính sách nội bộ (đặt cọc, phí trễ, bảo hiểm): BLOCKED — `reports/factory/policy-conflicts.md`.
- Validator cũ `scripts/validate-queue.js` chỉ dành cho campaign hanoi-seo-480 (`_queue/NNN-slug.md`); kết quả "skipped" không phải bằng chứng PASS cho `_posts`.

Mọi quy tắc còn lại (gate xuất bản, frontmatter, không đổi URL legacy, không bịa dữ liệu kinh doanh, báo cáo HEAD/build/deploy/runtime) xem `AGENTS.md`.
