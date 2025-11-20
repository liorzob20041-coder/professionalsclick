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
  function initFloatingTocPosition() {
    var toc = document.getElementById('bm-article-toc');
    var hero = document.getElementById('article-hero');
    if (!toc || !hero) return;
    function getHeaderHeight() {
      var cssVal = getComputedStyle(document.documentElement).getPropertyValue('--site-header-height');
      var parsed = parseInt(cssVal, 10);
      return isFinite(parsed) && parsed > 0 ? parsed : 72;
    }
    var extraOffset = 16;
    function updateTocTop() {
      if (window.innerWidth < 1100) {
        toc.style.top = '';
        return;
      }
      var headerHeight = getHeaderHeight();
      var heroRect = hero.getBoundingClientRect();
      var margin = extraOffset;
      var heroBottom = heroRect.bottom;
      var top = heroBottom + margin;
      var minTop = headerHeight + margin;
      if (top < minTop) {
        top = minTop;
      }
      toc.style.top = top + 'px';
    }
    window.addEventListener('scroll', updateTocTop, { passive: true });
    window.addEventListener('resize', updateTocTop);
    updateTocTop();
  }
  initFloatingTocPosition();
})();