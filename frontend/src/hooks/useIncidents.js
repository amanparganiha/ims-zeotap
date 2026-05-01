import { useState, useEffect, useCallback } from 'react'
import { getIncidents, getHealth } from '../api/client'

export function useIncidents(pollInterval = 5000) {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)

  const fetch = useCallback(async () => {
    try {
      const res = await getIncidents({ limit: 100 })
      setIncidents(res.data)
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
    const id = setInterval(fetch, pollInterval)
    return () => clearInterval(id)
  }, [fetch, pollInterval])

  return { incidents, loading, error, refetch: fetch }
}

export function useHealth() {
  const [health, setHealth] = useState(null)
  useEffect(() => {
    const check = async () => {
      try { setHealth((await getHealth()).data) }
      catch { setHealth({ status: 'unreachable' }) }
    }
    check()
    const id = setInterval(check, 10000)
    return () => clearInterval(id)
  }, [])
  return health
}
