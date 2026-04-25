import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from config import settings
from models.database import init_db
from simulator import engine as sim_engine
from simulator.scenarios import SERVICES, INFRA_HOSTS
from detection import anomaly_detector
from correlation import correlator
from scoring import health_scorer
from ai import groq_client, nlg_fallback, rca_engine, action_recommender
from collectors import windows_collector as wc

from api.routes import simulate, metrics, logs, incidents, services, anomalies, events
from api.routes.ingest import router as ingest_router
from api.routes.infrastructure import router as infra_router
from api.routes.prometheus import router as prometheus_router
from api.routes.loki import router as loki_router
from api.routes.metrics import store_metric
from api.routes.logs import store_logs
from api.routes.anomalies import store_anomaly
from api.routes.events import store_event
from api.routes.prometheus import _inject_metric as prometheus_inject_metric
from api.routes.loki import _inject_logs as loki_inject_logs


async def simulation_loop():
    """Background task: microservice simulation, anomaly detection, correlation, AI enrichment."""
    while True:
        try:
            if simulate.is_running():
                tick = sim_engine.generate_all_services()

                for svc, data in tick.items():
                    snap = data["metrics"]
                    log_entries = data["logs"]

                    store_metric(snap)
                    store_logs(log_entries)
                    health_scorer.record_snapshot(svc, snap)
                    anomaly_detector.push_metric(svc, snap)

                    detected = anomaly_detector.detect_anomalies(svc, snap)
                    for ano in detected:
                        store_anomaly(ano)
                        correlator.push_anomaly(ano)
                        health_scorer.record_anomaly(svc, ano)

                    dep_event = snap.get("deployment_event")
                    if dep_event:
                        ev = {
                            "event_id": f"evt-{uuid.uuid4().hex[:8]}",
                            "timestamp": snap["timestamp"],
                            "event_type": dep_event.get("type", "deployment"),
                            "service": svc,
                            "version": dep_event.get("version"),
                            "description": f"Deployed {svc} {dep_event.get('version', '')}",
                            "triggered_by": "simulator",
                        }
                        store_event(ev)
                        correlator.push_event(ev)

                new_incidents = correlator.correlate_and_group()
                for inc in new_incidents:
                    if inc.get("ai_summary") is None:
                        summary = groq_client.generate_summary(inc)
                        if not summary:
                            summary = nlg_fallback.generate_summary(inc)
                        rca = rca_engine.suggest_root_causes(inc)
                        actions = action_recommender.recommend_actions(rca)
                        svc_scores = {
                            s: health_scorer.compute_service_health(s)["health_score"]
                            for s in inc.get("affected_services", [])
                        }
                        correlator.update_incident_ai(
                            inc["incident_id"], summary, rca, actions, svc_scores
                        )

        except Exception as e:
            print(f"[simulation_loop] Error: {e}")

        await asyncio.sleep(settings.simulation_interval_seconds)


async def infra_simulation_loop():
    """Background task: Windows VM and IIS infrastructure simulation."""
    while True:
        try:
            if simulate.is_running():
                infra_tick = sim_engine.generate_all_infra()

                for host, data in infra_tick.items():
                    snap = data["snapshot"]
                    win_events = data["win_events"]
                    iis_logs = data["iis_logs"]

                    wc.push_infra_snapshot(host, snap)
                    health_scorer.record_snapshot(host, {
                        "cpu_pct": snap.get("cpu_pct", 0),
                        "memory_pct": snap.get("memory_pct", 0),
                        "error_rate_pct": snap.get("error_rate_5xx_pct", 0),
                        "latency_p99_ms": snap.get("latency_p99_ms", 0),
                    })

                    for ev in win_events:
                        wc.push_win_event(host, ev)

                    if iis_logs:
                        wc.push_iis_raw(iis_logs)

                    # Detect anomalies on infra hosts
                    if snap.get("error_rate_5xx_pct", 0) > 5 or snap.get("cpu_pct", 0) > 85 or snap.get("memory_pct", 0) > 88 or snap.get("disk_pct", 0) > 90 or snap.get("app_pool_status") == "stopped":
                        ano = _build_infra_anomaly(host, snap)
                        if ano:
                            store_anomaly(ano)
                            correlator.push_anomaly(ano)
                            health_scorer.record_anomaly(host, ano)

        except Exception as e:
            print(f"[infra_simulation_loop] Error: {e}")

        await asyncio.sleep(settings.simulation_interval_seconds)


def _build_infra_anomaly(host: str, snap: dict) -> dict | None:
    """Build an anomaly record from a degraded infra snapshot."""
    if snap.get("app_pool_status") == "stopped":
        return {
            "anomaly_id": f"ano-{uuid.uuid4().hex[:10]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": host,
            "metric": "app_pool_status",
            "value": 0,
            "baseline_value": 1,
            "deviation_pct": 100.0,
            "severity": "critical",
            "detection_method": "threshold",
        }
    err = snap.get("error_rate_5xx_pct", 0)
    if err > 10:
        return {
            "anomaly_id": f"ano-{uuid.uuid4().hex[:10]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": host,
            "metric": "error_rate_5xx_pct",
            "value": round(err, 2),
            "baseline_value": 0.2,
            "deviation_pct": round((err - 0.2) / 0.2 * 100, 1),
            "severity": "critical" if err > 20 else "warning",
            "detection_method": "threshold",
        }
    disk = snap.get("disk_pct", 0)
    if disk > 90:
        return {
            "anomaly_id": f"ano-{uuid.uuid4().hex[:10]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": host,
            "metric": "disk_pct",
            "value": round(disk, 1),
            "baseline_value": 55.0,
            "deviation_pct": round((disk - 55) / 55 * 100, 1),
            "severity": "critical" if disk > 95 else "warning",
            "detection_method": "threshold",
        }
    return None


async def prometheus_scrape_loop():
    """Phase 2A — Background task: scrape real Prometheus metrics on a schedule."""
    import asyncio as _asyncio
    from collectors.prometheus_collector import PrometheusCollector

    collector = PrometheusCollector(base_url=settings.prometheus_url)
    print(f"[prometheus_scrape_loop] Starting — target: {settings.prometheus_url}")

    while True:
        try:
            # Determine job list: explicit config wins, else auto-discover
            if settings.prometheus_jobs.strip():
                jobs = [j.strip() for j in settings.prometheus_jobs.split(",") if j.strip()]
            else:
                jobs = await _asyncio.to_thread(collector.list_jobs)

            if jobs:
                snapshots = await _asyncio.to_thread(
                    collector.scrape_all_jobs, jobs, settings.prometheus_environment
                )
                for snap in snapshots.values():
                    prometheus_inject_metric(snap)
        except Exception as exc:
            print(f"[prometheus_scrape_loop] Error: {exc}")

        await _asyncio.sleep(settings.prometheus_scrape_interval_seconds)


async def loki_scrape_loop():
    """Phase 2B — Background task: pull real Loki logs on a schedule."""
    import asyncio as _asyncio
    from collectors.loki_collector import LokiCollector

    collector = LokiCollector(base_url=settings.loki_url)
    print(f"[loki_scrape_loop] Starting — target: {settings.loki_url}")

    while True:
        try:
            if settings.loki_jobs.strip():
                jobs = [j.strip() for j in settings.loki_jobs.split(",") if j.strip()]
            else:
                jobs = await _asyncio.to_thread(collector.list_jobs)

            if jobs:
                results = await _asyncio.to_thread(
                    collector.scrape_all_jobs,
                    jobs,
                    settings.loki_lookback_seconds,
                    settings.loki_limit_per_job,
                )
                for svc, entries in results.items():
                    loki_inject_logs(svc, entries)
        except Exception as exc:
            print(f"[loki_scrape_loop] Error: {exc}")

        await _asyncio.sleep(settings.loki_scrape_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    anomaly_detector.ensure_models_trained()
    svc_loop = asyncio.create_task(simulation_loop())
    infra_loop = asyncio.create_task(infra_simulation_loop())

    # Phase 2A/2B — real data integrations (only started when enabled)
    optional_tasks = []
    if settings.prometheus_enabled:
        optional_tasks.append(asyncio.create_task(prometheus_scrape_loop()))
        print("[Phase 2A] Prometheus scrape loop started.")
    if settings.loki_enabled:
        optional_tasks.append(asyncio.create_task(loki_scrape_loop()))
        print("[Phase 2B] Loki scrape loop started.")

    print("AIOps Sentinel backend started.")
    yield

    svc_loop.cancel()
    infra_loop.cancel()
    for t in optional_tasks:
        t.cancel()
    for t in [svc_loop, infra_loop, *optional_tasks]:
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="AIOps Sentinel API",
    description="AI-Driven IT System Observability — Microservices + Windows/IIS Infrastructure",
    version="2.0.0",
    lifespan=lifespan,
)

# Expose /metrics for Prometheus scraping
Instrumentator().instrument(app).expose(app, include_in_schema=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Microservice routes
app.include_router(simulate.router)
app.include_router(metrics.router)
app.include_router(logs.router)
app.include_router(incidents.router)
app.include_router(services.router)
app.include_router(anomalies.router)
app.include_router(events.router)

# Infrastructure routes
app.include_router(ingest_router)
app.include_router(infra_router)

# Phase 2A/2B — Prometheus & Loki integration routes
app.include_router(prometheus_router)
app.include_router(loki_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/summary/system")
def system_summary():
    health = health_scorer.compute_system_health(SERVICES)
    all_incidents = correlator.get_all_incidents()
    active = [i for i in all_incidents if i["status"] == "active"]
    critical = [i for i in active if i["severity"] == "critical"]

    # Infra summary
    all_snaps = wc.get_all_latest()
    infra_scores = []
    for snap in all_snaps.values():
        from api.routes.infrastructure import _compute_host_score
        infra_scores.append(_compute_host_score(snap))
    infra_health = round(sum(infra_scores) / len(infra_scores), 1) if infra_scores else 100.0

    return {
        **health,
        "active_incident_count": len(active),
        "critical_incident_count": len(critical),
        "infra_health_score": infra_health,
        "infra_hosts_monitored": len(all_snaps),
        "prometheus_enabled": settings.prometheus_enabled,
        "loki_enabled": settings.loki_enabled,
    }
