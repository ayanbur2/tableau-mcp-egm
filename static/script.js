const PALETTE = ['#4f6ef7','#8b5cf6','#10b981','#f59e0b','#ef4444','#0ea5e9','#a855f7','#14b8a6'];
let chartCounter = 0;
const CHAT_STORAGE_KEY = 'tableau-chat-history-v1';
let appState = { conversations: [], currentId: null };

// ── Lightweight markdown ──────────────────────────────────────────────────────
function renderMarkdown(raw) {
  let t = raw.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  t = t
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/^#{1,3} (.+)$/gm, '<strong>$1</strong>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  t = t.replace(/(<li>[^\n]*\n?)+/g, s => `<ul>${s}</ul>`);
  t = t.replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>');
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
  const { persist = true } = options;
  const welcome = document.getElementById('welcomeScreen');
  if (welcome) welcome.remove();

  const chatBox = document.getElementById('chatBox');
  const msg = document.createElement('div');
  msg.className = `msg ${role}${isThinking ? ' thinking' : ''}`;

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
    if (persist) persistMessage(role, text);
    return msg;
  } else {
    bubble.textContent = text;
  }

  msg.appendChild(avatar);
  msg.appendChild(bubble);
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
  if (persist && !isThinking) persistMessage(role, text);
  return msg;
}

// ── Send ──────────────────────────────────────────────────────────────────────
async function sendMessage() {
  const input = document.getElementById('messageInput');
  const btn   = document.getElementById('sendBtn');
  const text  = input.value.trim();
  if (!text) return;

  input.value = '';
  input.style.height = 'auto';
  addMessage(text, 'user');

  btn.disabled = true;
  const thinking = addMessage('', 'bot', true);

  try {
    const res  = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    thinking.remove();
    addMessage(data.response || 'No response received.', 'bot');
  } catch (_) {
    thinking.remove();
    addMessage('Connection error — is the server running?', 'bot');
  } finally {
    btn.disabled = false;
    input.focus();
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
  appState.conversations.unshift(convo);
  appState.currentId = convo.id;
  saveConversationState();
  renderHistoryList();
  renderConversation();
}

function deleteConversation(conversationId) {
  const idx = appState.conversations.findIndex(c => c.id === conversationId);
  if (idx === -1) return;

  const wasCurrent = appState.currentId === conversationId;
  appState.conversations.splice(idx, 1);

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
}

function persistMessage(role, text) {
  const convo = getCurrentConversation();
  if (!convo) return;
  convo.messages.push({ role, text });
  convo.updatedAt = Date.now();
  if (convo.title === 'New chat' && role === 'user') {
    convo.title = text.slice(0, 34) || 'New chat';
  }
  appState.conversations.sort((a, b) => b.updatedAt - a.updatedAt);
  saveConversationState();
  renderHistoryList();
}

function renderHistoryList() {
  const list = document.getElementById('historyList');
  if (!list) return;
  list.innerHTML = '';
  appState.conversations.forEach(convo => {
    const btn = document.createElement('button');
    btn.className = `history-item${convo.id === appState.currentId ? ' active' : ''}`;
    const txt = document.createElement('span');
    txt.className = 'history-item-text';
    txt.textContent = convo.title || 'New chat';

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
        <h2>Ask anything about your data</h2>
        <p>Query your Tableau datasources, surface insights, and render charts automatically.</p>
      </div>`;
    return;
  }

  convo.messages.forEach(msg => addMessage(msg.text, msg.role, false, { persist: false }));
}

async function loadMcpInfo() {
  const serverEl = document.getElementById('mcpServerInfo');
  const siteEl = document.getElementById('mcpSiteInfo');
  if (!serverEl || !siteEl) return;

  try {
    const res = await fetch(`/mcp-info?t=${Date.now()}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('mcp info fetch failed');

    const data = await res.json();
    const server = (data.server || '').trim();
    const site = (data.site_name || '').trim();

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
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('messageInput');
  const newChatBtn = document.getElementById('newChatBtn');
  const deleteChatBtn = document.getElementById('deleteChatBtn');
  input.focus();
  loadMcpInfo();
  loadConversationState();
  if (!appState.currentId || appState.conversations.length === 0) {
    createConversation();
  } else {
    renderHistoryList();
    renderConversation();
  }
  if (newChatBtn) newChatBtn.addEventListener('click', createConversation);
  if (deleteChatBtn) {
    deleteChatBtn.addEventListener('click', () => {
      if (!appState.currentId) return;
      deleteConversation(appState.currentId);
    });
  }
  input.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
});
