{{/*
═══════════════════════════════════════════════════════════════════════════════
AIOps Sentinel — Helm Template Helpers  (_helpers.tpl)

CONCEPT: This file defines reusable named templates — think of them as
"functions" in Helm's templating language (Go templates).

Key syntax:
  {{- define "template.name" -}}  ... {{- end }}  → define a template
  {{ include "template.name" . }}                  → call a template
  {{- ... -}}  → the dashes trim surrounding whitespace/newlines

The dot (.) represents the current "context" — in most templates, this is
the top-level Helm object containing:
  .Values      → your values.yaml data
  .Release     → release info (.Release.Name, .Release.Namespace, etc.)
  .Chart       → Chart.yaml data (.Chart.Name, .Chart.Version, etc.)
  .Files       → access to non-template files in the chart
  .Capabilities → Kubernetes API capabilities

═══════════════════════════════════════════════════════════════════════════════
*/}}

{{/*────────────────────────────────────────────────────────────────────────────
Chart name — used in labels. Truncated to 63 chars (K8s label value limit).
*/}}
{{- define "aiops-sentinel.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*────────────────────────────────────────────────────────────────────────────
Chart label value — used in the helm.sh/chart label.
Format: "chart-name-chart-version" (e.g., "aiops-sentinel-0.1.0")
*/}}
{{- define "aiops-sentinel.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*────────────────────────────────────────────────────────────────────────────
Namespace helper.
Uses global.namespace from values.yaml, or falls back to .Release.Namespace.
*/}}
{{- define "aiops-sentinel.namespace" -}}
{{- .Values.global.namespace | default .Release.Namespace }}
{{- end }}

{{/*────────────────────────────────────────────────────────────────────────────
Common labels — applied to every resource.
These follow the Kubernetes recommended label convention:
  https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/

They enable:
  - kubectl get all -l helm.sh/chart=aiops-sentinel-0.1.0
  - helm upgrade detecting managed resources
  - kubectl top pods -l app.kubernetes.io/instance=aiops
*/}}
{{- define "aiops-sentinel.labels" -}}
helm.sh/chart: {{ include "aiops-sentinel.chart" . }}
app.kubernetes.io/name: {{ include "aiops-sentinel.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*────────────────────────────────────────────────────────────────────────────
Component-specific labels.

Usage:
  {{- include "aiops-sentinel.componentLabels" (dict "component" "backend" "ctx" .) | nindent 6 }}

IMPORTANT: The selector labels on a Deployment/Service pair MUST match exactly.
Once a Deployment is created with a selector, it cannot be changed without
deleting and recreating the resource (breaking change).
*/}}
{{- define "aiops-sentinel.componentLabels" -}}
app.kubernetes.io/name: {{ .ctx.Chart.Name }}-{{ .component }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*────────────────────────────────────────────────────────────────────────────
Component name helpers.
All resources for a component share this consistent naming prefix.
Pattern: <release-name>-<component>

Examples (with release name "aiops"):
  aiops-backend, aiops-frontend, aiops-prometheus, aiops-loki, aiops-grafana
*/}}
{{- define "aiops-sentinel.backend.name" -}}
{{- printf "%s-backend" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "aiops-sentinel.frontend.name" -}}
{{- printf "%s-frontend" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "aiops-sentinel.prometheus.name" -}}
{{- printf "%s-prometheus" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "aiops-sentinel.loki.name" -}}
{{- printf "%s-loki" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "aiops-sentinel.grafana.name" -}}
{{- printf "%s-grafana" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
