/* ─────────────────────────────────────────────────────────────────────
   FOLIO New Materials — client app
   Reads embedded JSON from <script type="application/json" id="items-data">
   and builds both grid and table views.  Filters, sorts, and view toggle
   operate on the rendered DOM (avoids re-rendering on each interaction).
   ───────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  var STORAGE_KEY = 'folio-new-materials:view';

  // ── Load embedded data ──────────────────────────────────────────────
  var dataEl = document.getElementById('items-data');
  if (!dataEl) {
    console.error('[folio] items-data block missing');
    return;
  }

  var data;
  try {
    data = JSON.parse(dataEl.textContent);
  } catch (err) {
    console.error('[folio] failed to parse items data', err);
    return;
  }
  var items = data.items || [];

  // Display preferences come from data-* attributes on <html> (see template)
  var holdingsMode = document.documentElement.getAttribute('data-holdings-display') || 'summary';

  // ── DOM helpers ─────────────────────────────────────────────────────
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      for (var key in attrs) {
        if (key === 'class')      node.className = attrs[key];
        else if (key === 'data')  Object.assign(node.dataset, attrs[key]);
        else if (key === 'style') node.setAttribute('style', attrs[key]);
        else if (key.indexOf('aria-') === 0 || key === 'role')
                                  node.setAttribute(key, attrs[key]);
        else                      node[key] = attrs[key];
      }
    }
    if (children) {
      for (var i = 0; i < children.length; i++) {
        var c = children[i];
        if (c == null || c === false) continue;
        node.appendChild(typeof c === 'string'
          ? document.createTextNode(c)
          : c);
      }
    }
    return node;
  }

  function dataAttrs(item) {
    return {
      data: {
        type:    item.type_uuid || '',
        subject: item.subject_group || '',
        title:   (item.title || '').toLowerCase(),
        author:  (item.author || '').toLowerCase(),
        date:    item.receipt_date || ''
      }
    };
  }

  // ── Build a single grid card ────────────────────────────────────────
  function buildCard(item, index) {
    var fullTitle = item.title || '';

    var coverChild = item.cover_url
      ? el('img', {
          class:   'card-cover',
          src:     item.cover_url,
          alt:     'Cover of ' + fullTitle,
          loading: 'lazy'
        })
      : el('div', {
          class: 'card-placeholder',
          style: '--placeholder-color: ' + (item.placeholder_color || '#5a6c7d') + ';',
          'aria-hidden': 'true'
        }, [
          el('span', { class: 'ph-type'  }, [item.type_label || 'Item']),
          el('span', { class: 'ph-title' }, [fullTitle])
        ]);

    // The title link carries title="..." so hovering shows the full
    // (CSS-truncated) title via native browser tooltip.  Screen readers
    // read the full title text inside the link.
    var titleLink = item.eds_url
      ? el('a', {
          href:   item.eds_url,
          title:  fullTitle,
          target: '_blank',
          rel:    'noopener noreferrer'
        }, [fullTitle])
      : el('span', { title: fullTitle }, [fullTitle]);

    var bodyChildren = [
      el('h2', { class: 'card-title', id: 'grid-title-' + index }, [titleLink])
    ];
    if (item.author) {
      bodyChildren.push(el('p', { class: 'card-author', title: item.author }, [item.author]));
    }
    // (publisher intentionally omitted from display — still in items.json)
    if (item.year) {
      bodyChildren.push(el('p', { class: 'card-year' }, [item.year]));
    }

    var holdingsNode = buildHoldingsBlock(item, false);
    if (holdingsNode) bodyChildren.push(holdingsNode);

    var metaChildren = [
      el('span', { class: 'badge' }, [item.type_label || 'Other'])
    ];
    if (item.subject_group) {
      metaChildren.push(el('span', {
        class: 'badge badge-subject',
        title: item.subject_group
      }, [item.subject_group]));
    }
    if (item.receipt_date) {
      metaChildren.push(el('span', { class: 'card-received', title: 'Received' }, [
        el('span', { class: 'sr-only' }, ['Received: ']),
        item.receipt_date
      ]));
    }
    bodyChildren.push(el('div', { class: 'card-meta' }, metaChildren));

    var article = el('article', { 'aria-labelledby': 'grid-title-' + index }, [
      el('div', { class: 'card-cover-wrap' }, [coverChild]),
      el('div', { class: 'card-body' }, bodyChildren)
    ]);

    var attrs = dataAttrs(item);
    attrs.class = 'material-card filterable-item';
    return el('li', attrs, [article]);
  }

  // ── Holdings block (consortium / multi-branch aware) ─────────────────
  function buildHoldingsBlock(item, isTable) {
    var holdings = item.holdings || [];
    if (holdingsMode === 'none' || holdings.length === 0) {
      // Fall back to the legacy single call_number when no RTAC holdings
      if (item.call_number) {
        return el('p', { class: 'card-callno' }, [item.call_number]);
      }
      return null;
    }

    if (holdingsMode === 'compact') {
      var label = holdings.length === 1 ? '1 copy' : holdings.length + ' copies';
      return el('p', { class: 'card-callno' }, [label]);
    }

    if (holdingsMode === 'detailed') {
      var list = el('ul', { class: 'card-holdings card-holdings-detail' });
      holdings.forEach(function (h) {
        list.appendChild(el('li', null, [formatHoldingLine(h)]));
      });
      return list;
    }

    // summary (default): show first holding with a "+N more" hint
    var first = holdings[0];
    var primary = el('p', { class: 'card-callno' }, [formatHoldingLine(first)]);
    if (holdings.length > 1) {
      primary.appendChild(el('span', {
        class: 'card-callno-more',
        title: formatRemainingHoldings(holdings.slice(1))
      }, [' +' + (holdings.length - 1) + ' more']));
    }
    return primary;
  }

  function formatHoldingLine(h) {
    var parts = [];
    if (h.call_number) parts.push(h.call_number);
    if (h.library)     parts.push(h.library);
    else if (h.location) parts.push(h.location);
    return parts.join(' — ');
  }

  function formatRemainingHoldings(rest) {
    return rest.map(formatHoldingLine).join('\n');
  }

  // ── Build a single table row ────────────────────────────────────────
  function buildRow(item, hasSubject) {
    var fullTitle = item.title || '';

    var coverChild = item.cover_url
      ? el('img', { src: item.cover_url, alt: '', loading: 'lazy' })
      : el('div', {
          class: 'ph-mini',
          style: '--placeholder-color: ' + (item.placeholder_color || '#5a6c7d') + ';',
          'aria-hidden': 'true'
        });

    var titleNode = item.eds_url
      ? el('a', {
          class:  'row-title',
          href:   item.eds_url,
          title:  fullTitle,
          target: '_blank',
          rel:    'noopener noreferrer'
        }, [fullTitle])
      : el('span', { class: 'row-title', title: fullTitle }, [fullTitle]);

    var titleChildren = [titleNode];
    if (item.year) {
      titleChildren.push(el('div', { class: 'col-meta' }, [item.year]));
    }

    var cells = [
      el('td', { class: 'col-cover' }, [coverChild]),
      el('td', null, titleChildren),
      el('td', { class: 'col-meta' }, [item.author || '']),
      el('td', { class: 'col-meta' }, [item.type_label || ''])
    ];
    if (hasSubject) {
      cells.push(el('td', { class: 'col-meta' }, [item.subject_group || '']));
    }
    cells.push(
      el('td', { class: 'col-meta' }, [buildHoldingsCell(item)]),
      el('td', { class: 'col-meta col-date' }, [item.receipt_date || ''])
    );

    var attrs = dataAttrs(item);
    attrs.class = 'material-row filterable-item';
    return el('tr', attrs, cells);
  }

  // ── Table version of the holdings cell ──────────────────────────────
  function buildHoldingsCell(item) {
    var holdings = item.holdings || [];
    if (holdingsMode === 'none' || holdings.length === 0) {
      return document.createTextNode(item.call_number || '');
    }
    if (holdingsMode === 'compact') {
      return document.createTextNode(
        holdings.length + (holdings.length === 1 ? ' copy' : ' copies')
      );
    }
    if (holdingsMode === 'detailed') {
      var list = el('ul', { class: 'table-holdings' });
      holdings.forEach(function (h) {
        list.appendChild(el('li', null, [formatHoldingLine(h)]));
      });
      return list;
    }
    // summary
    var first = holdings[0];
    var label = formatHoldingLine(first);
    if (holdings.length > 1) {
      label += ' +' + (holdings.length - 1);
    }
    var span = el('span', null, [label]);
    if (holdings.length > 1) {
      span.title = formatRemainingHoldings(holdings.slice(1));
    }
    return span;
  }

  // ── Render both views ───────────────────────────────────────────────
  var grid       = document.getElementById('materials-grid');
  var tableWrap  = document.getElementById('materials-table-wrap');
  var tableBody  = tableWrap ? tableWrap.querySelector('tbody') : null;
  var hasSubject = !!document.getElementById('subject-filter');

  if (grid) {
    items.forEach(function (item, i) { grid.appendChild(buildCard(item, i)); });
  }
  if (tableBody) {
    items.forEach(function (item) { tableBody.appendChild(buildRow(item, hasSubject)); });
  }

  var cards = grid ? [].slice.call(grid.querySelectorAll('.material-card')) : [];
  var rows  = tableBody ? [].slice.call(tableBody.querySelectorAll('.material-row')) : [];

  // ── View toggle ─────────────────────────────────────────────────────
  var viewButtons = document.querySelectorAll('.view-toggle button');
  function setView(view) {
    if (view !== 'grid' && view !== 'table') view = 'grid';
    if (grid)      grid.hidden      = view !== 'grid';
    if (tableWrap) tableWrap.hidden = view !== 'table';
    viewButtons.forEach(function (btn) {
      btn.setAttribute('aria-pressed', btn.dataset.view === view ? 'true' : 'false');
    });
    try { localStorage.setItem(STORAGE_KEY, view); } catch (e) { /* ignore */ }
  }
  viewButtons.forEach(function (btn) {
    btn.addEventListener('click', function () { setView(btn.dataset.view); });
  });
  try {
    var saved = localStorage.getItem(STORAGE_KEY);
    if (saved) setView(saved);
  } catch (e) { /* ignore */ }

  // ── Filtering ───────────────────────────────────────────────────────
  var searchInput   = document.getElementById('search-input');
  var formatSelect  = document.getElementById('format-filter');
  var subjectSelect = document.getElementById('subject-filter');
  var sortSelect    = document.getElementById('sort-select');
  var clearBtn      = document.getElementById('clear-filters');
  var chipsHost     = document.getElementById('active-filters');
  var counter       = document.getElementById('results-count');
  var noResults     = document.getElementById('no-results');

  function getState() {
    return {
      search:  (searchInput && searchInput.value || '').trim().toLowerCase(),
      format:  formatSelect ? formatSelect.value : 'all',
      subject: subjectSelect ? subjectSelect.value : 'all'
    };
  }

  function matches(node, state) {
    if (state.format !== 'all'  && node.dataset.type !== state.format)   return false;
    if (state.subject !== 'all' && node.dataset.subject !== state.subject) return false;
    if (state.search) {
      var hay = node.dataset.title + ' ' + node.dataset.author;
      if (hay.indexOf(state.search) === -1) return false;
    }
    return true;
  }

  function renderChips(state) {
    if (!chipsHost) return;
    chipsHost.textContent = '';
    var any = false;

    function addChip(label, onClear) {
      any = true;
      var btn = el('button', {
        type: 'button',
        'aria-label': 'Remove filter ' + label
      }, ['×']);
      btn.addEventListener('click', onClear);
      var chip = el('span', { class: 'filter-chip' }, [label + ' ', btn]);
      chipsHost.appendChild(chip);
    }

    if (state.format !== 'all' && formatSelect) {
      var opt = formatSelect.options[formatSelect.selectedIndex];
      addChip('Format: ' + opt.text.replace(/\s*\(\d+\)$/, ''), function () {
        formatSelect.value = 'all'; applyFilters();
      });
    }
    if (subjectSelect && state.subject !== 'all') {
      var s = subjectSelect.options[subjectSelect.selectedIndex];
      addChip('Subject: ' + s.text.replace(/\s*\(\d+\)$/, ''), function () {
        subjectSelect.value = 'all'; applyFilters();
      });
    }
    if (state.search) {
      addChip('Search: "' + state.search + '"', function () {
        searchInput.value = ''; applyFilters();
      });
    }
    if (clearBtn) clearBtn.hidden = !any;
  }

  function applyFilters() {
    var state = getState();
    var visible = 0;
    cards.forEach(function (node) {
      var show = matches(node, state);
      node.hidden = !show;
      if (show) visible++;
    });
    rows.forEach(function (node) {
      node.hidden = !matches(node, state);
    });
    if (counter) {
      counter.textContent = 'Showing ' + visible + ' item' + (visible !== 1 ? 's' : '');
    }
    if (noResults) noResults.hidden = visible > 0;
    renderChips(state);
  }

  function clearAll() {
    if (searchInput)   searchInput.value = '';
    if (formatSelect)  formatSelect.value = 'all';
    if (subjectSelect) subjectSelect.value = 'all';
    applyFilters();
  }

  // ── Sorting ─────────────────────────────────────────────────────────
  function cmp(a, b, mode) {
    if (mode === 'newest')    return (b.dataset.date || '').localeCompare(a.dataset.date || '');
    if (mode === 'oldest')    return (a.dataset.date || '').localeCompare(b.dataset.date || '');
    if (mode === 'title-asc') return (a.dataset.title || '').localeCompare(b.dataset.title || '');
    if (mode === 'title-desc')return (b.dataset.title || '').localeCompare(a.dataset.title || '');
    return 0;
  }

  function applySort() {
    if (!sortSelect) return;
    var mode = sortSelect.value;
    if (grid)      cards.slice().sort(function (a, b) { return cmp(a, b, mode); })
                                .forEach(function (n) { grid.appendChild(n); });
    if (tableBody) rows.slice().sort(function (a, b) { return cmp(a, b, mode); })
                                .forEach(function (n) { tableBody.appendChild(n); });
  }

  // ── Wire up ─────────────────────────────────────────────────────────
  if (searchInput)   searchInput.addEventListener('input',  applyFilters);
  if (formatSelect)  formatSelect.addEventListener('change', applyFilters);
  if (subjectSelect) subjectSelect.addEventListener('change', applyFilters);
  if (sortSelect)    sortSelect.addEventListener('change',  applySort);
  if (clearBtn)      clearBtn.addEventListener('click',     clearAll);
}());
