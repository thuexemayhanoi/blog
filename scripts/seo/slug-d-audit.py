#!/usr/bin/env python3
"""SEO Master — audit slug thiếu chữ đ và bản đồ OLD -> NEW (đọc-only, KHÔNG đổi URL, không gọi mạng).

Đầu vào : data/content-matrix.csv, _posts/*.md (front matter `permalink`), data/qa/<ID>.json, data/state/writer-claims.json,
          nguồn văn bản của repo (_posts, trang gốc, _data, _includes, _layouts, _drafts) để đếm liên kết nội bộ tới URL cũ.
Đầu ra  : reports/factory/seo-master/slug-d-migration-map.csv   một hàng/URL bị ảnh hưởng (OLD, NEW, va chạm, ràng buộc phải đổi, chặn)
          reports/factory/seo-master/slug-d-audit.md            báo cáo đọc được + bằng chứng hạ tầng + quy trình di trú khi đủ điều kiện
          reports/factory/seo-master/slug-d-audit.json          số liệu tổng hợp (máy đọc)

Không ghi vào _posts, matrix, data/qa, checkpoint, lease. Idempotent. Nhãn: FACT = đọc từ tệp; INFERRED/UNKNOWN nêu rõ trong báo cáo.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

from slugs import DATE_PREFIX, is_d_stripped, slug_correct, split_date_prefix

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "factory" / "seo-master"
PATH_TOKEN = re.compile(r"/(?:[a-z0-9\-%]+/){5}")  # /<cat>/<yyyy>/<mm>/<dd>/<slug>/

BINDINGS = ("front matter permalink (đổi byte bài => content_sha256); "
            "matrix expected_url + output_path + canonical_url (=> matrix_row_sha256); "
            "data/qa/<ID>.json source_path + content_sha256 + matrix_row_sha256; tên tệp _posts")
BLOCKERS = "BLOCKED_INFRA_301|BLOCKED_NO_EVIDENCE_REVISION_PATH"


def read_matrix() -> list[dict]:
    with (ROOT / "data" / "content-matrix.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def front_matter_value(text: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+?)\s*$", text[:4000], re.M)
    return m.group(1).strip().strip("\"'") if m else ""


def text_files() -> list[Path]:
    files: list[Path] = []
    for pat in ("_posts/*.md", "_drafts/*.md", "*.md", "*.html", "_data/*.yml", "_data/*.json", "_data/*/*", "_includes/*", "_layouts/*"):
        files += [p for p in ROOT.glob(pat) if p.is_file()]
    return sorted(set(files))


def active_leases() -> dict[str, str]:
    p = ROOT / "data" / "state" / "writer-claims.json"
    out: dict[str, str] = {}
    if p.exists():
        for slot, lease in (json.loads(p.read_text(encoding="utf-8")).get("leases") or {}).items():
            for i in lease.get("ids", []):
                out[i] = f"{slot}:{lease.get('session', '')}"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    matrix = read_matrix()
    by_id = {r["id"]: r for r in matrix}
    leases = active_leases()

    # ---- URL hiện có (để phát hiện va chạm)
    existing_urls: dict[str, str] = {}
    post_urls: dict[str, str] = {}
    for p in sorted((ROOT / "_posts").glob("*.md")):
        t = p.read_text(encoding="utf-8", errors="replace")
        u = front_matter_value(t, "permalink")
        if u:
            existing_urls[u] = f"_posts/{p.name}"
            post_urls[f"_posts/{p.name}"] = u
    for r in matrix:
        if r.get("expected_url") and "{date}" not in r["expected_url"]:
            existing_urls.setdefault(r["expected_url"], r["output_path"])
    for p in ROOT.glob("*.md"):
        u = front_matter_value(p.read_text(encoding="utf-8", errors="replace"), "permalink")
        if u:
            existing_urls.setdefault(u, p.name)
    slug_use = collections.Counter(u.rstrip("/").rsplit("/", 1)[-1] for u in post_urls.values())

    # ---- tập bị ảnh hưởng (FACT: khớp tuyệt đối với slug cũ tính từ tiêu đề matrix)
    affected: list[dict] = []
    for r in matrix:
        if r["status"] != "PUBLISHED":
            continue
        path = ROOT / r["output_path"]
        if not path.is_file():
            continue
        old_url = post_urls.get(r["output_path"], "")
        if not old_url:
            continue
        old_slug = unquote(old_url.rstrip("/").rsplit("/", 1)[-1])
        if not is_d_stripped(r["title"], old_slug):
            continue
        prefix, _ = split_date_prefix(old_slug)
        new_slug = prefix + slug_correct(r["title"])
        new_url = old_url[: -(len(old_slug) + 1)] + new_slug + "/"
        fname = Path(r["output_path"]).name
        date_part = fname[:11]  # YYYY-MM-DD-
        new_path = f"_posts/{date_part}{new_slug}.md" if DATE_PREFIX.match(date_part) else ""
        affected.append({"article_id": r["id"], "old_url": old_url, "new_url": new_url, "old_slug": old_slug,
                         "new_slug": new_slug, "title": r["title"], "parent_id": r.get("parent_id", ""),
                         "child_id": r.get("child_id", ""), "published_date": r.get("published_date", ""),
                         "old_output_path": r["output_path"], "new_output_path": new_path})

    # ---- va chạm
    new_count = collections.Counter(a["new_url"] for a in affected)
    old_set = {a["old_url"] for a in affected}
    for a in affected:
        flags = []
        if a["new_url"] in existing_urls:
            flags.append("NEW_URL_EXISTS")
        if new_count[a["new_url"]] > 1:
            flags.append("NEW_URL_DUPLICATE")
        if a["new_url"] in old_set:
            flags.append("CHAIN_RISK")
        if slug_use[a["new_slug"]] > 0:
            flags.append("SLUG_REUSED_ELSEWHERE")
        if a["new_output_path"] and (ROOT / a["new_output_path"]).exists():
            flags.append("NEW_FILE_EXISTS")
        a["collision_flags"] = "|".join(flags)

    # ---- liên kết nội bộ tới URL cũ (đếm theo tệp, loại trừ chính bài)
    refs_posts: dict[str, set[str]] = collections.defaultdict(set)
    refs_other: dict[str, set[str]] = collections.defaultdict(set)
    wanted = {a["old_url"] for a in affected}
    for f in text_files():
        rel = f.relative_to(ROOT).as_posix()
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for tok in set(PATH_TOKEN.findall(t)):
            if tok in wanted:
                (refs_posts if rel.startswith("_posts/") or rel.startswith("_drafts/") else refs_other)[tok].add(rel)
    referencing_posts: set[str] = set()
    for a in affected:
        rp = refs_posts[a["old_url"]] - {a["old_output_path"]}
        a["inbound_posts"] = len(rp)
        a["inbound_other"] = len(refs_other[a["old_url"]])
        referencing_posts |= rp

    # ---- bằng chứng QA và lease
    def evidence_state(aid: str, output_path: str) -> str:
        qap = ROOT / "data" / "qa" / f"{aid}.json"
        if not qap.exists():
            return "MISSING"
        qa = json.loads(qap.read_text(encoding="utf-8"))
        real = hashlib.sha256((ROOT / output_path).read_bytes()).hexdigest()
        if qa.get("source_path") != output_path:
            return "DRIFT_SOURCE_PATH"
        return "yes" if qa.get("content_sha256") == real else "DRIFT_CONTENT_SHA"

    for a in affected:
        a["qa_evidence_intact"] = evidence_state(a["article_id"], a["old_output_path"])
        a["writer_lease"] = leases.get(a["article_id"], "")
        a["bindings_to_change"] = BINDINGS
        a["blockers"] = BLOCKERS
        a["migration_ready"] = "NO"
    published_drift = collections.Counter(
        evidence_state(r["id"], r["output_path"]) for r in matrix
        if r["status"] == "PUBLISHED" and (ROOT / r["output_path"]).is_file())

    affected.sort(key=lambda a: a["old_url"])
    cols = ["article_id", "old_url", "new_url", "old_slug", "new_slug", "title", "parent_id", "child_id", "published_date",
            "old_output_path", "new_output_path", "qa_evidence_intact", "writer_lease", "inbound_posts", "inbound_other",
            "collision_flags", "bindings_to_change", "blockers", "migration_ready"]
    with (out / "slug-d-migration-map.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for a in affected:
            w.writerow({k: a.get(k, "") for k in cols})

    flag_counts = collections.Counter(f for a in affected for f in a["collision_flags"].split("|") if f)
    summary = {
        "affected_urls": len(affected),
        "published_posts_in_matrix": sum(1 for r in matrix if r["status"] == "PUBLISHED"),
        "planned_rows": sum(1 for r in matrix if r["status"] == "PLANNED"),
        "planned_rows_with_d_in_title": sum(1 for r in matrix if r["status"] == "PLANNED" and "đ" in r["title"].lower()),
        "planned_rows_slug_wrong": sum(1 for r in matrix if r["status"] == "PLANNED" and r.get("slug") and r["slug"] != slug_correct(r["title"])),
        "by_parent": dict(sorted(collections.Counter(a["parent_id"] for a in affected).items())),
        "collision_flags": dict(sorted(flag_counts.items())),
        "qa_evidence_intact": dict(sorted(collections.Counter(a["qa_evidence_intact"] for a in affected).items())),
        "published_evidence_state_all": dict(sorted(published_drift.items())),
        "leased_ids": sum(1 for a in affected if a["writer_lease"]),
        "urls_with_inbound_posts": sum(1 for a in affected if a["inbound_posts"]),
        "urls_with_inbound_other": sum(1 for a in affected if a["inbound_other"]),
        "inbound_post_refs_total": sum(a["inbound_posts"] for a in affected),
        "distinct_other_posts_to_edit_for_links": len(referencing_posts),
        "migration_ready": 0,
        "blockers": BLOCKERS.split("|"),
    }
    (out / "slug-d-audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "slug-d-audit.md").write_text(render_report(summary, affected), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def render_report(s: dict, affected: list[dict]) -> str:
    ex = [a for a in affected if a["inbound_posts"] == 0][:5]
    sample = "\n".join(f"| `{a['old_url']}` | `{a['new_url']}` | {a['article_id']} |" for a in ex)
    coll = ", ".join(f"{k}: {v}" for k, v in s["collision_flags"].items()) or "không có"
    return f"""# Slug thiếu chữ đ — audit và bản đồ OLD → NEW

Sinh bởi `scripts/seo/slug-d-audit.py` (đọc-only). Bản đồ đầy đủ: `slug-d-migration-map.csv`. **Trạng thái: BLOCKED_INFRA_301 + BLOCKED_NO_EVIDENCE_REVISION_PATH.
Chưa đổi URL nào; không có URL nào được sửa thật.**

## 1. Số liệu (FACT, đọc từ repo)

| Hạng mục | Giá trị |
|---|---:|
| URL đã xuất bản bị mất chữ đ (khớp tuyệt đối với slug cũ tính từ tiêu đề matrix) | {s['affected_urls']} |
| Bài PUBLISHED trong matrix | {s['published_posts_in_matrix']} |
| Hàng PLANNED (chưa xuất bản) / trong đó tiêu đề có chữ đ | {s['planned_rows']} / {s['planned_rows_with_d_in_title']} |
| Hàng PLANNED có slug sai | {s['planned_rows_slug_wrong']} |
| Va chạm của URL mới | {coll} |
| Bằng chứng QA của các URL này: khớp / lệch sẵn (xem ghi chú) | {json.dumps(s['qa_evidence_intact'], ensure_ascii=False)} |
| Bằng chứng QA của toàn bộ bài PUBLISHED | {json.dumps(s['published_evidence_state_all'], ensure_ascii=False)} |
| Bài thuộc lease writer đang giữ | {s['leased_ids']} |
| URL cũ còn được bài khác trỏ tới (số URL / tổng liên kết / số bài khác phải sửa nếu cập nhật link) | {s['urls_with_inbound_posts']} / {s['inbound_post_refs_total']} / {s['distinct_other_posts_to_edit_for_links']} |
| URL cũ còn nằm trong dữ liệu/mẫu giao diện (_data, _includes, _layouts, trang gốc) | {s['urls_with_inbound_other']} |
| Phân bố theo parent | {json.dumps(s['by_parent'], ensure_ascii=False)} |

Ghi chú về `DRIFT_CONTENT_SHA`: đây là tình trạng **có sẵn, không do audit này**. `content_sha256` trong evidence lệch byte bài hiện tại ở ~1.068 bài PUBLISHED chủ yếu vì đợt migrate domain
(phân tích và kế hoạch: `docs/LEGACY-QA-RE-ATTESTATION-PLAN.md`, `reports/qa-audit/legacy-evidence-2026-10-12.json`); chờ chủ duyệt `reattest-legacy-qa.py apply --approval-ref`. Gate hàng ngày chỉ kiểm scope chunk nên không đỏ.
Việc di trú URL phải đi sau (hoặc cùng) đường bảo trì đó.

Hàng PLANNED đã đúng: slugify của generator và refill đã sửa chữ đ (đ → d trước khi bỏ dấu); không hàng PLANNED nào sai slug, nên bài **mới** không tái diễn lỗi.

## 2. Vì sao chưa thể di trú 1.410 URL đã xuất bản

Hai điều kiện bắt buộc đều chưa đạt, mỗi điều kiện đủ để chặn một mình.

**A. BLOCKED_INFRA_301 — không có chuyển hướng HTTP 301/308 thật.**
- Site chạy trên GitHub Pages (tệp `CNAME` = `blog.thuexemaynguyentu.com`; build bằng `actions/jekyll-build-pages`; plugin trong `_config.yml`: `jekyll-sitemap`, `jekyll-feed`).
  GitHub Pages không hỗ trợ cấu hình chuyển hướng phía máy chủ (không có `_redirects`, không đặt được header/status). Plugin `jekyll-redirect-from` chỉ sinh trang HTML trả **HTTP 200**
  chứa meta refresh + JavaScript, không phải 301; yêu cầu của chủ website là không coi đó là chuyển hướng.
- Không có hạ tầng edge nào được xác minh: tài khoản Vercel đang kết nối có 0 domain và 0 project (FACT, truy vấn 2026-10-23); repo không có cấu hình Cloudflare/Netlify/Vercel
  (`grep` không thấy `_redirects`, `vercel.json`, `netlify.toml`). Không thể dò header production từ môi trường chạy (proxy chặn tên miền, HTTP 403) nên không xác minh được có CDN đứng trước hay không (UNKNOWN).

**B. BLOCKED_NO_EVIDENCE_REVISION_PATH — đổi URL làm vỡ ba ràng buộc toàn vẹn của factory, và chưa có công cụ chính thức cập nhật chúng.**
Mỗi bài có `permalink` nằm trong front matter, nên đổi slug là đổi byte bài. Phải đổi đồng thời: {BINDINGS}.
`scripts/factory/validate.py` (scope batch/full) báo đỏ ngay khi `content_sha256`, `matrix_row_sha256` hoặc `source_path` lệch. Công cụ ghi evidence duy nhất, `reattest-legacy-qa.py`, chỉ cho
trường hợp chỉ đổi domain đối chiếu baseline `1b55bd81`; không có đường chính thức cho "đổi nội dung/URL rồi chấm lại". Sửa tay `data/qa/` bị cấm (AGENTS.md quy tắc 9).
Ngoài ra, nếu cập nhật liên kết nội bộ cho đúng URL mới thì thêm {s['distinct_other_posts_to_edit_for_links']} bài khác bị đổi byte và rơi vào cùng vấn đề.

## 3. Việc đã làm an toàn và việc chặn tái diễn

- Bài mới: generator (`generate-matrix.py`) và refill (`refill-queue.py`) dùng slugify đã sửa (đ → d trước khi bỏ dấu), `TestSeoSlugForms` và `TestSlugify` trong
  `scripts/factory/tests/test_slugify_vi.py` khóa hành vi (so với toàn bộ tiêu đề matrix, và không hàng PLANNED nào mang slug thiếu chữ đ).
  Ghi nhận không cần sửa: `expand-topic-universe.py` chỉ dùng `norm()` để kiểm trùng (không sinh slug); dòng kiểm trùng slug trong đó là mã chết (regex thoát sai nên không bao giờ thay khoảng trắng bằng gạch ngang) nhưng vô hại vì công cụ chạy một lần
  (chạy lại trên dữ liệu đã commit: 121/121 ứng viên bị từ chối vì trùng chính hàng đã nhận, seed và báo cáo không đổi) và tính duy nhất slug/output_path/canonical được ép ở `generate-matrix.py` cùng test của nó.
- Bản đồ OLD → NEW đã sẵn (không va chạm theo bảng trên), kèm số liên kết nội bộ và ràng buộc phải đổi cho từng URL.

Năm ví dụ trong bản đồ (URL cũ chưa có liên kết nội bộ trỏ tới):

| OLD | NEW | ID |
|---|---|---|
{sample}

## 4. Quy trình di trú khi đủ điều kiện (chưa thực hiện)

Chỉ bắt đầu khi **cả hai** điều kiện sau đều có bằng chứng: (1) có chuyển hướng HTTP 301/308 thật cho từng đường dẫn cũ, kiểm bằng `curl -I` trên production
(ví dụ chuyển site sang nền tảng hỗ trợ redirect, hoặc đặt lớp edge có quy tắc chuyển hướng theo ánh xạ OLD → NEW); (2) chủ website duyệt một công cụ bảo trì chính thức cho "đổi URL/nội dung bài đã xuất bản":
sao lưu evidence cũ, chấm lại độc lập bằng scorer chuẩn (ngưỡng 75/70 không đổi), ghi provenance, rollback theo lô.

Mỗi lô tối đa 50 bài, một commit: (a) đổi tên tệp + `permalink`, (b) cập nhật hàng matrix, (c) ghi evidence mới bằng công cụ ở (2), (d) cập nhật liên kết nội bộ chỉ trong lô đó và dữ liệu `_data`,
(e) thêm quy tắc 301 OLD → NEW, (f) build + `check-built-links.py` + validate FULL, (g) sau deploy: kiểm 301 cho mọi OLD trong lô (một bước, không chuỗi), kiểm NEW trả 200, canonical/sitemap/breadcrumb mới, OLD không còn trong sitemap,
(h) giữ nguyên lô trước nếu lô sau lỗi; rollback = revert đúng commit lô và gỡ quy tắc 301 của lô.
Không bao giờ chuyển hướng hàng loạt về trang chủ, không tạo chuỗi hay vòng chuyển hướng.
"""


if __name__ == "__main__":
    sys.exit(main())
