# AIOps Sentinel — Kubernetes & Helm Guide

A practical, hands-on guide to Kubernetes and Helm using **your own project** as the learning playground.

---

## Table of Contents

1. [Mental Model — What Is Kubernetes?](#1-mental-model--what-is-kubernetes)
2. [Kubernetes Architecture](#2-kubernetes-architecture)
3. [Core Kubernetes Objects](#3-core-kubernetes-objects)
4. [Kubernetes DNS & Service Discovery](#4-kubernetes-dns--service-discovery)
5. [Helm — The Package Manager](#5-helm--the-package-manager)
6. [Pre-Deployment Setup](#6-pre-deployment-setup)
7. [Deploy AIOps Sentinel on Kubernetes](#7-deploy-aiops-sentinel-on-kubernetes)
8. [Essential kubectl Commands](#8-essential-kubectl-commands)
9. [Troubleshooting Runbook](#9-troubleshooting-runbook)
10. [Helm Chart Deep Dive](#10-helm-chart-deep-dive)
11. [Scaling & Production Patterns](#11-scaling--production-patterns)
12. [What to Learn Next](#12-what-to-learn-next)

---

## 1. Mental Model — What Is Kubernetes?

Think of Kubernetes as **an operating system for a cluster of machines**.

| Traditional Server | Kubernetes |
|---|---|
| You SSH into a server and run `python app.py` | You declare "I want 3 replicas of this container" |
| App crashes → someone pages you at 3am | App crashes → Kubernetes restarts it automatically |
| Need more capacity → provision a new VM manually | Need more capacity → `kubectl scale --replicas=10` |
| Config is in files on the server | Config is in the Kubernetes API (declarative) |

**Declarative vs. Imperative:**
- **Imperative**: "Start the container, connect it to the network, expose port 8000..."
- **Declarative**: "Here is my desired state (YAML). Make it so." ← Kubernetes approach

You write YAML describing **what you want**. Kubernetes figures out **how to make it happen**.

---

## 2. Kubernetes Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Control Plane (Master)                     │  │
│  │                                                              │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐  │  │
│  │  │ API Server  │  │  Scheduler   │  │ Controller Manager │  │  │
│  │  │ (REST API)  │  │ (place pods) │  │ (reconcile loops)  │  │  │
│  │  └────────────┘  └──────────────┘  └────────────────────┘  │  │
│  │           │               │                  │               │  │
│  │  ┌────────┴───────────────┴──────────────────┴────────────┐ │  │
│  │  │                       etcd                              │ │  │
│  │  │          (distributed key-value store — the brain)      │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │   Worker Node 1  │  │   Worker Node 2  │  │   Worker Node 3  │   │
│  │                  │  │                  │  │                  │   │
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │   │
│  │  │   kubelet  │  │  │  │   kubelet  │  │  │  │   kubelet  │  │   │
│  │  │(node agent)│  │  │  │(node agent)│  │  │  │(node agent)│  │   │
│  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │   │
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │   │
│  │  │ kube-proxy │  │  │  │ kube-proxy │  │  │  │ kube-proxy │  │   │
│  │  │(networking)│  │  │  │(networking)│  │  │  │(networking)│  │   │
│  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │   │
│  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────────┐  │   │
│  │  │ Container  │  │  │  │ Container  │  │  │  │ Container  │  │   │
│  │  │  Runtime   │  │  │  │  Runtime   │  │  │  │  Runtime   │  │   │
│  │  │ (containerd│  │  │  │ (containerd│  │  │  │ (containerd│  │   │
│  │  └────────────┘  │  │  └────────────┘  │  │  └────────────┘  │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Docker Desktop** gives you a single-node cluster where the control plane and worker are the same machine — perfect for learning.

**Components explained:**
- **API Server**: The front door. `kubectl` talks to this. Everything goes through it.
- **etcd**: The database. Stores ALL cluster state. If etcd dies, your cluster "forgets" everything.
- **Scheduler**: Decides WHICH node a new Pod should run on (based on resources, affinity, etc.)
- **Controller Manager**: Runs control loops that make reality match your desired state. Deployment controller, ReplicaSet controller, etc.
- **kubelet**: Agent running on each node. Pulls images, starts/stops containers, reports status.
- **kube-proxy**: Manages iptables/ipvs rules for Service networking on each node.

---

## 3. Core Kubernetes Objects

### 3.1 Pod

A Pod is the **smallest deployable unit** in Kubernetes. It wraps one or more containers that share:
- The same network namespace (same IP address)
- The same storage volumes

```
┌──────────────────────────────────────────────┐
│                    Pod                        │
│  IP: 10.244.1.8                              │
│                                              │
│  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Main Container   │  │  Sidecar (e.g.,  │  │
│  │  (backend:latest) │  │  log shipper)    │  │
│  └──────────────────┘  └──────────────────┘  │
│                                              │
│  Volumes: [/app/data (PVC), /tmp (emptyDir)] │
└──────────────────────────────────────────────┘
```

**You almost never create Pods directly.** Use a Deployment instead, which manages Pods.

### 3.2 Deployment

Controls a **ReplicaSet** which controls **Pods**. Gives you rolling updates and rollbacks.

```
Deployment (desired: 3 replicas)
    └── ReplicaSet (manages the pod count)
            ├── Pod 1  (running)
            ├── Pod 2  (running)
            └── Pod 3  (running)
```

```yaml
# deployment.yaml — minimal example
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 3                     # I want 3 pods
  selector:
    matchLabels:
      app: my-app                 # Pods this controls
  template:
    metadata:
      labels:
        app: my-app               # Must match selector!
    spec:
      containers:
        - name: my-app
          image: my-app:latest
          ports:
            - containerPort: 8000
```

### 3.3 Service

A **stable network endpoint** for a set of Pods. Pods have ephemeral IPs; a Service provides a fixed VIP.

```
                         Selector (app=backend)
                               │
Client → Service (ClusterIP: 10.96.1.50:8000)
               │
        ┌──────┴───────────────┐
        │         │            │
      Pod 1     Pod 2        Pod 3
  (10.244.1.2) (10.244.1.3) (10.244.2.1)
```

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
spec:
  selector:
    app: backend    # Route to pods with this label
  ports:
    - port: 8000        # Service port
      targetPort: 8000  # Container port
  type: ClusterIP     # Internal only
```

### 3.4 ConfigMap

Non-sensitive configuration, passed to Pods as env vars or files.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: backend-config
data:
  PROMETHEUS_URL: "http://prometheus:9090"
  SIMULATION_INTERVAL_SECONDS: "10"
```

Consumed in a Pod:
```yaml
envFrom:
  - configMapRef:
      name: backend-config
# OR as individual envs:
env:
  - name: PROMETHEUS_URL
    valueFrom:
      configMapKeyRef:
        name: backend-config
        key: PROMETHEUS_URL
```

### 3.5 Secret

Like ConfigMap, but for sensitive data (base64-encoded, can be encrypted at rest).

```yaml
apiVersion: v1
kind: Secret
type: Opaque
metadata:
  name: backend-secret
stringData:           # Kubernetes encodes to base64 automatically
  GROQ_API_KEY: "gsk_your_real_key"
```

### 3.6 PersistentVolumeClaim (PVC)

A **request for storage** that survives Pod restarts.

```
StorageClass (defines HOW)
     ↓ provisions
PersistentVolume (PV — the actual disk)
     ↑ binds to
PersistentVolumeClaim (PVC — your request)
     ↑ mounted by
Pod (via volumes + volumeMounts)
```

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: backend-data
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 2Gi
```

In a Pod:
```yaml
volumes:
  - name: data
    persistentVolumeClaim:
      claimName: backend-data
containers:
  - name: backend
    volumeMounts:
      - name: data
        mountPath: /app/data
```

### 3.7 Ingress

L7 HTTP routing — one entry point, routes by host/path.

```
browser → Ingress (port 80)
              ├── /api/*  → backend Service
              └── /       → frontend Service
```

### 3.8 HorizontalPodAutoscaler (HPA)

Auto-scales replica count based on CPU/memory metrics.

```
HPA watches: CPU usage of backend pods
when usage > 70% of requests.cpu → scale up
when usage < 30% for 5 minutes → scale down
(within minReplicas–maxReplicas bounds)
```

### 3.9 Namespace

Virtual cluster within a cluster. Provides isolation and scope.

```bash
kubectl get pods -n aiops-sentinel    # Pods in this namespace
kubectl get pods -A                   # Pods in ALL namespaces
```

---

## 4. Kubernetes DNS & Service Discovery

This is one of the most important concepts for microservices.

**Every Service gets a DNS name:**
```
<service-name>.<namespace>.svc.cluster.local
```

Examples for this project (namespace: `aiops-sentinel`, release: `aiops`):

| Service | Full DNS Name | Short Name (same namespace) |
|---|---|---|
| Backend | `aiops-backend.aiops-sentinel.svc.cluster.local:8000` | `aiops-backend:8000` |
| Prometheus | `aiops-prometheus.aiops-sentinel.svc.cluster.local:9090` | `aiops-prometheus:9090` |
| Loki | `aiops-loki.aiops-sentinel.svc.cluster.local:3100` | `aiops-loki:3100` |
| Grafana | `aiops-grafana.aiops-sentinel.svc.cluster.local:3000` | `aiops-grafana:3000` |

**That's why our ConfigMap has:**
```yaml
PROMETHEUS_URL: "http://aiops-prometheus:9090"
LOKI_URL: "http://aiops-loki:3100"
```

And Grafana's datasources.yaml has:
```yaml
url: http://aiops-prometheus:9090
url: http://aiops-loki:3100
```

These are **not** `localhost` — they're DNS names resolved by CoreDNS running inside the cluster.

---

## 5. Helm — The Package Manager

Helm is to Kubernetes what `apt`/`pip`/`npm` is to traditional software.

```
┌─────────────────────────────────────────────────────────┐
│                    Helm Chart                           │
│                                                         │
│  Chart.yaml      ← metadata (name, version, description)│
│  values.yaml     ← default configuration parameters     │
│  templates/      ← Kubernetes YAML with Go templating   │
│    _helpers.tpl  ← reusable template functions          │
│    NOTES.txt     ← printed after helm install           │
│    deployment.yaml, service.yaml, ...                   │
│  .helmignore     ← files to exclude from package        │
└─────────────────────────────────────────────────────────┘
```

### How Helm Works

```
values.yaml  +  templates/  →  helm template  →  rendered K8s YAML  →  kubectl apply
```

1. You write templates with `{{ .Values.backend.replicas }}` placeholders
2. Helm renders them using values from `values.yaml` (merged with any `--set` overrides)
3. The rendered YAML is applied to the Kubernetes API

### Key Template Syntax

```yaml
# Simple value substitution
replicas: {{ .Values.backend.replicas }}

# With default fallback
name: {{ .Values.nameOverride | default .Chart.Name }}

# Conditional block
{{- if .Values.prometheus.enabled }}
# ... only rendered if prometheus.enabled is true
{{- end }}

# Loop over a list
{{- range .Values.corsOrigins }}
- {{ . }}
{{- end }}

# Include a named template (from _helpers.tpl)
labels:
  {{- include "aiops-sentinel.labels" . | nindent 4 }}

# toYaml — dump a YAML structure (preserves indentation with nindent)
resources:
  {{- toYaml .Values.backend.resources | nindent 10 }}

# String functions
{{ .Values.backend.image.tag | quote }}    # wrap in quotes: "latest"
{{ "hello world" | upper }}               # "HELLO WORLD"
{{ printf "http://%s:%d" "host" 8000 }}   # "http://host:8000"
```

### The Dash `{{-` and `-}}` Trick

```yaml
# Without dashes → extra blank line
{{ if true }}

# With dashes → whitespace trimmed
{{- if true }}
```

---

## 6. Pre-Deployment Setup

### Step 1: Enable Kubernetes in Docker Desktop

1. Open Docker Desktop
2. Settings → Kubernetes → ✅ Enable Kubernetes
3. Wait for the green "Kubernetes is running" indicator
4. Verify: `kubectl cluster-info`

### Step 2: Install Helm

```powershell
# Option A: winget (Windows Package Manager)
winget install Helm.Helm

# Option B: Chocolatey
choco install kubernetes-helm

# Option C: Scoop
scoop install helm

# Verify
helm version
```

### Step 3: Build the Docker Images

Kubernetes needs the images to exist locally. Build them:

```powershell
# From the project root (c:\Python\AIOps.Sentinel)
cd c:\Python\AIOps.Sentinel

# Build backend image
docker build -t aiops-backend:latest ./backend

# Build frontend image
docker build -t aiops-frontend:latest ./frontend

# Verify images exist
docker images | Select-String "aiops"
```

> **Why?** Docker Desktop shares the Docker daemon with its Kubernetes cluster.
> Images you build with `docker build` are immediately available to Kubernetes pods
> without needing to push to a registry, as long as `imagePullPolicy: IfNotPresent`.

### Step 4: Verify kubectl Context

```powershell
# Show current context
kubectl config current-context
# Should output: docker-desktop

# If not, switch to it
kubectl config use-context docker-desktop

# Verify the cluster is reachable
kubectl get nodes
# NAME             STATUS   ROLES           AGE   VERSION
# docker-desktop   Ready    control-plane   ...   v1.x.x
```

---

## 7. Deploy AIOps Sentinel on Kubernetes

### Option A: Quick Deploy (minimal flags)

```powershell
cd c:\Python\AIOps.Sentinel

# Install the Helm chart with release name "aiops"
helm install aiops ./helm/aiops-sentinel `
  --set backend.groqApiKey="gsk_your_key_here"
```

### Option B: Deploy with Custom Values File

Create `helm/values-local.yaml` (do NOT commit this file with secrets!):

```yaml
backend:
  groqApiKey: "gsk_your_actual_key"
  prometheusEnabled: true
  lokiEnabled: true

grafana:
  adminPassword: "my-secure-password"
```

```powershell
helm install aiops ./helm/aiops-sentinel -f helm/values-local.yaml
```

### Option C: Dry Run First (Highly Recommended)

```powershell
# Render all templates and inspect them WITHOUT applying to the cluster
helm template aiops ./helm/aiops-sentinel --set backend.groqApiKey="test" | more

# Or save to a file to review
helm template aiops ./helm/aiops-sentinel > rendered-manifests.yaml
```

### Watch the Deployment

```powershell
# Watch pods come up in real-time (Ctrl+C to stop)
kubectl get pods -n aiops-sentinel -w

# Expected output (after ~60-90 seconds):
# NAME                                  READY   STATUS    RESTARTS   AGE
# aiops-backend-7d4f5b9c6-x8p2n         1/1     Running   0          2m
# aiops-frontend-6f9b8c7d5-k3q7m        1/1     Running   0          2m
# aiops-prometheus-5c8d6f4b9-m9x2p      1/1     Running   0          2m
# aiops-loki-8b7c9d5f6-p4k8n            1/1     Running   0          2m
# aiops-grafana-9f6b8c7d4-r7j2m         1/1     Running   0          2m
```

### Access the Application

| Service | URL |
|---|---|
| Frontend (React) | http://localhost:30300 |
| Backend API | http://localhost:30800 |
| Backend Docs (Swagger) | http://localhost:30800/docs |
| Prometheus | http://localhost:30909 |
| Grafana | http://localhost:30301 (admin / admin) |

---

## 8. Essential kubectl Commands

### Viewing Resources

```powershell
# List all resources in the namespace
kubectl get all -n aiops-sentinel

# Get pods with more details (node, IP, status)
kubectl get pods -n aiops-sentinel -o wide

# Get a resource in YAML format (shows full state including status)
kubectl get deployment aiops-backend -n aiops-sentinel -o yaml

# Describe a resource (human-readable with Events section — great for debugging)
kubectl describe pod <pod-name> -n aiops-sentinel
kubectl describe deployment aiops-backend -n aiops-sentinel
kubectl describe service aiops-backend -n aiops-sentinel

# List services
kubectl get svc -n aiops-sentinel

# List PVCs
kubectl get pvc -n aiops-sentinel

# List ConfigMaps
kubectl get configmap -n aiops-sentinel

# List Secrets
kubectl get secret -n aiops-sentinel
```

### Logs

```powershell
# View logs of a specific pod
kubectl logs <pod-name> -n aiops-sentinel

# Follow logs (like tail -f)
kubectl logs -f <pod-name> -n aiops-sentinel

# Logs for a specific container in the pod
kubectl logs <pod-name> -c backend -n aiops-sentinel

# Logs by label (useful when pod name changes)
kubectl logs -n aiops-sentinel -l app.kubernetes.io/component=backend -f

# View previous pod's logs (after a crash)
kubectl logs <pod-name> -n aiops-sentinel --previous
```

### Exec Into Containers

```powershell
# Open interactive shell (like SSH)
kubectl exec -it <pod-name> -n aiops-sentinel -- /bin/bash

# Run a one-off command
kubectl exec <pod-name> -n aiops-sentinel -- env | Select-String "GROQ"

# Shortcut: get backend pod name and exec in one command
$pod = kubectl get pod -n aiops-sentinel -l app.kubernetes.io/component=backend -o jsonpath='{.items[0].metadata.name}'
kubectl exec -it $pod -n aiops-sentinel -- /bin/bash
```

### Scaling

```powershell
# Scale manually
kubectl scale deployment aiops-backend -n aiops-sentinel --replicas=2

# Check status
kubectl rollout status deployment/aiops-backend -n aiops-sentinel
```

### Rollouts & Rollbacks

```powershell
# View rollout history
kubectl rollout history deployment/aiops-backend -n aiops-sentinel

# Roll back to previous version
kubectl rollout undo deployment/aiops-backend -n aiops-sentinel

# Roll back to specific revision
kubectl rollout undo deployment/aiops-backend -n aiops-sentinel --to-revision=2

# Restart all pods in a deployment (like docker-compose restart)
kubectl rollout restart deployment/aiops-backend -n aiops-sentinel
```

### Port Forwarding (for debugging)

```powershell
# Forward local port 8000 to the backend service
# Useful when service type is ClusterIP (no NodePort)
kubectl port-forward svc/aiops-backend -n aiops-sentinel 8000:8000

# Forward to a specific pod
kubectl port-forward pod/<pod-name> -n aiops-sentinel 8000:8000
```

### Events (Best Debugging Tool)

```powershell
# See recent events — shows WHY a pod is failing
kubectl get events -n aiops-sentinel --sort-by='.lastTimestamp'

# Watch events in real-time
kubectl get events -n aiops-sentinel -w
```

---

## 9. Troubleshooting Runbook

### Problem: Pod stuck in `Pending`

**Cause**: Scheduler can't place the pod.

```powershell
kubectl describe pod <pod-name> -n aiops-sentinel
# Look at the Events section at the bottom
```

Common reasons:
- **Insufficient CPU/memory**: Reduce resource requests in values.yaml
- **PVC not bound**: `kubectl get pvc -n aiops-sentinel` — check status
- **Node selector / taint**: For Docker Desktop, usually not an issue

### Problem: Pod in `ImagePullBackOff` or `ErrImagePull`

**Cause**: Kubernetes can't pull the image.

```powershell
kubectl describe pod <pod-name> -n aiops-sentinel
# Events will show the error message
```

Fix:
```powershell
# Make sure the image was built locally
docker images | Select-String "aiops"

# Rebuild if missing
docker build -t aiops-backend:latest ./backend

# Check the imagePullPolicy in values.yaml
# Must be IfNotPresent (not Always) for local images
```

### Problem: Pod in `CrashLoopBackOff`

**Cause**: Container starts but immediately crashes (unhealthy).

```powershell
# See why it crashed
kubectl logs <pod-name> -n aiops-sentinel --previous

# Describe for exit code and restart count
kubectl describe pod <pod-name> -n aiops-sentinel
```

Common causes for this project:
- `DATABASE_URL` path doesn't exist → check the PVC is mounted correctly
- Port conflict → check the container port matches the app's listening port
- Missing env var → check the ConfigMap/Secret

### Problem: Pod `Running` but app unreachable

**Cause**: Service selector doesn't match pod labels, or wrong port.

```powershell
# Check endpoints — does the service see the pods?
kubectl get endpoints -n aiops-sentinel
# aiops-backend   10.244.0.8:8000   (should show a pod IP)
# If empty: selector mismatch between Service and Deployment

# Verify labels on the pod match the service selector
kubectl get pod <pod-name> -n aiops-sentinel --show-labels

# Test inside the cluster with a temporary debug pod
kubectl run debug --rm -it --image=alpine --restart=Never -n aiops-sentinel -- sh
# Inside: wget -O- http://aiops-backend:8000/health
```

### Problem: `helm install` fails with "already exists"

```powershell
# Uninstall and reinstall
helm uninstall aiops -n aiops-sentinel

# Or upgrade instead of install
helm upgrade --install aiops ./helm/aiops-sentinel
```

### Problem: ConfigMap changes not picked up

ConfigMaps mounted as env vars require a pod restart:
```powershell
kubectl rollout restart deployment/aiops-backend -n aiops-sentinel
```

---

## 10. Helm Chart Deep Dive

### Release Lifecycle

```
helm install  →  revision 1
helm upgrade  →  revision 2 (stores old manifest for rollback)
helm upgrade  →  revision 3
helm rollback →  revision 2 (reapplied)
helm uninstall → removes all resources EXCEPT PVCs with keep policy
```

### Useful Helm Commands

```powershell
# List all releases
helm list -A

# Check release status and notes
helm status aiops -n aiops-sentinel

# Inspect default values of a chart
helm show values ./helm/aiops-sentinel

# View rendered templates (dry run — does NOT apply)
helm template aiops ./helm/aiops-sentinel --debug

# Lint your chart for errors
helm lint ./helm/aiops-sentinel

# Upgrade with new values (rolling update triggered automatically)
helm upgrade aiops ./helm/aiops-sentinel `
  --set backend.replicas=2 `
  -n aiops-sentinel

# Upgrade and reset values to chart defaults
helm upgrade aiops ./helm/aiops-sentinel --reset-values

# View upgrade history
helm history aiops -n aiops-sentinel

# Roll back to previous revision
helm rollback aiops -n aiops-sentinel

# Package chart into a .tgz (for distribution)
helm package ./helm/aiops-sentinel
```

### Understanding `_helpers.tpl`

`_helpers.tpl` defines reusable named templates. The naming convention
`chart-name.thing` prevents conflicts with sub-charts.

```
{{- define "aiops-sentinel.backend.name" -}}
{{- printf "%s-backend" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
```

Calling it:
```yaml
name: {{ include "aiops-sentinel.backend.name" . }}
# Output: aiops-backend  (when release name is "aiops")
```

Passing extra context (using dict):
```yaml
{{- include "aiops-sentinel.componentLabels" (dict "component" "backend" "ctx" .) | nindent 6 }}
```

### The `checksum/config` Pattern

When your ConfigMap changes, pods need to restart to pick up new values.
This pattern solves it automatically:

```yaml
metadata:
  annotations:
    checksum/config: {{ include (print $.Template.BasePath "/backend/configmap.yaml") . | sha256sum }}
```

When the configmap content changes → its hash changes → annotation changes
→ Helm sees this as a Deployment spec change → rolling restart triggered automatically.

### Values Override Hierarchy (lowest to highest priority)

```
Chart's values.yaml (defaults)
    ↑
-f values-base.yaml
    ↑
-f values-prod.yaml
    ↑
--set key=value (CLI flag)
```

---

## 11. Scaling & Production Patterns

### Enable HPA (Auto-scaling)

```powershell
# First check metrics-server is running
kubectl get pods -n kube-system | Select-String "metrics"

# Enable HPA in values
helm upgrade aiops ./helm/aiops-sentinel `
  --set backend.hpa.enabled=true `
  --set backend.hpa.minReplicas=2 `
  --set backend.hpa.maxReplicas=5 `
  -n aiops-sentinel

# Watch it scale
kubectl get hpa -n aiops-sentinel -w
```

### Use Ingress Instead of NodePort

```powershell
# Install nginx ingress controller
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx

# Wait for it
kubectl get pods -n default -w -l app.kubernetes.io/name=ingress-nginx

# Add to hosts file: 127.0.0.1  aiops.local
# On Windows: C:\Windows\System32\drivers\etc\hosts

# Redeploy with ingress enabled and ClusterIP services
helm upgrade aiops ./helm/aiops-sentinel `
  --set ingress.enabled=true `
  --set backend.service.type=ClusterIP `
  --set frontend.service.type=ClusterIP `
  -n aiops-sentinel

# Access at: http://aiops.local
```

### Production: Multiple Environments

```
helm/
  values.yaml            # base defaults
  values-dev.yaml        # development overrides
  values-staging.yaml    # staging overrides
  values-prod.yaml       # production overrides (no secrets!)
```

```powershell
# Deploy to dev
helm upgrade --install aiops-dev ./helm/aiops-sentinel `
  -f helm/values.yaml `
  -f helm/values-dev.yaml `
  --set backend.groqApiKey=$env:GROQ_API_KEY `
  -n aiops-dev

# Deploy to prod
helm upgrade --install aiops-prod ./helm/aiops-sentinel `
  -f helm/values.yaml `
  -f helm/values-prod.yaml `
  --set backend.groqApiKey=$env:GROQ_API_KEY `
  -n aiops-prod
```

### Resource Optimization

```yaml
# values-prod.yaml example
backend:
  replicas: 2
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 2000m
      memory: 1Gi
  hpa:
    enabled: true
    minReplicas: 2
    maxReplicas: 8
    targetCPUUtilizationPercentage: 60
```

---

## 12. What to Learn Next

### Immediate next steps (in order):

1. **Deploy and break things** — change values, watch what happens, fix it.
   The best way to learn Kubernetes is to make mistakes in a safe environment.

2. **k9s** — a terminal UI for Kubernetes that makes navigation much easier.
   ```powershell
   winget install k9s
   k9s
   ```

3. **Lens** — a GUI Kubernetes IDE for Windows. Download from k8slens.dev.

4. **ConfigMap hot reloading** — learn about volume-mounted ConfigMaps
   that update without pod restarts (vs env var ConfigMaps that require restart).

5. **RBAC** (Role-Based Access Control) — control who can do what in the cluster.
   `kubectl explain role`, `kubectl explain clusterrole`.

6. **NetworkPolicy** — Kubernetes firewall. Restrict which pods can talk to which.

7. **StatefulSets** — like Deployments but for stateful apps (databases).
   Provides stable pod names (pod-0, pod-1) and ordered startup/shutdown.

8. **Jobs and CronJobs** — run tasks to completion on a schedule.

9. **Helm Subchart Dependencies** — instead of writing Prometheus/Loki/Grafana
   from scratch, use the official community charts as dependencies:
   ```yaml
   # Chart.yaml
   dependencies:
     - name: prometheus
       version: "25.x.x"
       repository: https://prometheus-community.github.io/helm-charts
     - name: grafana
       version: "7.x.x"
       repository: https://grafana.github.io/helm-charts
   ```

10. **GitOps with ArgoCD or Flux** — let Git be the single source of truth.
    Push to Git → ArgoCD automatically deploys to Kubernetes.

### Key Resources

- **Official docs**: https://kubernetes.io/docs/concepts/
- **Helm docs**: https://helm.sh/docs/
- **Interactive learning**: https://killercoda.com (free browser-based K8s labs)
- **Certified Kubernetes Admin (CKA)**: industry-recognized exam
- **kubectl cheat sheet**: https://kubernetes.io/docs/reference/kubectl/cheatsheet/

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                    KUBECTL QUICK REFERENCE                      │
├──────────────────────────────┬──────────────────────────────────┤
│ kubectl get pods -n NS       │ List pods in namespace           │
│ kubectl get all -n NS        │ List everything in namespace     │
│ kubectl describe pod NAME    │ Detailed pod info + events       │
│ kubectl logs NAME -f         │ Follow pod logs                  │
│ kubectl exec -it NAME -- sh  │ Shell into pod                   │
│ kubectl get events -n NS     │ See cluster events (debug first!)│
│ kubectl get endpoints -n NS  │ Check service routing            │
│ kubectl port-forward svc/..  │ Forward local port to service    │
├──────────────────────────────┼──────────────────────────────────┤
│ helm install NAME ./chart    │ First deployment                 │
│ helm upgrade NAME ./chart    │ Update existing release          │
│ helm upgrade --install       │ Install if not exist, upgrade    │
│ helm template NAME ./chart   │ Preview rendered YAML            │
│ helm lint ./chart            │ Check chart for errors           │
│ helm status NAME             │ Release status + NOTES           │
│ helm rollback NAME           │ Revert to previous revision      │
│ helm uninstall NAME          │ Delete release                   │
└──────────────────────────────┴──────────────────────────────────┘
```
