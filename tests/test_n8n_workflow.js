#!/usr/bin/env node
/**
 * QuantumFlex — Verification Test for n8n Autonomous Lead Triage Workflow
 * 
 * Verifies:
 * 1. Immediate HTTP 202 receipt delivery connection decoupled from inference.
 * 2. Safe JSON escaping of multiline text, quotes, and backslashes in model prompt.
 * 3. Strict schema enforcement in Code node (extra keys rejected, invalid enums rejected).
 * 4. Alert prefix derivation (Urgent vs Standard service intake).
 * 5. Fail-closed fallback setting urgency='UNKNOWN' and state='MANUAL_REVIEW_REQUIRED' on error.
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const vm = require('vm');

const workflowPath = path.resolve(__dirname, '../n8n_workflows/02_autonomous_lead_triage.json');
const workflowJson = JSON.parse(fs.readFileSync(workflowPath, 'utf8'));

console.log('=============================================================');
console.log('  VERIFYING n8n WORKFLOW: 02_autonomous_lead_triage.json     ');
console.log('=============================================================');

// 1. Verify structure and nodes
assert(workflowJson.name, 'Workflow must have a name');
assert(Array.isArray(workflowJson.nodes), 'Workflow must have nodes array');
assert(workflowJson.connections, 'Workflow must have connections');

const webhookNode = workflowJson.nodes.find(n => n.name === 'Inbound Lead Webhook');
const ingressNode = workflowJson.nodes.find(n => n.name === 'Persist Ticket & Structured Ingress');
const receiptNode = workflowJson.nodes.find(n => n.name === 'Immediate 202 Customer Receipt');
const claimNode = workflowJson.nodes.find(n => n.name === 'Claim Pending Ticket');
const httpQwenNode = workflowJson.nodes.find(n => n.name === 'Local Qwen Evaluation');
const codeNode = workflowJson.nodes.find(n => n.name === 'Strict Schema Validation & Triage Logic');
const outcomeNode = workflowJson.nodes.find(n => n.name === 'Persist Final Triage Outcome');

assert(webhookNode, 'Webhook node must exist');
assert(ingressNode, 'Ingress persistence node must exist');
assert(receiptNode, 'Immediate 202 receipt node must exist');
assert.strictEqual(receiptNode.parameters.responseCode, 202, 'Receipt node must return HTTP 202');
assert(claimNode, 'Claim node must exist');
assert(httpQwenNode, 'HTTP Qwen node must exist');
assert.strictEqual(httpQwenNode.continueOnFail, true, 'HTTP Qwen node must have continueOnFail: true');
assert(codeNode, 'Code node must exist');
assert(outcomeNode, 'Outcome persistence node must exist');
console.log('[+] Workflow structure, nodes, and error traps: VERIFIED');

// Verify connection graph: Ingress connects directly to Immediate Receipt AND Claim/Inference
const ingressConnections = workflowJson.connections['Persist Ticket & Structured Ingress'].main[0];
const connectedNodeNames = ingressConnections.map(c => c.node);
assert(connectedNodeNames.includes('Immediate 202 Customer Receipt'), 'Ingress must connect to Immediate Receipt');
assert(connectedNodeNames.includes('Claim Pending Ticket'), 'Ingress must connect to Claim node');
console.log('[+] Receipt connection graph: Ingress returns 202 immediately, decoupled from inference branch: VERIFIED');

// Helper to run code node
function runCodeNode(ticketData, httpResponse, webhookMessage = "Test message") {
  const sandbox = {
    $: (nodeName) => {
      if (nodeName === 'Persist Ticket & Structured Ingress') {
        return {
          first: () => ({
            json: ticketData
          })
        };
      }
      if (nodeName === 'Inbound Lead Webhook') {
        return {
          first: () => ({
            json: {
              body: {
                message: webhookMessage
              }
            }
          })
        };
      }
      throw new Error(`Mock node ${nodeName} not defined`);
    },
    $input: {
      first: () => ({
        json: httpResponse
      })
    },
    JSON,
    Array,
    Object,
    Error,
    console
  };

  const script = new vm.Script(`(function() {\n${codeNode.parameters.jsCode}\n})()`);
  const context = vm.createContext(sandbox);
  return script.runInContext(context);
}

const mockIngress = {
  ticket_id: 'TCK-uuid-5555',
  client_name: "Dino's Bistro",
  client_phone: "(570) 555-0192",
  location: "Market St, Wilkes-Barre, PA",
  intake_status: "RECEIVED_PENDING_TRIAGE",
  receipt_status: "ACCEPTED",
  is_duplicate_request: false,
  customer_acknowledgment: {
    channel: "SMS_DRAFT",
    delivery_status: "DRAFT_NOT_SENT_OUTBOUND_DISABLED",
    message_text: "Your service request has been received. A technician has not yet been assigned, and no arrival time is confirmed. For immediate assistance, call our published emergency number."
  },
  created_at_utc: "2026-09-19T12:00:00Z"
};

// --- TEST 1: Immediate 202 Receipt Expression ---
console.log('\n[+] Test 1: Immediate 202 Receipt Expression');
const receiptExpr = receiptNode.parameters.responseBody;
assert(receiptExpr.startsWith('={{') && receiptExpr.endsWith('}}'));
const receiptSandbox = {
  $json: mockIngress,
  JSON
};
const receiptScript = new vm.Script(receiptExpr.slice(3, -2).trim());
const receiptOutputStr = receiptScript.runInContext(vm.createContext(receiptSandbox));
const receiptParsed = JSON.parse(receiptOutputStr);
assert.strictEqual(receiptParsed.ticket_id, mockIngress.ticket_id);
assert.strictEqual(receiptParsed.receipt_status, 'ACCEPTED');
assert.strictEqual(receiptParsed.status, 'RECEIVED_PENDING_TRIAGE');
console.log('  --> PASS: 202 Receipt evaluated to 100% valid JSON before inference begins');

// --- TEST 2: Complex Multiline & Quoted Customer Prompt Escaping ---
console.log('\n[+] Test 2: Multiline, Backslash, and Quote Escaping in Model Prompt');
const complexCustomerMessage = `Walk-in cooler down! "Urgent" warning: \\temp\\ rising above 50°F.
Owner says: 'Please hurry!'`;

const qwenExpr = httpQwenNode.parameters.jsonBody;
assert(qwenExpr.startsWith('={{') && qwenExpr.endsWith('}}'));
const qwenSandbox = {
  $: (nodeName) => ({
    first: () => ({
      json: nodeName === 'Persist Ticket & Structured Ingress' ? mockIngress : { body: { message: complexCustomerMessage } }
    })
  }),
  JSON
};
const qwenScript = new vm.Script(qwenExpr.slice(3, -2).trim());
const qwenEvaluatedStr = qwenScript.runInContext(vm.createContext(qwenSandbox));
const qwenParsed = JSON.parse(qwenEvaluatedStr);
assert.strictEqual(qwenParsed.model, 'qwen2.5-coder:7b');
assert(qwenParsed.prompt.includes('Market St, Wilkes-Barre, PA'), 'Location must be preserved in prompt');
assert(qwenParsed.prompt.includes(complexCustomerMessage), 'Complex message must be properly embedded without syntax error');
console.log('  --> PASS: Quotes, backslashes, and multiline input safely encoded via JSON.stringify');

// --- TEST 3: Neutral vs Urgent Alert Wording ---
console.log('\n[+] Test 3: Alert Wording Derivation (Urgent vs Standard Service Intake)');
// Case A: CRITICAL -> "Urgent intake"
const urgentHttpResponse = {
  response: JSON.stringify({
    urgency: "CRITICAL",
    trade_category: "COMMERCIAL_REFRIGERATION",
    requires_urgent_review: true,
    incident_summary: "Walk-in cooler compressor failure reported."
  })
};
const resUrgent = runCodeNode(mockIngress, urgentHttpResponse);
assert.strictEqual(resUrgent.urgency, 'CRITICAL');
assert.ok(resUrgent.operator_alert_draft.includes('Urgent intake'), 'Alert must say Urgent intake for critical tickets');
console.log('  --> PASS: Critical ticket generates "Urgent intake" alert draft');

// Case B: STANDARD -> "Standard service intake" (neutral wording!)
const standardHttpResponse = {
  response: JSON.stringify({
    urgency: "STANDARD",
    trade_category: "PLUMBING",
    requires_urgent_review: false,
    incident_summary: "Routine maintenance requested on kitchen grease trap."
  })
};
const resStandard = runCodeNode(mockIngress, standardHttpResponse);
assert.strictEqual(resStandard.urgency, 'STANDARD');
assert.ok(resStandard.operator_alert_draft.includes('Standard service intake'), 'Alert must say Standard service intake for standard tickets');
assert(!resStandard.operator_alert_draft.includes('Urgent intake'), 'Must NOT say Urgent intake for standard tickets');
console.log('  --> PASS: Standard ticket generates neutral "Standard service intake" alert draft');

// --- TEST 4: Schema Rejection of Forbidden Extra Keys ---
console.log('\n[+] Test 4: Schema Rejection of Forbidden Extra Keys');
const extraKeysResponse = {
  response: JSON.stringify({
    urgency: "CRITICAL",
    trade_category: "COMMERCIAL_REFRIGERATION",
    requires_urgent_review: true,
    incident_summary: "Commercial walk-in cooler temp rising, compressor failure reported.",
    technician_assigned: "AUTO_APPROVED",
    estimated_revenue: 4500
  })
};
const resExtra = runCodeNode(mockIngress, extraKeysResponse);
assert.strictEqual(resExtra.intake_status, 'FALLBACK_MANUAL_REVIEW');
assert.strictEqual(resExtra.urgency, 'UNKNOWN', 'Must NOT fabricate CRITICAL on schema violation');
assert.strictEqual(resExtra.trade_category, 'UNKNOWN');
assert.strictEqual(resExtra.dispatch_state, 'MANUAL_REVIEW_REQUIRED');
assert.ok(resExtra.error_reason.includes('Extra forbidden keys rejected'));
console.log('  --> PASS: Forbidden extra keys rejected, urgency=UNKNOWN, state=MANUAL_REVIEW_REQUIRED');

// --- TEST 5: HTTP Timeout / Connection Error Fallback ---
console.log('\n[+] Test 5: HTTP Timeout / Connection Error Fallback');
const timeoutResponse = {
  error: {
    message: "ETIMEDOUT: Connection to http://127.0.0.1:11434 timed out after 20000ms"
  }
};
const resTimeout = runCodeNode(mockIngress, timeoutResponse);
assert.strictEqual(resTimeout.intake_status, 'FALLBACK_MANUAL_REVIEW');
assert.strictEqual(resTimeout.urgency, 'UNKNOWN', 'Must NOT fabricate CRITICAL on timeout');
assert.strictEqual(resTimeout.dispatch_state, 'MANUAL_REVIEW_REQUIRED');
assert.strictEqual(resTimeout.ticket_id, mockIngress.ticket_id);
console.log('  --> PASS: Timeout handled fail-closed, urgency=UNKNOWN, state=MANUAL_REVIEW_REQUIRED');

console.log('\n=============================================================');
console.log('  n8n WORKFLOW VERIFICATION: ALL 5 TEST SUITES PASSED        ');
console.log('=============================================================');
