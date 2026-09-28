# DIAG validate.py output (UTC timestamp: 2026-09-28T01:51:23Z)

## validate.py
=== VALIDATE FOUNDATION ===
Taxonomy: 7 parent / 56 child | Inventory: 483 bài legacy | Matrix: CÓ
Trạng thái matrix: {'EXISTING': 473, 'REVIEW': 10, 'PUBLISHED': 130, 'BLOCKED': 1, 'WRITING': 10, 'PLANNED': 318}
KẾT QUẢ: PASS (0 cảnh báo)

validate exit: 0

## factory-operator status
{
  "head": "e0233475bf04e002710d59bd44b3e3ed38587f87",
  "checkpoint": {
    "status": "PARTIAL_BLOCKED",
    "last_completed": "BLG-00614",
    "next_claimable": "BLG-00625",
    "in_progress_chunk": [
      "BLG-00615",
      "BLG-00616",
      "BLG-00617",
      "BLG-00618",
      "BLG-00619",
      "BLG-00620",
      "BLG-00621",
      "BLG-00622",
      "BLG-00623",
      "BLG-00624"
    ]
  },
  "transaction_active": false,
  "lock_held": false,
  "lock_holder": null,
  "matrix_counts": {
    "EXISTING": 473,
    "REVIEW": 10,
    "PUBLISHED": 130,
    "BLOCKED": 1,
    "WRITING": 10,
    "PLANNED": 318
  }
}

## queue stats
=== QUEUE STATS (view over matrix) ===
claimable PLANNED : 318
min_ready_queue    : 100
refill_target      : 300
next refill need   : 0
--- per-child: materialized / editorial capacity ---
C-BAO-DUONG               20 /   191 (con 171)
C-BAO-HIEM                16 /   177 (con 161)
C-BAO-TANG                17 /   123 (con 106)
C-BIEN-BAO                 7 /   136 (con 129)
C-CD-CUOI-TUAN            29 /   177 (con 148)
C-CD-HA-GIANG              6 /   109 (con 103)
C-CD-MAI-CHAU              5 /   109 (con 104)
C-CD-MOC-CHAU              6 /   109 (con 103)
C-CD-NOI-THANH             6 /   136 (con 130)
C-CD-PHO-BAC              19 /   123 (con 104)
C-DIEM-DEN                58 /   232 (con 174)
C-GIAY-TO                 13 /   150 (con 137)
C-GPLX                    11 /   205 (con 194)
C-HD-CHON-XE               7 /   123 (con 116)
C-HD-GIA                   6 /   123 (con 117)
C-HD-NGUOI-MOI            26 /   123 (con 97)
C-HD-PHAP-LY               7 /   123 (con 116)
C-HD-SU-CO                 5 /   123 (con 118)
C-HD-THU-TUC               6 /   123 (con 117)
C-HO-TAY                   8 /   136 (con 128)
C-HONDA-AIR-BLADE          5 /   150 (con 145)
C-HONDA-CLICK              4 /   136 (con 132)
C-HONDA-VISION             6 /   164 (con 158)
C-HONDA-WAVE               6 /   164 (con 158)
C-KY-NANG-CHO-DO          29 /   177 (con 148)
C-KY-NANG-CO-BAN          45 /   245 (con 200)
C-KY-NANG-GUI-XE          26 /   164 (con 138)
C-KY-NANG-SUC-KHOE        30 /   150 (con 120)
C-KY-NANG-THOI-TIET       51 /   204 (con 153)
C-KY-NANG-TINH-HUONG     106 /   245 (con 139)
C-LONG-BIEN                6 /   150 (con 144)
C-NGOAI-THANH              8 /   150 (con 142)
C-NOI-DO-CONG              8 /   164 (con 156)
C-PHAT-NGUOI               8 /   164 (con 156)
C-PHO-CO                  10 /   150 (con 140)
C-QUY-DINH                21 /   204 (con 183)
C-THUE-DAT-COC            10 /   205 (con 195)
C-THUE-DIA-DIEM            9 /    95 (con 86)
C-THUE-DOI-TUONG           8 /   109 (con 101)
C-THUE-GIA                21 /   300 (con 279)
C-THUE-NGAY               18 /   245 (con 227)
C-THUE-NHAN-TRA           32 /   245 (con 213)
C-THUE-QUOC-TE            14 /   191 (con 177)
C-THUE-SU-CO              40 /   245 (con 205)
C-THUE-THANG              18 /   273 (con 255)
C-THUE-THU-TUC            33 /   273 (con 240)
C-THUE-TUAN                7 /   232 (con 225)
C-XE-50CC                  8 /   191 (con 183)
C-XE-DAP-DIEN              7 /   136 (con 129)
C-XE-DIEN                 17 /   218 (con 201)
C-XE-GA                   11 /   218 (con 207)
C-XE-KHAC-PHUC            10 /   123 (con 113)
C-XE-LUA-CHON             10 /   109 (con 99)
C-XE-SO                    9 /   218 (con 209)
C-XE-SO-SANH               9 /   123 (con 114)
C-YAMAHA-SIRIUS            4 /   136 (con 132)

## capacity audit
=== CAPACITY AUDIT ===
hard_capacity          : 10000
editorial allocated    : 10000 (children 9517 + legacy 483)
materialized topics    : 942
unmaterialized capacity: 9058
published (factory)    : 130
legacy existing        : 473
claimable PLANNED      : 318 (min_ready_queue 100)
needs refill           : NO
RESULT: PASS
