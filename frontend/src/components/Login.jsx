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
        setError(data.message || 'Giris basarisiz')
        return
      }
      setToken(data.token)
      onLogin(data)
    } catch {
      setError('API baglantisi yok')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6">
      <form onSubmit={submit} className="bg-slate-800 rounded-xl p-8 w-full max-w-md border border-slate-700">
        <h1 className="text-xl font-bold text-white mb-1">MCBU Guvenlik Paneli</h1>
        <p className="text-slate-400 text-sm mb-6">Giris yapin</p>
        {error && <div className="mb-4 p-3 bg-red-900/40 border border-red-500 rounded text-sm">{error}</div>}
        <label className="block text-sm text-slate-300 mb-1">Kullanici adi</label>
        <input
          className="w-full mb-4 px-3 py-2 rounded bg-slate-700 border border-slate-600 text-white"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <label className="block text-sm text-slate-300 mb-1">Sifre</label>
        <input
          type="password"
          className="w-full mb-6 px-3 py-2 rounded bg-slate-700 border border-slate-600 text-white"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium disabled:opacity-50"
        >
          {loading ? 'Giris...' : 'Giris Yap'}
        </button>
        <p className="text-xs text-slate-500 mt-4">Varsayilan: admin / admin123</p>
      </form>
    </div>
  )
}
