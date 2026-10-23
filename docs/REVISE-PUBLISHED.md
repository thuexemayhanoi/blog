# Sửa nội dung bài PUBLISHED có kiểm soát (`revise-published.py`)

Ngày thêm: 2026-10-23 (SEO Master). Công cụ bảo trì LOCAL do người vận hành chạy — không workflow, không cron.

## Vì sao cần

Bài PUBLISHED bị ràng buộc bởi `data/qa/<ID>.json` (`content_sha256`, `matrix_row_sha256`, `source_path`).
Sửa tay một chữ làm evidence lệch hash; sửa tay evidence là cấm (AGENTS.md, quy tắc 9). `reattest-legacy-qa.py`
chỉ phục vụ ca lệch hash do đổi domain (`docs/LEGACY-QA-RE-ATTESTATION-PLAN.md`). Khi nội dung bài **thật sự phải đổi**
(ví dụ giá thuê trong bài khác bảng giá chủ xe, câu lỗi thời), đây là đường GHI duy nhất: sửa nhẹ + chấm lại độc lập + evidence
mới có provenance + sao lưu byte-exact + hoàn tác.

Bài **legacy** (không có `data/qa/<ID>.json`: 473 EXISTING + 10 REVIEW) không bị ràng buộc evidence nên sửa trực tiếp được.

## Điều kiện cho một bài (tool tự kiểm, không có cờ ép)

1. Hàng matrix `PUBLISHED`, `output_path` trong `_posts/`, **evidence nguyên vẹn**: hash khớp byte bài và hàng matrix hiện tại,
   `source_path` đúng, `result = PASS`. Evidence đã lệch (vd. đổi domain) → `EVIDENCE_NOT_INTACT`: đi qua `reattest-legacy-qa.py`
   (cần chủ duyệt) rồi mới sửa nội dung.
2. ID không nằm trong lease writer nào (kể cả hết hạn) và không có draft cùng slug / `article_id`.
3. Chỉ đổi **thân bài** và dòng `description:`. Mọi dòng front matter khác (title, date, permalink, article_id, parent_id,
   child_id, tags…) giữ nguyên từng byte; tập liên kết/Liquid/URL trong thân và số heading theo cấp giữ nguyên; tối đa 60 sửa/bài;
   tổng ký tự đổi ≤ 20% độ dài bài. Muốn đổi title/URL/liên kết: không thuộc công cụ này (đổi hàng matrix + URL cần đường riêng).
4. Chấm lại **độc lập** trên byte ứng viên bằng scorer canonical (`factory-operator.qa_check_one`): PASS, quality ≥ 75,
   seo ≥ 70, business_fact PASS, legal PASS|NOT_REQUIRED, không critical failure — **và** không tiêu chí nào đạt ở bản chưa sửa
   rớt ở bản đã sửa, điểm không thấp hơn. Sàn 75/70 do chính công cụ giữ (không đọc từ repo).
5. `--approval-ref` bắt buộc (ghi vào provenance), cây làm việc sạch (`DIRTY_TREE`), lô ≤ 50 ID, mỗi lô một commit.

## Quy trình một lô

```bash
git pull --ff-only origin main            # cây sạch, đúng HEAD
python3 scripts/factory/revise-published.py plan --patches patches.json --out manifest.json
#   -> manifest: ELIGIBLE / mã từ chối cho từng ID (không ghi gì)
python3 scripts/factory/revise-published.py apply --manifest manifest.json \
        --approval-ref "<tham chiếu chủ duyệt>" --limit 50 --offset 0 --batch-id revise-YYYYMMDD-<tag>-01 --dry-run
python3 scripts/factory/revise-published.py apply ...   (bỏ --dry-run)
python3 scripts/factory/revise-published.py verify --backup reports/qa-audit/revise/<batch>.json
git add _posts data/qa reports/qa-audit/revise && git commit && git push   # PR; Quality gate xác minh lại sao lưu
```

`patches.json` (schema `revise-patches/1`): `{"purpose": "...", "reason": "...", "patches": {"BLG-00123": {"edits":
[{"old": "...", "new": "...", "count": 1}]}}}`. Mỗi `old` phải xuất hiện đúng `count` lần trong byte hiện tại; các sửa không chồng
nhau. Manifest không có hiệu lực pháp lý: `apply` tự kiểm lại từ byte hiện tại và từ chối khi manifest bị sửa/lỗi thời
(`BAD_MANIFEST`, `INPUT_CHANGED_SINCE_PLAN`, `SCORER_CHANGED_SINCE_PLAN`…). Một ID không đạt → cả lô dừng, chưa ghi gì;
`--skip-ineligible` chỉ bỏ qua ID đổi trạng thái sau plan (có báo cáo).

## Kết quả ghi

- `_posts/<file>.md`: đúng byte sau các sửa trong manifest.
- `data/qa/<ID>.json`: đầu ra scorer **mới** + khối `revision` (provenance: hash evidence/bài cũ, hash bài mới, sha256 danh sách sửa,
  người duyệt, mã scorer/facts/taxonomy, chuỗi `history` nếu bài từng bị sửa). `scored_at`/`published_at` giữ mốc lịch sử gốc
  (watchdog đọc chúng như tín hiệu hoạt động); mọi chú thích lịch sử khác (`reattestation`, `post_publish_repair`…) giữ nguyên.
- `reports/qa-audit/revise/<batch>.json`: nguyên văn bài + evidence cũ, sha cũ/mới, danh sách sửa; ghi và đọc lại **trước** khi sửa file nào.
- Không đụng matrix, checkpoint, lease, draft, bài khác. Apply lỗi giữa chừng tự trả mọi ID đã bắt đầu ghi về byte cũ
  (nếu không trả được: `PARTIAL_APPLY_BACKUP_KEPT`, giữ sao lưu, khôi phục bằng `rollback`).

## Xác minh và hoàn tác

- `verify --backup FILE`: hash, provenance, `bài = bài cũ + danh sách sửa`, bất biến front matter/liên kết/heading và chấm lại độc lập
  từng ID (`--no-rescore`: chỉ cấu trúc). Quality gate chạy lệnh này cho mọi sao lưu được **thêm/sửa** trong PR
  (`reports/qa-audit/revise/*.json`).
- `rollback --backup FILE [--ids A,B] [--dry-run]`: khôi phục byte-exact bài + evidence cũ, chỉ khi file còn đúng bản đã ghi
  (không đè thay đổi của người khác).

## Công cụ sinh danh sách sửa giá

`scripts/seo/build-price-patches.py` đọc `_data/pricing.yml`, quét bài bằng `scripts/seo/price_phrases.py` (chỉ kỳ hạn tuần/tháng; cụm
gắn được MỘT xe + MỘT kỳ hạn; câu có phép tính/so sánh và cụm không ràng buộc được **không** tự sửa) và xuất `revise-patches/1`.
Mọi đề xuất phải qua `plan` (chấm lại độc lập) và được người đọc diff trước khi `apply`.
