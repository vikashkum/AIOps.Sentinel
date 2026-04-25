from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/anomalies", tags=["anomalies"])

_anomalies_store: list[dict] = []
MAX_ANOMALIES = 500


def store_anomaly(anomaly: dict):
    _anomalies_store.append(anomaly)
    if len(_anomalies_store) > MAX_ANOMALIES:
        _anomalies_store.pop(0)


@router.get("")
def list_anomalies(
    limit: int = Query(50, ge=1, le=200),
    service: Optional[str] = None,
    severity: Optional[str] = None,
):
    filtered = _anomalies_store
    if service:
        filtered = [a for a in filtered if a["service"] == service]
    if severity:
        filtered = [a for a in filtered if a["severity"] == severity.lower()]
    return filtered[-limit:]


@router.get("/{service}")
def service_anomalies(service: str, limit: int = Query(50, ge=1, le=200)):
    return [a for a in _anomalies_store if a["service"] == service][-limit:]
