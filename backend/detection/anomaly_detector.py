import os
import uuid
import numpy as np
import pandas as pd
import joblib
from datetime import datetime, timezone
from sklearn.ensemble import IsolationForest
from config import settings, BASE_DIR
from simulator.scenarios import SERVICES, BASELINES

MODEL_PATH = BASE_DIR / "ml_models" / "isolation_forest.pkl"
SCALER_PATH = BASE_DIR / "ml_models" / "scaler.pkl"

FEATURES = [
    "latency_p99_ms",
    "latency_p95_ms",
    "error_rate_pct",
    "cpu_pct",
    "memory_pct",
    "request_volume",
]

_models: dict = {}   # per-service models
_scalers: dict = {}  # per-service scalers
_rolling_buffers: dict = {svc: [] for svc in SERVICES}  # last N snapshots per service


def _generate_baseline_data(service: str, n: int) -> pd.DataFrame:
    """Generate synthetic normal-traffic rows for model pre-training."""
    base = BASELINES[service]
    rows = []
    for _ in range(n):
        rows.append({
            "latency_p99_ms": max(10, np.random.normal(base["latency_p99_ms"], base["latency_p99_ms"] * 0.12)),
            "latency_p95_ms": max(10, np.random.normal(base["latency_p95_ms"], base["latency_p95_ms"] * 0.10)),
            "error_rate_pct": max(0, np.random.normal(base["error_rate_pct"], 0.15)),
            "cpu_pct": max(5, np.random.normal(base["cpu_pct"], base["cpu_pct"] * 0.10)),
            "memory_pct": max(5, np.random.normal(base["memory_pct"], base["memory_pct"] * 0.06)),
            "request_volume": max(10, np.random.normal(base["request_volume"], base["request_volume"] * 0.15)),
        })
    return pd.DataFrame(rows)


def _severity_from_score(score: float, deviation_pct: float) -> str:
    if deviation_pct > 300 or score < -0.25:
        return "critical"
    if deviation_pct > 100 or score < -0.10:
        return "warning"
    return "info"


def ensure_models_trained():
    """Pre-train and persist Isolation Forest models for all services."""
    os.makedirs(BASE_DIR / "ml_models", exist_ok=True)
    from sklearn.preprocessing import StandardScaler

    for svc in SERVICES:
        model_path = BASE_DIR / "ml_models" / f"if_{svc}.pkl"
        scaler_path = BASE_DIR / "ml_models" / f"scaler_{svc}.pkl"

        if model_path.exists() and scaler_path.exists():
            _models[svc] = joblib.load(model_path)
            _scalers[svc] = joblib.load(scaler_path)
            continue

        df = _generate_baseline_data(svc, settings.baseline_samples)
        scaler = StandardScaler().fit(df[FEATURES])
        X = scaler.transform(df[FEATURES])
        model = IsolationForest(
            contamination=settings.isolation_forest_contamination,
            random_state=42,
            n_estimators=100,
        ).fit(X)

        joblib.dump(model, model_path)
        joblib.dump(scaler, scaler_path)
        _models[svc] = model
        _scalers[svc] = scaler


def push_metric(service: str, snapshot: dict):
    """Add latest metric snapshot to the rolling buffer."""
    _rolling_buffers[service].append(snapshot)
    if len(_rolling_buffers[service]) > 60:
        _rolling_buffers[service].pop(0)


def detect_anomalies(service: str, snapshot: dict) -> list[dict]:
    """
    Run both Isolation Forest and Z-score detection on the latest snapshot.
    Returns a list of anomaly dicts (may be empty).
    """
    anomalies = []
    base = BASELINES[service]

    # --- Isolation Forest ---
    if service in _models and service in _scalers:
        try:
            row = [[snapshot.get(f, base.get(f, 0)) for f in FEATURES]]
            scaled = _scalers[service].transform(row)
            score = _models[service].score_samples(scaled)[0]
            pred = _models[service].predict(scaled)[0]

            if pred == -1:
                worst_metric = FEATURES[0]
                worst_dev = 0.0
                for f in FEATURES:
                    bval = base.get(f, 1)
                    if bval > 0:
                        dev = abs(snapshot.get(f, bval) - bval) / bval * 100
                        if dev > worst_dev:
                            worst_dev = dev
                            worst_metric = f

                bval = base.get(worst_metric, 1)
                anomalies.append({
                    "anomaly_id": f"ano-{uuid.uuid4().hex[:10]}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": service,
                    "metric": worst_metric,
                    "value": round(snapshot.get(worst_metric, bval), 2),
                    "baseline_value": round(bval, 2),
                    "deviation_pct": round(worst_dev, 1),
                    "severity": _severity_from_score(score, worst_dev),
                    "detection_method": "isolation_forest",
                })
        except Exception:
            pass

    # --- Rolling Z-score ---
    if len(_rolling_buffers[service]) >= 10:
        buf = _rolling_buffers[service]
        for metric in ["latency_p99_ms", "error_rate_pct", "cpu_pct", "memory_pct"]:
            values = [s.get(metric, 0) for s in buf[:-1]]
            current = snapshot.get(metric, 0)
            mean = np.mean(values)
            std = np.std(values)
            if std < 1e-6:
                continue
            z = (current - mean) / std
            if abs(z) > settings.zscore_threshold:
                dev_pct = abs(current - mean) / max(mean, 0.001) * 100
                already_flagged = any(a["metric"] == metric for a in anomalies)
                if not already_flagged:
                    anomalies.append({
                        "anomaly_id": f"ano-{uuid.uuid4().hex[:10]}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": service,
                        "metric": metric,
                        "value": round(current, 2),
                        "baseline_value": round(mean, 2),
                        "deviation_pct": round(dev_pct, 1),
                        "severity": _severity_from_score(-abs(z) / 10, dev_pct),
                        "detection_method": "zscore",
                    })

    return anomalies
