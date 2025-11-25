(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    var articleRoot = document.getElementById('bm-article-main');
    var tocNav = document.getElementById('bm-article-toc');
    var tocList = document.getElementById('bm-article-toc-list');
    if (!articleRoot || !tocNav || !tocList) {
      return;
    }
    var headings = Array.prototype.slice
      .call(articleRoot.querySelectorAll('h2, h3'))
      .filter(function (heading) {
        return heading && heading.textContent && heading.textContent.trim().length;
      });
    if (!headings.length) {
      tocNav.dataset.empty = 'true';
      tocNav.style.display = 'none';
      return;
    }
    tocNav.dataset.empty = 'false';
    tocNav.style.display = '';
    tocList.innerHTML = '';
    var linkById = new Map();
    var slugify = function (text) {
      return text
        .toString()
        .trim()
        .toLowerCase()
        .replace(/[^\p{L}\p{N}\s-]/gu, '')
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-');
    };
    headings.forEach(function (heading, index) {
      if (!heading.id) {
        var slug = slugify(heading.textContent || '');
        var baseId = slug || 'section-' + (index + 1);
        var uniqueId = baseId;
        var counter = 1;
        while (document.getElementById(uniqueId)) {
          uniqueId = baseId + '-' + counter++;
        }
        heading.id = uniqueId;
      }
      var li = document.createElement('li');
      var link = document.createElement('a');
      link.href = '#' + heading.id;
      link.textContent = heading.textContent || heading.id;
      link.addEventListener('click', function (event) {
        event.preventDefault();
        var target = document.getElementById(heading.id);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
      li.appendChild(link);
      tocList.appendChild(li);
      linkById.set(heading.id, link);
    });
    var activeId = null;
    var setActive = function (id) {
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
    var observer = new IntersectionObserver(
      function (entries) {
        var bestId = activeId;
        var bestScore = Number.POSITIVE_INFINITY;
        var viewportCenter = window.innerHeight / 2;
        entries.forEach(function (entry) {
          var rect = entry.boundingClientRect;
          var center = rect.top + rect.height / 2;
          var distance = Math.abs(center - viewportCenter);
          if (entry.isIntersecting && distance < bestScore) {
            bestScore = distance;
            bestId = entry.target.id;
          }
        });
        if (!entries.some(function (entry) { return entry.isIntersecting; })) {
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
    headings.forEach(function (heading) {
      observer.observe(heading);
    });
  });
})();