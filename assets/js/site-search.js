/**
 * Public article search for humans on mobile and desktop.
 * Uses the same lazy Jekyll metadata index as the WebMCP ask_site pilot.
 * No AI model, secrets, tracking API, backend, or external dependency.
 */
(function () {
  'use strict';

  var form = document.getElementById('site-search-form');
  if (!form) return;
  var input = document.getElementById('site-search-query');
  var resultList = document.getElementById('site-search-results');
  var status = document.getElementById('site-search-status');
  var google = document.getElementById('site-search-google');
  if (!input || !resultList || !status || !google) return;

  var indexUrl = form.getAttribute('data-index-url');
  var loaded = null;
  var searchGeneration = 0;

  var ignoredWords = {
    toi: true, muon: true, biet: true, hoi: true, lam: true, sao: true,
    the: true, nao: true, can: true, gi: true, nhung: true, cac: true,
    cho: true, ve: true, o: true, tai: true, la: true, co: true,
    hay: true, khong: true, duoc: true, voi: true, mot: true
  };

  function fold(value) {
    var text = String(value || '').toLowerCase();
    if (typeof text.normalize === 'function') {
      text = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }
    return text.replace(/đ/g, 'd').replace(/[^a-z0-9]+/g, ' ').trim();
  }

  function keywords(query) {
    return Array.from(new Set(fold(query).split(' ').filter(function (term) {
      return term.length > 0 && !ignoredWords[term];
    })));
  }

  function validPath(url) {
    return typeof url === 'string' && url.length <= 512 &&
      url.charAt(0) === '/' && url.charAt(1) !== '/' &&
      !/[\s\\?#]/.test(url);
  }

  function updateGoogle(query) {
    var text = 'site:blog.thuexemaynguyentu.com';
    if (query) text += ' ' + query;
    google.href = 'https://www.google.com/search?q=' + encodeURIComponent(text);
  }

  function clearResults() {
    while (resultList.firstChild) resultList.removeChild(resultList.firstChild);
  }

  function loadIndex() {
    if (!loaded) {
      loaded = fetch(indexUrl, { credentials: 'same-origin' })
        .then(function (response) {
          if (!response.ok) throw new Error('Không tải được chỉ mục bài công khai.');
          return response.json();
        })
        .then(function (data) {
          if (!Array.isArray(data) || data.length > 20000) {
            throw new Error('Dữ liệu tìm kiếm không hợp lệ.');
          }
          return data.filter(function (post) {
            return post && validPath(post.url) &&
              typeof post.title === 'string' && typeof post.description === 'string';
          });
        })
        .catch(function (error) {
          loaded = null;
          throw error;
        });
    }
    return loaded;
  }

  function appendResult(post) {
    if (!validPath(post.url)) return;
    var li = document.createElement('li');
    li.className = 'site-search-result';
    var link = document.createElement('a');
    link.href = post.url;
    link.textContent = post.title.slice(0, 220) || 'Bài viết';
    li.appendChild(link);
    if (post.description) {
      var excerpt = document.createElement('p');
      excerpt.textContent = post.description.slice(0, 320);
      li.appendChild(excerpt);
    }
    resultList.appendChild(li);
  }

  function scorePost(post, terms, wholeQuery) {
    var title = fold(post.title);
    var summary = fold(post.description);
    var titleWords = ' ' + title + ' ';
    var summaryWords = ' ' + summary + ' ';
    var matched = 0, score = 0;
    terms.forEach(function (term) {
      var token = ' ' + term + ' ';
      var inTitle = titleWords.indexOf(token) !== -1;
      var inSummary = summaryWords.indexOf(token) !== -1;
      if (inTitle || inSummary) matched++;
      if (inTitle) score += 3;
      if (inSummary) score += 1;
    });
    // Natural questions may include context words absent from a short title.
    if (matched < Math.ceil(terms.length * 0.75)) return 0;
    if (title.indexOf(wholeQuery) !== -1) score += 12;
    if (summary.indexOf(wholeQuery) !== -1) score += 5;
    return score;
  }

  function render(query, posts) {
    var terms = keywords(query);
    clearResults();
    if (!terms.length || terms.length > 12) {
      status.textContent = 'Hãy nhập một câu hỏi cụ thể, tối đa 12 từ khóa chính.';
      return;
    }
    var wholeQuery = fold(query);
    var matches = [];
    posts.forEach(function (post, index) {
      var score = scorePost(post, terms, wholeQuery);
      if (score > 0) matches.push({ post: post, score: score, index: index });
    });
    matches.sort(function (a, b) {
      return b.score - a.score || a.index - b.index;
    });
    matches.slice(0, 24).forEach(function (result) {
      appendResult(result.post);
    });
    if (!matches.length) {
      status.textContent = 'Chưa tìm thấy bài phù hợp trong ' + posts.length +
        ' bài công khai. Thử ít từ khóa hơn hoặc tìm trên Google.';
    } else {
      status.textContent = 'Tìm thấy ' + matches.length + ' bài phù hợp trong ' +
        posts.length + ' bài công khai; hiển thị tối đa 24 kết quả.';
    }
  }

  function search(query) {
    var term = String(query || '').trim().slice(0, 120);
    updateGoogle(term);
    var generation = ++searchGeneration;
    clearResults();
    if (fold(term).length < 2) {
      status.textContent = 'Nhập ít nhất 2 ký tự để tìm bài viết.';
      return;
    }
    status.textContent = 'Đang tìm trong các bài viết đã xuất bản…';
    loadIndex().then(function (posts) {
      if (generation === searchGeneration) render(term, posts);
    }).catch(function () {
      if (generation === searchGeneration) {
        status.textContent = 'Chưa tải được dữ liệu. Hãy thử lại hoặc tìm qua Google.';
      }
    });
  }

  function queryFromUrl() {
    try {
      return (new URLSearchParams(window.location.search).get('q') || '').slice(0, 120);
    } catch (_) { return ''; }
  }

  form.addEventListener('submit', function (event) {
    if (fold(input.value).length < 2) return; // preserve native Google fallback
    event.preventDefault();
    var query = input.value.trim().slice(0, 120);
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '',
        window.location.pathname + '?q=' + encodeURIComponent(query));
    }
    search(query);
  });

  window.addEventListener('popstate', function () {
    var query = queryFromUrl();
    input.value = query;
    search(query);
  });

  var initial = queryFromUrl();
  if (initial) {
    input.value = initial;
    search(initial);
  } else {
    updateGoogle('');
  }
})();
