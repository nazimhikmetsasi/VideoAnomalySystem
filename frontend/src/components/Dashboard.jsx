import { useEffect, useState, useRef, useCallback } from 'react'

const ANOMALY_COLORS = {
  FALL: 'bg-red-600',
  RUN: 'bg-orange-500',
  ZONE_VIOLATION: 'bg-purple-600'
}

const ANOMALY_LABELS = {
  FALL: 'Dusme',
  RUN: 'Kosma',
  ZONE_VIOLATION: 'Alan Ihlali'
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/alerts'

function handleAlert(data, setAlerts, setPopup, fetchHistory) {
  if (data.type !== 'anomaly_alert') return
  setAlerts((prev) => [data, ...prev].slice(0, 20))
  setPopup(data)
  fetchHistory()
  setTimeout(() => setPopup(null), 8000)
}

export default function Dashboard() {
  const [alerts, setAlerts] = useState([])
  const [history, setHistory] = useState([])
  const [connected, setConnected] = useState(false)
  const [popup, setPopup] = useState(null)
  const [testMsg, setTestMsg] = useState('')
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/anomalies?limit=30`)
      const data = await res.json()
      setHistory(data.items || [])
    } catch (e) {
      console.error('Gecmis kayitlar alinamadi', e)
    }
  }, [])

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      ws.send('ping')
    }

    ws.onclose = () => {
      setConnected(false)
      reconnectRef.current = setTimeout(connectWs, 3000)
    }

    ws.onerror = () => setConnected(false)

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        handleAlert(data, setAlerts, setPopup, fetchHistory)
      } catch (e) {
        console.error('WS mesaj hatasi', e)
      }
    }
  }, [fetchHistory])

  useEffect(() => {
    fetchHistory()
    connectWs()
    return () => {
      clearTimeout(reconnectRef.current)
      wsRef.current?.close()
    }
  }, [fetchHistory, connectWs])

  const sendTestAlert = async () => {
    try {
      const res = await fetch(`${API_URL}/api/test-alert`)
      const data = await res.json()
      setTestMsg(
        data.connected_clients > 0
          ? 'Test bildirimi gonderildi!'
          : `Uyari: Bagli istemci yok (${data.connected_clients}). Sayfayi yenile.`
      )
      if (data.connected_clients === 0) {
        connectWs()
      }
    } catch (e) {
      setTestMsg('API baglantisi yok — run_api.bat calistir.')
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 text-white p-6">
      <header className="mb-8 flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">MCBU Video Anomali Tespit Paneli</h1>
          <p className="text-slate-400 text-sm">Video Tabanli Anomali Tespiti ve Davranis Analizi</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={sendTestAlert}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium"
          >
            Test Bildirimi Gonder
          </button>
          <div className={`px-3 py-1 rounded-full text-sm ${connected ? 'bg-green-700' : 'bg-red-700'}`}>
            {connected ? 'WebSocket Bagli' : 'Baglanti Yok'}
          </div>
        </div>
      </header>

      {testMsg && (
        <div className="mb-4 p-3 bg-blue-900/50 border border-blue-500 rounded-lg text-sm">
          {testMsg}
        </div>
      )}

      {popup && (
        <div className="fixed top-4 right-4 z-50 max-w-md animate-pulse">
          <div className={`${ANOMALY_COLORS[popup.anomaly_type] || 'bg-red-600'} rounded-lg p-4 shadow-2xl border border-white/20`}>
            <h3 className="font-bold text-lg">
              {ANOMALY_LABELS[popup.anomaly_type] || popup.anomaly_type}
            </h3>
            <p className="mt-2 text-sm">{popup.report}</p>
            <p className="mt-1 text-xs opacity-80">
              Kamera: {popup.camera_id} | ID: {popup.track_id} | Guven: {popup.confidence_score?.toFixed(2)}
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-slate-800 rounded-xl p-5">
          <h2 className="text-lg font-semibold mb-4">Canli Uyarilar</h2>
          {alerts.length === 0 ? (
            <p className="text-slate-400 text-sm">
              Henuz bildirim yok. Ustteki mavi &quot;Test Bildirimi Gonder&quot; butonuna tikla.
            </p>
          ) : (
            <ul className="space-y-3">
              {alerts.map((a, i) => (
                <li key={i} className="bg-slate-700 rounded-lg p-3 border-l-4 border-orange-400">
                  <div className="flex justify-between">
                    <span className="font-medium">{ANOMALY_LABELS[a.anomaly_type]}</span>
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
