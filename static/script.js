const PALETTE = ['#4f6ef7','#8b5cf6','#10b981','#f59e0b','#ef4444','#0ea5e9','#a855f7','#14b8a6'];
let chartCounter = 0;
const CHAT_STORAGE_KEY = 'tableau-chat-history-v1';
let appState = { conversations: [], currentId: null, lastDatasource: null };
let loadedTools = [];
/** Published datasources from GET /datasources */
let siteDatasources = [];
let dsPickerOpen = false;
let dsLoadState = 'idle'; // idle | loading | ready | error
let dsLoadError = '';
/** conversationId -> true while a /chat request is in flight for that session */
const inFlightByConversation = new Map();
/** conversationId -> [{ id, prompt, steps, createdAt }] Progress groups per turn */
const progressRunsByConversation = new Map();
/** @deprecated kept for any callers; prefer progressRunsByConversation */
let latestTraceSteps = [];

// {{DS_NAME}} / {{DS_LUID}} filled from the Active Datasource at click time — never hardcode a DS.
const WORKFLOW_SHORTCUTS = [
  {
    id: 'analyze',
    label: 'Analyze',
    purpose: 'query-datasource / local_query_chart / local_business_insight on the selected DS',
    icon: '✦',
    needsDatasource: true,
    items: [
      {
        label: 'Metadata',
        prompt:
          'Call get-datasource-metadata for Active Datasource "{{DS_NAME}}" (datasourceLuid={{DS_LUID}}). ' +
          'Summarize the main dimensions and measures in plain English.',
      },
      {
        label: 'Monthly trend chart',
        prompt:
          'For Active Datasource "{{DS_NAME}}" (datasourceLuid={{DS_LUID}}): call local_query_chart with chart_type=line ' +
          'for a monthly trend of the primary measure. Include the ```chart block in your answer.',
      },
      {
        label: 'Top members bar',
        prompt:
          'For Active Datasource "{{DS_NAME}}" (datasourceLuid={{DS_LUID}}): call local_query_chart with chart_type=bar ' +
          'for the top 10 members of the best category dimension by the primary measure. Include the ```chart block.',
      },
      {
        label: 'Business insight',
        prompt:
          'Call local_business_insight for Active Datasource "{{DS_NAME}}" (datasourceLuid={{DS_LUID}}). ' +
          'Answer: what stands out in the primary measure (highest period, weak spots)? Keep it short and factual.',
      },
    ],
  },
  {
    id: 'discover',
    label: 'Discover',
    purpose: 'list-datasources / list-workbooks / list-views / search-content',
    icon: '🔎',
    needsDatasource: false,
    items: [
      {
        label: 'List datasources',
        prompt:
          'Call list-datasources and summarize the top results (name, project, id). ' +
          'If an Active Datasource is selected ("{{DS_NAME}}" / {{DS_LUID}}), confirm it appears in the list.',
      },
      {
        label: 'List workbooks',
        prompt:
          'Call list-workbooks and summarize notable workbooks with name, project, and updated time. Keep it concise.',
      },
      {
        label: 'List views',
        prompt:
          'Call list-views and summarize notable views with their workbook context. Keep it concise.',
      },
      {
        label: 'Search content',
        prompt:
          'Call search-content for recent or popular site content and give a short ranked summary.',
      },
    ],
  },
  {
    id: 'workbook',
    label: 'Workbooks',
    purpose: 'list-projects / publish-workbook / get-view-data examples',
    icon: '📘',
    needsDatasource: false,
    items: [
      {
        label: 'List projects',
        prompt: 'Call list-projects and summarize project names and ids I can publish into.',
      },
      {
        label: 'View data sample',
        prompt:
          'Call list-views, pick one accessible view, then call get-view-data for a small sample. Summarize columns and a few rows.',
      },
      {
        label: 'View image',
        prompt:
          'Call list-views, pick one accessible view, then call get-view-image and describe what the viz shows.',
      },
    ],
  },
  {
    id: 'pulse',
    label: 'Pulse',
    purpose: 'Pulse metric definition / subscription tools',
    icon: '📈',
    needsDatasource: false,
    items: [
      {
        label: 'Metric definitions',
        prompt: 'Call the Pulse metric-definition listing tool and summarize available Pulse metrics briefly.',
      },
      {
        label: 'Subscriptions',
        prompt: 'Call the Pulse subscription listing tool and summarize my Pulse subscriptions briefly.',
      },
    ],
  },
  {
    id: 'dataapps',
    label: 'Data Apps',
    purpose: 'local_generate_data_app → preview → publish-workbook for the selected DS',
    icon: '🧩',
    needsDatasource: true,
    items: [
      {
        label: 'Generate data app',
        prompt:
          'Follow design-data-app then build-data-app. ' +
          'For Active Datasource "{{DS_NAME}}" (datasourceLuid={{DS_LUID}}): ' +
          '1) Optionally call get-datasource-metadata. ' +
          '2) Decide BLUF takeaway + role (strategic/operational/analytical) + encodings. ' +
          '3) Call local_generate_data_app (NOT rebuild/scaffold alone) with that English brief. ' +
          'Return the new previewUrl (?v=) and the takeaway sentence. Do NOT publish.',
      },
      {
        label: 'Generate red theme app',
        prompt:
          'Follow design-data-app then build-data-app. ' +
          'Active Datasource "{{DS_NAME}}" (datasourceLuid={{DS_LUID}}), theme="red". ' +
          'Design a BLUF takeaway for a strategic performance view, then call local_generate_data_app only. ' +
          'Return the new previewUrl. Do NOT publish.',
      },
      {
        label: 'Publish generated app',
        prompt:
          'PUBLISH ONLY — do NOT call local_generate_data_app. ' +
          'Call local_resolve_publish_workbook for datasource_luid={{DS_LUID}} (or the latest app from this chat). ' +
          'Then call list-projects and list every project (name + projectId). ' +
          'Ask which project I want. Put each project in a followup chip like: ' +
          'Publish to <ProjectName> (projectId=<uuid>). ' +
          'Do NOT call publish-workbook until I choose a project. Never assume Samples.',
      },
    ],
  },
  {
    id: 'admin',
    label: 'Admin',
    purpose: 'list-users / list-jobs / extract tasks (admin role may be required)',
    icon: '🛡',
    needsDatasource: false,
    items: [
      {
        label: 'List users',
        prompt:
          'Call list-users and summarize site users with site role and email when available. ' +
          'If permission is denied, say so clearly.',
      },
      {
        label: 'List jobs',
        prompt:
          'Call list-jobs and summarize recent background jobs (status, type, timing). ' +
          'If permission is denied, state the admin role requirement.',
      },
      {
        label: 'Extract tasks',
        prompt:
          'Call list-extract-refresh-tasks and summarize scheduled extract refreshes. ' +
          'If permission is denied, say so clearly.',
      },
    ],
  },
];

const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

function getActiveDatasource() {
  const convo = getCurrentConversation();
  if (convo && convo.datasource && convo.datasource.luid) return convo.datasource;
  if (appState.lastDatasource && appState.lastDatasource.luid) return appState.lastDatasource;
  for (let i = 0; i < appState.conversations.length; i++) {
    const ds = appState.conversations[i].datasource;
    if (ds && ds.luid) return ds;
  }
  return null;
}

function setActiveDatasource(ds, conversationId) {
  if (!ds || !ds.luid) return;
  const clean = {
    luid: String(ds.luid).trim(),
    name: (ds.name || 'Selected datasource').trim(),
  };
  const convo = appState.conversations.find(c => c.id === (conversationId || appState.currentId));
  if (convo) convo.datasource = clean;
  appState.lastDatasource = clean;
  saveConversationState();
  renderActiveDatasource();
  renderHistoryList();
}

function clearActiveDatasource() {
  const convo = getCurrentConversation();
  if (convo) delete convo.datasource;
  appState.lastDatasource = null;
  saveConversationState();
  renderActiveDatasource();
  renderHistoryList();
}

function extractDatasourceHint(text) {
  if (!text) return null;
  const uuid = UUID_RE.source;
  const explicit =
    text.match(new RegExp('datasource[_ ]?luid\\s*[=:]\\s*["\'`]?(' + uuid + ')["\'`]?', 'i')) ||
    text.match(new RegExp('(?:luid|id)\\s*[=:]\\s*["\'`]?(' + uuid + ')["\'`]?', 'i'));
  let luid = explicit ? explicit[1] : null;
  if (!luid) {
    const all = text.match(new RegExp(uuid, 'gi')) || [];
    if (all.length === 1) luid = all[0];
  }
  if (!luid) return null;

  let name = null;
  const namePatterns = [
    /Active Datasource:\s*([^|\]]+?)(?:\s*\||\s*])/i,
    /datasource(?:\s+name)?\s*[:=]\s*["']([^"']+)["']/i,
    /(?:using|selected|wired(?:\s+to)?|against|from)\s+(?:the\s+)?["']?([A-Za-z0-9][^"'\n,]{0,80}?)["']?\s+datasource/i,
    /["']([A-Za-z0-9][^"']{0,80})["']\s*\(\s*datasourceLuid/i,
  ];
  for (let i = 0; i < namePatterns.length; i++) {
    const m = text.match(namePatterns[i]);
    if (m && m[1]) {
      name = m[1].trim();
      break;
    }
  }
  return { luid, name: name || 'Selected datasource' };
}

function maybeCaptureDatasource(text, conversationId) {
  const hint = extractDatasourceHint(text);
  if (!hint) return;
  // Ignore generic scaffolding chatter without an explicit select/use/active cue
  // unless the text also names datasourceLuid.
  const intentional = /datasource[_ ]?luid|active datasource|use(?:ing)?\s+datasource|selected datasource|wired/i.test(text);
  if (!intentional && !/datasource[_ ]?luid/i.test(text)) return;
  setActiveDatasource(hint, conversationId);
}

function resolveShortcutPrompt(template, needsDatasource) {
  const ds = getActiveDatasource();
  if (needsDatasource && (!ds || !ds.luid)) {
    return (
      'No datasource selected. Pick one in the left Datasource picker first. ' +
      'Do not call tools yet and do not assume any default datasource.'
    );
  }
  const safeName = ds && ds.name ? String(ds.name).replace(/"/g, '') : 'Selected datasource';
  const luid = ds && ds.luid ? String(ds.luid) : '';
  return String(template || '')
    .replace(/\{\{DS_LUID\}\}/g, luid || '(no datasource selected)')
    .replace(/\{\{DS_NAME\}\}/g, luid ? safeName : '(no datasource selected)');
}

function filterSiteDatasources(query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return siteDatasources.slice(0, 80);
  return siteDatasources.filter(function (ds) {
    const hay = [ds.name, ds.projectName, ds.id, ds.contentUrl].join(' ').toLowerCase();
    return hay.indexOf(q) !== -1;
  }).slice(0, 80);
}

function closeDsDropdown() {
  dsPickerOpen = false;
  const drop = document.getElementById('dsDropdown');
  if (drop) drop.hidden = true;
}

function openDsDropdown() {
  dsPickerOpen = true;
  renderDsDropdown();
}

function renderDsDropdown() {
  const drop = document.getElementById('dsDropdown');
  const search = document.getElementById('dsSearch');
  if (!drop) return;
  drop.hidden = !dsPickerOpen;
  while (drop.firstChild) drop.removeChild(drop.firstChild);

  if (dsLoadState === 'loading') {
    const status = document.createElement('div');
    status.className = 'ds-dropdown-status';
    status.textContent = 'Loading datasources…';
    drop.appendChild(status);
    return;
  }
  if (dsLoadState === 'error') {
    const status = document.createElement('div');
    status.className = 'ds-dropdown-status';
    status.textContent = dsLoadError || 'Could not load datasources';
    drop.appendChild(status);
    return;
  }

  const matches = filterSiteDatasources(search ? search.value : '');
  if (!matches.length) {
    const empty = document.createElement('div');
    empty.className = 'ds-dropdown-empty';
    empty.textContent = siteDatasources.length ? 'No matches' : 'No datasources on this site';
    drop.appendChild(empty);
    return;
  }

  const active = getActiveDatasource();
  matches.forEach(function (ds) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ds-option' + (active && active.luid === ds.id ? ' active' : '');
    const name = document.createElement('span');
    name.className = 'ds-option-name';
    name.textContent = ds.name;
    const meta = document.createElement('span');
    meta.className = 'ds-option-meta';
    meta.textContent = (ds.projectName ? ds.projectName + ' · ' : '') + ds.id;
    btn.appendChild(name);
    btn.appendChild(meta);
    btn.onclick = function () {
      setActiveDatasource({ luid: ds.id, name: ds.name, projectName: ds.projectName || '' });
      if (search) search.value = ds.name;
      closeDsDropdown();
      updateUiForDatasourceGate();
    };
    drop.appendChild(btn);
  });
}

function renderActiveDatasource() {
  const el = document.getElementById('dsSelected');
  const search = document.getElementById('dsSearch');
  if (!el) return;
  const ds = getActiveDatasource();
  while (el.firstChild) el.removeChild(el.firstChild);
  if (!ds) {
    el.className = 'ds-selected';
    el.textContent = 'No datasource selected — pick one above to unlock chat & tools.';
    return;
  }
  el.className = 'ds-selected ready';
  const name = document.createElement('span');
  name.className = 'ds-selected-name';
  name.textContent = ds.name || ds.luid;
  const luid = document.createElement('span');
  luid.className = 'ds-selected-luid';
  luid.textContent = ds.luid;
  const actions = document.createElement('div');
  actions.className = 'ds-selected-actions';
  const clear = document.createElement('button');
  clear.className = 'ds-clear';
  clear.type = 'button';
  clear.textContent = 'Clear';
  clear.onclick = function () {
    clearActiveDatasource();
    if (search) search.value = '';
    updateUiForDatasourceGate();
  };
  actions.appendChild(clear);
  el.appendChild(name);
  el.appendChild(luid);
  el.appendChild(actions);
  if (search && document.activeElement !== search && !dsPickerOpen) {
    search.value = ds.name || '';
  }
}

async function loadDatasources(force) {
  if (dsLoadState === 'loading' && !force) return;
  dsLoadState = 'loading';
  dsLoadError = '';
  const refresh = document.getElementById('dsRefreshBtn');
  if (refresh) refresh.disabled = true;
  if (dsPickerOpen) renderDsDropdown();
  try {
    const res = await fetch('/datasources?t=' + Date.now(), { cache: 'no-store' });
    if (!res.ok) {
      let detail = 'HTTP ' + res.status;
      try {
        const err = await res.json();
        if (err && err.detail) detail = String(err.detail);
      } catch (_) {}
      throw new Error(detail);
    }
    const data = await res.json();
    siteDatasources = Array.isArray(data.datasources) ? data.datasources : [];
    dsLoadState = 'ready';
    // If a previously selected LUID still exists, keep it; else keep selection as-is.
    const active = getActiveDatasource();
    if (active && active.luid) {
      const hit = siteDatasources.find(function (d) { return d.id === active.luid; });
      if (hit) setActiveDatasource({ luid: hit.id, name: hit.name, projectName: hit.projectName || '' });
    }
  } catch (err) {
    siteDatasources = [];
    dsLoadState = 'error';
    dsLoadError = (err && err.message) ? err.message : 'Failed to load datasources';
  } finally {
    if (refresh) refresh.disabled = false;
    renderActiveDatasource();
    if (dsPickerOpen) renderDsDropdown();
    updateUiForDatasourceGate();
  }
}

function updateUiForDatasourceGate() {
  const hasDs = !!(getActiveDatasource() && getActiveDatasource().luid);
  const input = document.getElementById('messageInput');
  if (input) {
    input.placeholder = hasDs
      ? 'Ask about the active datasource, list workbooks, scaffold a data app, publish…'
      : 'Select a datasource on the left first…';
    input.disabled = !hasDs;
  }
  updateSendButtonState();
  renderSidebarShortcuts();
  renderShortcutBar();
  const welcome = document.getElementById('welcomeScreen');
  if (welcome) {
    const h2 = welcome.querySelector('h2');
    const p = welcome.querySelector('p');
    if (h2) h2.textContent = hasDs ? 'Ask, analyze, or publish' : 'Start with a datasource';
    if (p) {
      p.textContent = hasDs
        ? 'Shortcuts and MCP tools will use the selected datasource.'
        : 'Use the left Datasource search to pick a published datasource. Everything else unlocks after that.';
    }
  }
  renderWelcomeShortcuts();
}

const TOOL_GROUPS = [
  {
    id: 'local',
    label: 'Local data apps',
    purpose: 'Scaffold, preview, package',
    match: (name) => String(name).indexOf('local_') === 0,
  },
  {
    id: 'datasource',
    label: 'Datasource',
    purpose: 'List, metadata, query',
    match: (name) => /datasource|query-datasource|get-datasource/i.test(name),
  },
  {
    id: 'workbook',
    label: 'Workbook & views',
    purpose: 'Browse and publish content',
    match: (name) => /workbook|view|publish|download-workbook|move-workbook|search-content|list-projects/i.test(name),
  },
  {
    id: 'pulse',
    label: 'Pulse',
    purpose: 'Metrics and insights',
    match: (name) => /pulse|insight/i.test(name),
  },
  {
    id: 'flow',
    label: 'Flows',
    purpose: 'Prep flows and runs',
    match: (name) => /flow/i.test(name),
  },
  {
    id: 'admin',
    label: 'Admin',
    purpose: 'Users, jobs, extract tasks',
    match: (name) => /user|job|extract|admin|stale|license|permission|token/i.test(name),
  },
  {
    id: 'other',
    label: 'Other',
    purpose: 'Everything else',
    match: () => true,
  },
];

function classifyTool(tool) {
  const name = tool.name || '';
  for (let i = 0; i < TOOL_GROUPS.length; i++) {
    if (TOOL_GROUPS[i].match(name)) return TOOL_GROUPS[i];
  }
  return TOOL_GROUPS[TOOL_GROUPS.length - 1];
}

// ── Lightweight markdown ──────────────────────────────────────────────────────
function linkifyHtml(t) {
  // Markdown links: [label](https://...)
  t = t.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  // Bare http(s) URLs (skip ones already inside href="...")
  t = t.replace(/(^|[^"'>=])(https?:\/\/[^\s<]+)/g, function (_, pre, url) {
    let trailing = '';
    const clean = url.replace(/[),.;:!?\]]+$/g, function (m) {
      trailing = m;
      return '';
    });
    if (!clean) return pre + url;
    return (
      pre +
      '<a href="' + clean + '" target="_blank" rel="noopener noreferrer">' + clean + '</a>' +
      trailing
    );
  });
  return t;
}

function renderMarkdown(raw) {
  let t = raw.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  // Protect inline code so URLs inside backticks stay plain text
  const codeChunks = [];
  t = t.replace(/`([^`\n]+)`/g, function (_, code) {
    codeChunks.push('<code>' + code + '</code>');
    return '\u0000CODE' + (codeChunks.length - 1) + '\u0000';
  });
  t = t
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^#{1,3} (.+)$/gm, '<strong>$1</strong>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  t = t.replace(/(<li>[^\n]*\n?)+/g, s => `<ul>${s}</ul>`);
  t = linkifyHtml(t);
  t = t.replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>');
  t = t.replace(/\u0000CODE(\d+)\u0000/g, function (_, i) {
    return codeChunks[Number(i)] || '';
  });
  return t;
}

// ── Extract ONE fenced block by tag, return {content, remaining} or null ──────
function extractBlock(text, tag) {
  const openRe = new RegExp('```' + tag + '[^\\n]*\\n', 'gi');
  let m;
  while ((m = openRe.exec(text)) !== null) {
    const start = m.index + m[0].length;
    const after = text.slice(start);
    const closeM = /```|\.\.\./.exec(after);
    const content = (closeM ? after.slice(0, closeM.index) : after).trim();
    if (!content) continue;
    const fullEnd = start + (closeM ? closeM.index + closeM[0].length : after.length);
    const remaining = (text.slice(0, m.index) + text.slice(fullEnd)).trim();
    return { content, remaining };
  }
  return null;
}

// ── Extract ALL chart blocks from text ───────────────────────────────────────
// Returns { charts: [{option}], remaining: string }
function extractAllCharts(text) {
  const charts = [];
  let remaining = text;
  for (const tag of ['chart', 'echarts']) {
    let block;
    // Keep pulling blocks of this tag until none left
    while ((block = extractBlock(remaining, tag)) !== null) {
      if (!block.content.startsWith('{')) { remaining = block.remaining; continue; }
      try {
        charts.push(JSON.parse(block.content));
        remaining = block.remaining;
      } catch (e) {
        console.warn('Chart JSON parse failed:', e.message, '\n', block.content.slice(0, 300));
        remaining = block.remaining;
      }
    }
  }
  return { charts, remaining };
}

// ── Extract followup block ────────────────────────────────────────────────────
function extractFollowups(text) {
  const block = extractBlock(text, 'followup');
  if (!block) return null;
  try {
    const items = JSON.parse(block.content);
    if (!Array.isArray(items) || items.length === 0) return null;
    const suggestions = items.map(item =>
      typeof item === 'string'
        ? { label: item, prompt: item }
        : { label: item.label || item.prompt, prompt: item.prompt || item.label }
    );
    return { suggestions, remaining: block.remaining };
  } catch (e) {
    console.warn('Followup JSON parse failed:', e.message, '\n', block.content.slice(0, 300));
    return null;
  }
}

// ── ECharts render ────────────────────────────────────────────────────────────
function renderChart(option, container) {
  const chart = echarts.init(container, null, { renderer: 'canvas' });
  function styledAxis(axis) {
    const base = Array.isArray(axis) ? axis[0] : axis;
    return {
      ...base,
      axisLine:  { lineStyle: { color: '#d8dced' } },
      axisLabel: { color: '#717aaa', fontSize: 12 },
      splitLine: { lineStyle: { color: '#eaecf7' } }
    };
  }
  chart.setOption({
    backgroundColor: 'transparent',
    color: PALETTE,
    grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true },
    tooltip: {
      trigger: option.series?.[0]?.type === 'pie' ? 'item' : 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#d8dced',
      textStyle: { color: '#1a1e3c', fontSize: 13 }
    },
    legend: { textStyle: { color: '#717aaa' }, top: 'bottom' },
    ...option,
    xAxis: option.xAxis ? styledAxis(option.xAxis) : undefined,
    yAxis: option.yAxis ? styledAxis(option.yAxis) : undefined,
  });
  window.addEventListener('resize', () => chart.resize());
}

function buildChartCard(option) {
  const card = document.createElement('div');
  card.className = 'chart-card';
  const titleEl = document.createElement('div');
  titleEl.className = 'chart-title';
  titleEl.textContent = (option.title && (option.title.text || option.title)) || 'Chart';
  const container = document.createElement('div');
  container.className = 'chart-container';
  container.id = `chart-${++chartCounter}`;
  card.appendChild(titleEl);
  card.appendChild(container);
  requestAnimationFrame(() =>
    requestAnimationFrame(() => renderChart(option, container))
  );
  return card;
}

// ── Follow-up chip row ────────────────────────────────────────────────────────
function buildFollowupRow(suggestions) {
  const row = document.createElement('div');
  row.className = 'followup-row';
  const lbl = document.createElement('div');
  lbl.className = 'followup-label';
  lbl.textContent = '↳ Explore further';
  row.appendChild(lbl);
  const chips = document.createElement('div');
  chips.className = 'followup-chips';
  suggestions.forEach(({ label: btnLabel, prompt }) => {
    const btn = document.createElement('button');
    btn.className = 'chip followup-chip';
    btn.textContent = btnLabel;
    btn.title = prompt;
    btn.onclick = () => sendPrompt(prompt);
    chips.appendChild(btn);
  });
  row.appendChild(chips);
  return row;
}

// ── Add message ───────────────────────────────────────────────────────────────
function addMessage(text, role, isThinking, options = {}) {
  const { persist = true, conversationId = appState.currentId } = options;
  const isActiveView = conversationId === appState.currentId;

  if (persist && !isThinking) {
    persistMessage(role, text, conversationId);
  }

  // If the user switched chats, keep storage pinned to the origin session
  // and skip painting into the wrong transcript.
  if (!isActiveView) {
    return null;
  }

  const welcome = document.getElementById('welcomeScreen');
  if (welcome) welcome.remove();

  const chatBox = document.getElementById('chatBox');
  if (!chatBox) return null;

  const msg = document.createElement('div');
  msg.className = `msg ${role}${isThinking ? ' thinking' : ''}`;
  if (conversationId) msg.dataset.conversationId = conversationId;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'user' ? 'U' : '✦';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (isThinking) {
    bubble.innerHTML = `Thinking <span class="dots"><span></span><span></span><span></span></span>`;
  } else if (role === 'bot') {
    // 1. Strip followup block
    const followupResult = extractFollowups(text);
    const afterFollowup = followupResult ? followupResult.remaining : text;

    // 2. Strip all chart blocks
    const { charts, remaining: displayText } = extractAllCharts(afterFollowup);

    // 3. Render text
    bubble.innerHTML = `<p>${renderMarkdown(displayText)}</p>`;

    // 4. Append chart cards inside bubble
    charts.forEach(option => bubble.appendChild(buildChartCard(option)));

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chatBox.appendChild(msg);

    // 5. Follow-up row outside bubble
    if (followupResult && followupResult.suggestions.length > 0) {
      chatBox.appendChild(buildFollowupRow(followupResult.suggestions));
    }

    chatBox.scrollTop = chatBox.scrollHeight;
    return msg;
  } else {
    bubble.textContent = text;
  }

  msg.appendChild(avatar);
  msg.appendChild(bubble);
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
  return msg;
}

function updateSendButtonState() {
  const btn = document.getElementById('sendBtn');
  if (!btn) return;
  const busy = !!(appState.currentId && inFlightByConversation.has(appState.currentId));
  const hasDs = !!(getActiveDatasource() && getActiveDatasource().luid);
  btn.disabled = busy || !hasDs;
}

function clearThinkingForConversation(conversationId) {
  if (appState.currentId !== conversationId) return;
  document.querySelectorAll('.msg.thinking').forEach((node) => {
    if (!node.dataset.conversationId || node.dataset.conversationId === conversationId) {
      node.remove();
    }
  });
}

// ── Send ──────────────────────────────────────────────────────────────────────
async function sendMessage() {
  const input = document.getElementById('messageInput');
  const text  = input.value.trim();
  if (!text) return;

  // Pin the response to the chat that asked — even if user opens a new chat mid-flight.
  const conversationId = appState.currentId;
  if (!conversationId) return;
  if (inFlightByConversation.has(conversationId)) return;

  const activeDs = getActiveDatasource();
  if (!activeDs || !activeDs.luid) {
    addMessage(
      'Select a datasource in the left picker first. Chat and tools stay locked until then.',
      'bot',
      false,
      { conversationId, persist: false }
    );
    openDsDropdown();
    const search = document.getElementById('dsSearch');
    if (search) search.focus();
    return;
  }

  input.value = '';
  input.style.height = 'auto';
  addMessage(text, 'user', false, { conversationId });

  inFlightByConversation.set(conversationId, true);
  updateSendButtonState();
  renderHistoryList();
  addMessage('', 'bot', true, { conversationId, persist: false });

  try {
    const convo = appState.conversations.find(c => c.id === conversationId);
    const ds = (convo && convo.datasource) || appState.lastDatasource || null;
    const res  = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        datasource_luid: ds && ds.luid ? ds.luid : null,
        datasource_name: ds && ds.name ? ds.name : null,
      })
    });
    const data = await res.json();
    clearThinkingForConversation(conversationId);
    addMessage(data.response || 'No response received.', 'bot', false, { conversationId });
    appendProgressRun(conversationId, text, Array.isArray(data.steps) ? data.steps : []);
  } catch (_) {
    clearThinkingForConversation(conversationId);
    addMessage('Connection error — is the server running?', 'bot', false, { conversationId });
  } finally {
    inFlightByConversation.delete(conversationId);
    updateSendButtonState();
    renderHistoryList();
    renderActiveDatasource();
    if (appState.currentId === conversationId) input.focus();
  }
}

function useChip(el) {
  const prompt = el.dataset.prompt || el.textContent;
  document.getElementById('messageInput').value = prompt;
  sendMessage();
}

function sendPrompt(prompt) {
  document.getElementById('messageInput').value = prompt;
  sendMessage();
}

function draftToolPrompt(tool) {
  const name = tool.name || '';
  const desc = (tool.description || '').replace(/\s+/g, ' ').trim();
  const shortDesc = desc.length > 180 ? desc.slice(0, 177) + '…' : desc;
  const ds = getActiveDatasource();
  const hasDs = !!(ds && ds.luid);
  const dsLabel = hasDs
    ? '"' + String(ds.name || 'Selected datasource').replace(/"/g, '') + '" (datasourceLuid=' + ds.luid + ')'
    : null;
  const dsScoped =
    /datasource|query-datasource|get-datasource|local_query|local_business|local_generate|local_rebuild|local_seed|local_bind|local_resolve_publish/i.test(
      name
    );

  if (dsScoped && !hasDs) {
    return (
      'No datasource selected. Pick one in the left Datasource picker, then run `' + name + '`.'
    );
  }

  // Tool-family example prompts (English) — always bind to Active Datasource when relevant.
  if (name === 'query-datasource' && hasDs) {
    return (
      'Call query-datasource for Active Datasource ' + dsLabel + '. ' +
      'Return a small aggregated sample of the primary measure by a useful dimension. Summarize in plain English.'
    );
  }
  if (name === 'get-datasource-metadata' && hasDs) {
    return (
      'Call get-datasource-metadata for Active Datasource ' + dsLabel + '. ' +
      'List the main dimensions and measures briefly.'
    );
  }
  if (name === 'list-datasources') {
    return (
      'Call list-datasources and summarize name, project, and id for the top results.' +
      (hasDs ? ' Confirm Active Datasource ' + dsLabel + ' is present.' : '')
    );
  }
  if (name === 'list-workbooks') {
    return 'Call list-workbooks and summarize notable workbooks (name, project, updated).';
  }
  if (name === 'list-views') {
    return 'Call list-views and summarize notable views with their workbook context.';
  }
  if (name === 'list-projects') {
    return 'Call list-projects and summarize project names and ids available for publish.';
  }
  if (name === 'list-users') {
    return 'Call list-users and summarize users with site role and email when available. If denied, say so.';
  }
  if (name === 'list-jobs') {
    return 'Call list-jobs and summarize recent jobs (status, type, timing). If denied, say so.';
  }
  if (name === 'list-extract-refresh-tasks') {
    return 'Call list-extract-refresh-tasks and summarize scheduled extract refreshes. If denied, say so.';
  }
  if (name === 'search-content') {
    return 'Call search-content for popular or recent site content and give a short ranked summary.';
  }
  if (name === 'publish-workbook' && hasDs) {
    return (
      'PUBLISH ONLY for Active Datasource ' + dsLabel + '. ' +
      'Call local_resolve_publish_workbook, then list-projects. ' +
      'Ask which project to use and offer followup chips like Publish to <Name> (projectId=<uuid>). ' +
      'Do NOT publish until I choose a project. Never assume Samples.'
    );
  }
  if (name === 'local_generate_data_app' && hasDs) {
    return (
      'Call local_generate_data_app for datasource_luid=' + ds.luid + ' ("' +
      String(ds.name || '').replace(/"/g, '') +
      '"). Invent new src/app.js + styles.css. Return the new previewUrl. Do NOT publish.'
    );
  }
  if (name === 'local_query_chart' && hasDs) {
    return (
      'Call local_query_chart for Active Datasource ' + dsLabel +
      ' with chart_type=auto. Include the ```chart block in your answer.'
    );
  }
  if (name === 'local_business_insight' && hasDs) {
    return (
      'Call local_business_insight for Active Datasource ' + dsLabel +
      '. Give a short factual takeaway on the primary measure.'
    );
  }
  if (name === 'local_resolve_publish_workbook' && hasDs) {
    return (
      'Call local_resolve_publish_workbook for datasource_luid=' + ds.luid +
      ', then list-projects and ask which project to publish into. Do NOT generate a new app or publish yet.'
    );
  }

  if (name.indexOf('local_') === 0) {
    return (
      'Call `' + name + '` now.' +
      (hasDs ? ' Use Active Datasource ' + dsLabel + '.' : '') +
      (shortDesc ? ' ' + shortDesc : '')
    ).trim();
  }

  return (
    'Call the Tableau MCP tool `' + name + '` now.' +
    (hasDs && dsScoped ? ' Use Active Datasource ' + dsLabel + '.' : '') +
    (shortDesc ? ' ' + shortDesc : '') +
    ' Summarize the result in plain English.'
  ).trim();
}

function renderSidebarShortcuts() {
  const host = document.getElementById('sidebarShortcuts');
  if (!host) return;
  while (host.firstChild) host.removeChild(host.firstChild);

  WORKFLOW_SHORTCUTS.forEach(function (group) {
    const details = document.createElement('details');
    details.className = 'purpose-group';
    details.open = group.id === 'analyze' || group.id === 'dataapps';

    const summary = document.createElement('summary');
    summary.className = 'purpose-summary';
    const title = document.createElement('span');
    title.className = 'purpose-title';
    title.textContent = group.icon + ' ' + group.label;
    const purpose = document.createElement('span');
    purpose.className = 'purpose-desc';
    purpose.textContent = group.purpose || '';
    summary.appendChild(title);
    summary.appendChild(purpose);
    details.appendChild(summary);

    const items = document.createElement('div');
    items.className = 'purpose-items';
    group.items.forEach(function (item) {
      const btn = document.createElement('button');
      btn.className = 'sidebar-chip';
      btn.textContent = item.label;
      btn.title = resolveShortcutPrompt(item.prompt, group.needsDatasource);
      btn.onclick = function () {
        sendPrompt(resolveShortcutPrompt(item.prompt, group.needsDatasource));
      };
      items.appendChild(btn);
    });
    details.appendChild(items);
    host.appendChild(details);
  });
}

function renderShortcutBar() {
  const bar = document.getElementById('shortcutBar');
  if (!bar) return;
  while (bar.firstChild) bar.removeChild(bar.firstChild);
  // Compact bottom bar: one chip per purpose group (full list lives in the left sidebar).
  WORKFLOW_SHORTCUTS.forEach(function (group) {
    const item = group.items[0];
    if (!item) return;
    const resolved = resolveShortcutPrompt(item.prompt, group.needsDatasource);
    const btn = document.createElement('button');
    btn.className = (group.id === 'dataapps' || group.id === 'admin') ? 'chip tool' : 'chip';
    btn.textContent = group.icon + ' ' + group.label;
    btn.title = (group.purpose ? group.purpose + ' — ' : '') + resolved;
    btn.dataset.prompt = resolved;
    btn.onclick = function () {
      btn.dataset.prompt = resolveShortcutPrompt(item.prompt, group.needsDatasource);
      useChip(btn);
    };
    bar.appendChild(btn);
  });
}

function renderWelcomeShortcuts() {
  const host = document.getElementById('welcomeShortcuts');
  if (!host) return;
  while (host.firstChild) host.removeChild(host.firstChild);
  WORKFLOW_SHORTCUTS.forEach(function (group) {
    const item = group.items[0];
    if (!item) return;
    const btn = document.createElement('button');
    btn.className = 'welcome-chip';
    btn.textContent = group.label;
    btn.title = group.purpose || item.prompt;
    btn.onclick = function () {
      sendPrompt(resolveShortcutPrompt(item.prompt, group.needsDatasource));
    };
    host.appendChild(btn);
  });
}

function renderToolsList(filter) {
  const list = document.getElementById('toolsList');
  const count = document.getElementById('toolsCount');
  if (!list) return;
  const q = (filter || '').trim().toLowerCase();
  const tools = loadedTools.filter(function (t) {
    if (!q) return true;
    const group = classifyTool(t);
    return (
      String(t.name || '').toLowerCase().indexOf(q) !== -1 ||
      String(t.description || '').toLowerCase().indexOf(q) !== -1 ||
      String(t.source || '').toLowerCase().indexOf(q) !== -1 ||
      String(group.label || '').toLowerCase().indexOf(q) !== -1 ||
      String(group.purpose || '').toLowerCase().indexOf(q) !== -1
    );
  });
  if (count) count.textContent = String(tools.length);
  while (list.firstChild) list.removeChild(list.firstChild);
  if (!tools.length) {
    const empty = document.createElement('div');
    empty.className = 'tools-empty';
    empty.textContent = 'No tools match';
    list.appendChild(empty);
    return;
  }

  const buckets = {};
  TOOL_GROUPS.forEach(function (g) { buckets[g.id] = []; });
  tools.forEach(function (tool) {
    const group = classifyTool(tool);
    buckets[group.id].push(tool);
  });

  TOOL_GROUPS.forEach(function (group) {
    const items = buckets[group.id] || [];
    if (!items.length) return;

    const details = document.createElement('details');
    details.className = 'purpose-group tool-group';
    details.open = !!q || group.id === 'local' || group.id === 'datasource';

    const summary = document.createElement('summary');
    summary.className = 'purpose-summary';
    const title = document.createElement('span');
    title.className = 'purpose-title';
    title.textContent = group.label + ' (' + items.length + ')';
    const purpose = document.createElement('span');
    purpose.className = 'purpose-desc';
    purpose.textContent = group.purpose;
    summary.appendChild(title);
    summary.appendChild(purpose);
    details.appendChild(summary);

    const wrap = document.createElement('div');
    wrap.className = 'purpose-items';
    items.forEach(function (tool) {
      const btn = document.createElement('button');
      btn.className = 'tool-item ' + (tool.source === 'local' ? 'local' : 'mcp');
      btn.title = tool.description || tool.name;
      const nameEl = document.createElement('span');
      nameEl.className = 'tool-name';
      nameEl.textContent = tool.name;
      const srcEl = document.createElement('span');
      srcEl.className = 'tool-src';
      srcEl.textContent = tool.source || 'mcp';
      btn.appendChild(nameEl);
      btn.appendChild(srcEl);
      btn.onclick = function () {
        document.getElementById('messageInput').value = draftToolPrompt(tool);
        document.getElementById('messageInput').focus();
      };
      btn.ondblclick = function () { sendPrompt(draftToolPrompt(tool)); };
      wrap.appendChild(btn);
    });
    details.appendChild(wrap);
    list.appendChild(details);
  });
}

async function loadTools() {
  try {
    const res = await fetch('/tools?t=' + Date.now(), { cache: 'no-store' });
    if (!res.ok) throw new Error('tools fetch failed');
    const data = await res.json();
    loadedTools = Array.isArray(data.tools) ? data.tools : [];
    const search = document.getElementById('toolsSearch');
    renderToolsList(search ? search.value : '');
  } catch (_) {
    loadedTools = [];
    const count = document.getElementById('toolsCount');
    if (count) count.textContent = '0';
    const list = document.getElementById('toolsList');
    if (list) {
      while (list.firstChild) list.removeChild(list.firstChild);
      const empty = document.createElement('div');
      empty.className = 'tools-empty';
      empty.textContent = 'Could not load tools';
      list.appendChild(empty);
    }
  }
}

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function loadConversationState() {
  try {
    const saved = localStorage.getItem(CHAT_STORAGE_KEY);
    if (!saved) return;
    const parsed = JSON.parse(saved);
    if (Array.isArray(parsed.conversations)) {
      appState.conversations = parsed.conversations;
      appState.currentId = parsed.currentId || parsed.conversations[0]?.id || null;
    }
    if (parsed.lastDatasource && parsed.lastDatasource.luid) {
      appState.lastDatasource = parsed.lastDatasource;
    }
  } catch (_) {}
}

function saveConversationState() {
  localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(appState));
}

function getCurrentConversation() {
  return appState.conversations.find(c => c.id === appState.currentId) || null;
}

function createConversation() {
  const convo = {
    id: makeId(),
    title: 'New chat',
    updatedAt: Date.now(),
    messages: []
  };
  if (appState.lastDatasource && appState.lastDatasource.luid) {
    convo.datasource = {
      luid: appState.lastDatasource.luid,
      name: appState.lastDatasource.name || 'Selected datasource',
    };
  }
  appState.conversations.unshift(convo);
  appState.currentId = convo.id;
  progressRunsByConversation.set(convo.id, []);
  saveConversationState();
  renderHistoryList();
  renderConversation();
  renderProgressPanel();
  renderActiveDatasource();
  updateUiForDatasourceGate();
}

function deleteConversation(conversationId) {
  const idx = appState.conversations.findIndex(c => c.id === conversationId);
  if (idx === -1) return;

  const wasCurrent = appState.currentId === conversationId;
  appState.conversations.splice(idx, 1);
  progressRunsByConversation.delete(conversationId);

  if (appState.conversations.length === 0) {
    createConversation();
    return;
  }

  if (wasCurrent) {
    appState.currentId = appState.conversations[0].id;
  }

  saveConversationState();
  renderHistoryList();
  renderConversation();
  renderProgressPanel();
}

function persistMessage(role, text, conversationId = appState.currentId) {
  const convo = appState.conversations.find(c => c.id === conversationId);
  if (!convo) return;
  convo.messages.push({ role, text });
  convo.updatedAt = Date.now();
  if (convo.title === 'New chat' && role === 'user') {
    convo.title = text.slice(0, 34) || 'New chat';
  }
  maybeCaptureDatasource(text, conversationId);
  appState.conversations.sort((a, b) => b.updatedAt - a.updatedAt);
  saveConversationState();
  renderHistoryList();
  renderActiveDatasource();
}

function renderHistoryList() {
  const list = document.getElementById('historyList');
  if (!list) return;
  list.innerHTML = '';
  appState.conversations.forEach(convo => {
    const pending = inFlightByConversation.has(convo.id);
    const btn = document.createElement('button');
    btn.className = `history-item${convo.id === appState.currentId ? ' active' : ''}${pending ? ' pending' : ''}`;
    const txt = document.createElement('span');
    txt.className = 'history-item-text';
    txt.textContent = `${pending ? '… ' : ''}${convo.title || 'New chat'}`;

    const del = document.createElement('button');
    del.className = 'history-item-delete';
    del.textContent = 'x';
    del.title = 'Delete chat';
    del.onclick = (e) => {
      e.stopPropagation();
      deleteConversation(convo.id);
    };

    btn.appendChild(txt);
    btn.appendChild(del);
    btn.onclick = () => {
      appState.currentId = convo.id;
      saveConversationState();
      renderHistoryList();
      renderConversation();
      renderProgressPanel();
      renderActiveDatasource();
      updateUiForDatasourceGate();
    };
    list.appendChild(btn);
  });
}

function renderConversation() {
  const chatBox = document.getElementById('chatBox');
  if (!chatBox) return;
  chatBox.innerHTML = '';

  const convo = getCurrentConversation();
  if (!convo || convo.messages.length === 0) {
    chatBox.innerHTML = `
      <div class="welcome-screen" id="welcomeScreen">
        <div class="welcome-icon">📊</div>
        <h2>Start with a datasource</h2>
        <p>Use the left Datasource search to pick a published datasource. Everything else unlocks after that.</p>
        <div class="welcome-shortcuts" id="welcomeShortcuts"></div>
      </div>`;
    updateUiForDatasourceGate();
    if (convo && inFlightByConversation.has(convo.id)) {
      addMessage('', 'bot', true, { conversationId: convo.id, persist: false });
    }
    updateSendButtonState();
    return;
  }

  convo.messages.forEach(msg => addMessage(msg.text, msg.role, false, {
    persist: false,
    conversationId: convo.id,
  }));
  if (inFlightByConversation.has(convo.id)) {
    addMessage('', 'bot', true, { conversationId: convo.id, persist: false });
  }
  updateSendButtonState();
}

function applyStudioTheme(profile) {
  const theme = (profile && profile.theme) || 'blue';
  const isRed = theme === 'red';
  document.body.classList.toggle('theme-red', isRed);
  const themeLink = document.getElementById('themeOverride');
  if (themeLink) themeLink.disabled = !isRed;
  const title = document.getElementById('studioTitle');
  const status = document.getElementById('studioStatusTitle');
  const context = document.getElementById('pageContextLabel');
  const brand = document.querySelector('.rail-brand');
  if (isRed) {
    if (title) title.textContent = 'Bedrock Gateway';
    if (status) status.textContent = 'Gateway · Llama';
    if (context) context.textContent = 'Studio v2 · red Bedrock profile';
    if (brand) {
      brand.textContent = 'G';
      brand.title = 'Bedrock Gateway Studio';
    }
    document.title = 'Tableau AI · Bedrock Gateway';
  } else {
    if (title) title.textContent = 'Tableau AI Studio';
    if (status) status.textContent = 'Studio v2';
    if (context) context.textContent = 'Studio v2 · OpenAI profile';
    if (brand) {
      brand.textContent = 'T';
      brand.title = 'Tableau AI Studio';
    }
    document.title = 'Tableau AI · Studio';
  }
}

function studioUrlForProfile(profileId) {
  const id = String(profileId || '').trim();
  if (id && id !== 'openai') return '/?llm=' + encodeURIComponent(id);
  return '/';
}

async function activateLlmProfile(profileId, opts) {
  opts = opts || {};
  const id = String(profileId || '').trim();
  if (!id) return null;
  const res = await fetch('/llm-profiles/active', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: id }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to activate LLM profile');
  }
  if (data.profile) applyStudioTheme(data.profile);
  if (opts.reload) {
    // Always stay on Studio v2 — never classic UI.
    window.location.href = studioUrlForProfile(id);
    return data;
  }
  await loadMcpInfo();
  await loadLlmProfiles();
  return data;
}

async function loadLlmProfiles() {
  const select = document.getElementById('llmProfileSelect');
  if (!select) return null;
  try {
    const res = await fetch(`/llm-profiles?t=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('profiles fetch failed');
    const data = await res.json();
    const profiles = Array.isArray(data.profiles) ? data.profiles : [];
    const activeId = data.active_profile_id || '';
    const active = profiles.find(function (p) { return p.id === activeId; });
    if (active) applyStudioTheme(active);
    select.innerHTML = '';
    profiles.forEach(function (p) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.disabled = !p.enabled;
      opt.textContent = (p.label || p.id) + (p.enabled ? '' : ' (not configured)');
      if (p.id === activeId) opt.selected = true;
      select.appendChild(opt);
    });
    if (!select._bound) {
      select._bound = true;
      select.addEventListener('change', async function () {
        const next = select.value;
        select.disabled = true;
        try {
          await activateLlmProfile(next, { reload: true });
        } catch (err) {
          alert(err.message || String(err));
          select.disabled = false;
          await loadLlmProfiles();
        }
      });
    }
    return data;
  } catch (_) {
    select.innerHTML = '<option value="">Could not load</option>';
    return null;
  }
}

async function ensurePreferredLlmProfile() {
  const params = new URLSearchParams(window.location.search || '');
  const fromUrl = (params.get('llm') || '').trim();
  const preferred = fromUrl || (document.body && document.body.dataset.preferredLlmProfile) || '';
  if (!preferred) {
    // Sync theme to whatever is already active on the server.
    try {
      const res = await fetch(`/llm-profiles?t=${Date.now()}`, { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      const active = (data.profiles || []).find(function (p) { return p.id === data.active_profile_id; });
      if (active) applyStudioTheme(active);
    } catch (_) {}
    return;
  }
  try {
    const res = await fetch(`/llm-profiles?t=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    const match = (data.profiles || []).find(function (p) { return p.id === preferred; });
    if (!match || !match.enabled) return;
    if (data.active_profile_id === preferred) {
      applyStudioTheme(match);
      return;
    }
    await activateLlmProfile(preferred, { reload: false });
  } catch (_) {
    // Keep page usable even if profile switch fails.
  }
}

async function activateTableauSite(profileId) {
  const id = String(profileId || '').trim();
  if (!id) return null;
  const res = await fetch('/tableau-sites/active', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile_id: id }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail || 'Failed to switch Tableau site';
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  // Site LUIDs differ — clear Active Datasource and refresh picker.
  try { clearActiveDatasource(); } catch (_) {}
  await loadMcpInfo();
  await loadTableauSites();
  if (typeof loadDatasources === 'function') await loadDatasources(true);
  if (typeof loadTools === 'function') await loadTools();
  return data;
}

async function loadTableauSites() {
  const select = document.getElementById('tableauSiteSelect');
  if (!select) return null;
  try {
    const res = await fetch(`/tableau-sites?t=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('tableau sites fetch failed');
    const data = await res.json();
    const profiles = Array.isArray(data.profiles) ? data.profiles : [];
    const activeId = data.active_profile_id || '';
    select.innerHTML = '';
    profiles.forEach(function (p) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.disabled = !p.enabled;
      const host = p.host || '';
      const site = p.site_display || p.site_name || 'Default site';
      const kind = (p.kind === 'cloud') ? 'Cloud' : 'Server';
      // Short, distinct labels so both sites are obvious in the dropdown
      const shortLabel = kind + ' · ' + site;
      opt.textContent = p.enabled
        ? shortLabel
        : shortLabel + ' (not configured)';
      opt.title = (p.label || p.id) + (host ? ' — ' + host : '');
      if (p.id === activeId) opt.selected = true;
      select.appendChild(opt);
    });
    if (!select._bound) {
      select._bound = true;
      select.addEventListener('change', async function () {
        const next = select.value;
        select.disabled = true;
        try {
          await activateTableauSite(next);
        } catch (err) {
          alert(err.message || String(err));
          await loadTableauSites();
        } finally {
          select.disabled = false;
        }
      });
    }
    return data;
  } catch (_) {
    select.innerHTML = '<option value="">Could not load</option>';
    return null;
  }
}

async function loadMcpInfo() {
  const serverEl = document.getElementById('mcpServerInfo');
  const siteEl = document.getElementById('mcpSiteInfo');
  const providerEl = document.getElementById('mcpLlmProvider');
  const modelEl = document.getElementById('mcpLlmModel');
  if (!serverEl || !siteEl) return;

  try {
    const res = await fetch(`/mcp-info?t=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('mcp info fetch failed');

    const data = await res.json();
    const server = (data.server || '').trim();
    const site = (data.site_name || '').trim();
    const provider = (data.llm_provider || '').trim();
    const model = (data.llm_model || '').trim();

    if (providerEl) providerEl.textContent = provider || 'LLM';
    if (modelEl) modelEl.textContent = model || 'Not set';

    if (!server) {
      serverEl.textContent = 'Not configured';
      siteEl.textContent = site || 'Not set';
      return;
    }

    let hostText = server;
    try {
      hostText = new URL(server).host;
    } catch (_) {
      // Keep raw server text if URL parsing fails.
    }

    const isCloud = hostText.includes('online.tableau.com');
    serverEl.textContent = `${isCloud ? 'Tableau Cloud' : 'Tableau Server'} - ${hostText}`;
    siteEl.textContent = site || 'Default site';
  } catch (_) {
    serverEl.textContent = 'Could not load';
    siteEl.textContent = 'Could not load';
    if (providerEl) providerEl.textContent = 'LLM';
    if (modelEl) modelEl.textContent = 'Could not load';
  }
}

function bindDatasourcePicker() {
  const search = document.getElementById('dsSearch');
  const refresh = document.getElementById('dsRefreshBtn');
  if (search) {
    search.addEventListener('focus', function () {
      openDsDropdown();
      if (!siteDatasources.length && dsLoadState !== 'loading') loadDatasources(true);
    });
    search.addEventListener('input', function () {
      openDsDropdown();
    });
    search.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closeDsDropdown();
        search.blur();
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        const matches = filterSiteDatasources(search.value);
        if (matches.length === 1) {
          setActiveDatasource({
            luid: matches[0].id,
            name: matches[0].name,
            projectName: matches[0].projectName || '',
          });
          search.value = matches[0].name;
          closeDsDropdown();
          updateUiForDatasourceGate();
        }
      }
    });
  }
  if (refresh) {
    refresh.addEventListener('click', function () {
      loadDatasources(true);
      openDsDropdown();
    });
  }
  document.addEventListener('click', function (e) {
    const picker = document.getElementById('dsPicker');
    if (!picker) return;
    if (!picker.contains(e.target)) closeDsDropdown();
  });
}

// ── Progress panel (tool / prompt trace) ──────────────────────────────────────
function setProgressCollapsed(collapsed) {
  const shell = document.getElementById('appShell');
  const openBtn = document.getElementById('progressOpenBtn');
  if (!shell) return;
  shell.classList.toggle('progress-collapsed', !!collapsed);
  shell.classList.toggle('progress-open', !collapsed);
  if (openBtn) openBtn.hidden = !collapsed;
  try {
    localStorage.setItem('tableau-studio-progress-collapsed', collapsed ? '1' : '0');
  } catch (_) {}
}

function bindProgressPanel() {
  const closeBtn = document.getElementById('progressCloseBtn');
  const openBtn = document.getElementById('progressOpenBtn');
  if (closeBtn) {
    closeBtn.addEventListener('click', function () {
      setProgressCollapsed(true);
    });
  }
  if (openBtn) {
    openBtn.addEventListener('click', function () {
      setProgressCollapsed(false);
    });
  }
  let collapsed = false;
  try {
    collapsed = localStorage.getItem('tableau-studio-progress-collapsed') === '1';
  } catch (_) {}
  if (window.matchMedia('(max-width: 960px)').matches) collapsed = true;
  setProgressCollapsed(collapsed);
}

function getProgressRuns(conversationId) {
  const id = conversationId || appState.currentId;
  if (!id) return [];
  if (!progressRunsByConversation.has(id)) progressRunsByConversation.set(id, []);
  return progressRunsByConversation.get(id);
}

function truncatePromptLabel(text, limit) {
  const t = String(text || '').replace(/\s+/g, ' ').trim();
  const max = limit || 72;
  if (t.length <= max) return t || 'Untitled prompt';
  return t.slice(0, max - 1) + '…';
}

function appendProgressRun(conversationId, prompt, steps) {
  const runs = getProgressRuns(conversationId);
  const run = {
    id: 'run-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7),
    prompt: String(prompt || ''),
    steps: Array.isArray(steps) ? steps : [],
    createdAt: Date.now(),
  };
  runs.push(run);
  latestTraceSteps = run.steps;
  if (conversationId === appState.currentId) {
    renderProgressPanel({ scrollToLatest: true, openRunId: run.id });
  }
}

function buildProgressStepEl(step, idx) {
  const wrap = document.createElement('div');
  wrap.className = 'progress-step';
  wrap.dataset.kind = step.kind || 'step';

  const summary = document.createElement('button');
  summary.type = 'button';
  summary.className = 'progress-step-summary';

  const badge = document.createElement('span');
  badge.className = 'progress-step-badge';
  badge.textContent = String(step.index || idx + 1);

  const copy = document.createElement('span');
  copy.className = 'progress-step-copy';
  const title = document.createElement('span');
  title.className = 'progress-step-title';
  title.textContent = step.title || step.kind || 'Step';
  const kind = document.createElement('span');
  kind.className = 'progress-step-kind';
  kind.textContent = step.kind || 'step';
  copy.appendChild(title);
  copy.appendChild(kind);

  const chev = document.createElement('span');
  chev.className = 'progress-step-chevron';
  chev.textContent = '›';

  summary.appendChild(badge);
  summary.appendChild(copy);
  summary.appendChild(chev);
  summary.addEventListener('click', function () {
    wrap.classList.toggle('open');
  });

  const detail = document.createElement('div');
  detail.className = 'progress-step-detail';
  const pre = document.createElement('pre');
  pre.textContent = step.detail || '(empty)';
  detail.appendChild(pre);

  wrap.appendChild(summary);
  wrap.appendChild(detail);
  return wrap;
}

/** @deprecated use renderProgressPanel / appendProgressRun */
function renderProgressSteps(steps) {
  appendProgressRun(appState.currentId, 'Manual trace', steps);
}

function renderProgressPanel(opts) {
  opts = opts || {};
  const host = document.getElementById('progressSteps');
  const meta = document.getElementById('progressMeta');
  const empty = document.getElementById('progressEmpty');
  if (!host) return;

  const runs = getProgressRuns(appState.currentId);
  const openRunId = opts.openRunId || (runs.length ? runs[runs.length - 1].id : '');
  let totalSteps = 0;
  let toolEvents = 0;
  runs.forEach(function (run) {
    const steps = run.steps || [];
    totalSteps += steps.length;
    toolEvents += steps.filter(function (s) {
      return s.kind === 'tool_call' || s.kind === 'tool_result';
    }).length;
  });

  if (meta) {
    meta.textContent = runs.length
      ? (runs.length + ' turn' + (runs.length === 1 ? '' : 's') + ' · ' + totalSteps + ' steps · ' + toolEvents + ' tools')
      : 'Grouped by each question';
  }

  host.querySelectorAll('.progress-run, .progress-step').forEach(function (el) { el.remove(); });
  if (empty) {
    empty.hidden = runs.length > 0;
    empty.textContent = 'Send a message to see each question’s tools and prompts grouped here.';
  }

  runs.forEach(function (run, runIdx) {
    const group = document.createElement('section');
    group.className = 'progress-run';
    group.dataset.runId = run.id;
    if (run.id === openRunId) group.classList.add('open');

    const head = document.createElement('button');
    head.type = 'button';
    head.className = 'progress-run-summary';

    const idxBadge = document.createElement('span');
    idxBadge.className = 'progress-run-badge';
    idxBadge.textContent = String(runIdx + 1);

    const copy = document.createElement('span');
    copy.className = 'progress-run-copy';
    const title = document.createElement('span');
    title.className = 'progress-run-title';
    title.textContent = truncatePromptLabel(run.prompt, 80);
    title.title = run.prompt || '';
    const sub = document.createElement('span');
    sub.className = 'progress-run-meta';
    const stepCount = (run.steps || []).length;
    const tools = (run.steps || []).filter(function (s) {
      return s.kind === 'tool_call' || s.kind === 'tool_result';
    }).length;
    sub.textContent = stepCount + ' steps · ' + tools + ' tool events';
    copy.appendChild(title);
    copy.appendChild(sub);

    const chev = document.createElement('span');
    chev.className = 'progress-run-chevron';
    chev.textContent = '›';

    head.appendChild(idxBadge);
    head.appendChild(copy);
    head.appendChild(chev);
    head.addEventListener('click', function () {
      group.classList.toggle('open');
    });

    const body = document.createElement('div');
    body.className = 'progress-run-body';
    (run.steps || []).forEach(function (step, idx) {
      const stepEl = buildProgressStepEl(step, idx);
      // Expand first couple of steps in the active (latest) run
      if (run.id === openRunId && idx < 2) stepEl.classList.add('open');
      body.appendChild(stepEl);
    });
    if (!(run.steps || []).length) {
      const none = document.createElement('p');
      none.className = 'progress-run-empty';
      none.textContent = 'No tool/prompt steps recorded for this turn.';
      body.appendChild(none);
    }

    group.appendChild(head);
    group.appendChild(body);
    host.appendChild(group);
  });

  if (runs.length) {
    setProgressCollapsed(false);
    if (opts.scrollToLatest) {
      requestAnimationFrame(function () {
        const latest = host.querySelector('.progress-run[data-run-id="' + openRunId + '"]')
          || host.querySelector('.progress-run:last-child');
        if (latest) latest.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      });
    }
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('messageInput');
  const newChatBtn = document.getElementById('newChatBtn');
  const deleteChatBtn = document.getElementById('deleteChatBtn');
  const toolsSearch = document.getElementById('toolsSearch');
  loadConversationState();
  bindDatasourcePicker();
  bindProgressPanel();
  renderProgressPanel();
  renderSidebarShortcuts();
  renderShortcutBar();
  renderWelcomeShortcuts();
  renderActiveDatasource();
  updateUiForDatasourceGate();
  ensurePreferredLlmProfile()
    .then(function () { return loadMcpInfo(); })
    .then(function () { return loadLlmProfiles(); })
    .then(function () { return loadTableauSites(); })
    .catch(function () {
      loadMcpInfo();
      loadLlmProfiles();
      loadTableauSites();
    });
  loadTools();
  loadDatasources(true);
  if (!appState.currentId || appState.conversations.length === 0) {
    createConversation();
  } else {
    renderHistoryList();
    renderConversation();
  }
  renderActiveDatasource();
  updateUiForDatasourceGate();
  if (newChatBtn) newChatBtn.addEventListener('click', createConversation);
  if (deleteChatBtn) {
    deleteChatBtn.addEventListener('click', () => {
      if (!appState.currentId) return;
      deleteConversation(appState.currentId);
    });
  }
  if (toolsSearch) {
    toolsSearch.addEventListener('input', () => renderToolsList(toolsSearch.value));
  }
  if (input) {
    input.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
  }
});
