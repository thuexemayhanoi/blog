/**
 * WebMCP pilot: ONE read-only ask_site tool for the public Jekyll blog.
 * Does nothing if the browser does not support document.modelContext.
 * No SDK, polyfill, API keys, privileged routes, or effects on human UI.
 */
(function () {
  'use strict';

  var context = document.modelContext;
  if (!context && typeof navigator !== 'undefined') {
    context = navigator.modelContext; // Chrome 149 compatibility only
  }
  if (!context || typeof context.registerTool !== 'function') return;

  var script = document.currentScript;
  var indexUrl = script && script.getAttribute('data-index-url');
  if (!indexUrl || indexUrl.charAt(0) !== '/' || indexUrl.charAt(1) === '/') return;

  var controller = new AbortController();
  var publishedIndex = null;

  function fold(value) {
    var text = String(value || '').toLowerCase();
    if (typeof text.normalize === 'function') {
      text = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }
    return text.replace(/đ/g, 'd').replace(/[^a-z0-9]+/g, ' ').trim();
  }

  function validPath(path) {
    return typeof path === 'string' &&
      path.charAt(0) === '/' && path.charAt(1) !== '/' &&
      path.length <= 512 && !/[\s\\?#]/.test(path);
  }

  async function loadPublicIndex(signal) {
    if (publishedIndex) return publishedIndex;
    var response = await fetch(indexUrl, {
      credentials: 'same-origin',
      signal: signal
    });
    if (!response.ok) throw new Error('Không tải được danh mục bài công khai.');
    var data = await response.json();
    if (!Array.isArray(data) || data.length > 20000) {
      throw new Error('Danh mục bài viết không hợp lệ.');
    }
    // Exclude malformed/untrusted URLs even when delivered from same origin.
    publishedIndex = data.filter(function (row) {
      return row && validPath(row.url) &&
        typeof row.title === 'string' && typeof row.description === 'string';
    }).map(function (row) {
      return {
        title: row.title.slice(0, 220),
        description: row.description.slice(0, 320),
        url: row.url
      };
    });
    return publishedIndex;
  }

  async function askSite(input, options) {
    var question = input && input.question;
    if (typeof question !== 'string' || question.trim().length < 2 ||
        question.trim().length > 120) {
      throw new Error('Câu hỏi phải dài từ 2 đến 120 ký tự.');
    }

    var normalized = fold(question);
    var terms = Array.from(new Set(normalized.split(' ').filter(Boolean)));
    if (!normalized || terms.length > 12) {
      throw new Error('Vui lòng dùng câu hỏi ngắn, tối đa 12 từ khóa.');
    }
    var signal = options && options.signal;
    if (signal && signal.aborted) throw new Error('Đã hủy yêu cầu.');
    var rows = await loadPublicIndex(signal);
    if (signal && signal.aborted) throw new Error('Đã hủy yêu cầu.');

    var ranked = [];
    rows.forEach(function (row) {
      var title = fold(row.title);
      var desc = fold(row.description);
      var combined = title + ' ' + desc;
      if (!terms.every(function (term) { return combined.indexOf(term) !== -1; })) {
        return;
      }
      var score = 1;
      if (title.indexOf(normalized) !== -1) score += 12;
      if (desc.indexOf(normalized) !== -1) score += 5;
      terms.forEach(function (term) {
        if (title.indexOf(term) !== -1) score += 3;
        if (desc.indexOf(term) !== -1) score += 1;
      });
      ranked.push({ row: row, score: score });
    });
    ranked.sort(function (a, b) { return b.score - a.score; });

    return {
      question: question.trim(),
      scope: 'Chỉ tìm tiêu đề và mô tả của các bài đã xuất bản',
      indexed_articles: rows.length,
      matched_articles: ranked.length,
      sources: ranked.slice(0, 5).map(function (match) {
        return {
          title: match.row.title,
          excerpt: match.row.description,
          url: window.location.origin + match.row.url
        };
      }),
      note: ranked.length
        ? 'Các đoạn mô tả là nguồn tham khảo, không phải câu trả lời được xác minh độc lập. Mở URL nguồn để đọc toàn văn.'
        : 'Chưa tìm thấy bài khớp tất cả từ khóa. Thử câu hỏi ngắn hơn hoặc sử dụng trang /tim-kiem/.'
    };
  }

  window.addEventListener('pagehide', function () {
    controller.abort(); // release only this page's registration
  }, { once: true });

  try {
    Promise.resolve(context.registerTool({
      name: 'ask_site',
      title: 'Tra cứu cẩm nang Nguyễn Tú',
      description: 'Tìm bài viết công khai của blog Nguyễn Tú theo câu hỏi tiếng Việt, trả tối đa 5 nguồn có tiêu đề, đoạn mô tả và URL để kiểm chứng. Dùng khi cần thông tin về thuê xe máy, xe máy, kỹ năng lái và du lịch Hà Nội. Không đặt xe, không chỉnh sửa nội dung và không trả lời từ thông tin riêng tư.',
      inputSchema: {
        type: 'object',
        properties: {
          question: {
            type: 'string',
            minLength: 2,
            maxLength: 120,
            description: 'Câu hỏi hoặc cụm từ tiếng Việt cần tra cứu'
          }
        },
        required: ['question'],
        additionalProperties: false
      },
      annotations: {
        readOnlyHint: true,
        untrustedContentHint: true
      },
      execute: askSite
    }, { signal: controller.signal })).catch(function () {
      controller.abort(); // unsupported/rejected registration cannot break UI
    });
  } catch (_) {
    controller.abort();
  }
})();
