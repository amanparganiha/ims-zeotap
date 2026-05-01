import { useState, useEffect } from 'react'
import { submitRCA, getCategories } from '../api/client'

const toLocalDatetime = (d) => {
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function RCAForm({ incidentId, onSubmit }) {
  const now = new Date()
  const [categories, setCategories] = useState([])
  const [form, setForm] = useState({
    incident_start: toLocalDatetime(new Date(now - 3600000)),
    incident_end:   toLocalDatetime(now),
    root_cause_category: '',
    fix_applied: '',
    prevention_steps: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getCategories().then(r => setCategories(r.data.categories)).catch(() => {})
  }, [])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async () => {
    setError(null)
    if (!form.root_cause_category) return setError('Select a root cause category')
    if (!form.fix_applied.trim())  return setError('Fix applied is required')
    if (!form.prevention_steps.trim()) return setError('Prevention steps are required')

    setSubmitting(true)
    try {
      await submitRCA(incidentId, {
        ...form,
        incident_start: new Date(form.incident_start).toISOString(),
        incident_end:   new Date(form.incident_end).toISOString(),
      })
      onSubmit?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-5">
      <h2 className="text-base font-semibold text-white">Root Cause Analysis</h2>

      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <Label text="Incident Start">
          <input
            type="datetime-local"
            value={form.incident_start}
            onChange={e => set('incident_start', e.target.value)}
            className={input}
          />
        </Label>
        <Label text="Incident End">
          <input
            type="datetime-local"
            value={form.incident_end}
            onChange={e => set('incident_end', e.target.value)}
            className={input}
          />
        </Label>
      </div>

      <Label text="Root Cause Category">
        <select
          value={form.root_cause_category}
          onChange={e => set('root_cause_category', e.target.value)}
          className={input}
        >
          <option value="">— Select category —</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </Label>

      <Label text="Fix Applied">
        <textarea
          rows={4}
          value={form.fix_applied}
          onChange={e => set('fix_applied', e.target.value)}
          placeholder="Describe the fix that was applied to resolve the incident..."
          className={`${input} resize-none`}
        />
      </Label>

      <Label text="Prevention Steps">
        <textarea
          rows={4}
          value={form.prevention_steps}
          onChange={e => set('prevention_steps', e.target.value)}
          placeholder="What steps will prevent this from happening again?"
          className={`${input} resize-none`}
        />
      </Label>

      <button
        onClick={handleSubmit}
        disabled={submitting}
        className="w-full py-2.5 rounded bg-green-700 hover:bg-green-600 text-sm font-semibold disabled:opacity-50 transition-colors"
      >
        {submitting ? 'Submitting...' : 'Submit RCA'}
      </button>
    </div>
  )
}

const input = 'w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 text-gray-100'

function Label({ text, children }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-1.5">{text}</div>
      {children}
    </div>
  )
}
