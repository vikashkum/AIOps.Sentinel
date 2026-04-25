import { X, Clock, Server } from 'lucide-react'
import { clsx } from 'clsx'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import AIAnalysisPanel from './AIAnalysisPanel'
import IncidentTimeline from './IncidentTimeline'
import { format } from 'date-fns'

const statusBadge = {
  active:       'bg-red-500/20 text-red-400 border-red-500/40',
  acknowledged: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40',
  resolved:     'bg-green-500/20 text-green-400 border-green-500/40',
}

export default function IncidentDrawer({ incident, onClose }) {
  const qc = useQueryClient()

  const updateStatus = useMutation({
    mutationFn: ({ id, status }) => api.updateIncidentStatus(id, status),
    onSuccess: () => qc.invalidateQueries(['incidents']),
  })

  if (!incident) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />

      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 w-full max-w-2xl bg-slate-950 border-l border-sentinel-border z-50 overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="sticky top-0 bg-slate-950 border-b border-sentinel-border px-6 py-4 flex items-start justify-between z-10">
          <div className="min-w-0 flex-1 pr-4">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className={clsx('text-xs font-mono px-2 py-0.5 rounded border', statusBadge[incident.status] ?? statusBadge.active)}>
                {incident.status}
              </span>
              <span className="text-xs font-mono text-slate-500">{incident.incident_id}</span>
            </div>
            <h2 className="text-base font-semibold text-slate-100 truncate">{incident.title}</h2>
            <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <Server size={10} /> {(incident.affected_services ?? []).join(', ')}
              </span>
              {incident.first_detected && (
                <span className="flex items-center gap-1">
                  <Clock size={10} /> {format(new Date(incident.first_detected), 'HH:mm:ss')}
                </span>
              )}
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 px-6 py-5 space-y-6">
          {/* Status actions */}
          <div className="flex gap-2">
            {incident.status === 'active' && (
              <button
                onClick={() => updateStatus.mutate({ id: incident.incident_id, status: 'acknowledged' })}
                className="text-xs px-3 py-1.5 rounded-lg bg-yellow-600/30 border border-yellow-500/40 text-yellow-400 hover:bg-yellow-600/50 transition-colors"
              >
                Acknowledge
              </button>
            )}
            {incident.status !== 'resolved' && (
              <button
                onClick={() => updateStatus.mutate({ id: incident.incident_id, status: 'resolved' })}
                className="text-xs px-3 py-1.5 rounded-lg bg-green-600/30 border border-green-500/40 text-green-400 hover:bg-green-600/50 transition-colors"
              >
                Mark Resolved
              </button>
            )}
          </div>

          {/* Health scores */}
          {incident.health_scores && Object.keys(incident.health_scores).length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Service Health at Detection</p>
              <div className="flex gap-3 flex-wrap">
                {Object.entries(incident.health_scores).map(([svc, score]) => {
                  const color = score >= 85 ? 'text-green-400' : score >= 60 ? 'text-yellow-400' : score >= 35 ? 'text-orange-400' : 'text-red-400'
                  return (
                    <div key={svc} className="bg-sentinel-card border border-sentinel-border rounded-lg px-3 py-2">
                      <p className="text-xs text-slate-500 font-mono">{svc}</p>
                      <p className={clsx('text-base font-bold', color)}>{Math.round(score)}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Timeline */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Incident Timeline</p>
            <IncidentTimeline incident={incident} />
          </div>

          {/* AI analysis */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">AI Analysis</p>
            <AIAnalysisPanel incident={incident} />
          </div>
        </div>
      </div>
    </>
  )
}
