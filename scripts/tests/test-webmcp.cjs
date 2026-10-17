#!/usr/bin/env node
/**
 * No dependencies: exercises the exact browser WebMCP tool in a VM.
 * A fake registry does NOT prove native browser compatibility.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(
  path.join(__dirname, '../../assets/js/webmcp-ask-site.js'), 'utf8'
);
const rows = [
  {
    title: 'Thủ tục thuê xe máy Hà Nội',
    description: 'Hướng dẫn đặt cọc và giấy tờ khi thuê xe máy.',
    url: '/thue-xe/thu-tuc/'
  },
  {
    title: 'Kinh nghiệm du lịch Hà Nội',
    description: 'Cung đường xe máy cuối tuần.',
    url: '/du-lich/'
  },
  {
    title: 'Xe máy điện tại Hà Nội',
    description: 'So sánh xe điện và xe xăng.',
    url: '/xe-may/xe-dien/'
  },
  { title: 'Không an toàn', description: 'Thuê xe máy', url: '//bad.example/' },
  { title: 'URL giả', description: 'Thuê xe máy', url: '/bad?q=1' }
];

function init(suppliedRows, options = {}) {
  let tool, registrationOptions, fetchCount = 0;
  const listeners = {};
  const context = {
    async registerTool(definition, registration) {
      tool = definition;
      registrationOptions = registration;
      if (options.rejectRegistration) throw new Error('registration denied');
    }
  };
  const document = {
    currentScript: { getAttribute: (name) =>
      name === 'data-index-url' ? '/assets/data/webmcp-index.json' : null
    },
    modelContext: options.unsupported ? undefined : context
  };
  const window = {
    location: { origin: 'https://blog.example.com' },
    addEventListener: (name, handler) => { listeners[name] = handler; }
  };
  const fetch = async (url, settings) => {
    fetchCount += 1;
    assert.equal(url, '/assets/data/webmcp-index.json');
    assert.equal(settings.credentials, 'same-origin');
    assert.ok(settings.signal);
    if (options.failFetch) return { ok: false, status: 503 };
    return { ok: true, json: async () => suppliedRows };
  };
  vm.runInNewContext(source, {
    document, window, navigator: {}, fetch, AbortController, Promise,
    Array, Set, console
  }, { filename: 'webmcp-ask-site.js' });
  return {
    getTool: () => tool,
    getOptions: () => registrationOptions,
    getFetchCount: () => fetchCount,
    listeners
  };
}

async function main() {
  const a = init(rows);
  const tool = a.getTool();
  assert.ok(tool, 'tool must register when modelContext exists');
  assert.equal(tool.name, 'ask_site');
  assert.equal(tool.annotations.readOnlyHint, true);
  assert.equal(tool.annotations.untrustedContentHint, true);
  assert.deepEqual(Array.from(tool.inputSchema.required), ['question']);
  assert.equal(a.getFetchCount(), 0, 'do not download the index on page load');

  const result = await tool.execute({ question: 'thu tuc thue xe' }, {
    signal: new AbortController().signal
  });
  assert.equal(result.indexed_articles, 3, 'unsafe URLs must be excluded');
  assert.equal(result.matched_articles, 1);
  assert.equal(result.sources[0].url,
    'https://blog.example.com/thue-xe/thu-tuc/');
  assert.ok(result.sources[0].excerpt.includes('đặt cọc'));

  const accented = await tool.execute({ question: 'Thủ tục thuê xe' }, {
    signal: new AbortController().signal
  });
  assert.equal(accented.sources[0].title, 'Thủ tục thuê xe máy Hà Nội');
  assert.equal(a.getFetchCount(), 1, 'cache metadata once per page');

  const noHit = await tool.execute({ question: 'loai xe khong ton tai' }, {});
  assert.equal(noHit.matched_articles, 0);
  assert.equal(noHit.sources.length, 0);

  await assert.rejects(tool.execute({ question: 'x' }, {}), /2 đến 120/);
  await assert.rejects(tool.execute({ question: 'a'.repeat(121) }, {}), /2 đến 120/);
  const aborted = new AbortController();
  aborted.abort();
  await assert.rejects(tool.execute({ question: 'xe may' }, {
    signal: aborted.signal
  }), /Đã hủy/);
  assert.equal(a.getFetchCount(), 1);

  assert.ok(a.getOptions().signal);
  a.listeners.pagehide();
  assert.equal(a.getOptions().signal.aborted, true, 'tool must release on exit');

  const unsupported = init(rows, { unsupported: true });
  assert.equal(unsupported.getTool(), undefined);
  assert.equal(unsupported.getFetchCount(), 0);

  const failed = init(rows, { failFetch: true });
  await assert.rejects(failed.getTool().execute({ question: 'xe máy' }, {
    signal: new AbortController().signal
  }), /Không tải/);

  const rejected = init(rows, { rejectRegistration: true });
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(rejected.getOptions().signal.aborted, true);

  console.log('PASS WebMCP ask_site mock tests: registration, search, safety, cancellation, no-op.');
}

main().catch((err) => { console.error(err); process.exitCode = 1; });
