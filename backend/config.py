from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Database
    database_url: str = f"sqlite:///{BASE_DIR}/aiops_sentinel.db"

    # Groq API
    groq_api_key: str = ""
    groq_model: str = "llama3-8b-8192"

    # Simulation
    simulation_interval_seconds: int = 10
    metrics_retention_limit: int = 500  # per service

    # Anomaly detection
    isolation_forest_contamination: float = 0.05
    zscore_threshold: float = 2.8
    baseline_samples: int = 3000

    # Correlation
    correlation_window_minutes: int = 10
    min_anomalies_for_incident: int = 2

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Phase 2A: Prometheus integration ──────────────────────────────────────
    prometheus_enabled: bool = False
    prometheus_url: str = "http://prometheus:9090"
    # Comma-separated list of Prometheus job labels to scrape.
    # If empty, all jobs discovered via /api/v1/label/job/values are used.
    prometheus_jobs: str = ""
    prometheus_scrape_interval_seconds: int = 15
    prometheus_environment: str = "production"

    # ── Phase 2B: Loki integration ─────────────────────────────────────────────
    loki_enabled: bool = False
    loki_url: str = "http://loki:3100"
    # Comma-separated list of Loki job labels to query.
    # If empty, all jobs discovered via /loki/api/v1/label/job/values are used.
    loki_jobs: str = ""
    loki_scrape_interval_seconds: int = 15
    loki_lookback_seconds: int = 30
    loki_limit_per_job: int = 500

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
