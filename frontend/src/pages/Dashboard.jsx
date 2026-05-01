import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { RefreshCw, AlertTriangle, CheckCircle, Search } from 'lucide-react'
import { useIncidents } from '../hooks/useIncidents'
import { SeverityBadge, StatusBadge } from '../components/SeverityBadge'
import { useState } from 'react'

const SEVERITY_ORDER = { P0: 0, P1: 1, P2: 2, P3: 3 }

export default function Dashboard() {
  const { incidents, loading, error, refetch } = useIncidents(5000)
  const navigate = useNavigate()
  const [filter, setFilter] = useState('ALL')
  const [search, setSearch] = useState('')

  const filtered = incidents
    .filter(i => filter === 'ALL' || i.status === filter)
    .filter(i => !search || i.title.toLowerCase().includes(search.toLowerCase()) ||
                 i.component_id.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9))

  const counts = incidents.reduce((acc, i) => {
    acc[i.status] = (acc[i.status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'OPEN', color: 'border-red-700 text-red-400' },
          { label: 'INVESTIGATING', color: 'border-blue-700 text-blue-400' },
          { label: 'RESOLVED', color: 'border-green-700 text-green-400' },
          { label: 'CLOSED', color: 'border-gray-600 text-gray-400' },
        ].map(({ label, color }) => (
          <div key={label} className={`bg-gray-900 rounded-lg p-4 border ${color}`}>
            <div className={`text-2xl font-bold ${color.split(' ')[1]}`}>
              {counts[label] || 0}
            </div>
            <div className="text-xs text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
          <input
            className="w-full bg-gray-900 border border-gray-700 rounded pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            placeholder="Search incidents..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1">
          {['ALL', 'OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-xs px-3 py-1.5 rounded transition-colors ${
                filter === f
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        <button
          onClick={refetch}
          className="p-2 rounded bg-gray-800 hover:bg-gray-700 text-gray-400"
          title="Refresh"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Incidents table */}
      {loading ? (
        <div className="text-center text-gray-500 py-20">Loading incidents...</div>
      ) : error ? (
        <div className="text-center text-red-400 py-20">
          <AlertTriangle className="mx-auto mb-2" />
          {error}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center text-gray-600 py-20">
          <CheckCircle className="mx-auto mb-2 text-green-700" size={32} />
          No incidents match the current filter
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(inc => (
            <div
              key={inc.id}
              onClick={() => navigate(`/incidents/${inc.id}`)}
              className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-600 hover:bg-gray-800 cursor-pointer transition-all group"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <SeverityBadge severity={inc.severity} />
                  <span className="font-semibold text-sm truncate group-hover:text-white">
                    {inc.title}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <StatusBadge status={inc.status} />
                </div>
              </div>
              <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                <span>🔧 {inc.component_id}</span>
                <span>📡 {inc.signal_count} signals</span>
                {inc.mttr_seconds && (
                  <span>⏱ MTTR {Math.round(inc.mttr_seconds / 60)}m</span>
                )}
                <span>🕐 {formatDistanceToNow(new Date(inc.created_at), { addSuffix: true })}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
