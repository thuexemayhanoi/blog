#!/usr/bin/env python3
"""SEO Master — báo cáo ĐỌC-ONLY: giá thuê tuần/tháng trong bài/trang có khớp `_data/pricing.yml` không.

Quét `_posts/*.md` (thân + front matter) và các trang `.md` ở gốc/`thue-xe/` bằng `price_phrases.py` (chỉ kỳ hạn tuần/tháng gắn được
MỘT xe + MỘT kỳ hạn). Không ghi bài, không ghi evidence. Mã thoát 1 khi `--fail-on-mismatch` và còn cụm MISMATCH.

  python3 scripts/seo/check-price-consistency.py [--pricing FILE] [--out reports/factory/seo-master/price-consistency.csv]
                                                 [--fail-on-mismatch]

Cột CSV: path, kind (factory = có data/qa/<ID>.json | legacy | page), status (MISMATCH|REVIEW|UNBOUND_STALE), vehicle, period, text, proposed, disposition.
UNBOUND_STALE = cụm không ràng buộc được xe/kỳ hạn nhưng mang một số tiền không còn nằm trong bảng giá hiện hành (cần người đọc).
disposition (chỉ bài factory): NOTICE_LAYER = bài đang có khối "Giá thuê tham khảo hiện hành" (_data/price-notices.json);
REVIEWED_FALSE_POSITIVE = bài đã đọc tay là dương tính giả (EXCLUDE của build-price-notices.py); rỗng = còn việc phải xử lý.
"""
from __future__ import annotations

import argparse
import collections
import csv
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import price_phrases as pp  # noqa: E402


def retired_amounts(expected) -> set[int]:
    """Số tiền tuần/tháng từng được công bố nhưng không còn là mức hợp lệ cho BẤT KỲ xe nào."""
    valid = set()
    for per_vehicle in expected.values():
        for period in ("week", "month"):
            if period in per_vehicle:
                lo, hi = per_vehicle[period]
                valid.update(range(lo, hi + 1, 50000))
    return {600000, 650000, 800000, 850000, 1400000} - valid


def evidence_paths() -> dict[str, str]:
    """source_path → mã bài của mọi evidence QA."""
    out = {}
    for p in (ROOT / "data/qa").glob("*.json"):
        try:
            out[json.loads(p.read_text(encoding="utf-8")).get("source_path", "")] = p.stem
        except ValueError:
            pass
    return out


def dispositions() -> tuple[set[str], set[str]]:
    """(mã bài đang có khối giá hiện hành, mã bài dương tính giả đã duyệt tay)."""
    notices = set()
    path = ROOT / "_data" / "price-notices.json"
    if path.is_file():
        notices = {v["id"] for v in json.loads(path.read_text(encoding="utf-8")).get("posts", {}).values()}
    spec = importlib.util.spec_from_file_location("build_price_notices", HERE / "build-price-notices.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return notices, set(mod.EXCLUDE)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pricing")
    ap.add_argument("--out")
    ap.add_argument("--fail-on-mismatch", action="store_true")
    a = ap.parse_args()
    expected = pp.load_expected(Path(a.pricing) if a.pricing else None)
    stale = retired_amounts(expected)
    factory = evidence_paths()
    notice_ids, reviewed_fp = dispositions()
    files = sorted((ROOT / "_posts").glob("*.md")) + sorted(p for p in ROOT.glob("*.md")) + sorted((ROOT / "thue-xe").glob("*.md"))
    rows, counts, posts = [], collections.Counter(), collections.defaultdict(set)
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if rel in ("README.md", "AGENTS.md", "CLAUDE.md"):
            continue
        text = path.read_text(encoding="utf-8")
        tm = re.search(r"^title:\s*(.+)$", text, re.M)
        vt = pp.vehicles_in(tm.group(1) if tm else "")
        kind = "page" if not rel.startswith("_posts/") else ("factory" if rel in factory else "legacy")
        for p in pp.scan_text(text, expected, vt[0] if len(vt) == 1 else ""):
            status = p.status
            if status == "UNBOUND" and (p.lo in stale or p.hi in stale):
                status = "UNBOUND_STALE"
            if status not in ("MISMATCH", "REVIEW", "UNBOUND_STALE"):
                continue
            counts[(kind, status)] += 1
            posts[(kind, status)].add(rel)
            post_id = factory.get(rel, "")
            disposition = "NOTICE_LAYER" if post_id in notice_ids else "REVIEWED_FALSE_POSITIVE" if post_id in reviewed_fp else ""
            rows.append({"path": rel, "kind": kind, "status": status, "vehicle": p.vehicle, "period": p.period,
                         "text": p.text, "proposed": p.fix_new, "disposition": disposition})
    summary = {f"{k}/{s}": {"phrases": n, "files": len(posts[(k, s)])} for (k, s), n in sorted(counts.items())}
    by_disposition = collections.Counter({r["path"]: r["disposition"] or "OPEN" for r in rows}.values())
    print(json.dumps({"files_scanned": len(files), "retired_amounts": sorted(stale), "findings": summary,
                      "files_by_disposition": dict(sorted(by_disposition.items()))}, ensure_ascii=False, indent=1))
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["path", "kind", "status", "vehicle", "period", "text", "proposed", "disposition"])
            w.writeheader()
            w.writerows(rows)
    return 1 if a.fail_on_mismatch and any(s == "MISMATCH" for (_, s) in counts) else 0


if __name__ == "__main__":
    sys.exit(main())
