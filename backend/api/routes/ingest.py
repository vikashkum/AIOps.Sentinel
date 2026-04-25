"""
/ingest endpoints — receive real telemetry from PowerShell agents running on Windows VMs.
All endpoints accept JSON posted by aiops-agent.ps1.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from collectors import windows_collector as wc
from collectors.iis_log_parser import aggregate_iis_entries
from detection import anomaly_detector
from scoring import health_scorer

router = APIRouter(prefix="/ingest", tags=["ingest"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class WindowsMetricPayload(BaseModel):
    host: str
    host_type: str = "windows"
    environment: str = "production"
    timestamp: Optional[str] = None
    cpu_pct: float
    memory_pct: float
    disk_pct: float
    bytes_sent_mb: float = 0.0
    bytes_recv_mb: float = 0.0
    requests_per_sec: float = 0.0
    active_connections: int = 0
    error_rate_5xx_pct: float = 0.0
    latency_p99_ms: float = 0.0
    app_pool_status: str = "unknown"
    worker_process_count: int = 0
    sql_connections: Optional[int] = None
    sql_queries_per_sec: Optional[float] = None
    sql_blocked_queries: Optional[int] = None
    disk_read_mb_s: Optional[float] = None
    disk_write_mb_s: Optional[float] = None


class WindowsEventPayload(BaseModel):
    host: str
    level: str           # Information / Warning / Error / Critical
    source: str
    event_id: int
    message: str
    timestamp: Optional[str] = None


class IISLogBatchPayload(BaseModel):
    host: str
    log_content: Optional[str] = None   # raw W3C log file content (multiline)
    entries: Optional[list[dict]] = None  # pre-parsed entries from agent


class IISRawEntry(BaseModel):
    host: str
    method: str
    uri: str
    status_code: int
    time_taken_ms: int
    client_ip: str = "-"
    timestamp: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/windows")
def ingest_windows_metrics(payload: WindowsMetricPayload):
    """Receive Windows VM metrics from PowerShell agent."""
    now = datetime.now(timezone.utc).isoformat()
    snapshot = {
        **payload.model_dump(),
        "timestamp": payload.timestamp or now,
        "source": "real_agent",
    }
    wc.push_infra_snapshot(payload.host, snapshot)
    health_scorer.record_snapshot(payload.host, {
        "cpu_pct": payload.cpu_pct,
        "memory_pct": payload.memory_pct,
        "error_rate_pct": payload.error_rate_5xx_pct,
        "latency_p99_ms": payload.latency_p99_ms,
    })
    return {"status": "accepted", "host": payload.host}


@router.post("/winevent")
def ingest_windows_event(payload: WindowsEventPayload):
    """Receive Windows Event Log entry from PowerShell agent."""
    now = datetime.now(timezone.utc).isoformat()
    event = {
        **payload.model_dump(),
        "timestamp": payload.timestamp or now,
        "source_type": "real_agent",
    }
    wc.push_win_event(payload.host, event)
    return {"status": "accepted", "host": payload.host, "event_id": payload.event_id}


@router.post("/iis/batch")
def ingest_iis_log_batch(payload: IISLogBatchPayload):
    """
    Receive a batch of IIS log data.
    Accepts either raw W3C log file content or pre-parsed entry list.
    """
    from collectors.iis_log_parser import parse_w3c_file

    entries = []

    if payload.log_content:
        parsed, _ = parse_w3c_file(payload.log_content)
        for e in parsed:
            e["host"] = payload.host
        entries = parsed

    elif payload.entries:
        entries = [{**e, "host": payload.host} for e in payload.entries]

    if entries:
        wc.push_iis_raw(entries)
        agg = aggregate_iis_entries(payload.host, entries)
        if agg:
            wc.push_infra_snapshot(payload.host, agg)
            wc.push_iis_aggregation(payload.host, agg)

    return {"status": "accepted", "host": payload.host, "entries_processed": len(entries)}


@router.post("/iis/entry")
def ingest_iis_single_entry(payload: IISRawEntry):
    """Receive a single IIS request entry (for real-time streaming from agent)."""
    now = datetime.now(timezone.utc).isoformat()
    entry = {**payload.model_dump(), "timestamp": payload.timestamp or now}
    wc.push_iis_raw([entry])
    return {"status": "accepted"}
