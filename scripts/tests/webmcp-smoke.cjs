/* Run: node scripts/tests/webmcp-smoke.cjs — no external dependencies. */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('assets/js/webmcp.js', 'utf8');

function bootstrap(options = {}) {
  let registered = null;
  let fetchCount = 0;
  const records = options.records || [
    { title: 'Thuê xe máy Hà Nội', description: 'Kinh nghiệm thuê xe', url: '/thue-xe/' },
    { title: 'Hướng dẫn lái Honda Wave', description: 'Kỹ năng an toàn', url: '/xe-may/wave/' },
    { title: 'Độc hại', description: 'URL không tin cậy', url: '//other.example/bad' }
  ];
  const context = {
    AbortController,
    URL,
    Promise,
    document: {
      currentScript: { getAttribute: () => '/assets/data/search-recent.json' },
      modelContext: options.unsupported ? undefined : {
        registerTool: (tool) => { registered = tool; return Promise.resolve(); }
      }
    },
    window: {
      location: { href: 'https://blog.thuexemaynguyentu.com/', origin: 'https://blog.thuexemaynguyentu.com' },
      addEventListener: () => {}
    },
    fetch: async (url) => {
      fetchCount++;
      assert.equal(url, 'https://blog.thuexemaynguyentu.com/assets/data/search-recent.json');
      return { ok: true, json: async () => records };
    }
  };
  vm.runInNewContext(source, context, { filename: 'assets/js/webmcp.js' });
  return { get tool() { return registered; }, get fetchCount() { return fetchCount; } };
}

(async () => {
  assert.equal(bootstrap({ unsupported: true }).tool, null, 'No WebMCP: no registration');
  const app = bootstrap();
  assert.ok(app.tool, 'WebMCP tool registered');
  assert.equal(app.tool.name, 'ask_site');
  assert.equal(app.tool.annotations.readOnlyHint, true);
  const data = await app.tool.execute({ query: 'thuê xe' });
  assert.equal(data.matches_in_recent_index, 1);
  assert.equal(data.articles[0].url, 'https://blog.thuexemaynguyentu.com/thue-xe/');
  assert.equal(data.articles.length, 1);
  assert.equal(app.fetchCount, 1);
  const none = await app.tool.execute({ query: 'không có' });
  assert.equal(none.articles.length, 0);
  assert.equal(app.fetchCount, 1, 'Cached index');
  await assert.rejects(app.tool.execute({ query: ' ' }), /2 đến 120/);
  await assert.rejects(app.tool.execute({ query: 'x'.repeat(121) }), /2 đến 120/);
  const limited = bootstrap({ records: Array.from({ length: 301 }, (_, i) => ({ title: String(i), description: '', url: '/a/' })) });
  await assert.rejects(limited.tool.execute({ query: 'hi' }), /không hợp lệ/);
  console.log('WebMCP smoke tests PASS (no browser registration or native agent execution asserted).');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
