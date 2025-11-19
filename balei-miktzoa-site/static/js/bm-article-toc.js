(function() {
  const tocCol = document.querySelector('.bm-article-page .article-page__toc');
  const grid = document.querySelector('.bm-article-page .article-page__grid--has-toc');
  if (!tocCol || !grid) return;
  const DESKTOP_BP = 992;
  function getHeaderHeight() {
    const root = document.documentElement;
    const varVal = getComputedStyle(root).getPropertyValue('--site-header-height');
    const parsed = parseInt(varVal, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 72;
  }
  function updateAffix() {
    const vw = window.innerWidth || document.documentElement.clientWidth;
    // Mobile / tablet: reset everything
    if (vw < DESKTOP_BP) {
      tocCol.classList.remove('article-page__toc--affixed', 'article-page__toc--pinned-bottom');
      tocCol.style.top = '';
      return;
    }
    const headerH = getHeaderHeight();
    const offsetTop = headerH + 16;
    // Compute container and TOC dimensions relative to the document
    const gridRect = grid.getBoundingClientRect();
    const tocRect = tocCol.getBoundingClientRect();
    const scrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
    const containerTop = gridRect.top + scrollY;
    const containerHeight = grid.offsetHeight;
    const containerBottom = containerTop + containerHeight;
    const tocHeight = tocRect.height;
    // Start affixing when the top of the grid reaches the header line
    const startAffix = containerTop - offsetTop;
    // Stop affixing (and pin to bottom) when the bottom of the TOC would
    // go past the bottom of the container
    const stopAffix = containerBottom - offsetTop - tocHeight;
    if (scrollY <= startAffix) {
      // 1) Normal: TOC in-flow, just under the HERO
      tocCol.classList.remove('article-page__toc--affixed', 'article-page__toc--pinned-bottom');
      tocCol.style.top = '';
    } else if (scrollY >= stopAffix) {
      // 3) Pinned-bottom: TOC attached to bottom of the article container
      tocCol.classList.remove('article-page__toc--affixed');
      tocCol.classList.add('article-page__toc--pinned-bottom');
      tocCol.style.top = ''; // top handled by CSS (bottom: 0)
    } else {
      // 2) Affixed: TOC fixed under the header while scrolling over the article body
      tocCol.classList.remove('article-page__toc--pinned-bottom');
      tocCol.classList.add('article-page__toc--affixed');
      tocCol.style.top = offsetTop + 'px';
    }
  }
  window.addEventListener('scroll', updateAffix, { passive: true });
  window.addEventListener('resize', updateAffix);
  document.addEventListener('DOMContentLoaded', updateAffix);
  window.addEventListener('load', updateAffix);
  updateAffix();
})();