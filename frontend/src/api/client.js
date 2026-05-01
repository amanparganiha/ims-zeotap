import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 10000,
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

export default api

export const getIncidents  = (params) => api.get('/api/incidents', { params })
export const getIncident   = (id)     => api.get(`/api/incidents/${id}`)
export const getSignals    = (id)     => api.get(`/api/incidents/${id}/signals`)
export const updateStatus  = (id, s)  => api.patch(`/api/incidents/${id}/status`, { status: s })
export const submitRCA     = (id, d)  => api.post(`/api/incidents/${id}/rca`, d)
export const getRCA        = (id)     => api.get(`/api/incidents/${id}/rca`)
export const getCategories = ()       => api.get('/api/incidents/meta/categories')
export const getHealth     = ()       => api.get('/health')
