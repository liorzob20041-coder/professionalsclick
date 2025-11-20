(function() {
  const tocCol = document.querySelector('.bm-article-page .article-page__toc');
  const grid   = document.querySelector('.bm-article-page .article-page__grid--has-toc');
  if (!tocCol || !grid) return;
  const DESKTOP_BP = 992;
  let baseFixedInline = null; // px from viewport edge
  let baseAbsInline   = null; // px from grid edge
  let baseWidth       = null; // px
  let baseDir         = null; // 'ltr' or 'rtl'
  function getHeaderHeight() {
    const root = document.documentElement;
    const varVal = getComputedStyle(root).getPropertyValue('--site-header-height');
    const parsed = parseInt(varVal, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 72;
  }
  function captureBaseGeometry() {
    const vw = window.innerWidth || document.documentElement.clientWidth;
    if (vw < DESKTOP_BP) {
      baseFixedInline = baseAbsInline = baseWidth = null;
      return;
    }
    // Geometry capture retained for compatibility; no position overrides applied.
  }
  function resetInlineStyles() {
    tocCol.style.left  = '';
    tocCol.style.right = '';
    tocCol.style.width = '';
    tocCol.style.top   = '';
  }
  function applyNormalLayout() {
    tocCol.classList.remove('article-page__toc--affixed',
                            'article-page__toc--pinned-bottom');
    resetInlineStyles();
  }
  function applyAffixedLayout(offsetTop) {
    tocCol.classList.remove('article-page__toc--pinned-bottom');
    tocCol.classList.add('article-page__toc--affixed');
    resetInlineStyles();
  }
  function applyPinnedBottomLayout() {
    tocCol.classList.remove('article-page__toc--affixed');
    tocCol.classList.add('article-page__toc--pinned-bottom');
    resetInlineStyles();
  }
  function updateAffix() {
    const vw = window.innerWidth || document.documentElement.clientWidth;
    if (vw < DESKTOP_BP) {
      // Mobile: everything normal
      applyNormalLayout();
      baseFixedInline = baseAbsInline = baseWidth = null;
      return;
    }
    const headerH   = getHeaderHeight();
    const offsetTop = headerH + 16;
    const scrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
    const gridRect       = grid.getBoundingClientRect();
    const gridTop        = gridRect.top + scrollY;
    const gridHeight     = grid.offsetHeight;
    const gridBottom     = gridTop + gridHeight;
    // Use current TOC height – it might grow if list changes
    const tocRect   = tocCol.getBoundingClientRect();
    const tocHeight = tocRect.height;
    const startAffix = gridTop - offsetTop;
    const stopAffix  = gridBottom - offsetTop - tocHeight;
    // Capture base geometry whenever we are clearly in "normal" mode
    if (scrollY <= startAffix) {
      captureBaseGeometry();
      applyNormalLayout();
      return;
    }
    if (scrollY >= stopAffix) {
      applyPinnedBottomLayout();
    } else {
      applyAffixedLayout(offsetTop);
    }
  }
  window.addEventListener('scroll', updateAffix, { passive: true });
  window.addEventListener('resize', function() {
    // On resize we need to recalc geometry
    applyNormalLayout();
    captureBaseGeometry();
    updateAffix();
  });
  document.addEventListener('DOMContentLoaded', function() {
    captureBaseGeometry();
    updateAffix();
  });
  window.addEventListener('load', function() {
    captureBaseGeometry();
    updateAffix();
  });
})();