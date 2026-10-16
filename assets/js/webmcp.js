/*
 * WebMCP read-only article discovery for Nguyen Tu Blog.
 * No API keys, third-party requests, DOM scraping, or client-side AI.
 * Only browsers supporting document.modelContext receive this tool.
 */
(function () {
  'use strict';

  var modelContext = document.modelContext;
  if (!modelContext || typeof modelContext.registerTool !== 'function') return;

  var script = document.currentScript;
  var indexPath = script && script.getAttribute('data-index-url');
  if (!indexPath) return;

  var indexUrl;
  try {
    indexUrl = new URL(indexPath, window.location.href);
    if (indexUrl.origin !== window.location.origin) return;
  } catch (_) {
    return;
  }

  var controller = new AbortController();
  var cachedPosts = null;
  var MAX_POSTS = 300;
  var MAX_RESULTS = 8;

  function normalize(value) {
    var text = String(value || '').toLowerCase();
    if (typeof text.normalize === 'function') {
      text = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }
    return text.replace(/đ/g, 'd').replace(/\s+/g, ' ').trim();
  }

  function safePost(post) {
    if (!post || typeof post.url !== 'string' ||
        !post.url.startsWith('/') || post.url.startsWith('//')) return null;
    try {
      var url = new URL(post.url, window.location.origin);
      if (url.origin !== window.location.origin) return null;
      return {
        title: String(post.title || '').slice(0, 240),
        description: String(post.description || '').slice(0, 500),
        url: url.href
      };
    } catch (_) {
      return null;
    }
  }

  async function loadPublishedPosts(signal) {
    if (cachedPosts) return cachedPosts;
    var response = await fetch(indexUrl.href, {
      credentials: 'same-origin',
      signal: signal
    });
    if (!response.ok) throw new Error('Không tải được chỉ mục bài viết.');
    var data = await response.json();
    if (!Array.isArray(data) || data.length > MAX_POSTS) {
      throw new Error('Chỉ mục bài viết không hợp lệ.');
    }
    cachedPosts = data.map(safePost).filter(Boolean);
    return cachedPosts;
  }

  async function askSite(input, context) {
    var query = input && typeof input.query === 'string' ? input.query.trim() : '';
    if (query.length < 2 || query.length > 120) {
      throw new Error('Từ khóa tìm kiếm phải dài từ 2 đến 120 ký tự.');
    }

    var normalizedQuery = normalize(query);
    var terms = normalizedQuery.split(' ').filter(Boolean);
    if (!terms.length) throw new Error('Vui lòng nhập từ khóa hợp lệ.');

    var posts = await loadPublishedPosts(context && context.signal);
    var ranked = posts.map(function (post, index) {
      var title = normalize(post.title);
      var description = normalize(post.description);
      var combined = title + ' ' + description;
      if (!terms.every(function (term) { return combined.includes(term); })) return null;
      var score = 2;
      if (title.includes(normalizedQuery)) score += 10;
      if (description.includes(normalizedQuery)) score += 3;
      return { post: post, score: score, index: index };
    }).filter(Boolean);

    ranked.sort(function (a, b) { return b.score - a.score || a.index - b.index; });

    return {
      query: query,
      matches_in_recent_index: ranked.length,
      articles: ranked.slice(0, MAX_RESULTS).map(function (item) { return item.post; }),
      scope: 'Chỉ tiêu đề và mô tả của tối đa 300 bài đã xuất bản gần nhất',
      note: 'Kết quả là nguồn để AI đọc tiếp và trích dẫn, không phải câu trả lời đã xác minh từ toàn văn. Không tìm thấy ở đây không có nghĩa website không có bài phù hợp.'
    };
  }

  var tool = {
    name: 'ask_site',
    title: 'Tìm bài viết trên blog Nguyễn Tú',
    description: 'Tìm bài viết đã xuất bản theo từ khóa tiếng Việt trong chỉ mục tối đa 300 bài mới nhất của blog Nguyễn Tú. Dùng khi khách hỏi về cẩm nang xe máy, thuê xe, luật giao thông hoặc du lịch Hà Nội. Trả về tiêu đề, mô tả ngắn, URL nguồn; không trả lời từ toàn văn, không đặt xe, không cam kết giá hay tình trạng xe.',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          minLength: 2,
          maxLength: 120,
          description: 'Cụm từ cần tìm trong tiêu đề và mô tả bài viết.'
        }
      },
      required: ['query'],
      additionalProperties: false
    },
    annotations: {
      readOnlyHint: true,
      untrustedContentHint: true
    },
    execute: askSite
  };

  Promise.resolve(modelContext.registerTool(tool, { signal: controller.signal }))
    .catch(function () { controller.abort(); });
  window.addEventListener('pagehide', function () { controller.abort(); }, { once: true });
})();
