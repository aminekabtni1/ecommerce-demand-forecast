import axios from 'axios'

const RAW = import.meta.env.VITE_API_BASE_URL
// Vercel: VITE_API_BASE_URL="" means same origin (serverless). Keep empty, don't fallback to localhost.
const BASE = RAW !== undefined ? RAW : 'http://localhost:8000'

export const api = axios.create({ baseURL: BASE || undefined, timeout: 15000 })

export const fetchHealth = () => api.get('/api/health').then(r=>r.data)
export const fetchKpis = (days=30) => api.get(`/api/kpis?days=${days}`).then(r=>r.data)
export const fetchTrends = (params={}) => {
  const q = new URLSearchParams(params).toString()
  return api.get(`/api/sales/trends?${q}`).then(r=>r.data)
}
export const fetchForecast = (params={}) => {
  const q = new URLSearchParams(params).toString()
  return api.get(`/api/forecast?${q}`).then(r=>r.data)
}
export const fetchAnomalies = (params={}) => {
  const q = new URLSearchParams(params).toString()
  return api.get(`/api/anomalies?${q}`).then(r=>r.data)
}
export const fetchProducts = () => api.get('/api/products').then(r=>r.data)
export const fetchCategories = () => api.get('/api/categories').then(r=>r.data)
