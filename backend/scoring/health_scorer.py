"""
Health scoring module.
Computes per-service and system-wide health scores (0-100).
Lower score = worse health.
"""

from datetime import datetime, timezone, timedelta

# In-memory anomaly history per service for scoring
_anomaly_history: dict[str, list[dict]] = {}
_metric_snapshots: dict[str, list[dict]] = {}


def record_anomaly(service: str, anomaly: dict):
    if service not in _anomaly_history:
        _anomaly_history[service] = []
    _anomaly_history[service].append({**anomaly, "_recorded": datetime.now(timezone.utc)})
    # Keep last 30 anomalies per service
    _anomaly_history[service] = _anomaly_history[service][-30:]


def record_snapshot(service: str, snapshot: dict):
    if service not in _metric_snapshots:
        _metric_snapshots[service] = []
    _metric_snapshots[service].append(snapshot)
    _metric_snapshots[service] = _metric_snapshots[service][-20:]


def _severity_penalty(sev: str) -> float:
    return {"critical": 35.0, "warning": 15.0, "info": 5.0}.get(sev, 0.0)


def _decay(seconds_ago: float, half_life: float = 300.0) -> float:
    """Exponential decay so older anomalies have less weight."""
    return 0.5 ** (seconds_ago / half_life)


def compute_service_health(service: str) -> dict:
    now = datetime.now(timezone.utc)
    window = timedelta(minutes=30)
    cutoff = now - window

    recent_anomalies = [
        a for a in _anomaly_history.get(service, [])
        if a["_recorded"] >= cutoff
    ]

    penalty = 0.0
    for a in recent_anomalies:
        age_seconds = (now - a["_recorded"]).total_seconds()
        weight = _decay(age_seconds)
        penalty += _severity_penalty(a["severity"]) * weight

    score = max(0, min(100, 100 - penalty))

    # Collect latest metrics for display
    latest = _metric_snapshots.get(service, [{}])[-1]

    return {
        "service": service,
        "health_score": round(score, 1),
        "status": _score_to_status(score),
        "anomaly_count_30m": len(recent_anomalies),
        "latest_metrics": {
            "latency_p99_ms": latest.get("latency_p99_ms"),
            "error_rate_pct": latest.get("error_rate_pct"),
            "cpu_pct": latest.get("cpu_pct"),
            "memory_pct": latest.get("memory_pct"),
            "request_volume": latest.get("request_volume"),
        },
    }


def compute_system_health(services: list[str]) -> dict:
    service_scores = {svc: compute_service_health(svc) for svc in services}
    scores = [v["health_score"] for v in service_scores.values()]
    system_score = round(sum(scores) / len(scores), 1) if scores else 100.0

    return {
        "system_health_score": system_score,
        "system_status": _score_to_status(system_score),
        "services": service_scores,
    }


def _score_to_status(score: float) -> str:
    if score >= 85:
        return "healthy"
    if score >= 60:
        return "degraded"
    if score >= 35:
        return "critical"
    return "down"


def reset_scores():
    _anomaly_history.clear()
    _metric_snapshots.clear()
