# ARCHITECTURE 10K — BLOG CAPACITY FACTORY

Tham khao kien truc: codeappweb/lab (chi lam MAU KIEN TRUC,
khong sao chep noi dung hoac du lieu kinh doanh).

## Nguyen tac cot loi

CAPACITY -> TAXONOMY BUDGETS -> MANIFEST/QUEUE -> CLAIM BATCH
-> VALIDATE INTENT -> WRITE -> QA -> PUBLISH -> NEXT BATCH

Muc tieu 10.000 la NANG LUC ENGINE, khong phai yeu cau tao
10.000 hang de bai viet truoc khi factory "san sang".

## Bon khai niem bat buoc phan biet

- HARD_CAPACITY = 10.000: tran ky thuat.
- EDITORIAL_CAPACITY = 10.000: da phan bo (56 child tong 9.517
  + legacy 483), tin vao data/factory-capacity.json.
- MATERIALIZED_MANIFEST: so luong hang matrix thuc te LUON doc tu
  reports/factory/matrix-report.md (snapshot tai thoi diem ghi
  tai lieu khong duoc coi la chan ly dong thai).
- PUBLISHED = 3 factory (+ 473 legacy song).

Phan con lai 9.058 la UNMATERIALIZED CAPACITY: khoang trong
hop le, KHONG goi la "hang thieu". Mot child co the khai bao
editorial_capacity 300 trong khi moi materialized vai chuc.

## Phan bo editorial capacity

Cong thuc (deterministic, trong data/factory-capacity.json):

- Tong planned_target 56 child = 6.980 (chi tieu da kiem chung).
- child editorial_capacity = floor(target x 9.517 / 6.980).
- Phan du 31 chay theo phan thap phan lon nhat (hoa child_id).
- legacy_allocation = 483 giu rieng. Tong = dung 10.000.

Cum lon nhan nhieu (vi du C-THUE-GIA 300), cum hep nhan it
(C-THUE-DIA-DIEM 95). Khong phan bo deu.

## Manifest / queue layer

- data/content-matrix.csv van la nguon su that duy nhat
  (942 hang, schema v2: cannibalization_key, batch_id,
  audience, location_scope, word_target, legal_risk,
  source_required...).
- KHONG tao article-manifest.jsonl song song (tranh trung lap
  su that). Queue la VIEW: scripts/factory/queue.py
  (--stats, --needs-refill) doc truc tiep tu matrix.
- Moi chu de materialized phai qua gate: intent unique,
  keyword unique, khong trung legacy, khong cannibalization
  sibling, canonical/output_path unique, legal feasible,
  depth feasible (word_target >= 1.200).

## Lazy refill (materialization)

- MIN_READY_QUEUE = 100; REFILL_TARGET = 300.
- Khi claimable PLANNED < 100: sinh candidate den ~300.
- KHONG bao gio sinh 9.000 hang mot luc.
- Candidate staged trong data/state/refill-candidates.json;
  gate G1-G8 kiem boi scripts/factory/refill-queue.py
  --verify (PURE validation, chay trong CI, read-only:
  mac dinh in stdout va KHONG ghi file nao; --report - stdout;
  --report PATH chi ghi dung PATH duoc yeu cau ro rang,
  khong bao gio commit ve main tu CI).
  Candidate bi loai: ghi ro ly do trong phan rejected.
  KHONG ha nguong chat luong de lap day capacity.
- Them: --dry-run (in-memory, cay lam viec khong doi),
  --selftest (9 test tieu cuc va xung dot),
  tests/test_refill_safety.py (Refill lock-safety hardening suite: purity,
  atomic lock, HEAD re-check, cleanup).
- Materialization (refill --refill --yes, operator-only)
  chi chay khi owner phe duyet, trong clone git: doc START_HEAD,
  transaction phai inactive, ACQUIRE KHOA ATOMIC
  O_CREAT|O_EXCL sentinel (cung hop dong publish-gate.py,
  hai writer khong the cung giu khoa), re-check HEAD sau khi
  giu khoa (doi -> nha khoa, STOP, khong auto-merge),
  re-run gate, append vao data/state/matrix-seed.json,
  validate, nha khoa trong finally dam bao;
  generate-matrix.py sinh lai matrix (idempotent, CI kiem).

## Batch / run model

- Mot transaction: 3-5 bai (toi da 10).
- Mot RUN: nhieu transaction; muc tieu mem 20-50 PUBLISHED/run.
- Batch planning: 50 hang/lo, ~200 lo cho 10K; mot lo co the
  materialized mot phan (vi du B037: capacity 50,
  materialized 12, published 7).

## Sitemap 10K

- Hien tai: jekyll-sitemap, 1 file sitemap.xml; URL con thap
  nen KHONG shard som.
- San sang: khi URL >= 1.000, chuyen sang sitemap index +
  sitemaps/articles-NNN.xml (~1.000 URL/shard, du kien
  10 shard tai 10K). Ke hoach in ra boi
  scripts/factory/sitemap-plan.py (CI chay).

## Scale gates (milestone audit day du)

500 -> 1000 -> 2000 -> 5000 -> 10000. Tai moi moc chay audit:
duplicate intent, cannibalization, broken links, sitemap,
indexability, build size, CI duration, Pages deploy,
chat luong noi dung, legal freshness, factory state.
(Kiem tra trong factory-validate.yml + capacity-validate.yml.)

## Cac thanh phan tri tue

- data/factory-capacity.json: mo hinh nang luc.
- scripts/factory/capacity-audit.py: kiem mo hinh vs matrix.
- scripts/factory/queue.py: view queue phia tren matrix.
- scripts/factory/refill-queue.py: lazy refill (plan/verify/
  dry-run/selftest/refill).
- scripts/factory/sitemap-plan.py: du do shard sitemap.
- .github/workflows/factory-capacity-validate.yml: CI read-only
  (contents: read, KHONG commit bao cao ve main) cho toan bo
  tren: capacity audit, queue stats, refill verify + idempotency,
  collision selftest, dry-run sach cay lam viec, sitemap plan.

## So huu production engine (ownership guard)

- .github/workflows/publish-queue.yml + _data/publishing.yml:
  LEGACY-SUPERSEDED, dang enabled: false. Chi la campaign cu
  duoc giu lai lam tai lieu; KHONG duoc bat lai song song voi
  factory 10K. Factory 10K (writer lock + transaction + publish
  gate) la engine duy nhat so huu production.
