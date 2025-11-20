(function() {
  const tocNav = document.getElementById('bm-article-toc');
  const tocList = document.getElementById('bm-article-toc-list');
  const articleRoot = document.getElementById('bm-article-main') || document.getElementById('bm-article-body');
  if (!tocNav || !tocList || !articleRoot) return;
  const headings = Array.from(articleRoot.querySelectorAll('h2[id], h3[id]'));
  if (!headings.length) {
    tocNav.dataset.empty = 'true';
    return;
  }
  tocNav.dataset.empty = 'false';
  const linkById = new Map();
  const listFragment = document.createDocumentFragment();
  headings.forEach((heading) => {
    const li = document.createElement('li');
    const anchor = document.createElement('a');
    anchor.href = `#${heading.id}`;
    anchor.textContent = heading.textContent;
    li.appendChild(anchor);
    listFragment.appendChild(li);
    linkById.set(heading.id, anchor);
  });
  tocList.innerHTML = '';
  tocList.appendChild(listFragment);
  tocNav.classList.add('article-toc--visible');
  let currentActiveId = null;
  const visibleHeadings = new Map();
  function setActiveLink(id) {
    if (id === currentActiveId) return;
    linkById.forEach((link) => link.classList.remove('is-active'));
    const activeLink = linkById.get(id);
    if (activeLink) {
      activeLink.classList.add('is-active');
      currentActiveId = id;
    }
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const id = entry.target.id;
        if (entry.isIntersecting) {
          visibleHeadings.set(id, entry.boundingClientRect.top);
        } else {
          visibleHeadings.delete(id);
        }
      });
      if (visibleHeadings.size) {
        const [nextId] = Array.from(visibleHeadings.entries()).sort((a, b) => a[1] - b[1])[0];
        setActiveLink(nextId);
        return;
      }
      let closestId = null;
      let closestDistance = Infinity;
      headings.forEach((heading) => {
        const distance = Math.abs(heading.getBoundingClientRect().top);
        if (distance < closestDistance) {
          closestDistance = distance;
          closestId = heading.id;
        }
      });
      if (closestId) {
        setActiveLink(closestId);
      }
    },
    {
      rootMargin: '-10% 0px -70% 0px',
      threshold: [0, 0.1, 1],
    }
  );
  headings.forEach((heading) => observer.observe(heading));
  // --- Floating TOC behavior on desktop ---
  const sidebarEl =
    tocNav.closest('.bm-article-page__sidebar') ||
    tocNav.closest('.article-page__toc') ||
    tocNav.parentElement;
  const mainEl = document.querySelector('.bm-article-page__main');
  if (sidebarEl && mainEl) {
    const rootDoc = document.documentElement;
    const headerVar = getComputedStyle(rootDoc).getPropertyValue('--site-header-height');
    const headerHeight = parseInt(headerVar, 10) || 72;
    let startY = null;
    function computeStartY() {
      const rect = tocNav.getBoundingClientRect();
      startY = window.scrollY + rect.top - headerHeight - 16;
    }
    function updateFloating() {
      const viewportWidth = window.innerWidth || rootDoc.clientWidth;
      // Disable on small screens
      if (viewportWidth < 1100) {
        tocNav.classList.remove('article-toc--fixed');
        tocNav.style.width = '';
        return;
      }
      if (startY === null) {
        computeStartY();
      }
      const scrollY = window.scrollY || window.pageYOffset;
      if (scrollY >= startY) {
        // Enter fixed mode
        const sidebarRect = sidebarEl.getBoundingClientRect();
        tocNav.classList.add('article-toc--fixed');
        tocNav.style.width = sidebarRect.width + 'px';
      } else {
        // Back to normal
        tocNav.classList.remove('article-toc--fixed');
        tocNav.style.width = '';
      }
    }
    computeStartY();
    updateFloating();
    window.addEventListener('scroll', updateFloating, { passive: true });
    window.addEventListener('resize', () => {
      startY = null;
      updateFloating();
    });
  }
})();