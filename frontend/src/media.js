import { apiFetch, getToken } from './api'

/** Auth gerektiren görseller için blob URL üretir. */
export async function fetchMediaUrl(path) {
  const apiBase = import.meta.env.VITE_API_URL || ''
  const token = getToken()
  const res = await fetch(`${apiBase}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) return null
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

export { apiFetch }
