from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from correlation import correlator

router = APIRouter(prefix="/incidents", tags=["incidents"])


class StatusUpdate(BaseModel):
    status: str  # active / acknowledged / resolved


@router.get("")
def list_incidents():
    return correlator.get_all_incidents()


@router.get("/{incident_id}")
def get_incident(incident_id: str):
    inc = correlator.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@router.patch("/{incident_id}")
def update_incident(incident_id: str, body: StatusUpdate):
    valid = {"active", "acknowledged", "resolved"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")
    updated = correlator.update_incident_status(incident_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"incident_id": incident_id, "status": body.status}
