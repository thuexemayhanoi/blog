# Rubric — semantic FAQ / AI-search audit (read-only)

This rubric is given verbatim to every analysis agent so that 300 posts + 77 main pages are judged with
the same definitions. Agents only READ the repository and write ONE JSON file with their own results.

## 0. Hard rules

1. READ-ONLY. Do not edit, create or delete anything in the repository, `_posts/`, `_drafts/`, `data/`,
   `_includes/`, `_layouts/`, `.github/`. The only file you may write is the output JSON named in your task.
   Never run git commands that change state (no commit, push, checkout, reset, stash).
2. EVIDENCE OR NOTHING. Every `*_quote` field must be copied CHARACTER FOR CHARACTER from the page text you
   read (<= 30 words; markdown emphasis characters `*` `_` and backticks may be omitted, nothing else may
   change). A validator searches every quote in the source; a quote that is not found invalidates the record.
   Do not paraphrase inside quote fields. Put paraphrase in `notes` fields only.
3. NO INVENTED DATA. Never invent search volume, impressions, clicks, rankings, traffic, AI citations,
   "AI Overview" appearances, prices, deposits, fees, insurance terms, opening hours, policies, number of
   customers or years of experience. The only approved business facts are in `data/business-facts.json`
   (address, phone, hours 09:00-21:00, vehicle types, five approved day/week/month price lines, deposit
   = "Xác nhận trực tiếp", electric price = "liên hệ"). Everything else a post says about prices, deposits,
   fees, laws, penalties, documents or third-party places is an UNVERIFIED claim: flag it, do not endorse it.
4. NEVER write a suggested FAQ answer that is not already supported by a passage in the page. A suggested
   question is only allowed if you can quote the existing passage that answers it WITHOUT changing its meaning.
5. FAQPage structured data is only legitimate when the same questions and answers are VISIBLE on the page.
   FAQ markup is not a guarantee of AI Overviews, AI Mode or any rich result. Do not promise outcomes.
6. Do not create a template of 5-10 generic questions. Questions must come from THIS page's content.
7. Write all free-text fields in Vietnamese (the owner reads Vietnamese). Enumerations stay in English
   upper-case exactly as listed. Keep each free-text field short (<= the limit given in the schema).
8. If something cannot be verified from the material you were given, say so in `notes` (do not guess).

## 1. FAQ status (exactly one value)

* `EXPLICIT` — the page ALREADY shows a visible section where >= 2 distinct reader questions are each
  followed by an answer (question-form headings with answers beneath them, bold question + answer, `Q:`/`A:`
  lines, `<details>`). A heading such as "Câu hỏi thường gặp" that only lists questions the reader should ASK
  THE SHOP (a checklist) or only has a generic sentence is NOT explicit.
* `IMPLICIT` — no explicit FAQ section, but the body already answers >= 2 DISTINCT, search-realistic questions
  (a person could type or say them) in self-contained 1-3 sentence passages that could be lifted as Q&A without
  changing meaning.
* `NONE` — neither: narrative/guide content without separable answers, or answers are too entangled/long to
  lift safely. An FAQ is not needed.
* `NOT_RECOMMENDED` — a FAQ would be harmful or low value: (a) its answers would amplify UNVERIFIED legal /
  price / deposit / insurance / fee claims; (b) the questions would duplicate another URL's FAQ (use action
  MERGE); (c) the page is purely navigational / transactional / legal text where Q&A adds nothing; (d) answers
  are time-sensitive and not maintained. State the reason.

## 2. Recommended action (exactly one value)

* `KEEP` — EXPLICIT FAQ of GOOD quality, nothing to change (or page where no change is useful and none is harmful
  and the FAQ is already present).
* `IMPROVE` — EXPLICIT FAQ exists but is FAIR/WEAK (numbering inside questions, answer starts with "Trả lời:",
  answers that overreach, unverified legal/price claims, duplicate/generic questions, missing the key question).
* `ADD` — IMPLICIT answers exist and a visible FAQ block built from those existing passages would be genuinely
  useful (clear question intent, helps AI/answer extraction and the reader).
* `MERGE` — the same FAQ / same question set / same intent exists on another URL: consolidate to one
  canonical answer and cross-link, do not duplicate.
* `NO_FAQ` — leave the page without FAQ (status NONE or NOT_RECOMMENDED).

Consistency: NONE => NO_FAQ. NOT_RECOMMENDED => NO_FAQ or MERGE. EXPLICIT => KEEP, IMPROVE or MERGE. IMPLICIT => ADD,
NO_FAQ (with reason) or MERGE.

## 3. Priority (P0-P3)

* `P0` — an issue that must be settled BEFORE any FAQ work: unverified legal/price/deposit claims inside an
  existing FAQ, wrong or contradictory answers, invalid/mismatched structured data, or a high-intent page
  (price / deposit / documents / how to rent) whose FAQ gap or error directly misleads a renter.
* `P1` — HIGH AI-search opportunity and a clear, safe action (IMPROVE/ADD/MERGE) on a core renter question.
* `P2` — MEDIUM opportunity or a safe but minor improvement.
* `P3` — LOW opportunity, NO_FAQ, or KEEP.

## 4. AI-search opportunity (reason required)

* `HIGH` — question-led or decision-led intent a renter really has (price, deposit, documents/licence, how to
  rent, which bike, receiving/returning, breakdown, tourist rental) AND the page already contains direct
  answers.
* `MEDIUM` — informational topic with some direct answers or moderate commercial relevance.
* `LOW` — narrative/local-culture content, thin or off-intent, or answers are not stable/verifiable.
This is a qualitative editorial judgement. It is NOT based on traffic, rankings or citation data (none is
available for this blog property) — never imply otherwise.

## 5. Other fields

* Answer directness: `DIRECT` = the first ~150 words state the answer to the page's main question;
  `PARTIAL` = the answer is only implied/after a long preamble; `INDIRECT` = the answer is spread out or missing.
* AI extractability: `HIGH` = descriptive headings + short self-contained answer paragraphs / lists / tables;
  `MEDIUM`; `LOW` = long narrative, vague headings ("Ưu điểm", "Kết luận"), answers depend on surrounding text.
* Headings (`GOOD|OK|WEAK`): one clear topic per H2, question/intent-style headings where useful, no skipped
  levels, no generic repeated headings. (The page title is rendered as the single H1 by the layout; a body H1
  is a defect.)
* Cannibalization: compare with the `similar` candidates in your pack (and `grep` the `_posts/` titles if you
  need to). `HIGH` = another URL answers the SAME primary question; `MEDIUM` = strong overlap on a sub-intent;
  `LOW` = related but distinct; `NONE`. Give the competing IDs and say which intent each serves.
* Internal links: the RENDERED page already gets links from the layout: a generic breadcrumb, the taxonomy breadcrumb
  (home -> Cẩm nang -> hub -> topic), a TOC, prev/next (chronological, NOT topical), up to 4 related posts (same
  topic cluster, taken in site order, NOT chosen by relevance) and a CTA button to /bang-gia/ (see
  `rendered_links_from_layout` and `layout_links_already_present` in your pack). Legacy posts have ZERO links in the
  body text (verified). Judge (a) whether the layout's related posts are really relevant to this page's intent and
  (b) whether a contextual in-body link is missing. Suggest at most 3 ADDITIONAL links, ONLY to targets listed in
  `allowed_link_targets` (that list already excludes what the layout links), each with a reason. Put layout links that
  are irrelevant or defective into `fix`. Never invent URLs.
* Title/meta: judge intent match, length (rendered title incl. site suffix > 60 chars is long; description
  < 70 or > 170 chars), duplicated boilerplate, missing keyword. Keep notes short.
* Implementation method: `TEMPLATE` (change in a layout/include for all posts), `COMPONENT` (a shared FAQ
  component fed by per-page data), `GENERATOR` (derived by tooling from existing content, then reviewed), or
  `CONTENT` (manual editorial edit of that one page).
* `qa_requirements`: what must be checked before this page may change (owner fact-check, visible-vs-schema
  parity, uniqueness, link check, Rich Results/validator test, 75/70 QA unchanged...).

## 6. Output

Write one JSON file with this shape (UTF-8, valid JSON, double quotes inside strings escaped as `\"`):

```
{"batch": "<batch id>", "records": [ { ...one record per input item, same order... } ]}
```

Record fields (all keys required; use empty arrays / "" where nothing applies):

```
"id": "<input id>",
"primary_intent": {"type": "INFORMATIONAL|COMMERCIAL|TRANSACTIONAL|LOCAL|NAVIGATIONAL", "description": "<=160 chars"},
"primary_keyword": {"value": "<=8 words", "source": "MATRIX|INFERRED"},
"semantic_entities": ["<=8 entities that really occur in the text"],
"answer_directness": {"level": "DIRECT|PARTIAL|INDIRECT", "evidence_quote": "verbatim quote or \"\""},
"ai_extractability": {"level": "HIGH|MEDIUM|LOW", "reason": "<=200 chars"},
"headings": {"level": "GOOD|OK|WEAK", "notes": "<=200 chars"},
"content_assessment": {"accuracy_risk": "LOW|MEDIUM|HIGH", "completeness": "COMPLETE|PARTIAL|THIN",
   "unverifiable_claims": [{"claim_quote": "verbatim", "kind": "LEGAL|PRICE|DEPOSIT|STATISTIC|THIRD_PARTY_FACT|DATE|OTHER", "note": "<=160 chars"}],   // <= 5
   "notes": "<=240 chars"},
"faq_status": "EXPLICIT|IMPLICIT|NONE|NOT_RECOMMENDED",
"faq_status_reason": "<=240 chars",
"existing_faq": [{"question": "verbatim", "answer_location": "section heading / line no.", "answer_quote": "verbatim"}],
"faq_quality": "GOOD|FAIR|WEAK|NA",
"faq_quality_notes": "<=240 chars",
"implicit_questions": [{"question": "natural Vietnamese question", "answer_location": "section heading / line no.",
   "answer_quote": "verbatim", "search_realistic": true}],   // <= 6
"suggested_questions": [{"question": "natural Vietnamese question", "answer_source": {"location": "...", "quote": "verbatim"},
   "needs_fact_check": false, "fact_check_reason": ""}],      // 0-5, only questions answered by existing passages
"faq_duplication": {"risk": "NONE|LOW|HIGH", "notes": "<=200 chars"},
"schema_fit": {"faqpage_eligible_now": false, "notes": "<=200 chars"},
"cannibalization": {"level": "NONE|LOW|MEDIUM|HIGH", "competing_ids": ["BLG-..."], "notes": "<=240 chars"},
"internal_links": {"assessment": "<=200 chars", "add": [{"target": "/path/", "reason": "<=120 chars"}], "fix": []},
"title_meta": {"assessment": "OK|IMPROVE", "notes": "<=200 chars"},
"ai_search_opportunity": {"level": "HIGH|MEDIUM|LOW", "reason": "<=200 chars"},
"recommended_action": "KEEP|IMPROVE|ADD|MERGE|NO_FAQ",
"priority": "P0|P1|P2|P3",
"risk": {"level": "LOW|MEDIUM|HIGH", "reason": "<=200 chars"},
"implementation_method": "TEMPLATE|COMPONENT|GENERATOR|CONTENT",
"qa_requirements": "<=240 chars",
"confidence": "HIGH|MEDIUM|LOW"
```

`schema_fit.faqpage_eligible_now` is true ONLY when the page already shows >= 2 visible Q&A pairs whose answers
are accurate enough to mark up. `existing_faq` must list every visible Q&A pair (EXPLICIT) and be empty otherwise.

## 7. Calibration anchors

* A post with the heading "Câu hỏi thường gặp" followed by five `###` questions each with a "Trả lời:" answer
  => `EXPLICIT`. If one answer states a legal rule as fact without a source (e.g. a foreigner may rent a 50cc
  without a licence "theo luật Việt Nam") => quality FAIR/WEAK, `unverifiable_claims` has a LEGAL entry,
  action `IMPROVE`, priority `P0` (legal claim inside a FAQ that would be marked up).
* A post whose section "Những câu hỏi nên hỏi trước khi đặt cọc" is a bullet list of questions the renter should
  ask the shop (no answers) => NOT an explicit FAQ. Judge the rest of the post: if it contains separable answers
  => `IMPLICIT`, else `NONE`. A deposit topic is high intent, but amounts/conditions must come only from
  approved facts => risk and `needs_fact_check` accordingly.
* A heading "Câu hỏi thường gặp khi sạc xe điện" with a paragraph but no Q&A pairs => not explicit.
* A walking-tour / local-culture narrative => `NONE`, `NO_FAQ`, opportunity `LOW`.

## 8. Main pages (items with `"kind": "PAGE"`)

* Your source text is the plain-text export of the RENDERED `<main>` of the page (headings prefixed with `#`; long card/list
  blocks are truncated after 12 items, totals are in the pack). Quote only from that file; cite the nearest heading as the
  location (there are no line numbers).
* Page types: Homepage, Category (`/du-lich/`...), Hub (`/thue-xe/`...), Topic (cluster) pages (`/thue-xe/dat-coc/`...), static /
  service pages (`/bang-gia*`, `/lien-he/`, `/gioi-thieu/`, `/bao-mat/`, `/dieu-khoan/`, `/bai-viet/`, `/chu-de/`).
* Homepage / category / hub / topic pages are mostly navigation and aggregation (cards of posts, counts, directories). A FAQ
  there usually only duplicates answers that live in the posts they list => `NONE` or `NOT_RECOMMENDED` (reason), unless the page
  carries its own editorial text that really answers questions. Do NOT treat a `<details>` directory/menu as a FAQ.
* Static pages: a visible FAQ is judged like a post FAQ (existing Q&A pairs, quality, unverified amounts). Policy pages
  (privacy, terms) => `NOT_RECOMMENDED`. Price pages: every amount, deposit or fee not in `data/business-facts.json` is an
  UNVERIFIED claim (kind PRICE/DEPOSIT) and makes the page risk HIGH / priority P0 if it sits inside a FAQ.
* `primary_keyword.source` is always `INFERRED` for pages. Cannibalization: compare with the sibling pages and the
  `similar_posts_by_title_tokens` in the pack (competing_ids may be post ids or page ids from the pack); price / deposit /
  documents / area topics are the usual overlaps.
* `implementation_method` for pages is usually `COMPONENT` (shared FAQ include fed by data) or `CONTENT`; `TEMPLATE` only when
  a layout-level change helps every page of that type.
