import os
from groq import Groq
from config import settings

_client: Groq | None = None


def _get_client() -> Groq | None:
    global _client
    if _client is None and settings.groq_api_key:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def build_prompt(incident: dict) -> str:
    services = ", ".join(incident.get("affected_services", []))
    anomalies = incident.get("raw_anomalies", [])
    trigger = incident.get("trigger_event")
    trigger_str = ""
    if trigger:
        trigger_str = f"- Deployment event: {trigger.get('service')} version {trigger.get('version', 'unknown')} deployed at {trigger.get('timestamp', 'unknown')}\n"

    anomaly_lines = "\n".join(
        f"  - {a['service']}: {a['metric']} = {a['value']} (baseline {a['baseline_value']}, deviation {a['deviation_pct']}%, severity {a['severity']}, method {a['detection_method']})"
        for a in anomalies[:10]
    )

    return f"""You are an AI observability assistant. Analyze the following incident data and generate a concise, professional incident summary in 3-4 sentences.

INCIDENT DATA:
- Incident ID: {incident.get('incident_id')}
- Affected services: {services}
- First detected: {incident.get('first_detected')}
- Overall severity: {incident.get('severity')}
{trigger_str}
Detected anomalies:
{anomaly_lines}

Write a factual, plain-English summary that includes:
1. Which services are affected
2. What symptoms were detected (specific metrics and values)
3. Whether a deployment or change event likely triggered it
4. The estimated blast radius

Be concise and technical. Do not use bullet points. Output only the summary paragraph."""


def generate_summary(incident: dict) -> str | None:
    client = _get_client()
    if not client:
        return None
    try:
        prompt = build_prompt(incident)
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": "You are a senior site reliability engineer and AI observability assistant. Be concise, factual, and technical."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return None
