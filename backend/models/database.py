from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime, timezone
from config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class MetricRecord(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    service = Column(String, index=True)
    environment = Column(String, default="production")
    latency_p50_ms = Column(Float)
    latency_p95_ms = Column(Float)
    latency_p99_ms = Column(Float)
    error_rate_pct = Column(Float)
    request_volume = Column(Integer)
    cpu_pct = Column(Float)
    memory_pct = Column(Float)
    status_2xx = Column(Integer)
    status_4xx = Column(Integer)
    status_5xx = Column(Integer)
    scenario = Column(String, nullable=True)


class LogRecord(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    service = Column(String, index=True)
    environment = Column(String, default="production")
    level = Column(String, index=True)
    trace_id = Column(String)
    request_id = Column(String)
    message = Column(Text)
    latency_ms = Column(Float, nullable=True)
    status_code = Column(Integer, nullable=True)


class AnomalyRecord(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    anomaly_id = Column(String, unique=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    service = Column(String, index=True)
    metric = Column(String)
    value = Column(Float)
    baseline_value = Column(Float)
    deviation_pct = Column(Float)
    severity = Column(String)  # info / warning / critical
    detection_method = Column(String)  # isolation_forest / zscore / threshold
    incident_id = Column(String, nullable=True, index=True)
    resolved = Column(Boolean, default=False)


class IncidentRecord(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String, unique=True, index=True)
    title = Column(String)
    status = Column(String, default="active")  # active / acknowledged / resolved
    severity = Column(String)
    affected_services = Column(JSON)
    first_detected = Column(DateTime)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    trigger_event = Column(JSON, nullable=True)
    anomaly_ids = Column(JSON)
    ai_summary = Column(Text, nullable=True)
    root_cause_suggestions = Column(JSON, nullable=True)
    recommended_actions = Column(JSON, nullable=True)
    health_scores = Column(JSON, nullable=True)


class DeploymentEvent(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, unique=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    event_type = Column(String)  # deployment / config_change / scale_event
    service = Column(String, index=True)
    version = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    triggered_by = Column(String, default="simulator")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
