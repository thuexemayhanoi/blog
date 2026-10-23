#!/usr/bin/env python3
"""SEO Master — báo cáo ĐỌC-ONLY: giá thuê tuần/tháng trong bài/trang có khớp `_data/pricing.yml` không.

Quét `_posts/*.md` (thân + front matter) và các trang `.md` ở gốc/`thue-xe/` bằng `price_phrases.py` (chỉ kỳ hạn tuần/tháng gắn được
MỘT xe + MỘT kỳ hạn). Không ghi bài, không ghi evidence. Mã thoát 1 khi `--fail-on-mismatch` và còn cụm MISMATCH.

  python3 scripts/seo/check-price-consistency.py [--pricing FILE] [--out reports/factory/seo-master/price-consistency.csv]
                                                 [--fail-on-mismatch]

Cột CSV: path, kind (factory = có data/qa/<ID>.json | legacy | page), status (MISMATCH|REVIEW|UNBOUND_STALE), vehicle, period, text, proposed.
UNBOUND_STALE = cụm không ràng buộc được xe/kỳ hạn nhưng mang một số tiền không còn nằm trong bảng giá hiện hành (cần người đọc).
"""
from __future__ import annotations

import argparse
import collections
import csv
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


def evidence_paths() -> set[str]:
    out = set()
    for p in (ROOT / "data/qa").glob("*.json"):
        try:
            out.add(json.loads(p.read_text(encoding="utf-8")).get("source_path", ""))
        except ValueError:
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pricing")
    ap.add_argument("--out")
    ap.add_argument("--fail-on-mismatch", action="store_true")
    a = ap.parse_args()
    expected = pp.load_expected(Path(a.pricing) if a.pricing else None)
    stale = retired_amounts(expected)
    factory = evidence_paths()
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
            rows.append({"path": rel, "kind": kind, "status": status, "vehicle": p.vehicle, "period": p.period,
                         "text": p.text, "proposed": p.fix_new})
    summary = {f"{k}/{s}": {"phrases": n, "files": len(posts[(k, s)])} for (k, s), n in sorted(counts.items())}
    print(json.dumps({"files_scanned": len(files), "retired_amounts": sorted(stale), "findings": summary}, ensure_ascii=False, indent=1))
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["path", "kind", "status", "vehicle", "period", "text", "proposed"])
            w.writeheader()
            w.writerows(rows)
    return 1 if a.fail_on_mismatch and any(s == "MISMATCH" for (_, s) in counts) else 0


if __name__ == "__main__":
    sys.exit(main())
