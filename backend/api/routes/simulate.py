from fastapi import APIRouter
from pydantic import BaseModel
from simulator import engine as sim_engine
from simulator.scenarios import SCENARIOS, INFRA_SCENARIOS
from correlation import correlator
from scoring import health_scorer
from collectors import windows_collector as wc

router = APIRouter(prefix="/simulate", tags=["simulate"])

_simulation_running = False


class ScenarioRequest(BaseModel):
    scenario: str


class InfraScenarioRequest(BaseModel):
    scenario: str


@router.post("/start")
def start_simulation():
    global _simulation_running
    _simulation_running = True
    return {
        "status": "simulation started",
        "scenario": sim_engine.get_active_scenario(),
        "infra_scenario": sim_engine.get_active_infra_scenario(),
    }


@router.post("/stop")
def stop_simulation():
    global _simulation_running
    _simulation_running = False
    return {"status": "simulation stopped"}


@router.post("/scenario")
def set_scenario(req: ScenarioRequest):
    if req.scenario not in SCENARIOS:
        return {"error": f"Unknown scenario. Valid: {list(SCENARIOS.keys())}"}
    sim_engine.set_scenario(req.scenario)
    return {"status": "scenario set", "scenario": req.scenario}


@router.post("/infra/scenario")
def set_infra_scenario(req: InfraScenarioRequest):
    if req.scenario not in INFRA_SCENARIOS:
        return {"error": f"Unknown infra scenario. Valid: {list(INFRA_SCENARIOS.keys())}"}
    sim_engine.set_infra_scenario(req.scenario)
    return {"status": "infra scenario set", "scenario": req.scenario}


@router.post("/reset")
def reset_simulation():
    sim_engine.set_scenario("normal")
    sim_engine.set_infra_scenario("normal")
    correlator.reset_all()
    health_scorer.reset_scores()
    wc.reset_infra()
    return {"status": "reset complete"}


@router.get("/status")
def simulation_status():
    return {
        "running": _simulation_running,
        "active_scenario": sim_engine.get_active_scenario(),
        "available_scenarios": list(SCENARIOS.keys()),
        "active_infra_scenario": sim_engine.get_active_infra_scenario(),
        "available_infra_scenarios": list(INFRA_SCENARIOS.keys()),
    }


def is_running() -> bool:
    return _simulation_running
