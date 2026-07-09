import { useEffect, useState } from 'react'
import Login from './components/Login'
import Dashboard from './components/Dashboard'
import { apiFetch, clearToken, getToken } from './api'

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const init = async () => {
      try {
        const healthRes = await fetch(`${import.meta.env.VITE_API_URL || ''}/health`)
        const health = await healthRes.json()
        if (!health.auth_enabled) {
          setUser({ username: 'guest', role: 'admin' })
          setLoading(false)
          return
        }
        const token = getToken()
        if (!token) {
          setLoading(false)
          return
        }
        const meRes = await apiFetch('/api/auth/me')
        if (meRes.ok) {
          setUser(await meRes.json())
        } else {
          clearToken()
        }
      } catch {
        setUser({ username: 'offline', role: 'viewer' })
      }
      setLoading(false)
    }
    init()
  }, [])

  if (loading) {
    return <div className="min-h-screen bg-slate-900 text-white flex items-center justify-center">Yukleniyor...</div>
  }

  if (!user) {
    return <Login onLogin={setUser} />
  }

  return <Dashboard user={user} onLogout={() => { clearToken(); setUser(null) }} />
}
