import { useHealth } from '../hooks/useIncidents'

const dot = (ok) =>
  `inline-block w-2 h-2 rounded-full mr-1 ${ok ? 'bg-green-400' : 'bg-red-500'}`

export default function HealthBar() {
  const h = useHealth()
  if (!h) return null
  const ok = (v) => v === 'ok'
  return (
    <div className="flex items-center gap-4 text-xs text-gray-400">
      <span className={`font-semibold ${h.status === 'healthy' ? 'text-green-400' : 'text-red-400'}`}>
        ● {h.status?.toUpperCase()}
      </span>
      {['postgres','mongo','redis'].map(s => (
        <span key={s}>
          <span className={dot(ok(h[s]))} />
          {s}
        </span>
      ))}
      <span className="text-gray-600">uptime {Math.round(h.uptime_seconds)}s</span>
    </div>
  )
}
