# Hướng dẫn cho agent ngoài (BLOG FACTORY) — con trỏ tương thích ngược

File này chỉ giữ cho các prompt/agent cũ vẫn mở được đường dẫn `docs/mistral/README.md`. NGUỒN CHUẨN là `AGENTS.md` ở gốc
repository; bản một trang cho AI writer (bất kỳ nhà cung cấp nào, tối đa 3 slot): `docs/AI-WRITER-QUICKSTART.md`. Không dùng file
này như bộ hướng dẫn riêng để tránh hai bộ quy tắc mâu thuẫn.

## Thứ tự đọc

1. `AGENTS.md` (gốc) — hợp đồng vận hành đầy đủ
2. `docs/AI-WRITER-QUICKSTART.md` — vào việc trong 5 phút (nhận slot → viết → check → push → confirm)
3. `README.md`, `docs/CONTENT-FACTORY.md` và các tài liệu `docs/` liên quan

## Ghi chú nền

- Bài mới viết trong `_drafts/` (không deploy) trước khi publisher promote sang `_posts/`; writer KHÔNG tự promote.
- Công cụ writer: `python3 scripts/factory/writer-session.py begin|status|check|push|confirm|release`.
- CI: `quality-gate.yml` (dual-mode), sản xuất: `factory-publish.yml` (docs/factory-workflow-contract.md), audit FULL:
  `factory-publish-verify.yml` (dispatch).
- Xung đột chính sách nội bộ (đặt cọc, phí trễ, bảo hiểm): BLOCKED — `reports/factory/policy-conflicts.md`.
- Validator cũ `scripts/validate-queue.js` chỉ dành cho campaign hanoi-seo-480 (`_queue/NNN-slug.md`); kết quả "skipped" không phải bằng chứng PASS cho `_posts`.

Mọi quy tắc còn lại (gate xuất bản, frontmatter, không đổi URL legacy, không bịa dữ liệu kinh doanh, báo cáo HEAD/build/deploy/runtime) xem `AGENTS.md`.
