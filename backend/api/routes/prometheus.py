"""
Phase 2A — Prometheus integration REST routes.

Two modes are supported:

1. **Pull mode** (default): AIOps Sentinel's background loop scrapes your
   Prometheus server on a schedule using PrometheusCollector.  Configure via
   PROMETHEUS_URL and PROMETHEUS_ENABLED in .env.

2. **Push mode**: External scripts / pipelines POST a JSON metric snapshot
   to POST /ingest/prometheus and it is processed immediately without waiting
   for the next scrape tick.

Endpoints
---------
    GET  /prometheus/status            — connectivity health check
    GET  /prometheus/jobs              — list job labels discovered in Prometheus
    POST /prometheus/scrape/{job}      — trigger an immediate on-demand scrape for one job
    POST /ingest/prometheus            — push a pre-built metric snapshot (batch or single)
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Optional
from datetime import datetime, timezone
import logging

from config import settings
from collectors.prometheus_collector import PrometheusCollector
from api.routes.metrics import store_metric
from detection import anomaly_detector
from scoring import health_scorer
from correlation import correlator

logger = logging.getLogger(__name__)
router = APIRouter(tags=["prometheus"])

# Lazy singleton — instantiated only when Prometheus integration is enabled
_collector: Optional[PrometheusCollector] = None


def get_collector() -> PrometheusCollector:
    global _collector
    if _collector is None:
        _collector = PrometheusCollector(
            base_url=settings.prometheus_url,
            timeout=10.0,
        )
    return _collector


# ── Health / discovery ────────────────────────────────────────────────────────

@router.get("/prometheus/status")
def prometheus_status():
    """Check whether AIOps Sentinel can reach the configured Prometheus instance."""
    enabled = settings.prometheus_enabled
    if not enabled:
        return {
            "enabled": False,
            "message": "Prometheus integration is disabled.  Set PROMETHEUS_ENABLED=true in .env.",
        }

    c = get_collector()
    healthy = c.check_health()
    jobs = c.list_jobs() if healthy else []
    return {
        "enabled": True,
        "url": settings.prometheus_url,
        "healthy": healthy,
        "jobs_discovered": jobs,
    }


@router.get("/prometheus/jobs")
def prometheus_jobs():
    """List all job label values currently known to Prometheus."""
    if not settings.prometheus_enabled:
        raise HTTPException(status_code=503, detail="Prometheus integration is disabled.")
    jobs = get_collector().list_jobs()
    return {"jobs": jobs}


# ── On-demand scrape ──────────────────────────────────────────────────────────

@router.post("/prometheus/scrape/{job}")
def prometheus_scrape_job(job: str):
    """
    Immediately scrape a single Prometheus job and inject the resulting
    metric snapshot into the detection and health-scoring pipeline.
    """
    if not settings.prometheus_enabled:
        raise HTTPException(status_code=503, detail="Prometheus integration is disabled.")

    c = get_collector()
    snap = c.scrape_job(job, environment=settings.prometheus_environment)

    _inject_metric(snap)

    return {
        "status": "scraped",
        "job": job,
        "snapshot": snap,
    }


# ── Push ingest ───────────────────────────────────────────────────────────────

@router.post("/ingest/prometheus")
def ingest_prometheus_push(
    payload: list[dict] = Body(
        ...,
        examples=[
            [
                {
                    "service": "api-gateway",
                    "environment": "production",
                    "latency_p99_ms": 320.5,
                    "error_rate_pct": 1.2,
                    "request_volume": 2400,
                    "cpu_pct": 65.0,
                    "memory_pct": 72.1,
                }
            ]
        ],
    )
):
    """
    Accept a JSON array of metric snapshots from external Prometheus scrape
    exporters, recording scripts, or CI/CD pipelines.

    Each item must include at minimum:
      - service (str)   — maps to Prometheus job label
      - environment (str, optional)

    All numeric metric fields (latency_p99_ms, error_rate_pct, etc.) are
    optional; missing fields default to 0.
    """
    if not isinstance(payload, list):
        payload = [payload]

    now = datetime.now(timezone.utc).isoformat()
    processed = 0

    for item in payload:
        if not isinstance(item, dict) or not item.get("service"):
            continue

        snap = {
            "timestamp": item.get("timestamp") or now,
            "service": item["service"],
            "environment": item.get("environment", "production"),
            "source": "prometheus_push",
            "latency_p50_ms": float(item.get("latency_p50_ms", 0)),
            "latency_p95_ms": float(item.get("latency_p95_ms", 0)),
            "latency_p99_ms": float(item.get("latency_p99_ms", 0)),
            "error_rate_pct": float(item.get("error_rate_pct", 0)),
            "request_volume": int(item.get("request_volume", 0)),
            "cpu_pct": float(item.get("cpu_pct", 0)),
            "memory_pct": float(item.get("memory_pct", 0)),
            "status_codes": item.get("status_codes", {}),
            "deployment_event": item.get("deployment_event"),
        }

        _inject_metric(snap)
        processed += 1

    return {"status": "accepted", "snapshots_processed": processed}


# ── Internal helper ───────────────────────────────────────────────────────────

def _inject_metric(snap: dict) -> None:
    """
    Push a metric snapshot through the full processing pipeline:
    storage → health scoring → anomaly detection → correlation.
    """
    svc = snap["service"]
    store_metric(snap)
    health_scorer.record_snapshot(svc, snap)
    anomaly_detector.push_metric(svc, snap)

    detected = anomaly_detector.detect_anomalies(svc, snap)
    for ano in detected:
        correlator.push_anomaly(ano)
        health_scorer.record_anomaly(svc, ano)
