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
  function normalizeChartType(type) {
    if (!type) {
      return '';
    }
    if (type === 'donut') {
      return 'doughnut';
    }
    if (type === 'pie' || type === 'doughnut' || type === 'bar') {
      return type;
    }
    return '';
  }
  function ensureChartCard(table) {
    var card = table.closest('.chart-card');
    if (card) {
      card.classList.add('chart-card');
      return card;
    }
    var parent = table.parentElement;
    if (parent && !parent.classList.contains('charts-grid')) {
      parent.classList.add('chart-card');
      return parent;
    }
    card = document.createElement('div');
    card.className = 'chart-card';
    if (parent) {
      parent.insertBefore(card, table);
    }
    card.appendChild(table);
    return card;
  }
  function extractTableDataset(table) {
    var rows = table.querySelectorAll('tbody tr');
    var labelIndex = parseInt(table.getAttribute('data-label-index'), 10);
    var valueIndex = parseInt(table.getAttribute('data-value-index'), 10);
    if (isNaN(labelIndex)) {
      labelIndex = 0;
    }
    if (isNaN(valueIndex)) {
      valueIndex = 1;
    }
    var labels = [];
    var values = [];
    Array.prototype.forEach.call(rows, function (row) {
      var cells = row.children;
      if (!cells || !cells.length) {
        return;
      }
      var labelCell = cells[labelIndex];
      var valueCell = cells[valueIndex];
      if (!labelCell || !valueCell) {
        return;
      }
      var label = labelCell.textContent ? labelCell.textContent.trim() : '';
      var rawValue = valueCell.textContent ? valueCell.textContent.trim() : '';
      var normalized = rawValue.replace(/[^0-9.,\-]/g, '');
      if (normalized.indexOf(',') !== -1 && normalized.indexOf('.') === -1) {
        normalized = normalized.replace(',', '.');
      } else {
        normalized = normalized.replace(/,/g, '');
      }
      var numeric = parseFloat(normalized);
      if (label && !isNaN(numeric) && isFinite(numeric)) {
        labels.push(label);
        values.push(numeric);
      }
    });
    return { labels: labels, values: values };
  }
  function buildChartConfig(type, dataset, palette, title) {
    var colors = dataset.labels.map(function (_, index) {
      return palette[index % palette.length];
    });
    var config = {
      type: type === 'doughnut' ? 'doughnut' : type === 'bar' ? 'bar' : 'pie',
      data: {
        labels: dataset.labels,
        datasets: [
          {
            data: dataset.values,
            backgroundColor: colors,
            borderWidth: 0,
            borderRadius: type === 'bar' ? 12 : 0,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        locale: 'he-IL',
        layout: { padding: 8 },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              usePointStyle: true,
              boxWidth: 14,
            },
          },
          tooltip: { rtl: true, titleAlign: 'right', bodyAlign: 'right' },
          title: {
            display: Boolean(title),
            text: title,
            align: 'start',
            font: { weight: '600', size: 15 },
            padding: { bottom: 10 },
          },
        },
      },
    };
    if (config.type === 'bar') {
      config.options.indexAxis = 'y';
      config.options.scales = {
        x: {
          grid: { display: false },
          ticks: { precision: 0 },
        },
        y: {
          grid: { display: false },
        },
      };
    }
    return config;
  }
  function upgradeTablesToCharts(root) {
    if (typeof window.Chart !== 'function') {
      return;
    }
    var scope = root || document;
    var tables = scope.querySelectorAll('table[data-ui="datatable"][data-chart]');
    if (!tables.length) {
      return;
    }
    var computed = window.getComputedStyle(document.documentElement);
    var brand = computed.getPropertyValue('--brand').trim() || '#8A1538';
    var brandSoft = computed.getPropertyValue('--brand-soft').trim() || '#EBD0D8';
    var accent = computed.getPropertyValue('--hero-accent').trim() || '#2E3A45';
    var palette = [
      brand,
      accent,
      brandSoft,
      '#4a6b6f',
      '#7fbfb0',
      '#a7d7c5',
      '#2f4858',
      '#b56982',
      '#6a9fb5',
      '#94c678',
      '#e6a266',
      '#c1b6e0',
    ];
    Array.prototype.forEach.call(tables, function (table) {
      if (table.dataset.chartProcessed === '1') {
        return;
      }
      var rawType = (table.getAttribute('data-chart') || '').toLowerCase();
      var type = normalizeChartType(rawType);
      if (!type) {
        return;
      }
      var dataset = extractTableDataset(table);
      if (!dataset.labels.length || !dataset.values.length) {
        return;
      }
      var card = ensureChartCard(table);
      var canvas = document.createElement('canvas');
      canvas.dir = document.documentElement.getAttribute('dir') || 'rtl';
      var title = table.getAttribute('data-chart-title') || '';
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', title || table.getAttribute('aria-label') || 'תרשים נתונים');
      card.insertBefore(canvas, table);
      table.classList.add('visually-hidden');
      table.dataset.chartProcessed = '1';
      var config = buildChartConfig(type, dataset, palette, title);
      try {
        new window.Chart(canvas.getContext('2d'), config);
      } catch (chartError) {
        table.classList.remove('visually-hidden');
        table.dataset.chartProcessed = '0';
        if (window && window.console) {
          console.warn('chart render failed', chartError);
        }
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
    try {
      upgradeTablesToCharts(root);
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