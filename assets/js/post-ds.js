/* Post Design System — chỉ tải ở trang bài viết (docs/POST-DESIGN-SYSTEM.md).
 * 1) Thanh tiến độ đọc  2) Hỏi đáp dạng accordion (+/−)  3) Mục lục tô đậm mục đang đọc.
 * Nâng cấp dần: không có JS thì mọi nội dung vẫn hiển thị đầy đủ; HTML tĩnh của bài không đổi. */
(function () {
  'use strict';
  var article = document.querySelector('.post-detail');
  if (!article) return;

  /* Giải mã an toàn: chuỗi %-escape hỏng trong URL không được làm dừng script. */
  function decode(value) {
    try { return decodeURIComponent(value); } catch (e) { return value; }
  }

  /* Mọi việc theo cuộn dùng chung một trình nghe thụ động và một rAF mỗi khung hình. */
  var frameTasks = [];
  var scheduled = false;
  var runFrame = function () {
    scheduled = false;
    for (var i = 0; i < frameTasks.length; i += 1) frameTasks[i]();
  };
  var schedule = function () {
    if (scheduled) return;
    scheduled = true;
    if (typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(runFrame);
    } else {
      runFrame();
    }
  };

  /* 1. Tiến độ đọc. */
  var bar = article.querySelector('.reading-progress-bar');
  if (bar) {
    frameTasks.push(function () {
      var rect = article.getBoundingClientRect();
      var scrollY = window.scrollY || window.pageYOffset || 0;
      var top = scrollY + rect.top;
      var distance = Math.max(1, article.offsetHeight - window.innerHeight);
      var progress = Math.min(1, Math.max(0, (scrollY - top) / distance));
      bar.style.transform = 'scaleX(' + progress.toFixed(3) + ')';
    });
  }
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  schedule();

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
  function enhance(section, questions, collect, keepLastOpen) {
    if (questions.length < 2) return;
    section.setAttribute('data-pds-acc', '1');
    questions.forEach(function (q, index) {
      var nodes = collect(q);
      /* Mục hỏi đáp là mục cuối bài: đoạn kết của bài nằm sau câu trả lời cuối, nên câu cuối có nhiều khối thì để mở. */
      var open = index === 0 || (keepLastOpen && index === questions.length - 1 && nodes.length > 1);
      var item = buildAccordion(q, nodes, open);
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
    }, true);
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
    var id = decode((window.location.hash || '').slice(1));
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

  /* 3. Mục lục: đánh dấu mục đang đọc = mục H2 cuối cùng đã chạm mép dưới của header (chỉ thêm class). */
  var toc = article.querySelector('.article-toc');
  if (toc) {
    var links = {};
    Array.prototype.forEach.call(toc.querySelectorAll('a[href^="#"]'), function (a) {
      links[decode(a.getAttribute('href').slice(1))] = a;
    });
    var headings = Array.prototype.filter.call(article.querySelectorAll('.article-body h2[id]'), function (h) {
      return !!links[h.id];
    });
    var current = null;
    if (headings.length) {
      frameTasks.push(function () {
        var active = null;
        for (var i = 0; i < headings.length; i += 1) {
          if (headings[i].getBoundingClientRect().top > 140) break;
          active = headings[i].id;
        }
        if (active === current) return;
        if (current) links[current].classList.remove('is-active');
        if (active) links[active].classList.add('is-active');
        current = active;
        /* Ray mục lục dài hơn màn hình thì tự cuộn (chỉ cuộn ray, không cuộn trang) để mục đang đọc luôn nằm trong ray. */
        if (active && toc.scrollHeight > toc.clientHeight + 1) {
          var box = toc.getBoundingClientRect();
          var row = links[active].getBoundingClientRect();
          if (row.top < box.top + 56) toc.scrollTop -= box.top + 56 - row.top;
          else if (row.bottom > box.bottom - 12) toc.scrollTop += row.bottom - box.bottom + 12;
        }
      });
      schedule();
    }
  }
})();
