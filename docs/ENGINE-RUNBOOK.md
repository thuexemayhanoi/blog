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
- python3 scripts/factory/factory-operator.py status
  Trang thai engine (checkpoint/transaction/lock/matrix) cho operator.
  Vong van hanh day du: docs/PROC-PUBLISH.md.
  Ops whitelist: status, prepare-next, qa, publish, recover, requeue,
  verify, refill, reports. Lenh day qua
  data/factory/operator-command.json; workflow factory-operator.yml
  la TAY deterministic (khong AI, khong secret AI, khong cron).

## 2. Queue refill (lazy, chi khi can)

- python3 scripts/factory/refill-queue.py --plan
  In claimable, min_ready_queue (100), refill_target (300).
- python3 scripts/factory/refill-queue.py --verify
  Kiem toan bo gate G1-G8 cho ledger refill-candidates.json.
  PURE VALIDATION: in ket qua ra stdout, KHONG ghi file nao,
  khong ghi ledger/matrix/checkpoint, khong gan ID.
  exit 0 = PASS; khac 0 = gate violation thuc su.
- python3 scripts/factory/refill-queue.py --verify --report -
  In bao cao deterministic ra stdout (CI gan vao
  $GITHUB_STEP_SUMMARY). Khong bao gio commit bao cao tu CI.
- python3 scripts/factory/refill-queue.py --verify --report PATH
  Chi khi operator truyen PATH ro rang: ghi bao cao
  deterministic dung PATH do. KHONG co duong dan mac dinh —
  khong co --report thi khong file nao duoc tao.
- python3 scripts/factory/refill-queue.py --dry-run
  Sinh candidate trong memory (khong ghi): generated/accepted/
  rejected. Cay lam viec KHONG doi sau dry-run.
- python3 scripts/factory/refill-queue.py --selftest
  9 test tieu cuc (dup intent/kw/slug/title, sai child,
  word_target nong, capacity overflow, candidate_id trung).
- python3 scripts/factory/tests/test_refill_safety.py
  Refill lock-safety hardening suite: verify/dry-run purity (hash cay),
  --report PATH dung path, O_EXCL atomic lock, 8 lock
  attempts dong thoi -> 1 thanh cong, transaction guard,
  HEAD mismatch abort, cleanup sau failure/success,
  khong stale sentinel.
- python3 scripts/factory/refill-queue.py --refill --yes
  CHI CHAY KHI OWNER PHE DUYET, trong clone git (can doc
  git HEAD): materialize ledger vao data/state/matrix-seed.json.
  Thu tu: doc START_HEAD; transaction phai inactive; ACQUIRE
  KHOA ATOMIC O_CREAT|O_EXCL sentinel (busy -> tu choi, khong
  mutate); re-check HEAD (doi -> nha khoa, STOP, khong
  auto-merge); re-run gate; mutate seed; validate; NHA KHOA
  trong finally dam bao (moi loi/exception deu nha khoa).
  Sau do buoc buoc:
  python3 scripts/factory/generate-matrix.py
  roi commit matrix + seed + bao cao.
  (--commit --yes van hoat dong nhu alias cu.)

Gate G1-G8 (khong ha nguong): child ton tai + headroom (G1);
kw unique trong child (G2); intent unique trong child (G3);
slug unique toan matrix (G4); canonical + output_path unique (G4b);
word_target >= 1.200 (G5); candidate_id unique (G6);
child thuoc taxonomy, ke thua source policy (G7);
title khong trung toan matrix (G8).

LUU Y CI: workflow factory-capacity-validate.yml la
READ-ONLY (permissions: contents: read), khong bao gio
commit/push ve main. Refill --verify chi in log/step summary.
Thay doi trang thai (matrix, seed, ledger, checkpoint) chi
xay ra qua lenh operator chu dong.

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
