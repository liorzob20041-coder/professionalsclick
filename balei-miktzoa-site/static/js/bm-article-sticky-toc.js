(function () {
  console.log('STICKY_TOC: file loaded');

  function initStickyToc() {
    console.log('STICKY_TOC: init start');

    const page = document.querySelector('.bm-article-page.bm-article-sticky');
    if (!page) {
      console.log('STICKY_TOC: no .bm-article-page.bm-article-sticky');
      return;
    }

    const main = page.querySelector('.bm-article-sticky-main');
    const tocList = page.querySelector('#bm-article-sticky-toc-list');
    if (!main || !tocList) {
      console.log('STICKY_TOC: missing main or tocList', { main: !!main, tocList: !!tocList });
      return;
    }

    const headings = Array.from(main.querySelectorAll('h2, h3'));
    console.log('STICKY_TOC: headings found =', headings.length);
    if (!headings.length) return;

    const linkById = new Map();

    const slugify = (text) =>
      (text || '')
        .toString()
        .trim()
        .toLowerCase()
        .replace(/['"’”“]/g, '')
        .replace(/[^0-9a-z\u0590-\u05FF\u0400-\u04FF\s-]/g, '')
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-')
        .replace(/^-|-$/g, '');

    headings.forEach((heading, index) => {
      if (!heading.id) {
        const slug = slugify(heading.textContent || `section-${index + 1}`);
        const baseId = slug || `section-${index + 1}`;
        let uniqueId = baseId;
        let counter = 1;

        while (document.getElementById(uniqueId)) {
          uniqueId = `${baseId}-${counter++}`;
        }

        heading.id = uniqueId;
      }

      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = `#${heading.id}`;
      link.textContent = heading.textContent || heading.id;

      link.addEventListener('click', (event) => {
        event.preventDefault();
        const target = document.getElementById(heading.id);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });

      li.appendChild(link);
      tocList.appendChild(li);
      linkById.set(heading.id, link);
    });

    let activeId = null;

    const setActive = (id) => {
      if (id === activeId) return;

      if (activeId && linkById.has(activeId)) {
        linkById.get(activeId).classList.remove('is-active');
      }
      if (id && linkById.has(id)) {
        linkById.get(id).classList.add('is-active');
        activeId = id;
      } else {
        activeId = null;
      }
    };

    if (!('IntersectionObserver' in window)) {
      console.log('STICKY_TOC: no IntersectionObserver support');
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        let bestId = activeId;
        let bestScore = Number.POSITIVE_INFINITY;
        const viewportCenter = window.innerHeight / 2;

        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const rect = entry.boundingClientRect;
          const center = rect.top + rect.height / 2;
          const distance = Math.abs(center - viewportCenter);
          if (distance < bestScore) {
            bestScore = distance;
            bestId = entry.target.id;
          }
        });

        if (!entries.some((entry) => entry.isIntersecting)) return;
        setActive(bestId);
      },
      {
        root: null,
        rootMargin: '-50% 0px -40% 0px',
        threshold: [0, 0.3, 0.6, 1],
      }
    );

    headings.forEach((heading) => observer.observe(heading));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStickyToc);
  } else {
    initStickyToc();
  }
})();
