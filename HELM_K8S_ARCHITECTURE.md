# AIOps Sentinel — Helm Chart & Kubernetes Architecture

> **Audience**: Developers who built this project and want to deeply understand how the Helm chart is designed, why every decision was made, and how to move this to Azure Kubernetes Service (AKS) in production.

---

## Table of Contents

1. [Why Kubernetes & Helm for This Project](#1-why-kubernetes--helm-for-this-project)
2. [Helm Chart Structure — Every File Explained](#2-helm-chart-structure--every-file-explained)
3. [Template Design Patterns Used](#3-template-design-patterns-used)
4. [Service Architecture on Kubernetes](#4-service-architecture-on-kubernetes)
5. [Network Flow — How Components Talk to Each Other](#5-network-flow--how-components-talk-to-each-other)
6. [Configuration & Secrets Design](#6-configuration--secrets-design)
7. [Storage Architecture](#7-storage-architecture)
8. [Health Probes & Rolling Updates](#8-health-probes--rolling-updates)
9. [Lessons Learned — Bugs Fixed During Deployment](#9-lessons-learned--bugs-fixed-during-deployment)
10. [AKS Production Roadmap](#10-aks-production-roadmap)

---

## 1. Why Kubernetes & Helm for This Project

### The Problem with Docker Compose

`docker-compose.yml` is great for local development. On a single machine it is simple and fast. But it has hard limits:

| Concern | Docker Compose | Kubernetes |
|---|---|---|
| Self-healing | Restart policy only | Full controller loop — always reconciles to desired state |
| Multi-machine | Not supported | Native — spans many nodes |
| Zero-downtime deploys | Not supported | Rolling updates built-in |
| Auto-scaling | Not supported | HPA scales pods on CPU/memory |
| Secret management | `.env` files | Secrets API, encrypted at rest |
| Health-gating traffic | Not supported | readinessProbe removes unhealthy pods from rotation |
| Config change rollouts | Restart manually | Checksum annotation triggers automatic rolling restart |

### Why Helm on top of Kubernetes

Raw Kubernetes YAML is static. For AIOps Sentinel:

- The Prometheus URL changes based on the **release name** (e.g., `aiops-prometheus` vs `prod-prometheus`)
- CORS origins depend on the **frontend port** in values
- ConfigMaps must reference **service names** that are computed at install time

Helm solves this with Go templating — write YAML once, render it correctly for every environment.

---

## 2. Helm Chart Structure — Every File Explained

```
helm/aiops-sentinel/
│
├── Chart.yaml                    ← Chart identity & metadata
├── values.yaml                   ← All configurable defaults
├── .helmignore                   ← Files excluded from helm package
│
└── templates/
    ├── _helpers.tpl              ← Reusable named templates (functions)
    ├── NOTES.txt                 ← Printed to terminal after helm install
    ├── namespace.yaml            ← Comment-only (namespace managed externally)
    ├── ingress.yaml              ← Optional L7 HTTP router (disabled by default)
    │
    ├── backend/
    │   ├── secret.yaml           ← GROQ_API_KEY (Kubernetes Secret)
    │   ├── configmap.yaml        ← All non-sensitive env vars
    │   ├── pvc.yaml              ← 2Gi persistent disk for SQLite + ML models
    │   ├── deployment.yaml       ← FastAPI app, probes, rolling update
    │   ├── service.yaml          ← LoadBalancer exposing port 8000
    │   └── hpa.yaml              ← HorizontalPodAutoscaler (disabled by default)
    │
    ├── frontend/
    │   ├── configmap.yaml        ← Kubernetes-aware nginx.conf (fixes upstream DNS)
    │   ├── deployment.yaml       ← React/Nginx app
    │   └── service.yaml          ← LoadBalancer exposing port 80
    │
    ├── prometheus/
    │   ├── configmap.yaml        ← prometheus.yml with dynamic backend target
    │   ├── pvc.yaml              ← 5Gi TSDB storage
    │   ├── deployment.yaml       ← Prometheus server
    │   └── service.yaml          ← LoadBalancer port 9090
    │
    ├── loki/
    │   ├── configmap.yaml        ← loki local-config.yaml
    │   ├── pvc.yaml              ← 5Gi log chunk storage
    │   ├── deployment.yaml       ← Loki single-binary mode
    │   └── service.yaml          ← ClusterIP only (internal access)
    │
    └── grafana/
        ├── configmap.yaml        ← datasources.yaml + dashboards.yaml provisioning
        ├── pvc.yaml              ← 2Gi dashboard/plugin storage
        ├── deployment.yaml       ← Grafana server
        └── service.yaml          ← LoadBalancer port 3001
```

### Chart.yaml — The Identity Card

```yaml
apiVersion: v2          # Helm 3 chart format
name: aiops-sentinel
type: application       # deployable (vs "library" = helper-only)
version: 0.1.0          # bump this when the CHART changes (SemVer)
appVersion: "1.0.0"     # the application version — informational only
```

**Rule**: `version` tracks chart changes. `appVersion` tracks app changes. They are independent.

### values.yaml — The Contract

Every user-adjustable parameter lives here with a sensible default. Templates reference values with `{{ .Values.backend.replicas }}`. This makes the chart self-documenting:

```
values.yaml
    ↓ overridden by
-f values-prod.yaml
    ↓ overridden by
--set backend.replicas=3
```

The hierarchy is: chart defaults → values files (left to right) → `--set` flags.

---

## 3. Template Design Patterns Used

### Pattern 1: Named Templates in `_helpers.tpl`

Files prefixed with `_` are never rendered as Kubernetes resources. They define reusable Go template "functions":

```
{{- define "aiops-sentinel.backend.name" -}}
{{- printf "%s-backend" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
```

**Why this matters**: Every resource name is computed from the Helm release name, not hardcoded. With release name `aiops`, the backend service is `aiops-backend`. With release name `prod`, it becomes `prod-backend`. This allows running multiple environments in the same cluster:

```
Namespace: aiops-dev    → release: dev    → dev-backend, dev-prometheus
Namespace: aiops-prod   → release: prod   → prod-backend, prod-prometheus
```

### Pattern 2: Component Labels

```yaml
{{- define "aiops-sentinel.componentLabels" -}}
app.kubernetes.io/name: {{ .ctx.Chart.Name }}-{{ .component }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}
```

These labels are used in **two places that must match exactly**:

1. The Deployment's `spec.selector.matchLabels` — how it finds "its" pods
2. The Service's `spec.selector` — how it finds pods to route traffic to

**Critical rule**: Once a Deployment is created, `spec.selector` is **immutable**. Changing it requires deleting and recreating the Deployment. This is why we use a stable naming convention from day one.

### Pattern 3: Checksum Annotations for Config Reloads

```yaml
annotations:
  checksum/config: {{ include (print $.Template.BasePath "/backend/configmap.yaml") . | sha256sum }}
  checksum/secret: {{ include (print $.Template.BasePath "/backend/secret.yaml") . | sha256sum }}
```

**The problem it solves**: When you change a ConfigMap, Kubernetes doesn't automatically restart the pods using it. The pods keep running with the old config.

**How it works**: The entire ConfigMap template is rendered and SHA256-hashed into the Deployment annotation. When the config content changes → the hash changes → the Deployment spec changes → Kubernetes triggers a rolling restart automatically on `helm upgrade`.

### Pattern 4: Conditional Components

```yaml
{{- if .Values.prometheus.enabled }}
# ... entire prometheus deployment
{{- end }}
```

Prometheus, Loki, and Grafana are completely omitted from the rendered YAML when disabled. This means the same chart works for:

```bash
# Minimal — app only
helm install aiops . --set prometheus.enabled=false --set loki.enabled=false --set grafana.enabled=false

# Full observability stack
helm install aiops .
```

### Pattern 5: Dynamic Service DNS URLs

```yaml
PROMETHEUS_URL: {{ printf "http://%s:%d"
  (include "aiops-sentinel.prometheus.name" .)
  (int .Values.prometheus.port) | quote }}
```

Renders to: `"http://aiops-prometheus:9090"`

This is a key Helm advantage — the URL is always correct regardless of the release name or port configured in values. No manual editing of URLs between environments.

### Pattern 6: `toYaml` + `nindent` for Nested Structures

```yaml
resources:
  {{- toYaml .Values.backend.resources | nindent 10 }}
```

`toYaml` serializes the resources object from values.yaml as YAML. `nindent 10` adds 10 spaces of indentation to every line. This is the standard pattern for any nested YAML block that users might want to customise.

### Pattern 7: Recreate vs RollingUpdate Strategy

- **Backend**: `RollingUpdate` (maxSurge=1, maxUnavailable=0) — zero-downtime. The new pod must pass readinessProbe before the old one is terminated.
- **Prometheus, Loki, Grafana**: `Recreate` — the old pod is killed before the new one starts. Required because `ReadWriteOnce` PVCs can only be attached to **one node at a time**. Two pods on different nodes would fight over the disk.

---

## 4. Service Architecture on Kubernetes

### Resource Map

```
┌─────────────────────────── Namespace: aiops-sentinel ────────────────────────────┐
│                                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────────┐   │
│  │                        USER-FACING LAYER                                  │   │
│  │                                                                           │   │
│  │   aiops-frontend (LoadBalancer :80)          aiops-backend (LB :8000)    │   │
│  │   ┌─────────────────────────┐                ┌────────────────────────┐  │   │
│  │   │  React SPA (Nginx)      │                │  FastAPI + uvicorn     │  │   │
│  │   │  Static HTML/JS/CSS     │ ──/api/──────► │  Simulation Engine    │  │   │
│  │   │  nginx ConfigMap        │                │  Anomaly Detector     │  │   │
│  │   └─────────────────────────┘                │  RCA Engine (Groq AI) │  │   │
│  │                                              │  Health Scorer        │  │   │
│  │                                              └──────────┬────────────┘  │   │
│  └────────────────────────────────────────────────────────┼────────────────┘   │
│                                                            │                    │
│  ┌─────────────────────────────────────────────────────────┼────────────────┐   │
│  │                    OBSERVABILITY LAYER                   │                │   │
│  │                                                          │ scrapes        │   │
│  │   aiops-prometheus (LB :9090)    aiops-loki (ClupIP)    │ pushes         │   │
│  │   ┌──────────────────────┐       ┌──────────────────┐   │                │   │
│  │   │  Prometheus TSDB     │       │  Loki Log Store  │◄──┘                │   │
│  │   │  Metrics scraping    │       │  Single-binary   │                    │   │
│  │   │  7-day retention     │       │  168h retention  │                    │   │
│  │   └──────────┬───────────┘       └────────┬─────────┘                   │   │
│  │              │                            │                              │   │
│  │              └──────────────┬─────────────┘                             │   │
│  │                             ▼                                            │   │
│  │              aiops-grafana (LB :3001)                                   │   │
│  │              ┌────────────────────────┐                                 │   │
│  │              │  Grafana 11.0.0        │                                 │   │
│  │              │  Auto-provisioned:     │                                 │   │
│  │              │  • Prometheus source   │                                 │   │
│  │              │  • Loki source         │                                 │   │
│  │              └────────────────────────┘                                 │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
│  ┌──────────────────────────── STORAGE LAYER ──────────────────────────────┐    │
│  │  PVC: aiops-backend-data (2Gi)    ← SQLite DB + ML models               │    │
│  │  PVC: aiops-prometheus-data (5Gi) ← Prometheus TSDB                     │    │
│  │  PVC: aiops-loki-data (5Gi)       ← Log chunks + index                  │    │
│  │  PVC: aiops-grafana-data (2Gi)    ← Dashboards + plugins                │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Kubernetes Objects per Component

| Component | Deployment | Service | ConfigMap | Secret | PVC | HPA |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Backend | ✅ | ✅ LoadBalancer | ✅ config | ✅ groq key | ✅ 2Gi | ✅ optional |
| Frontend | ✅ | ✅ LoadBalancer | ✅ nginx.conf | — | — | — |
| Prometheus | ✅ | ✅ LoadBalancer | ✅ prometheus.yml | — | ✅ 5Gi | — |
| Loki | ✅ | ✅ ClusterIP | ✅ loki config | — | ✅ 5Gi | — |
| Grafana | ✅ | ✅ LoadBalancer | ✅ datasources + dashboards | — | ✅ 2Gi | — |

---

## 5. Network Flow — How Components Talk to Each Other

### Internal DNS — The Core of Kubernetes Networking

Every Service gets a stable DNS name automatically:
```
<service-name>.<namespace>.svc.cluster.local
```

Within the same namespace, the short form resolves:
```
aiops-backend      → 10.96.131.154 (ClusterIP, load-balanced to pods)
aiops-prometheus   → 10.96.55.40
aiops-loki         → 10.96.235.83
aiops-grafana      → 10.96.192.212
```

### Flow 1: Browser → Frontend → Backend

```
User's Browser
    │
    │  HTTP GET /
    ▼
kubectl port-forward (local machine tunnel)
    │
    ▼
aiops-frontend Service (LoadBalancer)
    │
    ▼
Nginx container (serves /usr/share/nginx/html)
    │
    │  When browser calls /api/*
    │  Nginx proxies to: http://aiops-backend:8000
    ▼
aiops-backend Service (ClusterIP internally)
    │
    ▼
FastAPI Pod
```

**Key insight**: Nginx uses Kubernetes internal DNS (`aiops-backend:8000`), not `localhost`. The nginx ConfigMap is overridden at deploy time by the Helm chart to inject the correct service name — this is why a plain Docker image with hardcoded `backend:8000` would fail on Kubernetes.

### Flow 2: Prometheus Scraping Backend

```
Prometheus Pod
    │
    │  Every 15 seconds via Job: aiops-sentinel-backend
    │  Target: aiops-backend:8000/metrics
    ▼
aiops-backend Service
    │
    ▼
FastAPI /metrics endpoint (prometheus-fastapi-instrumentator)
    │
    ▼
Metrics stored in Prometheus TSDB (PVC: aiops-prometheus-data)
```

### Flow 3: Backend → Loki (Log Pull)

```
Backend scrape loop (every 15s)
    │
    │  GET http://aiops-loki:3100/loki/api/v1/query_range
    ▼
aiops-loki Service (ClusterIP — internal only)
    │
    ▼
Loki Pod → returns log streams
    │
    ▼
Backend processes logs → anomaly detection → incident correlation
```

### Flow 4: Grafana → Prometheus + Loki

```
Grafana Pod (auto-provisioned via ConfigMap)
    │
    ├── DataSource: Prometheus → http://aiops-prometheus:9090
    └── DataSource: Loki       → http://aiops-loki:3100
```

The datasources ConfigMap is rendered by Helm with the correct service DNS names at install time.

---

## 6. Configuration & Secrets Design

### Why ConfigMap vs Secret

| Data | Resource | Why |
|---|---|---|
| GROQ_API_KEY | **Secret** | Sensitive — base64 encoded, can be encrypted at rest in etcd |
| PROMETHEUS_URL | **ConfigMap** | Non-sensitive service URL |
| DATABASE_URL | **ConfigMap** | File path — not sensitive |
| CORS_ORIGINS | **ConfigMap** | Non-sensitive list |
| GROQ_MODEL | **ConfigMap** | Non-sensitive model name |

### How the Backend Consumes Both

```yaml
envFrom:
  - configMapRef:
      name: aiops-backend-config   # loads all keys as env vars
  - secretRef:
      name: aiops-backend-secret   # overlaid on top
```

`envFrom` with `secretRef` **after** `configMapRef` means Secrets override ConfigMap values for any duplicate keys — a useful safety property.

### CORS_ORIGINS — A Subtle Gotcha

pydantic-settings parses `list[str]` fields from environment variables as **JSON arrays**, not comma-separated strings:

```yaml
# ❌ Wrong — pydantic raises SettingsError
CORS_ORIGINS: "http://localhost:3000,http://localhost:5173"

# ✅ Correct — JSON array format
CORS_ORIGINS: '["http://localhost:3000","http://localhost:5173"]'
```

The ConfigMap template generates this correctly using Helm's `printf`:
```
{{ printf "[\"http://localhost:%d\",...]" (int .Values.frontend.service.nodePort) | quote }}
```

### Secret Management in Production

The current design passes the Groq key via `--set`:
```bash
helm install aiops . --set backend.groqApiKey="gsk_..."
```

**This is safe for learning but NOT production-ready.** The value is stored in Helm's release history (in a Kubernetes Secret in the `kube-system` namespace). See the AKS roadmap below for the correct approach.

---

## 7. Storage Architecture

### PVC Design Decisions

```
backend PVC (2Gi, ReadWriteOnce)
    ├── /app/data/aiops_sentinel.db   ← SQLite (subPath: database)
    └── /app/ml_models/               ← scikit-learn models (subPath: ml_models)
```

Using `subPath` means a single PVC serves two different mount points in the same pod, keeping storage simple.

### Why `ReadWriteOnce` for Everything

- `ReadWriteOnce` (RWO) = one **node** can read/write at a time
- Matches the deployment model: all stateful components run with 1 replica
- For the backend: SQLite requires single-writer access — RWO enforces this at the infrastructure level

### Why `Recreate` Strategy for Stateful Pods

```yaml
strategy:
  type: Recreate   # for Prometheus, Loki, Grafana
```

With `ReadWriteOnce`:
1. Pod A on Node 1 has the disk attached
2. Rolling update starts Pod B on Node 2
3. Kubernetes tries to attach the disk to Node 2
4. **Fails** — disk is still attached to Node 1

`Recreate` kills Pod A first, releasing the disk, then starts Pod B.

### `helm.sh/resource-policy: keep` Annotation

```yaml
annotations:
  helm.sh/resource-policy: keep
```

Every PVC has this annotation. It means `helm uninstall aiops` **does not delete the PVCs**. Your data survives an uninstall. You must manually delete PVCs if you truly want to wipe data:

```bash
kubectl delete pvc -n aiops-sentinel --all
```

---

## 8. Health Probes & Rolling Updates

### Three Probes on the Backend

```
Pod starts
    │
    ▼
startupProbe  /health   (30 attempts × 5s = 150s max startup window)
    │
    │  PASSES → liveness and readiness take over
    ▼
livenessProbe  /health   (every 30s — failure = OOMKill + restart)
readinessProbe /health   (every 10s — failure = removed from Service endpoints)
```

**Why startupProbe matters**: On first boot, the backend initialises the SQLite DB, trains the IsolationForest model on 3000 baseline samples, and starts background simulation tasks. This can take 30—90 seconds. Without startupProbe, the liveness probe would fire during this window and restart the pod in a loop.

### Rolling Update Guarantee

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1          # 1 extra pod allowed during update
    maxUnavailable: 0    # zero pods below desired count
```

With 1 replica and these settings:
1. New pod starts (total: 2 pods)
2. Kubernetes waits for new pod to pass readinessProbe
3. Old pod is terminated (total: 1 pod)

**Zero downtime**: traffic is never interrupted because the old pod keeps serving until the new one is ready.

---

## 9. Lessons Learned — Bugs Fixed During Deployment

These are real issues encountered deploying to Docker Desktop Kubernetes. Understanding them teaches core Kubernetes concepts.

### Bug 1 — Go Template Action Inside YAML Comment

```yaml
# ❌ The {{- if .Values.prometheus.enabled }} guard means...
```

**Problem**: Go's template engine does NOT respect `#` as a comment. It parsed the `{{- if }}` as a real action with no matching `{{- end }}`, causing `unexpected EOF` at line 101.

**Fix**: Remove template syntax from YAML comments. Never write `{{ }}` inside `#` comment lines.

**Lesson**: Helm templates are pure Go text/template. Only `{{/* */}}` is a real comment.

---

### Bug 2 — Namespace Owned by Helm

```
Error: invalid ownership metadata; annotation validation error:
key "meta.helm.sh/release-namespace" must equal "aiops-sentinel"
```

**Problem**: The chart originally created the Namespace as a Kubernetes resource inside the chart. When the first `helm install` failed (timeout), the Namespace was left with `default` as its release namespace annotation. The next install tried to claim it for `aiops-sentinel` — conflict.

**Fix**: Removed `namespace.yaml` from the chart templates. Use `--create-namespace` flag instead. Helm creates the namespace without owning it, so it survives failures and reinstalls cleanly.

**Lesson**: Helm should not own Namespace resources in application charts. Manage namespaces outside Helm (via `--create-namespace` or a separate `setup.sh`).

---

### Bug 3 — CORS_ORIGINS Type Mismatch

```
pydantic_settings.sources.SettingsError: error parsing value for field
"cors_origins" from source "EnvSettingsSource"
```

**Problem**: The ConfigMap set `CORS_ORIGINS` as a comma-separated string. pydantic-settings expects a JSON array for `list[str]` fields.

**Fix**: `["http://localhost:3000","http://localhost:5173"]`

**Lesson**: pydantic-settings JSON parsing rules differ from simple string splitting. Always test env var types in a local Python session before deploying.

---

### Bug 4 — Nginx Hardcoded Upstream Hostname

```
nginx: [emerg] host not found in upstream "backend"
```

**Problem**: The Docker image baked in `nginx.conf` with `proxy_pass http://backend:8000`. In Docker Compose, the container name is `backend`. In Kubernetes, the Service is `aiops-backend`. Kubernetes DNS resolver had no `backend` record.

**Fix**: A Helm ConfigMap renders `nginx.conf` with the correct `aiops-backend:8000` upstream, mounted over the image's default config at `/etc/nginx/conf.d/default.conf`.

**Lesson**: Docker Compose service names and Kubernetes service names are different. Never hardcode hostnames in Docker images. Always inject them at runtime via ConfigMaps or environment variables.

---

### Bug 5 — ErrImagePull for Public Images

```
Failed to pull image "prom/prometheus:v2.52.0": unexpected status from HEAD request
to http://registry-mirror:1273/v2/...: 500 Internal Server Error
```

**Problem**: Docker Desktop's internal registry mirror returned 500. Kubernetes workers couldn't reach Docker Hub through it.

**Fix**: Pre-pull images with `docker pull` — images in Docker's local store are shared with the Kubernetes nodes on Docker Desktop (single-host scenario).

**Lesson**: In production (AKS/EKS/GKE), always pre-pull critical images or use a private registry with your cluster's managed identity.

---

### Bug 6 — Stale Node Image Cache

**Problem**: After `docker build -t aiops-backend:latest`, `helm upgrade` triggered a rolling restart. The new pod used the **old** image from the node's cache. The node image cache is separate from Docker daemon's store in Docker Desktop multi-node Kubernetes.

**Fix**: Set `imagePullPolicy: Always` for app images (backend, frontend). Kubernetes re-reads the image on every pod start.

**Lesson**: `imagePullPolicy: IfNotPresent` is correct for versioned images (`:v1.2.3`) but wrong for mutable tags (`:latest`). Use `Always` for `:latest` or better — use immutable image tags in production.

---

### Bug 7 — port-forward Binds IPv6 Only

**Problem**: `kubectl port-forward` defaulted to `[::1]` (IPv6 loopback). Browsers on Windows default to `127.0.0.1` (IPv4), causing "connection refused".

**Fix**: `--address "127.0.0.1,::1"` or rely on the fact that Windows already had another port-forward job binding `0.0.0.0:8000`.

**Lesson**: `kubectl port-forward` is a development tool only. In production, use a proper LoadBalancer or Ingress controller — this problem disappears entirely.

---

## 10. AKS Production Roadmap

Moving from Docker Desktop to Azure Kubernetes Service (AKS) requires changes at every layer. This roadmap covers each one.

```
CURRENT STATE                           PRODUCTION TARGET
─────────────────────────────────       ────────────────────────────────────
Docker Desktop (single machine)    →    AKS cluster (multi-node, managed)
Local Docker images                →    Azure Container Registry (ACR)
SQLite                             →    Azure Database for PostgreSQL Flexible
--set groqApiKey=...               →    Azure Key Vault + CSI driver
LoadBalancer (Docker LB)           →    Application Gateway Ingress Controller
port-forward.ps1                   →    Proper DNS + TLS certificate
kubectl apply manual               →    GitHub Actions CI/CD + Helm
1 replica (SQLite constraint)      →    N replicas with PostgreSQL
```

---

### Phase 1 — Container Registry (ACR)

**Problem**: `aiops-backend:latest` only exists locally.
**Solution**: Push images to Azure Container Registry.

```bash
# Create ACR
az acr create --resource-group rg-aiops --name acraiops --sku Basic

# Authenticate Docker to ACR
az acr login --name acraiops

# Tag and push
docker tag aiops-backend:latest acraiops.azurecr.io/aiops-backend:1.0.0
docker tag aiops-frontend:latest acraiops.azurecr.io/aiops-frontend:1.0.0
docker push acraiops.azurecr.io/aiops-backend:1.0.0
docker push acraiops.azurecr.io/aiops-frontend:1.0.0
```

Update `values-production.yaml`:
```yaml
global:
  appImagePullPolicy: IfNotPresent   # tags are immutable in prod

backend:
  image:
    repository: acraiops.azurecr.io/aiops-backend
    tag: "1.0.0"   # never use :latest in production

frontend:
  image:
    repository: acraiops.azurecr.io/aiops-frontend
    tag: "1.0.0"
```

Attach ACR to AKS (so nodes can pull without credentials):
```bash
az aks update --resource-group rg-aiops --name aks-aiops --attach-acr acraiops
```

---

### Phase 2 — Database Migration (SQLite → PostgreSQL)

**Problem**: SQLite is a file-based DB. It cannot handle concurrent writes from multiple backend replicas.
**Solution**: Azure Database for PostgreSQL Flexible Server.

```bash
az postgres flexible-server create \
  --resource-group rg-aiops \
  --name psql-aiops \
  --sku-name Standard_B2ms \
  --tier Burstable \
  --version 16
```

Update `backend/config.py` — pydantic-settings already supports any SQLAlchemy URL:
```python
database_url: str = "postgresql+asyncpg://user:pass@psql-aiops.postgres.database.azure.com/aiops"
```

Update Helm chart: remove the SQLite PVC, remove the `database` volume mount, add the PostgreSQL URL to ConfigMap (host/dbname) and Secret (password).

This also unblocks **horizontal scaling**:
```yaml
# values-production.yaml
backend:
  replicas: 3          # now safe with PostgreSQL
  hpa:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 60
```

---

### Phase 3 — Secrets Management (Azure Key Vault)

**Problem**: `--set backend.groqApiKey=...` stores the key in Helm release history.
**Solution**: Azure Key Vault + Secrets Store CSI Driver.

```bash
# Install the CSI driver on AKS
az aks enable-addons --addons azure-keyvault-secrets-provider \
  --resource-group rg-aiops --name aks-aiops

# Store secret in Key Vault
az keyvault secret set --vault-name kv-aiops --name GROQ-API-KEY --value "gsk_..."
```

Create a `SecretProviderClass` (new Helm template in production):
```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: aiops-secrets
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"
    useVMManagedIdentity: "true"
    userAssignedIdentityID: <managed-identity-client-id>
    keyvaultName: kv-aiops
    objects: |
      array:
        - |
          objectName: GROQ-API-KEY
          objectType: secret
    tenantId: <tenant-id>
  secretObjects:
    - secretName: aiops-backend-secret
      type: Opaque
      data:
        - key: GROQ_API_KEY
          objectName: GROQ-API-KEY
```

The backend pod mounts the CSI volume, which creates the Kubernetes Secret automatically from Key Vault. **No secret is ever passed on the command line or stored in Helm history.**

---

### Phase 4 — Ingress & TLS (Application Gateway)

**Problem**: `kubectl port-forward` is a development hack. LoadBalancer type gets random external IPs.
**Solution**: Azure Application Gateway Ingress Controller (AGIC) + cert-manager.

```bash
# Enable AGIC on AKS
az aks enable-addons --addons ingress-appgw \
  --appgw-name agw-aiops \
  --resource-group rg-aiops --name aks-aiops

# Install cert-manager for automated TLS
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager --set installCRDs=true
```

Update `values-production.yaml`:
```yaml
frontend:
  service:
    type: ClusterIP    # no direct external access — use Ingress

backend:
  service:
    type: ClusterIP

ingress:
  enabled: true
  className: "azure/application-gateway"
  host: aiops.yourcompany.com
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  tls:
    - hosts:
        - aiops.yourcompany.com
      secretName: aiops-tls-secret
```

Traffic flow in production:
```
Internet → Azure Application Gateway (TLS termination)
    → Kubernetes Ingress
        → /api/*  → aiops-backend Service (ClusterIP)
        → /       → aiops-frontend Service (ClusterIP)
```

---

### Phase 5 — Observability Stack (Managed Services)

**Problem**: Running Prometheus, Loki, Grafana as pods wastes compute and requires maintenance.
**Solution**: Use Azure Managed Prometheus + Grafana.

```bash
# Enable Azure Monitor managed Prometheus
az aks update --resource-group rg-aiops --name aks-aiops \
  --enable-azure-monitor-metrics

# Create Azure Managed Grafana
az grafana create --name grafana-aiops --resource-group rg-aiops
```

Disable the in-cluster observability stack:
```yaml
# values-production.yaml
prometheus:
  enabled: false   # replaced by Azure Monitor

loki:
  enabled: false   # replaced by Azure Log Analytics

grafana:
  enabled: false   # replaced by Azure Managed Grafana
```

The backend's `PROMETHEUS_URL` and `LOKI_URL` point to the managed service endpoints.

---

### Phase 6 — CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Build and Deploy

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Azure Login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Login to ACR
        run: az acr login --name acraiops

      - name: Build & Push Backend
        run: |
          docker build -t acraiops.azurecr.io/aiops-backend:${{ github.sha }} ./backend
          docker push acraiops.azurecr.io/aiops-backend:${{ github.sha }}

      - name: Build & Push Frontend
        run: |
          docker build -t acraiops.azurecr.io/aiops-frontend:${{ github.sha }} ./frontend
          docker push acraiops.azurecr.io/aiops-frontend:${{ github.sha }}

      - name: Get AKS Credentials
        run: az aks get-credentials --resource-group rg-aiops --name aks-aiops

      - name: Helm Upgrade
        run: |
          helm upgrade --install aiops ./helm/aiops-sentinel \
            --namespace aiops-sentinel \
            --create-namespace \
            --values helm/values-production.yaml \
            --set backend.image.tag=${{ github.sha }} \
            --set frontend.image.tag=${{ github.sha }} \
            --wait --timeout 5m
```

**Key practices**:
- Image tag = `github.sha` — every build is immutable and unique
- `--wait` — pipeline only passes when all pods are Ready
- Production values in `values-production.yaml` — no secrets in the file
- Secrets come from Key Vault via the CSI driver, not from the pipeline

---

### AKS Architecture Target Diagram

```
                          GitHub Actions CI/CD
                          ┌─────────────────┐
                          │ Build → Push ACR │
                          │ helm upgrade     │
                          └────────┬────────┘
                                   │
                          ┌────────▼────────────────────────────────────┐
                          │           Azure Kubernetes Service (AKS)    │
                          │                                             │
Internet ──HTTPS──► Azure Application Gateway (AGIC + TLS)             │
                          │                                             │
                          │   ┌─────────────────────────────────────┐  │
                          │   │         Namespace: aiops-prod        │  │
                          │   │                                     │  │
                          │   │  frontend (ClusterIP)               │  │
                          │   │  backend × N replicas (ClusterIP)   │  │
                          │   │  ↕ Azure PostgreSQL Flexible        │  │
                          │   │  ↕ Azure Key Vault (CSI)            │  │
                          │   │  ↕ Azure Monitor (Prometheus)       │  │
                          │   │  ↕ Azure Log Analytics (Loki)       │  │
                          │   │  ↕ Azure Managed Grafana            │  │
                          │   └─────────────────────────────────────┘  │
                          │                                             │
                          │  Node Pool: system (3 nodes)               │
                          │  Node Pool: user (2-10 nodes, autoscale)   │
                          └─────────────────────────────────────────────┘
                                   │
                          ┌────────▼─────────────────────────────┐
                          │    Azure Container Registry (ACR)    │
                          │    aiops-backend:sha-abc123          │
                          │    aiops-frontend:sha-abc123         │
                          └──────────────────────────────────────┘
```

---

### Production Readiness Checklist

| Item | Current (Docker Desktop) | AKS Target |
|---|---|---|
| Container registry | Local Docker daemon | ACR (private, geo-replicated) |
| Image tags | `:latest` (mutable) | `:git-sha` (immutable) |
| Database | SQLite (1 writer) | Azure PostgreSQL Flexible |
| Secrets | `--set` CLI flag | Azure Key Vault + CSI |
| TLS | None | cert-manager + Let's Encrypt |
| Ingress | port-forward.ps1 | AGIC + custom domain |
| Replicas | 1 (SQLite constraint) | 2–10 (HPA + PostgreSQL) |
| Observability | In-cluster pods | Azure Monitor + Managed Grafana |
| CI/CD | Manual docker build + helm upgrade | GitHub Actions |
| Node scaling | Fixed (Docker Desktop) | AKS Cluster Autoscaler |
| Backup | None | Azure Backup for PostgreSQL + PVC snapshots |
| RBAC | None | Azure AD workload identity + K8s RBAC |
| Network policy | None | Azure CNI + NetworkPolicy resources |
| Cost control | N/A | Azure Spot nodes for non-critical workloads |

---

### Estimated AKS Running Cost (Basic Production)

| Resource | SKU | Monthly Estimate |
|---|---|---|
| AKS Cluster (management) | Free tier | $0 |
| 3× System nodes | Standard_D2s_v3 | ~$210 |
| 2× User nodes (autoscale 2–5) | Standard_D4s_v3 | ~$280 |
| Azure PostgreSQL Flexible | Standard_B2ms | ~$50 |
| Azure Container Registry | Basic | ~$5 |
| Azure Key Vault | Standard | ~$5 |
| Azure Managed Grafana | Standard | ~$65 |
| Azure Monitor | Pay-per-use | ~$30 |
| Application Gateway | WAF_v2 | ~$180 |
| **Total** | | **~$825/month** |

> Costs can be reduced 50–60% using Azure Reserved Instances (1-year commitment) or Spot node pools for the backend workload.
