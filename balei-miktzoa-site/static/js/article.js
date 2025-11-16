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
  var qsa = function (sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  };
  function mountChartFromTable(tbl) {
    var typeAttr = (tbl.dataset.chart || '').toLowerCase();
    var isPie = ['pie', 'donut'].indexOf(typeAttr) !== -1;
    var isBar = typeAttr === 'bar' || typeAttr === 'bar-h';
    var card = tbl.closest('.chart-card');
    if (!card) {
      card = document.createElement('div');
      card.className = 'chart-card';
      tbl.parentNode.insertBefore(card, tbl);
      card.appendChild(tbl);
    }
    card.dataset.chartType = isPie ? 'pie' : isBar ? 'bar-h' : 'other';
    var canvas = document.createElement('canvas');
    canvas.className = 'chart-canvas';
    card.appendChild(canvas);
    var rows = qsa('tbody tr', tbl);
    var labels = rows.map(function (r) {
      return r.children[0].textContent.trim();
    });
    var values = rows.map(function (r) {
      var raw = r.children[1].textContent;
      var normalized = String(raw).replace(/[^\d.]/g, '');
      return parseFloat(normalized) || 0;
    });
    tbl.hidden = true;
    var ctx = canvas.getContext('2d');
    var cfg = {
      type: isPie ? 'doughnut' : 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: tbl.dataset.chartTitle ? tbl.dataset.chartTitle : '',
            data: values,
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 12, usePointStyle: true, font: { size: 12 } },
          },
          title: tbl.dataset.chartTitle ? { display: true, text: tbl.dataset.chartTitle } : { display: false },
        },
        layout: { padding: { left: 6, right: 6, top: 0, bottom: 0 } },
        scales: isPie
          ? {}
          : {
              x: { ticks: { font: { size: 11 } }, grid: { display: false } },
              y: { ticks: { font: { size: 11 } }, grid: { color: 'rgba(0,0,0,.06)' } },
            },
        indexAxis: isBar ? 'y' : 'x',
      },
    };
    var chart = new Chart(ctx, cfg);
    var ro = new ResizeObserver(function () {
      chart.resize();
    });
    ro.observe(card);
  }
  function initArticleCharts(root) {
    if (typeof Chart !== 'function') {
      return;
    }
    qsa('table[data-ui="datatable"][data-chart]', root || document).forEach(function (tbl) {
      mountChartFromTable(tbl);
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
    try {
      initArticleCharts(root);
    } catch (err) {
      if (window && window.console) {
        console.warn('chart upgrade failed', err);
      }
    }
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