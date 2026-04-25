"""
Phase 2B — Real Loki Log Ingestion
Queries a live Grafana Loki instance and converts the returned log streams
into AIOps Sentinel's internal log schema so they flow through the same
anomaly detection, health scoring, and AI summarisation pipeline as
simulated logs.

Configuration (via config.py / .env):
    LOKI_URL               — base URL, e.g. http://loki:3100
    LOKI_ENABLED           — set to "true" to activate (default: false)
    LOKI_SCRAPE_INTERVAL_SECONDS — how often to pull new logs (default: 15)
    LOKI_LOOKBACK_SECONDS  — how far back to query on each pull (default: 30)

Log mapping strategy
--------------------
Loki stores logs as streams of plain text with label selectors.  The
collector queries:

    {job="<service>"}

for each tracked service and maps each log line into our internal log dict:

    {
        "timestamp": ISO-8601 string,
        "service":   str  (from Loki label or provided job name),
        "level":     str  (parsed from line — INFO/WARN/ERROR/CRITICAL),
        "message":   str  (the raw log line),
        "trace_id":  str | None,
        "request_id": str | None,
        "latency_ms": int | None,
        "status_code": int | None,
        "source":    "loki",
    }

Level detection matches common log frameworks (Python logging, Log4j, Logrus,
Zap, slog) via case-insensitive prefix / keyword scan.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Regex patterns used to extract structured fields from free-text log lines
_TRACE_RE = re.compile(r"trace[_-]?id[=:\s]+([a-fA-F0-9\-]+)", re.IGNORECASE)
_REQUEST_RE = re.compile(r"request[_-]?id[=:\s]+([a-zA-Z0-9\-]+)", re.IGNORECASE)
_LATENCY_RE = re.compile(r"(\d+)\s*ms", re.IGNORECASE)
_STATUS_RE = re.compile(r"\b([1-5]\d{2})\b")

_LEVEL_KEYWORDS = {
    "critical": "CRITICAL",
    "crit": "CRITICAL",
    "fatal": "CRITICAL",
    "error": "ERROR",
    "err": "ERROR",
    "warn": "WARNING",
    "warning": "WARNING",
    "info": "INFO",
    "information": "INFO",
    "debug": "DEBUG",
    "trace": "DEBUG",
}


def _detect_level(line: str) -> str:
    """Best-effort log level extraction from a free-text log line."""
    lower = line.lower()
    for keyword, level in _LEVEL_KEYWORDS.items():
        if keyword in lower:
            return level
    return "INFO"


def _extract_fields(line: str) -> dict:
    """Extract structured fields from a free-text log line."""
    fields: dict = {}

    m = _TRACE_RE.search(line)
    if m:
        fields["trace_id"] = m.group(1)

    m = _REQUEST_RE.search(line)
    if m:
        fields["request_id"] = m.group(1)

    # Latency: take the first numeric ms value
    m = _LATENCY_RE.search(line)
    if m:
        fields["latency_ms"] = int(m.group(1))

    # Status code: look for a 3-digit HTTP status-like number
    for m in _STATUS_RE.finditer(line):
        code = int(m.group(1))
        if 100 <= code <= 599:
            fields["status_code"] = code
            break

    return fields


class LokiCollector:
    """
    Queries a Grafana Loki instance for log streams and converts them into
    AIOps Sentinel's internal log format.
    """

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._url = base_url.rstrip("/")
        self._timeout = timeout
        # Per-service cursor: last nanosecond timestamp seen
        self._cursors: dict[str, int] = {}

    # ── Health check ────────────────────────────────────────────────────────

    def check_health(self) -> bool:
        """Ping Loki /ready.  Returns True if reachable."""
        try:
            resp = httpx.get(f"{self._url}/ready", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    # ── Label / stream discovery ─────────────────────────────────────────────

    def list_jobs(self) -> list[str]:
        """Return all values of the 'job' label known to Loki."""
        try:
            resp = httpx.get(
                f"{self._url}/loki/api/v1/label/job/values",
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as exc:
            logger.warning("Could not list Loki job labels: %s", exc)
            return []

    # ── Log query ───────────────────────────────────────────────────────────

    def query_range(
        self,
        logql: str,
        start_ns: int,
        end_ns: int,
        limit: int = 500,
        direction: str = "forward",
    ) -> list[dict]:
        """
        Execute a Loki query_range call.
        Returns list of raw stream entries as {timestamp_ns, line, labels} dicts.
        """
        try:
            resp = httpx.get(
                f"{self._url}/loki/api/v1/query_range",
                params={
                    "query": logql,
                    "start": str(start_ns),
                    "end": str(end_ns),
                    "limit": limit,
                    "direction": direction,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            entries: list[dict] = []
            for stream in data.get("data", {}).get("result", []):
                labels = stream.get("stream", {})
                for ts_ns_str, line in stream.get("values", []):
                    entries.append(
                        {
                            "timestamp_ns": int(ts_ns_str),
                            "line": line,
                            "labels": labels,
                        }
                    )
            return entries

        except Exception as exc:
            logger.debug("Loki query_range failed: %s — %s", logql[:80], exc)
            return []

    # ── Conversion ──────────────────────────────────────────────────────────

    def _to_log_entry(self, raw: dict, service: str) -> dict:
        """Convert a raw Loki entry into AIOps Sentinel log schema."""
        ts_ns = raw["timestamp_ns"]
        dt = datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=timezone.utc)
        line: str = raw["line"]
        labels: dict = raw.get("labels", {})

        # Prefer 'level' label from Loki stream if available
        level = labels.get("level") or labels.get("severity") or _detect_level(line)
        level = level.upper()

        structured = _extract_fields(line)

        return {
            "timestamp": dt.isoformat(),
            "service": labels.get("job") or labels.get("service") or service,
            "environment": labels.get("env") or labels.get("environment") or "production",
            "level": level,
            "message": line,
            "trace_id": structured.get("trace_id"),
            "request_id": structured.get("request_id"),
            "latency_ms": structured.get("latency_ms"),
            "status_code": structured.get("status_code"),
            "source": "loki",
        }

    # ── Public scrape API ───────────────────────────────────────────────────

    def scrape_job(
        self,
        job: str,
        lookback_seconds: int = 30,
        limit: int = 500,
    ) -> list[dict]:
        """
        Fetch new log entries for a Prometheus/Loki job label since the last
        successful scrape (or *lookback_seconds* ago for the first call).

        Returns a list of log entry dicts compatible with store_logs().
        """
        now_ns = time.time_ns()
        cursor_ns = self._cursors.get(job)

        if cursor_ns is None:
            start_ns = now_ns - lookback_seconds * 1_000_000_000
        else:
            # +1 ns to avoid re-fetching the last seen entry
            start_ns = cursor_ns + 1

        logql = f'{{job="{job}"}}'
        raw_entries = self.query_range(
            logql, start_ns=start_ns, end_ns=now_ns, limit=limit
        )

        if not raw_entries:
            return []

        # Advance cursor to the latest timestamp seen
        max_ts = max(e["timestamp_ns"] for e in raw_entries)
        self._cursors[job] = max_ts

        return [self._to_log_entry(e, service=job) for e in raw_entries]

    def scrape_all_jobs(
        self,
        jobs: list[str],
        lookback_seconds: int = 30,
        limit_per_job: int = 500,
    ) -> dict[str, list[dict]]:
        """
        Scrape every job in *jobs*.
        Returns {job_name: [log_entry, ...]} — empty list if no new logs.
        """
        results: dict[str, list[dict]] = {}
        for job in jobs:
            try:
                entries = self.scrape_job(
                    job,
                    lookback_seconds=lookback_seconds,
                    limit=limit_per_job,
                )
                results[job] = entries
            except Exception as exc:
                logger.warning("Failed to scrape Loki job '%s': %s", job, exc)
                results[job] = []
        return results

    def reset_cursors(self) -> None:
        """Clear all per-job cursors (e.g. after a system reset)."""
        self._cursors.clear()
