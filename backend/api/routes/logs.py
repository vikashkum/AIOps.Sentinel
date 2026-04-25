from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/logs", tags=["logs"])

_logs_store: list[dict] = []
MAX_LOGS = 2000


def store_logs(entries: list[dict]):
    global _logs_store
    _logs_store.extend(entries)
    if len(_logs_store) > MAX_LOGS:
        _logs_store = _logs_store[-MAX_LOGS:]


def get_store() -> list[dict]:
    return _logs_store


@router.get("")
def get_logs(
    limit: int = Query(100, ge=1, le=500),
    service: Optional[str] = None,
    level: Optional[str] = None,
):
    filtered = _logs_store
    if service:
        filtered = [l for l in filtered if l["service"] == service]
    if level:
        filtered = [l for l in filtered if l["level"] == level.upper()]
    return filtered[-limit:]


@router.get("/{service}")
def get_service_logs(
    service: str,
    limit: int = Query(100, ge=1, le=500),
    level: Optional[str] = None,
):
    filtered = [l for l in _logs_store if l["service"] == service]
    if level:
        filtered = [l for l in filtered if l["level"] == level.upper()]
    return filtered[-limit:]
