from fastapi import APIRouter
from scoring import health_scorer
from simulator.scenarios import SERVICES
from correlation import correlator

router = APIRouter(prefix="/events", tags=["events"])

_events_store: list[dict] = []


def store_event(event: dict):
    _events_store.append(event)
    if len(_events_store) > 200:
        _events_store.pop(0)


@router.get("")
def list_events(limit: int = 50):
    return _events_store[-limit:]


@router.get("/summary/system")
def system_summary():
    health = health_scorer.compute_system_health(SERVICES)
    incidents = correlator.get_all_incidents()
    active = [i for i in incidents if i["status"] == "active"]
    critical = [i for i in active if i["severity"] == "critical"]
    return {
        **health,
        "active_incident_count": len(active),
        "critical_incident_count": len(critical),
    }
