import { useState } from 'react'
import { setToken } from '../api'
import { applyTheme, getStoredTheme } from '../constants'
import ThemeToggle from './ThemeToggle'

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [theme, setTheme] = useState(() => getStoredTheme())

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    applyTheme(next)
  }

  const submitLogin = async (e) => {
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
    <div className="login-page">
      <div className="login-page__theme">
        <ThemeToggle theme={theme} onToggle={toggleTheme} />
      </div>

      <div className="login-brand">
        <p className="login-brand__eyebrow">MCBU</p>
        <h1 className="login-brand__title">Güvenlik Paneli</h1>
      </div>

      <div className="login-container">
        <div className="login-form-panel login-form-panel--signin">
          <form className="login-form" onSubmit={submitLogin}>
            <h2>Giriş Yap</h2>
            <p className="login-form__hint">Admin paneline devam et</p>

            {error && <div className="login-alert login-alert--error">{error}</div>}

            <input
              type="text"
              placeholder="Kullanıcı Adı"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
            <input
              type="password"
              placeholder="Şifre"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
            <button type="submit" className="login-btn login-btn--solid" disabled={loading}>
              {loading ? 'Giriş yapılıyor…' : 'Giriş'}
            </button>
          </form>
        </div>

        <div className="login-overlay-container login-overlay-container--static">
          <div className="login-overlay login-overlay--static">
            <div className="login-overlay-panel login-overlay-panel--info">
              <h3>Proje Hakkında</h3>
              <p>
                Video tabanlı anomali tespiti: YOLO ile kişi algılama, DeepSORT ile takip,
                pose ve hareket analiziyle düşme, koşma ve alan ihlali uyarıları.
              </p>
              <p className="login-overlay__meta">
                Manisa Celal Bayar Üniversitesi · Bitirme projesi paneli
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
