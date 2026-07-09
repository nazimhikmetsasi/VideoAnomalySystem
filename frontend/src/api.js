const TOKEN_KEY = 'mcbu_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function apiFetch(path, options = {}) {
  const apiBase = import.meta.env.VITE_API_URL || ''
  const headers = {
    'Content-Type': 'application/json',
    ...authHeaders(),
    ...(options.headers || {}),
  }
  const res = await fetch(`${apiBase}${path}`, { ...options, headers })
  if (res.status === 401) {
    clearToken()
    window.location.reload()
  }
  return res
}
