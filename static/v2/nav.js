(function () {
  'use strict';

  var PAGE_LABELS = {
    workspace: 'Workspace · datasource & chats',
    shortcuts: 'Shortcuts · one-click workflows',
    tools: 'Tools · MCP + local catalog',
    docs: 'MCP Docs · how Studio works'
  };

  function isCompact() {
    return window.matchMedia('(max-width: 960px)').matches;
  }

  function getShell() {
    return document.getElementById('appShell');
  }

  function openSide() {
    var shell = getShell();
    var backdrop = document.getElementById('sideBackdrop');
    if (shell) shell.classList.add('side-open');
    if (backdrop) backdrop.hidden = false;
  }

  function closeSide() {
    var shell = getShell();
    var backdrop = document.getElementById('sideBackdrop');
    if (shell) shell.classList.remove('side-open');
    if (backdrop) backdrop.hidden = true;
  }

  function setPage(page, opts) {
    opts = opts || {};
    var pages = document.querySelectorAll('.side-page');
    pages.forEach(function (el) {
      var on = el.getAttribute('data-page') === page;
      el.hidden = !on;
      el.classList.toggle('active', on);
    });
    document.querySelectorAll('.rail-btn[data-page]').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-page') === page);
    });
    var label = document.getElementById('pageContextLabel');
    if (label) label.textContent = PAGE_LABELS[page] || page;
    try {
      localStorage.setItem('tableau-studio-v2-page', page);
    } catch (_) {}
    if (page === 'docs') renderDocsTools();
    if (opts.openDrawer !== false && isCompact()) openSide();
    if (!isCompact()) closeSide();
  }

  function renderDocsTools() {
    var host = document.getElementById('docsToolsCatalog');
    var countEl = document.getElementById('docsToolsCount');
    if (!host) return;
    var tools = (typeof loadedTools !== 'undefined' && Array.isArray(loadedTools)) ? loadedTools : [];
    if (countEl) countEl.textContent = String(tools.length);
    while (host.firstChild) host.removeChild(host.firstChild);
    if (!tools.length) {
      var empty = document.createElement('p');
      empty.className = 'docs-muted';
      empty.textContent = 'Tools not loaded yet — open the Tools page once, or wait for /tools.';
      host.appendChild(empty);
      return;
    }
    tools.slice().sort(function (a, b) {
      return String(a.name || '').localeCompare(String(b.name || ''));
    }).forEach(function (tool) {
      var row = document.createElement('div');
      row.className = 'docs-tool-row';
      var name = document.createElement('div');
      name.className = 'docs-tool-name';
      name.textContent = tool.name || '(unnamed)';
      var meta = document.createElement('div');
      meta.className = 'docs-tool-meta';
      meta.textContent = (tool.source || 'mcp') + (tool.description ? ' · ' + tool.description : '');
      row.appendChild(name);
      row.appendChild(meta);
      host.appendChild(row);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.rail-btn[data-page]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        setPage(btn.getAttribute('data-page'));
      });
    });
    var backdrop = document.getElementById('sideBackdrop');
    if (backdrop) {
      backdrop.addEventListener('click', closeSide);
    }
    window.addEventListener('resize', function () {
      if (!isCompact()) closeSide();
    });
    var saved = 'workspace';
    try {
      saved = localStorage.getItem('tableau-studio-v2-page') || 'workspace';
    } catch (_) {}
    setPage(saved, { openDrawer: false });
    setTimeout(renderDocsTools, 1200);
    setTimeout(renderDocsTools, 3000);
  });
})();
