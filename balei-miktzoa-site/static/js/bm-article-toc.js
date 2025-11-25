(function () {
  'use strict';
  var tocNav = document.getElementById('bm-article-toc');
  var tocList = document.getElementById('bm-article-toc-list');
  var articleRoot = document.getElementById('bm-article-main');
  if (!tocNav || !tocList || !articleRoot) {
    return;
  }
  var headings = Array.prototype.slice.call(articleRoot.querySelectorAll('h2, h3')).filter(function (node) {
    return node && node.textContent && node.textContent.trim().length;
  });
  if (!headings.length) {
    tocNav.dataset.empty = 'true';
    tocNav.style.display = 'none';
    return;
  }
  tocNav.dataset.empty = 'false';
  tocNav.style.display = '';
  tocNav.classList.add('article-toc--visible');
  tocList.innerHTML = '';
  var slugCounts = Object.create(null);
  function slugify(text) {
    var slug = (text || '').trim().toLowerCase();
    slug = slug.replace(/["'`~!@#$%^&*()+=\[\]{}|\\/:;<>,.?]/g, '');
    slug = slug.replace(/\s+/g, '-');
    slug = slug.replace(/-+/g, '-');
    slug = slug.replace(/^-|-$/g, '');
    return slug || 'section';
  }
  headings.forEach(function (heading) {
    var text = heading.textContent.trim();
    var id = heading.getAttribute('id');
    if (!id) {
      id = slugify(text);
    }
    if (slugCounts[id]) {
      slugCounts[id] += 1;
      id = id + '-' + slugCounts[id];
    } else {
      slugCounts[id] = 1;
    }
    heading.id = id;
    var item = document.createElement('li');
    var link = document.createElement('a');
    link.href = '#' + id;
    link.textContent = text;
    link.addEventListener('click', function (event) {
      event.preventDefault();
      var target = document.getElementById(id);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', '#' + id);
      }
    });
    item.appendChild(link);
    tocList.appendChild(item);
  });
  var links = Array.prototype.slice.call(tocList.querySelectorAll('a'));
  var visibleScores = new Map();
  function setActive(id) {
    links.forEach(function (link) {
      var match = link.getAttribute('href') === '#' + id;
      link.classList.toggle('is-active', match);
    });
  }
  if (headings.length) {
    setActive(headings[0].id);
  }
  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        var id = entry.target.id;
        var score = entry.isIntersecting ? entry.intersectionRatio : 0;
        visibleScores.set(id, score);
      });
      var bestId = '';
      var bestScore = 0;
      visibleScores.forEach(function (score, id) {
        if (score > bestScore) {
          bestScore = score;
          bestId = id;
        }
      });
      if (!bestId && headings.length) {
        bestId = headings[0].id;
      }
      if (bestId) {
        setActive(bestId);
      }
    },
    { rootMargin: '-50% 0px -40% 0px', threshold: [0, 0.25, 0.5, 0.75, 1] }
  );
  headings.forEach(function (heading) {
    observer.observe(heading);
  });
})();