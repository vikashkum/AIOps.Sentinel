"""
Template-based NLG fallback for incident summarization.
Used when Groq API is unavailable (no key, no internet, rate limit).
"""

from datetime import datetime


def generate_summary(incident: dict) -> str:
    services = incident.get("affected_services", [])
    severity = incident.get("severity", "unknown")
    anomalies = incident.get("raw_anomalies", [])
    trigger = incident.get("trigger_event")
    first_detected = incident.get("first_detected", "")

    # Parse timestamp
    try:
        dt = datetime.fromisoformat(first_detected.replace("Z", "+00:00"))
        time_str = dt.strftime("%H:%M UTC")
    except Exception:
        time_str = "an unknown time"

    primary = services[0] if services else "an unknown service"
    affected_count = len(services)

    # Find dominant anomaly
    severity_rank = {"critical": 3, "warning": 2, "info": 1}
    top_anomaly = None
    if anomalies:
        top_anomaly = max(anomalies, key=lambda a: severity_rank.get(a.get("severity", "info"), 0))

    symptom_str = ""
    if top_anomaly:
        metric_display = top_anomaly["metric"].replace("_", " ").replace("pct", "%").replace("ms", " (ms)")
        symptom_str = (
            f"{primary} is showing a {top_anomaly['severity']} anomaly in {metric_display}: "
            f"current value {top_anomaly['value']} vs baseline {top_anomaly['baseline_value']} "
            f"({top_anomaly['deviation_pct']}% deviation)."
        )

    trigger_str = ""
    if trigger:
        trigger_str = (
            f" This correlates with a deployment of {trigger.get('service')} "
            f"version {trigger.get('version', 'unknown')} shortly before the anomaly onset."
        )

    cascade_str = ""
    if affected_count > 1:
        others = ", ".join(services[1:])
        cascade_str = f" The issue has propagated to {others}, indicating a potential cascading failure."

    summary = (
        f"At {time_str}, AIOps Sentinel detected a {severity}-severity incident originating from {primary}. "
        f"{symptom_str}"
        f"{trigger_str}"
        f"{cascade_str} "
        f"Immediate investigation is recommended to prevent further service degradation."
    )

    return summary.strip()
