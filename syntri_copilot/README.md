# Conversational Copilot

**Goal:** Let owners ask questions in plain language and upload receipts/invoices via WhatsApp.

![Conversational Copilot](../docs/Conversational_Copilot.png)

## Capabilities
- NL → SQL‑like aggregation over MongoDB (grounded answers)
- Media OCR (pytesseract) → structured JSON → stored
- Forecast questions route to the forecaster with deterministic output
- Granite‑8B produces concise, **cited** responses

## WhatsApp Flow (Example)
1. User: *"How am I doing this week?"*  
2. System: runs `aggregate(revenue, cost, profit)` last 7 days → replies with KPIs + sparkline link  
3. User uploads photo of a supplier invoice → OCR → confirmation summary

## Endpoints
- `POST /webhooks/whatsapp` — text + media entrypoint
- `POST /query` — programmatic NL query
- `POST /ingest/receipt` — explicit media ingest

**Example: NL query**
```bash
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"business_id":"acme-001","question":"profit last week vs previous?"}'
```

## Notes
- For OCR accuracy on mobile photos, auto‑deskew + grayscale are enabled.
- Each answer includes the **aggregation pipeline** used for transparency.
