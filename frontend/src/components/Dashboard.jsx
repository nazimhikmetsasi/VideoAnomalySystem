import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { apiFetch } from '../api'
import MetricsPanel from './MetricsPanel'
import LivePreview from './LivePreview'
import ZoneMap from './ZoneMap'
import AlertFilters, { matchFilters } from './AlertFilters'
import StatsSummary from './StatsSummary'
import SnapshotModal from './SnapshotModal'
import ThemeToggle from './ThemeToggle'
import SoundToggle from './SoundToggle'
import {
  ANOMALY_LABELS,
  ANOMALY_ACCENT,
  ANOMALY_BADGE,
  SEVERITY_RANK,
  SOUND_KEY,
  getStoredTheme,
  applyTheme,
  playAlertBeep,
  alertKey,
  loadReadSet,
  saveReadSet,
} from '../constants'

const wsUrl = import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/alerts`

const MERGE_PRIORITY = {
  RUN_ZONE: 4,
  FALL: 4,
  RUN: 3,
  ZONE_VIOLATION: 2,
  PERSON_ENTERED: 1,
}

function showAlert(data, setAlerts, setPopup, soundOn) {
  if (!data || data.type !== 'anomaly_alert') return
  setAlerts((prev) => {
    const tid = data.track_id
    const cam = data.camera_id
    const atype = data.anomaly_type
    if (data.id != null && prev.some((a) => a.id != null && a.id === data.id)) return prev

    const idx = prev.findIndex((a) => a.track_id === tid && a.camera_id === cam)
    if (idx >= 0) {
      const old = prev[idx]
      const oldP = MERGE_PRIORITY[old.anomaly_type] || 0
      const newP = MERGE_PRIORITY[atype] || 0
      if (newP <= oldP) return prev
      const next = [...prev]
      next[idx] = { ...data, read: false }
      return next
    }
    if (soundOn) queueMicrotask(() => playAlertBeep())
    return [{ ...data, read: false }, ...prev].slice(0, 40)
  })
  setPopup(data)
  setTimeout(() => setPopup(null), 8000)
}

function sortBySeverity(list, readSet) {
  return [...list].sort((a, b) => {
    const ra = readSet.has(alertKey(a)) ? 1 : 0
    const rb = readSet.has(alertKey(b)) ? 1 : 0
    if (ra !== rb) return ra - rb
    const sa = SEVERITY_RANK[a.anomaly_type] || 0
    const sb = SEVERITY_RANK[b.anomaly_type] || 0
    if (sb !== sa) return sb - sa
    const ta = new Date(a.timestamp || 0).getTime()
    const tb = new Date(b.timestamp || 0).getTime()
    return tb - ta
  })
}

export default function Dashboard({ user, onLogout }) {
  const [alerts, setAlerts] = useState([])
  const [history, setHistory] = useState([])
  const [connected, setConnected] = useState(false)
  const [popup, setPopup] = useState(null)
  const [testMsg, setTestMsg] = useState('')
  const [llmStatus, setLlmStatus] = useState(null)
  const [cameras, setCameras] = useState([])
  const [theme, setTheme] = useState(() => getStoredTheme())
  const [soundOn, setSoundOn] = useState(() => localStorage.getItem(SOUND_KEY) !== 'off')
  const [filters, setFilters] = useState({ q: '', type: '', camera: '', date: '', range: '' })
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [previewCam, setPreviewCam] = useState('cam_01')
  const [readSet, setReadSet] = useState(() => loadReadSet())
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)
  const lastDbIdRef = useRef(0)
  const soundRef = useRef(soundOn)
  soundRef.current = soundOn

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    applyTheme(next)
  }

  const toggleSound = () => {
    const next = !soundOn
    setSoundOn(next)
    localStorage.setItem(SOUND_KEY, next ? 'on' : 'off')
  }

  const markRead = useCallback((item) => {
    const key = alertKey(item)
    setReadSet((prev) => {
      const next = new Set(prev)
      next.add(key)
      saveReadSet(next)
      return next
    })
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const res = await apiFetch('/api/anomalies?limit=100')
      if (!res.ok) return
      const data = await res.json()
      const items = data.items || []
      setHistory(items)

      const wsOpen = wsRef.current?.readyState === WebSocket.OPEN
      if (!wsOpen && items.length > 0 && items[0].id > lastDbIdRef.current) {
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
            timestamp: latest.timestamp,
            snapshot_id: latest.snapshot_id,
          }, setAlerts, setPopup, soundRef.current)
        }
        lastDbIdRef.current = items[0].id
      } else if (items.length > 0) {
        lastDbIdRef.current = Math.max(lastDbIdRef.current, items[0].id)
      }
    } catch (e) {
      console.error('Geçmiş kayıtlar alınamadı', e)
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

    ws.onerror = () => setConnected(false)

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)
        if (data.type === 'connected') return
        showAlert(data, setAlerts, setPopup, soundRef.current)
        fetchHistory()
      } catch (e) {
        console.error('WS mesaj hatası', e)
      }
    }
  }, [fetchHistory])

  const fetchLlmStatus = useCallback(async () => {
    try {
      const res = await apiFetch('/api/llm/status')
      if (res.ok) setLlmStatus(await res.json())
    } catch (e) {
      console.error('LLM durumu alınamadı', e)
    }
  }, [])

  const fetchCameras = useCallback(async () => {
    try {
      const res = await apiFetch('/api/cameras')
      if (res.ok) {
        const data = await res.json()
        const list = data.cameras || []
        setCameras(list)
        if (list[0]?.id) setPreviewCam(list[0].id)
      }
    } catch (e) {
      console.error('Kamera listesi alınamadı', e)
    }
  }, [])

  useEffect(() => {
    fetchHistory()
    fetchLlmStatus()
    fetchCameras()
    connectWs()
    const poll = setInterval(fetchHistory, 5000)
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
        showAlert(data.alert, setAlerts, setPopup, soundRef.current)
        setTestMsg('Test bildirimi gösterildi.')
      } else {
        setTestMsg(data.message || 'Bildirim gönderildi.')
      }
      fetchHistory()
    } catch {
      setTestMsg('API bağlantısı yok — .\\run_api.bat çalıştırın.')
    }
  }

  const filteredAlerts = useMemo(() => {
    const list = alerts.filter((a) => matchFilters(a, filters))
    return sortBySeverity(list, readSet)
  }, [alerts, filters, readSet])

  const filteredHistory = useMemo(() => {
    const list = history.filter((h) => matchFilters({
      ...h,
      report: h.ai_generated_report,
    }, filters))
    return sortBySeverity(list, readSet)
  }, [history, filters, readSet])

  const unreadCount = filteredAlerts.filter((a) => !readSet.has(alertKey(a))).length

  const btnGhost = 'px-3.5 py-1.5 rounded-md text-sm font-medium border border-[var(--line)] text-[var(--text)] hover:bg-[var(--bg2)] transition'
  const btnPrimary = 'px-3.5 py-1.5 rounded-md text-sm font-medium bg-[var(--accent)] text-[#04120f] hover:brightness-110 transition'

  const userLabel = user?.username || 'kullanıcı'

  return (
    <div className="min-h-screen text-[var(--text)]">
      <header className="border-b border-[var(--line)] bg-[var(--bg1)]/85 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-4 min-w-0">
            <div className="header-toggles">
              <ThemeToggle theme={theme} onToggle={toggleTheme} />
              <SoundToggle soundOn={soundOn} onToggle={toggleSound} />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--accent)] font-semibold mb-1">
                MCBU
              </p>
              <h1 className="font-display text-xl md:text-2xl font-semibold">
                Video Anomali Paneli
              </h1>
              <p className="text-sm text-[var(--muted)] mt-0.5">
                Video tabanlı anomali tespiti ve davranış analizi
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium border border-[var(--line)] ${
              connected ? 'text-emerald-600 bg-emerald-500/10' : 'text-rose-500 bg-rose-500/10'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
              {connected ? 'Bağlı' : 'Bağlantı yok'}
            </span>

            {llmStatus && (
              <span
                className="px-3 py-1.5 rounded-md text-xs font-medium border border-[var(--line)] text-[var(--muted)] bg-[var(--bg2)]"
                title={llmStatus.mode === 'llm' ? `${llmStatus.provider} / ${llmStatus.model}` : 'GEMINI_API_KEY tanımlı değil'}
              >
                {llmStatus.mode === 'llm' ? 'Gemini AI' : 'Şablon rapor'}
              </span>
            )}

            <span className="text-sm text-[var(--muted)] hidden sm:inline">
              {userLabel}
            </span>

            {user?.role === 'admin' && (
              <button type="button" onClick={sendTestAlert} className={btnPrimary}>
                Test bildirimi
              </button>
            )}

            <button type="button" onClick={onLogout} className={btnGhost}>
              Çıkış Yap
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-5 py-6 space-y-5">
        {testMsg && (
          <div className="toast-in px-4 py-3 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10 text-sm">
            {testMsg}
          </div>
        )}

        {popup && (
          <div className="fixed top-20 right-5 z-50 max-w-sm toast-in">
            <button
              type="button"
              onClick={() => setSelectedAlert(popup)}
              className={`w-full text-left rounded-lg border border-[var(--line)] bg-[var(--bg1)] p-4 shadow-2xl border-l-4 ${ANOMALY_ACCENT[popup.anomaly_type] || 'border-l-[#e05656]'}`}
            >
              <h3 className="font-display font-semibold">
                {ANOMALY_LABELS[popup.anomaly_type] || popup.anomaly_type}
              </h3>
              <p className="mt-2 text-sm text-[var(--muted)] leading-relaxed">{popup.report}</p>
              <p className="mt-3 text-xs text-[var(--muted)]">
                {popup.camera_id} · Varlık {popup.track_id} · Güven {Number(popup.confidence_score).toFixed(2)}
              </p>
            </button>
          </div>
        )}

        <AlertFilters
          filters={filters}
          onChange={setFilters}
          cameras={cameras}
          exportRows={filteredHistory}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <section className="panel-surface overflow-hidden">
            <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between gap-2">
              <h2 className="font-display text-base font-semibold">Canlı Uyarılar</h2>
              <span className="text-xs text-[var(--muted)]">
                {unreadCount} okunmamış · {filteredAlerts.length} toplam
              </span>
            </div>
            <div className="p-3 max-h-[28rem] overflow-auto">
              {filteredAlerts.length === 0 ? (
                <p className="text-[var(--muted)] text-sm px-2 py-6 text-center">
                  Filtreye uyan bildirim yok.
                </p>
              ) : (
                <ul className="space-y-2">
                  {filteredAlerts.map((a, i) => {
                    const key = alertKey(a)
                    const isRead = readSet.has(key)
                    return (
                      <li key={`${key}-${i}`} className={isRead ? 'alert-card--read' : ''}>
                        <div
                          className={`rounded-lg bg-[var(--bg2)]/80 border border-[var(--line)] border-l-4 p-3.5 ${ANOMALY_ACCENT[a.anomaly_type] || 'border-l-[#e8a54b]'}`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <button
                              type="button"
                              className="text-left flex-1 min-w-0"
                              onClick={() => setSelectedAlert(a)}
                            >
                              <span className={`text-xs font-medium px-2 py-0.5 rounded ${ANOMALY_BADGE[a.anomaly_type] || 'bg-black/5'}`}>
                                {ANOMALY_LABELS[a.anomaly_type] || a.anomaly_type}
                              </span>
                              <p className="text-sm mt-2 text-[var(--muted)] leading-relaxed">{a.report}</p>
                              <p className="text-xs text-[var(--muted)] mt-1">{a.camera_id} · Varlık {a.track_id}</p>
                            </button>
                            <div className="flex flex-col items-end gap-2 shrink-0">
                              <span className="text-xs text-[var(--muted)]">{a.camera_id}</span>
                              {!isRead ? (
                                <button
                                  type="button"
                                  onClick={() => markRead(a)}
                                  className="px-2 py-1 text-[11px] rounded-md border border-[var(--line)] hover:bg-[var(--bg1)]"
                                >
                                  Okundu
                                </button>
                              ) : (
                                <span className="text-[11px] text-[var(--muted)]">Okundu</span>
                              )}
                            </div>
                          </div>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </section>

          <section className="panel-surface overflow-hidden">
            <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between">
              <h2 className="font-display text-base font-semibold">Geçmiş Kayıtlar</h2>
              <span className="text-xs text-[var(--muted)]">{filteredHistory.length}</span>
            </div>
            <div className="overflow-auto max-h-[28rem]">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[var(--bg1)]">
                  <tr className="text-[var(--muted)] text-left border-b border-[var(--line)]">
                    <th className="px-5 py-3 font-medium">Zaman</th>
                    <th className="px-3 py-3 font-medium">Tip</th>
                    <th className="px-3 py-3 font-medium">Kamera</th>
                    <th className="px-5 py-3 font-medium text-right">Güven</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHistory.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-5 py-8 text-center text-[var(--muted)]">
                        Kayıt yok.
                      </td>
                    </tr>
                  ) : (
                    filteredHistory.map((h) => {
                      const isRead = readSet.has(alertKey(h))
                      return (
                        <tr
                          key={h.id}
                          className={`border-b border-[var(--line)] hover:bg-black/[0.03] cursor-pointer ${isRead ? 'alert-card--read' : ''}`}
                          onClick={() => setSelectedAlert({
                            ...h,
                            report: h.ai_generated_report,
                          })}
                        >
                          <td className="px-5 py-3 text-xs text-[var(--muted)] whitespace-nowrap">
                            {new Date(h.timestamp).toLocaleString('tr-TR')}
                          </td>
                          <td className="px-3 py-3">
                            <span className={`text-xs font-medium px-2 py-0.5 rounded ${ANOMALY_BADGE[h.anomaly_type] || ''}`}>
                              {ANOMALY_LABELS[h.anomaly_type] || h.anomaly_type}
                            </span>
                          </td>
                          <td className="px-3 py-3 text-[var(--muted)]">{h.camera_id}</td>
                          <td className="px-5 py-3 text-right tabular-nums">
                            {h.confidence_score?.toFixed(2)}
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 space-y-5">
            <LivePreview cameraId={previewCam} />
            {cameras.length > 1 && (
              <div className="flex flex-wrap gap-2 -mt-2">
                {cameras.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setPreviewCam(c.id)}
                    className={`px-3 py-1 rounded-md text-xs border ${
                      previewCam === c.id
                        ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10'
                        : 'border-[var(--line)] text-[var(--muted)]'
                    }`}
                  >
                    {c.name || c.id}
                  </button>
                ))}
              </div>
            )}
            <StatsSummary history={history} />
          </div>
          <div className="space-y-5">
            <ZoneMap cameraId={previewCam} />
            <MetricsPanel />
          </div>
        </div>
      </main>

      <SnapshotModal
        alert={selectedAlert}
        history={history}
        onClose={() => setSelectedAlert(null)}
        onMarkRead={(a) => {
          markRead(a)
        }}
      />
    </div>
  )
}
