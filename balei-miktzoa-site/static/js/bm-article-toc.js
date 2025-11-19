(function () {
  var tocCol = document.querySelector('.bm-article-page .article-page__toc');
  var grid = document.querySelector('.bm-article-page .article-page__grid--has-toc');
  var hero = document.getElementById('article-hero');
  if (!tocCol || !grid || !hero) return;
  function getHeaderHeight() {
    var root = document.documentElement;
    var varVal = getComputedStyle(root).getPropertyValue('--site-header-height');
    var parsed = parseInt(varVal, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 72;
  }
  function updateAffix() {
    var vw = window.innerWidth || document.documentElement.clientWidth;
    // Disable on mobile/tablet
    if (vw < 992) {
      tocCol.classList.remove('article-page__toc--affixed');
      tocCol.style.top = '';
      return;
    }
    var headerH = getHeaderHeight();
    var heroRect = hero.getBoundingClientRect();
    // When the bottom of the HERO is above the header + margin,
    // affix the TOC. Until then, let it sit in the normal grid flow.
    var triggerY = headerH + 16;
    var shouldAffix = heroRect.bottom <= triggerY;
    if (shouldAffix) {
      if (!tocCol.classList.contains('article-page__toc--affixed')) {
        tocCol.classList.add('article-page__toc--affixed');
      }
    } else {
      tocCol.classList.remove('article-page__toc--affixed');
    }
  }
  window.addEventListener('scroll', updateAffix, { passive: true });
  window.addEventListener('resize', updateAffix);
  document.addEventListener('DOMContentLoaded', updateAffix);
  updateAffix();
})();