import { clsx } from 'clsx'
import { AlertTriangle, AlertCircle, Info, XCircle } from 'lucide-react'
import { format } from 'date-fns'

const LEVEL_CONFIG = {
  Critical:    { icon: XCircle,       color: 'text-red-400',    bg: 'bg-red-500/10',    badge: 'border-red-500/40 text-red-400' },
  Error:       { icon: AlertCircle,   color: 'text-orange-400', bg: 'bg-orange-500/10', badge: 'border-orange-500/40 text-orange-400' },
  Warning:     { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10', badge: 'border-yellow-500/40 text-yellow-400' },
  Information: { icon: Info,          color: 'text-blue-400',   bg: 'bg-blue-500/10',   badge: 'border-blue-500/40 text-blue-400' },
}

function EventRow({ event }) {
  const cfg = LEVEL_CONFIG[event.level] ?? LEVEL_CONFIG.Information
  const Icon = cfg.icon

  return (
    <div className={clsx('flex gap-3 p-3 rounded-lg border border-transparent hover:border-slate-700 transition-colors', cfg.bg)}>
      <Icon size={14} className={clsx(cfg.color, 'mt-0.5 shrink-0')} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          <span className={clsx('text-xs font-mono px-1.5 py-0 rounded border', cfg.badge)}>
            {event.level}
          </span>
          <span className="text-xs text-slate-500 font-mono">{event.source}</span>
          <span className="text-xs text-slate-600 font-mono">ID: {event.event_id}</span>
          <span className="text-xs text-slate-600 font-mono">
            {event.host}
          </span>
          {event.timestamp && (
            <span className="text-xs text-slate-600 ml-auto">
              {format(new Date(event.timestamp), 'HH:mm:ss')}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-400 line-clamp-2">{event.message}</p>
      </div>
    </div>
  )
}

export default function WinEventLog({ events = [], loading }) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-12 rounded-lg bg-slate-800/60 animate-pulse" />
        ))}
      </div>
    )
  }

  const criticalFirst = [...events].sort((a, b) => {
    const rank = { Critical: 4, Error: 3, Warning: 2, Information: 1 }
    return (rank[b.level] ?? 0) - (rank[a.level] ?? 0)
  })

  if (criticalFirst.length === 0) {
    return (
      <div className="text-center py-6 text-slate-500 text-sm">
        No Windows Event Log entries collected yet.
      </div>
    )
  }

  return (
    <div className="space-y-1 max-h-72 overflow-y-auto pr-1">
      {criticalFirst.map((ev, i) => (
        <EventRow key={`${ev.host}-${ev.event_id}-${i}`} event={ev} />
      ))}
    </div>
  )
}
