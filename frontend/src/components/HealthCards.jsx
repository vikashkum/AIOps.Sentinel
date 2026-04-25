import { clsx } from 'clsx'
import { Activity, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'

const statusConfig = {
  healthy:  { color: 'text-green-400',  border: 'border-green-500/30',  bg: 'bg-green-500/10',  icon: CheckCircle },
  degraded: { color: 'text-yellow-400', border: 'border-yellow-500/30', bg: 'bg-yellow-500/10', icon: AlertTriangle },
  critical: { color: 'text-orange-400', border: 'border-orange-500/30', bg: 'bg-orange-500/10', icon: AlertTriangle },
  down:     { color: 'text-red-400',    border: 'border-red-500/30',    bg: 'bg-red-500/10',    icon: XCircle },
}

function ScoreRing({ score }) {
  const radius = 20
  const circ = 2 * Math.PI * radius
  const offset = circ - (score / 100) * circ
  const color = score >= 85 ? '#22c55e' : score >= 60 ? '#eab308' : score >= 35 ? '#f97316' : '#ef4444'

  return (
    <svg width="52" height="52" viewBox="0 0 52 52">
      <circle cx="26" cy="26" r={radius} fill="none" stroke="#2a2d3a" strokeWidth="4" />
      <circle
        cx="26" cy="26" r={radius}
        fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 26 26)"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
      <text x="26" y="31" textAnchor="middle" fontSize="11" fontWeight="bold" fill={color}>
        {Math.round(score)}
      </text>
    </svg>
  )
}

export default function HealthCards({ systemData }) {
  if (!systemData?.services) return null
  const { services, system_health_score, system_status, active_incident_count, critical_incident_count } = systemData

  return (
    <div className="space-y-3">
      {/* System header */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-indigo-400" />
          <span className="text-sm font-medium text-slate-300">System Health</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span>{active_incident_count ?? 0} active incidents</span>
          {critical_incident_count > 0 && (
            <span className="text-red-400 font-medium">{critical_incident_count} critical</span>
          )}
        </div>
      </div>

      {/* Service cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {Object.entries(services).map(([name, data]) => {
          const cfg = statusConfig[data.status] ?? statusConfig.healthy
          const Icon = cfg.icon
          return (
            <div
              key={name}
              className={clsx(
                'rounded-xl border p-3 flex flex-col gap-2',
                'bg-sentinel-card', cfg.border
              )}
            >
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <p className="text-xs font-mono text-slate-400 truncate">{name}</p>
                  <p className={clsx('text-xs font-semibold mt-0.5 capitalize', cfg.color)}>
                    {data.status}
                  </p>
                </div>
                <ScoreRing score={data.health_score ?? 100} />
              </div>
              <div className="flex items-center gap-1 text-xs text-slate-500">
                <Icon size={11} className={cfg.color} />
                <span>{data.anomaly_count_30m ?? 0} anomalies/30m</span>
              </div>
              {data.latest_metrics && (
                <div className="text-xs space-y-0.5 text-slate-500 border-t border-sentinel-border pt-2">
                  <div className="flex justify-between">
                    <span>p99</span>
                    <span className="text-slate-300">{data.latest_metrics.latency_p99_ms?.toFixed(0) ?? '—'}ms</span>
                  </div>
                  <div className="flex justify-between">
                    <span>err%</span>
                    <span className={data.latest_metrics.error_rate_pct > 5 ? 'text-red-400' : 'text-slate-300'}>
                      {data.latest_metrics.error_rate_pct?.toFixed(2) ?? '—'}%
                    </span>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
