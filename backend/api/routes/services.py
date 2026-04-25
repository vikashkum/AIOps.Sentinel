from fastapi import APIRouter
from scoring import health_scorer
from simulator.scenarios import SERVICES
from correlation import correlator

router = APIRouter(prefix="/services", tags=["services"])


@router.get("")
def list_services():
    return health_scorer.compute_system_health(SERVICES)


@router.get("/{service}/health")
def service_health(service: str):
    if service not in SERVICES:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown service: {service}")
    return health_scorer.compute_service_health(service)
