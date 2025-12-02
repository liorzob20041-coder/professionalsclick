(function () {
  function buildToc() {
    var main = document.getElementById('bm-article-main');
    var toc = document.getElementById('bm-article-toc');
    if (!main || !toc) return;

    var list = toc.querySelector('.bm-article-toc-list');
    if (!list) return;

    var headings = main.querySelectorAll('h2, h3');
    var items = [];

    headings.forEach(function (heading, index) {
      var text = heading.textContent && heading.textContent.trim();
      if (!text) return;
      if (!heading.id) {
        heading.id = 'bm-article-heading-' + (index + 1);
      }
      items.push({ id: heading.id, text: text, level: heading.tagName.toLowerCase() });
    });

    if (!items.length) {
      toc.setAttribute('data-empty', 'true');
      return;
    }

    toc.removeAttribute('data-empty');
    list.innerHTML = '';

    items.forEach(function (item) {
      var li = document.createElement('li');
      if (item.level === 'h3') {
        li.classList.add('bm-article-toc-subitem');
      }
      var link = document.createElement('a');
      link.href = '#' + item.id;
      link.textContent = item.text;
      li.appendChild(link);
      list.appendChild(li);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildToc);
  } else {
    buildToc();
  }
})();