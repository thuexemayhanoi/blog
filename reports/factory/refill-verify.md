# Refill verify report (tu dong, khong sua tay)

Sinh boi scripts/factory/refill-queue.py --verify. Deterministic: chi phu thuoc matrix + ledger + capacity.
CI chi IN bao cao (stdout/summary) - KHONG BAO GIO commit bao cao.

- Candidates staged: 29
- Rejected recorded: 6
- Gate violations: 0
- RESULT: PASS

## Gate violations

- (khong co)

## Candidates staged

| candidate | child | kw | word |
|---|---|---|---|
| CAND-2026-001-001 | C-THUE-GIA | giá thuê xe máy tết hà nội | 1400 |
| CAND-2026-001-002 | C-THUE-THU-TUC | thuê xe máy không cần đặt cọc | 1300 |
| CAND-2026-001-003 | C-THUE-QUOC-TE | giấy tờ thuê xe máy cho khách quốc tế | 1400 |
| CAND-2026-001-004 | C-THUE-SU-CO | xe thuê bị thủng lốp xử lý | 1200 |
| CAND-2026-001-005 | C-XE-DIEN | xe máy điện chạy được bao xa | 1300 |
| CAND-2026-001-006 | C-HONDA-WAVE | chạy honda wave đường đèo | 1400 |
| CAND-2026-001-007 | C-BAO-DUONG | chăm ắc quy xe máy mùa đông | 1300 |
| CAND-2026-001-008 | C-BAO-HIEM | bảo hiểm tự nguyện xe máy va chạm | 1400 |
| CAND-2026-001-009 | C-PHAT-NGUOI | tra phạt nguội xe máy thuê | 1200 |
| CAND-2026-001-010 | C-DIEM-DEN | vòng hồ gươm buổi sáng | 1200 |
| CAND-2026-001-011 | C-BAO-TANG | bảo tàng dân tộc học đi xe máy | 1300 |
| CAND-2026-001-012 | C-HO-TAY | chạy xe quanh hồ tây | 1300 |
| CAND-2026-001-013 | C-LONG-BIEN | đi xe máy qua cầu long biên | 1200 |
| CAND-2026-001-014 | C-CD-CUOI-TUAN | phượt tràng an bằng xe máy | 1400 |
| CAND-2026-001-015 | C-CD-CUOI-TUAN | chạy xe máy đi chùa hương | 1400 |
| CAND-2026-001-016 | C-CD-MAI-CHAU | hà nội mai châu mùa lúa chín | 1400 |
| CAND-2026-001-017 | C-KY-NANG-TINH-HUONG | gặp đoàn rước trên đường | 1200 |
| CAND-2026-001-018 | C-KY-NANG-THOI-TIET | chạy xe máy khi mưa lớn | 1300 |
| CAND-2026-001-019 | C-KY-NANG-CHO-DO | chở hàng nặng trên xe máy | 1200 |
| CAND-2026-001-020 | C-KY-NANG-GUI-XE | gửi xe qua đêm phố cổ hà nội | 1200 |
| CAND-2026-001-021 | C-HD-GIA | thuê xe máy 3 ngày giá | 1200 |
| CAND-2026-001-022 | C-HD-THU-TUC | thuê xe máy cần hộ chiếu không | 1200 |
| CAND-2026-001-023 | C-HD-PHAP-LY | đi xe thuê không giấy phép lái xe | 1400 |
| CAND-2026-001-024 | C-HD-CHON-XE | thuê vision hay air blade | 1300 |
| CAND-2026-001-025 | C-HD-SU-CO | xe thuê mất chìa khóa | 1200 |
| CAND-2026-001-026 | C-HD-NGUOI-MOI | lần đầu thuê xe máy hà nội | 1200 |
| CAND-2026-001-027 | C-THUE-DOI-TUONG | thuê xe máy cho người lớn tuổi | 1300 |
| CAND-2026-001-029 | C-XE-KHAC-PHUC | xe thuê chết máy giữa đường | 1300 |
| CAND-2026-001-030 | C-XE-SO-SANH | so sánh sirius và wave | 1300 |

## Rejected (ghi lai ly do)

| candidate | ly do |
|---|---|
| CAND-2026-001-R01 | DUPLICATE_PRIMARY_KEYWORD: kw chuan hoa trung voi hang seed 'bang gia thue xe may ha noi' trong C-THUE-GIA |
| CAND-2026-001-R02 | DUPLICATE_INTENT: trung intent 'xem gia thue xe may theo ngay' voi hang seed cung child |
| CAND-2026-001-R03 | LEGACY_OVERLAP: trung slug voi bai legacy 'checklist-kiem-tra-xe-khi-nhan-xe-thue' |
| CAND-2026-001-R04 | DEPTH_FEASIBILITY: word_target 800 < 1200, khong du do sau noi dung |
| CAND-2026-001-R05 | WRONG_CLUSTER: chu de thuoc C-PHAT-NGUOI, dat sai child nen loai bo |
| CAND-2026-001-028 | DUPLICATE_PRIMARY_KEYWORD: kw "thuê xe máy gần ga hà nội" trùng BLG-00905 (cạnh tranh cùng ý định trong C-THUE-DIA-DIEM) — gate G2 từ chối đúng, loại candidate. |
