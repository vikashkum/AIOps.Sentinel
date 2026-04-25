"""
Rule-based root cause analysis engine.
Each rule pattern maps signal combinations to a probable cause with confidence scoring.
"""

from simulator.scenarios import BASELINES


def _deviation(current, baseline) -> float:
    if baseline == 0:
        return 0
    return (current - baseline) / baseline * 100


def suggest_root_causes(incident: dict) -> list[dict]:
    anomalies = incident.get("raw_anomalies", [])
    trigger = incident.get("trigger_event")
    services = incident.get("affected_services", [])

    causes = []

    # --- Pattern 1: Post-deployment regression ---
    if trigger and trigger.get("type") == "deployment":
        deployment_service = trigger.get("service")
        deployment_anomalies = [a for a in anomalies if a["service"] == deployment_service]
        if deployment_anomalies:
            error_anomaly = next((a for a in deployment_anomalies if "error" in a["metric"]), None)
            latency_anomaly = next((a for a in deployment_anomalies if "latency" in a["metric"]), None)
            confidence = 0.55
            signals = ["deployment event within correlation window"]
            if error_anomaly:
                confidence += 0.18
                signals.append(f"error rate spike in {deployment_service}")
            if latency_anomaly:
                confidence += 0.12
                signals.append(f"latency regression in {deployment_service}")
            if len(services) > 1:
                confidence += 0.07
                signals.append("cross-service impact suggests upstream regression")
            causes.append({
                "cause": f"Regression introduced by deployment {trigger.get('version', 'unknown')} of {deployment_service}",
                "confidence": round(min(confidence, 0.96), 2),
                "signals": signals,
            })

    # --- Pattern 2: Cascading downstream failure ---
    if len(services) >= 3:
        causes.append({
            "cause": "Cascading failure from upstream service dependency",
            "confidence": round(0.45 + min(len(services) * 0.07, 0.30), 2),
            "signals": [
                f"{len(services)} services affected simultaneously",
                "anomaly onset ordering consistent with cascade pattern",
            ],
        })

    # --- Pattern 3: Resource saturation ---
    mem_anomalies = [a for a in anomalies if "memory" in a["metric"] and a["deviation_pct"] > 60]
    cpu_anomalies = [a for a in anomalies if "cpu" in a["metric"] and a["deviation_pct"] > 50]
    if mem_anomalies or cpu_anomalies:
        confidence = 0.38
        signals = []
        if mem_anomalies:
            signals.append(f"memory pressure on {mem_anomalies[0]['service']} ({mem_anomalies[0]['deviation_pct']:.0f}% above baseline)")
            confidence += 0.20
        if cpu_anomalies:
            signals.append(f"CPU saturation on {cpu_anomalies[0]['service']} ({cpu_anomalies[0]['deviation_pct']:.0f}% above baseline)")
            confidence += 0.15
        causes.append({
            "cause": "Resource saturation (memory or CPU exhaustion)",
            "confidence": round(min(confidence, 0.82), 2),
            "signals": signals,
        })

    # --- Pattern 4: Database or connection pool exhaustion ---
    error_anomalies = [a for a in anomalies if "error" in a["metric"] and a["deviation_pct"] > 200]
    latency_anomalies = [a for a in anomalies if "latency" in a["metric"] and a["deviation_pct"] > 150]
    if error_anomalies and latency_anomalies:
        causes.append({
            "cause": "Database connection pool exhaustion or slow query regression",
            "confidence": round(0.30 + min(len(error_anomalies) * 0.06, 0.28), 2),
            "signals": [
                "simultaneous error rate and latency spikes",
                "pattern consistent with connection pool saturation",
            ],
        })

    # --- Pattern 5: External dependency failure ---
    high_error_services = [a["service"] for a in anomalies if "error" in a["metric"] and a["deviation_pct"] > 400]
    if high_error_services:
        causes.append({
            "cause": "External API or downstream dependency returning errors",
            "confidence": 0.28,
            "signals": [
                f"extreme error rate spike on {high_error_services[0]}",
                "pattern consistent with external 5xx responses",
            ],
        })

    # --- Pattern 6: Traffic spike / load surge ---
    vol_anomalies = [a for a in anomalies if "volume" in a["metric"] and a["deviation_pct"] > 100]
    if vol_anomalies:
        causes.append({
            "cause": "Unexpected traffic surge or load spike",
            "confidence": round(0.40 + min(vol_anomalies[0]["deviation_pct"] / 500, 0.30), 2),
            "signals": [
                f"request volume {vol_anomalies[0]['deviation_pct']:.0f}% above baseline",
                "latency and error rate increase consistent with overload",
            ],
        })

    # Ensure at least one cause
    if not causes:
        causes.append({
            "cause": "Unknown — insufficient signal correlation for confident diagnosis",
            "confidence": 0.15,
            "signals": ["insufficient pattern match", "manual investigation recommended"],
        })

    # Sort by confidence descending
    return sorted(causes, key=lambda c: c["confidence"], reverse=True)
