/**
 * Lightweight on-site search of the 300 most recent titles and excerpts.
 * Data is fetched only on /tim-kiem/ after a non-empty user query.
 * Full historical coverage remains available via the explicitly labelled
 * Google site: search link. No external libraries, API keys or all-post payload.
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

  function fold(text) {
    var value = String(text || '').toLowerCase();
    if (value.normalize) value = value.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    return value.replace(/đ/g, 'd').replace(/\s+/g, ' ').trim();
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
      loaded = fetch(indexUrl, { credentials: 'same-origin' }).then(function (response) {
        if (!response.ok) throw new Error('Search index HTTP ' + response.status);
        return response.json();
      }).then(function (data) {
        if (!Array.isArray(data) || data.length > 300) throw new Error('Search index invalid');
        return data;
      }).catch(function (error) {
        loaded = null; // allow retry after a transient connection error
        throw error;
      });
    }
    return loaded;
  }

  function appendResult(post) {
    // Do not allow the generated data to become an open-redirect or HTML sink.
    if (!post || typeof post.url !== 'string' ||
        post.url.charAt(0) !== '/' || post.url.charAt(1) === '/') return;
    var li = document.createElement('li');
    li.className = 'site-search-result';
    var link = document.createElement('a');
    link.href = post.url;
    link.textContent = String(post.title || 'Bài viết');
    li.appendChild(link);
    if (post.description) {
      var paragraph = document.createElement('p');
      paragraph.textContent = String(post.description);
      li.appendChild(paragraph);
    }
    resultList.appendChild(li);
  }

  function render(query, posts) {
    clearResults();
    var terms = fold(query).split(' ').filter(Boolean);
    var matches = posts.map(function (post, index) {
      var title = fold(post.title);
      var summary = fold(post.description);
      var combined = title + ' ' + summary;
      var score = 0;
      if (title.indexOf(fold(query)) !== -1) score += 10;
      if (summary.indexOf(fold(query)) !== -1) score += 3;
      if (terms.every(function (term) { return combined.indexOf(term) !== -1; })) {
        score += 2;
      } else {
        score = 0;
      }
      return { post: post, score: score, index: index };
    }).filter(function (v) { return v.score > 0; });

    matches.sort(function (a, b) { return b.score - a.score || a.index - b.index; });
    matches.slice(0, 24).forEach(function (result) { appendResult(result.post); });

    if (!matches.length) {
      status.textContent = 'Chưa tìm thấy bài phù hợp trong 300 bài gần nhất. Bạn có thể tìm rộng hơn qua Google.';
    } else {
      status.textContent = 'Tìm thấy ' + matches.length + ' bài trong danh sách 300 bài mới nhất; hiển thị tối đa 24 kết quả.';
    }
  }

  function search(query) {
    var term = String(query || '').trim().slice(0, 120);
    updateGoogle(term);
    var generation = ++searchGeneration;
    clearResults();
    if (fold(term).length < 2) {
      status.textContent = 'Nhập ít nhất 2 ký tự để tìm trong các bài mới.';
      return;
    }
    status.textContent = 'Đang tìm kiếm trong các bài mới nhất…';
    loadIndex().then(function (posts) {
      if (generation === searchGeneration) render(term, posts);
    }).catch(function () {
      if (generation === searchGeneration) {
        status.textContent = 'Chưa tải được danh sách bài viết. Hãy thử lại hoặc dùng liên kết tìm kiếm Google.';
      }
    });
  }

  function queryFromUrl() {
    try {
      return (new URLSearchParams(window.location.search).get('q') || '').slice(0, 120);
    } catch (error) {
      return '';
    }
  }

  form.addEventListener('submit', function (event) {
    if (fold(input.value).length < 2) return; // native form fallback if JS cannot search
    event.preventDefault();
    var query = input.value.trim().slice(0, 120);
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', window.location.pathname + '?q=' + encodeURIComponent(query));
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
