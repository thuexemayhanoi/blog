#!/usr/bin/env node
/**
 * Lightweight contract test for the public pricing pages (bảng giá chung, xe số, xe ga, xe 50cc).
 * Validates structural, responsive and no-price-invention invariants.
 * Browser visual checks remain a separate acceptance step.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const read = p => fs.readFileSync(path.join(root, p), 'utf8');
const pages = [
  ['bang-gia.md', ['Xe số', 'Xe ga', 'Xe 50cc']],
  ['bang-gia-xe-so.md', ['Xe số']],
  ['bang-gia-xe-ga.md', ['Xe ga']],
  ['bang-gia-xe-50cc.md', ['Xe 50cc']]
];

for (const [file, categories] of pages) {
  const source = read(file);
  assert.match(source, /^pricing_table:\s*true\s*$/m, file + ': pricing CSS enabled');
  assert.doesNotMatch(source, /<div class="pricing-card/, file + ': do not use homepage flex class');
  assert.equal((source.match(/\{% include pricing-rate-table\.html /g) || []).length, categories.length);
  for (const category of categories) {
    assert.ok(source.includes('category="' + category + '"'), file + ': missing ' + category);
  }
}

const include = read('_includes/pricing-rate-table.html');
assert.ok(include.includes('site.data.pricing.vehicles'), 'rates must use canonical YAML');
assert.ok(include.includes('where: "category", include.category'), 'must filter by category');
assert.match(include, /<table class="rental-rate-matrix__table">/);
assert.match(include, /<th scope="col">Dòng xe<\/th>/);
assert.match(include, /<th scope="row" class="rental-rate-matrix__vehicle">/);
for (const rate of ['day', 'week', 'month']) {
  assert.ok(include.includes('vehicle.rates.' + rate + '.min != nil'));
  assert.ok(include.includes('min=vehicle.rates.' + rate + '.min'));
}
// Giá null: nhãn `quote` của kỳ hạn (vd. "Báo giá riêng") hoặc unknown_label chung — không gõ tay số/nhãn trong template.
assert.ok(include.includes('site.data.pricing.unknown_label'), 'unknown-price label comes from pricing.yml');
assert.equal((include.match(/\.quote \| default: pricing_unknown/g) || []).length, 6,
  'both desktop table and mobile price cards must use the same unknown-price fallback');
assert.doesNotMatch(include, /\d{1,3}(?:\.\d{3})+/, 'no hard-coded VND amount in the shared table');
// Tiền đặt cọc: cột/hàng RIÊNG trên cả desktop và mobile, đọc từ vehicle.deposit (không cộng vào giá thuê).
assert.match(include, /<th scope="col">Tiền đặt cọc<\/th>/);
assert.match(include, /data-label="Tiền đặt cọc"/);
assert.equal((include.match(/vehicle\.deposit\.min != nil/g) || []).length, 2, 'deposit in desktop table and mobile cards');
assert.equal((include.match(/vehicle\.deposit_note \| default: pricing_unknown/g) || []).length, 2);
assert.match(include, /data-label="Theo ngày"/);
assert.match(include, /data-label="Theo tuần"/);
assert.match(include, /data-label="Theo tháng"/);
assert.match(include, /rental-rate-matrix__deposit/, 'deposit disclaimer stays visible');
assert.ok(include.includes('site.data.pricing.deposit_policy.separate'), 'deposit is stated as separate from rent');

const css = read('assets/css/pricing-table.css');
assert.match(css, /@media \(max-width:\s*767px\)/, 'phone rules');
assert.match(css, /@media \(min-width:\s*768px\) and \(max-width:\s*1199px\)/, 'tablet rules');
assert.match(css, /@media \(min-width:\s*1200px\)/, 'desktop rules');
assert.match(css, /border-right:\s*1px solid/, 'vertical gridlines');
assert.match(css, /border-bottom:\s*1px solid/, 'horizontal gridlines');
assert.match(css, /content:\s*attr\(data-label\)/, 'mobile rate labels');
assert.match(css, /overflow-x:\s*auto/, 'tablet overflow contained');
assert.match(css, /grid-template-columns:\s*minmax\(112px, 36%\) minmax\(0, 1fr\)/,
  'phone shows two columns within each pricing row');

const layout = read('_layouts/default.html');
assert.ok(layout.includes('if page.pricing_table'), 'only pricing pages load extra CSS');
assert.ok(layout.includes('/assets/css/pricing-table.css'), 'CSS stylesheet linked');
const priceData = read('_data/pricing.yml');
assert.match(priceData, /min:\s*150000/);
assert.match(priceData, /min:\s*200000/);
// iPhone portrait fix: never expose the four-column <table> to mobile Safari.
const mobileList = include.match(/<ul class="rental-rate-matrix__mobile"/g) || [];
assert.equal(mobileList.length, 1, 'mobile uses dedicated list markup, not a flex table');
assert.match(include, /<li class="rental-rate-matrix__mobile-card">/);
assert.match(include, /<dl class="rental-rate-matrix__mobile-rates">/);
assert.equal((include.match(/<div class="rental-rate-matrix__mobile-row">/g) || []).length, 4);
for (const label of ['Giá theo ngày', 'Giá theo tuần', 'Giá theo tháng', 'Tiền đặt cọc']) {
  assert.ok(include.includes('<dt>' + label + '</dt>'), 'missing mobile label ' + label);
}
assert.match(css, /PORTRAIT SAFARI FIX V2/);
assert.match(css, /\.rental-rate-matrix > \.rental-rate-matrix__scroll\s*\{\s*display: none !important;/);
assert.match(css, /\.rental-rate-matrix > \.rental-rate-matrix__mobile\s*\{\s*display: block;/);
assert.match(css, /\.rental-rate-matrix__mobile-row\s*\{[\s\S]*?grid-template-columns: minmax\(100px, 38%\) minmax\(0, 1fr\)/);
assert.match(css, /\.rental-rate-matrix__mobile-row dt\s*\{[\s\S]*?border-right: 1px solid/);
assert.match(css, /\.rental-rate-matrix__mobile-row\s*\{[\s\S]*?border-bottom: 1px solid/);
assert.match(layout, /pricing-table\.css[^"\n]*\?v=20261027-deposit/, 'cache-bust stylesheet (5-column table)');
console.log('PASS pricing table source/semantic/3-breakpoint/border/value and Safari portrait contracts');
