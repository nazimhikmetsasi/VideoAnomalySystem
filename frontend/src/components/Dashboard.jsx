import { useEffect, useState, useRef, useCallback } from 'react'
import { apiFetch } from '../api'
import MetricsPanel from './MetricsPanel'

const ANOMALY_COLORS = {
  FALL: 'bg-red-600',
  PERSON_ENTERED: 'bg-blue-600',
  RUN: 'bg-orange-500',
  ZONE_VIOLATION: 'bg-purple-600'
}

const ANOMALY_LABELS = {
  FALL: 'Dusme',
  PERSON_ENTERED: 'Kisi Girdi',
  RUN: 'Kosma',
  ZONE_VIOLATION: 'Alan Ihlali'
}

// Vite proxy uzerinden ayni origin (5173) — CORS/WS sorunu olmaz
const apiBase = import.meta.env.VITE_API_URL || ''
const wsUrl = import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/alerts`

function showAlert(data, setAlerts, setPopup) {
  if (!data || data.type !== 'anomaly_alert') return
  setAlerts((prev) => {
    const key = `${data.id}-${data.timestamp}-${data.track_id}`
    if (prev.some((a) => `${a.id}-${a.timestamp}-${a.track_id}` === key)) return prev
    return [data, ...prev].slice(0, 20)
  })
  setPopup(data)
  setTimeout(() => setPopup(null), 8000)
}

export default function Dashboard({ user, onLogout }) {
  const [alerts, setAlerts] = useState([])
  const [history, setHistory] = useState([])
  const [connected, setConnected] = useState(false)
  const [popup, setPopup] = useState(null)
  const [testMsg, setTestMsg] = useState('')
  const [llmStatus, setLlmStatus] = useState(null)
  const [cameras, setCameras] = useState([])
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)
  const lastDbIdRef = useRef(0)

  const fetchHistory = useCallback(async () => {
    try {
      const res = await apiFetch('/api/anomalies?limit=30')
      if (!res.ok) return
      const data = await res.json()
      const items = data.items || []
      setHistory(items)

      if (items.length > 0 && items[0].id > lastDbIdRef.current) {
        const latest = items[0]
        if (lastDbIdRef.current > 0) {
          showAlert({
            type: 'anomaly_alert',
            id: latest.id,
            camera_id: latest.camera_id,
            track_id: latest.track_id,
            anomaly_type: latest.anomaly_type,
            confidence_score: latest.confidence_score,
            report: latest.ai_generated_report || `${latest.anomaly_type} tespit edildi`,
            timestamp: latest.timestamp
          }, setAlerts, setPopup)
        }
        lastDbIdRef.current = items[0].id
      } else if (items.length > 0 && lastDbIdRef.current === 0) {
        lastDbIdRef.current = items[0].id
      }
    } catch (e) {
      console.error('Gecmis kayitlar alinamadi', e)
    }
  }, [])

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setTestMsg('')
      ws.send('ping')
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      reconnectRef.current = setTimeout(connectWs, 3000)
    }

    ws.onerror = () => {
      setConnected(false)
    }

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        if (data.type === 'connected') return
        showAlert(data, setAlerts, setPopup)
        fetchHistory()
      } catch (e) {
        console.error('WS mesaj hatasi', e)
      }
    }
  }, [fetchHistory])

  const fetchLlmStatus = useCallback(async () => {
    try {
      const res = await apiFetch('/api/llm/status')
      if (res.ok) setLlmStatus(await res.json())
    } catch (e) {
      console.error('LLM durumu alinamadi', e)
    }
  }, [])

  const fetchCameras = useCallback(async () => {
    try {
      const res = await apiFetch('/api/cameras')
      if (res.ok) {
        const data = await res.json()
        setCameras(data.cameras || [])
      }
    } catch (e) {
      console.error('Kamera listesi alinamadi', e)
    }
  }, [])

  useEffect(() => {
    fetchHistory()
    fetchLlmStatus()
    fetchCameras()
    connectWs()
    const poll = setInterval(fetchHistory, 3000)
    return () => {
      clearInterval(poll)
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [fetchHistory, fetchLlmStatus, fetchCameras, connectWs])

  const sendTestAlert = async () => {
    try {
      const res = await apiFetch('/api/test-alert', { method: 'POST' })
      const data = await res.json()
      if (data.alert) {
        showAlert(data.alert, setAlerts, setPopup)
        setTestMsg('Test bildirimi gosterildi!')
      } else {
        setTestMsg(data.message || 'Bildirim gonderildi')
      }
      fetchHistory()
    } catch (e) {
      setTestMsg('API baglantisi yok — .\\run_api.bat calistir (PowerShell)')
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      <header className="mb-8 flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">MCBU Video Anomali Tespit Paneli</h1>
          <p className="text-slate-400 text-sm">Video Tabanli Anomali Tespiti ve Davranis Analizi</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {user?.role === 'admin' && (
            <button
              onClick={sendTestAlert}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium"
            >
              Test Bildirimi Gonder
            </button>
          )}
          <span className="text-sm text-slate-400">{user?.username} ({user?.role})</span>
          <button onClick={onLogout} className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-sm">
            Cikis
          </button>
          {llmStatus && (
            <div className={`px-3 py-1 rounded-full text-sm ${llmStatus.mode === 'llm' ? 'bg-emerald-700' : 'bg-slate-600'}`}
              title={llmStatus.mode === 'llm' ? `${llmStatus.provider} / ${llmStatus.model}` : 'GEMINI_API_KEY tanimli degil — sablon rapor'}
            >
              {llmStatus.mode === 'llm' ? 'Gemini AI Aktif' : 'Sablon Rapor'}
            </div>
          )}
          <div className={`px-3 py-1 rounded-full text-sm ${connected ? 'bg-green-700' : 'bg-red-700'}`}>
            {connected ? 'WebSocket Bagli' : 'Baglanti Yok (polling aktif)'}
          </div>
        </div>
      </header>

      {testMsg && (
        <div className="mb-4 p-3 bg-blue-900/50 border border-blue-500 rounded-lg text-sm">
          {testMsg}
        </div>
      )}

      <MetricsPanel />

      {cameras.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {cameras.map((c) => (
            <span key={c.id} className="px-3 py-1 bg-slate-800 rounded-full text-xs text-slate-300">
              {c.name || c.id} {c.enabled === false ? '(kapali)' : ''}
            </span>
          ))}
        </div>
      )}

      {popup && (
        <div className="fixed top-4 right-4 z-50 max-w-md">
          <div className={`${ANOMALY_COLORS[popup.anomaly_type] || 'bg-red-600'} rounded-lg p-4 shadow-2xl border border-white/20`}>
            <h3 className="font-bold text-lg">
              {ANOMALY_LABELS[popup.anomaly_type] || popup.anomaly_type}
            </h3>
            <p className="mt-2 text-sm">{popup.report}</p>
            <p className="mt-1 text-xs opacity-80">
              Kamera: {popup.camera_id} | ID: {popup.track_id} | Guven: {Number(popup.confidence_score).toFixed(2)}
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-slate-800 rounded-xl p-5">
          <h2 className="text-lg font-semibold mb-4">Canli Uyarilar</h2>
          {alerts.length === 0 ? (
            <p className="text-slate-400 text-sm">
              Henuz bildirim yok. &quot;Test Bildirimi Gonder&quot; butonuna tikla.
            </p>
          ) : (
            <ul className="space-y-3">
              {alerts.map((a, i) => (
                <li key={i} className="bg-slate-700 rounded-lg p-3 border-l-4 border-orange-400">
                  <div className="flex justify-between">
                    <span className="font-medium">{ANOMALY_LABELS[a.anomaly_type] || a.anomaly_type}</span>
                    <span className="text-xs text-slate-400">{a.camera_id}</span>
                  </div>
                  <p className="text-sm mt-1 text-slate-300">{a.report}</p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-slate-800 rounded-xl p-5">
          <h2 className="text-lg font-semibold mb-4">Gecmis Kayitlar</h2>
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-600">
                  <th className="text-left py-2">Zaman</th>
                  <th className="text-left py-2">Tip</th>
                  <th className="text-left py-2">Kamera</th>
                  <th className="text-left py-2">Guven</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id} className="border-b border-slate-700">
                    <td className="py-2 text-xs">{new Date(h.timestamp).toLocaleString('tr-TR')}</td>
                    <td className="py-2">{ANOMALY_LABELS[h.anomaly_type] || h.anomaly_type}</td>
                    <td className="py-2">{h.camera_id}</td>
                    <td className="py-2">{h.confidence_score?.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  )
}
