/**
 * Quantum Flex // Mobile Tactical Console Engine
 */

const API_BASE = window.location.origin;

let selectedBot = "";
let isSending = false;
let notificationsArmed = false;
let lastKnownDraftCount = 0;

// ── DOM References ────────────────────────────────────────────────────────────
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const targetBotSelect = document.getElementById("targetBotSelect");
const teammatesContainer = document.getElementById("teammatesContainer");
const draftsFeed = document.getElementById("draftsFeed");
const draftsFeedMobile = document.getElementById("draftsFeedMobile");
const draftsCountBadge = document.getElementById("draftsCountBadge");
const tabAuthBadge = document.getElementById("tabAuthBadge");
const authTabCountBadge = document.getElementById("authTabCountBadge");
const activityFeed = document.getElementById("activityFeed");
const btnArmAlerts = document.getElementById("btnArmAlerts");
const armAlertsText = document.getElementById("armAlertsText");

// Header Telemetry Elements
const valDrive = document.getElementById("valDrive");
const valTpm = document.getElementById("valTpm");
const valPqc = document.getElementById("valPqc");

// Dedicated Vitals Tab Elements
const vitalsDriveVal = document.getElementById("vitalsDriveVal");
const vitalsDriveStatus = document.getElementById("vitalsDriveStatus");
const vitalsTpmVal = document.getElementById("vitalsTpmVal");
const vitalsTpmStatus = document.getElementById("vitalsTpmStatus");
const vitalsPqcVal = document.getElementById("vitalsPqcVal");
const vitalsOpaStatus = document.getElementById("vitalsOpaStatus");
const vitalsLoadVal = document.getElementById("vitalsLoadVal");
const vitalsMemVal = document.getElementById("vitalsMemVal");

// ── Initialization ───────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  loadTeammates();
  loadStatus();
  loadDrafts();

  // Polling cadences
  setInterval(loadStatus, 8000);
  setInterval(loadDrafts, 6000);

  // Auto-resize chat input
  chatInput.addEventListener("input", function() {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 120) + "px";
  });

  // Enter to send
  chatInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  chatForm.addEventListener("submit", handleSendMessage);

  targetBotSelect.addEventListener("change", (e) => {
    selectedBot = e.target.value;
    updateActiveSidebarCard();
  });

  btnArmAlerts.addEventListener("click", toggleArmAlerts);

  // Check existing notification permission
  if ("Notification" in window && Notification.permission === "granted") {
    setAlertsArmedState(true);
  }
});

// ── Mobile Tab Navigation ─────────────────────────────────────────────────────
function setupTabs() {
  const tabs = document.querySelectorAll(".mobile-tabs-bar .tab-btn");
  const views = {
    chat: document.getElementById("viewChat"),
    telemetry: document.getElementById("viewTelemetry"),
    authorizations: document.getElementById("viewAuthorizations"),
    sweeps: document.getElementById("viewSweeps"),
  };

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      Object.keys(views).forEach(k => {
        if (k === target) {
          views[k].style.display = (k === "chat") ? "flex" : "block";
        } else {
          views[k].style.display = "none";
        }
      });

      if (target === "chat") {
        scrollToBottom();
      }

      // Haptic feedback on mobile if supported
      if (navigator.vibrate) {
        navigator.vibrate(15);
      }
    });
  });
}

// ── Notifications System (Phone Alerts) ───────────────────────────────────────
async function toggleArmAlerts() {
  if (!("Notification" in window)) {
    alert("Web notifications not supported on this browser.");
    return;
  }

  if (Notification.permission === "granted") {
    notificationsArmed = !notificationsArmed;
    setAlertsArmedState(notificationsArmed);
    if (notificationsArmed) {
      dispatchNotification("ALERTS ARMED", "Quantum Flex tactical notifications active on this device.");
    }
    return;
  }

  const perm = await Notification.requestPermission();
  if (perm === "granted") {
    setAlertsArmedState(true);
    dispatchNotification("TACTICAL ALERTS ARMED", "Your phone will receive alerts for perimeter threats and authorization requests.");
  } else {
    alert("Notification permission denied.");
  }
}

function setAlertsArmedState(armed) {
  notificationsArmed = armed;
  if (armed) {
    btnArmAlerts.classList.add("armed");
    armAlertsText.textContent = "ALERTS ARMED";
  } else {
    btnArmAlerts.classList.remove("armed");
    armAlertsText.textContent = "ARM ALERTS";
  }
}

function dispatchNotification(title, body) {
  if (navigator.vibrate) {
    navigator.vibrate([100, 50, 100]);
  }

  if ("Notification" in window && Notification.permission === "granted") {
    try {
      new Notification(`[QF-TACTICAL] ${title}`, {
        body: body,
        icon: "icon.svg",
        tag: "qf-tactical-alert",
      });
    } catch (e) {
      console.warn("Notification error:", e);
    }
  }
}

// ── Load Tactical Units ───────────────────────────────────────────────────────
async function loadTeammates() {
  try {
    const res = await fetch(`${API_BASE}/api/teammates`);
    const data = await res.json();
    if (!data.roster) return;

    let html = `
      <div class="teammate-card ${selectedBot === "" ? "active" : ""}" data-bot="" onclick="selectTeammate('')">
        <div class="teammate-avatar">⬡</div>
        <div class="teammate-info">
          <div class="teammate-name">SWARM COORDINATION</div>
          <div class="teammate-role">Autonomous Multi-Unit Dispatch</div>
        </div>
        <div class="teammate-status-dot online"></div>
      </div>
    `;

    data.roster.forEach(t => {
      const isSelected = selectedBot === t.callsign;
      html += `
        <div class="teammate-card ${isSelected ? "active" : ""}" data-bot="${t.callsign}" onclick="selectTeammate('${t.callsign}')">
          <div class="teammate-avatar">${t.avatar}</div>
          <div class="teammate-info">
            <div class="teammate-name">${t.name}</div>
            <div class="teammate-role">${t.role}</div>
          </div>
          <div class="teammate-status-dot online"></div>
        </div>
      `;
    });

    teammatesContainer.innerHTML = html;
  } catch (err) {
    console.error("Failed to load tactical units:", err);
  }
}

function selectTeammate(callsign) {
  selectedBot = callsign;
  targetBotSelect.value = callsign;
  updateActiveSidebarCard();
  chatInput.focus();
}

function updateActiveSidebarCard() {
  const cards = document.querySelectorAll(".teammate-card");
  cards.forEach(c => {
    if (c.getAttribute("data-bot") === selectedBot) {
      c.classList.add("active");
    } else {
      c.classList.remove("active");
    }
  });

  const badge = document.getElementById("activeFilterBadge");
  badge.textContent = selectedBot ? `@${selectedBot.toUpperCase()}` : "Swarm Coordination";
}

// ── Live Status & Telemetry ──────────────────────────────────────────────────
async function loadStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    const data = await res.json();

    if (data.sentinel && data.sentinel.drive_score !== undefined) {
      const score = Number(data.sentinel.drive_score).toFixed(1);
      const status = data.sentinel.drive_status || "OPTIMAL";
      valDrive.textContent = `${score} ${status}`;
      vitalsDriveVal.textContent = score;
      vitalsDriveStatus.textContent = `${status} (TOLERANCE: NOMINAL)`;

      const tpmOk = data.sentinel.tpm_anchor_matched;
      const tpmDisp = tpmOk ? "0x1c00010 MATCHED" : "UNREAD / DISCONNECTED";
      valTpm.textContent = tpmDisp;
      vitalsTpmStatus.textContent = tpmOk ? "MATCHED TO LEDGER TIP" : "TPM UNREAD";

      if (data.sentinel.cpu_usage !== undefined) {
        vitalsLoadVal.textContent = `${data.sentinel.cpu_usage.toFixed(1)}% CPU`;
      }
      if (data.sentinel.mem_usage !== undefined) {
        vitalsMemVal.textContent = `${data.sentinel.mem_usage.toFixed(1)} MB RAM`;
      }
    }

    if (data.immune && data.immune.active_kem) {
      valPqc.textContent = data.immune.active_kem;
      vitalsPqcVal.textContent = data.immune.active_kem;
      vitalsOpaStatus.textContent = `OPA: ${data.immune.opa_verdict || 'COMPLIANT'}`;
    }
  } catch (err) {
    console.warn("Status fetch warning:", err);
  }
}

// ── Action Authorizations (Two-Man Rule) ─────────────────────────────────────
async function loadDrafts() {
  try {
    const res = await fetch(`${API_BASE}/api/drafts`);
    const data = await res.json();
    const drafts = data.drafts || [];

    const pending = drafts.filter(d => d.status === "PENDING_APPROVAL");
    draftsCountBadge.textContent = pending.length;
    tabAuthBadge.textContent = pending.length;
    authTabCountBadge.textContent = `${pending.length} ACTION(S) REQUIRED`;

    // Fire notification if new authorization appeared
    if (pending.length > lastKnownDraftCount && notificationsArmed) {
      const newest = pending[pending.length - 1];
      dispatchNotification("ACTION AUTHORIZATION REQUIRED", `[${newest.draft_id}] ${newest.title}`);
    }
    lastKnownDraftCount = pending.length;

    if (pending.length === 0) {
      const emptyHtml = `<div class="empty-state">No pending actions requiring authorization.</div>`;
      draftsFeed.innerHTML = emptyHtml;
      draftsFeedMobile.innerHTML = emptyHtml;
      return;
    }

    let html = "";
    pending.forEach(d => {
      html += `
        <div class="draft-card" id="draft-item-${d.draft_id}">
          <div class="draft-header">
            <span class="draft-badge-tag">${escapeHtml(d.risk_level)}</span>
            <span class="draft-time">${d.draft_id}</span>
          </div>
          <div class="draft-title">${escapeHtml(d.title)}</div>
          <div class="draft-details">${escapeHtml(d.description)}</div>
          <div class="draft-actions-bar">
            <button class="btn btn-xs btn-primary" onclick="approveDraft('${d.draft_id}')">AUTHORIZE EXECUTION</button>
            <button class="btn btn-xs btn-outline" onclick="discardDraft('${d.draft_id}')">ABORT</button>
          </div>
        </div>
      `;
    });

    draftsFeed.innerHTML = html;
    draftsFeedMobile.innerHTML = html;
  } catch (err) {
    console.warn("Drafts fetch failed:", err);
  }
}

async function approveDraft(draftId) {
  try {
    addActivityLog("CHIEF ARCHITECT", `Authorized staged action [${draftId}]`);
    const res = await fetch(`${API_BASE}/api/drafts/${draftId}/approve`, { method: "POST" });
    const data = await res.json();
    if (data.status === "EXECUTED") {
      alert(`✓ Action [${draftId}] Authorized & Executed!\nResult: ${data.result}`);
      loadDrafts();
    } else {
      alert(`Execution fault: ${data.error || data.result}`);
    }
  } catch (err) {
    alert(`Authorization failed: ${err.message}`);
  }
}

async function discardDraft(draftId) {
  try {
    addActivityLog("CHIEF ARCHITECT", `Aborted staged action [${draftId}]`);
    await fetch(`${API_BASE}/api/drafts/${draftId}/discard`, { method: "POST" });
    loadDrafts();
  } catch (err) {
    alert(`Abort failed: ${err.message}`);
  }
}

// ── Messaging & Directives ───────────────────────────────────────────────────
async function handleSendMessage(e) {
  e.preventDefault();
  if (isSending) return;

  const text = chatInput.value.trim();
  if (!text) return;

  appendUserMessage(text);
  chatInput.value = "";
  chatInput.style.height = "44px";
  isSending = true;

  const typingId = showTypingIndicator();

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, target_bot: selectedBot || null })
    });

    removeTypingIndicator(typingId);
    const data = await res.json();

    if (data.error) {
      appendBotMessage({
        avatar: "⚠️",
        name: "GATEWAY FAULT",
        callsign: "system",
        role: "Fault Gateway",
        text: `Error processing directive: ${data.error}`
      });
      return;
    }

    appendBotMessage({
      avatar: data.bot.avatar,
      name: data.bot.name,
      callsign: data.bot.callsign,
      role: data.bot.role,
      text: data.response,
      handoffs: data.handoffs,
      staged_draft: data.staged_draft
    });

    if (data.staged_draft) {
      loadDrafts();
    }

  } catch (err) {
    removeTypingIndicator(typingId);
    appendBotMessage({
      avatar: "⚠️",
      name: "SUBSTRATE UNREACHABLE",
      callsign: "system",
      role: "Network Fault",
      text: `Failed to transmit directive to Yoga host: ${err.message}`
    });
  } finally {
    isSending = false;
  }
}

function sendPrompt(text) {
  // If not on chat tab, switch to it
  const chatTab = document.querySelector(".mobile-tabs-bar .tab-btn[data-tab='chat']");
  if (chatTab) chatTab.click();

  chatInput.value = text;
  chatForm.dispatchEvent(new Event("submit"));
}

// ── Render Messages ──────────────────────────────────────────────────────────
function appendUserMessage(text) {
  const msgEl = document.createElement("div");
  msgEl.className = "chat-message user-msg";
  msgEl.innerHTML = `
    <div class="msg-avatar">⚡</div>
    <div class="msg-body">
      <div class="msg-meta">
        <span class="msg-sender">Chief Architect (You)</span>
        <span class="msg-time">${getCurrentTime()}</span>
      </div>
      <div class="msg-content">
        <p>${escapeHtml(text)}</p>
      </div>
    </div>
  `;
  chatMessages.appendChild(msgEl);
  scrollToBottom();
}

function appendBotMessage(data) {
  const msgEl = document.createElement("div");
  msgEl.className = "chat-message bot-msg";

  let handoffHtml = "";
  if (data.handoffs && data.handoffs.length > 0) {
    data.handoffs.forEach(h => {
      handoffHtml += `
        <div class="handoff-chip">
          <span>⚡ [${h.from.toUpperCase()} ➔ ${h.to.toUpperCase()}]:</span>
          <span>${escapeHtml(h.action)}</span>
        </div>
      `;
    });
  }

  let draftHtml = "";
  if (data.staged_draft) {
    const d = data.staged_draft;
    draftHtml = `
      <div class="draft-card">
        <div class="draft-header">
          <span class="draft-badge-tag">${escapeHtml(d.risk_level)}</span>
          <span class="draft-time">${d.draft_id}</span>
        </div>
        <div class="draft-title">${escapeHtml(d.title)}</div>
        <div class="draft-details">${escapeHtml(d.description)}</div>
        <div class="draft-actions-bar">
          <button class="btn btn-xs btn-primary" onclick="approveDraft('${d.draft_id}')">AUTHORIZE EXECUTION</button>
          <button class="btn btn-xs btn-outline" onclick="discardDraft('${d.draft_id}')">ABORT</button>
        </div>
      </div>
    `;
  }

  msgEl.innerHTML = `
    <div class="msg-avatar">${data.avatar || "⬡"}</div>
    <div class="msg-body">
      <div class="msg-meta">
        <span class="msg-sender">${escapeHtml(data.name || "UNIT")}</span>
        <span class="msg-callsign">@${escapeHtml(data.callsign || "swarm")}</span>
        <span class="msg-badge">${escapeHtml(data.role || "Specialist")}</span>
        <span class="msg-time">${getCurrentTime()}</span>
      </div>
      ${handoffHtml}
      <div class="msg-content">
        ${formatMarkdown(data.text)}
      </div>
      ${draftHtml}
    </div>
  `;

  chatMessages.appendChild(msgEl);
  scrollToBottom();
}

function showTypingIndicator() {
  const id = "typing-" + Date.now();
  const el = document.createElement("div");
  el.id = id;
  el.className = "chat-message bot-msg";
  el.innerHTML = `
    <div class="msg-avatar">⬡</div>
    <div class="msg-body" style="padding: 10px 14px;">
      <div class="msg-meta">
        <span class="msg-sender">Quantum Flex Swarm</span>
        <span class="msg-callsign">executing...</span>
      </div>
      <div style="color: var(--text-muted); font-size: 11px; font-family: var(--font-mono);">
        Querying bare-metal telemetry & evaluating neural model...
      </div>
    </div>
  `;
  chatMessages.appendChild(el);
  scrollToBottom();
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ── Tactical Sweeps & Routines ───────────────────────────────────────────────
async function runRoutine(routineId) {
  appendUserMessage(`Trigger Tactical Sweep: ${routineId.toUpperCase()}`);
  const typingId = showTypingIndicator();

  try {
    const res = await fetch(`${API_BASE}/api/routines/${routineId}/run`, { method: "POST" });
    removeTypingIndicator(typingId);
    const data = await res.json();

    if (routineId === "overnight_audit") {
      appendBotMessage({
        avatar: "🌙",
        name: "DEEP AUDIT ENGINE",
        callsign: "routine",
        role: "Multi-Subsystem Sweep",
        text: `**Deep Audit Complete in ${data.duration_sec?.toFixed(1)}s**\n\n${data.debrief || "Verification succeeded across all substrates."}`
      });
      addActivityLog("AUDIT SWEEP", `Completed in ${data.duration_sec?.toFixed(1)}s`);
    } else {
      appendBotMessage({
        avatar: "▲",
        name: "SENTINEL",
        callsign: "sentinel",
        role: "Perimeter Heartbeat",
        text: `**Drive Metric (D):** ${data.data?.drive_score} (${data.data?.drive_status})\n**TPM 2.0 Anchor Verified:** ${data.data?.tpm_anchor_matched ? "YES (NV 0x1c00010 matched)" : "NO"}`
      });
      addActivityLog("SENTINEL", `Heartbeat verified: Drive score ${data.data?.drive_score}`);
    }
    loadStatus();
  } catch (err) {
    removeTypingIndicator(typingId);
    alert(`Sweep execution failed: ${err.message}`);
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function getCurrentTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function formatMarkdown(text) {
  if (!text) return "";
  let out = escapeHtml(text);
  // Bold
  out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Newlines to paragraphs
  out = out.split('\n\n').map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
  return out;
}

function addActivityLog(bot, msg) {
  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.innerHTML = `
    <span class="log-time">${getCurrentTime()}</span>
    <span class="log-bot">${escapeHtml(bot)}</span>
    <span class="log-msg">${escapeHtml(msg)}</span>
  `;
  activityFeed.prepend(entry);
}
