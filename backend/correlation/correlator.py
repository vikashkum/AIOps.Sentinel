import uuid
from datetime import datetime, timezone, timedelta
from config import settings

# In-memory stores (drained on reset)
_pending_anomalies: list[dict] = []
_active_incidents: dict[str, dict] = {}  # incident_id -> incident dict
_recent_events: list[dict] = []  # deployment events


def push_event(event: dict):
    _recent_events.append(event)
    # keep last 50 events
    if len(_recent_events) > 50:
        _recent_events.pop(0)


def push_anomaly(anomaly: dict):
    _pending_anomalies.append(anomaly)


def get_recent_event_for_service(service: str, window_minutes: int = 15) -> dict | None:
    """Return the most recent deployment event for a service within the window."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_minutes)
    for ev in reversed(_recent_events):
        ts = ev.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if ts >= cutoff and ev.get("service") == service:
            return ev
    return None


def _severity_rank(sev: str) -> int:
    return {"critical": 3, "warning": 2, "info": 1}.get(sev, 0)


def _group_severity(anomalies: list[dict]) -> str:
    top = max(anomalies, key=lambda a: _severity_rank(a["severity"]))
    return top["severity"]


def correlate_and_group() -> list[dict]:
    """
    Group pending anomalies into incidents based on:
    - Time proximity (within correlation_window_minutes)
    - Service overlap or cross-service cascade pattern
    Returns list of new/updated incident dicts.
    """
    if not _pending_anomalies:
        return []

    window = timedelta(minutes=settings.correlation_window_minutes)
    now = datetime.now(timezone.utc)
    cutoff = now - window

    # Filter to recent anomalies only
    recent = []
    for a in _pending_anomalies:
        ts = a.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if ts >= cutoff:
            recent.append({**a, "_ts": ts})

    if not recent:
        return []

    # Group by affected services
    services_seen = list({a["service"] for a in recent})

    # Check if existing active incident covers these services
    matched_incident = None
    for inc in _active_incidents.values():
        if inc["status"] != "resolved":
            overlap = set(inc["affected_services"]) & set(services_seen)
            if overlap:
                matched_incident = inc
                break

    new_anomaly_ids = [a["anomaly_id"] for a in recent]

    if matched_incident:
        # Update existing incident
        existing_services = set(matched_incident["affected_services"])
        existing_services.update(services_seen)
        matched_incident["affected_services"] = sorted(existing_services)
        existing_ids = set(matched_incident.get("anomaly_ids", []))
        existing_ids.update(new_anomaly_ids)
        matched_incident["anomaly_ids"] = list(existing_ids)
        matched_incident["severity"] = _group_severity(recent)
        matched_incident["last_updated"] = now.isoformat()
        _pending_anomalies.clear()
        return [matched_incident]

    # Create new incident if enough anomalies
    if len(recent) < settings.min_anomalies_for_incident:
        return []

    incident_id = f"INC-{now.strftime('%Y%m%d')}-{str(uuid.uuid4().hex[:4]).upper()}"

    # Find trigger event
    trigger = None
    for svc in services_seen:
        ev = get_recent_event_for_service(svc, window_minutes=15)
        if ev:
            trigger = ev
            break

    # Build title
    primary_svc = services_seen[0]
    worst = max(recent, key=lambda a: _severity_rank(a["severity"]))
    title = f"{primary_svc} {worst['metric'].replace('_', ' ')} anomaly"
    if len(services_seen) > 1:
        title += f" — cascade affecting {len(services_seen)} services"

    incident = {
        "incident_id": incident_id,
        "title": title,
        "status": "active",
        "severity": _group_severity(recent),
        "affected_services": sorted(services_seen),
        "first_detected": min(a["_ts"] for a in recent).isoformat(),
        "last_updated": now.isoformat(),
        "trigger_event": trigger,
        "anomaly_ids": new_anomaly_ids,
        "ai_summary": None,
        "root_cause_suggestions": None,
        "recommended_actions": None,
        "health_scores": None,
        "raw_anomalies": recent,
    }

    _active_incidents[incident_id] = incident
    _pending_anomalies.clear()
    return [incident]


def get_all_incidents() -> list[dict]:
    return sorted(
        _active_incidents.values(),
        key=lambda i: _severity_rank(i["severity"]),
        reverse=True,
    )


def get_incident(incident_id: str) -> dict | None:
    return _active_incidents.get(incident_id)


def update_incident_status(incident_id: str, status: str) -> bool:
    if incident_id in _active_incidents:
        _active_incidents[incident_id]["status"] = status
        _active_incidents[incident_id]["last_updated"] = datetime.now(timezone.utc).isoformat()
        return True
    return False


def update_incident_ai(incident_id: str, summary: str, rca: list, actions: list, health: dict):
    if incident_id in _active_incidents:
        _active_incidents[incident_id]["ai_summary"] = summary
        _active_incidents[incident_id]["root_cause_suggestions"] = rca
        _active_incidents[incident_id]["recommended_actions"] = actions
        _active_incidents[incident_id]["health_scores"] = health


def reset_all():
    _pending_anomalies.clear()
    _active_incidents.clear()
    _recent_events.clear()
