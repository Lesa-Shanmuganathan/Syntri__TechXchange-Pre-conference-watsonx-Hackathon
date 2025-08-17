# Syntri — Agentic AI Business Intelligence Service for SMBs

Syntri is a **WhatsApp‑native business intelligence copilot** that uses **agentic AI** (IBM watsonx.ai Granite) to forecast cash flow, surface risks, and execute actions (UPI payment links, supplier reminders, reorders) directly from chat.

[**Powered by IBM WATSONX.AI**]
---

# Why Syntri
- SMBs often fail not due to lack of effort, but due to **late insights** and **no execution loop**.
- Most owners already live in **WhatsApp**; Syntri brings **BI + actions** to where they are.
- Built for **low‑friction adoption**: photograph receipts, ask questions in plain language, and get **do‑or‑delegate** buttons.

---

# Core Capabilities
1. **Conversational Copilot** — Ask “How am I doing this week?”, upload receipts/invoices; get answers grounded in your own data.
2. **Predictive Advisory Loop** — Daily forecasting detects dips and proposes **preferred actions** with simulated impact before confirmation.
3. **Cash‑Flow Reports** — Weekly KPI roll‑ups with a chart + concise narrative, delivered automatically.
4. **Action Toolkit** — One‑tap UPI “Pay now”, “Send reminder”, “Reorder now”. Tasks are created, tracked, and closed in chat.

---

# Architecture (High‑Level)
- **Agent Orchestrator**: Granite (watsonx.ai) plans, calls tools, and explains outcomes.
- **Tools**: Prophet forecaster, MongoDB aggregate/query, OCR (pytesseract), Action executors (UPI, Email), Notifier (Twilio WhatsApp).
- **Schedulers**: APScheduler jobs for **daily advisory** and **weekly reports**.


---

# Tech Stack
- **Backend**: FastAPI microservices (plus a lightweight Flask webhook option)
- **AI**: IBM watsonx.ai Granite (13B‑instruct‑v2 / 3‑3‑8B‑instruct where appropriate)
- **Forecasting**: Prophet (deterministic projection)
- **Messaging**: Twilio WhatsApp API
- **OCR**: pytesseract
- **Database**: MongoDB
- **Scheduling**: APScheduler

---

# Note
- **Agentic loop**: detect → explain → propose → simulate → **execute** → learn.
- **Grounding**: every answer cites the underlying query/aggregation.
- **Practicality**: designed for WhatsApp; no new app to learn.
- **Extensible**: plug‑in connectors for POS, banks, and accounting suites.
---
## API Surface (selected)
- `POST /webhooks/whatsapp` — Twilio inbound handler
- `POST /ingest/receipt` — upload or reference media for OCR
- `POST /query` — NL to data; returns grounded answer + sources
- `POST /advisory/run-daily` — force run detector for a tenant
- `POST /reports/run-weekly` — force run weekly cash‑flow report
- `POST /actions/confirm` — confirm an action proposal
- `GET  /tasks/pending` — list pending actions for WhatsApp menu

**Example: confirm action**
```json
{
  "business_id": "acme-001",
  "action_id": "act_9241",
  "confirm": true,
  "channel": "whatsapp"
}
```

## Data Model (simplified)
```jsonc
// financial_records
{
  "_id": "...", "business_id": "acme-001",
  "ts": "2025-08-15T10:12:03Z",
  "type": "inflow|outflow",
  "amount": 12500.00,
  "counterparty": "supplier|customer",
  "source": "ocr|manual|pos|bank",
  "meta": {"invoice_no": "INV-102", "category": "inventory"}
}

// risk_events
{
  "_id": "...", "business_id": "acme-001",
  "date": "2025-08-16", "signal": "cash_dip",
  "score": 0.83, "snapshot": {}, "suggested_actions": [ ... ]
}

// action_tasks
{
  "_id": "act_9241", "business_id": "acme-001",
  "kind": "payment|reorder|reminder",
  "payload": {}, "status": "open|sent|confirmed|done",
  "created_at": "...", "updated_at": "..."
}

// conversations
{ "business_id": "acme-001", "role": "user|assistant", "text": "...", "msg_id": "...", "ts": "..." }

// media_inputs
{ "business_id": "acme-001", "url": "...", "ocr_text": "...", "json": {} }


---


# Team
**Team Syntri** — IBM TechXchange 2025 Pre‑conference watsonx Hackathon  
- Lesa Shanmuganathan
- Indhuja I

---

# License
MIT © Team Syntri
