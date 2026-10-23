"""SEO Master — nhận diện cụm giá thuê (xe + kỳ hạn + số tiền) trong văn bản và đối chiếu với `_data/pricing.yml`.

Dùng cho `check-price-consistency.py` (báo cáo) và công cụ sửa giá có kiểm soát. KHÔNG bịa giá: giá đúng luôn lấy từ pricing.yml.
Chỉ ràng buộc (bind) khi chắc chắn: cụm giá phải gắn được với MỘT xe (nhắc gần nhất phía trước trong cùng câu/dòng/hàng bảng,
hoặc xe duy nhất của câu trước) và MỘT kỳ hạn (ngày/tuần/tháng sát số tiền, hoặc cột của bảng). Cụm không ràng buộc được
=> UNBOUND, để người xem; không bao giờ tự sửa.

Phạm vi sửa: chỉ kỳ hạn TUẦN và THÁNG (giá ngày không đổi; số tiền đứng cạnh chữ "ngày" thường là phép tính hoặc chênh lệch,
ví dụ "7 ngày = 1.400.000đ", "rẻ hơn 50.000đ mỗi ngày", nên không bao giờ bị coi là giá thuê để sửa).
Cụm nằm trong câu có dấu hiệu phép tính / so sánh / ví dụ số học (REVIEW_CUES) có status REVIEW: không tự sửa, người phải đọc.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

VEHICLES = (
    ("wave", re.compile(r"\bWave\b", re.I)),
    ("vision", re.compile(r"\bVision\b", re.I)),
    ("airblade", re.compile(r"\bAir\s?Blade\b", re.I)),
    ("click", re.compile(r"\bClick\b|\bMio\b", re.I)),
)
YAML_ID = {"wave": "honda-wave", "vision": "honda-vision", "airblade": "honda-airblade", "click": "honda-click"}

NUM = r"\d{1,3}(?:\.\d{3})+"
UNIT = r"(?:\s?(?:đồng|đ|VND|vnđ|₫)(?![\wÀ-ỹ]))?"
SEP = r"(?:\s*[–—-]\s*|\s+(?:đến|tới)\s+)"
PHRASE = re.compile(rf"(?<![\d.])(?P<a>{NUM})(?P<ua>{UNIT})(?:(?P<sep>{SEP})(?P<b>{NUM})(?P<ub>{UNIT}))?(?![\d.])")
PREFIX = re.compile(r"(?<![\wÀ-ỹ])(?P<pre>(?:dao động\s+)?(?:khoảng\s+)?(?:từ\s+)?(?:khoảng\s+)?)$", re.I)
PERIODS = {"ngày": "day", "tuần": "week", "tháng": "month"}
AFTER = re.compile(r"^(?P<conn>\s*(?:(?:/|mỗi|một|theo|cho|trên|từng|1)\s*)*)(?P<kw>ngày|tuần|tháng)\b", re.I)
KEYWORD = re.compile(r"\b(ngày|tuần|tháng)\b", re.I)
FIX_PERIODS = ("week", "month")
REVIEW_CUES = re.compile(
    r"chênh|tiết kiệm|rẻ hơn|đắt hơn|thấp hơn|cao hơn|nhiều hơn|ít hơn|hơn\s+\d|giảm|tăng thêm|gấp|lên tới|lên đến|"
    r"tương đương|ngang\s(?:bằng|ngửa|với)|nhân\s|cộng\s|tổng|tính ra|tính theo|quy đổi|bình quân|trung bình|"
    r"\bx\s?\d|×|=|\b\d+\s*(?:ngày|tuần|tháng)\b|\b(?:hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\s+(?:ngày|tuần|tháng)\b|"
    r"mỗi\s+(?:một\s+)?(?:người|khách)|phần trăm|%",
    re.I,
)


def load_expected(path: Path | None = None) -> dict[str, dict[str, tuple[int, int]]]:
    import yaml  # chỉ cần khi đọc pricing.yml: bộ quét (scan_text) và test không phụ thuộc PyYAML

    d = yaml.safe_load((path or ROOT / "_data" / "pricing.yml").read_text(encoding="utf-8"))
    by_id = {v["id"]: v for v in d["vehicles"]}
    out: dict[str, dict[str, tuple[int, int]]] = {}
    for key, yid in YAML_ID.items():
        rates = by_id[yid]["rates"]
        out[key] = {}
        for period in ("day", "week", "month"):
            lo, hi = rates[period]["min"], rates[period]["max"]
            if lo is not None:
                out[key][period] = (int(lo), int(hi if hi is not None else lo))
    return out


def vn(n: int) -> str:
    return f"{n:,}".replace(",", ".")


@dataclass
class Phrase:
    start: int                      # vị trí tuyệt đối của cụm giá trong văn bản
    end: int
    text: str
    lo: int
    hi: int
    is_range: bool
    vehicle: str = ""
    period: str = ""
    status: str = "UNBOUND"         # OK | MISMATCH | UNBOUND
    expected: tuple[int, int] | None = None
    fix_start: int = -1             # vùng bị thay (có thể gồm tiền tố "từ ..."), vị trí tuyệt đối
    fix_end: int = -1
    fix_old: str = ""
    fix_new: str = ""
    note: str = ""


def vehicles_in(seg: str) -> list[str]:
    seen = []
    for key, rx in VEHICLES:
        if rx.search(seg):
            seen.append(key)
    return seen


def _vehicle_before(seg: str, pos: int) -> str:
    best, best_pos = "", -1
    for key, rx in VEHICLES:
        for m in rx.finditer(seg, 0, pos):
            if m.start() > best_pos:
                best, best_pos = key, m.start()
    return best


def _period_for(seg: str, m: re.Match) -> str:
    """AFTER có từ nối ('/', mỗi, một, cho một...) > từ khóa sát phía trước (không có chữ số xen giữa) >
    AFTER trần > kỳ hạn kế thừa từ đầu câu ("Theo tuần, A khoảng X, B khoảng Y": duy nhất một kỳ hạn trước cụm giá)."""
    after = AFTER.match(seg[m.end():m.end() + 30])
    if after and after.group("conn").strip():
        return PERIODS[after.group("kw").lower()]
    window = seg[max(0, m.start() - 60):m.start()]
    last = None
    for km in KEYWORD.finditer(window):
        if not re.search(r"\d", window[km.end():]):
            last = km
    if last:
        return PERIODS[last.group(1).lower()]
    if after:
        return PERIODS[after.group("kw").lower()]
    kws = {PERIODS[k.group(1).lower()] for k in KEYWORD.finditer(seg[:m.start()])}
    if len(kws) == 1:
        return kws.pop()
    return ""


def _collapse_prefix(pre: str) -> str:
    """Một khoảng co thành một số duy nhất: bỏ 'từ'; 'khoảng từ'/'dao động từ' -> 'khoảng '."""
    low = pre.lower()
    return "khoảng " if ("khoảng" in low or "dao động" in low) else ""


def _evaluate(seg: str, base: int, m: re.Match, ph: Phrase, expected: dict) -> None:
    if not ph.vehicle or not ph.period or ph.period not in expected.get(ph.vehicle, {}):
        ph.note = ph.note or "không ràng buộc được xe/kỳ hạn"
        return
    if ph.period not in FIX_PERIODS:
        ph.status, ph.note = "SKIP_DAY", "giá ngày không đổi; số tiền cạnh chữ 'ngày' có thể là phép tính"
        return
    elo, ehi = ph.expected = expected[ph.vehicle][ph.period]
    ok = (ph.lo, ph.hi) == (elo, ehi) if ph.is_range else elo <= ph.lo <= ehi
    if ok:
        ph.status = "OK"
        return
    ph.status = "MISMATCH"
    ua, ub, sep = m.group("ua") or "", m.group("ub") or "", m.group("sep") or ""
    pre_m = PREFIX.search(seg[max(0, m.start() - 30):m.start()])
    pre = pre_m.group("pre") if pre_m else ""
    if elo == ehi:                                    # giá đúng là MỘT số
        if ph.is_range:                               # co khoảng cũ thành số mới (bỏ/đổi tiền tố)
            ph.fix_start = base + m.start() - len(pre)
            ph.fix_end = base + m.end()
            ph.fix_new = _collapse_prefix(pre) + vn(elo) + ub
        else:
            ph.fix_start, ph.fix_end = base + m.start(), base + m.end()
            ph.fix_new = vn(elo) + ua
    else:                                             # giá đúng là MỘT khoảng
        if ph.is_range:
            ph.fix_start, ph.fix_end = base + m.start(), base + m.end()
            ph.fix_new = f"{vn(elo)}{ua}{sep}{vn(ehi)}{ub}"
        else:
            ph.note = "giá đúng là một khoảng nhưng bài ghi một số: cần sửa tay"
    if ph.fix_start >= 0:
        ph.fix_old = None  # điền sau bởi scan_text (cần văn bản gốc)
    if REVIEW_CUES.search(seg):
        ph.status = "REVIEW"
        ph.note = "câu có phép tính/so sánh: người đọc quyết định (đề xuất giữ trong fix_new)"


def scan_segment(seg: str, base: int, expected: dict, vehicle_hint: str = "", period_hint: str = "") -> list[Phrase]:
    out: list[Phrase] = []
    for m in PHRASE.finditer(seg):
        lo = int(m.group("a").replace(".", ""))
        hi = int(m.group("b").replace(".", "")) if m.group("b") else lo
        ph = Phrase(base + m.start(), base + m.end(), m.group(0), lo, hi, bool(m.group("b")))
        ph.vehicle = vehicle_hint or _vehicle_before(seg, m.start())
        ph.period = period_hint or _period_for(seg, m)
        _evaluate(seg, base, m, ph, expected)
        out.append(ph)
    return out


def sentence_spans(line: str):
    start = 0
    for m in re.finditer(r"(?<=[.!?])\s+", line):
        yield start, m.start()
        start = m.end()
    yield start, len(line)


TABLE_ROW = re.compile(r"^\s*\|")


def scan_text(text: str, expected: dict, doc_vehicle: str = "") -> list[Phrase]:
    """Mọi cụm giá trong văn bản (vị trí tuyệt đối). Quét từng dòng; dòng thường tách tiếp theo câu; hàng bảng theo cột."""
    results: list[Phrase] = []
    header_periods: list[str] = []
    offset = 0
    prev_vehicle_ctx: list[str] | str = ""
    section_vehicle = ""          # xe duy nhất được nêu trong heading gần nhất ("### Honda Air Blade")
    for line in text.split("\n"):
        base = offset
        offset += len(line) + 1
        if not line.strip():
            prev_vehicle_ctx = ""
            continue
        if line.lstrip().startswith("#"):
            hv = vehicles_in(line)
            section_vehicle = hv[0] if len(hv) == 1 else ""
            prev_vehicle_ctx = ""
            continue
        if TABLE_ROW.match(line):
            cells = [(m.group(1), m.start(1)) for m in re.finditer(r"\|([^|\n]*)(?=\|)", line)]
            if cells and all(set(c.strip()) <= set("-: ") for c, _ in cells):
                continue
            has_phrase = bool(PHRASE.search(line))
            if not has_phrase and re.search(r"ngày|tuần|tháng", line, re.I):
                header_periods = [next((v for k, v in PERIODS.items() if k in c.lower()), "") for c, _ in cells]
                continue
            veh = ""
            for idx, (c, cs) in enumerate(cells):
                if idx == 0:
                    vs = vehicles_in(c)
                    veh = vs[0] if len(vs) == 1 else ""
                    continue
                per = header_periods[idx] if idx < len(header_periods) else ""
                if veh and per:
                    results += scan_segment(c, base + cs, expected, vehicle_hint=veh, period_hint=per)
                elif PHRASE.search(c):
                    for ph in scan_segment(c, base + cs, expected, vehicle_hint=veh, period_hint=per):
                        ph.note = ph.note or "ô bảng không ràng buộc được xe/kỳ hạn"
                        results.append(ph)
            continue
        header_periods = []
        for s, e in sentence_spans(line):
            seg = line[s:e]
            vs = vehicles_in(seg)
            if PHRASE.search(seg):
                hint = ""
                prev = prev_vehicle_ctx[0] if len(prev_vehicle_ctx) == 1 else ""
                if not vs:
                    # heading của mục nói xe nào thì câu giá không tên xe thuộc xe đó; câu trước nhắc một xe KHÁC
                    # (vd. "chắc chắn hơn Vision") là so sánh, không phải chủ thể => mơ hồ, để UNBOUND.
                    if section_vehicle and prev and prev != section_vehicle:
                        hint = ""
                    elif section_vehicle:
                        hint = section_vehicle
                    elif prev:
                        hint = prev
                    elif doc_vehicle:
                        hint = doc_vehicle
                phs = scan_segment(seg, base + s, expected, vehicle_hint="")
                if hint:
                    for ph in phs:
                        if not ph.vehicle:
                            ph.vehicle = hint
                            ph.status, ph.note = "UNBOUND", ""
                            m = PHRASE.match(seg, ph.start - base - s)
                            if m and ph.period and ph.period in expected.get(hint, {}):
                                _evaluate(seg, base + s, m, ph, expected)
                results += phs
            if vs:
                prev_vehicle_ctx = vs
    for ph in results:
        if ph.fix_start >= 0:
            ph.fix_old = text[ph.fix_start:ph.fix_end]
    return results
