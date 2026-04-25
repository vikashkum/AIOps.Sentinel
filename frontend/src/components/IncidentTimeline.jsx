import { clsx } from 'clsx'
import { Rocket, AlertTriangle, AlertCircle, Brain, CheckCircle } from 'lucide-react'
import { format } from 'date-fns'

const EVENT_CONFIG = {
  deployment: { icon: Rocket,        color: 'text-indigo-400', bg: 'bg-indigo-500/20', label: 'Deployment' },
  anomaly_w:  { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/20', label: 'Warning' },
  anomaly_c:  { icon: AlertCircle,   color: 'text-red-400',    bg: 'bg-red-500/20',    label: 'Critical' },
  ai:         { icon: Brain,         color: 'text-purple-400', bg: 'bg-purple-500/20', label: 'AI Correlated' },
  resolved:   { icon: CheckCircle,   color: 'text-green-400',  bg: 'bg-green-500/20',  label: 'Resolved' },
}

function buildTimeline(incident) {
  if (!incident) return []
  const events = []

  if (incident.trigger_event) {
    events.push({
      type: 'deployment',
      ts: new Date(incident.trigger_event.timestamp),
      label: `Deployed ${incident.trigger_event.service} ${incident.trigger_event.version ?? ''}`,
    })
  }

  const anomalies = incident.raw_anomalies ?? []
  anomalies.slice(0, 5).forEach((a) => {
    events.push({
      type: a.severity === 'critical' ? 'anomaly_c' : 'anomaly_w',
      ts: new Date(a.timestamp),
      label: `${a.service}: ${a.metric.replace(/_/g, ' ')} = ${a.value} (${a.deviation_pct}% deviation)`,
    })
  })

  if (incident.ai_summary) {
    events.push({
      type: 'ai',
      ts: new Date(incident.last_updated ?? incident.first_detected),
      label: `AI correlated ${incident.anomaly_ids?.length ?? 0} signals into 1 incident`,
    })
  }

  if (incident.status === 'resolved') {
    events.push({
      type: 'resolved',
      ts: new Date(incident.last_updated),
      label: 'Incident resolved',
    })
  }

  return events.sort((a, b) => a.ts - b.ts)
}

export default function IncidentTimeline({ incident }) {
  if (!incident) return null

  const timeline = buildTimeline(incident)

  return (
    <div className="space-y-1">
      {timeline.map((ev, idx) => {
        const cfg = EVENT_CONFIG[ev.type] ?? EVENT_CONFIG.anomaly_w
        const Icon = cfg.icon

        return (
          <div key={idx} className="flex gap-3 group">
            {/* Connector line */}
            <div className="flex flex-col items-center">
              <div className={clsx('p-1.5 rounded-lg mt-0.5 shrink-0', cfg.bg)}>
                <Icon size={12} className={cfg.color} />
              </div>
              {idx < timeline.length - 1 && (
                <div className="w-px flex-1 bg-sentinel-border mt-1" />
              )}
            </div>

            <div className="pb-4 min-w-0">
              <p className="text-xs text-slate-400">
                {format(ev.ts, 'HH:mm:ss')}
                <span className={clsx('ml-2 font-medium', cfg.color)}>{cfg.label}</span>
              </p>
              <p className="text-xs text-slate-300 mt-0.5">{ev.label}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
