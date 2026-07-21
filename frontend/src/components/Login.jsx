import { useState } from 'react'
import { setToken } from '../api'

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const apiBase = import.meta.env.VITE_API_URL || ''
      const res = await fetch(`${apiBase}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await res.json()
      if (!data.ok) {
        setError(data.message || 'Giriş başarısız')
        return
      }
      setToken(data.token)
      onLogin(data)
    } catch {
      setError('API bağlantısı yok')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <form
        onSubmit={submit}
        className="panel-surface w-full max-w-md p-8"
      >
        <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--accent)] font-semibold mb-2">
          MCBU
        </p>
        <h1 className="font-display text-2xl font-semibold mb-1">Güvenlik Paneli</h1>
        <p className="text-[var(--muted)] text-sm mb-7">Devam etmek için giriş yapın</p>

        {error && (
          <div className="mb-4 px-3 py-2.5 rounded-lg border border-rose-500/40 bg-rose-500/10 text-sm text-rose-200">
            {error}
          </div>
        )}

        <label className="block text-sm text-[var(--muted)] mb-1.5">Kullanıcı adı</label>
        <input
          className="w-full mb-4 px-3.5 py-2.5 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-white outline-none focus:border-[var(--accent)] transition"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
        />

        <label className="block text-sm text-[var(--muted)] mb-1.5">Şifre</label>
        <input
          type="password"
          className="w-full mb-6 px-3.5 py-2.5 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-white outline-none focus:border-[var(--accent)] transition"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 rounded-lg font-medium bg-[var(--accent)] text-[#04120f] hover:brightness-110 transition disabled:opacity-50"
        >
          {loading ? 'Giriş yapılıyor…' : 'Giriş Yap'}
        </button>

        <p className="text-xs text-[var(--muted)] mt-5 text-center">
          Varsayılan: admin / admin123
        </p>
      </form>
    </div>
  )
}
