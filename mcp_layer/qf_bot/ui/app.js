// ═══════════════════════════════════════════════════════════════════
// QUANTUMFLEX MOBILE HUD — CLIENT RUNTIME
// Multi-Agent Swarm, Mesh Telemetry, Swipeable Tabs, PWA Support
// ═══════════════════════════════════════════════════════════════════

let activeBot = "";
let deferredInstallPrompt = null;
const tabs = ['view-chat', 'view-mesh', 'view-swarm', 'view-alerts'];
let currentTabIndex = 0;

// ── PWA Installation & Service Worker ──────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/ui/sw.js')
      .then(reg => console.log('QuantumFlex SW registered:', reg.scope))
      .catch(err => console.log('SW registration failed:', err));
  });
}

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  const btn = document.getElementById('btnPwaInstall');
  if (btn) btn.style.display = 'inline-flex';
});

function installPWA() {
  hapticFeedback('medium');
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    deferredInstallPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        const btn = document.getElementById('btnPwaInstall');
        if (btn) btn.style.display = 'none';
      }
      deferredInstallPrompt = null;
    });
  } else {
    const modal = document.getElementById('pwaGuideModal');
    if (modal) {
      modal.style.display = 'flex';
    } else {
      window.location.href = '/download';
    }
  }
}

// ── Haptic Feedback ────────────────────────────────────────────────
function hapticFeedback(type = 'light') {
  if (navigator.vibrate) {
    if (type === 'light') navigator.vibrate(8);
    if (type === 'medium') navigator.vibrate(18);
    if (type === 'heavy') navigator.vibrate([25, 15, 25]);
  }
}

// ── View Switching & Swipe Navigation ──────────────────────────────
function switchView(viewId, btnElement = null) {
  hapticFeedback('light');
  document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));

  const targetPane = document.getElementById(viewId);
  if (targetPane) targetPane.classList.add('active');

  currentTabIndex = tabs.indexOf(viewId);

  if (btnElement) {
    btnElement.classList.add('active');
  } else {
    const navBtn = document.querySelector(`.nav-tab[data-tab="${viewId}"]`);
    if (navBtn) navBtn.classList.add('active');
  }

  // Auto-refresh when entering view
  if (viewId === 'view-mesh') loadMeshNodes();
  if (viewId === 'view-swarm') loadSwarmData();
}

// Touch swipe gesture listeners
let touchStartX = 0;
let touchEndX = 0;

const viewsContainer = document.getElementById('viewsContainer');
viewsContainer.addEventListener('touchstart', (e) => {
  touchStartX = e.changedTouches[0].screenX;
}, { passive: true });

viewsContainer.addEventListener('touchend', (e) => {
  touchEndX = e.changedTouches[0].screenX;
  handleSwipeGesture();
}, { passive: true });

function handleSwipeGesture() {
  const diff = touchEndX - touchStartX;
  // Threshold 50px swipe
  if (Math.abs(diff) > 50) {
    if (diff < 0 && currentTabIndex < tabs.length - 1) {
      // Swiped left -> next tab
      switchView(tabs[currentTabIndex + 1]);
    } else if (diff > 0 && currentTabIndex > 0) {
      // Swiped right -> previous tab
      switchView(tabs[currentTabIndex - 1]);
    }
  }
}

// ── Agent Selector ─────────────────────────────────────────────────
function selectAgent(botCallsign, element) {
  hapticFeedback('light');
  activeBot = botCallsign;
  document.querySelectorAll('.agent-pill').forEach(p => p.classList.remove('active'));
  if (element) element.classList.add('active');

  const input = document.getElementById('chatInput');
  if (botCallsign) {
    input.placeholder = `Directive for @${botCallsign.toUpperCase()}...`;
  } else {
    input.placeholder = 'Tactical directive or /hardstop...';
  }
}

// ── Quick Prompt Chips ─────────────────────────────────────────────
function sendPrompt(text) {
  document.getElementById('chatInput').value = text;
  document.getElementById('chatForm').dispatchEvent(new Event('submit'));
}

// ── Chat Directive Submission ──────────────────────────────────────
document.getElementById('chatForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;

  hapticFeedback('medium');
  const feed = document.getElementById('chatFeed');

  // Append user bubble
  feed.innerHTML += `
    <div class="msg-bubble user">
      <p>${escapeHtml(msg)}</p>
    </div>
  `;
  input.value = '';
  feed.scrollTop = feed.scrollHeight;

  // Placeholder thinking bubble
  const loadingId = 'loading-' + Date.now();
  feed.innerHTML += `
    <div class="msg-bubble bot" id="${loadingId}">
      <div class="msg-header">
        <span>⬡ PROCESSING DIRECTIVE...</span>
      </div>
      <p style="color:var(--text-muted);">Evaluating variables and zero-trust policy...</p>
    </div>
  `;
  feed.scrollTop = feed.scrollHeight;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        target_bot: activeBot || undefined
      })
    });
    const data = await res.json();
    const loadingElem = document.getElementById(loadingId);
    if (loadingElem) loadingElem.remove();

    const sender = data.bot ? `${data.bot.avatar} ${data.bot.name}` : '▲ SENTINEL';
    const isHardstop = data.mode === 'hardstop';
    const borderColor = isHardstop ? 'border-left: 3px solid #ff4444;' : '';

    feed.innerHTML += `
      <div class="msg-bubble bot" style="${borderColor}">
        <div class="msg-header">
          <span>${sender}</span>
        </div>
        <p>${formatMessageContent(data.response)}</p>
      </div>
    `;
  } catch (err) {
    const loadingElem = document.getElementById(loadingId);
    if (loadingElem) loadingElem.remove();
    feed.innerHTML += `
      <div class="msg-bubble bot" style="border-left: 3px solid #ff4444;">
        <div class="msg-header" style="color:#ff4444;">FAULT ENCOUNTERED</div>
        <p style="color:#ff8888;">Node unreachable or API error: ${err.message}</p>
      </div>
    `;
  }
  feed.scrollTop = feed.scrollHeight;
});

function escapeHtml(text) {
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}

function formatMessageContent(text) {
  if (text.includes('[') && text.includes(']')) {
    return `<pre>${escapeHtml(text)}</pre>`;
  }
  return escapeHtml(text).replace(/\n/g, '<br>');
}

// ── Live Telemetry & Observations Poller ───────────────────────────
async function loadMeshNodes() {
  try {
    const res = await fetch('/api/mesh/nodes');
    const data = await res.json();
    if (data.nodes) {
      const grid = document.getElementById('nodeCardsGrid');
      grid.innerHTML = data.nodes.map(n => `
        <div class="node-glass-card">
          <div class="node-left">
            <div class="node-name-row">
              <span style="color:${n.status === 'ONLINE' ? 'var(--teal-signal)' : 'var(--status-amber)'};">●</span>
              <span class="node-name">${escapeHtml(n.name)}</span>
            </div>
            <div class="node-ip">${escapeHtml(n.ip)} · ${escapeHtml(n.role)}</div>
            <div class="node-detail">${escapeHtml(n.hardware_trust)} · ${escapeHtml(n.solvency)}</div>
          </div>
          <div class="node-right">
            <span class="status-badge ${n.status === 'ONLINE' ? 'online' : 'readonly'}">${escapeHtml(n.status)}</span>
            <span class="latency-tag">${escapeHtml(n.latency)}</span>
          </div>
        </div>
      `).join('');
    }
  } catch (e) {
    console.warn("Mesh fetch error", e);
  }
}

async function loadSwarmData() {
  try {
    const res = await fetch('/api/observations');
    const data = await res.json();
    if (data.observations) {
      const obsList = document.getElementById('obsList');
      obsList.innerHTML = data.observations.map(obs => `
        <div class="obs-card ${obs.source === 'lyceum-peer' ? 'read-only' : ''}">
          <div class="obs-header">
            <span class="obs-source ${obs.source === 'lyceum-peer' ? 'lyceum' : ''}">${escapeHtml(obs.source.toUpperCase())}</span>
            <span class="obs-time">${obs.timestamp ? obs.timestamp.substring(11, 19) : ''}</span>
          </div>
          <div class="obs-title">${escapeHtml(obs.title)}</div>
          <div class="obs-detail">${escapeHtml(obs.detail)}</div>
        </div>
      `).join('');
    }

    const dRes = await fetch('/api/drafts');
    const dData = await dRes.json();
    if (dData.drafts) {
      const draftsList = document.getElementById('draftsList');
      if (dData.drafts.length === 0) {
        draftsList.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted); font-family:var(--font-mono);">No pending authorizations. Pipelines optimal.</div>`;
      } else {
        draftsList.innerHTML = dData.drafts.map(d => `
          <div class="obs-card" style="border-left-color: var(--teal-signal); margin-bottom: 8px;">
            <div class="obs-header">
              <span style="color:var(--teal-signal); font-weight:bold;">${escapeHtml(d.draft_id)} [${escapeHtml(d.status)}]</span>
              <span class="obs-time">${d.created_at ? d.created_at.substring(11, 19) : ''}</span>
            </div>
            <div class="obs-title">${escapeHtml(d.title)}</div>
            <div class="obs-detail">${escapeHtml(d.description)}</div>
          </div>
        `).join('');
      }
    }
  } catch (e) {
    console.warn("Swarm fetch error", e);
  }
}

// Initial bootstrap load
loadMeshNodes();
loadSwarmData();
setInterval(() => {
  if (currentTabIndex === 1) loadMeshNodes();
  if (currentTabIndex === 2) loadSwarmData();
}, 10000);

// Hash route handler
window.addEventListener('DOMContentLoaded', () => {
  const hash = window.location.hash.replace('#', '');
  if (tabs.includes(hash)) {
    switchView(hash);
  }
});
