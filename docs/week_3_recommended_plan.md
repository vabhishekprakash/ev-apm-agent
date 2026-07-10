1. Rename and reframe.

"Alert" → "Maintenance Recommendation" in UI headers and deck
"Priority tier" → "Maintenance Priority"
Overall system tagline: "AI Maintenance Decision Support for EV Charging Infrastructure"
Keep every number, every detector, every metric — just relabel the surface

2. Add three fields to every alert payload:

confidence (Layer 1 = 100; Layer 2 = normalized IsoForest score)
likely_root_cause (static lookup by category or dominant drift feature)
recommended_action (static lookup: "Dispatch technician" / "Schedule inspection within 7 days" / "Monitor next 3 sessions" / "Log and review")
impact_class (Revenue-impacting / Safety-flagged / Non-revenue transient)

3. Add a per-connector health rollup.

New UI panel or column: connector → health state (Healthy / Degrading / At-risk / Faulted)
Health state is derived from recent Layer 2 drift trajectory + presence of unresolved Layer 1 alerts
Rule table, not a model

## WHY?
- It reframes the system as decision-support without inventing capabilities the data can't support.