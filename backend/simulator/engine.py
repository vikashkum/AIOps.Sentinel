import random
import uuid
from datetime import datetime, timezone
from faker import Faker
from simulator.scenarios import (
    SERVICES, BASELINES, SCENARIOS, LOG_TEMPLATES,
    INFRA_HOSTS, INFRA_BASELINES, INFRA_SCENARIOS,
    IIS_LOG_TEMPLATES, WIN_EVENT_TEMPLATES,
)

fake = Faker()

_active_scenario: str = "normal"
_active_infra_scenario: str = "normal"
_scenario_tick: int = 0


def set_scenario(name: str):
    global _active_scenario, _scenario_tick
    _active_scenario = name
    _scenario_tick = 0


def set_infra_scenario(name: str):
    global _active_infra_scenario
    _active_infra_scenario = name


def get_active_scenario() -> str:
    return _active_scenario


def get_active_infra_scenario() -> str:
    return _active_infra_scenario


def _jitter(value: float, pct: float = 0.08) -> float:
    return max(0.0, value * (1 + random.gauss(0, pct)))


def _apply_scenario_overrides(service: str, base: dict) -> tuple[dict, dict]:
    overrides = SCENARIOS.get(_active_scenario, {}).get(service, {})
    result = dict(base)
    for key, val in overrides.items():
        if key.endswith("_mult"):
            metric = key[:-5]
            if metric in result:
                result[metric] = result[metric] * val
        elif key.endswith("_add"):
            metric = key[:-4]
            if metric in result:
                result[metric] = min(99.0, result[metric] + val)
    return result, overrides


def _apply_infra_overrides(host: str, base: dict) -> tuple[dict, dict]:
    overrides = INFRA_SCENARIOS.get(_active_infra_scenario, {}).get(host, {})
    result = dict(base)
    for key, val in overrides.items():
        if key.endswith("_mult"):
            metric = key[:-5]
            if metric in result:
                result[metric] = result[metric] * val
        elif key.endswith("_add"):
            metric = key[:-4]
            if metric in result:
                result[metric] = min(99.9 if "pct" in metric else 9999, result[metric] + val)
        elif key.endswith("_set"):
            metric = key[:-4]
            result[metric] = val
    return result, overrides


# ── Microservice generation ────────────────────────────────────────────────────

def generate_metric_snapshot(service: str) -> dict:
    base = dict(BASELINES[service])
    result, overrides = _apply_scenario_overrides(service, base)

    vol = int(_jitter(result["request_volume"], 0.12))
    err_rate = min(99.0, _jitter(result["error_rate_pct"], 0.15))
    status_5xx_pct = overrides.get("status_5xx_pct", err_rate / 100)
    status_4xx_pct = 0.01
    status_2xx = int(vol * (1 - status_5xx_pct - status_4xx_pct))
    status_4xx = int(vol * status_4xx_pct)
    status_5xx = vol - status_2xx - status_4xx

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "environment": "production",
        "latency_p50_ms": round(_jitter(result["latency_p50_ms"]), 1),
        "latency_p95_ms": round(_jitter(result["latency_p95_ms"]), 1),
        "latency_p99_ms": round(_jitter(result["latency_p99_ms"]), 1),
        "error_rate_pct": round(err_rate, 3),
        "request_volume": vol,
        "cpu_pct": round(min(99.0, _jitter(result["cpu_pct"], 0.10)), 1),
        "memory_pct": round(min(99.0, _jitter(result["memory_pct"], 0.05)), 1),
        "status_2xx": status_2xx,
        "status_4xx": status_4xx,
        "status_5xx": status_5xx,
        "scenario": _active_scenario if _active_scenario != "normal" else None,
        "deployment_event": overrides.get("deployment_event"),
    }


def generate_log_entries(service: str, count: int = 5) -> list[dict]:
    overrides = SCENARIOS.get(_active_scenario, {}).get(service, {})
    err_mult = overrides.get("error_rate_pct_mult", 1.0)
    base_err = BASELINES[service]["error_rate_pct"]
    effective_err = min(99.0, base_err * err_mult)

    logs = []
    for _ in range(count):
        roll = random.random() * 100
        if roll < effective_err * 0.5:
            level = "CRITICAL" if effective_err > 15 else "ERROR"
        elif roll < effective_err * 2:
            level = "WARN"
        else:
            level = "INFO"

        if level in ("ERROR", "CRITICAL"):
            templates = LOG_TEMPLATES["error"] + LOG_TEMPLATES["critical"]
        elif level == "WARN":
            templates = LOG_TEMPLATES["warning"]
        else:
            templates = LOG_TEMPLATES["normal"]

        latency_val = int(BASELINES[service]["latency_p99_ms"] * err_mult * random.uniform(0.8, 1.5))
        message = (
            random.choice(templates)
            .replace("{latency}", str(latency_val))
            .replace("{svc}", random.choice([s for s in SERVICES if s != service]))
            .replace("{id}", str(random.randint(1000, 9999)))
            .replace("{n}", str(random.randint(1, 5)))
            .replace("{pct}", str(round(effective_err, 1)))
            .replace("{code}", str(random.choice([500, 502, 503, 504])))
        )

        logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "environment": "production",
            "level": level,
            "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
            "request_id": f"req-{uuid.uuid4().hex[:8]}",
            "message": message,
            "latency_ms": latency_val if level in ("WARN", "ERROR", "CRITICAL") else None,
            "status_code": 503 if level in ("ERROR", "CRITICAL") else (400 if level == "WARN" else 200),
        })
    return logs


# ── IIS / Windows VM generation ───────────────────────────────────────────────

def generate_infra_snapshot(host: str) -> dict:
    base = dict(INFRA_BASELINES[host])
    result, overrides = _apply_infra_overrides(host, base)

    app_pool = overrides.get("app_pool_status", result.get("app_pool_status", "running"))
    win_event = overrides.get("win_event")

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "host_type": "iis" if host.startswith("iis") else "windows",
        "environment": "production",
        "cpu_pct": round(min(99.9, _jitter(result["cpu_pct"], 0.10)), 1),
        "memory_pct": round(min(99.9, _jitter(result["memory_pct"], 0.05)), 1),
        "disk_pct": round(min(99.9, _jitter(result["disk_pct"], 0.02)), 1),
        "requests_per_sec": round(max(0, _jitter(result["requests_per_sec"], 0.15)), 1),
        "active_connections": int(max(0, _jitter(result["active_connections"], 0.12))),
        "error_rate_5xx_pct": round(min(100.0, _jitter(result["error_rate_5xx_pct"], 0.20)), 3),
        "latency_p99_ms": round(max(0, _jitter(result["latency_p99_ms"], 0.12)), 1),
        "app_pool_status": app_pool,
        "worker_process_count": int(max(0, result.get("worker_process_count", 0))),
        "bytes_sent_mb": round(_jitter(result["bytes_sent_mb"], 0.15), 2),
        "bytes_recv_mb": round(_jitter(result["bytes_recv_mb"], 0.15), 2),
        "scenario": _active_infra_scenario if _active_infra_scenario != "normal" else None,
        "win_event": win_event,
    }

    # SQL Server extras for win-db-01
    if host == "win-db-01":
        snapshot.update({
            "sql_connections": int(max(0, _jitter(result.get("sql_connections", 48), 0.10))),
            "sql_queries_per_sec": round(max(0, _jitter(result.get("sql_queries_per_sec", 320), 0.12)), 1),
            "sql_blocked_queries": int(max(0, result.get("sql_blocked_queries", 0))),
            "disk_read_mb_s": round(max(0, _jitter(result.get("disk_read_mb_s", 12), 0.20)), 2),
            "disk_write_mb_s": round(max(0, _jitter(result.get("disk_write_mb_s", 8), 0.20)), 2),
        })

    return snapshot


def generate_win_events(host: str, count: int = 2) -> list[dict]:
    overrides = INFRA_SCENARIOS.get(_active_infra_scenario, {}).get(host, {})
    scenario_event = overrides.get("win_event")
    err_mult = overrides.get("error_rate_5xx_pct_mult", 1.0)

    events = []

    # Always emit the scenario-specific event if present
    if scenario_event:
        events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "host": host,
            "level": scenario_event["level"],
            "source": scenario_event["source"],
            "event_id": scenario_event["event_id"],
            "message": scenario_event["message"],
        })

    # Fill remaining with template events
    template_pool = WIN_EVENT_TEMPLATES["error"] if err_mult > 10 else (
        WIN_EVENT_TEMPLATES["warning"] if err_mult > 2 else WIN_EVENT_TEMPLATES["normal"]
    )
    for _ in range(count - len(events)):
        tmpl = dict(random.choice(template_pool))
        tmpl["message"] = (
            tmpl["message"]
            .replace("{pool}", "DefaultAppPool")
            .replace("{pct}", str(random.randint(70, 95)))
        )
        events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "host": host,
            **tmpl,
        })

    return events


def generate_iis_log_entries(host: str, count: int = 8) -> list[dict]:
    overrides = INFRA_SCENARIOS.get(_active_infra_scenario, {}).get(host, {})
    err_mult = overrides.get("error_rate_5xx_pct_mult", 1.0)
    base_err = INFRA_BASELINES[host].get("error_rate_5xx_pct", 0.2)
    effective_err = min(99.0, base_err * err_mult)
    base_latency = INFRA_BASELINES[host].get("latency_p99_ms", 200)

    entries = []
    for _ in range(count):
        roll = random.random() * 100
        is_error = roll < effective_err
        template_pool = IIS_LOG_TEMPLATES["error"] if is_error else (
            IIS_LOG_TEMPLATES["warning"] if roll < effective_err * 3 else IIS_LOG_TEMPLATES["normal"]
        )
        pattern = random.choice(template_pool)
        latency = int(base_latency * err_mult * random.uniform(0.5, 2.0)) if is_error else int(_jitter(base_latency * 0.4, 0.3))
        line = pattern.replace("{latency}", str(latency))
        parts = line.split()
        status = int(parts[3]) if len(parts) > 3 else (500 if is_error else 200)

        entries.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "host": host,
            "method": parts[0] if parts else "GET",
            "uri": parts[1] if len(parts) > 1 else "/",
            "protocol": parts[2] if len(parts) > 2 else "HTTP/1.1",
            "status_code": status,
            "time_taken_ms": latency,
            "client_ip": f"10.{random.randint(0,10)}.{random.randint(0,255)}.{random.randint(1,254)}",
        })
    return entries


def generate_all_services() -> dict:
    global _scenario_tick
    _scenario_tick += 1
    return {
        svc: {
            "metrics": generate_metric_snapshot(svc),
            "logs": generate_log_entries(svc, count=random.randint(3, 8)),
        }
        for svc in SERVICES
    }


def generate_all_infra() -> dict:
    return {
        host: {
            "snapshot": generate_infra_snapshot(host),
            "win_events": generate_win_events(host, count=random.randint(1, 3)),
            "iis_logs": generate_iis_log_entries(host) if host != "win-db-01" else [],
        }
        for host in INFRA_HOSTS
    }
