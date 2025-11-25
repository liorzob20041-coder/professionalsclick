// TOC סטיקי – ורק למאמר עם הלייאאוט החדש
document.addEventListener('DOMContentLoaded', () => {
  const main = document.querySelector('.bm-article-sticky-main');
  const tocList = document.querySelector('.bm-article-sticky-toc-list');
  if (!main || !tocList) {
    return;
  }
  const headings = Array.from(main.querySelectorAll('h2, h3'));
  if (!headings.length) {
    return;
  }
  const linkById = new Map();
  const slugify = (text) => {
    return text
      .toString()
      .trim()
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s-]/gu, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-');
  };
  // מוסיפים id לכותרות + בונים את הרשימה בצד
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
    if (id === activeId) {
      return;
    }
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
  // משתמשים ב-IntersectionObserver לבחור כותרת "הכי באמצע" מסך
  const observer = new IntersectionObserver(
    (entries) => {
      let bestId = activeId;
      let bestScore = Number.POSITIVE_INFINITY;
      const viewportCenter = window.innerHeight / 2;
      entries.forEach((entry) => {
        const rect = entry.boundingClientRect;
        const center = rect.top + rect.height / 2;
        const distance = Math.abs(center - viewportCenter);
        if (entry.isIntersecting && distance < bestScore) {
          bestScore = distance;
          bestId = entry.target.id;
        }
      });
      if (!entries.some((entry) => entry.isIntersecting)) {
        return;
      }
      setActive(bestId);
    },
    {
      root: null,
      rootMargin: '-50% 0px -40% 0px',
      threshold: [0, 0.3, 0.6, 1],
    }
  );
  headings.forEach((heading) => observer.observe(heading));
});