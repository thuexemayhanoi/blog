#!/usr/bin/env node
/**
 * Tests public smart-search against a fake DOM + same-origin JSON.
 * No external packages and no browser feature flags required.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../assets/js/site-search.js'), 'utf8');
const posts = [
  {
    title: 'Thủ tục thuê xe máy Hà Nội',
    description: 'Giấy tờ và đặt cọc cần thiết khi thuê xe.',
    url: '/thue-xe/thu-tuc/'
  },
  {
    title: 'Xe máy điện Hà Nội',
    description: 'Giá và bảo dưỡng xe điện.',
    url: '/xe-may/xe-dien/'
  },
  { title: 'Untrusted redirect', description: 'Thủ tục thuê xe',
    url: '//evil.example/' }
];

function makeElement(tag) {
  const handlers = {};
  return {
    tagName: tag,
    className: '',
    href: '',
    textContent: '',
    value: '',
    children: [],
    appendChild(child) { this.children.push(child); return child; },
    removeChild(child) {
      const i = this.children.indexOf(child);
      if (i !== -1) this.children.splice(i, 1);
    },
    get firstChild() { return this.children[0] || null; },
    addEventListener(name, fn) { handlers[name] = fn; },
    handlers
  };
}

function load(options = {}) {
  const form = makeElement('form');
  form.getAttribute = (name) => name === 'data-index-url'
    ? '/assets/data/webmcp-index.json' : null;
  const input = makeElement('input');
  const output = makeElement('ul');
  const status = makeElement('p');
  const google = makeElement('a');
  const elems = {
    'site-search-form': form,
    'site-search-query': input,
    'site-search-results': output,
    'site-search-status': status,
    'site-search-google': google
  };
  const winEvents = {};
  let count = 0;
  const window = {
    location: { pathname: '/tim-kiem/', search: options.query || '' },
    addEventListener(name, fn) { winEvents[name] = fn; },
    history: {
      replaceState(_, __, url) {
        window.location.search = url.slice(url.indexOf('?'));
      }
    }
  };
  const document = {
    getElementById: id => elems[id],
    createElement: makeElement
  };
  const fetch = async (url, settings) => {
    count += 1;
    assert.equal(url, '/assets/data/webmcp-index.json');
    assert.equal(settings.credentials, 'same-origin');
    return { ok: !options.fetchFail, json: async () => posts };
  };
  vm.runInNewContext(source, {
    window, document, fetch, URLSearchParams, Promise, Array, Set
  });
  return {
    input, output, status, form, google, winEvents, window,
    count: () => count
  };
}

async function flush() {
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
}

async function main() {
  const a = load({ query: '?q=thu%20tuc%20thue%20xe' });
  assert.equal(a.count(), 1, 'lazy fetch on initial non-empty query');
  await flush();
  assert.equal(a.output.children.length, 1, 'exclude unsafe URLs');
  assert.equal(a.output.children[0].children[0].href, '/thue-xe/thu-tuc/');
  assert.ok(a.status.textContent.includes('2 bài công khai'));
  assert.ok(a.google.href.includes('site%3Ablog.thuexemaynguyentu.com'));

  a.input.value = 'Tôi muốn biết thủ tục thuê xe máy Hà Nội cần giấy tờ gì?';
  let prevented = false;
  a.form.handlers.submit({ preventDefault() { prevented = true; } });
  await flush();
  assert.equal(prevented, true);
  assert.equal(a.output.children.length, 1, 'natural question should work');
  assert.equal(a.count(), 1, 'reuse already downloaded index');
  assert.ok(a.window.location.search.includes('q='));

  a.input.value = 'zzz không tồn tại';
  a.form.handlers.submit({ preventDefault() {} });
  await flush();
  assert.equal(a.output.children.length, 0);
  assert.ok(a.status.textContent.includes('Chưa tìm thấy'));

  const b = load();
  assert.equal(b.count(), 0, 'do not fetch on page load with no question');
  assert.equal(b.output.children.length, 0);

  const c = load({ query: '?q=xe%20dien', fetchFail: true });
  await flush();
  assert.ok(c.status.textContent.includes('Chưa tải được dữ liệu'));

  console.log('PASS iPhone-visible search tests: results, natural Vietnamese, safe links, lazy cache, fallback.');
}
main().catch(e => { console.error(e); process.exitCode = 1; });
