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
   The owner has also declared these topics BLOCKED until the owner decides (read `reports/factory/policy-conflicts.md`): a deposit
   amount/range, a late-return fee, renter insurance, holding ID documents, helmet included, refund of unused days. A page that
   STATES any of these as fact (amount or commitment) carries an unverifiable claim (kind DEPOSIT / PRICE / OTHER); a FAQ about
   them is `NOT_RECOMMENDED` (or `needs_fact_check=true` on a suggested question) and an existing FAQ that states them is
   `IMPROVE` with priority `P0`.
4. NEVER write a suggested FAQ answer that is not already supported by a passage in the page. A suggested
   question is only allowed if you can quote the existing passage that answers it WITHOUT changing its meaning.
5. FAQPage structured data is only legitimate when the same questions and answers are VISIBLE on the page.
   CURRENT GOOGLE FACTS (verified on Google Search Central, 2026-10-12): the FAQ rich result feature is deprecated and no longer
   shown in Google Search since 2026-05-07 (documentation removed June 2026); Google's AI-features guide (updated 2026-07-10) says
   structured data is not required for generative AI search, there is no special schema.org markup to add, "chunking" content
   into tiny pieces, rewriting content just for AI systems and llms.txt are not needed, and creating separate content for every
   query variation can violate the scaled-content spam policy. So NEVER justify a FAQ by "rich result", "AI Overview" or "schema
   boost". A FAQ is only worth recommending when it HELPS THE READER find a real answer that is currently buried, vague or
   scattered; if the answer is already clear under a descriptive heading, duplicating it in a Q&A block adds nothing => `NO_FAQ`.
   Do not promise outcomes.
6. Do not create a template of 5-10 generic questions. Questions must come from THIS page's content.
7. Write all free-text fields in Vietnamese (the owner reads Vietnamese). Enumerations stay in English
   upper-case exactly as listed. Keep each free-text field short (<= the limit given in the schema).
8. If something cannot be verified from the material you were given, say so in `notes` (do not guess).

## 1. FAQ status (exactly one value)

* `EXPLICIT` — the page ALREADY shows a visible section where >= 2 distinct reader questions are each
  followed by an answer (question-form headings with answers beneath them, bold question + answer, `Q:`/`A:`
  lines, `<details>`). A heading such as "Câu hỏi thường gặp" that only lists questions the reader should ASK
  THE SHOP (a checklist) or only has a generic sentence is NOT explicit.
  RUN-IN Q&A counts as explicit: many posts write the pairs inside ordinary paragraphs ("Hỏi một: ...? <answer> Hỏi hai: ...?",
  "Hỏi: ...? Trả lời: ...", "Câu hỏi đầu tiên: ... Câu hỏi thứ hai: ..."). It is visible Q&A, so `EXPLICIT`, but its quality is at most
  `FAIR` (not separable / not markup-ready) and the usual action is `IMPROVE` (restructure into discrete Q&A through the shared
  component WITHOUT changing the meaning), plus P0 if the answers state unverified legal / price / deposit facts. A single incidental
  "Hỏi:" is not a FAQ. List every pair in `existing_faq` (verbatim question text without the "Hỏi một:" label is fine; the quote must
  still be found in the source).
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
* `ADD` — IMPLICIT answers exist, they are currently hard to find (buried in long paragraphs, vague headings, no question-style
  signposting) and a short visible FAQ block built from those existing passages would genuinely help the reader. Use sparingly.
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
This is a qualitative editorial judgement about reader value and answer clarity. It is NOT based on traffic, rankings or citation
data (none is available for this blog property) — never imply otherwise. `HIGH` does not mean "add FAQ schema"; it means the page
serves a core renter question and its answer could be made clearer.

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
  `rendered_links_from_layout`, `layout_links_already_present` and `rendered_body_links` in your pack). Most legacy posts also carry
  2-5 TEMPLATED in-body links (mainly /lien-he/, /kinh-nghiem/, /bang-gia/ and the pillar post "kinh-nghiem-thue-xe-may-ha-noi"; the
  link to the pillar post ends in a double slash `//`, which is served as 200 with a single-slash canonical). Judge (a) whether the
  layout's related posts are really relevant to this page's intent, (b) whether the body's templated links are relevant or only
  boilerplate, and (c) whether a contextual in-body link is missing. Suggest at most 3 ADDITIONAL links, ONLY to targets listed in
  `allowed_link_targets` (that list already excludes what the layout links), each with a reason. Put links that are irrelevant or
  defective into `fix`. Never invent URLs.
* Title/meta: judge intent match, keyword placement and clarity (see the clarification above about length). Keep notes short.
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


Shape and semantics clarifications (from the calibration run):
* `internal_links.fix` is a list of short strings (each <= 120 chars), e.g. `"related block shows 4 posts about X, irrelevant to this topic"`.
* `risk.level` = the risk that this page's CURRENT content, or the FAQ you recommend, misleads renters or breaks the owner's policy
  (unverified facts, BLOCKED topics, legal claims). It is NOT the technical risk of editing the page.
* `MERGE`: put the proposed canonical URL's id first in `cannibalization.competing_ids` (at least one id) and say in
  `cannibalization.notes` which page should own the answer and why.
* `implicit_questions` may be filled for any status (EXPLICIT, NOT_RECOMMENDED included) with body-only candidates; keep it empty for NONE.
* Title / description length: do NOT flag the site-suffix length or generic over-length by itself (all posts share the same 31-char
  suffix; it is a template-wide finding measured deterministically). Use `title_meta.assessment = IMPROVE` only for content-specific problems:
  vague or clickbait title, keyword/intent mismatch, duplicate of another title/description, description that does not match the page.

## 7. Calibration anchors

* A post with the heading "Câu hỏi thường gặp" followed by five `###` questions each with a "Trả lời:" answer
  => `EXPLICIT`. If one answer states a legal rule as fact without a source (e.g. a foreigner may rent a 50cc
  without a licence "theo luật Việt Nam") => quality FAIR/WEAK, `unverifiable_claims` has a LEGAL entry,
  action `IMPROVE`, priority `P0` (legal claim inside a FAQ that would be marked up).
* A post whose section "Những câu hỏi nên hỏi trước khi đặt cọc" is a bullet list of questions the renter should
  ask the shop (no answers) => NOT an explicit FAQ. Judge the rest of the post: if it contains separable answers
  => `IMPLICIT`, else `NONE`. A deposit topic is high intent, but amounts/conditions must come only from
  approved facts => risk and `needs_fact_check` accordingly.
* A heading "Câu hỏi thường gặp khi sạc xe điện" followed by ONE paragraph that holds five run-in question/answer pairs => `EXPLICIT`
  (visible Q&A), quality `FAIR` (not separable), action `IMPROVE` (restructure without changing meaning). If the same heading only has a generic
  sentence and no real pairs => not explicit.
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

## 9. Working rules (speed and consistency)

* Facts already verified for the whole site — do NOT re-verify them: there is NO FAQ component and NO `FAQPage` JSON-LD anywhere; the
  head JSON-LD (Organization / LocalBusiness / WebSite / BlogPosting) and the post BreadcrumbList are valid on every audited page; robots.txt
  allows everything; every audited URL is in the sitemap and returns 200; the layout adds breadcrumbs, TOC, prev/next, 4 related posts and a
  CTA (see your pack); `data/business-facts.json` and `reports/factory/policy-conflicts.md` are the only fact sources.
* Read each source file fully, once. Do NOT read other posts in full to compare. For cannibalization use the titles/headings in the pack's
  `similar` list; at most 2 `grep -n '^#' <file>` calls on competing posts if a judgement really needs it.
* Process the items one by one. Keep each free-text field short; quotes are the evidence, prose is only the label.
* Write the single output file once at the end with the Write tool, run the validator, fix every error, and finish. Do not leave scratch
  files in the repository.
