#!/usr/bin/env node
// validate-queue.js — campaign hanoi-seo-480 queue article validator
// Source of truth: git-hub-maintainer-v-2 Knowledge (OWNER-APPROVED facts).
// A validator must NEVER redefine business facts; this file only encodes them.
// Run: node scripts/validate-queue.js <dir-with-queue-md-files>
//
// OWNER-AUTHORITATIVE FACTS:
//   - Deposit: 2.000.000–5.000.000 VND depending on vehicle/case. NOT 1–3 million.
//   - Late return: 20.000 VND per late hour. More than 6 hours late may add one
//     additional full rental day, approx. 150.000–200.000 VND depending on vehicle.
//   - Honda Wave: ONLY 150.000đ/day approved. NO Wave weekly/monthly price
//     (including 700.000đ/tuần) unless the owner explicitly approves one.
//   - Nguyễn Tú does NOT provide motorbike insurance to renters.
//   - No refund entitlement for unused rental time (early return).
//   - Do NOT claim Nguyễn Tú retains passport/CCCD/identity documents.
//   - Do NOT claim helmets are included unless owner-approved (ask-first phrasing is fine).
//   - No free delivery, no fixed delivery fee, no guaranteed availability,
//     no guaranteed rescue/availability times.
//   - Rental prices: Wave 150k/day; Vision 200k/day, 800k–1M/week, 1.8–2M/month;
//     Air Blade 200k/day, 800k/week, 1.4M/month; Click/Mio 150k/day, 600–700k/week,
//     1–1.2M/month; xe điện / xe đạp điện / 50cc -> contact, never invent a price.
//   - Phone 0942 467 674; address 112 Nguyễn Văn Cừ, Bồ Đề, Long Biên, Hà Nội;
//     hours 09:00–21:00; no delivery outside opening hours.
'use strict';
const fs = require('fs');
const path = require('path');

const dir = process.argv[2] || '.';
const files = fs.readdirSync(dir)
  .filter(n => /^[0-9]{3}-.*\.md$/.test(n))
  .sort();
if (!files.length) { console.log('No queue article files found (queue empty) - validation skipped'); process.exit(0); }

const ALLOWED_PAGES = ['/bang-gia/','/bang-gia-xe-so/','/bang-gia-xe-ga/','/bang-gia-xe-50cc/','/bang-gia-xe-dien/','/lien-he/','/gioi-thieu/','/kinh-nghiem/','/du-lich/','/chia-se/'];
const ALLOWED_POSTS = ['2026-09-13-kinh-nghiem-thue-xe-may-ha-noi','2026-09-13-xe-so-xe-ga-hay-xe-50cc-nen-chon-loai-nao','2026-09-13-goi-y-kham-pha-ha-noi-bang-xe-may-cho-nguoi-moi'];
const UNSAFE = /khuyến mãi|giảm giá|ưu đãi|cam kết|miễn phí|24\/7|hài lòng|tin dùng|số 1|5 sao|hàng nghìn|vạn khách/i;
const ENG = /\b(the|and|with|for|you|your|not|this|that|from|have|will|when|what|which|they|their|been|more|than|into|also|some|only|very|much|make|take|like|just|over|under|after|before|while|there|would|could|should|where|itself|better|facing|itinerary|delegate|roughly|everywhere|walks|visibility|checklist|pre-check|fokus|gallery|pack|multi)\b/i;
const EXTRA = new Set('“”‘’·«»…—–'.split(''));
const PHONE = /0\d{2}[\s.]?\d{3}[\s.]?\d{3}/g;
const APPROVED_PHONE = '0942 467 674';

// --- business-fact gates -----------------------------------------------------
// Deposit lines (context: cọc). Wrong range -> ERROR. Approved range accepted.
const DEPOSIT_CONTEXT = /cọc/i;
const WRONG_DEPOSIT = [
  /1\.000\.000[^\n]{0,40}3\.000\.000/,
  /3\.000\.000[^\n]{0,40}1\.000\.000/,
  /một đến ba triệu/,
  /1\s?[–-]\s?3\s?triệu/,
  /từ một triệu đến ba triệu/,
];

// Late-fee lines (context: trễ/muộn + phí/giá/tiền or "phí trễ").
const LATE_CONTEXT = /(trễ|muộn)[^\n]{0,60}(phí|giá|tiền)|(phí|tiền)[^\n]{0,20}(trễ|muộn)|phí trễ/i;
const APPROVED_LATE_AMOUNTS = new Set(['20.000', '150.000', '200.000']);

// Honda Wave: only 150.000đ/day. No Wave weekly/monthly numeric price.
const WAVE_DAILY_ONLY = 150000;
const DEPOSIT_ENDPOINTS = new Set(['2.000.000', '5.000.000']);

// Insurance: Nguyễn Tú does NOT provide motorbike insurance.
// Helmet mentions are stripped first so "mũ/nón bảo hiểm" never triggers this gate.
const INSURANCE_CLAIM = /(cung cấp|đi kèm|bao gồm|bồi thường|chi trả|được tặng|covered)/i;
const INSURANCE_NEGATION = /(không|chưa|tự (chuẩn bị|cân nhắc|mua)|nên mua|mua bảo hiểm|tự lo)/i;

// Refund: no refund merely for returning the vehicle early / unused rental time.
const REFUND_PROMISE = /(hoàn|trả lại)[^\n]{0,60}(tiền thuê|khoản thuê|ngày chưa dùng|thời gian chưa dùng|phần (thuê|còn lại của khoản thuê))/i;
const REFUND_NEGATION = /(không|trừ khi|phải hỏi|tùy)/i;

// Identity-document retention claims (question forms and generic market
// statements about "some shops" are allowed; claims about this shop are not).
const ID_CLAIM = /(để lại (một )?(giấy tờ|cccd|hộ chiếu|căn cước|giấy tờ tùy thân))|((giữ|thu) (kèm |gốc |lại )?(giấy tờ|cccd|hộ chiếu|căn cước|giấy tờ tùy thân))|kèm theo việc để lại/i;
const ID_ALLOWED = /(hỏi|hay không|một số cửa hàng|nhiều cửa hàng|một vài|có nơi|tùy cửa hàng|tùy thỏa thuận)/i;

// Helmet inclusion claims (ask-first / conditional phrasing is allowed).
const HELMET_TERM = /(mũ|nón)\s*bảo hiểm/i;
const HELMET_CLAIM = /(luôn (đi kèm|được)|được (cửa hàng )?kèm theo|kèm sẵn|hỗ trợ sẵn|thường có [^\n]{0,15}đi kèm|đi kèm xe)/i;
const HELMET_ALLOWED = /(hỏi|nếu có|không\b|chưa)/i;

// Availability guarantees.
const AVAIL_GUARANTEE = /(chắc chắn có (xe|đúng xe|đúng dòng))|(luôn có sẵn xe)|(đảm bảo (có xe|sẵn xe|tình trạng xe))|(sẵn sàng phục vụ)|(không bao giờ hết xe)/i;

// Delivery: free or fixed-fee delivery (free is also banned by UNSAFE "miễn phí").
const DELIVERY_CLAIM = /(miễn phí[^\n]{0,25}giao)|(giao[^\n]{0,15}miễn phí)|(phí giao[^\n]{0,20}\d)|(giao xe tận nơi miễn)/i;

// Amounts allowed anywhere (rental prices, deposits, late fees, monthly, derived, small cash).
const KNOWN_AMOUNTS = new Set([
  '1.000','2.000','3.000','5.000','10.000','15.000','20.000','50.000','100.000',
  '150.000','200.000','300.000','350.000','400.000','450.000','600.000','700.000',
  '750.000','800.000','1.000.000','1.200.000','1.400.000','1.500.000','1.800.000',
  '2.000.000','5.000.000','2.100.000','4.000.000','6.000.000',
]);

// Split a line into sentences (numbers like 150.000đ do not end a sentence
// because the dot is never followed by whitespace).
function sentences(line) {
  return line.split(/(?<=[.!?:;])\s+/).filter(Boolean);
}

const titles = new Map();
const slugs = new Map();
let passed = 0, failed = 0;

for (const n of files) {
  const txt = fs.readFileSync(path.join(dir, n), 'utf8');
  const errs = [], warns = [];
  const lines = txt.split('\n');

  // 1. character whitelist
  for (let i = 0; i < txt.length; i++) {
    const c = txt.codePointAt(i);
    const ch = txt[i];
    const ok = ch === '\n' || ch === '\t' || EXTRA.has(ch) ||
      (c >= 0x20 && c <= 0x24F) || (c >= 0x1E00 && c <= 0x1EFF);
    if (!ok) { errs.push('bad char U+' + c.toString(16) + ' at index ' + i); break; }
  }

  // 2. front matter: 11 lines
  if (lines[0] !== '---' || lines[10] !== '---') errs.push('front matter must be 11 lines (--- ... ---)');
  const fm = lines.slice(0, 11);
  if (!/^layout: post$/.test(fm[1] || '')) errs.push('line2 layout: post');
  if (!/^title: ".+"$/.test(fm[2] || '')) errs.push('line3 title quoted');
  if (!/^author: "Nguyễn Tú"$/.test(fm[3] || '')) errs.push('line4 author Nguyễn Tú');
  if (!/^description: ".+"$/.test(fm[4] || '')) errs.push('line5 description quoted');
  if (!/^categories: \[(Du lịch|Kinh nghiệm|Chia sẻ)\]$/.test(fm[5] || '')) errs.push('line6 categories');
  if (!/^lang: vi$/.test(fm[6] || '')) errs.push('line7 lang vi');
  const tagCount = ((fm[7] || '').match(/^tags: \[(.+)\]$/)||[])[1];
  if (!tagCount) errs.push('line8 tags bracket');
  else { const t = tagCount.split(',').map(s=>s.trim()).filter(Boolean); if (t.length < 4 || t.length > 5) errs.push('line8 tags must be 4-5, got ' + t.length); }
  if (!/^reading_time: 9$/.test(fm[8] || '')) errs.push('line9 reading_time: 9');
  if (!/^campaign: hanoi-seo-480$/.test(fm[9] || '')) errs.push('line10 campaign');
  if (fm.some(l => /^date:/.test(l))) errs.push('front matter must not contain date:');

  // 3. body word count
  const body = lines.slice(11).join('\n');
  const words = body.split(/\s+/).filter(Boolean).length;
  if (words < 1500 || words > 2000) errs.push('body words ' + words + ' outside 1500-2000');

  // 4. links
  const links = [...body.matchAll(/\]\(([^)]*)\)/g)].map(m => m[1]);
  if (links.length < 2 || links.length > 5) errs.push('links ' + links.length + ' outside 2-5');
  for (const l of links) {
    const page = l.match(/'([^']+)'/);
    const post = l.match(/post_url\s+([^\s}]+)/);
    if (post) { if (!ALLOWED_POSTS.includes(post[1])) errs.push('bad post link ' + post[1]); }
    else if (page) { if (!ALLOWED_PAGES.includes(page[1])) errs.push('bad page link ' + page[1]); }
    else errs.push('unrecognized link ' + l);
  }

  // 5. unsafe claims, 6. English junk
  const um = txt.match(UNSAFE); if (um) errs.push('UNSAFE phrase: ' + um[0]);
  const em = txt.match(ENG); if (em) errs.push('ENG junk: ' + em[0]);

  // 7. phone numbers
  for (const p of txt.match(PHONE) || []) {
    if (p !== APPROVED_PHONE && p.replace(/[.\s]/g,'') !== '0942467674') errs.push('phone ' + p + ' != approved');
  }

  // 8. Liquid balance, no http, no newline-split Liquid
  const o1 = (body.match(/\{\{/g)||[]).length, c1 = (body.match(/\}\}/g)||[]).length;
  const o2 = (body.match(/\{%/g)||[]).length, c2 = (body.match(/%\}/g)||[]).length;
  if (o1 !== c1) errs.push('Liquid {{ }} imbalance ' + o1 + '/' + c1);
  if (o2 !== c2) errs.push('Liquid {% %} imbalance ' + o2 + '/' + c2);
  if (/http/.test(body)) errs.push('http link present');
  if (/\]\(\{\n|%\n\s*post_url|\{\n%/.test(body)) errs.push('newline-split Liquid tag');

  // 9. unique titles/slugs
  const title = (fm[2]||'').replace(/^title: "|"$/g,'').toLowerCase();
  const slug = n.replace(/^[0-9]{3}-/,'').replace(/\.md$/,'');
  if (titles.has(title)) errs.push('duplicate title with ' + titles.get(title));
  if (slugs.has(slug)) errs.push('duplicate slug with ' + slugs.get(slug));
  titles.set(title, n); slugs.set(slug, n);

  // 10. deposit fact gate
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i];
    if (!DEPOSIT_CONTEXT.test(L)) continue;
    for (const re of WRONG_DEPOSIT) {
      if (re.test(L)) errs.push('WRONG DEPOSIT RANGE line ' + (i+1) + ': ' + L.slice(0,80));
    }
    const amounts = L.match(/\d{1,3}(?:\.\d{3})+/g) || [];
    for (const a of amounts) {
      if (['1.000.000','2.000.000','3.000.000','5.000.000'].includes(a)) continue; // range endpoints
      if (!KNOWN_AMOUNTS.has(a)) warns.push('UNUSUAL ' + a + ' in deposit context line ' + (i+1));
    }
  }

  // 11. late-fee fact gate: approved amounts accepted; other amounts on late-fee lines are errors
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i];
    if (!LATE_CONTEXT.test(L)) continue;
    const amounts = L.match(/\d{1,3}(?:\.\d{3})+/g) || [];
    for (const a of amounts) {
      if (APPROVED_LATE_AMOUNTS.has(a)) continue;
      errs.push('UNSUPPORTED LATE FEE ' + a + ' line ' + (i+1) + ': ' + L.slice(0,80));
      break;
    }
  }

  // 12. amount sanity warnings
  for (const a of body.match(/\d{1,3}(?:\.\d{3})+/g) || []) {
    if (!KNOWN_AMOUNTS.has(a)) warns.push('UNUSUAL amount ' + a);
  }

  // 13. Honda Wave daily-only price gate (sentence level)
  for (let i = 0; i < lines.length; i++) {
    for (const s of sentences(lines[i])) {
      if (!/wave/i.test(s)) continue;
      if (/700\.000/.test(s)) { errs.push('WAVE 700.000đ/tuần NOT APPROVED line ' + (i+1) + ': ' + s.slice(0,80)); continue; }
      if (!/(tuần|tháng)/i.test(s)) continue;
      const amounts = (s.match(/\d{1,3}(?:\.\d{3})+/g) || [])
        .filter(a => !DEPOSIT_ENDPOINTS.has(a) && a !== '150.000');
      if (amounts.length) errs.push('WAVE weekly/monthly numeric price NOT APPROVED line ' + (i+1) + ': ' + s.slice(0,80));
    }
  }

  // 14. insurance gate (helmet terms stripped so "mũ bảo hiểm" cannot trigger it)
  for (let i = 0; i < lines.length; i++) {
    const L2 = lines[i].replace(/(mũ|nón)\s*bảo hiểm/gi, '');
    if (!/bảo hiểm/i.test(L2)) continue;
    if (INSURANCE_CLAIM.test(L2) && !INSURANCE_NEGATION.test(L2)) {
      errs.push('INSURANCE PROVISION CLAIM line ' + (i+1) + ': ' + lines[i].slice(0,80));
    }
  }

  // 15. unused-rental-time refund gate
  for (let i = 0; i < lines.length; i++) {
    if (REFUND_PROMISE.test(lines[i]) && !REFUND_NEGATION.test(lines[i])) {
      errs.push('REFUND PROMISE (unused rental time) line ' + (i+1) + ': ' + lines[i].slice(0,80));
    }
  }

  // 16. identity-document retention gate
  for (let i = 0; i < lines.length; i++) {
    if (ID_CLAIM.test(lines[i]) && !ID_ALLOWED.test(lines[i])) {
      errs.push('ID RETENTION CLAIM line ' + (i+1) + ': ' + lines[i].slice(0,80));
    }
  }

  // 17. helmet inclusion gate
  for (let i = 0; i < lines.length; i++) {
    const L = lines[i];
    if (HELMET_TERM.test(L) && HELMET_CLAIM.test(L) && !HELMET_ALLOWED.test(L)) {
      errs.push('HELMET INCLUSION CLAIM line ' + (i+1) + ': ' + L.slice(0,80));
    }
  }

  // 18. availability guarantee gate
  for (let i = 0; i < lines.length; i++) {
    if (AVAIL_GUARANTEE.test(lines[i])) {
      errs.push('AVAILABILITY GUARANTEE line ' + (i+1) + ': ' + lines[i].slice(0,80));
    }
  }

  // 19. delivery fee gate
  for (let i = 0; i < lines.length; i++) {
    if (DELIVERY_CLAIM.test(lines[i])) {
      errs.push('DELIVERY FEE CLAIM line ' + (i+1) + ': ' + lines[i].slice(0,80));
    }
  }

  if (errs.length) { failed++; console.log('FAIL ' + n); errs.forEach(e => console.log('   - ' + e)); }
  else { passed++; console.log('PASS ' + n); }
  warns.forEach(w => console.log('   WARN ' + n + ': ' + w));
}
console.log('TOTAL ' + files.length + ' PASSED ' + passed + ' FAILED ' + failed);
process.exit(failed ? 1 : 0);
