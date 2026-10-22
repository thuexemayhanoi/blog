#!/usr/bin/env python3
"""SEO Master — kiểm tra phần giới thiệu pillar/hub trước khi ghi vào .md.

Dùng: validate-hub-intros.py <bodies.json> [--apply]
  bodies.json: {"<đường dẫn .md tương đối>": "<thân markdown, không front matter>"}
  --apply    : (chỉ khi mọi kiểm tra PASS) thay phần thân của từng tệp .md, giữ nguyên front matter.

Kiểm tra (fail-closed, mọi lỗi in ra rồi exit 1):
  - khóa là tệp hub/pillar có thật (taxonomy + 7 tệp pillar); không ghi tệp lạ
  - không front matter, không Liquid ({% / {{), không HTML (< >), không H1
  - không chữ số (trừ 50cc/110cc/125cc/09:00/21:00) — không bịa giá, thời hạn, mức phạt, hạng bằng
  - không từ cấm (khuyến mại, hoàn tiền, cam kết, bảo hành, 24/7, top, tốt nhất... ) theo data/business-facts.json forbidden_claims + danh sách thêm
  - liên kết markdown chỉ tới URL nội bộ trong danh sách cho phép (hub/pillar/trang giá/liên hệ); không link ngoài, không link bài
  - độ dài: pillar 220-480 từ, hub con 80-190 từ; >= 2 đoạn
  - có nhắc tên hub (không dấu) ít nhất một lần; không lặp nguyên văn mô tả (description) trong front matter
  - không câu trùng giữa các tệp; độ giống shingle 6-từ giữa hai tệp bất kỳ <= 0.30
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
ALLOWED_DIGITS = re.compile(r"\b(?:50|110|125)\s?cc\b|\b09:00\b|\b21:00\b", re.I)
EXTRA_FORBIDDEN = ["khuyến mại", "khuyến mãi", "ưu đãi", "giảm giá", "24/7", "cam kết", "hoàn tiền", "bảo hành", "tốt nhất",
                   "rẻ nhất", "uy tín nhất", "số 1", "số một", "hàng đầu", "đảm bảo", "miễn phí", "không cọc", "không cần cọc",
                   "top ", "5 sao", "đã phục vụ", "năm kinh nghiệm", "khách hàng hài lòng", "duy nhất"]


def nd(s: str) -> str:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def words(s: str) -> list[str]:
    return re.findall(r"[\wÀ-ỹ]+", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s))


def hub_files() -> dict[str, dict]:
    tax = json.loads((ROOT / "data" / "content-taxonomy.json").read_text(encoding="utf-8"))
    out = {}
    for p in tax["parents"]:
        if p["slug"] == "du-lich":  # trang du-lich.md là trang danh mục legacy dài sẵn, không thay thân
            continue
        out[f"{p['slug']}.md"] = {"kind": "pillar", "title": p["title"], "url": p["hub_url"]}
    pmap = {p["parent_id"]: p for p in tax["parents"]}
    for c in tax["children"]:
        out[f"{pmap[c['parent_id']]['slug']}/{c['slug']}.md"] = {"kind": "hub", "title": c["title"], "url": c["hub_url"]}
    return out


def allowed_links() -> set[str]:
    tax = json.loads((ROOT / "data" / "content-taxonomy.json").read_text(encoding="utf-8"))
    urls = {p["hub_url"] for p in tax["parents"]} | {c["hub_url"] for c in tax["children"]}
    urls |= {"/bang-gia/", "/lien-he/", "/chu-de/", "/gioi-thieu/", "/bang-gia-xe-so/", "/bang-gia-xe-ga/",
             "/bang-gia-xe-50cc/", "/bang-gia-xe-dien/"}
    return urls


def shingles(text: str, n: int = 6) -> set[tuple[str, ...]]:
    w = [x for x in nd(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)).split() if x]
    return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bodies")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--allow-missing", action="store_true", help="không báo lỗi nếu thiếu tệp hub (kiểm một phần)")
    args = ap.parse_args()
    bodies: dict[str, str] = json.loads(Path(args.bodies).read_text(encoding="utf-8"))
    hubs = hub_files()
    allow = allowed_links()
    facts = json.loads((ROOT / "data" / "business-facts.json").read_text(encoding="utf-8"))
    forbidden = [x.lower() for x in EXTRA_FORBIDDEN] + [x.lower() for x in facts.get("forbidden_claims", []) if len(x) < 40]
    errors: list[str] = []

    if not args.allow_missing:
        for k in hubs:
            if k not in bodies:
                errors.append(f"THIẾU thân cho {k}")

    descs = {}
    for k in bodies:
        if k not in hubs:
            errors.append(f"{k}: không phải tệp hub/pillar hợp lệ")
            continue
        f = ROOT / k
        if not f.exists():
            errors.append(f"{k}: tệp không tồn tại")
            continue
        m = FM_RE.match(f.read_text(encoding="utf-8"))
        descs[k] = str((yaml.safe_load(m.group(1)) or {}).get("description", "")) if m else ""

    for k, body in bodies.items():
        if k not in hubs:
            continue
        meta = hubs[k]
        low = body.lower()
        if body.lstrip().startswith("---"):
            errors.append(f"{k}: có front matter")
        if "{%" in body or "{{" in body:
            errors.append(f"{k}: có Liquid")
        if "<" in body or ">" in body:
            errors.append(f"{k}: có HTML/ký tự < >")
        if re.search(r"^#\s", body, re.M):
            errors.append(f"{k}: có H1 (layout đã render H1)")
        stripped = ALLOWED_DIGITS.sub("", body)
        if re.search(r"\d", stripped):
            ctx = re.findall(r".{0,12}\d+.{0,8}", stripped)[:3]
            errors.append(f"{k}: có chữ số ngoài phạm vi cho phép: {ctx}")
        for term in forbidden:
            if term in low:
                errors.append(f"{k}: chứa từ cấm '{term}'")
        for text, url in LINK_RE.findall(body):
            if url not in allow:
                errors.append(f"{k}: liên kết không cho phép: {url}")
        n = len(words(body))
        lo, hi = (220, 480) if meta["kind"] == "pillar" else (80, 190)
        if not lo <= n <= hi:
            errors.append(f"{k}: {n} từ, ngoài khoảng {lo}-{hi}")
        paras = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip() and not p.strip().startswith("#")]
        if len(paras) < 2:
            errors.append(f"{k}: cần >= 2 đoạn")
        if nd(meta["title"]) not in nd(body):
            errors.append(f"{k}: không nhắc tên hub '{meta['title']}'")
        d = descs.get(k, "")
        if d and nd(d) in nd(body):
            errors.append(f"{k}: lặp nguyên văn description")

    # trùng lặp giữa các tệp
    sent_idx: dict[str, str] = {}
    for k, body in bodies.items():
        for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)):
            ns = nd(s)
            if len(ns.split()) >= 8:
                if ns in sent_idx and sent_idx[ns] != k:
                    errors.append(f"câu trùng giữa {k} và {sent_idx[ns]}: '{s[:70]}'")
                sent_idx.setdefault(ns, k)
    sh = {k: shingles(b) for k, b in bodies.items()}
    for a, b in itertools.combinations(sorted(sh), 2):
        if not sh[a] or not sh[b]:
            continue
        j = len(sh[a] & sh[b]) / len(sh[a] | sh[b])
        if j > 0.30:
            errors.append(f"quá giống nhau ({j:.2f}): {a} ~ {b}")

    if errors:
        print(f"FAIL: {len(errors)} lỗi")
        for e in errors[:80]:
            print(" -", e)
        return 1
    tot = sum(len(words(b)) for b in bodies.values())
    print(f"PASS: {len(bodies)} tệp, tổng {tot} từ")
    if args.apply:
        for k, body in bodies.items():
            f = ROOT / k
            raw = f.read_text(encoding="utf-8")
            m = FM_RE.match(raw)
            f.write_text(raw[: m.end()].rstrip("\n") + "\n\n" + body.strip() + "\n", encoding="utf-8")
        print(f"đã ghi thân cho {len(bodies)} tệp (front matter giữ nguyên)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
