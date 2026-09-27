# CONTENT POLICY 10K — NGON NGU NANG LUC VA RANG BUOC NOI DUNG

Chinh sach nay KHONG thay the cac tai lieu hien co; no giai
thich ngon ngu nang luc va rang buoc khi scale len 10.000.

## 1. Ngon ngu trung thuc ve nang luc (BAT BUOC)

- NOI DUNG mau (doc so lieu tai moi lan noi): "Factory hard
  capacity: 10.000; Editorial capacity allocated: 10.000;
  Materialized validated topics: <doc tu
  reports/factory/matrix-report.md>; Published: <doc tu
  reports/factory/matrix-report.md>." KHONG hardcode so dong vao
  tai lieu tinh; doc dong nay la vi du mau, con so thuc luon doc
  tu bao cao sinh tu dong.
- CAM noi: "10.000 article matrix complete" hoac bat ky cau nao
  ngam 10.000 chu de da ton tai. Phan chua materialized la
  UNMATERIALIZED CAPACITY, khong phai "missing rows".
- QUYET DINH CHU XE 2026-09-27: 10.000 bai HOP LE PUBLISHED la CHI
  TIEU san xuat (target), khong chi tran ky thuat. Chi bai qua du
  gate moi dem vao chi tieu; khong ha gate, khong dem bai dem.
  Het hang PLANNED hop le -> mo rong vu tru chu de qua gate G1-G8.
- Mot child co editorial_capacity 300 va moi materialized
  vai chuc bai la BINH THUONG. Capacity khong bang noi dung.

## 2. Khong dem, khong lap day

- Moi hang matrix phai la mot y dinh tim kiem that rieng.
  CAM sinh hang bang hoan vi vai tu; CAM dem hang rong cho
  du chi tieu. Refill gate tu choi candidate trung y dinh,
  trung tu khoa, trung slug, cannibalization sibling.
- Candidate bi loai bo duoc ghi ro ly do trong
  data/state/refill-candidates.json (phan rejected).
- CI validation la READ-ONLY (contents: read): khong commit
  bao cao ve main, khong doi matrix/seed/checkpoint/lock.
  Materialization (refill --refill --yes) chi la lenh
  operator chu dong, sau khi kiem writer lock + transaction.

## 3. Su that kinh doanh

- Chi dung du lieu trong /blog (_data/business.yml,
  _data/pricing.yml, tai lieu duoc duyet). CAM nhap gia,
  so dien thoai, dia chi tu /shop hoac nguon khac.
- Ba van de chua chot (tien coc cu the, phi tra tre,
  bao hiem): "Lien he de xac nhan." CAM bia khuyen mai,
  con so khach hang, cam ket, ho tro 24/7.
- Model chua duyet gia: dung cu phap chuan
  "lien he de xac nhan gia hien tai".

## 4. Phap ly va nguon

- Hang source_required=true phai doi chieu nguon chinh thong
  khi
 viet; khong co nguong -> REVIEW/BLOCKED, KHONG bia
  muc phat hien hanh.
- Khong keu khong vi pham luat giao thong Viet Nam.
- Child phap ly ke thua source policy tu taxonomy; refill
  KHONG tu mo cluster phap ly moi.

## 5. Chat luong va do sau

- word_target >= 1.200 moi candidate (gate G5).
- QA evidence: quality >= 90, seo >= 90, business_fact PASS,
  legal PASS hoac NOT_REQUIRED; SHA hash khop
  (xem docs/factory-workflow-contract.md muc 6).
- Khong ha nguong de chay nhanh hoac lap day capacity.

## 6. Lien ket va SEO

- Lien ket noi bo theo canonical: docs/INTERNAL-LINKING.md
  (3-5 lien ket ngu canh moi bai: child hub -> parent hub ->
  bai cung cum; thuc hien TRONG luc viet bai). Breadcrumb/TOC/
  related/footer khong tinh.
- Nghien cuu nguon khi viet: docs/SOURCE-RESEARCH.md
  (3 lop: tinh / hien tai dia diem / phap ly).
- Khong do 10.000 link vao menu/footer; dieu huong cong khai
  theo hub + phan trang (xem factory-workflow-contract.md
  muc 10).
- SEO ownership: xem docs/SEO-OWNERSHIP.md; quy tac bai viet:
  docs/ARTICLE-RULES.md; rubric: docs/QUALITY-RUBRIC.md.

## 7. Scale gates audit

Tai moi moc 500 / 1.000 / 2.000 / 5.000 / 10.000 chay audit
day du (duplicate, cannibalization, broken links, sitemap,
indexability, build size, CI duration, Pages, chat luong,
legal freshness, factory state). Khong cho do bai 10.000 moi
phat hien van de kien truc.
