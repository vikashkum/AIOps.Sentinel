import { clsx } from 'clsx'
import { Server, Cpu, HardDrive, Globe, AlertTriangle, CheckCircle, XCircle, RefreshCw } from 'lucide-react'

const STATUS_CONFIG = {
  healthy:  { color: 'text-green-400',  bg: 'bg-green-500/10',  border: 'border-green-500/30',  icon: CheckCircle },
  degraded: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', icon: AlertTriangle },
  critical: { color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', icon: AlertTriangle },
  down:     { color: 'text-red-400',    bg: 'bg-red-500/10',    border: 'border-red-500/30',    icon: XCircle },
  no_data:  { color: 'text-slate-500',  bg: 'bg-slate-800',     border: 'border-slate-700',     icon: Server },
}

function MetricBar({ label, value, warn = 75, critical = 90 }) {
  const color = value >= critical ? 'bg-red-500' : value >= warn ? 'bg-yellow-500' : 'bg-green-500'
  return (
    <div>
      <div className="flex justify-between text-xs mb-0.5">
        <span className="text-slate-500">{label}</span>
        <span className="text-slate-300 font-mono">{value?.toFixed(1)}%</span>
      </div>
      <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all', color)} style={{ width: `${Math.min(value ?? 0, 100)}%` }} />
      </div>
    </div>
  )
}

function AppPoolBadge({ status }) {
  const config = {
    running:   { label: 'Running',   cls: 'text-green-400 bg-green-500/15 border-green-500/30' },
    stopped:   { label: 'Stopped',   cls: 'text-red-400 bg-red-500/15 border-red-500/30' },
    recycling: { label: 'Recycling', cls: 'text-yellow-400 bg-yellow-500/15 border-yellow-500/30' },
    unknown:   { label: 'Unknown',   cls: 'text-slate-400 bg-slate-700 border-slate-600' },
    'n/a':     { label: 'N/A',       cls: 'text-slate-500 bg-slate-800 border-slate-700' },
  }[status ?? 'unknown'] ?? { label: status, cls: 'text-slate-400 bg-slate-700 border-slate-600' }

  return (
    <span className={clsx('text-xs px-1.5 py-0.5 rounded border font-mono', config.cls)}>
      {config.label}
    </span>
  )
}

function HostCard({ host, snap }) {
  if (!snap) return null

  const score = snap._score ?? 100
  const status = score >= 85 ? 'healthy' : score >= 60 ? 'degraded' : score >= 35 ? 'critical' : 'down'
  const cfg = STATUS_CONFIG[status]
  const Icon = cfg.icon
  const isIIS = snap.host_type === 'iis'

  return (
    <div className={clsx('rounded-xl border p-4 space-y-3 transition-all hover:border-slate-600', cfg.bg, cfg.border)}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <Server size={12} className={cfg.color} />
            <span className="text-xs font-mono text-slate-300 truncate">{host}</span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={clsx('text-xl font-bold', cfg.color)}>{Math.round(score)}</span>
            <span className="text-xs text-slate-500">/100</span>
            {isIIS && <AppPoolBadge status={snap.app_pool_status} />}
          </div>
        </div>
        <Icon size={16} className={clsx(cfg.color, 'shrink-0 mt-0.5')} />
      </div>

      {/* Bars */}
      <div className="space-y-1.5">
        <MetricBar label="CPU" value={snap.cpu_pct} />
        <MetricBar label="Memory" value={snap.memory_pct} warn={80} critical={92} />
        <MetricBar label="Disk" value={snap.disk_pct} warn={80} critical={92} />
      </div>

      {/* IIS extras */}
      {isIIS && (
        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-800">
          <div>
            <p className="text-xs text-slate-500">Req/s</p>
            <p className="text-sm font-mono text-slate-200">{snap.requests_per_sec?.toFixed(0) ?? '—'}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">5xx rate</p>
            <p className={clsx('text-sm font-mono', snap.error_rate_5xx_pct > 5 ? 'text-red-400' : 'text-slate-200')}>
              {snap.error_rate_5xx_pct?.toFixed(2) ?? '—'}%
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Connections</p>
            <p className="text-sm font-mono text-slate-200">{snap.active_connections ?? '—'}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">p99 latency</p>
            <p className={clsx('text-sm font-mono', snap.latency_p99_ms > 1000 ? 'text-orange-400' : 'text-slate-200')}>
              {snap.latency_p99_ms ? `${snap.latency_p99_ms}ms` : '—'}
            </p>
          </div>
        </div>
      )}

      {/* SQL extras for db host */}
      {host.includes('db') && snap.sql_connections != null && (
        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-800">
          <div>
            <p className="text-xs text-slate-500">SQL Conns</p>
            <p className="text-sm font-mono text-slate-200">{snap.sql_connections}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Blocked</p>
            <p className={clsx('text-sm font-mono', snap.sql_blocked_queries > 5 ? 'text-red-400' : 'text-slate-200')}>
              {snap.sql_blocked_queries ?? 0}
            </p>
          </div>
        </div>
      )}

      {snap.source === 'real_agent' && (
        <p className="text-xs text-indigo-400 font-medium">Live agent data</p>
      )}
    </div>
  )
}

export default function InfrastructurePanel({ summary }) {
  if (!summary) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 text-center">
        <RefreshCw size={20} className="text-slate-600 mx-auto mb-2 animate-spin" />
        <p className="text-sm text-slate-500">Waiting for infrastructure data...</p>
      </div>
    )
  }

  const hosts = summary.hosts ?? []

  return (
    <div className="space-y-4">
      {/* Infra system health bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <HardDrive size={14} className="text-slate-400" />
          <span className="text-sm text-slate-400 font-medium">Infrastructure Health</span>
        </div>
        <div className="flex items-center gap-2">
          {summary.active_infra_scenario && summary.active_infra_scenario !== 'normal' && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-orange-500/20 border border-orange-500/40 text-orange-400 font-mono">
              {summary.active_infra_scenario}
            </span>
          )}
          <span className={clsx(
            'text-sm font-bold',
            summary.system_infra_health >= 85 ? 'text-green-400' :
            summary.system_infra_health >= 60 ? 'text-yellow-400' :
            summary.system_infra_health >= 35 ? 'text-orange-400' : 'text-red-400'
          )}>
            {summary.system_infra_health}/100
          </span>
        </div>
      </div>

      {hosts.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 text-center">
          <Globe size={20} className="text-slate-600 mx-auto mb-2" />
          <p className="text-sm text-slate-500">No host data yet. Start the simulation or run the PowerShell agent.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          {hosts.map((h) => (
            <HostCard key={h.host} host={h.host} snap={h} />
          ))}
        </div>
      )}
    </div>
  )
}
