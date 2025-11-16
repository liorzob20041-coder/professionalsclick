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
  var chartRegistry = [];
  var chartDefaultsApplied = false;
  var BRAND_COLORS = {
    primary: '#8A1538',
    dark: '#2E3A46',
    muted: '#5C6B77',
    soft: '#CADFD9',
    mint: '#A7E2CF',
    blush: '#F2CBD2',
  };
  var PIE_COLORS = [
    BRAND_COLORS.primary,
    BRAND_COLORS.dark,
    '#0E6D73',
    BRAND_COLORS.mint,
    '#9AD1C8',
    BRAND_COLORS.blush,
    BRAND_COLORS.soft,
  ];
  var BAR_COLORS = [
    BRAND_COLORS.primary,
    BRAND_COLORS.mint,
    BRAND_COLORS.dark,
    BRAND_COLORS.soft,
    '#6CA7A8',
    BRAND_COLORS.blush,
  ];
  function applyChartDefaults() {
    if (chartDefaultsApplied || typeof window.Chart !== 'function') {
      return;
    }
    chartDefaultsApplied = true;
    if (window.Chart.defaults) {
      window.Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", "Noto Sans", "Helvetica Neue", Arial, sans-serif';
      window.Chart.defaults.font.size = 14;
      if (!window.Chart.defaults.plugins) {
        window.Chart.defaults.plugins = {};
      }
      if (!window.Chart.defaults.plugins.tooltip) {
        window.Chart.defaults.plugins.tooltip = {};
      }
      window.Chart.defaults.plugins.tooltip.rtl = true;
      window.Chart.defaults.plugins.tooltip.bodyAlign = 'right';
      window.Chart.defaults.plugins.tooltip.titleAlign = 'right';
    }
  }
  function resolveChartType(value) {
    var normalized = (value || 'bar').toLowerCase();
    if (normalized === 'pie' || normalized === 'doughnut' || normalized === 'donut') {
      return 'doughnut';
    }
    return 'bar';
  }
  function parseTableDataset(table) {
    if (!table) {
      return null;
    }
    var body = table.querySelector('tbody');
    if (!body) {
      return null;
    }
    var rows = body.querySelectorAll('tr');
    if (!rows.length) {
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
      if (!label || !rawValue) {
        return;
      }
      var normalized = rawValue.replace(/[^0-9.,\-]/g, '');
      if (!normalized) {
        return;
      }
      if (normalized.indexOf(',') !== -1 && normalized.indexOf('.') === -1) {
        normalized = normalized.replace(',', '.');
      } else {
        normalized = normalized.replace(/,/g, '');
      }
      var numeric = parseFloat(normalized);
      if (!isNaN(numeric) && isFinite(numeric)) {
        labels.push(label);
        values.push(numeric);
      }
    });
    if (!labels.length || !values.length) {
      return null;
    }
    return { labels: labels, values: values };
  }
  function ensureChartCard(table, titleText) {
    var card = table.previousElementSibling;
    var createdCard = false;
    while (card && card.nodeType === 3) {
      card = card.previousSibling;
    }
    if (!card || !card.classList || !card.classList.contains('chart-card')) {
      card = document.createElement('div');
      card.className = 'chart-card';
      card.dir = document.documentElement.getAttribute('dir') || 'rtl';
      table.parentNode.insertBefore(card, table);
      createdCard = true;
    }
    var heading = card.querySelector('h4');
    if (titleText) {
      if (!heading) {
        heading = document.createElement('h4');
        card.insertBefore(heading, card.firstChild);
      }
      heading.textContent = titleText;
    } else if (heading) {
      heading.parentNode.removeChild(heading);
    }
    var canvas = card.querySelector('canvas.chart-canvas');
    var createdCanvas = false;
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.className = 'chart-canvas';
      canvas.dir = document.documentElement.getAttribute('dir') || 'rtl';
      card.appendChild(canvas);
      createdCanvas = true;
    }
    var requestedSize = (table.getAttribute('data-chart-size') || 'sm').toLowerCase();
    if (requestedSize !== 'md' && requestedSize !== 'lg') {
      requestedSize = 'sm';
    }
    canvas.setAttribute('data-size', requestedSize);
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', titleText || table.getAttribute('aria-label') || 'תרשים נתונים');
    return { card: card, canvas: canvas, createdCard: createdCard, createdCanvas: createdCanvas };
  }
  function storeChart(table, canvas, instance) {
    var found = null;
    for (var i = 0; i < chartRegistry.length; i += 1) {
      if (chartRegistry[i].table === table) {
        found = chartRegistry[i];
        break;
      }
    }
    if (found) {
      found.canvas = canvas;
      found.instance = instance;
    } else {
      chartRegistry.push({ table: table, canvas: canvas, instance: instance });
    }
  }
  function buildChartOptions(isDoughnut) {
    var legendDisplay = !!isDoughnut;
    var options = {
      responsive: true,
      maintainAspectRatio: false,
      locale: 'he-IL',
      interaction: { intersect: false, mode: 'nearest' },
      plugins: {
        legend: {
          display: legendDisplay,
          position: 'bottom',
          labels: {
            usePointStyle: true,
            boxWidth: 8,
            padding: 12,
            color: BRAND_COLORS.dark,
            textAlign: 'right',
          },
        },
        title: { display: false },
        tooltip: {
          rtl: true,
          bodyAlign: 'right',
          titleAlign: 'right',
          backgroundColor: BRAND_COLORS.dark,
        },
      },
    };
    if (!isDoughnut) {
      options.indexAxis = 'y';
      options.scales = {
        x: {
          beginAtZero: true,
          grid: { display: false, drawBorder: false },
          ticks: { color: BRAND_COLORS.muted, precision: 0 },
        },
        y: {
          grid: { display: false, drawBorder: false },
          ticks: { color: BRAND_COLORS.dark, autoSkip: false },
        },
      };
    } else {
      options.cutout = '60%';
    }
    return options;
  }
  function renderChartFromTable(table) {
    if (table.dataset.chartProcessed === '1') {
      return;
    }
    var dataset = parseTableDataset(table);
    if (!dataset) {
      return;
    }
    var type = resolveChartType(table.getAttribute('data-chart'));
    var titleText = table.getAttribute('data-chart-title') || '';
    var datasetLabel = table.getAttribute('data-dataset-label') || 'ערכים';
    var elements = ensureChartCard(table, titleText);
    var palette = type === 'doughnut' ? PIE_COLORS : BAR_COLORS;
    var colors = dataset.labels.map(function (_, index) {
      return palette[index % palette.length];
    });
    var chartConfig = {
      type: type,
      data: {
        labels: dataset.labels,
        datasets: [
          {
            label: datasetLabel,
            data: dataset.values,
            backgroundColor: colors,
            borderWidth: 0,
            borderRadius: type === 'doughnut' ? 0 : 12,
            hoverBackgroundColor: type === 'doughnut' ? undefined : BRAND_COLORS.primary,
            minBarLength: 3,
          },
        ],
      },
      options: buildChartOptions(type === 'doughnut'),
    };
    if (type !== 'doughnut') {
      chartConfig.data.datasets[0].borderSkipped = false;
    }
    try {
      var chart = new window.Chart(elements.canvas.getContext('2d'), chartConfig);
      table.dataset.chartProcessed = '1';
      table.classList.add('visually-hidden');
      table.setAttribute('aria-hidden', 'true');
      storeChart(table, elements.canvas, chart);
    } catch (chartError) {
      if (elements.createdCanvas && elements.canvas.parentNode) {
        elements.canvas.parentNode.removeChild(elements.canvas);
      }
      if (elements.createdCard && elements.card.parentNode) {
        elements.card.parentNode.removeChild(elements.card);
      }
      table.classList.remove('visually-hidden');
      table.removeAttribute('aria-hidden');
      if (window && window.console) {
        console.warn('chart render failed', chartError);
      }
    }
  }
  function initArticleCharts(root) {
    if (typeof window.Chart !== 'function') {
      return;
    }
    applyChartDefaults();
    var scope = root || document;
    var tables = scope.querySelectorAll('table[data-ui="datatable"][data-chart]');
    if (!tables.length) {
      return;
    }
    Array.prototype.forEach.call(tables, function (table) {
      renderChartFromTable(table);
    });
  }
  function rebuildCharts() {
    if (!chartRegistry.length) {
      return;
    }
    var tables = chartRegistry.map(function (entry) {
      if (entry.instance && typeof entry.instance.destroy === 'function') {
        entry.instance.destroy();
      }
      entry.table.dataset.chartProcessed = '0';
      return entry.table;
    });
    chartRegistry = [];
    tables.forEach(function (table) {
      renderChartFromTable(table);
    });
  }
  var resizeTimer = null;
  window.addEventListener(
    'resize',
    function () {
      if (!chartRegistry.length) {
        return;
      }
      if (resizeTimer) {
        window.clearTimeout(resizeTimer);
      }
      resizeTimer = window.setTimeout(rebuildCharts, 200);
    },
    { passive: true }
  );
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