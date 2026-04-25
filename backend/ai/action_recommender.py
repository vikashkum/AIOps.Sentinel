"""
Action recommendation engine.
Maps root cause categories to actionable next steps.
"""

_ACTION_MAP = {
    "regression": [
        {
            "priority": 1,
            "action": "Roll back to the previous stable version",
            "rationale": "Deployment correlation confidence is high. Rollback has the lowest blast radius and fastest recovery path.",
            "command_hint": "kubectl rollout undo deployment/<service-name>",
        },
        {
            "priority": 2,
            "action": "Scale out the affected service horizontally",
            "rationale": "Reduces request pressure while the rollback is being prepared or validated.",
            "command_hint": "kubectl scale deployment/<service-name> --replicas=<n+2>",
        },
        {
            "priority": 3,
            "action": "Check application logs for stack traces or error patterns",
            "rationale": "Confirms whether the regression is code-level or configuration-level.",
            "command_hint": "kubectl logs -l app=<service-name> --tail=200",
        },
    ],
    "cascading": [
        {
            "priority": 1,
            "action": "Identify and isolate the root upstream service",
            "rationale": "Cascading failures originate from one service. Isolating it stops further propagation.",
            "command_hint": "Check service dependency map; apply circuit breaker if available.",
        },
        {
            "priority": 2,
            "action": "Enable circuit breaker or increase timeout tolerance on dependent services",
            "rationale": "Prevents downstream services from queuing requests indefinitely.",
            "command_hint": "Update Istio VirtualService or application circuit breaker config.",
        },
        {
            "priority": 3,
            "action": "Scale downstream services to absorb backpressure",
            "rationale": "Buys time while the upstream root cause is addressed.",
            "command_hint": "kubectl scale deployment/<downstream-service> --replicas=<n+3>",
        },
    ],
    "resource": [
        {
            "priority": 1,
            "action": "Increase memory and CPU limits for the affected service",
            "rationale": "Resource saturation is causing latency and errors. Expanded limits provide immediate relief.",
            "command_hint": "kubectl edit deployment/<service-name> — update resources.limits",
        },
        {
            "priority": 2,
            "action": "Investigate for memory leaks in recent code changes",
            "rationale": "Gradual memory growth often indicates a leak introduced in a recent deployment.",
            "command_hint": "Review heap dumps or enable pprof profiling endpoint.",
        },
        {
            "priority": 3,
            "action": "Add horizontal autoscaling policy",
            "rationale": "Prevents future resource saturation under variable load.",
            "command_hint": "kubectl autoscale deployment/<service-name> --min=2 --max=8 --cpu-percent=70",
        },
    ],
    "database": [
        {
            "priority": 1,
            "action": "Check database connection pool size and active connections",
            "rationale": "High latency + error rate pattern is consistent with pool exhaustion.",
            "command_hint": "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';",
        },
        {
            "priority": 2,
            "action": "Increase connection pool size or add a connection pooler (PgBouncer)",
            "rationale": "Immediate relief for pool exhaustion without code changes.",
            "command_hint": "Update DATABASE_POOL_SIZE env variable and restart the service.",
        },
        {
            "priority": 3,
            "action": "Check for long-running queries or table locks",
            "rationale": "Slow queries can exhaust connections and amplify latency.",
            "command_hint": "SELECT query, duration FROM pg_stat_activity ORDER BY duration DESC LIMIT 10;",
        },
    ],
    "external": [
        {
            "priority": 1,
            "action": "Check external API or third-party service status",
            "rationale": "Extreme error spikes not correlated with deployment often indicate external dependency issues.",
            "command_hint": "Check vendor status page; review error response bodies for upstream error codes.",
        },
        {
            "priority": 2,
            "action": "Enable fallback or degraded mode for the external dependency",
            "rationale": "Prevents the external failure from fully blocking your service.",
            "command_hint": "Toggle ENABLE_FALLBACK_MODE=true in service config.",
        },
    ],
    "traffic": [
        {
            "priority": 1,
            "action": "Scale out the entry point service (api-gateway) immediately",
            "rationale": "Traffic spikes require horizontal capacity before other optimizations take effect.",
            "command_hint": "kubectl scale deployment/api-gateway --replicas=<current+4>",
        },
        {
            "priority": 2,
            "action": "Enable rate limiting at the gateway layer",
            "rationale": "Prevents downstream services from being overwhelmed by upstream volume.",
            "command_hint": "Apply Nginx or API Gateway rate limit policy.",
        },
        {
            "priority": 3,
            "action": "Review if traffic spike is legitimate or a bot/scraping attack",
            "rationale": "Unusual traffic patterns may indicate abuse rather than real user growth.",
            "command_hint": "Check access logs for unusual User-Agent patterns or IP concentrations.",
        },
    ],
    "unknown": [
        {
            "priority": 1,
            "action": "Review recent changes: deployments, config changes, infrastructure updates",
            "rationale": "Without a clear pattern match, a change-based review is the most reliable starting point.",
            "command_hint": "Check deployment history, feature flags, and infrastructure change logs.",
        },
        {
            "priority": 2,
            "action": "Manually inspect logs and traces for error patterns",
            "rationale": "AIOps Sentinel has insufficient signal correlation; manual investigation is required.",
            "command_hint": "Filter logs by ERROR/CRITICAL level for the affected service in the last 30 minutes.",
        },
    ],
}


def _classify_cause(cause_str: str) -> str:
    cause_lower = cause_str.lower()
    if "deployment" in cause_lower or "regression" in cause_lower:
        return "regression"
    if "cascading" in cause_lower or "cascade" in cause_lower or "upstream" in cause_lower:
        return "cascading"
    if "resource" in cause_lower or "memory" in cause_lower or "cpu" in cause_lower or "saturation" in cause_lower:
        return "resource"
    if "database" in cause_lower or "connection pool" in cause_lower or "query" in cause_lower:
        return "database"
    if "external" in cause_lower or "third-party" in cause_lower or "dependency" in cause_lower:
        return "external"
    if "traffic" in cause_lower or "load" in cause_lower or "surge" in cause_lower:
        return "traffic"
    return "unknown"


def recommend_actions(root_cause_suggestions: list[dict]) -> list[dict]:
    if not root_cause_suggestions:
        return _ACTION_MAP["unknown"]

    top_cause = root_cause_suggestions[0]
    category = _classify_cause(top_cause["cause"])
    return _ACTION_MAP.get(category, _ACTION_MAP["unknown"])
