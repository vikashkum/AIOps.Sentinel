import { clsx } from 'clsx'
import { Brain, Target, Zap, ChevronRight, Copy } from 'lucide-react'

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100)
  const color = pct >= 75 ? 'bg-red-500' : pct >= 50 ? 'bg-orange-500' : pct >= 30 ? 'bg-yellow-500' : 'bg-slate-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all duration-700', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-400 w-8 text-right">{pct}%</span>
    </div>
  )
}

function copyText(text) {
  navigator.clipboard.writeText(text).catch(() => {})
}

export default function AIAnalysisPanel({ incident }) {
  if (!incident) return (
    <div className="text-center text-slate-500 text-sm py-8">
      Select an incident to view AI analysis.
    </div>
  )

  const hasAI = !!incident.ai_summary

  return (
    <div className="space-y-5">
      {/* Summary */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Brain size={14} className="text-purple-400" />
          <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">AI Summary</span>
          {!hasAI && <span className="text-xs text-slate-500">(generating...)</span>}
        </div>
        <div className="bg-purple-500/5 border border-purple-500/20 rounded-xl p-4">
          {hasAI ? (
            <p className="text-sm text-slate-300 leading-relaxed">{incident.ai_summary}</p>
          ) : (
            <div className="flex gap-2 items-center text-slate-500 text-sm">
              <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
              AI analysis in progress...
            </div>
          )}
        </div>
      </div>

      {/* Root Cause Suggestions */}
      {incident.root_cause_suggestions?.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Target size={14} className="text-orange-400" />
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">Root Cause Suggestions</span>
          </div>
          <div className="space-y-2">
            {incident.root_cause_suggestions.map((rca, i) => (
              <div key={i} className="bg-sentinel-card border border-sentinel-border rounded-xl p-3">
                <div className="flex items-start gap-2 mb-2">
                  <span className="text-xs font-mono text-slate-600 mt-0.5">#{i + 1}</span>
                  <p className="text-sm text-slate-200 flex-1">{rca.cause}</p>
                </div>
                <ConfidenceBar value={rca.confidence} />
                {rca.signals?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {rca.signals.map((s, j) => (
                      <span key={j} className="text-xs bg-slate-800 text-slate-400 rounded px-2 py-0.5">{s}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommended Actions */}
      {incident.recommended_actions?.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Zap size={14} className="text-yellow-400" />
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">Recommended Actions</span>
          </div>
          <div className="space-y-2">
            {incident.recommended_actions.map((act, i) => (
              <div key={i} className="bg-sentinel-card border border-sentinel-border rounded-xl p-3">
                <div className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-yellow-500/20 text-yellow-400 text-xs font-bold flex items-center justify-center mt-0.5">
                    {act.priority}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-200">{act.action}</p>
                    <p className="text-xs text-slate-500 mt-1">{act.rationale}</p>
                    {act.command_hint && (
                      <div className="mt-2 flex items-center gap-1 bg-slate-900 rounded-lg px-3 py-1.5">
                        <code className="text-xs text-green-400 flex-1 font-mono truncate">{act.command_hint}</code>
                        <button
                          onClick={() => copyText(act.command_hint)}
                          className="text-slate-600 hover:text-slate-400 flex-shrink-0 ml-1"
                        >
                          <Copy size={11} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
