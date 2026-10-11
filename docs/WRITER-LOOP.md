# Writer Loop — driver đọc/QA tương thích ngược (provider-neutral)

Driver: `scripts/factory/writer-loop.py`. Với đa-writer (slot W1/W2/W3, phiên độc lập, CAS push) dùng
**`scripts/factory/writer-session.py`** — xem `docs/AI-WRITER-QUICKSTART.md`. `writer-loop.py` giữ các lệnh đọc/QA
tương thích ngược, KHÔNG sửa engine, KHÔNG hạ gate.

## Lệnh

```
python3 scripts/factory/writer-loop.py status
    # counts, claimable_planned, needs_refill, unfinished_ids, leases (đã prune trong bộ nhớ),
    # expired_leases, slots (session/epoch/hạn/ID in-flight), registry_error, next_pairs — read-only
python3 scripts/factory/writer-loop.py next --writer Wn --count N
    # claim lease qua writer-claim.py (Wn mặc định W1 hoặc env FACTORY_WRITER_SLOT) + in chi tiết hàng để viết draft
python3 scripts/factory/writer-loop.py qa --ids BLG-xxx,BLG-yyy
    # pre-check bằng CHÍNH scorer + CHÍNH whitelist giá của publisher (factory-operator.qa_check_one);
    # read-only, KHÔNG ghi evidence; exit 0 + "WRITER_QA PASS" mới được push
python3 scripts/factory/writer-loop.py verify --ids BLG-xxx,BLG-yyy
    # hậu kiểm sau khi fetch main: PUBLISHED + checkpoint + txn inactive + lock free + queue report không fatal
python3 scripts/factory/writer-loop.py release --writer Wn --ids BLG-xxx,BLG-yyy
```

## Bất biến

- Writer KHÔNG PHẢI publisher: chỉ ghi draft của ID mình giữ, registry (qua tool) và batch refill.
  Registry `data/state/writer-claims.json` nằm NGOÀI filter của factory-publish.yml nên một mình nó KHÔNG kích production run.
- KHÔNG force push, KHÔNG PR; luôn fetch fresh main trước batch mới.
- Registry self-heal: ID đã publish tự bị prune; hàng in-flight (REPAIR/PASS...) VẪN thuộc lease chủ cho tới khi PUBLISHED.
- Một slot một phiên: hai AI không dùng chung slot (SLOT_HELD); lease hết hạn thì AI khác nhận.

## Refill

`status.needs_refill = true` (claimable PLANNED < 100) → quy trình trong `docs/CONTINUOUS-WRITER.md` mục Refill
(push batch `data/factory/refill-batches/*.json` + bump `refill-request.json`; workflow tự stage G1–G8 và materialize).

## Điểm dừng hợp lệ

Pair fail content là RECOVERABLE (sửa đúng draft, push lại). Chỉ dừng khi hết hàng PLANNED hợp lệ + hết capacity, blocker thật
ngoài quyền, hoặc runtime/quota hết — khi dừng: push phần xong, ghi `slot + session id` để bàn giao, không bỏ draft dở.

## Test

`python3 scripts/factory/tests/test_writer_loop.py` — status read-only, qa fail-closed thiếu draft và dùng cùng whitelist giá
với publisher, verify PASS/FAIL đúng chiều, next/release claim-nhả lease deterministic, không đụng matrix/checkpoint.
