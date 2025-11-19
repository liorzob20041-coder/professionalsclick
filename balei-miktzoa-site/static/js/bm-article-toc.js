(function () {
  var tocCol = document.querySelector('.bm-article-page .article-page__toc');
  var grid = document.querySelector('.bm-article-page .article-page__grid--has-toc');
  var hero = document.getElementById('article-hero');
  if (!tocCol || !grid) return;
  function updateAffix() {
    var vw = window.innerWidth || document.documentElement.clientWidth;
    if (vw < 992) {
      tocCol.classList.remove('article-page__toc--affixed');
      tocCol.style.top = '';
      return;
    }
    tocCol.classList.add('article-page__toc--affixed');
  }
  window.addEventListener('scroll', updateAffix, { passive: true });
  window.addEventListener('resize', updateAffix);
  document.addEventListener('DOMContentLoaded', updateAffix);
  window.addEventListener('load', updateAffix);
  updateAffix();
})();