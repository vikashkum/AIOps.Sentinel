"""
Phase 2B — Loki integration REST routes.

Two modes are supported:

1. **Pull mode** (default): AIOps Sentinel's background loop queries Loki
   on a schedule using LokiCollector.  Configure via LOKI_URL and
   LOKI_ENABLED in .env.

2. **Push mode**: External log shippers (Promtail, Alloy, custom scripts)
   POST log entries to POST /ingest/loki and they are processed immediately.

Endpoints
---------
    GET  /loki/status                  — connectivity health check
    GET  /loki/jobs                    — list job labels discovered in Loki
    POST /loki/scrape/{job}            — trigger an immediate on-demand pull for one job
    POST /ingest/loki                  — push pre-parsed log entries (Loki-format or plain)
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Optional
from datetime import datetime, timezone
import logging

from config import settings
from collectors.loki_collector import LokiCollector
from api.routes.logs import store_logs
from detection import anomaly_detector
from scoring import health_scorer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["loki"])

_collector: Optional[LokiCollector] = None


def get_collector() -> LokiCollector:
    global _collector
    if _collector is None:
        _collector = LokiCollector(
            base_url=settings.loki_url,
            timeout=10.0,
        )
    return _collector


# ── Health / discovery ────────────────────────────────────────────────────────

@router.get("/loki/status")
def loki_status():
    """Check whether AIOps Sentinel can reach the configured Loki instance."""
    enabled = settings.loki_enabled
    if not enabled:
        return {
            "enabled": False,
            "message": "Loki integration is disabled.  Set LOKI_ENABLED=true in .env.",
        }

    c = get_collector()
    healthy = c.check_health()
    jobs = c.list_jobs() if healthy else []
    return {
        "enabled": True,
        "url": settings.loki_url,
        "healthy": healthy,
        "jobs_discovered": jobs,
    }


@router.get("/loki/jobs")
def loki_jobs():
    """List all job label values currently known to Loki."""
    if not settings.loki_enabled:
        raise HTTPException(status_code=503, detail="Loki integration is disabled.")
    jobs = get_collector().list_jobs()
    return {"jobs": jobs}


# ── On-demand scrape ──────────────────────────────────────────────────────────

@router.post("/loki/scrape/{job}")
def loki_scrape_job(
    job: str,
    lookback_seconds: int = 30,
    limit: int = 500,
):
    """
    Immediately pull log entries for a single Loki job label and inject them
    into the log store, anomaly detector, and health scorer.
    """
    if not settings.loki_enabled:
        raise HTTPException(status_code=503, detail="Loki integration is disabled.")

    c = get_collector()
    entries = c.scrape_job(job, lookback_seconds=lookback_seconds, limit=limit)
    _inject_logs(job, entries)

    return {
        "status": "scraped",
        "job": job,
        "entries_ingested": len(entries),
    }


# ── Push ingest ───────────────────────────────────────────────────────────────

@router.post("/ingest/loki")
def ingest_loki_push(
    payload: list[dict] = Body(
        ...,
        examples=[
            [
                {
                    "service": "order-service",
                    "level": "ERROR",
                    "message": "Timeout waiting for payment-service response after 5000ms",
                    "timestamp": "2026-04-25T14:32:01.412Z",
                }
            ]
        ],
    )
):
    """
    Accept a JSON array of log entries from external log shippers or scripts.

    Each item must include at minimum:
      - service (str)   — job/service name
      - message (str)   — the log line text

    Optional fields: timestamp, level, trace_id, request_id, latency_ms,
    status_code, environment.

    Also accepts Loki's native push format — if an item contains a 'streams'
    key (Loki /loki/api/v1/push body), it is automatically unwrapped.
    """
    if not isinstance(payload, list):
        payload = [payload]

    now = datetime.now(timezone.utc).isoformat()
    all_entries: list[dict] = []

    for item in payload:
        if not isinstance(item, dict):
            continue

        # Handle native Loki push format: {"streams": [{"stream": {...}, "values": [[ts, line], ...]}]}
        if "streams" in item:
            all_entries.extend(_unwrap_loki_push(item, now))
            continue

        # Plain AIOps format
        if not item.get("service") or not item.get("message"):
            continue

        entry = {
            "timestamp": item.get("timestamp") or now,
            "service": item["service"],
            "environment": item.get("environment", "production"),
            "level": (item.get("level") or "INFO").upper(),
            "message": item["message"],
            "trace_id": item.get("trace_id"),
            "request_id": item.get("request_id"),
            "latency_ms": item.get("latency_ms"),
            "status_code": item.get("status_code"),
            "source": "loki_push",
        }
        all_entries.append(entry)

    # Group by service and inject
    by_service: dict[str, list[dict]] = {}
    for e in all_entries:
        svc = e.get("service", "unknown")
        by_service.setdefault(svc, []).append(e)

    for svc, entries in by_service.items():
        _inject_logs(svc, entries)

    return {"status": "accepted", "entries_processed": len(all_entries)}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _unwrap_loki_push(body: dict, fallback_ts: str) -> list[dict]:
    """Convert a Loki /loki/api/v1/push body into our log entry list."""
    from collectors.loki_collector import _detect_level, _extract_fields
    entries: list[dict] = []

    for stream in body.get("streams", []):
        labels: dict = stream.get("stream", {})
        service = labels.get("job") or labels.get("service") or "unknown"
        environment = labels.get("env") or labels.get("environment") or "production"
        level_label = labels.get("level") or labels.get("severity")

        for value in stream.get("values", []):
            if not isinstance(value, (list, tuple)) or len(value) < 2:
                continue
            ts_ns_str, line = value[0], value[1]
            try:
                from datetime import datetime, timezone
                ts = datetime.fromtimestamp(
                    int(ts_ns_str) / 1_000_000_000, tz=timezone.utc
                ).isoformat()
            except Exception:
                ts = fallback_ts

            level = (level_label or _detect_level(line)).upper()
            structured = _extract_fields(line)

            entries.append({
                "timestamp": ts,
                "service": service,
                "environment": environment,
                "level": level,
                "message": line,
                "trace_id": structured.get("trace_id"),
                "request_id": structured.get("request_id"),
                "latency_ms": structured.get("latency_ms"),
                "status_code": structured.get("status_code"),
                "source": "loki_push",
            })

    return entries


def _inject_logs(service: str, entries: list[dict]) -> None:
    """Push log entries through the storage and health-scoring pipeline."""
    if not entries:
        return
    store_logs(entries)
    # Use error-rate proxy: fraction of ERROR/CRITICAL lines
    error_count = sum(
        1 for e in entries if e.get("level") in ("ERROR", "CRITICAL")
    )
    error_rate = (error_count / len(entries)) * 100 if entries else 0.0
    health_scorer.record_snapshot(service, {"error_rate_pct": error_rate})
