# Action Toolkit

**Goal:** Reduce “I’ll do it later” friction. Convert advice into a **one‑tap action**.

![SAMPLE OUTPUT](https://drive.google.com/uc?export=view&id=1kVBcueh-pcs_vA73iH9b6RBe05ZG2z-k)


## Supported Actions
- **Pay Now** — server‑generated UPI deep link
- **Send Reminder** — email/SMS to supplier/customer with template
- **Reorder Now** — vendor email with last PO summary

## Orchestration
- Granite classifies intent → `Action Orchestrator` routes to handler:
  - Payment Handler → UPI link generator
  - Reminder Service → SMTP send + receipt
  - Reorder Manager → compose vendor email

## API
- `GET /tasks/pending?business_id=...`
- `POST /actions/confirm`

**Confirm example**
```bash
curl -X POST http://localhost:8000/actions/confirm -H "Content-Type: application/json" -d '{"business_id":"acme-001","action_id":"act_9241","confirm":true}'
```

## Reliability
- Idempotent action IDs, at‑least‑once delivery, and explicit acknowledgements.
