# PROJECT STATUS — BLOG 10K CAPACITY FACTORY

Cap nhat: 2026-09-27. Nguon tien do: reports/factory/progress.json
(tu sinh tu du lieu that) + data/state/checkpoint.json.

## Ngu doc trung thuc (BAI BAC, KHONG PHA che)

| Khai niem | Gia tri | Y nghia |
|---|---|---|
| Factory hard capacity | 10.000 | Tran ky thuat cua engine (data/factory-capacity.json) |
| Editorial capacity allocated | 10.000 | Da phan bo het qua 56 child + 483 legacy |
| Materialized validated topics | 942 | Hang matrix that (moi hang mot y dinh rieng) |
| Published (factory) | 3 | Bai da qua publish gate |
| Legacy EXISTING | 473 | Bai cu dang song, giu nguyen URL |
| Legacy REVIEW | 10 | Giu trang thai, khong tu PASS |
| BLOCKED | 1 | BLG-00507 (trung slug legacy) |
| Unmaterialized capacity | 9.058 | KHOANG TRONG HOP LE - khong phai hang thieu |

## Ba cap phai phan biet ro

1. 10K-CAPABLE: engine co tran 10.000 va mo hinh phan bo du.
2. 10K-MATERIALIZED: 942 chu de da sinh + kiem chung (con 9.058
   unmaterialized capacity, se materialize LAZY theo nhu cau).
3. 10K-PUBLISHED: 3 (factory) + 473 (legacy dang song).

## Nguon su that duy nhat

- data/content-matrix.csv: 942 hang = materialized manifest.
- data/factory-capacity.json: mo hinh nang luc va nguong refill.
- data/state/refill-candidates.json: staging ledger cua refill
  (smoke test 2026-09-27: 30 candidate staged, 5 rejected ghi ro).
- KHONG tao bang su that thu hai; queue chi la view
  (scripts/factory/queue.py).

## Trang thai run hien tai

- Batch planning: 50 hang/lo (B001...), ~200 lo cho 10K.
- Claim tiep theo: BLG-00486 (tu checkpoint).
- Queue: 455 PLANNED claimable - chua can refill
  (min_ready_queue 100). Co che refill da duoc chung minh
  bang smoke test va gate CI.
- Scheduler: CHUA tao (dung). READY_FOR_SCHEDULING chi bao khi
  moi gate xanh.
