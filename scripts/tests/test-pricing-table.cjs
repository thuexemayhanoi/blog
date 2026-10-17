#!/usr/bin/env node
/**
 * Lightweight contract test for the three public pricing pages.
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
  ['bang-gia.md', ['Xe số', 'Xe ga']],
  ['bang-gia-xe-so.md', ['Xe số']],
  ['bang-gia-xe-ga.md', ['Xe ga']]
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
assert.equal((include.match(/Liên hệ báo giá/g) || []).length, 3,
  'unknown values must be explicitly unknown, never 0 or invented');
assert.match(include, /data-label="Theo ngày"/);
assert.match(include, /data-label="Theo tuần"/);
assert.match(include, /data-label="Theo tháng"/);
assert.match(include, /rental-rate-matrix__deposit/, 'deposit disclaimer stays visible');

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
console.log('PASS pricing table source/semantic/3-breakpoint/border/value contracts');
