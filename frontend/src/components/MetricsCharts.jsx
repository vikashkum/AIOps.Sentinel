import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { format } from 'date-fns'
import { useState } from 'react'

const SERVICES = ['api-gateway', 'auth-service', 'order-service', 'payment-service', 'notification-service']
const COLORS   = ['#6366f1', '#22c55e', '#eab308', '#ef4444', '#06b6d4']

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }} className="font-medium">
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(1) : p.value}
        </p>
      ))}
    </div>
  )
}

export default function MetricsCharts({ metricsData }) {
  const [activeService, setActiveService] = useState('all')

  if (!metricsData) return (
    <div className="text-slate-500 text-sm text-center py-12">Loading metrics...</div>
  )

  // Normalize: build a time-series array for the selected service(s)
  const buildSeries = (key) => {
    const allTimes = new Set()
    const byService = {}

    const servicesToShow = activeService === 'all' ? SERVICES : [activeService]

    for (const svc of servicesToShow) {
      const records = metricsData[svc] ?? []
      byService[svc] = {}
      records.forEach((r) => {
        const t = format(new Date(r.timestamp), 'HH:mm:ss')
        allTimes.add(t)
        byService[svc][t] = r[key]
      })
    }

    return [...allTimes].sort().slice(-30).map((t) => {
      const point = { time: t }
      for (const svc of servicesToShow) {
        point[svc] = byService[svc]?.[t] ?? null
      }
      return point
    })
  }

  const latencyData = buildSeries('latency_p99_ms')
  const errorData   = buildSeries('error_rate_pct')
  const volumeData  = buildSeries('request_volume')

  const servicesToShow = activeService === 'all' ? SERVICES : [activeService]

  return (
    <div className="space-y-4">
      {/* Service filter */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setActiveService('all')}
          className={`text-xs px-3 py-1 rounded-full border transition-colors ${
            activeService === 'all'
              ? 'bg-indigo-600 border-indigo-500 text-white'
              : 'border-slate-700 text-slate-400 hover:border-slate-500'
          }`}
        >
          All services
        </button>
        {SERVICES.map((svc, i) => (
          <button
            key={svc}
            onClick={() => setActiveService(svc)}
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${
              activeService === svc
                ? 'border-transparent text-white'
                : 'border-slate-700 text-slate-400 hover:border-slate-500'
            }`}
            style={activeService === svc ? { backgroundColor: COLORS[i], borderColor: COLORS[i] } : {}}
          >
            {svc}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Latency p99 */}
        <div className="bg-sentinel-card border border-sentinel-border rounded-xl p-4">
          <p className="text-xs font-medium text-slate-400 mb-3">Latency p99 (ms)</p>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={latencyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
              <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#64748b' }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 9, fill: '#64748b' }} />
              <Tooltip content={<CustomTooltip />} />
              {servicesToShow.map((svc, i) => (
                <Line key={svc} type="monotone" dataKey={svc} stroke={COLORS[i % COLORS.length]}
                  dot={false} strokeWidth={1.5} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Error rate */}
        <div className="bg-sentinel-card border border-sentinel-border rounded-xl p-4">
          <p className="text-xs font-medium text-slate-400 mb-3">Error Rate (%)</p>
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={errorData}>
              <defs>
                {servicesToShow.map((svc, i) => (
                  <linearGradient key={svc} id={`errGrad${i}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
              <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#64748b' }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 9, fill: '#64748b' }} />
              <Tooltip content={<CustomTooltip />} />
              {servicesToShow.map((svc, i) => (
                <Area key={svc} type="monotone" dataKey={svc}
                  stroke={COLORS[i % COLORS.length]} fill={`url(#errGrad${i})`}
                  strokeWidth={1.5} dot={false} connectNulls />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Request volume */}
        <div className="bg-sentinel-card border border-sentinel-border rounded-xl p-4">
          <p className="text-xs font-medium text-slate-400 mb-3">Request Volume (req/tick)</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={volumeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
              <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#64748b' }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 9, fill: '#64748b' }} />
              <Tooltip content={<CustomTooltip />} />
              {servicesToShow.map((svc, i) => (
                <Bar key={svc} dataKey={svc} fill={COLORS[i % COLORS.length]} opacity={0.8} radius={[2,2,0,0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
