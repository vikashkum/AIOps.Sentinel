import { clsx } from 'clsx'
import { AlertCircle, AlertTriangle, Info, ChevronRight, Clock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

const severityConfig = {
  critical: { icon: AlertCircle,   color: 'text-red-400',    bg: 'bg-red-500/10',    border: 'border-red-500/40' },
  warning:  { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/40' },
  info:     { icon: Info,          color: 'text-blue-400',   bg: 'bg-blue-500/10',   border: 'border-blue-500/40' },
}

const statusBadge = {
  active:       'bg-red-500/20 text-red-400',
  acknowledged: 'bg-yellow-500/20 text-yellow-400',
  resolved:     'bg-green-500/20 text-green-400',
}

export default function IncidentList({ incidents = [], onSelect }) {
  if (incidents.length === 0) {
    return (
      <div className="rounded-xl border border-sentinel-border bg-sentinel-card p-6 text-center">
        <div className="text-green-400 mb-2"><AlertCircle size={32} className="mx-auto opacity-60" /></div>
        <p className="text-slate-400 text-sm">No active incidents. All systems nominal.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {incidents.map((inc) => {
        const cfg = severityConfig[inc.severity] ?? severityConfig.info
        const Icon = cfg.icon
        const timeAgo = inc.first_detected
          ? formatDistanceToNow(new Date(inc.first_detected), { addSuffix: true })
          : '—'

        return (
          <button
            key={inc.incident_id}
            onClick={() => onSelect(inc)}
            className={clsx(
              'w-full text-left rounded-xl border p-4 transition-all duration-200',
              'hover:border-indigo-500/50 hover:bg-indigo-500/5',
              'bg-sentinel-card', cfg.border
            )}
          >
            <div className="flex items-start gap-3">
              <div className={clsx('p-1.5 rounded-lg mt-0.5', cfg.bg)}>
                <Icon size={14} className={cfg.color} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={clsx('text-xs font-mono px-1.5 py-0.5 rounded', statusBadge[inc.status] ?? statusBadge.active)}>
                    {inc.status}
                  </span>
                  <span className={clsx('text-xs font-semibold capitalize px-1.5 py-0.5 rounded', cfg.bg, cfg.color)}>
                    {inc.severity}
                  </span>
                  <span className="text-xs text-slate-500 font-mono">{inc.incident_id}</span>
                </div>
                <p className="text-sm font-medium text-slate-200 mt-1.5 truncate">{inc.title}</p>
                <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-500">
                  <span>{(inc.affected_services ?? []).join(', ')}</span>
                  <span className="flex items-center gap-1">
                    <Clock size={10} /> {timeAgo}
                  </span>
                  {inc.trigger_event && (
                    <span className="text-indigo-400">deployment triggered</span>
                  )}
                </div>
                {inc.ai_summary && (
                  <p className="text-xs text-slate-400 mt-2 line-clamp-2 italic">
                    AI: {inc.ai_summary}
                  </p>
                )}
              </div>
              <ChevronRight size={14} className="text-slate-600 mt-1 flex-shrink-0" />
            </div>
          </button>
        )
      })}
    </div>
  )
}
