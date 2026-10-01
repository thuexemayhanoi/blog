# ENGINE RUNBOOK — LENH THUC, KHONG TUONG TUONG

Moi lenh duoi day ung script that trong repository. Khong co
lenh nao chua implement. Chay tu goc repository.

## 1. Preflight (truoc moi RUN / transaction)

- python3 scripts/factory/validate.py [--scope chunk|batch|full]
  Kiem nen tang (matrix, taxonomy, hash, lock, checkpoint).
  scope chunk = FAST QA (chi chunk hien tai + nen bat buoc); batch =
  DEEP (khong sitemap live); full (mac dinh) = toan bo + sitemap live.
  exit 0 moi duoc tiep tuc.
- python3 scripts/factory/qa.py --mode fast|deep|full
  QA thu cong 3 muc (docs/PROC-PUBLISH.md "QA modes"). fast = mac dinh
  cho moi chunk 10 bai; KHONG tu chay tiep, KHONG self-dispatch.
- python3 scripts/factory/factory-operator.py release-chunk
  Pause san xuat an toan: tra hang WRITING chua co draft ve PLANNED,
  giu nguyen hang co draft/QA evidence, bao ve PUBLISHED/REVIEW.
- python3 scripts/factory/capacity-audit.py
  Kiem mo hinh nang luc 10K (tong phan bo, headroom child).
- python3 scripts/factory/queue.py --stats
  Queue: claimable PLANNED, headroom tung child.
- python3 scripts/factory/queue.py --needs-refill
  exit 0 = can refill; exit 1 = khong can.
- python3 scripts/factory/factory-operator.py status
  Trang thai engine (checkpoint/transaction/lock/matrix) cho operator.
  Vong van hanh day du: docs/PROC-PUBLISH.md.
  Ops whitelist: status, prepare-next (—ids cho exact-ID claim), qa,
  publish, recover, requeue, verify, refill, reports. TU PHASE 1 san
  xuat CHAY THEO PUSH: writer push draft _drafts/ -> factory-production
  yml tu dong (push-selection.py chon EXACT ID -> prepare-next --ids
  -> qa --ids -> publish --ids --scope fast); workflow_dispatch chi
  con op bao tri status/recover/refill/diagnostics. TU 2026-10-01
  REFILL PUSH-DRIVEN: push _drafts/ HOAC data/factory/refill-
  request.json ma push-selection bao refill_advised (claimable PLANNED
  < chunk_size) va production-control enabled -> workflow TU CHAY op
  refill chuan trong cung lan push. Workflow la TAY
  deterministic (khong AI, khong secret AI, khong cron).

## 2. Queue refill (lazy, chi khi can)

- python3 scripts/factory/refill-queue.py --plan
  In claimable, min_ready_queue (100), refill_target (300).
- python3 scripts/factory/refill-qu
eue.py --verify
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
kw unique trong child (G2); in
tent unique trong child (G3);
slug unique toan matrix (G4); canonical + output_path unique (G4b);
word_target >= 1.200 (G5); candidate_id unique (G6);
child thuoc taxonomy, ke thua source policy (G7);
title khong trung toan matrix (G8).

LUU Y CI: cac workflow read-only la quality-gate.yml (FAST moi push)
va factory-publish-verify.yml (FULL audit theo yeu cau) — khong bao gio
commit/push ve main. Refill --verify chi in log/step summary.
Thay doi trang thai (matrix, seed, ledger, checkpoint) chi
xay ra qua lenh operator chu dong.

## 3. Claim

- Doc checkpoint: data/state/checkpoint.json
  (next_claimable_id, in_progress_chunk).
- Claim 2 hang PLANNED (chunk_size trong data/factory/production-control.json, toi da 10) theo thu tu id,
  giao batch_id 50 hang/lo (generate-matrix.py gan B001...).
- KHONG restart hang PUBLISHED; KHONG doi trang thai REVIEW.

## 4. Write / QA / Repair

- Viet draft vao _drafts/ (KHONG dung _posts/).
- QA + bang chung SHA: data/qa/<BLG-ID>.json
  (quality >= 75, seo >= 70, business_fact PASS,
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
- HEAD doi giua RUN: fetch lai, doi chieu 
truoc khi mutate.

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

- HOP DONG 3 WORKFLOW (2026-09-30, docs/factory-workflow-contract.md):
  khong con workflow dinh ky 30 phut. factory-liveness.yml (cron 6 gio,
  tuan) la duy nhat chay dinh ky — READ-ONLY diagnostics, KHONG phai
  scheduler van hanh: khong mutate state, khong claim, khong publish.
  Van hanh san xuat theo PUSH tren factory-production.yml (draft
  _drafts/ -> duong nong exact-ID; docs/PROC-PUBLISH.md), dispatch
  chi con op bao tri. publish-queue.yml da retire (campaign
  legacy da tat).

## 10. Liveness watchdog (READ-ONLY)

- python3 scripts/factory/watchdog.py
  Kiem tra suc song engine: chi DOC state, khong ghi gi. Chay hang
  khi can trong factory-publish-verify.yml + buoc purity (working tree
  phai sach sau khi chay).

Trang thai (uu tien tu tren xuong; exit 0 = HEALTHY, 1 = can can
thiep, 2 = loi du lieu):

| Trang thai            | Dieu kien                                    | Xu ly |
|-----------------------|--------------------------------------------|-------|
| DEGRADED_STATE_FILES  | state file thieu/hong JSON               | Kiem data/state/* |
| STALE_TXN             | txn active >= 3h                           | operator recover |
| STALE_LOCK            | lock treo >= 2h (BAT KY: con HAY 0 vie do) | RECOVERY.md (khong force-unlock) |
| STALE_CHECKPOINT      | con vie do, checkpoint im lang >= 24h     | Kiem tay + verify |
| STALLED_ACTIVE        | con vie do, khong lock/txn, im lang >= 6h | hoan tat hoac release-chunk |
| HEALTHY_ACTIVE   
     | txn/lock con tuoi                         | Khong lam gi |
| HEALTHY_IDLE          | khong viec do, khong txn/lock             | Khong lam gi |

- BAT KY lock dang giu qua nguong (>= 2h) deu la STALE_LOCK exit 1, KE
  CA khi 0 vie do: factory-operator preflight coi moi lock dang giu
  (locked=true / sentinel writer-lock.active) la "dang chan" va tu choi
  mutation -> lock mo coi stale KHONG phai HEALTHY_IDLE. Watchdog van
  READ-ONLY: khong tu xoa, khong force-unlock — don qua operator chuan
  (RECOVERY.md).
- Nghieng: --lock-stale-hours/--txn-stale-hours/
  --checkpoint-stale-hours/--active-stale-hours/--now (test),
  WATCHDOG_JSON dong doc may.

## 11. Hop dong kiem tra 4 tang

- Tang 1 UNIT: test theo module tren fixture nho — test_watchdog.py,
  test_publish_gate.py, test_operator.py, test_refill_safety.py,
  test_workflow_syntax.py. Nhanh, chay trong verify FAST.
- Tang 2 INTEGRATION: kich ban thao tac that tren ban sao hermetic —
  test_hardening.py (S1-S8c), test_qa_modes.py, test_publish_flow.py,
  test_link_integrity.py, test_refill_semantics.py,
  test_push_rebase_overlap.py. Chay trong DEEP/FULL.
- Tang 3 PRODUCTION INVARIANT: validate.py (chunk/batch/full) +
  CI quality-gate.yml (FAST moi push) + Pages. Gate xuat ban tung
  chunk = FAST; DEEP ~50 bai; FULL chay theo yeu cau (factory-publish-verify.yml).
- Tang 4 LONG-RUN/FAILURE RECOVERY: test_soak_recovery.py — 20 vong
  san xuat hermetic + failure injection (txn treo, reports hong,
  mat file _posts, lock treo, retry idempotent), bat bien moi vong
  (lc exact, counts, history khong trung, production state nguyen ven).
- Phan cap: FAST < DEEP < FULL (FULL = DEEP + test_hardening +
  test_watchdog + test_soak_recovery, 12 suite). KHONG ha nguong,
  KHONG bot kiem tra khi doi muc; nang muc khi phat hien he thong.
