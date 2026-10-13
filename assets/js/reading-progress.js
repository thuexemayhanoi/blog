/* Article-only reading progress: passive scroll, one rAF per frame, no dependencies. */
(function () {
  'use strict';
  var article = document.querySelector('.post-detail');
  var bar = article && article.querySelector('.reading-progress-bar');
  if (!article || !bar) return;
  var scheduled = false;

  function update() {
    scheduled = false;
    var rect = article.getBoundingClientRect();
    var top = (window.scrollY || window.pageYOffset || 0) + rect.top;
    var distance = Math.max(1, article.offsetHeight - window.innerHeight);
    var offset = (window.scrollY || window.pageYOffset || 0) - top;
    var progress = Math.min(1, Math.max(0, offset / distance));
    bar.style.transform = 'scaleX(' + progress.toFixed(3) + ')';
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    if (typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(update);
    } else {
      update();
    }
  }

  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  schedule();
})();
