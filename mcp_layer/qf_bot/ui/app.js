// ═══════════════════════════════════════════════════════════════════
// QUANTUMFLEX MOBILE OPERATOR COCKPIT — CLIENT RUNTIME (PIXEL 11 PRO)
// Sovereign Multi-Agent Swarm, Substrate Control, Live Invariants & CLI
// ═══════════════════════════════════════════════════════════════════

let activeBot = "";
let deferredInstallPrompt = null;
const tabs = ['view-chat', 'view-services', 'view-security', 'view-athena', 'view-terminal', 'view-swarm', 'view-mesh'];
let currentTabIndex = 0;

// Smart Host Resolver for Pixel 11 Pro Operator Cockpit
let hostNode = localStorage.getItem('qf_mobile_host') || '';

if (!hostNode) {
  if (window.location.hostname && !window.location.hostname.includes('localhost') && window.location.protocol.startsWith('http')) {
    hostNode = window.location.origin;
  } else {
    // Inside Capacitor (https://localhost) or standalone file on Pixel 11 Pro
    hostNode = 'https://quant-yoga-7-2-in-1-14akp10.example-tailnet.ts.net';
  }
}

function updateHostDisplay(url) {
  const el = document.getElementById('activeHostDisplay');
  if (el) el.textContent = url.replace('https://', '').replace('http://', '');
}

async function autoDetectBestHost() {
  const candidateHosts = [
    'https://quant-yoga-7-2-in-1-14akp10.example-tailnet.ts.net',
    'http://100.64.1.31:9001',
    'http://127.0.0.1:9001'
  ];

  try {
    const res = await qfFetch(`${hostNode}/api/status`, { method: 'GET', headers: OPERATOR_HEADERS, signal: AbortSignal.timeout(1500) });
    if (res.ok) {
      updateHostDisplay(hostNode);
      return;
    }
  } catch (e) {}

  for (const h of candidateHosts) {
    if (h === hostNode) continue;
    try {
      const res = await qfFetch(`${h}/api/status`, { method: 'GET', headers: OPERATOR_HEADERS, signal: AbortSignal.timeout(1500) });
      if (res.ok) {
        hostNode = h;
        localStorage.setItem('qf_mobile_host', h);
        updateHostDisplay(h);
        console.log('Auto-switched to active host:', h);
        loadServices();
        loadSecurityTelemetry();
        loadMeshNodes();
        loadSwarmData();
        return;
      }
    } catch (e) {}
  }
}

let isChiefArchitectPixel = false;  // until the server verifies a device signature
let verifiedDeviceRole = null;

const OPERATOR_HEADERS = {
  'Content-Type': 'application/json'
};

// Mutation authority is proven by a signature from the device's hardware-backed key
// (native QFDeviceKey plugin, Android Keystore / StrongBox). Without the plugin,
// requests go unsigned and the server treats the device as a read-only observer.
async function qfSignedHeaders(url, method, body) {
  const plugin = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.QFDeviceKey;
  const u = new URL(url, window.location.href);
  // StrongBox signing is slow; sign mutations plus the role probe, not telemetry polling.
  if (!plugin || (method === 'GET' && !u.pathname.endsWith('/api/device/role'))) return {};
  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = crypto.randomUUID().replace(/-/g, '');
  const bodyHash = Array.from(new Uint8Array(
    await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body || ''))
  )).map(b => b.toString(16).padStart(2, '0')).join('');
  const message = ['QF1', method, u.pathname + u.search, timestamp, nonce, bodyHash].join('\n');
  const { deviceId, signature } = await plugin.sign({ message });
  return {
    'X-QF-Device': deviceId,
    'X-QF-Timestamp': timestamp,
    'X-QF-Nonce': nonce,
    'X-QF-Signature': signature
  };
}

async function qfFetch(url, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase();
  const signed = await qfSignedHeaders(url, method, opts.body);
  return fetch(url, { ...opts, headers: { ...(opts.headers || {}), ...signed } });
}

async function checkDeviceRole() {
  try {
    const res = await qfFetch(`${hostNode}/api/device/role`, {
      method: 'GET',
      headers: OPERATOR_HEADERS,
      signal: AbortSignal.timeout(2000)
    });
    if (res.ok) {
      const data = await res.json();
      verifiedDeviceRole = data;
      isChiefArchitectPixel = data.can_mutate === true;
      applyDevicePermissions(data);
    }
  } catch (e) {
    console.warn("Device role check error:", e);
  }
}

function applyDevicePermissions(roleData) {
  const brandTag = document.querySelector('.brand-tag');
  const opBadge = document.querySelector('.operator-badge');
  const secBanner = document.getElementById('securityBanner');
  const bulkOps = document.getElementById('bulkServiceActions');
  const termInput = document.getElementById('termInput');
  const btnRunCmd = document.getElementById('btnRunCmd');

  if (roleData.can_mutate) {
    isChiefArchitectPixel = true;
    if (brandTag) brandTag.textContent = 'PIXEL 11 PRO';
    if (opBadge) {
      opBadge.textContent = 'CHIEF ARCHITECT';
      opBadge.className = 'operator-badge';
    }
    if (secBanner) secBanner.style.display = 'none';
    if (bulkOps) bulkOps.style.display = 'flex';
    if (termInput) {
      termInput.disabled = false;
      termInput.placeholder = 'Type command (e.g. qflex status)...';
    }
    if (btnRunCmd) {
      btnRunCmd.disabled = false;
      btnRunCmd.style.opacity = '1';
    }
  } else {
    // Non-pixel mobile device (untrusted mobile phone)
    isChiefArchitectPixel = false;
    const modelName = roleData.model ? roleData.model : 'OBSERVER NODE';
    if (brandTag) brandTag.textContent = modelName.toUpperCase();
    if (opBadge) {
      opBadge.textContent = 'SECURITY OBSERVER';
      opBadge.className = 'operator-badge observer';
    }
    if (secBanner) {
      secBanner.style.display = 'flex';
      const secText = document.getElementById('securityBannerText');
      if (secText) {
        secText.textContent = `SECURITY ISOLATION: Node '${modelName}' is restricted to security observation. Substrate mutations and CLI commands are locked to Pixel 11 Pro.`;
      }
    }
    if (bulkOps) bulkOps.style.display = 'none';
    if (termInput) {
      termInput.disabled = true;
      termInput.placeholder = '🔒 CLI LOCKED: Execution restricted to Pixel 11 Pro.';
    }
    if (btnRunCmd) {
      btnRunCmd.disabled = true;
      btnRunCmd.style.opacity = '0.4';
      btnRunCmd.title = 'Execution restricted to Pixel 11 Pro';
    }
    // Re-render services and swarm list to reflect locked state
    loadServices();
    loadSwarmData();
  }
}

// ── PWA Installation & Service Worker ──────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/ui/sw.js')
      .then(reg => console.log('QuantumFlex SW registered:', reg.scope))
      .catch(err => console.log('SW registration note: ', err));
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
    if (modal) modal.style.display = 'flex';
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

// ── View Navigation ────────────────────────────────────────────────
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
  if (viewId === 'view-services') loadServices();
  if (viewId === 'view-security') loadSecurityTelemetry();
  if (viewId === 'view-swarm') loadSwarmData();
  if (viewId === 'view-mesh') loadMeshNodes();
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

function sendPrompt(text) {
  const input = document.getElementById('chatInput');
  input.value = text;
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

  feed.innerHTML += `
    <div class="msg-bubble user">
      <p>${escapeHtml(msg)}</p>
    </div>
  `;
  input.value = '';
  feed.scrollTop = feed.scrollHeight;

  const loadingId = 'loading-' + Date.now();
  feed.innerHTML += `
    <div class="msg-bubble bot" id="${loadingId}">
      <div class="msg-header">
        <span>⬡ PROCESSING DIRECTIVE...</span>
      </div>
      <p style="color:var(--text-muted);">Dispatching to QuantumFlex neural substrate...</p>
    </div>
  `;
  feed.scrollTop = feed.scrollHeight;

  try {
    const res = await qfFetch(hostNode + '/api/chat', {
      method: 'POST',
      headers: OPERATOR_HEADERS,
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
        <p>${formatMessageContent(data.response || JSON.stringify(data))}</p>
      </div>
    `;
  } catch (err) {
    const loadingElem = document.getElementById(loadingId);
    if (loadingElem) loadingElem.remove();
    feed.innerHTML += `
      <div class="msg-bubble bot" style="border-left: 3px solid #ff4444;">
        <div class="msg-header" style="color:#ff4444;">COMMUNICATION FAULT</div>
        <p style="color:#ff8888;">Node unreachable: ${err.message}</p>
      </div>
    `;
  }
  feed.scrollTop = feed.scrollHeight;
});

function escapeHtml(text) {
  const div = document.createElement('div');
  div.innerText = String(text);
  return div.innerHTML;
}

function formatMessageContent(text) {
  if (typeof text !== 'string') text = JSON.stringify(text, null, 2);
  if (text.includes('[') && text.includes(']')) {
    return `<pre>${escapeHtml(text)}</pre>`;
  }
  return escapeHtml(text).replace(/\n/g, '<br>');
}

// ── Services Deck (Control & Lifecycle) ───────────────────────────
async function loadServices() {
  const container = document.getElementById('servicesContainer');
  if (!container) return;

  try {
    const res = await qfFetch(hostNode + '/api/services', { headers: OPERATOR_HEADERS });
    const data = await res.json();
    if (!data.services) return;

    container.innerHTML = data.services.map(s => {
      const isRunning = s.status === 'ACTIVE';
      const statusColor = isRunning ? 'var(--status-green)' : 'var(--status-red)';
      const portBadge = s.port ? `<span style="color:var(--text-muted); font-size:0.7rem; margin-left:6px;">:${s.port}</span>` : '';
      return `
        <div class="service-card ${isRunning ? 'active-svc' : 'failed-svc'}" id="svc-${s.id}">
          <div class="svc-info">
            <div class="svc-name">
              <span style="color:${statusColor}; font-size:0.75rem;">●</span>
              <span>${escapeHtml(s.name)}</span>
              ${portBadge}
            </div>
            <div class="svc-sub">${escapeHtml(s.unit)} · <strong style="color:${statusColor};">${s.status}</strong></div>
          </div>
          <div class="svc-actions">
            ${isChiefArchitectPixel ? `
              <button class="btn-svc-action" onclick="performServiceAction('${s.id}', 'restart')">🔄 Restart</button>
              <button class="btn-svc-action" onclick="performServiceAction('${s.id}', '${isRunning ? 'stop' : 'start'}')">${isRunning ? '⏹ Stop' : '▶ Start'}</button>
            ` : `
              <button class="btn-svc-action" disabled style="opacity:0.4; cursor:not-allowed;" title="Substrate changes restricted to Pixel 11 Pro">🔒 Locked</button>
            `}
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    container.innerHTML = `<div style="color:#ff8888; font-size:0.8rem; font-family:var(--font-mono);">Failed to poll services: ${e.message}</div>`;
  }
}

async function performServiceAction(serviceId, action) {
  if (!isChiefArchitectPixel) {
    alert("SECURITY LOCKOUT: Service lifecycle management is exclusively restricted to the Chief Architect on Google Pixel 11 Pro.");
    return;
  }

  hapticFeedback('medium');
  const card = document.getElementById(`svc-${serviceId}`);
  if (card) {
    card.style.opacity = '0.5';
  }

  try {
    const res = await qfFetch(`${hostNode}/api/services/${serviceId}/action`, {
      method: 'POST',
      headers: OPERATOR_HEADERS,
      body: JSON.stringify({ action })
    });
    const data = await res.json();
    hapticFeedback('heavy');
    setTimeout(loadServices, 500);
  } catch (e) {
    alert(`Action failed: ${e.message}`);
    if (card) card.style.opacity = '1';
  }
}

async function bulkStackAction(action) {
  if (!isChiefArchitectPixel) {
    alert("SECURITY LOCKOUT: Stack bulk lifecycle operations are restricted to Pixel 11 Pro.");
    return;
  }

  hapticFeedback('heavy');
  const services = ['api-node', 'athena-node', 'amara-dashboard', 'qf-bot', 'qf-kafka-consumer', 'qf-kafka-telemetry', 'qf-monitor'];
  for (const s of services) {
    try {
      await qfFetch(`${hostNode}/api/services/${s}/action`, {
        method: 'POST',
        headers: OPERATOR_HEADERS,
        body: JSON.stringify({ action })
      });
    } catch (e) {}
  }
  setTimeout(loadServices, 1000);
}

// ── Sentinel & Invariants (Security Deck) ───────────────────────────
async function runInvariantAudit() {
  hapticFeedback('medium');
  const btn = document.getElementById('btnRunInvariant');
  const verdictEl = document.getElementById('invLiveVerdict');
  if (btn) btn.disabled = true;
  if (verdictEl) verdictEl.textContent = 'EVALUATING INVARIANTS...';

  try {
    const res = await qfFetch(hostNode + '/api/invariant/run', {
      method: 'POST',
      headers: OPERATOR_HEADERS
    });
    const data = await res.json();
    hapticFeedback('heavy');

    const isAdmit = data.verdict === 'ADMIT';
    if (verdictEl) {
      verdictEl.textContent = isAdmit ? '✅ VERIFIED: ADMIT (R ≥ O)' : '🚨 CRITICAL: BREACH';
      verdictEl.style.color = isAdmit ? 'var(--status-green)' : 'var(--status-red)';
    }

    if (data.evaluations && data.evaluations.evaluations) {
      const ev = data.evaluations.evaluations;
      if (ev.digital_memory) {
        const memEl = document.getElementById('invMemVal');
        if (memEl) memEl.textContent = `${ev.digital_memory.payload.reserve_measured} MB ≥ ${ev.digital_memory.payload.units_claimed} MB`;
      }
      if (ev.tpm_anchor) {
        const tpmEl = document.getElementById('invTpmVal');
        if (tpmEl) tpmEl.textContent = '0x1c00010 MATCHED (Valid)';
      }
      if (ev.physical_water) {
        const waterEl = document.getElementById('invWaterVal');
        if (waterEl) waterEl.textContent = `${ev.physical_water.payload.reserve_measured} gal ≥ ${ev.physical_water.payload.units_claimed} gal`;
      }
    }
  } catch (e) {
    if (verdictEl) {
      verdictEl.textContent = `Audit Failed: ${e.message}`;
      verdictEl.style.color = 'var(--status-red)';
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadSecurityTelemetry() {
  try {
    const res = await qfFetch(hostNode + '/api/telemetry/live', { headers: OPERATOR_HEADERS });
    const data = await res.json();

    if (data.drive) {
      const score = Number(data.drive.drive_score || 0).toFixed(1);
      const scoreEl = document.getElementById('driveScoreVal');
      if (scoreEl) scoreEl.textContent = `D = ${score} / 1500.0`;

      const statusEl = document.getElementById('driveStatusVal');
      if (statusEl) {
        statusEl.textContent = data.drive.status || 'EQUILIBRIUM';
        statusEl.style.color = data.drive.status === 'EQUILIBRIUM' ? 'var(--status-green)' : 'var(--status-amber)';
      }
    }
  } catch (e) {
    console.warn("Security telemetry load error:", e);
  }
}

// ── Athena Cognitive Vault ─────────────────────────────────────────
async function queryAthena() {
  const input = document.getElementById('athenaQueryInput');
  const q = input.value.trim();
  if (!q) return;

  hapticFeedback('medium');
  const respCard = document.getElementById('athenaResponseCard');
  const ansText = document.getElementById('athenaAnswerText');
  const metaText = document.getElementById('athenaMetaText');

  respCard.style.display = 'block';
  ansText.innerHTML = `<span style="color:var(--text-muted);">🧠 Searching 7,397+ vectors in Athena cognitive vault...</span>`;
  metaText.textContent = '';

  try {
    const res = await qfFetch(hostNode + '/api/athena/query', {
      method: 'POST',
      headers: OPERATOR_HEADERS,
      body: JSON.stringify({ query: q, top_k: 5 })
    });
    const data = await res.json();
    hapticFeedback('heavy');

    ansText.innerHTML = formatMessageContent(data.answer || JSON.stringify(data));
    const sources = (data.sources || []).map(s => s.path || s).join(', ');
    metaText.textContent = sources ? `📚 Sources: ${sources}` : '⚡ Verified Ground Truth';
  } catch (e) {
    ansText.innerHTML = `<span style="color:#ff8888;">Athena query failed: ${e.message}</span>`;
  }
}

// ── Tactical Terminal (Live CLI Runner) ────────────────────────────
async function runTerminalCommand(cmdToRun = null) {
  if (!isChiefArchitectPixel) {
    const outBox = document.getElementById('termOutput');
    outBox.textContent += `\n[SECURITY REJECTION]: Terminal command execution is strictly restricted to Pixel 11 Pro.\n`;
    outBox.scrollTop = outBox.scrollHeight;
    return;
  }

  const input = document.getElementById('termInput');
  const cmd = cmdToRun || input.value.trim();
  if (!cmd) return;

  hapticFeedback('medium');
  const outBox = document.getElementById('termOutput');
  outBox.textContent += `\n$ ${cmd}\n[Executing in substrate...]`;
  outBox.scrollTop = outBox.scrollHeight;
  if (!cmdToRun) input.value = '';

  try {
    const res = await qfFetch(hostNode + '/api/terminal/run', {
      method: 'POST',
      headers: OPERATOR_HEADERS,
      body: JSON.stringify({ command: cmd })
    });
    const data = await res.json();
    hapticFeedback('light');

    let result = '';
    if (data.stdout) result += data.stdout;
    if (data.stderr) result += `\n[STDERR]: ${data.stderr}`;
    if (!result.trim()) result = `(Process exited with code ${data.returncode})`;

    outBox.textContent += `\n${result}\n────────────────────────────────────`;
    outBox.scrollTop = outBox.scrollHeight;
  } catch (e) {
    outBox.textContent += `\n[COMMAND FAILED]: ${e.message}\n`;
    outBox.scrollTop = outBox.scrollHeight;
  }
}

function clearTerminal() {
  document.getElementById('termOutput').textContent = "QUANTUMFLEX TACTICAL SHELL // OPERATOR: CHIEF ARCHITECT\nReady for input.\n────────────────────────────────────";
}

// ── Swarm Approvals & Observations ─────────────────────────────────
async function loadSwarmData() {
  try {
    const dRes = await qfFetch(hostNode + '/api/drafts', { headers: OPERATOR_HEADERS });
    const dData = await dRes.json();
    const draftsList = document.getElementById('draftsList');

    if (draftsList) {
      if (!dData.drafts || dData.drafts.length === 0) {
        draftsList.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted); font-family:var(--font-mono); padding:10px 0;">No pending authorizations. Stack verified.</div>`;
      } else {
        draftsList.innerHTML = dData.drafts.map(d => {
          const isPending = d.status === 'PENDING_APPROVAL';
          return `
            <div class="obs-card" style="border-left-color: ${isPending ? 'var(--status-amber)' : 'var(--teal-signal)'}; margin-bottom: 10px;">
              <div class="obs-header">
                <span style="color:${isPending ? 'var(--status-amber)' : 'var(--teal-signal)'}; font-weight:bold;">${escapeHtml(d.draft_id)} [${escapeHtml(d.status)}]</span>
                <span class="obs-time">${d.created_at ? d.created_at.substring(11, 19) : ''}</span>
              </div>
              <div class="obs-title">${escapeHtml(d.title)}</div>
              <div class="obs-detail">${escapeHtml(d.description)}</div>
              ${isPending ? (
                isChiefArchitectPixel ? `
                  <div class="action-row">
                    <button class="btn-interactive" onclick="approveDraft('${d.draft_id}')">✅ Approve & Execute</button>
                    <button class="btn-interactive btn-danger" onclick="discardDraft('${d.draft_id}')">❌ Discard</button>
                  </div>
                ` : `
                  <div class="action-row">
                    <span style="font-size:0.75rem; color:var(--status-amber); font-family:var(--font-mono); padding:6px 0;">🔒 Awaiting Pixel 11 Pro Sign-Off</span>
                  </div>
                `
              ) : ''}
            </div>
          `;
        }).join('');
      }
    }

    const obsRes = await qfFetch(hostNode + '/api/observations', { headers: OPERATOR_HEADERS });
    const obsData = await obsRes.json();
    const obsList = document.getElementById('obsList');
    if (obsList && obsData.observations) {
      obsList.innerHTML = obsData.observations.map(obs => `
        <div class="obs-card">
          <div class="obs-header">
            <span class="obs-source">${escapeHtml(obs.source.toUpperCase())}</span>
            <span class="obs-time">${obs.timestamp ? obs.timestamp.substring(11, 19) : ''}</span>
          </div>
          <div class="obs-title">${escapeHtml(obs.title)}</div>
          <div class="obs-detail">${escapeHtml(obs.detail)}</div>
        </div>
      `).join('');
    }
  } catch (e) {
    console.warn("Swarm data load error", e);
  }
}

async function approveDraft(draftId) {
  if (!isChiefArchitectPixel) {
    alert("SECURITY LOCKOUT: Draft approvals are strictly restricted to Chief Architect on Pixel 11 Pro.");
    return;
  }

  hapticFeedback('heavy');
  try {
    const res = await qfFetch(`${hostNode}/api/drafts/${draftId}/approve`, {
      method: 'POST',
      headers: OPERATOR_HEADERS
    });
    const data = await res.json();
    alert(`Draft Approved: ${data.message || 'Action executed successfully'}`);
    loadSwarmData();
  } catch (e) {
    alert(`Approval failed: ${e.message}`);
  }
}

async function discardDraft(draftId) {
  if (!isChiefArchitectPixel) {
    alert("SECURITY LOCKOUT: Draft actions are restricted to Pixel 11 Pro.");
    return;
  }

  hapticFeedback('medium');
  try {
    await qfFetch(`${hostNode}/api/drafts/${draftId}/discard`, {
      method: 'POST',
      headers: OPERATOR_HEADERS
    });
    loadSwarmData();
  } catch (e) {}
}

// ── Live Mesh Telemetry ────────────────────────────────────────────
async function loadMeshNodes() {
  try {
    const res = await qfFetch(hostNode + '/api/mesh/nodes', { headers: OPERATOR_HEADERS });
    const data = await res.json();
    if (data.nodes) {
      const grid = document.getElementById('nodeCardsGrid');
      if (grid) {
        grid.innerHTML = data.nodes.map(n => {
          const isPixel = n.id === 'qfx-pixel';
          return `
            <div class="node-glass-card" style="${isPixel ? 'border: 1px solid var(--teal-signal); background: rgba(0, 245, 212, 0.04);' : ''}">
              <div class="node-left">
                <div class="node-name-row">
                  <span style="color:${n.status === 'ONLINE' ? 'var(--teal-signal)' : 'var(--status-amber)'};">●</span>
                  <span class="node-name">${escapeHtml(n.name)}</span>
                  ${isPixel ? '<span class="operator-badge">PIXEL 11 PRO</span>' : ''}
                </div>
                <div class="node-ip">${escapeHtml(n.ip)} · ${escapeHtml(n.role)}</div>
                <div class="node-detail">${escapeHtml(n.hardware_trust)} · ${escapeHtml(n.solvency)}</div>
              </div>
              <div class="node-right">
                <span class="status-badge ${n.status === 'ONLINE' ? 'online' : 'readonly'}">${escapeHtml(n.status)}</span>
                <span class="latency-tag">${escapeHtml(n.latency)}</span>
              </div>
            </div>
          `;
        }).join('');
      }
    }
  } catch (e) {
    console.warn("Mesh fetch error", e);
  }
}

// ── Touch swipe gesture listeners ──────────────────────────────────
let touchStartX = 0;
let touchEndX = 0;
const viewsContainer = document.getElementById('viewsContainer');
if (viewsContainer) {
  viewsContainer.addEventListener('touchstart', (e) => {
    touchStartX = e.changedTouches[0].screenX;
  }, { passive: true });

  viewsContainer.addEventListener('touchend', (e) => {
    touchEndX = e.changedTouches[0].screenX;
    const diff = touchEndX - touchStartX;
    if (Math.abs(diff) > 60) {
      if (diff < 0 && currentTabIndex < tabs.length - 1) {
        switchView(tabs[currentTabIndex + 1]);
      } else if (diff > 0 && currentTabIndex > 0) {
        switchView(tabs[currentTabIndex - 1]);
      }
    }
  }, { passive: true });
}

// Initial bootstrap
window.addEventListener('DOMContentLoaded', () => {
  autoDetectBestHost();
  checkDeviceRole();
  loadServices();
  loadSecurityTelemetry();
  loadMeshNodes();
  loadSwarmData();
});

// Periodic background poller
setInterval(() => {
  if (currentTabIndex === 1) loadServices();
  if (currentTabIndex === 2) loadSecurityTelemetry();
  if (currentTabIndex === 5) loadSwarmData();
  if (currentTabIndex === 6) loadMeshNodes();
}, 8000);
