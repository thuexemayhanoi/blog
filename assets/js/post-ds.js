/* Post Design System — chỉ tải ở trang bài viết (docs/POST-DESIGN-SYSTEM.md).
 * 1) Thanh tiến độ đọc  2) Hỏi đáp dạng accordion (+/−)  3) Mục lục tô đậm mục đang đọc.
 * Nâng cấp dần: không có JS thì mọi nội dung vẫn hiển thị đầy đủ; HTML tĩnh của bài không đổi. */
(function () {
  'use strict';
  var article = document.querySelector('.post-detail');
  if (!article) return;

  /* 1. Tiến độ đọc: cuộn thụ động, một rAF mỗi khung hình. */
  var bar = article.querySelector('.reading-progress-bar');
  if (bar) {
    var scheduled = false;
    var update = function () {
      scheduled = false;
      var rect = article.getBoundingClientRect();
      var scrollY = window.scrollY || window.pageYOffset || 0;
      var top = scrollY + rect.top;
      var distance = Math.max(1, article.offsetHeight - window.innerHeight);
      var progress = Math.min(1, Math.max(0, (scrollY - top) / distance));
      bar.style.transform = 'scaleX(' + progress.toFixed(3) + ')';
    };
    var schedule = function () {
      if (scheduled) return;
      scheduled = true;
      if (typeof window.requestAnimationFrame === 'function') {
        window.requestAnimationFrame(update);
      } else {
        update();
      }
    };
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    schedule();
  }

  if (!article.hasAttribute('data-pds')) return;

  /* 2. Hỏi đáp: mỗi câu hỏi (h3) thành nút mở/đóng câu trả lời ngay sau nó. */
  var accSeq = 0;
  function buildAccordion(question, answerNodes, expanded) {
    if (!answerNodes.length) return null;
    accSeq += 1;
    var panel = document.createElement('div');
    panel.className = 'pds-acc__panel';
    panel.id = 'pds-acc-' + accSeq;
    question.parentNode.insertBefore(panel, answerNodes[0]);
    answerNodes.forEach(function (node) { panel.appendChild(node); });

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'pds-acc__btn';
    button.setAttribute('aria-controls', panel.id);
    while (question.firstChild) button.appendChild(question.firstChild);
    var sign = document.createElement('span');
    sign.className = 'pds-acc__sign';
    sign.setAttribute('aria-hidden', 'true');
    button.appendChild(sign);
    question.appendChild(button);
    question.classList.add('pds-acc__q');

    function set(open) {
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
      panel.hidden = !open;
    }
    button.addEventListener('click', function () {
      set(button.getAttribute('aria-expanded') !== 'true');
    });
    set(expanded);
    return { question: question, panel: panel, open: function () { set(true); } };
  }

  var items = [];
  function enhance(section, questions, collect) {
    if (questions.length < 2) return;
    section.setAttribute('data-pds-acc', '1');
    questions.forEach(function (q, index) {
      var item = buildAccordion(q, collect(q), index === 0);
      if (item) items.push(item);
    });
  }

  /* 2a. Mục "Câu hỏi thường gặp" viết trong thân bài: h3 = câu hỏi, các khối tới h3 kế = câu trả lời. */
  Array.prototype.forEach.call(article.querySelectorAll('.pds-sec--qa'), function (section) {
    var questions = Array.prototype.filter.call(section.children, function (el) { return el.tagName === 'H3'; });
    enhance(section, questions, function (q) {
      var nodes = [];
      var node = q.nextElementSibling;
      while (node && node.tagName !== 'H3' && node.tagName !== 'H2') {
        nodes.push(node);
        node = node.nextElementSibling;
      }
      return nodes;
    });
  });

  /* 2b. Khối FAQ dùng chung (_includes/faq.html): div.faq-item > h3 + p. */
  Array.prototype.forEach.call(article.querySelectorAll('section.faq'), function (section) {
    var questions = Array.prototype.map.call(section.querySelectorAll('.faq-item'), function (item) {
      return item.querySelector('h3');
    }).filter(Boolean);
    enhance(section, questions, function (q) {
      return Array.prototype.filter.call(q.parentNode.children, function (el) { return el !== q; });
    });
  });

  /* Liên kết neo tới một câu hỏi (hoặc nội dung bên trong câu trả lời) thì mở đúng câu đó. */
  function openForHash() {
    var id = decodeURIComponent((window.location.hash || '').slice(1));
    if (!id) return;
    var target = document.getElementById(id);
    if (!target) return;
    items.forEach(function (item) {
      if (item.question === target || item.question.contains(target) || item.panel.contains(target)) {
        item.open();
        target.scrollIntoView();
      }
    });
  }
  if (items.length) {
    openForHash();
    window.addEventListener('hashchange', openForHash);
  }

  /* 3. Mục lục: đánh dấu mục đang đọc (chỉ thêm class; không đổi nội dung mục lục). */
  var toc = article.querySelector('.article-toc');
  if (toc && typeof window.IntersectionObserver === 'function') {
    var links = {};
    Array.prototype.forEach.call(toc.querySelectorAll('a[href^="#"]'), function (a) {
      links[decodeURIComponent(a.getAttribute('href').slice(1))] = a;
    });
    var headings = Array.prototype.filter.call(article.querySelectorAll('.article-body h2[id]'), function (h) {
      return !!links[h.id];
    });
    var current = null;
    var mark = function (id) {
      if (current === id) return;
      if (current && links[current]) links[current].classList.remove('is-active');
      current = id;
      if (links[id]) links[id].classList.add('is-active');
    };
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) mark(entry.target.id);
      });
    }, { rootMargin: '-15% 0px -70% 0px', threshold: 0 });
    headings.forEach(function (h) { observer.observe(h); });
  }
})();
