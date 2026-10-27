#!/usr/bin/env node
/**
 * Hợp đồng dữ liệu giá + máy tính giá (không phụ thuộc thư viện ngoài).
 *  1. _data/pricing.yml đúng bảng giá và tiền cọc chủ xe duyệt (27/10/2026); giá chưa công bố là null.
 *  2. data/business-facts.json (approved_pricing) khớp _data/pricing.yml — một nguồn số liệu, không lệch.
 *  3. assets/js/calculator.js: ước tính theo ngày/tuần/tháng đúng; tiền cọc hiển thị riêng, KHÔNG cộng vào giá thuê;
 *     dòng xe "báo giá riêng" tuần/tháng có ghi chú thay vì giả làm giá tuần/tháng.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const read = p => fs.readFileSync(path.join(root, p), 'utf8');

// Bộ đọc YAML tối giản cho đúng tập con dùng trong _data/pricing.yml: map/list lồng nhau theo thụt lề,
// giá trị vô hướng là số, null, true/false hoặc chuỗi (có/không ngoặc kép). Dòng chú thích/rỗng bị bỏ qua.
function parseYaml(text) {
  const lines = text.split('\n')
    .map(raw => raw.replace(/\s+#.*$/, '').replace(/^\s*#.*$/, ''))
    .filter(l => l.trim() !== '')
    .map(l => ({ indent: l.match(/^ */)[0].length, text: l.trim() }));
  let i = 0;
  const scalar = v => {
    if (v === 'null' || v === '~') return null;
    if (v === 'true') return true;
    if (v === 'false') return false;
    if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
    const q = v.match(/^"(.*)"$/);
    return q ? q[1] : v;
  };
  function block(indent) {
    if (lines[i].text.startsWith('- ')) {
      const list = [];
      while (i < lines.length && lines[i].indent === indent && lines[i].text.startsWith('- ')) {
        const itemIndent = indent + 2;
        lines[i] = { indent: itemIndent, text: lines[i].text.slice(2) };
        list.push(map(itemIndent));
      }
      return list;
    }
    return map(indent);
  }
  function map(indent) {
    const obj = {};
    while (i < lines.length && lines[i].indent === indent && !lines[i].text.startsWith('- ')) {
      const m = lines[i].text.match(/^([\w-]+):\s*(.*)$/);
      assert.ok(m, 'unsupported YAML line: ' + lines[i].text);
      i++;
      if (m[2] !== '') obj[m[1]] = scalar(m[2]);
      else obj[m[1]] = (i < lines.length && lines[i].indent > indent) ? block(lines[i].indent)
        : (i < lines.length && lines[i].indent === indent && lines[i].text.startsWith('- ')) ? block(indent) : null;
    }
    return obj;
  }
  return block(0);
}

const pricing = parseYaml(read('_data/pricing.yml'));
const byId = Object.fromEntries(pricing.vehicles.map(v => [v.id, v]));
const r = (min, max) => ({ min, max: max === undefined ? min : max });

// 1. Bảng giá chủ xe duyệt (VNĐ). Tiền cọc min/max; null = chưa công bố (hiển thị nhãn, không đoán số).
const APPROVED = {
  'honda-wave': { day: r(150000), week: r(700000), month: r(900000, 1200000), deposit: r(2000000, 3000000) },
  'honda-vision': { day: r(200000), week: r(1000000), month: r(1800000, 2000000), deposit: r(4000000, 5000000) },
  'honda-airblade': { day: r(200000), week: r(1000000), month: r(1500000), deposit: r(3000000) },
  'honda-click': { day: r(150000), week: r(700000), month: r(900000, 1200000), deposit: r(2000000) },
  'xe-tay-ga-50cc': { day: r(200000), week: r(null), month: r(null), deposit: r(4000000) },
  'electric-bike': { day: r(null), week: r(null), month: r(null), deposit: r(null) },
  'electric-scooter': { day: r(null), week: r(null), month: r(null), deposit: r(null) },
};
assert.deepEqual(Object.keys(byId).sort(), Object.keys(APPROVED).sort(), 'vehicle ids');
for (const [id, want] of Object.entries(APPROVED)) {
  const v = byId[id];
  for (const p of ['day', 'week', 'month']) {
    assert.deepEqual({ min: v.rates[p].min, max: v.rates[p].max }, want[p], id + ' ' + p);
  }
  assert.deepEqual({ min: v.deposit.min, max: v.deposit.max }, want.deposit, id + ' deposit');
  if (v.deposit.min === null) assert.equal(v.deposit_note, 'Xác nhận theo mẫu xe', id + ' deposit note');
}
assert.equal(byId['xe-tay-ga-50cc'].rates.week.quote, 'Báo giá riêng');
assert.equal(byId['xe-tay-ga-50cc'].rates.month.quote, 'Báo giá riêng');
assert.equal(pricing.unknown_label, 'Liên hệ để xác nhận');
assert.deepEqual([pricing.deposit_policy.min, pricing.deposit_policy.max], [2000000, 5000000]);
const deposits = Object.values(APPROVED).filter(a => a.deposit.min !== null);
assert.equal(Math.min(...deposits.map(a => a.deposit.min)), pricing.deposit_policy.min, 'policy min = min approved deposit');
assert.equal(Math.max(...deposits.map(a => a.deposit.max)), pricing.deposit_policy.max, 'policy max = max approved deposit');

// 2. business-facts.json khớp pricing.yml ("a - b" là khoảng, số đơn là min = max, null là chưa công bố).
const facts = JSON.parse(read('data/business-facts.json'));
const NAME = {
  'Honda Wave': 'honda-wave', 'Honda Vision': 'honda-vision', 'Honda Air Blade': 'honda-airblade',
  'Honda Click / Yamaha Mio': 'honda-click', 'Xe tay ga 50cc': 'xe-tay-ga-50cc',
  'Xe máy điện': 'electric-bike', 'Xe đạp điện': 'electric-scooter',
};
const asRange = x => {
  if (x === null || x === undefined) return r(null);
  if (typeof x === 'number') return r(x);
  const m = String(x).match(/^(\d+)\s*-\s*(\d+)$/);
  return m ? r(Number(m[1]), Number(m[2])) : r(null);
};
assert.deepEqual(Object.keys(facts.approved_pricing).sort(), Object.keys(NAME).sort(), 'approved_pricing names');
for (const [name, id] of Object.entries(NAME)) {
  const f = facts.approved_pricing[name];
  for (const p of ['day', 'week', 'month']) assert.deepEqual(asRange(f[p]), APPROVED[id][p], name + ' ' + p + ' (business-facts)');
  assert.deepEqual(asRange(f.deposit), APPROVED[id].deposit, name + ' deposit (business-facts)');
}
assert.equal(facts.deposit_policy.range, '2000000 - 5000000');
assert.equal(facts.deposit_policy.refund, pricing.deposit_policy.refund, 'refund wording from one approved text');

// 3. Máy tính giá: nạp calculator.js với DOM giả (không có form => init không làm gì), gọi các hàm thuần.
const elements = {};
const document = {
  readyState: 'complete',
  querySelector: sel => elements[sel] || null,
  querySelectorAll: () => [],
  addEventListener: () => {},
  createElement: () => ({ className: '', innerHTML: '' }),
};
const window = { NGUYEN_TU_PRICING: pricing };
vm.runInNewContext(read('assets/js/calculator.js'), { window, document });
const C = window.Calculator;
assert.ok(C, 'calculator exported');
const estimate = (id, days) => [C._calculateEstimate(byId[id], days, 'min'), C._calculateEstimate(byId[id], days, 'max')];

// Ngày / tuần / tháng: chọn tổ hợp rẻ nhất trên giá đã duyệt (công thức không đổi).
assert.deepEqual(estimate('honda-wave', 1), [150000, 150000]);
assert.deepEqual(estimate('honda-wave', 7), [700000, 700000]);
assert.deepEqual(estimate('honda-wave', 30), [900000, 1200000]); // gói tháng rẻ hơn 4 tuần + 2 ngày
assert.deepEqual(estimate('honda-vision', 7), [1000000, 1000000]);
assert.deepEqual(estimate('honda-vision', 30), [1800000, 2000000]);
assert.deepEqual(estimate('honda-airblade', 30), [1500000, 1500000]);
assert.deepEqual(estimate('honda-click', 3), [450000, 450000]);
// 50cc: chỉ có giá ngày; tuần/tháng "Báo giá riêng" → ước tính theo ngày + ghi chú rõ ràng.
assert.deepEqual(estimate('xe-tay-ga-50cc', 7), [1400000, 1400000]);
assert.equal(C._missingPeriodNote(byId['xe-tay-ga-50cc'], 3), '');
assert.match(C._missingPeriodNote(byId['xe-tay-ga-50cc'], 7), /giá theo tuần: Báo giá riêng/);
assert.match(C._missingPeriodNote(byId['xe-tay-ga-50cc'], 30), /giá theo tuần: Báo giá riêng; giá theo tháng: Báo giá riêng/);
assert.equal(C._missingPeriodNote(byId['honda-wave'], 30), '');
// Xe điện: chưa công bố giá → không có ước tính, không đoán số.
assert.equal(C._hasValidPrices(byId['electric-bike']), false);
assert.deepEqual(estimate('electric-scooter', 7), [null, null]);

// Tiền cọc: hiển thị riêng từ dữ liệu, KHÔNG cộng vào giá thuê ước tính.
const fmt = n => n.toLocaleString('vi-VN') + 'đ';
assert.equal(C._depositText(byId['honda-wave']), fmt(2000000) + ' - ' + fmt(3000000));
assert.equal(C._depositText(byId['honda-vision']), fmt(4000000) + ' - ' + fmt(5000000));
assert.equal(C._depositText(byId['honda-airblade']), fmt(3000000));
assert.equal(C._depositText(byId['honda-click']), fmt(2000000));
assert.equal(C._depositText(byId['xe-tay-ga-50cc']), fmt(4000000));
assert.equal(C._depositText(byId['electric-bike']), 'Xác nhận theo mẫu xe');
// Hiển thị: _calculate ghi giá thuê vào #estimated-price và cọc vào #estimated-deposit (hai ô khác nhau).
const mk = () => ({ textContent: '', hidden: false, style: {}, innerHTML: '', appendChild() {} });
Object.assign(elements, {
  '#vehicle-select': { value: 'honda-wave' }, '#days-input': { value: '7' },
  '#estimated-price': mk(), '#estimated-deposit': mk(), '#price-breakdown': mk(), '#price-note': mk(),
});
C._calculate();
assert.equal(elements['#estimated-price'].textContent, fmt(700000), 'rent shown alone');
assert.equal(elements['#estimated-deposit'].textContent, fmt(2000000) + ' - ' + fmt(3000000), 'deposit shown separately');
assert.equal(elements['#price-note'].hidden, true);
elements['#vehicle-select'].value = 'xe-tay-ga-50cc';
C._calculate();
assert.equal(elements['#estimated-price'].textContent, fmt(1400000));
assert.equal(elements['#estimated-deposit'].textContent, fmt(4000000));
assert.equal(elements['#price-note'].hidden, false);
elements['#vehicle-select'].value = 'electric-bike';
C._calculate();
assert.equal(elements['#estimated-price'].textContent, 'Liên hệ Nguyễn Tú để kiểm tra giá hiện tại');
assert.equal(elements['#estimated-deposit'].textContent, 'Xác nhận theo mẫu xe');

console.log('PASS pricing data (owner table, business-facts sync) + calculator (day/week/month, deposit separate, quote notes)');
