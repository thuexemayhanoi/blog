# Nhật ký sản xuất — đợt mở lại 2026-10-29

Ảnh chụp do writer ghi tay để bàn giao; số liệu hiện hành LUÔN đọc từ
`data/content-matrix.csv`, `data/state/checkpoint.json`, `reports/factory/progress.json`.

## Phiên làm việc

- Writer: slot **W6**, session `s-claude-opus-w6` (nhãn công khai, không phải credential).
- Quy trình: `writer-session.py begin --slot W6` → viết draft → `check` → `push` (theo cặp) →
  publisher `factory-publish.yml` claim/QA/publish → `confirm`.
- Ngưỡng QA giữ nguyên (quality ≥ 75, seo ≥ 70, business_fact PASS, legal PASS/NOT_REQUIRED,
  không critical); `chunk_size` giữ 2; không sửa bài PUBLISHED, không đổi permalink.

## Kết quả (cập nhật 2026-10-31)

| Mốc | PUBLISHED (matrix) | Ghi chú |
|---|---|---|
| Đầu đợt (2026-10-29) | 5.664 | hàng đợi còn 2 hàng PLANNED |
| 2026-10-31 sau lô 7 | 5.736 | +72 bài: BLG-05709, BLG-05716, BLG-06151 → BLG-06220 |
| 2026-10-31 sau lô 9 | 5.756 | +92 bài: thêm BLG-06221 → BLG-06240 |

Mọi bài đều qua publisher (evidence `data/qa/<ID>.json`); không bài nào publish tay.
Kiểm live: `factory-liveness.yml` (live_audit) run 40995672844 ngày 2026-10-30 — 6.980/6.980 URL
sitemap HTTP 200, 0 liên kết hỏng, 0 soft-404, 0 lỗi canonical, 0 trang mồ côi.

## Refill chủ đề thật (gate G1–G9, không filler)

- `refill-2026-10-29-R29A…R29H.json`: 167 chủ đề → materialize 2026-10-29 (BLG-06151 → BLG-06317).
- `refill-2026-10-29-R29J/K/L.json`: 49 chủ đề (sự kiện mùa đông–Tết 2027, pháp lý–hành chính
  2025–2026, hạ tầng Hà Nội 2026) → STAGED, materialize 2026-10-31 khi claimable < 100
  (refill-request seq 169, commit cdcf930ff; BLG-06318 → BLG-06366).
- `refill-2026-10-30-R30A/B/C.json`: 46 chủ đề (thuê xe/hợp đồng theo BLDS; pháp lý TT 108/72/73, XLVPHC,
  QCVN 41; xe và kỹ năng) → STAGED 2026-10-31 (refill-request seq 170), materialize khi claimable < 100.
  Child đã bão hòa không có ứng viên: C-THUE-GIA, C-THUE-DAT-COC, C-THUE-DOI-TUONG, C-NOI-DO-CONG, C-BAO-HIEM.
- Hai ứng viên bị loại vì buộc phải nêu chính sách/giá chưa duyệt (giữ giấy tờ gốc; giá gửi xe).

## Sửa engine trong đợt (đều qua quality gate xanh)

- `91b2c9d64` phân loại run publisher không có bài (QUEUE_EMPTY / QUEUE_LOW / IDLE_NO_DRAFTS) +
  watchdog báo hàng đợi thấp — tách "xanh vì không có việc" khỏi lỗi pipeline.
- `a2c7100a9` lớp đính chính giá: tiền cọc đứng sau giá tháng không còn bị đọc nhầm là giá thuê.
- `4cd685ba6`, `6672d9b1d` nguyên nhân gốc engine tests timeout (`test_multiwriter_sim` 1500s):
  validate quét liên kết URL đã gỡ trên bytes; QA `intent_unique` loại trước cặp chắc chắn dưới
  ngưỡng bằng cận trên của SequenceMatcher (ngưỡng 0,97 giữ nguyên, kết quả trùng khớp bản cũ).

## Điểm tiếp nối (resume)

1. `git pull --ff-only origin main`; `export FACTORY_WRITER_SESSION=s-claude-opus-w6`;
   `python3 scripts/factory/writer-session.py status` (mục `me`).
2. Lease đang mở lúc ghi: BLG-06241 → BLG-06250 (lô 10). `begin --slot W6` nhận lại đúng lease;
   draft nào đã push vẫn được publisher xử lý.
3. Lô kế tiếp: BLG-06251 trở đi theo thứ tự matrix. Khi claimable PLANNED < 100: đẩy batch chủ đề
   thật mới vào `data/factory/refill-batches/` + bump `data/factory/refill-request.json`.

## Việc chủ website cần xác minh (không chặn sản xuất)

Chính sách cửa hàng chưa có trong `data/business-facts.json` (bài chỉ ghi "hỏi/xác nhận trực tiếp"):
phí trả xe trễ; mũ bảo hiểm/bảo hiểm cho người thuê; giữ giấy tờ tùy thân; độ tuổi và giấy tờ
khi thuê xe 50cc; lịch làm việc quanh Tết Đinh Mùi 2027; giá thuê tuần/tháng xe 50cc.

Chi tiết theo bài (điểm chưa kiểm tại chỗ hoặc nguồn chưa thống nhất):

- BLG-06201/06202: TT 79/2024/TT-BCA đối chiếu theo VBHN 41/VBHN-BCA (đến TT 51/2025); sửa đổi 2026
  chưa đối chiếu; NĐ 156/2024 chỉ đọc qua tóm tắt báo.
- BLG-06203: QCVN 41:2024 khoản 7.2 Điều 7 vẫn chia màu đèn theo câu chữ cũ (trước Luật 118/2025).
- BLG-06204: câu chữ Điều 6 NĐ 238/2026 lấy theo Cục CSGT qua báo (PDF chính thức là bản scan).
- BLG-06205: ví dụ "đường đôi" Nguyễn Văn Cừ, biển tốc độ từng tuyến chưa kiểm tại chỗ.
- BLG-06206: intent matrix ghi phường Hoàng Liệt (tên trước 01/7/2025), bài ghi nay là phường Hoàng
  Mai; điểm quay đầu và chỗ để xe chưa kiểm.
- BLG-06207/06208/06216/06219/06224…: chỗ để xe, lối vào, vị trí đền/đình trong làng chưa kiểm tại chỗ;
  tên phường/xã mới sau sắp xếp 2025 chỉ ghi khi có nguồn.
- BLG-06210: tên xã sau sắp xếp (An Khánh hay Sơn Đồng) chưa thống nhất.
- BLG-06212: chưa có danh sách bãi gửi xe chính thức 2025–2026 của Hà Nội Metro.
- BLG-06213: trường nay gọi bảo tàng là "Bảo tàng Lịch sử và Văn hoá"; bài giữ tiêu đề matrix.
- BLG-06214: địa chỉ số 1 hay số 2 Giang Văn Minh.
- BLG-06215: intent matrix ghi cơ sở Hà Đông 2B Quang Trung (cũ), trang chính thức nay ghi 126 Trần Phú.
- BLG-06217: bài nhắc triển lãm đến 06/12/2026 — lỗi thời sau mốc này.
- BLG-06218, 06223, 06225, 06230, 06237: sự kiện 2027 (Tết phố cổ, đêm 31/12, hội đình Nhật Tân, hội Cổ Loa,
  chợ Ngái) chưa công bố — bài viết theo lệ năm trước, ghi "dự kiến"; ngày âm lịch quy đổi theo lịch 2027.
- BLG-06238, 06239, 06240: phương án giao thông công trường (Vành đai 1, cầu Trần Hưng Đạo hết hạn 30/12/2026,
  cầu Tứ Liên rào đến 30/4/2027) — cần cập nhật khi Sở Xây dựng ra thông báo mới.
- BLG-06227: tiêu đề matrix ghi "chùa Động Linh", đa số nguồn ghi "Đông Linh tự" (bài giải thích cả hai).
- BLG-02150 (đã PUBLISHED): bài nói Honda Wave không có hộc chứa đồ, nhưng Wave RSX có hộc U-box dưới yên theo
  honda.com.vn — nếu chủ duyệt thì sửa qua `revise-published.py` (không sửa tay).
