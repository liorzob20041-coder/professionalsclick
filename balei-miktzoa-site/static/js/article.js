(function () {
  'use strict';
  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }
  function slugify(text) {
    var slug = (text || '').trim().toLowerCase();
    slug = slug.replace(/["'`~!@#$%^&*()+=\[\]{}|\\/:;<>,.?]/g, '');
    slug = slug.replace(/\s+/g, '-');
    slug = slug.replace(/-+/g, '-');
    slug = slug.replace(/^-|-$/g, '');
    return slug || 'section';
  }
  function enhanceCallouts(root) {
    var keys = ['warning', 'tip', 'info'];
    keys.forEach(function (key) {
      var nodes = root.querySelectorAll('[data-ui="' + key + '"]');
      Array.prototype.forEach.call(nodes, function () {});
    });
  }
  function enhanceChecklists(root) {
    var lists = root.querySelectorAll('ul[data-ui="checklist"]');
    Array.prototype.forEach.call(lists, function (list) {
      list.setAttribute('role', 'list');
    });
  }
  function enhanceSteps(root) {
    var lists = root.querySelectorAll('ol[data-ui="steps"]');
    Array.prototype.forEach.call(lists, function (list) {
      list.setAttribute('role', 'list');
    });
  }
  function tableToChartData(table) {
    var rows = table.querySelectorAll('tbody tr');
    var type = (table.getAttribute('data-chart') || '').toLowerCase();
    if (!type || !rows.length) {
      return null;
    }
    var labels = [];
    var values = [];
    Array.prototype.forEach.call(rows, function (row) {
      var cells = row.children;
      if (!cells || cells.length < 2) {
        return;
      }
      var label = cells[0].textContent ? cells[0].textContent.trim() : '';
      var rawValue = cells[1].textContent ? cells[1].textContent.trim() : '';
      var numeric = parseFloat(String(rawValue).replace(/[^\d.\-]/g, ''));
      if (label && !isNaN(numeric) && isFinite(numeric)) {
        labels.push(label);
        values.push(numeric);
      }
    });
    if (!labels.length) {
      return null;
    }
    return {
      type: type,
      title: table.getAttribute('data-chart-title') || '',
      labels: labels,
      values: values,
    };
  }
  function renderChartNextToTable(table, data) {
    if (typeof window.Chart !== 'function') {
      return;
    }
    var wrap = document.createElement('div');
    wrap.className = 'bm-chart-wrap';
    if (data.title) {
      var heading = document.createElement('div');
      heading.className = 'bm-chart-title';
      heading.textContent = data.title;
      wrap.appendChild(heading);
    }
    var canvas = document.createElement('canvas');
    wrap.appendChild(canvas);
    table.insertAdjacentElement('afterend', wrap);
    var config = {
      type: data.type === 'pie' ? 'pie' : 'bar',
      data: {
        labels: data.labels,
        datasets: [
          {
            data: data.values,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true },
        },
      },
    };
    if (config.type !== 'pie') {
      config.options.scales = { y: { beginAtZero: true } };
    }
    wrap.style.height = '360px';
    new window.Chart(canvas.getContext('2d'), config);
  }
  function enhanceTables(root) {
    var tables = root.querySelectorAll('table[data-ui="datatable"]');
    Array.prototype.forEach.call(tables, function (table) {
      var data = tableToChartData(table);
      if (data) {
        renderChartNextToTable(table, data);
      }
    });
  }
  ready(function () {
    var root = document.querySelector('.bm-article-page') || document;
    var heroImage = document.querySelector('.article-hero img');
    var bodyImages = root.querySelectorAll('.article-body img');
    bodyImages.forEach(function (img) {
      if (!heroImage || img !== heroImage) {
        if (!img.getAttribute('loading')) {
          img.setAttribute('loading', 'lazy');
        }
        if (!img.getAttribute('decoding')) {
          img.setAttribute('decoding', 'async');
        }
      }
    });
    enhanceCallouts(root);
    enhanceChecklists(root);
    enhanceSteps(root);
    enhanceTables(root);
    var tocContainer = document.getElementById('bm-article-toc');
    var tocList = document.getElementById('bm-article-toc-list');
    if (!tocContainer || !tocList) {
      return;
    }
    var headings = Array.prototype.slice.call(document.querySelectorAll('#bm-article-main h2, #bm-article-main h3'));
    headings = headings.filter(function (heading) {
      return heading && heading.textContent && heading.textContent.trim().length;
    });
    if (!headings.length) {
      tocContainer.hidden = true;
      return;
    }
    var slugCounts = Object.create(null);
    headings.forEach(function (heading, index) {
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
      var link = document.createElement('a');
      link.href = '#' + id;
      link.textContent = text;
      link.setAttribute('data-depth', heading.tagName === 'H3' ? '3' : '2');
      link.addEventListener('click', function (event) {
        event.preventDefault();
        var target = document.getElementById(id);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          history.replaceState(null, '', '#' + id);
        }
      });
      var item = document.createElement('li');
      item.appendChild(link);
      tocList.appendChild(item);
    });
    tocContainer.dataset.empty = 'false';
    var links = Array.prototype.slice.call(tocList.querySelectorAll('a'));
    var activeId = headings[0].id;
    function setActive(id) {
      if (!id || id === activeId) {
        return;
      }
      activeId = id;
      links.forEach(function (link) {
        link.classList.toggle('is-active', link.getAttribute('href') === '#' + id);
      });
    }
    var visibility = new Map();
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          visibility.set(entry.target.id, entry.isIntersecting ? entry.intersectionRatio : 0);
        });
        updateActive();
      },
      {
        rootMargin: '-55% 0px -35% 0px',
        threshold: [0, 0.25, 0.5, 0.75, 1],
      }
    );
    function updateActive() {
      var bestId = '';
      var bestScore = 0;
      visibility.forEach(function (score, id) {
        if (score > bestScore) {
          bestScore = score;
          bestId = id;
        }
      });
      if (!bestId) {
        var fallback = '';
        for (var i = 0; i < headings.length; i += 1) {
          var rect = headings[i].getBoundingClientRect();
          if (rect.top - 140 <= 0) {
            fallback = headings[i].id;
          } else {
            break;
          }
        }
        bestId = fallback || headings[0].id;
      }
      setActive(bestId);
    }
    headings.forEach(function (heading) {
      observer.observe(heading);
    });
    window.addEventListener(
      'scroll',
      function () {
        window.requestAnimationFrame(updateActive);
      },
      { passive: true }
    );
    updateActive();
    var sidebarInner = document.querySelector('.bm-article-page__sidebar-inner');
    if (sidebarInner) {
      var guard = document.createElement('div');
      guard.className = 'bm-article-page__sidebar-guard';
      guard.style.position = 'absolute';
      guard.style.top = '0';
      guard.style.height = '1px';
      guard.style.width = '1px';
      sidebarInner.parentElement.insertBefore(guard, sidebarInner);
      var stickyObserver = new IntersectionObserver(
        function (entries) {
          var entry = entries[0];
          sidebarInner.classList.toggle('is-stuck', entry.intersectionRatio < 1);
        },
        { rootMargin: '-120px 0px 0px 0px', threshold: [1] }
      );
      stickyObserver.observe(guard);
    }
  });
})();