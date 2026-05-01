const COLORS = {
  P0: 'bg-red-600 text-white',
  P1: 'bg-orange-500 text-white',
  P2: 'bg-yellow-500 text-black',
  P3: 'bg-gray-600 text-white',
}
const STATUS_COLORS = {
  OPEN:          'bg-red-900 text-red-300 border border-red-700',
  INVESTIGATING: 'bg-blue-900 text-blue-300 border border-blue-700',
  RESOLVED:      'bg-green-900 text-green-300 border border-green-700',
  CLOSED:        'bg-gray-800 text-gray-400 border border-gray-600',
}

export function SeverityBadge({ severity }) {
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded ${COLORS[severity] || COLORS.P3}`}>
      {severity}
    </span>
  )
}

export function StatusBadge({ status }) {
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${STATUS_COLORS[status] || ''}`}>
      {status}
    </span>
  )
}
