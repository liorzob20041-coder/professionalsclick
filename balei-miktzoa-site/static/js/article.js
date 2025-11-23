(function () {
  'use strict';
  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
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
  function upgradeChartGrids(root) {
    qsa('.charts-grid', root || document).forEach(function (grid) {
      var wrapper = document.createElement('div');
      wrapper.className = 'article-charts';
      wrapper.setAttribute('dir', 'rtl');
      qsa(':scope > *', grid).forEach(function (child) {
        if (!child) {
          return;
        }
        var card = child.classList && child.classList.contains('chart-card') ? child : document.createElement('section');
        if (!child.classList || !child.classList.contains('chart-card')) {
          card.className = 'chart-card';
          while (child.firstChild) {
            card.appendChild(child.firstChild);
          }
        }
        var table = card.querySelector('table[data-ui="datatable"][data-chart]');
        if (table) {
          var typeAttr = (table.dataset.chart || '').toLowerCase();
          if (['pie', 'donut', 'doughnut'].indexOf(typeAttr) !== -1) {
            card.setAttribute('data-shape', 'square');
          }
        }
        wrapper.appendChild(card);
      });
      grid.replaceWith(wrapper);
    });
  }
  var chartInstances = [];
  var windowResizeBound = false;
  function resizeAllCharts() {
    chartInstances.forEach(function (chart) {
      if (chart && chart.resize) {
        chart.resize();
      }
    });
  }
  var chartResizeObserver = new ResizeObserver(function (entries) {
    entries.forEach(function (entry) {
      var chart = entry.target.__chartInstance;
      if (chart && chart.resize) {
        chart.resize();
      }
    });
  });
  var chartViewportObserver = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          var chart = entry.target.__chartInstance;
          if (chart && chart.resize) {
            chart.resize();
          }
        }
      });
    },
    { threshold: 0.2 }
  );
  function ensureChartCanvas(tbl) {
    var wrapper = tbl.closest('.chart-canvas');
    if (!wrapper) {
      wrapper = document.createElement('div');
      wrapper.className = 'chart-canvas';
      tbl.parentNode.insertBefore(wrapper, tbl);
      wrapper.appendChild(tbl);
    }
    return wrapper;
  }
  function mountChartFromTable(tbl) {
    var typeAttr = (tbl.dataset.chart || '').toLowerCase();
    var isPie = ['pie', 'donut', 'doughnut'].indexOf(typeAttr) !== -1;
    var isBar = typeAttr === 'bar' || typeAttr === 'bar-h';
    var card = tbl.closest('.chart-card');
    if (!card) {
      card = document.createElement('section');
      card.className = 'chart-card';
      tbl.parentNode.insertBefore(card, tbl);
      card.appendChild(tbl);
    }
    if (isPie) {
      card.setAttribute('data-shape', 'square');
    }
    card.dataset.chartType = isPie ? 'pie' : isBar ? 'bar-h' : 'other';
    var canvasWrapper = ensureChartCanvas(tbl);
    var canvas = canvasWrapper.querySelector('canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvasWrapper.appendChild(canvas);
    }
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
    canvasWrapper.__chartInstance = chart;
    chartInstances.push(chart);
    chartResizeObserver.observe(canvasWrapper);
    chartViewportObserver.observe(canvasWrapper);
    if (!windowResizeBound) {
      windowResizeBound = true;
      window.addEventListener('resize', resizeAllCharts);
    }
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
    upgradeChartGrids(root);
    var heroImage = document.querySelector('.article-hero__media img');
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
  });
})();