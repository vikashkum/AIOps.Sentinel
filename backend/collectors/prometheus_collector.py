"""
Phase 2A — Real Prometheus Scrape Integration
Polls a live Prometheus HTTP API and maps the results into AIOps Sentinel's
internal metric schema so they flow through the same anomaly detection and
correlation pipeline as simulated data.

Configuration (via config.py / .env):
    PROMETHEUS_URL       — base URL, e.g. http://prometheus:9090
    PROMETHEUS_ENABLED   — set to "true" to activate (default: false)
    PROMETHEUS_SCRAPE_INTERVAL_SECONDS — how often to pull (default: 15)

Metric mapping strategy
-----------------------
Prometheus stores raw time-series.  We query a fixed set of PromQL expressions
that map onto the fields our anomaly detector and health scorer expect:

    latency_p99_ms      — histogram_quantile(0.99, ...) for http_request_duration
    latency_p95_ms      — histogram_quantile(0.95, ...)
    latency_p50_ms      — histogram_quantile(0.50, ...)
    error_rate_pct      — rate(http_requests_total{status=~"5.."}[1m]) /
                          rate(http_requests_total[1m]) * 100
    request_volume      — rate(http_requests_total[1m]) * 60   (per-minute)
    cpu_pct             — 100 - (avg by(job)(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)
    memory_pct          — (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100

All of these are standard node_exporter / instrumented-app metrics that exist
in any Prometheus-monitored stack.  If a metric is missing in a target
environment the field defaults to 0/null — the system keeps running.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# PromQL queries keyed by our internal field name.
# {job} is replaced with the Prometheus job label at query time.
_QUERIES: dict[str, str] = {
    "latency_p99_ms": (
        "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket"
        '{{job="{job}"}}[1m])) by (le)) * 1000'
    ),
    "latency_p95_ms": (
        "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket"
        '{{job="{job}"}}[1m])) by (le)) * 1000'
    ),
    "latency_p50_ms": (
        "histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket"
        '{{job="{job}"}}[1m])) by (le)) * 1000'
    ),
    "error_rate_pct": (
        'sum(rate(http_requests_total{{job="{job}",status=~"5.."}}[1m])) / '
        'sum(rate(http_requests_total{{job="{job}"}}[1m])) * 100'
    ),
    "request_volume": (
        'sum(rate(http_requests_total{{job="{job}"}}[1m])) * 60'
    ),
    "cpu_pct": (
        '(1 - avg(rate(node_cpu_seconds_total{{job="{job}",mode="idle"}}[1m]))) * 100'
    ),
    "memory_pct": (
        "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100"
    ),
}


class PrometheusCollector:
    """
    Fetches metrics for a set of Prometheus job labels and converts them
    into the dict format expected by store_metric() and anomaly_detector.push_metric().
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._url = base_url.rstrip("/")
        self._timeout = timeout

    # ── Low-level query ─────────────────────────────────────────────────────

    def _instant_query(self, promql: str) -> Optional[float]:
        """
        Execute an instant PromQL query.  Returns the first scalar value or None.
        Uses a plain httpx.Client (synchronous) — called from an asyncio thread
        via asyncio.to_thread in the scrape loop.
        """
        try:
            resp = httpx.get(
                f"{self._url}/api/v1/query",
                params={"query": promql},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", {}).get("result", [])
            if results:
                value = results[0].get("value", [None, None])[1]
                if value is not None:
                    f = float(value)
                    return None if (f != f) else round(f, 3)   # NaN guard
        except Exception as exc:
            logger.debug("Prometheus instant query failed: %s — %s", promql[:60], exc)
        return None

    def _range_query(
        self,
        promql: str,
        start: str,
        end: str,
        step: str = "15s",
    ) -> list[dict]:
        """
        Execute a range PromQL query.
        Returns list of {timestamp, value} dicts for the first matching series.
        """
        try:
            resp = httpx.get(
                f"{self._url}/api/v1/query_range",
                params={"query": promql, "start": start, "end": end, "step": step},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", {}).get("result", [])
            if results:
                return [
                    {"timestamp": ts, "value": float(val)}
                    for ts, val in results[0].get("values", [])
                    if val != "NaN"
                ]
        except Exception as exc:
            logger.debug("Prometheus range query failed: %s — %s", promql[:60], exc)
        return []

    # ── Target discovery ────────────────────────────────────────────────────

    def list_jobs(self) -> list[str]:
        """Return all active job labels known to Prometheus."""
        try:
            resp = httpx.get(
                f"{self._url}/api/v1/label/job/values",
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as exc:
            logger.warning("Could not list Prometheus jobs: %s", exc)
            return []

    def check_health(self) -> bool:
        """Ping Prometheus /-/healthy.  Returns True if reachable and healthy."""
        try:
            resp = httpx.get(f"{self._url}/-/healthy", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    # ── Metric snapshot ─────────────────────────────────────────────────────

    def scrape_job(self, job: str, environment: str = "production") -> dict:
        """
        Fetch all tracked metrics for a single Prometheus job label.
        Returns a metric snapshot dict compatible with store_metric() and
        anomaly_detector.push_metric().
        """
        now = datetime.now(timezone.utc).isoformat()
        snapshot: dict = {
            "timestamp": now,
            "service": job,
            "environment": environment,
            "source": "prometheus",
            # defaults – overwritten if Prometheus has data
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "latency_p99_ms": 0.0,
            "error_rate_pct": 0.0,
            "request_volume": 0,
            "cpu_pct": 0.0,
            "memory_pct": 0.0,
            "status_codes": {},
            "deployment_event": None,
        }

        for field, query_template in _QUERIES.items():
            promql = query_template.format(job=job)
            value = self._instant_query(promql)
            if value is not None:
                if field == "request_volume":
                    snapshot[field] = int(value)
                else:
                    snapshot[field] = value

        return snapshot

    def scrape_all_jobs(
        self,
        jobs: list[str],
        environment: str = "production",
    ) -> dict[str, dict]:
        """
        Scrape every job in *jobs* and return {job_name: snapshot}.
        Skips jobs that produce no data.
        """
        results: dict[str, dict] = {}
        for job in jobs:
            try:
                snap = self.scrape_job(job, environment=environment)
                results[job] = snap
            except Exception as exc:
                logger.warning("Failed to scrape Prometheus job '%s': %s", job, exc)
        return results

    # ── Historical backfill ─────────────────────────────────────────────────

    def fetch_history(
        self,
        job: str,
        field: str,
        start: str,
        end: str,
        step: str = "15s",
    ) -> list[dict]:
        """
        Fetch a time-range of a single field for a job.
        Useful for priming the anomaly detector's baseline window.

        Returns list of {timestamp (ISO-8601), value (float)} dicts.
        """
        query_template = _QUERIES.get(field)
        if not query_template:
            logger.warning("Unknown field '%s' — no PromQL template available.", field)
            return []

        promql = query_template.format(job=job)
        raw = self._range_query(promql, start=start, end=end, step=step)

        return [
            {
                "timestamp": datetime.fromtimestamp(r["timestamp"], tz=timezone.utc).isoformat(),
                "value": r["value"],
            }
            for r in raw
        ]
