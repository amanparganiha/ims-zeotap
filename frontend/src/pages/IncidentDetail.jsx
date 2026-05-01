import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { format } from 'date-fns'
import { ArrowLeft, ChevronRight } from 'lucide-react'
import { getIncident, getSignals, getRCA, updateStatus } from '../api/client'
import { SeverityBadge, StatusBadge } from '../components/SeverityBadge'
import RCAForm from './RCAForm'

const TRANSITIONS = {
  OPEN: 'INVESTIGATING',
  INVESTIGATING: 'RESOLVED',
  RESOLVED: 'CLOSED',
}

export default function IncidentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [incident, setIncident] = useState(null)
  const [signals, setSignals]   = useState([])
  const [rca, setRca]           = useState(null)
  const [tab, setTab]           = useState('signals')
  const [transitioning, setTransitioning] = useState(false)
  const [error, setError]       = useState(null)

  const load = async () => {
    try {
      const [inc, sigs] = await Promise.all([getIncident(id), getSignals(id)])
      setIncident(inc.data)
      setSignals(sigs.data.signals)
      try { setRca((await getRCA(id)).data) } catch { /* no RCA yet */ }
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => { load() }, [id])

  const handleTransition = async () => {
    const next = TRANSITIONS[incident.status]
    if (!next) return
    if (next === 'CLOSED' && !rca) {
      setTab('rca')
      alert('Submit an RCA before closing this incident.')
      return
    }
    setTransitioning(true)
    try {
      await updateStatus(id, next)
      await load()
    } catch (e) {
      alert(e.message)
    } finally {
      setTransitioning(false)
    }
  }

  if (error) return <div className="p-8 text-red-400">{error}</div>
  if (!incident) return <div className="p-8 text-gray-500">Loading...</div>

  const nextStatus = TRANSITIONS[incident.status]

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-1 text-gray-500 hover:text-gray-300 text-sm mb-4"
      >
        <ArrowLeft size={14} /> Back to Dashboard
      </button>

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <SeverityBadge severity={incident.severity} />
              <StatusBadge status={incident.status} />
            </div>
            <h1 className="text-lg font-bold text-white">{incident.title}</h1>
            <p className="text-sm text-gray-400 mt-1">
              Component: <span className="text-gray-200">{incident.component_id}</span>
              {' · '}Signals: <span className="text-gray-200">{incident.signal_count}</span>
              {' · '}Created: <span className="text-gray-200">
                {format(new Date(incident.created_at), 'MMM d, HH:mm:ss')}
              </span>
              {incident.mttr_seconds && (
                <> · MTTR: <span className="text-green-400">
                  {Math.round(incident.mttr_seconds / 60)}m
                </span></>
              )}
            </p>
          </div>

          {nextStatus && (
            <button
              onClick={handleTransition}
              disabled={transitioning}
              className="flex items-center gap-1 px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-sm font-semibold disabled:opacity-50 whitespace-nowrap"
            >
              Move to {nextStatus} <ChevronRight size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4">
        {['signals', 'rca'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm rounded-t capitalize ${
              tab === t
                ? 'bg-gray-900 text-white border-t border-x border-gray-700'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {t === 'rca' ? (rca ? '✓ RCA' : 'RCA') : `Signals (${signals.length})`}
          </button>
        ))}
      </div>

      {tab === 'signals' ? (
        <div className="bg-gray-900 border border-gray-700 rounded-b-xl rounded-tr-xl overflow-hidden">
          {signals.length === 0 ? (
            <div className="p-8 text-center text-gray-600">No signals found</div>
          ) : (
            <div className="divide-y divide-gray-800 max-h-[60vh] overflow-y-auto">
              {signals.map((s, i) => (
                <div key={i} className="p-3 text-xs font-mono hover:bg-gray-800">
                  <div className="flex items-center gap-3 text-gray-400 mb-1">
                    <span className="text-red-400">{s.error_code}</span>
                    <span>{s.component_type}</span>
                    {s.latency_ms && <span>⏱ {s.latency_ms}ms</span>}
                    <span className="ml-auto text-gray-600">
                      {s.received_at ? new Date(s.received_at * 1000).toLocaleTimeString() : ''}
                    </span>
                  </div>
                  <div className="text-gray-300">{s.message}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-700 rounded-b-xl rounded-tr-xl p-6">
          {rca ? (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <Field label="Incident Start" value={format(new Date(rca.incident_start), 'PPpp')} />
                <Field label="Incident End"   value={format(new Date(rca.incident_end), 'PPpp')} />
              </div>
              <Field label="Root Cause Category" value={rca.root_cause_category} />
              <Field label="Fix Applied"         value={rca.fix_applied} multiline />
              <Field label="Prevention Steps"    value={rca.prevention_steps} multiline />
            </div>
          ) : (
            <RCAForm incidentId={id} onSubmit={() => { load(); setTab('rca') }} />
          )}
        </div>
      )}
    </div>
  )
}

function Field({ label, value, multiline }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-gray-200 ${multiline ? 'whitespace-pre-wrap' : ''}`}>{value}</div>
    </div>
  )
}
