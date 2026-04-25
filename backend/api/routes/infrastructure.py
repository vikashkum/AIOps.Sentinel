"""
/infrastructure endpoints — infrastructure health, IIS metrics, Windows events.
Serves both simulated and real agent data from the same store.
"""
from fastapi import APIRouter
from typing import Optional
from collectors import windows_collector as wc
from simulator.scenarios import INFRA_SCENARIOS
from simulator import engine as sim_engine

router = APIRouter(prefix="/infrastructure", tags=["infrastructure"])


@router.get("")
def list_infrastructure():
    """All known hosts with their latest snapshot."""
    return {
        "hosts": wc.get_all_latest(),
        "known_hosts": wc.get_known_hosts(),
    }


@router.get("/hosts")
def list_hosts():
    return wc.get_known_hosts()


@router.get("/{host}/health")
def host_health(host: str):
    snap = wc.get_latest_snapshot(host)
    if not snap:
        return {"error": f"No data for host {host}"}

    score = _compute_host_score(snap)
    return {
        "host": host,
        "health_score": score,
        "status": _score_to_status(score),
        "latest": snap,
        "win_events": wc.get_win_events(host=host, limit=10),
    }


@router.get("/{host}/metrics")
def host_metrics(host: str, limit: int = 60):
    return {
        "host": host,
        "snapshots": wc.get_snapshots(host, limit=limit),
    }


@router.get("/{host}/iis-logs")
def host_iis_logs(host: str, limit: int = 100):
    return {
        "host": host,
        "entries": wc.get_iis_raw(host=host, limit=limit),
    }


@router.get("/events/windows")
def all_win_events(host: Optional[str] = None, limit: int = 100):
    return {
        "events": wc.get_win_events(host=host, limit=limit)
    }


@router.get("/summary")
def infra_summary():
    """System-wide infrastructure health summary."""
    all_snaps = wc.get_all_latest()
    if not all_snaps:
        return {"hosts": [], "system_infra_health": 100, "status": "no_data"}

    scores = []
    host_summaries = []
    for host, snap in all_snaps.items():
        score = _compute_host_score(snap)
        scores.append(score)
        host_summaries.append({
            "host": host,
            "health_score": score,
            "status": _score_to_status(score),
            "app_pool_status": snap.get("app_pool_status", "unknown"),
            "cpu_pct": snap.get("cpu_pct"),
            "memory_pct": snap.get("memory_pct"),
            "disk_pct": snap.get("disk_pct"),
            "error_rate_5xx_pct": snap.get("error_rate_5xx_pct"),
            "requests_per_sec": snap.get("requests_per_sec"),
        })

    system_score = round(sum(scores) / len(scores), 1) if scores else 100.0
    return {
        "system_infra_health": system_score,
        "system_infra_status": _score_to_status(system_score),
        "hosts": sorted(host_summaries, key=lambda h: h["health_score"]),
        "active_infra_scenario": sim_engine.get_active_infra_scenario(),
        "available_infra_scenarios": list(INFRA_SCENARIOS.keys()),
    }


def _compute_host_score(snap: dict) -> float:
    penalty = 0.0

    cpu = snap.get("cpu_pct", 0)
    if cpu > 90: penalty += 30
    elif cpu > 75: penalty += 15
    elif cpu > 60: penalty += 5

    mem = snap.get("memory_pct", 0)
    if mem > 92: penalty += 30
    elif mem > 80: penalty += 15
    elif mem > 70: penalty += 5

    disk = snap.get("disk_pct", 0)
    if disk > 95: penalty += 35
    elif disk > 85: penalty += 20
    elif disk > 75: penalty += 8

    err = snap.get("error_rate_5xx_pct", 0)
    if err > 20: penalty += 40
    elif err > 5: penalty += 20
    elif err > 1: penalty += 8

    if snap.get("app_pool_status") == "stopped": penalty += 45
    if snap.get("app_pool_status") == "recycling": penalty += 10

    blocked = snap.get("sql_blocked_queries", 0)
    if blocked and blocked > 10: penalty += 20
    elif blocked and blocked > 3: penalty += 8

    return round(max(0.0, min(100.0, 100.0 - penalty)), 1)


def _score_to_status(score: float) -> str:
    if score >= 85: return "healthy"
    if score >= 60: return "degraded"
    if score >= 35: return "critical"
    return "down"
