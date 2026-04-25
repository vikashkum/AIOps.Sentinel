import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import HealthCards from '../components/HealthCards'
import IncidentList from '../components/IncidentList'
import MetricsCharts from '../components/MetricsCharts'
import ScenarioControls from '../components/ScenarioControls'
import IncidentDrawer from '../components/IncidentDrawer'
import InfrastructurePanel from '../components/InfrastructurePanel'
import WinEventLog from '../components/WinEventLog'
import { Activity, Shield, RefreshCw, Server, Layers } from 'lucide-react'
import { format } from 'date-fns'
import { clsx } from 'clsx'

function SystemHealthBadge({ score, status }) {
  const color = score >= 85 ? 'text-green-400 border-green-500/40 bg-green-500/10'
    : score >= 60 ? 'text-yellow-400 border-yellow-500/40 bg-yellow-500/10'
    : score >= 35 ? 'text-orange-400 border-orange-500/40 bg-orange-500/10'
    : 'text-red-400 border-red-500/40 bg-red-500/10'

  return (
    <div className={clsx('flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-semibold', color)}>
      <Shield size={14} />
      System {Math.round(score ?? 100)}/100
      <span className="capitalize font-normal text-xs opacity-80">({status})</span>
    </div>
  )
}

const TABS = [
  { id: 'services',        label: 'Microservices',   icon: Layers },
  { id: 'infrastructure',  label: 'Infrastructure',  icon: Server },
]

export default function Dashboard() {
  const [selectedIncident, setSelectedIncident] = useState(null)
  const [activeTab, setActiveTab] = useState('services')

  const { data: systemData, dataUpdatedAt } = useQuery({
    queryKey: ['systemSummary'],
    queryFn: api.getSystemSummary,
    refetchInterval: 8000,
  })

  const { data: incidents = [] } = useQuery({
    queryKey: ['incidents'],
    queryFn: api.getIncidents,
    refetchInterval: 6000,
  })

  useEffect(() => {
    if (selectedIncident && incidents.length > 0) {
      const updated = incidents.find((i) => i.incident_id === selectedIncident.incident_id)
      if (updated) setSelectedIncident(updated)
    }
  }, [incidents])

  const { data: metricsData } = useQuery({
    queryKey: ['metrics'],
    queryFn: () => api.getMetrics(60),
    refetchInterval: 8000,
  })

  const { data: infraSummary } = useQuery({
    queryKey: ['infraSummary'],
    queryFn: api.getInfraSummary,
    refetchInterval: 8000,
  })

  const { data: winEventsData } = useQuery({
    queryKey: ['winEvents'],
    queryFn: () => api.getWinEvents(null, 50),
    refetchInterval: 10000,
    enabled: activeTab === 'infrastructure',
  })

  const lastUpdated = dataUpdatedAt ? format(new Date(dataUpdatedAt), 'HH:mm:ss') : '—'
  const activeIncidents = incidents.filter(i => i.status !== 'resolved')
  const resolvedIncidents = incidents.filter(i => i.status === 'resolved')

  return (
    <div className="min-h-screen bg-sentinel-bg text-slate-200">
      {/* Top nav */}
      <header className="sticky top-0 z-30 bg-sentinel-bg/80 backdrop-blur border-b border-sentinel-border">
        <div className="max-w-screen-2xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-lg bg-indigo-600/20 border border-indigo-500/30">
              <Activity size={18} className="text-indigo-400" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-100 leading-none">AIOps Sentinel</h1>
              <p className="text-xs text-slate-500 mt-0.5">AI-Driven Observability</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {systemData && (
              <>
                <SystemHealthBadge
                  score={systemData.system_health_score}
                  status={systemData.system_status}
                />
                {systemData.infra_health_score != null && (
                  <div className={clsx(
                    'flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold',
                    systemData.infra_health_score >= 85
                      ? 'text-green-400 border-green-500/30 bg-green-500/10'
                      : systemData.infra_health_score >= 60
                      ? 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10'
                      : 'text-red-400 border-red-500/30 bg-red-500/10'
                  )}>
                    <Server size={11} />
                    Infra {Math.round(systemData.infra_health_score)}/100
                  </div>
                )}
              </>
            )}
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <RefreshCw size={10} />
              {lastUpdated}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="max-w-screen-2xl mx-auto px-6 flex gap-1 border-t border-sentinel-border/50">
          {TABS.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors',
                  activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-400'
                    : 'border-transparent text-slate-500 hover:text-slate-300'
                )}
              >
                <Icon size={12} />
                {tab.label}
              </button>
            )
          })}
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto px-6 py-6 space-y-6">

        {/* ── MICROSERVICES TAB ─────────────────────────────────────── */}
        {activeTab === 'services' && (
          <>
            <section>
              <HealthCards systemData={systemData} />
            </section>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <div className="xl:col-span-2 space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-slate-300">
                    Active Incidents
                    {activeIncidents.length > 0 && (
                      <span className="ml-2 text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">
                        {activeIncidents.length}
                      </span>
                    )}
                  </h2>
                </div>
                <IncidentList incidents={activeIncidents} onSelect={setSelectedIncident} />
                {resolvedIncidents.length > 0 && (
                  <details className="group">
                    <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400 select-none">
                      {resolvedIncidents.length} resolved incident(s)
                    </summary>
                    <div className="mt-2">
                      <IncidentList incidents={resolvedIncidents} onSelect={setSelectedIncident} />
                    </div>
                  </details>
                )}
              </div>
              <div>
                <ScenarioControls />
              </div>
            </div>

            <section>
              <h2 className="text-sm font-semibold text-slate-300 mb-3">Metrics</h2>
              <MetricsCharts metricsData={metricsData} />
            </section>
          </>
        )}

        {/* ── INFRASTRUCTURE TAB ───────────────────────────────────── */}
        {activeTab === 'infrastructure' && (
          <>
            {/* Infra host cards */}
            <section>
              <InfrastructurePanel summary={infraSummary} />
            </section>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              {/* Windows Event Log */}
              <div className="xl:col-span-2">
                <div className="rounded-xl border border-sentinel-border bg-sentinel-card p-5">
                  <h2 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                    <Server size={14} className="text-slate-400" />
                    Windows Event Log
                    <span className="ml-auto text-xs text-slate-500 font-normal">
                      Critical / Error / Warning only
                    </span>
                  </h2>
                  <WinEventLog
                    events={winEventsData?.events ?? []}
                    loading={!winEventsData}
                  />
                </div>
              </div>

              {/* Infra scenario controls */}
              <div className="space-y-4">
                <div className="rounded-xl border border-sentinel-border bg-sentinel-card p-5">
                  <h2 className="text-sm font-semibold text-slate-300 mb-3">Infra Scenarios</h2>
                  <div className="space-y-2">
                    {[
                      { id: 'normal',            label: 'Normal',             desc: 'All hosts healthy' },
                      { id: 'iis_app_pool_crash', label: 'App Pool Crash',     desc: 'iis-web-01 pool down' },
                      { id: 'iis_memory_leak',   label: 'Memory Leak',        desc: 'iis-api-01 worker OOM' },
                      { id: 'iis_high_error_rate', label: 'High Error Rate',  desc: '30%+ 5xx on web servers' },
                      { id: 'disk_pressure',     label: 'Disk Pressure',      desc: 'win-db-01 C: at 93%' },
                      { id: 'iis_worker_recycle', label: 'Worker Recycle',    desc: 'iis-api-01 recycling' },
                      { id: 'ssl_cert_expiry',   label: 'SSL Cert Expiry',    desc: 'Certificate expiring' },
                    ].map((s) => (
                      <button
                        key={s.id}
                        onClick={() => api.setInfraScenario(s.id)}
                        className={clsx(
                          'w-full text-left px-3 py-2 rounded-lg border text-xs transition-colors',
                          s.id === 'normal'
                            ? 'border-green-500/30 bg-green-500/10 text-green-400 hover:bg-green-500/20'
                            : 'border-sentinel-border bg-slate-800/50 text-slate-300 hover:border-orange-500/40 hover:text-orange-400'
                        )}
                      >
                        <p className="font-medium">{s.label}</p>
                        <p className="text-slate-500 mt-0.5">{s.desc}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Agent setup hint */}
                <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-4">
                  <p className="text-xs font-semibold text-indigo-400 mb-2">Real VM Agent</p>
                  <p className="text-xs text-slate-400 mb-3">
                    Run the PowerShell agent on any Windows server to send live data here.
                  </p>
                  <code className="block text-xs bg-slate-900 rounded p-2 text-slate-300 font-mono overflow-x-auto">
                    {'.\aiops-agent.ps1 -BackendUrl "http://your-server:8000"'}
                  </code>
                  <p className="text-xs text-slate-500 mt-2">No admin rights required.</p>
                </div>
              </div>
            </div>
          </>
        )}
      </main>

      {selectedIncident && (
        <IncidentDrawer
          incident={selectedIncident}
          onClose={() => setSelectedIncident(null)}
        />
      )}
    </div>
  )
}
