# QuantumFlex: Master n8n Automation Engine Setup & Workflow Guide

> **Architecture:** Zero-trust, local-first workflow orchestration connecting `n8n` to QuantumFlex Neural Vector RAG (Athena), Post-Quantum Crypto Policy (OPA), and Autonomous Agent Routing (Amara).

---

## I. Infrastructure Overview

```
                      ┌────────────────────────────────────────┐
                      │    N8N WORKFLOW AUTOMATION (Port 5678) │
                      └───────────────────┬────────────────────┘
                                          │
        ┌─────────────────────────────────┼─────────────────────────────────┐
        │                                 │                                 │
        ▼                                 ▼                                 ▼
┌──────────────────┐            ┌──────────────────┐              ┌──────────────────┐
│  ATHENA RAG API  │            │ OLLAMA LLM POOL  │              │   OPA SIDECAR    │
│  (127.0.0.1:8001)│            │ (127.0.0.1:11434)│              │ (127.0.0.1:8181) │
│  Vector Memory   │            │ Qwen2.5 / Athena │              │ PQC Gating       │
└──────────────────┘            └──────────────────┘              └──────────────────┘
```

---

## II. How to Launch n8n

### Option A: From QuantumFlex HUD Console
```powershell
python C:\Users\quant\.gemini\antigravity-ide\scratch\repos\mycelium\qflex.py n8n
```

### Option B: Direct PowerShell Launcher
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\quant\.gemini\antigravity-ide\scratch\repos\mycelium\Start-N8nNode.ps1
```

Once launched, navigate to:
👉 **`http://127.0.0.1:5678`**

---

## III. Pre-Wired Workflow Blueprints

The following workflow templates are located in [`mycelium/n8n_workflows/`](file:///C:/Users/quant/.gemini/antigravity-ide/scratch/repos/mycelium/n8n_workflows):

### 1. [`01_athena_rag_bridge.json`](file:///C:/Users/quant/.gemini/antigravity-ide/scratch/repos/mycelium/n8n_workflows/01_athena_rag_bridge.json)
- **Webhook Endpoint:** `POST http://127.0.0.1:5678/webhook/athena-ask`
- **Payload:** `{"question": "How does the immune daemon handle vein collapse?"}`
- **Action:** Queries Athena's 75 active vector chunks and returns synthesized tactical response via `athena:latest`.

### 2. [`02_autonomous_lead_triage.json`](file:///C:/Users/quant/.gemini/antigravity-ide/scratch/repos/mycelium/n8n_workflows/02_autonomous_lead_triage.json)
- **Webhook Endpoint:** `POST http://127.0.0.1:5678/webhook/lead-triage`
- **Payload:** `{"name": "Client", "email": "ceo@example.com", "budget": "$5,000", "message": "Need PQC migration assessment"}`
- **Action:** Local Qwen evaluates lead intent and routes high-ticket leads ($1k+) to VIP alert pipelines.

### 3. [`03_pqc_cbom_audit_pipeline.json`](file:///C:/Users/quant/.gemini/antigravity-ide/scratch/repos/mycelium/n8n_workflows/03_pqc_cbom_audit_pipeline.json)
- **Webhook Endpoint:** `POST http://127.0.0.1:5678/webhook/pqc-audit`
- **Action:** Passes CycloneDX CBOM to local OPA sidecar (`:8181`) and generates instant compliance remediation report.

---

## IV. Importing Workflows into n8n
1. Open `http://127.0.0.1:5678` in your browser.
2. Click **Workflows** $\rightarrow$ **Import from File...**
3. Select any `.json` file from `C:\Users\quant\.gemini\antigravity-ide\scratch\repos\mycelium\n8n_workflows`.
4. Click **Activate Workflow** (Toggle in top right corner).
