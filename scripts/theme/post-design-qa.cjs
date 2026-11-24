#!/usr/bin/env node
/* Post Design System — QA hiển thị cho MỌI bài viết, theo lô (docs/POST-DESIGN-SYSTEM.md).
 *
 * Chỉ ĐỌC một bản build Jekyll có sẵn (không sửa _posts/, matrix, data/, không gọi host ngoài):
 * tự phục vụ thư mục build qua HTTP cục bộ, mở từng bài bằng Chromium (Playwright) ở 3 bề rộng
 * (điện thoại 390, máy tính bảng 820, máy tính 1440) và ghi lại thành phần được áp dụng + lỗi.
 *
 *   node scripts/theme/post-design-qa.cjs --site _site --out <thư mục kết quả> \
 *        [--batch-size 100] [--concurrency 4] [--from-batch 1] [--to-batch N] [--only <chuỗi con của URL>] \
 *        [--urls <file: mỗi dòng một đường dẫn bài, vd. bộ 15 bài đại diện>] \
 *        [--matrix reports/theme-upgrade/post-design-matrix.xlsx] [--invariance <json>]
 *
 * Kết quả: <out>/inventory.json (danh sách bài + số lô), <out>/batch-NNN.json (mỗi lô ≤ batch-size bài).
 * Có --matrix thì sau MỖI lô gọi scripts/theme/post-design-matrix.py để cập nhật Excel Master Matrix.
 * Thoát 1 nếu có bài FAIL. Cần Playwright + Chromium đã cài sẵn trong môi trường chạy.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawnSync } = require('child_process');
const { chromium } = require('playwright');

const args = {};
process.argv.slice(2).forEach((v, i, arr) => {
  if (v.startsWith('--')) args[v.slice(2)] = arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true;
});
if (!args.site || !args.out) {
  console.error('usage: post-design-qa.cjs --site <build dir> --out <dir> [--batch-size 100] [--concurrency 4] [--matrix file.xlsx]');
  process.exit(2);
}
const SITE = path.resolve(String(args.site));
const OUT = path.resolve(String(args.out));
const BATCH = Math.min(100, Math.max(1, +(args['batch-size'] || 100)));
const CONC = Math.max(1, +(args.concurrency || 4));
const VIEWPORTS = [['mobile', 390, 844], ['tablet', 820, 1180], ['desktop', 1440, 900]];
const MIME = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.avif': 'image/avif', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.xml': 'application/xml',
  '.txt': 'text/plain; charset=utf-8', '.webmanifest': 'application/manifest+json' };

/* 1. Danh sách bài: mọi index.html của bản build có <article class="post-detail". */
function inventory() {
  const posts = [];
  (function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) { walk(full); continue; }
      if (entry.name !== 'index.html') continue;
      const fd = fs.openSync(full, 'r');
      const size = fs.fstatSync(fd).size;
      const buf = Buffer.alloc(size);
      fs.readSync(fd, buf, 0, size, 0);
      fs.closeSync(fd);
      if (buf.includes('<article class="post-detail"')) {
        posts.push('/' + path.relative(SITE, dir).split(path.sep).join('/') + '/');
      }
    }
  })(SITE);
  posts.sort();
  return posts;
}

/* 2. Máy chủ tĩnh cục bộ (URL gốc "/" như site thật). */
function serve() {
  const server = http.createServer((req, res) => {
    let rel;
    try { rel = decodeURIComponent(req.url.split('?')[0]); } catch (e) { rel = req.url.split('?')[0]; }
    let file = path.join(SITE, rel);
    if (!file.startsWith(SITE)) { res.writeHead(403); res.end(); return; }
    if (rel.endsWith('/')) file = path.join(file, 'index.html');
    fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(404); res.end('not found'); return; }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream' });
      res.end(data);
    });
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

/* 3. Đo trong trang. */
function measureStructure() {
  const article = document.querySelector('.post-detail');
  const body = article.querySelector('.article-body');
  const q = (sel, root) => (root || article).querySelectorAll(sel);
  const kinds = [];
  q('.pds-sec', body).forEach((sec) => {
    sec.className.split(/\s+/).forEach((c) => {
      const m = /^pds-sec--(.+)$/.exec(c);
      if (m && m[1] !== 'card') kinds.push(m[1] + (sec.classList.contains('pds-sec--card') ? ':card' : ''));
    });
  });
  const toc = article.querySelector('.article-toc');
  const accSections = q('[data-pds-acc]');
  const qaExpected = Array.prototype.filter.call(q('.pds-sec--qa', body), (sec) =>
    Array.prototype.filter.call(sec.children, (el) => el.tagName === 'H3').length >= 2).length +
    Array.prototype.filter.call(q('section.faq'), (sec) => sec.querySelectorAll('.faq-item h3').length >= 2).length;
  const canonical = document.querySelector('link[rel="canonical"]');
  const cls = (window.__pdsCls || 0);
  return {
    title: (document.querySelector('h1') || {}).textContent || '',
    canonical: canonical ? canonical.getAttribute('href') : '',
    date: ((article.querySelector('.post-date') || {}).textContent || '').trim(),
    crumbs: Array.prototype.map.call(q('.breadcrumb a', article.querySelector('.post-header') || article),
      (a) => a.textContent.trim()).filter(Boolean),
    dek: q('.post-dek').length,
    words: (body.textContent || '').trim().split(/\s+/).length,
    h1: document.querySelectorAll('h1').length,
    h2: q('h2', body).length,
    h3: q('h3', body).length,
    sections: q('.pds-sec', body).length,
    kinds: kinds,
    tables: q('table', body).length,
    tablesWrapped: q('.pds-table > table', body).length,
    quotes: q('blockquote', body).length,
    pros: q('.pds-pros, .pds-cons', body).length,
    lists: q('ul, ol', body).length,
    photos: q('.post-photos img').length,
    toc: toc ? 1 : 0,
    tocOpen: toc && toc.querySelector('details') ? (toc.querySelector('details').open ? 1 : 0) : -1,
    accExpected: qaExpected,
    accBuilt: accSections.length,
    accButtons: q('.pds-acc__btn').length,
    accOpen: q('.pds-acc__btn[aria-expanded="true"]').length,
    faqInclude: q('section.faq').length,
    legalNotice: q('.legal-notice').length,
    priceNotice: q('.price-notice').length,
    siblings: q('.topic-siblings').length,
    related: q('.article-related a').length,
    cta: q('.post-cta').length,
    progress: q('.reading-progress-bar').length,
    numbered: article.hasAttribute('data-pds-numbered') ? 1 : 0,
    cls: Math.round(cls * 10000) / 10000
  };
}
function measureLayout() {
  const doc = document.documentElement;
  const vw = doc.clientWidth;
  const article = document.querySelector('.post-detail');
  let wide = 0;
  let first = '';
  /* Phần tử nằm trong một khung cuộn/cắt có chủ đích (bảng, bảng giá) không tính là vượt khung;
     nhưng khung cuộn đó phải nằm gọn trong màn hình và được đếm riêng (scrollers) để soát. */
  const clipped = (el) => {
    for (let p = el.parentElement; p && p !== article.parentElement; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === 'auto' || ox === 'scroll' || ox === 'hidden' || ox === 'clip') return true;
    }
    return false;
  };
  let scrollers = 0;
  article.querySelectorAll('*').forEach((el) => {
    if (el.closest('.reading-progress')) return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    const ox = getComputedStyle(el).overflowX;
    if ((ox === 'auto' || ox === 'scroll') && el.scrollWidth > el.clientWidth + 1) scrollers += 1;
    if (r.right > vw + 1 || r.left < -1) {
      if (clipped(el)) return;
      wide += 1;
      if (!first) first = el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '');
    }
  });
  const toc = article.querySelector('.article-toc');
  const body = article.querySelector('.article-body');
  let overlap = 0;
  if (toc && body) {
    const a = toc.getBoundingClientRect();
    const b = body.getBoundingClientRect();
    const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    const iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (ix > 1 && iy > 1) overlap = 1;
  }
  return { overflow: Math.max(0, doc.scrollWidth - vw), wide: wide, first: first, tocOverlap: overlap, scrollers: scrollers };
}

async function checkPost(context, base, url) {
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
  page.on('response', (r) => { if (r.status() >= 400) errors.push('HTTP ' + r.status() + ' ' + r.url().replace(base, '').slice(0, 120)); });
  await page.addInitScript(() => {
    window.__pdsCls = 0;
    try {
      new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => { if (!entry.hadRecentInput) window.__pdsCls += entry.value; });
      }).observe({ type: 'layout-shift', buffered: true });
    } catch (e) { /* trình duyệt không hỗ trợ */ }
  });
  const row = { url: url };
  try {
    await page.goto(base + encodeURI(url), { waitUntil: 'load', timeout: 60000 });
    await page.waitForTimeout(250);
    Object.assign(row, await page.evaluate(measureStructure));
    for (const [name, width, height] of VIEWPORTS) {
      if (name !== 'mobile') { await page.setViewportSize({ width: width, height: height }); await page.waitForTimeout(60); }
      row[name] = await page.evaluate(measureLayout);
    }
  } catch (e) {
    errors.push('NAV ' + String(e).slice(0, 160));
  }
  await page.close();
  row.errors = errors;
  const issues = [];
  if (errors.length) issues.push('js/http: ' + errors[0]);
  if (row.h1 !== 1) issues.push('h1=' + row.h1);
  if (row.progress !== 1) issues.push('thiếu thanh tiến độ');
  if (row.tables !== row.tablesWrapped) issues.push('bảng chưa bọc khung cuộn');
  if (row.accBuilt !== row.accExpected) issues.push('accordion ' + row.accBuilt + '/' + row.accExpected);
  if (row.accBuilt && row.accOpen < row.accBuilt) issues.push('accordion không mở mục đầu');
  if (row.toc === 1 && row.tocOpen !== 0) issues.push('mục lục không thu gọn trên điện thoại');
  if (row.cls > 0.05) issues.push('CLS ' + row.cls);
  for (const [name] of VIEWPORTS) {
    const m = row[name];
    if (!m) { issues.push(name + ': không đo được'); continue; }
    if (m.overflow > 0) issues.push(name + ': tràn ngang ' + m.overflow + 'px');
    if (m.wide > 0) issues.push(name + ': ' + m.wide + ' phần tử vượt khung (' + m.first + ')');
    if (m.tocOverlap) issues.push(name + ': mục lục đè nội dung');
  }
  row.issues = issues;
  row.qa = issues.length ? 'FAIL' : 'PASS';
  return row;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  let posts = inventory();
  if (args.only) posts = posts.filter((u) => u.includes(String(args.only)));
  if (args.urls) {
    const wanted = new Set(fs.readFileSync(String(args.urls), 'utf8').split('\n').map((s) => s.trim()).filter(Boolean));
    const missing = [...wanted].filter((u) => !posts.includes(u));
    if (missing.length) { console.error('không có trong bản build: ' + missing.join(', ')); process.exit(2); }
    posts = posts.filter((u) => wanted.has(u));
  }
  const batches = [];
  for (let i = 0; i < posts.length; i += BATCH) batches.push(posts.slice(i, i + BATCH));
  fs.writeFileSync(path.join(OUT, 'inventory.json'), JSON.stringify({ site: SITE, total: posts.length, batch_size: BATCH,
    posts: posts.map((u, i) => ({ n: i + 1, batch: Math.floor(i / BATCH) + 1, url: u })) }));
  console.log('posts=' + posts.length + ' batches=' + batches.length + ' size<=' + BATCH);

  const server = await serve();
  const base = 'http://127.0.0.1:' + server.address().port;
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const from = Math.max(1, +(args['from-batch'] || 1));
  const to = Math.min(batches.length, +(args['to-batch'] || batches.length));
  let failed = 0;
  for (let b = from; b <= to; b += 1) {
    const urls = batches[b - 1];
    const rows = new Array(urls.length);
    let next = 0;
    const started = Date.now();
    await Promise.all(Array.from({ length: Math.min(CONC, urls.length) }, async () => {
      while (next < urls.length) {
        const i = next; next += 1;
        rows[i] = await checkPost(context, base, urls[i]);
      }
    }));
    const fails = rows.filter((r) => r.qa !== 'PASS');
    failed += fails.length;
    const name = 'batch-' + String(b).padStart(3, '0') + '.json';
    fs.writeFileSync(path.join(OUT, name), JSON.stringify({ batch: b, checked_at: new Date().toISOString(), posts: rows }));
    console.log('lô ' + String(b).padStart(3, '0') + '/' + batches.length + ': ' + rows.length + ' bài, PASS ' + (rows.length - fails.length) +
      ', FAIL ' + fails.length + ', ' + Math.round((Date.now() - started) / 100) / 10 + 's' +
      (fails.length ? ' -> ' + fails.slice(0, 3).map((r) => r.url + ' [' + r.issues.join('; ') + ']').join(' | ') : ''));
    if (args.matrix) {
      const cmd = [path.join(__dirname, 'post-design-matrix.py'), '--qa', OUT, '--out', String(args.matrix)];
      if (args.invariance) cmd.push('--invariance', String(args.invariance));
      const res = spawnSync('python3', cmd, { encoding: 'utf8' });
      if (res.status !== 0) { console.error('matrix update failed: ' + (res.stderr || res.stdout)); process.exitCode = 1; }
    }
  }
  await browser.close();
  server.close();
  console.log('xong: FAIL=' + failed);
  if (failed) process.exitCode = 1;
})();
