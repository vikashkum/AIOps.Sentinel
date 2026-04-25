"""
Simulation scenarios: define normal baselines and degradation profiles.
Each scenario returns a dict of per-service overrides applied to metric generation.
"""

# ── Microservices ──────────────────────────────────────────────────────────────
SERVICES = [
    "api-gateway",
    "auth-service",
    "order-service",
    "payment-service",
    "notification-service",
]

# ── Windows / IIS infrastructure hosts ────────────────────────────────────────
INFRA_HOSTS = [
    "iis-web-01",
    "iis-web-02",
    "iis-api-01",
    "win-db-01",
]

ALL_SERVICES = SERVICES + INFRA_HOSTS

# ── Microservice baselines ─────────────────────────────────────────────────────
BASELINES = {
    "api-gateway": {
        "latency_p50_ms": 45, "latency_p95_ms": 120, "latency_p99_ms": 220,
        "error_rate_pct": 0.3, "request_volume": 3200, "cpu_pct": 38, "memory_pct": 52,
    },
    "auth-service": {
        "latency_p50_ms": 25, "latency_p95_ms": 70, "latency_p99_ms": 130,
        "error_rate_pct": 0.1, "request_volume": 2800, "cpu_pct": 22, "memory_pct": 40,
    },
    "order-service": {
        "latency_p50_ms": 90, "latency_p95_ms": 250, "latency_p99_ms": 480,
        "error_rate_pct": 0.5, "request_volume": 1800, "cpu_pct": 55, "memory_pct": 62,
    },
    "payment-service": {
        "latency_p50_ms": 110, "latency_p95_ms": 300, "latency_p99_ms": 550,
        "error_rate_pct": 0.2, "request_volume": 1200, "cpu_pct": 45, "memory_pct": 58,
    },
    "notification-service": {
        "latency_p50_ms": 30, "latency_p95_ms": 80, "latency_p99_ms": 150,
        "error_rate_pct": 0.4, "request_volume": 900, "cpu_pct": 18, "memory_pct": 35,
    },
}

# ── Windows / IIS host baselines ───────────────────────────────────────────────
INFRA_BASELINES = {
    "iis-web-01": {
        "cpu_pct": 32, "memory_pct": 55, "disk_pct": 48,
        "requests_per_sec": 420, "active_connections": 85,
        "error_rate_5xx_pct": 0.2, "latency_p99_ms": 190,
        "app_pool_status": "running", "worker_process_count": 2,
        "bytes_sent_mb": 12.4, "bytes_recv_mb": 3.1,
    },
    "iis-web-02": {
        "cpu_pct": 28, "memory_pct": 50, "disk_pct": 44,
        "requests_per_sec": 380, "active_connections": 72,
        "error_rate_5xx_pct": 0.15, "latency_p99_ms": 175,
        "app_pool_status": "running", "worker_process_count": 2,
        "bytes_sent_mb": 10.8, "bytes_recv_mb": 2.7,
    },
    "iis-api-01": {
        "cpu_pct": 45, "memory_pct": 62, "disk_pct": 52,
        "requests_per_sec": 260, "active_connections": 55,
        "error_rate_5xx_pct": 0.3, "latency_p99_ms": 310,
        "app_pool_status": "running", "worker_process_count": 4,
        "bytes_sent_mb": 8.2, "bytes_recv_mb": 5.6,
    },
    "win-db-01": {
        "cpu_pct": 38, "memory_pct": 72, "disk_pct": 61,
        "requests_per_sec": 0, "active_connections": 48,
        "error_rate_5xx_pct": 0.0, "latency_p99_ms": 0,
        "app_pool_status": "n/a", "worker_process_count": 0,
        "bytes_sent_mb": 4.1, "bytes_recv_mb": 3.8,
        "sql_connections": 48, "sql_queries_per_sec": 320,
        "sql_blocked_queries": 0, "disk_read_mb_s": 12.4, "disk_write_mb_s": 8.1,
    },
}

# ── Microservice scenarios ─────────────────────────────────────────────────────
SCENARIOS = {
    "normal": {},

    "traffic_spike": {
        "api-gateway": {
            "request_volume_mult": 3.5, "latency_p99_ms_mult": 1.8,
            "cpu_pct_mult": 1.7, "error_rate_pct_mult": 2.0,
        },
        "order-service": {
            "request_volume_mult": 3.0, "latency_p99_ms_mult": 1.6, "cpu_pct_mult": 1.5,
        },
    },

    "bad_deployment": {
        "payment-service": {
            "error_rate_pct_mult": 18.0, "latency_p99_ms_mult": 7.5,
            "latency_p95_ms_mult": 5.0, "cpu_pct_mult": 1.4,
            "deployment_event": {"version": "v2.4.1", "type": "deployment"},
        },
    },

    "cascading_failure": {
        "payment-service": {
            "error_rate_pct_mult": 20.0, "latency_p99_ms_mult": 8.0,
            "cpu_pct_mult": 1.6,
            "deployment_event": {"version": "v2.4.1", "type": "deployment"},
        },
        "order-service": {
            "error_rate_pct_mult": 8.0, "latency_p99_ms_mult": 5.0,
            "latency_p95_ms_mult": 3.5, "cpu_pct_mult": 1.4,
        },
        "api-gateway": {
            "error_rate_pct_mult": 3.0, "latency_p99_ms_mult": 2.0,
        },
    },

    "memory_pressure": {
        "auth-service": {
            "memory_pct_add": 45, "latency_p99_ms_mult": 2.5,
            "cpu_pct_mult": 1.8, "error_rate_pct_mult": 3.0,
        },
    },

    "error_burst": {
        "notification-service": {
            "error_rate_pct_mult": 25.0, "latency_p99_ms_mult": 3.0,
            "status_5xx_pct": 0.30,
        },
    },

    "latency_regression": {
        "order-service": {
            "latency_p50_ms_mult": 3.5, "latency_p95_ms_mult": 4.5,
            "latency_p99_ms_mult": 6.0,
            "deployment_event": {"version": "v3.1.2", "type": "deployment"},
        },
    },
}

# ── Infrastructure (IIS / Windows) scenarios ──────────────────────────────────
INFRA_SCENARIOS = {
    "normal": {},

    "iis_app_pool_crash": {
        "iis-web-01": {
            "app_pool_status": "stopped",
            "error_rate_5xx_pct_mult": 80.0,
            "active_connections_mult": 0.05,
            "requests_per_sec_mult": 0.02,
            "cpu_pct_mult": 0.3,
            "win_event": {
                "level": "Error",
                "source": "WAS",
                "event_id": 5002,
                "message": "Application pool DefaultAppPool has been disabled. Windows Process Activation Service (WAS) encountered a failure when it started a worker process to serve the application pool.",
            },
        },
        "iis-web-02": {
            "error_rate_5xx_pct_mult": 8.0,
            "requests_per_sec_mult": 1.9,
            "cpu_pct_mult": 1.7,
            "active_connections_mult": 1.8,
        },
    },

    "iis_memory_leak": {
        "iis-api-01": {
            "memory_pct_add": 28,
            "cpu_pct_mult": 1.6,
            "latency_p99_ms_mult": 4.2,
            "error_rate_5xx_pct_mult": 6.0,
            "win_event": {
                "level": "Warning",
                "source": "W3SVC-WP",
                "event_id": 2262,
                "message": "ISAPI 'aspnet_filter.dll' reported itself as unhealthy. Worker process memory usage at 89%. Private bytes limit exceeded.",
            },
        },
    },

    "iis_high_error_rate": {
        "iis-web-01": {
            "error_rate_5xx_pct_mult": 35.0,
            "latency_p99_ms_mult": 5.5,
            "win_event": {
                "level": "Error",
                "source": "ASP.NET",
                "event_id": 1309,
                "message": "An unhandled exception has occurred. Exception type: System.Data.SqlException. Connection timeout expired. The timeout period elapsed prior to obtaining a connection from the pool.",
            },
        },
        "iis-web-02": {
            "error_rate_5xx_pct_mult": 30.0,
            "latency_p99_ms_mult": 4.8,
        },
    },

    "disk_pressure": {
        "win-db-01": {
            "disk_pct_add": 32,
            "cpu_pct_mult": 1.4,
            "disk_read_mb_s_mult": 3.5,
            "disk_write_mb_s_mult": 4.2,
            "sql_blocked_queries_add": 18,
            "win_event": {
                "level": "Warning",
                "source": "Disk",
                "event_id": 51,
                "message": "An error was detected on device \\Device\\Harddisk0\\DR0 during a paging operation. Disk usage at 93%. SQL Server tempdb may be affected.",
            },
        },
        "iis-api-01": {
            "latency_p99_ms_mult": 6.0,
            "error_rate_5xx_pct_mult": 12.0,
        },
    },

    "iis_worker_recycle": {
        "iis-api-01": {
            "active_connections_mult": 0.1,
            "requests_per_sec_mult": 0.2,
            "worker_process_count_set": 0,
            "latency_p99_ms_mult": 8.0,
            "error_rate_5xx_pct_mult": 20.0,
            "win_event": {
                "level": "Information",
                "source": "WAS",
                "event_id": 5079,
                "message": "A worker process with process id of 4812 serving application pool ApiAppPool has requested a recycle because the worker process reached its allowed processing time limit.",
            },
        },
    },

    "ssl_cert_expiry": {
        "iis-web-01": {
            "error_rate_5xx_pct_mult": 15.0,
            "win_event": {
                "level": "Error",
                "source": "Schannel",
                "event_id": 36882,
                "message": "The certificate received from the remote server has expired or is not yet valid. SSL certificate for site expires in 3 days. Clients may begin receiving SSL handshake failures.",
            },
        },
        "iis-web-02": {
            "error_rate_5xx_pct_mult": 15.0,
        },
    },
}

# ── Log templates ──────────────────────────────────────────────────────────────
LOG_TEMPLATES = {
    "normal": [
        "Request processed successfully in {latency}ms",
        "Health check passed",
        "Cache hit for key user:{id}",
        "Database query completed in {latency}ms",
        "Token validated for user {id}",
    ],
    "warning": [
        "Slow query detected: {latency}ms exceeds threshold of 500ms",
        "Retry attempt {n}/3 for downstream call",
        "Circuit breaker at {pct}% of threshold",
        "Memory usage trending high: {pct}%",
        "Response time degraded: p99={latency}ms",
    ],
    "error": [
        "Timeout waiting for {svc} response after {latency}ms",
        "Connection pool exhausted: max={n} connections reached",
        "HTTP 503 received from {svc}: service unavailable",
        "Database transaction rolled back: deadlock detected",
        "Payment gateway returned error code {code}",
        "Authentication failed for request {id}: downstream auth-service timeout",
    ],
    "critical": [
        "CRITICAL: {svc} health check failed consecutively for {n} attempts",
        "CRITICAL: Error rate {pct}% exceeds SLO threshold of 1%",
        "CRITICAL: p99 latency {latency}ms exceeds SLA of 2000ms",
        "CRITICAL: Service {svc} returning all 503 responses",
    ],
}

# ── IIS / Windows Event Log templates ─────────────────────────────────────────
IIS_LOG_TEMPLATES = {
    "normal": [
        "GET /index.html HTTP/1.1 200 {latency}",
        "POST /api/submit HTTP/1.1 200 {latency}",
        "GET /assets/app.js HTTP/1.1 200 {latency}",
        "GET /health HTTP/1.1 200 {latency}",
        "GET /api/status HTTP/1.1 200 {latency}",
    ],
    "warning": [
        "GET /api/report HTTP/1.1 200 {latency}",
        "POST /api/upload HTTP/1.1 200 {latency}",
        "GET /api/dashboard HTTP/1.1 200 {latency}",
    ],
    "error": [
        "POST /api/submit HTTP/1.1 500 {latency}",
        "GET /api/data HTTP/1.1 503 {latency}",
        "POST /api/process HTTP/1.1 500 {latency}",
        "GET /api/resource HTTP/1.1 502 {latency}",
    ],
}

WIN_EVENT_TEMPLATES = {
    "normal": [
        {"level": "Information", "source": "WAS", "event_id": 5074, "message": "Application pool {pool} has been successfully recycled."},
        {"level": "Information", "source": "W3SVC", "event_id": 1001, "message": "IIS Service started successfully."},
        {"level": "Information", "source": "Security", "event_id": 4624, "message": "An account was successfully logged on."},
    ],
    "warning": [
        {"level": "Warning", "source": "W3SVC-WP", "event_id": 2262, "message": "Worker process memory usage at {pct}%."},
        {"level": "Warning", "source": "Perflib", "event_id": 1008, "message": "Performance counter collection is falling behind."},
        {"level": "Warning", "source": "Disk", "event_id": 51, "message": "Disk usage at {pct}% on C:\\. Consider cleanup."},
    ],
    "error": [
        {"level": "Error", "source": "Application Error", "event_id": 1000, "message": "Faulting application w3wp.exe, exception code 0xc0000005."},
        {"level": "Error", "source": "ASP.NET", "event_id": 1309, "message": "An unhandled exception occurred. System.Data.SqlException: Connection timeout."},
        {"level": "Error", "source": "WAS", "event_id": 5002, "message": "Application pool DefaultAppPool has been disabled due to repeated failures."},
    ],
}
