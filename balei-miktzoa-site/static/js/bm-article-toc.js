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
    // Only capture in "normal" state (no affix classes)
    if (tocCol.classList.contains('article-page__toc--affixed') ||
        tocCol.classList.contains('article-page__toc--pinned-bottom')) {
      return;
    }
    const dir = (document.documentElement.getAttribute('dir') || 'ltr').toLowerCase();
    const tocRect  = tocCol.getBoundingClientRect();
    const gridRect = grid.getBoundingClientRect();
    baseDir   = dir;
    baseWidth = tocRect.width;
    if (dir === 'rtl') {
      // distance from RIGHT edges
      baseFixedInline = window.innerWidth - tocRect.right;
      baseAbsInline   = gridRect.right - tocRect.right;
    } else {
      // distance from LEFT edges
      baseFixedInline = tocRect.left;
      baseAbsInline   = tocRect.left - gridRect.left;
    }
  }
  function resetInlineStyles() {
    tocCol.style.left  = '';
    tocCol.style.right = '';
    tocCol.style.width = '';
  }
  function applyNormalLayout() {
    tocCol.classList.remove('article-page__toc--affixed',
                            'article-page__toc--pinned-bottom');
    resetInlineStyles();
  }
  function applyAffixedLayout(offsetTop) {
    if (baseWidth == null || baseFixedInline == null || !baseDir) {
      captureBaseGeometry();
    }
    tocCol.classList.remove('article-page__toc--pinned-bottom');
    tocCol.classList.add('article-page__toc--affixed');
    tocCol.style.width = baseWidth + 'px';
    tocCol.style.top   = offsetTop + 'px';
    if (baseDir === 'rtl') {
      tocCol.style.right = baseFixedInline + 'px';
      tocCol.style.left  = 'auto';
    } else {
      tocCol.style.left  = baseFixedInline + 'px';
      tocCol.style.right = 'auto';
    }
  }
  function applyPinnedBottomLayout() {
    if (baseWidth == null || baseAbsInline == null || !baseDir) {
      captureBaseGeometry();
    }
    tocCol.classList.remove('article-page__toc--affixed');
    tocCol.classList.add('article-page__toc--pinned-bottom');
    tocCol.style.width = baseWidth + 'px';
    // vertical: handled by CSS (bottom: 0)
    if (baseDir === 'rtl') {
      tocCol.style.right = baseAbsInline + 'px';
      tocCol.style.left  = 'auto';
    } else {
      tocCol.style.left  = baseAbsInline + 'px';
      tocCol.style.right = 'auto';
    }
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