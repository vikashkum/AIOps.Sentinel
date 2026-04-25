"""
IIS W3C log parser.
Parses standard IIS W3C extended log format lines and batches of raw log entries
sent by the PowerShell agent into our internal metric schema.
"""
import re
from datetime import datetime, timezone
from typing import Optional

# Standard W3C field order when #Fields header is present
_DEFAULT_FIELDS = [
    "date", "time", "s-ip", "cs-method", "cs-uri-stem",
    "cs-uri-query", "s-port", "cs-username", "c-ip",
    "cs(User-Agent)", "sc-status", "sc-substatus",
    "sc-win32-status", "time-taken",
]


def parse_w3c_line(line: str, fields: list[str] = None) -> Optional[dict]:
    """Parse a single W3C log line into a dict. Returns None for comment lines."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    cols = fields or _DEFAULT_FIELDS
    parts = line.split(" ")
    if len(parts) < 4:
        return None

    record = {}
    for i, col in enumerate(cols):
        record[col] = parts[i] if i < len(parts) else "-"

    try:
        ts_str = f"{record.get('date', '2000-01-01')} {record.get('time', '00:00:00')}"
        timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        timestamp = datetime.now(timezone.utc)

    try:
        status_code = int(record.get("sc-status", 0))
    except ValueError:
        status_code = 0

    try:
        time_taken_ms = int(record.get("time-taken", 0))
    except ValueError:
        time_taken_ms = 0

    return {
        "timestamp": timestamp.isoformat(),
        "method": record.get("cs-method", "GET"),
        "uri": record.get("cs-uri-stem", "/"),
        "query": record.get("cs-uri-query", "-"),
        "status_code": status_code,
        "time_taken_ms": time_taken_ms,
        "client_ip": record.get("c-ip", "-"),
        "server_ip": record.get("s-ip", "-"),
        "port": record.get("s-port", "80"),
    }


def parse_w3c_file(content: str) -> tuple[list[dict], list[str]]:
    """
    Parse a full W3C log file content string.
    Returns (parsed_entries, field_names).
    """
    lines = content.splitlines()
    fields = _DEFAULT_FIELDS
    entries = []

    for line in lines:
        if line.startswith("#Fields:"):
            fields = line.replace("#Fields:", "").strip().split(" ")
            continue
        parsed = parse_w3c_line(line, fields)
        if parsed:
            entries.append(parsed)

    return entries, fields


def aggregate_iis_entries(host: str, entries: list[dict]) -> dict:
    """
    Aggregate a batch of parsed IIS log entries into a metric snapshot.
    Returns a dict compatible with the infra_snapshots store.
    """
    if not entries:
        return {}

    total = len(entries)
    errors_5xx = sum(1 for e in entries if e["status_code"] >= 500)
    errors_4xx = sum(1 for e in entries if 400 <= e["status_code"] < 500)
    latencies = sorted(e["time_taken_ms"] for e in entries if e["time_taken_ms"] > 0)

    def percentile(data, pct):
        if not data:
            return 0
        idx = int(len(data) * pct / 100)
        return data[min(idx, len(data) - 1)]

    return {
        "host": host,
        "host_type": "iis",
        "environment": "production",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "real_agent",
        "total_requests": total,
        "error_rate_5xx_pct": round(errors_5xx / total * 100, 3) if total else 0,
        "error_rate_4xx_pct": round(errors_4xx / total * 100, 3) if total else 0,
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "latency_p99_ms": percentile(latencies, 99),
        "top_uris": _top_uris(entries),
        "top_errors": _top_errors(entries),
    }


def _top_uris(entries: list[dict], n: int = 5) -> list[dict]:
    counts: dict[str, int] = {}
    for e in entries:
        uri = e.get("uri", "/")
        counts[uri] = counts.get(uri, 0) + 1
    return [
        {"uri": k, "count": v}
        for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]
    ]


def _top_errors(entries: list[dict], n: int = 5) -> list[dict]:
    errors = [e for e in entries if e["status_code"] >= 400]
    counts: dict[str, int] = {}
    for e in errors:
        key = f"{e['status_code']} {e['uri']}"
        counts[key] = counts.get(key, 0) + 1
    return [
        {"pattern": k, "count": v}
        for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]
    ]
