import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { Play, Square, RefreshCw, Zap } from 'lucide-react'
import { clsx } from 'clsx'

const SCENARIOS = [
  { id: 'normal',            label: 'Normal Traffic',        color: 'text-green-400' },
  { id: 'traffic_spike',     label: 'Traffic Spike',         color: 'text-yellow-400' },
  { id: 'bad_deployment',    label: 'Bad Deployment',        color: 'text-orange-400' },
  { id: 'cascading_failure', label: 'Cascading Failure',     color: 'text-red-400' },
  { id: 'memory_pressure',   label: 'Memory Pressure',       color: 'text-purple-400' },
  { id: 'error_burst',       label: 'Error Burst',           color: 'text-red-500' },
  { id: 'latency_regression',label: 'Latency Regression',    color: 'text-orange-300' },
]

export default function ScenarioControls() {
  const qc = useQueryClient()
  const [activeScenario, setActiveScenario] = useState('normal')

  const { data: status } = useQuery({
    queryKey: ['simulationStatus'],
    queryFn: api.getSimulationStatus,
    refetchInterval: 3000,
  })

  const startMut = useMutation({ mutationFn: api.startSimulation, onSuccess: () => qc.invalidateQueries() })
  const stopMut  = useMutation({ mutationFn: api.stopSimulation,  onSuccess: () => qc.invalidateQueries() })
  const resetMut = useMutation({ mutationFn: api.resetSimulation, onSuccess: () => qc.invalidateQueries() })
  const scenarioMut = useMutation({
    mutationFn: (s) => api.setScenario(s),
    onSuccess: (_, s) => { setActiveScenario(s); qc.invalidateQueries() },
  })

  const isRunning = status?.running ?? false

  return (
    <div className="bg-sentinel-card border border-sentinel-border rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">Simulation Controls</span>
        <div className={clsx('flex items-center gap-1.5 text-xs', isRunning ? 'text-green-400' : 'text-slate-500')}>
          <div className={clsx('w-1.5 h-1.5 rounded-full', isRunning ? 'bg-green-400 animate-pulse' : 'bg-slate-600')} />
          {isRunning ? 'Running' : 'Stopped'}
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => startMut.mutate()}
          disabled={isRunning}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-green-600 hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors"
        >
          <Play size={12} /> Start
        </button>
        <button
          onClick={() => stopMut.mutate()}
          disabled={!isRunning}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 transition-colors"
        >
          <Square size={12} /> Stop
        </button>
        <button
          onClick={() => resetMut.mutate()}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors"
        >
          <RefreshCw size={12} /> Reset
        </button>
      </div>

      <div>
        <p className="text-xs text-slate-500 mb-2 flex items-center gap-1">
          <Zap size={10} /> Inject Scenario
        </p>
        <div className="grid grid-cols-2 gap-1.5">
          {SCENARIOS.map((s) => (
            <button
              key={s.id}
              onClick={() => scenarioMut.mutate(s.id)}
              className={clsx(
                'text-xs px-2.5 py-1.5 rounded-lg border text-left transition-all',
                activeScenario === s.id
                  ? 'bg-indigo-600/30 border-indigo-500/60 text-indigo-300'
                  : 'border-sentinel-border text-slate-400 hover:border-slate-600 hover:text-slate-300'
              )}
            >
              <span className={s.color}>● </span>{s.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
