# ENGINE RUNBOOK — LENH THUC, KHONG TUONG TUONG

Moi lenh duoi day ung script that trong repository. Khong co
lenh nao chua implement. Chay tu goc repository.

## 1. Preflight (truoc moi RUN / transaction)

- python3 scripts/factory/validate.py
  Kiem nen tang (matrix, taxonomy, hash, lock, checkpoint).
  exit 0 moi duoc tiep tuc.
- python3 scripts/factory/capacity-audit.py
  Kiem mo hinh nang luc 10K (tong phan bo, headroom child).
- python3 scripts/factory/queue.py --stats
  Queue: claimable PLANNED, headroom tung child.
- python3 scripts/factory/queue.py --needs-refill
  exit 0 = can refill; exit 1 = khong can.

## 2. Queue refill (lazy, chi khi can)

- python3 scripts/factory/refill-queue.py --plan
  In claimable, min_ready_queue (100), refill_target (300).
- python3 scripts/factory/refill-queue.py --verify
  Kiem toan bo gate G1-G7 cho ledger refill-candidates.json.
  CI chay lenh nay o moi push (factory-capacity-validate.yml).
- python3 scripts/factory/refill-queue.py --commit --yes
  CHI CHAY KHI OWNER PHE DUYET: merge ledger vao
  data/state/matrix-seed.json. Sau do buoc buoc:
  python3 scripts/factory/generate-matrix.py
  roi commit matrix + seed + bao cao.

Gate G1-G7 (khong ha nguong): child ton tai + headroom;
kw unique trong child; intent unique trong child; slug
unique toan matrix; word_target >= 1.200; candidate_id
unique; child thuoc taxonomy (ke thua source policy).

## 3. Claim

- Doc checkpoint: data/state/checkpoint.json
  (next_claimable_id, in_progress_chunk).
- Claim 3-5 hang PLANNED (toi da 10) theo thu tu id,
  giao batch_id 50 hang/lo (generate-matrix.py gan B001...).
- KHONG restart hang PUBLISHED; KHONG doi trang thai REVIEW.

## 4. Write / QA / Repair

- Viet draft vao _drafts/ (KHONG dung _posts/).
- QA + bang chung SHA: data/qa/<BLG-ID>.json
  (quality >= 90, seo >= 90, business_fact PASS,
  legal PASS hoac NOT_REQUIRED, content_sha256 +
  matrix_row_sha256 khop).
- Repair: QA -> REPAIR -> QA (toi da vai vong; repair rate
  tang bat thuong = dieu kien dung RUN).
- Xem manifest 1 hang: python3 scripts/factory/manifest.py
  --id BLG-00484

## 5. Publish gate

- python3 scripts/factory/publish-gate.py
  Promote PUBLISHED chi qua gate (khoa + hash + lich su
  transaction). KHONG promote tay.

## 6. Checkpoint / commit / CI

- generate-reports.py cap nhat progress.json (CI doi chieu
  vân tay); checkpoint luu last_completed + next_claimable.
- Commit/push, cho CI xanh:
  Factory validate + Factory capacity validate + Pages.

## 7. Resume / pause / recover

- Writer lock: data/state/writer-lock.json (O_EXCL
  data/state/writer-lock.active). Trung khoa = dung RUN.
- Transaction active: phuc hoi truoc khi claim moi
  (xem docs/RECOVERY.md va hop dong quy trinh
  docs/factory-workflow-contract.md muc 5).
- HEAD doi giua RUN: fetch lai, doi chieu truoc khi mutate.

## 8. Stop conditions (dung RUN ngay)

- CI do hoac publish gate tu choi.
- Repair rate tang bat thuong.
- Blocker phap ly (hang source_required=true thieu nguon).
- Trung khoa ghi / HEAD doi bat thuong.
- Chat luong ngu canh giam ro (tu danh gia cua writer).

## 9. Scheduler

- KHONG tao scheduler trong run nay.
- Chi bao READY_FOR_SCHEDULING khi: capacity model PASS,
  refill PASS, claim PASS, lock PASS, transaction recovery
  PASS, QA hash gate PASS, publish gate PASS, CI PASS,
  Pages PASS.
