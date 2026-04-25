from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/metrics", tags=["metrics"])

# In-memory metrics store (ring buffer per service)
_metrics_store: dict[str, list[dict]] = {}
MAX_PER_SERVICE = 300


def store_metric(snapshot: dict):
    svc = snapshot["service"]
    if svc not in _metrics_store:
        _metrics_store[svc] = []
    _metrics_store[svc].append(snapshot)
    if len(_metrics_store[svc]) > MAX_PER_SERVICE:
        _metrics_store[svc].pop(0)


def get_store() -> dict:
    return _metrics_store


@router.get("")
def get_metrics(
    limit: int = Query(60, ge=1, le=300),
    service: Optional[str] = None,
):
    if service:
        return _metrics_store.get(service, [])[-limit:]

    result = {}
    for svc, records in _metrics_store.items():
        result[svc] = records[-limit:]
    return result


@router.get("/{service}")
def get_service_metrics(service: str, limit: int = Query(60, ge=1, le=300)):
    return _metrics_store.get(service, [])[-limit:]
