(function () {
  var tocCol = document.querySelector('.bm-article-page .article-page__toc');
  var grid = document.querySelector('.bm-article-page .article-page__grid--has-toc');
  var hero = document.getElementById('article-hero');
  if (!tocCol || !grid) return;
  function getHeaderHeight() {
    var root = document.documentElement;
    var varVal = getComputedStyle(root).getPropertyValue('--site-header-height');
    var parsed = parseInt(varVal, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 72;
  }
  function updateAffix() {
    var vw = window.innerWidth || document.documentElement.clientWidth;
    if (vw < 992) {
      tocCol.classList.remove('article-page__toc--affixed');
      tocCol.style.top = '';
      return;
    }
    tocCol.classList.add('article-page__toc--affixed');
    var headerH = getHeaderHeight();
    var minTop = headerH + 16;
    var top = minTop;
    if (hero) {
      var heroRect = hero.getBoundingClientRect();
      var desiredTop = heroRect.bottom + 16;
      if (desiredTop > minTop) {
        top = desiredTop;
      }
    }
    tocCol.style.top = top + 'px';
  }
  window.addEventListener('scroll', updateAffix, { passive: true });
  window.addEventListener('resize', updateAffix);
  document.addEventListener('DOMContentLoaded', updateAffix);
  window.addEventListener('load', updateAffix);
  updateAffix();
})();