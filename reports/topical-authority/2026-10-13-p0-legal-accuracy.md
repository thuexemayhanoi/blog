# P0 FACTUAL ACCURACY — Vietnam motorcycle licenses (2026-10-13)

STATUS: CONFIRMED CONFLICT IN PUBLISHED ARTICLE; **NO PRODUCTION EDIT MADE**.
Snapshot base: ea7c82f57185eb85487bb61287ff3539d8e41ce9.
Article: https://blog.thuexemaynguyentu.com/an-toan-phap-ly/2026/09/27/cac-hang-bang-lai-xe-may-tai-viet-nam/

## Finding L01 — Wrong minimum age for A1
Observed in the published article's "Hạng A1" section (retrieved via site-indexed article): minimum age stated as 16.
Governing source: Article 59(1)(b), Law 36/2024/QH15, effective 2025-01-01: 18 or older for A1/A/B1 licensing. Article 59(1)(a): 16 or older may operate *xe gắn máy*, not receive an A1 licence. Confusing these exposes customers to eligibility errors.
Official corroboration: https://xaydungchinhsach.chinhphu.vn/do-tuoi-cua-nguoi-lai-xe-may-va-muc-phat-voi-nguoi-chua-du-tuoi-lai-xe-theo-quy-dinh-119250202112655906.htm
Official legal text: https://xaydungchinhsach.chinhphu.vn/toan-van-luat-trat-tu-an-toan-giao-thong-duong-bo-119240909105718285.htm
Severity: HIGH. Recommendation: owner-authorized factual correction of existing URL only; preserve slug, URL and canonical and document legal source.

## Finding L02 — Incorrect B1 scope
Observed in same published article's "Hạng B1" section: asserts this class does not include two-wheeled motorcycles and only covers three-wheeled motorcycles.
Governing source: Article 57(1)(c), Law 36/2024/QH15: B1 covers three-wheeled motorcycles **and vehicles covered by class A1**.
Official source: https://xaydungchinhsach.chinhphu.vn/toan-van-luat-trat-tu-an-toan-giao-thong-duong-bo-119240909105718285.htm
Severity: HIGH. Recommendation: verify present regulation and transitional license conditions with an expert and correct the relevant sentence on the same URL in a small authorized content edit; no new overlapping article.

## Finding L03 — False blanket statement that motorcycle licences expire
Observed in the published article under "Điều kiện thi và thủ tục": "giấy phép lái xe máy có thời hạn theo quy định, đến hạn phải đổi đúng thủ tục." The FAQ also generalizes expired motorcycle licences.
Governing source: **Article 57(5)(a)**, Law 36/2024/QH15: A1, A and B1 driving licences are **without an expiry date**. Conditions affecting licence validity (e.g. withdrawal or points) are separate from fixed validity duration. This is about licences issued under the new regime; historical transitional licence classifications require review before making blanket claims.
Official source: https://xaydungchinhsach.chinhphu.vn/toan-van-luat-trat-tu-an-toan-giao-thong-duong-bo-119240909105718285.htm
Severity: HIGH. Recommendation: amend the blanket statement and the FAQ after owner authorization; retain the original article URL and avoid rewriting unrelated text.

## Evidence verification 2026-10-14
- Original _posts source file: `_posts/2026-09-27-cac-hang-bang-lai-xe-may-tai-viet-nam.md` on GitHub main; source blob: `1328f3a119820924f485751f5dbf03c11de5dd76`.
- Tavily Extract fetched the public URL and reflected all three findings. These errors are present in original repository text, not artifacts of HTML/markdown extraction.
- Parallel Search found relevant legal sources; the authoritative review used government-published full law (Article 57, Article 59).
- Note: the "16 tuổi thi được hạng A1" error also appears in the FAQ — correcting only the Hạng A1 paragraph would leave a conflicting statement on the page.

## Controlled remediation gate
- Freeze original article bytes, URL, canonical, metadata and inbound links.
- Produce one minimal content diff limited to provably inaccurate statements, with legal references and effective date.
- Check related posts for copied misinformation by searching exact statements; do not change large batches blindly.
- Independent review, QA, exact-URL live check after future approved deployment.
- Explicit website owner approval before modifying the published article. No automatic merge, redirects, or index changes.

No legal advice based on unverified draft facts should be generated. These findings are based on publicly visible published claims and authoritative government text as of audit date.
