# Predictive Advisory Loop

**Goal:** Detect risks proactively and help the owner act before a cash dip hurts operations and provides personalized actions which can be performed.

![Predictive Advisory Loop](../docs/Predictive_Advisory_Loop.png)

## Agent Design
- **Planner** (Granite‑13B‑instruct‑v2): decides if a dip/anomaly warrants action and drafts the alert.
- **Tools**:
  - `forecast_tool` → Prophet daily forecast on `financial_records`
  - `rules_tool` → maps signals to **preferred actions**
  - `impact_tool` → simulate action impact (counterfactual forecast)
  - `notify_tool` → Twilio WhatsApp message with buttons
  - `log_tool` → persist `risk_events` and `action_tasks`

## Inputs → Outputs
- **Input**: past 90–180 days of cash in/out; thresholds (config)
- **Output**: WhatsApp alert with 1–3 recommended actions + forecast on selected action


## Troubleshooting
- “No dip detected” → verify enough history; reduce threshold.
- Twilio 500 → check inbound signature + ngrok URL freshness.
