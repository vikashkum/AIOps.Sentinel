const BASE = '/api'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post(path, body = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

async function patch(path, body = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PATCH ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  getSystemSummary: () => get('/summary/system'),
  getServices: () => get('/services'),
  getServiceHealth: (svc) => get(`/services/${svc}/health`),
  getIncidents: () => get('/incidents'),
  getIncident: (id) => get(`/incidents/${id}`),
  updateIncidentStatus: (id, status) => patch(`/incidents/${id}`, { status }),
  getMetrics: (limit = 60) => get(`/metrics?limit=${limit}`),
  getServiceMetrics: (svc, limit = 60) => get(`/metrics/${svc}?limit=${limit}`),
  getLogs: (service, level, limit = 100) => {
    const params = new URLSearchParams({ limit })
    if (service) params.set('service', service)
    if (level) params.set('level', level)
    return get(`/logs?${params}`)
  },
  getAnomalies: (limit = 50) => get(`/anomalies?limit=${limit}`),
  getEvents: () => get('/events'),
  startSimulation: () => post('/simulate/start'),
  stopSimulation: () => post('/simulate/stop'),
  setScenario: (scenario) => post('/simulate/scenario', { scenario }),
  setInfraScenario: (scenario) => post('/simulate/infra/scenario', { scenario }),
  resetSimulation: () => post('/simulate/reset'),
  getSimulationStatus: () => get('/simulate/status'),

  // Infrastructure
  getInfraSummary: () => get('/infrastructure/summary'),
  getHostHealth: (host) => get(`/infrastructure/${host}/health`),
  getHostMetrics: (host, limit = 60) => get(`/infrastructure/${host}/metrics?limit=${limit}`),
  getWinEvents: (host, limit = 100) => {
    const params = new URLSearchParams({ limit })
    if (host) params.set('host', host)
    return get(`/infrastructure/events/windows?${params}`)
  },
  getIISLogs: (host, limit = 100) => get(`/infrastructure/${host}/iis-logs?limit=${limit}`),
}
