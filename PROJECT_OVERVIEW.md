# AIOps Sentinel: AI-Driven IT System Observability

> **Tagline:** From alert noise to actionable insight, powered by AI.

---

## Project Summary

AIOps Sentinel is an AI intelligence layer that sits above existing monitoring infrastructure (Grafana, Prometheus) and transforms raw telemetry into actionable intelligence. Instead of replacing static alerting, it ingests simulated metrics and logs, applies ML-based anomaly detection and pattern correlation, groups related signals into unified incidents, and uses a Groq-hosted LLM (free tier) to generate natural-language summaries, probable root causes, and recommended next actions — all surfaced in a professional React dashboard. The MVP demonstrates a complete end-to-end observability intelligence loop: from signal ingestion, through AI analysis, to human-readable insight and recommended remediation, running entirely on free and open-source tooling with no paid cloud dependency beyond the Groq free API tier.

---

## 1. Problem Statement

Modern engineering teams operate monitoring stacks that generate hundreds of alerts daily. Grafana and Prometheus are excellent at visualizing and thresholding metrics, but they do not answer the questions engineers actually need answered under pressure:

- Is this a real incident or noise?
- Which alerts belong to the same root event?
- What probably caused this?
- What should I do first?
- How bad is the overall system health right now?

Engineers still spend 15–40 minutes per incident manually correlating logs, checking dashboards, reading runbooks, and forming hypotheses. Static thresholds generate false positives during traffic spikes. Alerts from five different services for a single upstream failure look like five separate problems. Mean Time To Resolution (MTTR) stays high not because engineers are slow, but because the tools do not reason — they only display.

---

## 2. Solution Statement

AIOps Sentinel adds an AI reasoning layer on top of existing monitoring concepts. It:

1. Ingests simulated production-like metrics and logs across multiple services
2. Applies both threshold-based and ML-based anomaly detection
3. Correlates anomalies with deployment events and across service boundaries
4. Groups correlated signals into unified incidents
5. Uses Groq-hosted LLM (free tier, llama3-8b-8192) with an NLG template fallback to generate plain-English incident summaries
6. Suggests probable root causes from pattern libraries and signal correlation
7. Recommends concrete next actions with confidence markers
8. Presents everything through a clean React dashboard with health scores, timelines, and incident detail panels

---

## 3. Project Architecture

```
+------------------------------------------------------------------+
|                     React Frontend (Vite)                        |
|  Health Cards | Incident List | Charts | Detail Panel | Timeline |
+--------------------------------+---------------------------------+
                                 | REST (HTTP/JSON)
+--------------------------------v---------------------------------+
|                    FastAPI Backend (Python)                      |
|                                                                  |
|  +--------------+  +--------------+  +----------------------+   |
|  | Simulation   |  | Detection    |  | Incident Engine      |   |
|  | Engine       |  | Engine       |  |                      |   |
|  |              |  |              |  | Correlation          |   |
|  | - Metrics    |  | - Threshold  |  | Grouping             |   |
|  | - Logs       |  | - IsolFor.   |  | Health Scoring       |   |
|  | - Events     |  | - Z-Score    |  |                      |   |
|  +------+-------+  +------+-------+  +----------+-----------+   |
|         |                 |                     |               |
|  +------v-----------------v---------------------v-----------+   |
|  |                  AI / Analytics Layer                    |   |
|  |                                                          |   |
|  |  pandas (processing)   scikit-learn (anomaly detection)  |   |
|  |  pandas rolling stats (trends)  Groq API/llama3 (summarization)    |   |
|  |  Rule engine (RCA)     NLG fallback (offline safety)    |   |
|  +---------------------------+------------------------------+   |
|                              |                                  |
|  +---------------------------v------------------------------+   |
|  |                      Data Layer                          |   |
|  |   SQLite (incidents, anomalies)                          |   |
|  |   JSON/CSV (simulated logs, metrics)                     |   |
|  +----------------------------------------------------------+   |
+------------------------------------------------------------------+
```

**Data Flow:**
```
Simulator --> Raw Metrics/Logs --> Detection Engine --> Anomaly Records
                                                             |
                                                   Correlation Engine
                                                             |
                                                   Incident Records
                                                             |
                                                   AI Summary + RCA + Actions
                                                             |
                                                   REST API --> React Dashboard
```

---

## 4. AI Usage — Where, What, and Why

| AI Function | Technique | Library / Model | Defensibility |
|---|---|---|---|
| **Anomaly Detection** | Isolation Forest | scikit-learn | Learns from traffic patterns without labeled data; handles multivariate signals |
| **Trend Analysis** | Rolling Z-score, EWMA | pandas | Statistically principled drift detection before threshold breach; no statsmodels needed |
| **Log Pattern Analysis** | TF-IDF clustering, log template matching | scikit-learn | Groups semantically similar log lines; surfaces error clusters |
| **Event Correlation** | Time-window overlap + Pearson correlation on metric deltas | pandas | Links deployment events to anomaly windows with computed confidence |
| **Incident Grouping** | Rule-based deduplication + DBSCAN clustering on anomaly feature vectors | scikit-learn | Prevents alert storms from creating N separate incidents |
| **Incident Summarization** | Llama 3 via Groq API (free tier) | groq Python SDK | Sub-second response, no local GPU needed, free tier sufficient for demo and dev |
| **Root Cause Inference** | Pattern matching + weighted rule engine | Rule engine | Structured heuristics with explainable confidence scores; ChromaDB is roadmap, not MVP |
| **Next Action Recommendation** | Decision tree on incident type + LLM elaboration | Rules + Groq API | Deterministic base, LLM provides elaboration and context |
| **Health Scoring** | Weighted anomaly severity aggregation | Custom formula | Transparent, explainable scoring |
| **Alert Prioritization** | Anomaly severity x blast radius x recency | Scoring model | Surfaces the most impactful issues first |

**LLM Strategy:** Groq API (free tier) is the primary LLM runtime. It uses `llama3-8b-8192`, returns responses in under 1 second, and requires no local GPU. If the demo environment has no internet access, the system falls back to a template-based NLG module that produces structured summaries from incident metadata. The fallback is always on and always ready — the demo never breaks regardless of connectivity.

---

## 5. Tech Stack

### Frontend
```
React 18          — component framework
Vite              — build tool (fast dev server)
Tailwind CSS      — utility-first styling
Recharts          — metric time series charts
React Query       — API state management and polling
date-fns          — timestamp formatting
Lucide React      — icon set
```

### Backend
```
Python 3.11+
FastAPI           — REST API framework
Uvicorn           — ASGI server
SQLite            — incident and anomaly storage (via SQLAlchemy)
asyncio           — background simulation loop (built-in, no extra dependency)
```

### AI / Analytics
```
pandas            — data processing, rolling Z-score, EWMA (replaces statsmodels)
scikit-learn      — Isolation Forest, DBSCAN, TF-IDF, Z-score
joblib            — model serialization (pre-trained baseline for Isolation Forest)
groq              — Groq API Python SDK (free tier, llama3-8b-8192)
NLG template engine — offline fallback for summary generation (custom, no dependency)
```

### Data Layer
```
SQLite            — incidents, anomalies, service events
Faker             — synthetic data generation
JSON files        — simulated log streams
CSV files         — simulated metric snapshots
```

### DevOps
```
Docker            — containerize backend and frontend separately
Docker Compose    — single-command startup for the full stack
Makefile          — convenience commands (make demo, make simulate, make reset)
pytest            — backend unit tests
```

---

## 6. Simulated Services

```
api-gateway           — entry point; high request volume
auth-service          — downstream dependency of gateway
order-service         — business-critical; latency-sensitive
payment-service       — highest criticality; low tolerance for errors
notification-service  — async; less critical but visible
```

---

## 7. Data Schemas

### Metric Schema (per service, per timestamp)
```json
{
  "timestamp": "2026-04-25T14:32:01Z",
  "service": "order-service",
  "environment": "production",
  "latency_p50_ms": 142,
  "latency_p95_ms": 380,
  "latency_p99_ms": 720,
  "error_rate_pct": 2.4,
  "request_volume": 1840,
  "cpu_pct": 67.2,
  "memory_pct": 71.8,
  "status_codes": {"200": 1798, "500": 38, "503": 4},
  "deployment_event": null
}
```

### Log Schema
```json
{
  "timestamp": "2026-04-25T14:32:01.412Z",
  "service": "order-service",
  "environment": "production",
  "level": "ERROR",
  "trace_id": "abc-123-xyz",
  "request_id": "req-9912",
  "message": "Timeout waiting for payment-service response after 5000ms",
  "latency_ms": 5001,
  "status_code": 503
}
```

---

## 8. Simulation Scenarios

| Scenario | Affected Services | Duration |
|---|---|---|
| Normal traffic | All | Continuous |
| Traffic spike | api-gateway, order-service | 5 min |
| Bad deployment | payment-service | 10 min |
| Cascading failure | payment-service → order-service → gateway | 8 min |
| Memory pressure | auth-service | 15 min |
| Error burst | notification-service | 3 min |
| Latency regression | order-service | 10 min |

---

## 9. API Design

```
POST   /simulate/start                 — start continuous simulation
POST   /simulate/stop                  — stop simulation
POST   /simulate/scenario              — inject a named scenario (body: {scenario: "cascading_failure"})
POST   /simulate/logs                  — inject a custom log batch
POST   /simulate/metrics               — inject a custom metric snapshot
POST   /simulate/anomaly               — trigger an immediate anomaly on a service
POST   /simulate/reset                 — reset all state

GET    /metrics                        — last N metric snapshots, all services
GET    /metrics/{service}              — last N snapshots for one service
GET    /logs                           — last N log entries (filterable by service, level)
GET    /logs/{service}                 — logs for a specific service

GET    /incidents                      — all incidents, sorted by severity desc
GET    /incidents/{incident_id}        — full incident detail with AI analysis
PATCH  /incidents/{incident_id}        — update status (acknowledged, resolved)

GET    /anomalies                      — current detected anomalies
GET    /anomalies/{service}            — anomalies for one service

GET    /services                       — health summary for all services
GET    /services/{service}/health      — detailed health score and contributing factors

GET    /events                         — deployment and change events log
GET    /summary/system                 — system-wide health overview for dashboard header
```

### Incident Detail Payload (GET /incidents/{id})
```json
{
  "incident_id": "INC-20260425-0042",
  "status": "active",
  "severity": "critical",
  "affected_services": ["payment-service", "order-service"],
  "first_detected": "2026-04-25T14:28:00Z",
  "trigger_event": {
    "type": "deployment",
    "service": "payment-service",
    "version": "v2.4.1",
    "timestamp": "2026-04-25T14:25:00Z"
  },
  "anomalies": [],
  "ai_summary": "At 14:28 UTC, payment-service began experiencing a significant error rate increase (18.4%) and p99 latency degradation (4.2s) approximately 3 minutes after deployment of v2.4.1. This propagated upstream to order-service, which shows a correlated latency increase and rising timeout errors. Auth-service remains healthy.",
  "root_cause_suggestions": [
    {
      "cause": "Regression introduced in deployment v2.4.1",
      "confidence": 0.87,
      "signals": ["deployment correlation", "error pattern change", "latency onset timing"]
    },
    {
      "cause": "Database connection pool exhaustion",
      "confidence": 0.42,
      "signals": ["memory pressure", "response timeout pattern"]
    }
  ],
  "recommended_actions": [
    {
      "priority": 1,
      "action": "Roll back payment-service to v2.4.0",
      "rationale": "Deployment correlation confidence is high; rollback has lowest blast radius."
    },
    {
      "priority": 2,
      "action": "Scale order-service horizontally to absorb backpressure",
      "rationale": "Reduces cascading impact while payment-service is investigated."
    }
  ],
  "health_scores": {
    "payment-service": 18,
    "order-service": 41,
    "system": 62
  }
}
```

---

## 10. React Dashboard Layout

```
+------------------------------------------------------------------------+
|  AIOps Sentinel                         System Health: 62/100  [RED]   |
|  Last updated: 14:33:12 UTC                          2 Active Incidents |
+----------+-----------+-----------+-----------+---------------------------+
| api-gw   | auth-svc  | order-svc | payment   | notification              |
|   82 YLW |   91 GRN  |   58 ORG  |  18 RED   |   95 GRN                  |
| 2 anomaly| healthy   | 3 anomaly | CRITICAL  | healthy                   |
+----------+-----------+-----------+-----------+---------------------------+
| ACTIVE INCIDENTS                             [Simulate Scenario v]      |
|                                                                         |
| [RED] INC-0042  payment-service degradation -> order-service cascade    |
|       Critical | 3 services | Started 5m ago | AI: Deployment regression |
|                                                                         |
| [ORG] INC-0041  api-gateway latency spike                               |
|       Warning  | 1 service  | Started 12m ago | AI: Traffic spike        |
+-------------------------------------------------------------------------+
| METRICS                             Service: [All v]  Window: [5m v]   |
|                                                                         |
|  Latency (p99)             Error Rate              Request Volume       |
|  [Recharts line chart]     [Recharts area chart]   [Recharts bar]       |
|                                                                         |
+-------------------------------------------------------------------------+
| INCIDENT TIMELINE -- INC-0042                                           |
|                                                                         |
|  14:25  [DEPLOY] Deploy payment-service v2.4.1                          |
|  14:28  [WARN]   Error rate > 5% on payment-service                     |
|  14:29  [CRIT]   Latency p99 > 3s on payment-service                    |
|  14:30  [WARN]   Timeout errors rising on order-service                 |
|  14:31  [AI]     AI correlated 4 signals into 1 incident                |
|  14:32  [CRIT]   Incident escalated to Critical                         |
|                                                                         |
+-------------------------------------------------------------------------+
| AI ANALYSIS -- INC-0042                                                 |
|                                                                         |
| SUMMARY                                                                 |
| At 14:28 UTC, payment-service began experiencing a significant error    |
| rate increase (18.4%)... [full AI summary]                              |
|                                                                         |
| ROOT CAUSE SUGGESTIONS          RECOMMENDED ACTIONS                    |
| * Deployment regression  87%    1. Rollback payment-service v2.4.0     |
| * DB connection exhaust  42%    2. Scale order-service horizontally     |
| * Config drift           21%    3. Check DB connection pool config      |
|                                                                         |
+-------------------------------------------------------------------------+
```

---

## 11. MVP Scope vs. Optional Scope

### Essential (must have for hackathon)
- [ ] Simulation engine with 3+ scenarios
- [ ] Isolation Forest anomaly detection
- [ ] Rolling Z-score drift detection
- [ ] Time-window correlation engine
- [ ] Incident grouping (rule-based)
- [ ] LLM incident summary (Groq API, free tier) with NLG template fallback
- [ ] Rule-based RCA engine with confidence scores
- [ ] Action recommendation cards
- [ ] Service health scores
- [ ] React dashboard with all six sections
- [ ] All listed REST APIs
- [ ] Docker Compose startup

### Optional (add if time permits)
- [ ] SSE (Server-Sent Events) endpoint for push-based dashboard updates
- [ ] Pearson cross-service correlation matrix
- [ ] STL seasonal decomposition (requires statsmodels)
- [ ] Alert deduplication via DBSCAN
- [ ] Health score trend chart
- [ ] ChromaDB RAG over synthetic runbooks (production roadmap item)
- [ ] Azure DevOps YAML pipeline

---

## 12. Key Differentiators vs. Grafana / Prometheus

| Grafana / Prometheus | AIOps Sentinel |
|---|---|
| Shows you data | Interprets data for you |
| Fires alerts per threshold | Detects statistical anomalies before thresholds |
| N alerts for 1 event | Groups N alerts into 1 incident |
| No cross-service correlation | Automatic cascade detection |
| Engineers write runbook queries | AI generates natural-language summaries |
| Root cause: manual investigation | Root cause: AI suggestion with confidence |
| Next step: engineer decides | Next step: AI recommends with rationale |
| Dashboard per service | Unified system health score |

> "Grafana shows you the fire. AIOps Sentinel tells you why it started and how to put it out."

---

## 13. Demo Scenario Flow (15-minute presentation)

| Time | Action |
|---|---|
| 0–2 min | Show healthy dashboard (all services green, health ~90) |
| 2–4 min | Trigger "Bad Deployment: payment-service v2.4.1" |
| 4–7 min | Watch AI detect cascade: error rate → latency → order-service impact |
| 7–10 min | Open INC-0042: AI summary, root cause bars, action cards, timeline |
| 10–12 min | Show log cluster view: 87 "Timeout waiting for DB" lines grouped |
| 12–14 min | Acknowledge → Resolve → trigger rollback → health scores recover |
| 14–15 min | Close with before/after MTTR comparison |

---

## 14. Suggested Division of Work

### Person A — AI / Backend Engineer
- Simulation engine (data generation for all scenarios)
- Anomaly detection module (Isolation Forest + Z-score, pre-trained on synthetic baseline)
- Event correlation engine
- Root cause rule engine with confidence scoring
- Groq API integration and prompt engineering
- NLG fallback module

### Person B — Backend / API Engineer
- FastAPI application structure
- All REST API endpoints
- SQLite schema and SQLAlchemy models
- asyncio background simulation loop (FastAPI lifespan)
- Docker and Docker Compose configuration
- pytest unit tests

### Person C — Frontend Engineer
- React app setup (Vite + Tailwind)
- All dashboard sections and layouts
- Recharts metric charts with real-time polling (React Query)
- Incident list and detail drawer
- Timeline component
- Scenario trigger control panel
- Health score cards

> **Day 1 priority:** Agree on the incident JSON schema before building in parallel.

---

## 15. Short Pitch for Judges

> Every engineering team has Grafana. Every engineering team still spends 30 minutes figuring out what broke and why.
>
> AIOps Sentinel is an AI reasoning layer that sits above your existing monitoring. It detects anomalies before they breach thresholds, correlates signals from multiple services into a single incident, and uses a fast cloud LLM to generate a plain-English summary that tells you what happened, what probably caused it, and what to do next — in under 90 seconds.
>
> Free to run. Open-source stack. Runs alongside Grafana and Prometheus, not instead of them.
>
> We demonstrated a simulated cascading failure triggered by a bad deployment. AIOps Sentinel detected it, correlated four anomaly signals into one incident, and surfaced a root cause hypothesis with 87% confidence — all automatically. That is the difference between a monitoring tool and an intelligence tool.

---

## 16. Presentation Outline

| Slide | Content |
|---|---|
| 1 | Title + one-line value proposition |
| 2 | The problem (MTTR cost, alert noise) |
| 3 | What AIOps Sentinel does (6-point solution list) |
| 4 | Architecture diagram (simplified) |
| 5 | Where AI is used (table: function → technique → library) |
| 6 | LIVE DEMO (8 minutes) |
| 7 | Results: before vs. after comparison |
| 8 | Tech stack visual |
| 9 | Essential now vs. production roadmap |
| 10 | Team and division of work |
| 11 | Call to action / next steps if approved |

---

## 17. Future Production Roadmap

| Phase | Capability | Tools |
|---|---|---|
| Phase 1 (Current) | Simulated data, Groq API LLM (free tier), SQLite | As described above |
| Phase 2A ✅ | Real Prometheus scrape integration | prometheus-api-client, httpx |
| Phase 2B ✅ | Real Loki log ingestion + Promtail agent config | httpx, Grafana Loki 3.0 |
| Phase 3 | Azure OpenAI or GPT-4o summarization | Azure OpenAI SDK |
| Phase 4 | Azure Monitor or Datadog alert webhook receiver | Webhook endpoint |
| Phase 5 | Multi-tenant incident management with RBAC | PostgreSQL, Entra ID |
| Phase 6 | Runbook automation from action cards | Ansible, Azure DevOps REST API |
| Phase 7 | Feedback loop — engineer ratings train the RCA model | Active learning pipeline |

---

## 18. Recommended Implementation Order

1. Define and freeze the incident JSON schema
2. Build the simulation engine (at least 2 scenarios working)
3. Stand up FastAPI with stub endpoints returning mock data
4. Build the React dashboard against the stub APIs
5. Implement anomaly detection and wire to real APIs
6. Implement correlation engine and incident grouping
7. Integrate Groq API summarization with NLG template fallback
8. Implement RCA rule engine and action cards
9. Build health scoring
10. Polish dashboard, wire all panels end-to-end
11. Full demo run-through and timing
12. Docker Compose packaging and one-command startup verification

---

*Document generated: 2026-04-25*
*Revised: 2026-04-25 — LLM runtime changed from Ollama (local) to Groq API (free tier); APScheduler replaced with asyncio; statsmodels removed from essential scope; ChromaDB moved to production roadmap.*
*Project: AIOps Sentinel — Internal Hackathon*
