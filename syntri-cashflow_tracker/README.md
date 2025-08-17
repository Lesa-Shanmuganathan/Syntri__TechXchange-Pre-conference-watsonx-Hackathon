# Cash‑Flow Reports

**Goal:** Deliver a **once‑a‑week** executive snapshot over WhatsApp: chart + narrative.

![Cash Flow Reports](../docs/CashFlow_Reports.png)

## What It Sends
- Line chart of cash in/out and net position
- KPIs: revenue, expenses, gross margin, MoM trend
- 4–6 sentence narrative (Granite‑8B), **actionable** and humble

## Scheduler
- Default: Sunday 18:00 local time via APScheduler

## Manual Trigger
```bash
curl -X POST http://localhost:8000/reports/run-weekly -H "Content-Type: application/json" -d '{"business_id":"acme-001"}'
```

## Storage
- Each report is stored in `reports` (or within `risk_events` as snapshots) with a link to the chart image.
