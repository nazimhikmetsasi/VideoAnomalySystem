import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { apiFetch } from '../api'
import { matchFilters } from '../components/AlertFilters'
import {
  SEVERITY_RANK,
  SOUND_KEY,
  getStoredTheme,
  applyTheme,
  playAlertBeep,
  unlockAlertSound,
  alertKey,
  isAlertRead,
  addAlertToReadSet,
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
  if (soundOn) queueMicrotask(() => playAlertBeep())
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
    return [{ ...data, read: false }, ...prev].slice(0, 40)
  })
  setPopup(data)
  setTimeout(() => setPopup(null), 8000)
}

function sortBySeverity(list, readSet) {
  return [...list].sort((a, b) => {
    const ra = isAlertRead(readSet, a) ? 1 : 0
    const rb = isAlertRead(readSet, b) ? 1 : 0
    if (ra !== rb) return ra - rb
    const sa = SEVERITY_RANK[a.anomaly_type] || 0
    const sb = SEVERITY_RANK[b.anomaly_type] || 0
    if (sb !== sa) return sb - sa
    const ta = new Date(a.timestamp || 0).getTime()
    const tb = new Date(b.timestamp || 0).getTime()
    return tb - ta
  })
}

function historyToAlert(h) {
  return {
    type: 'anomaly_alert',
    id: h.id,
    camera_id: h.camera_id,
    track_id: h.track_id,
    anomaly_type: h.anomaly_type,
    confidence_score: h.confidence_score,
    report: h.ai_generated_report || `${h.anomaly_type} tespit edildi`,
    timestamp: h.timestamp,
    snapshot_id: h.snapshot_id,
  }
}

/** Okunmamış kayıtları canlı kuyruğa yükle (yenilemede sıfırlanmasın). */
function mergeUnreadAlerts(prev, historyItems, read) {
  const map = new Map()
  for (const h of historyItems || []) {
    const mapped = historyToAlert(h)
    if (isAlertRead(read, mapped)) continue
    map.set(alertKey(mapped), mapped)
  }
  for (const a of prev || []) {
    if (isAlertRead(read, a)) continue
    const key = alertKey(a)
    if (!map.has(key)) map.set(key, a)
  }
  return [...map.values()].slice(0, 40)
}

export function useDashboard() {
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
  const [selectedKeys, setSelectedKeys] = useState(() => new Set())
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)
  const lastDbIdRef = useRef(0)
  const soundRef = useRef(soundOn)
  soundRef.current = soundOn
  const readSetRef = useRef(readSet)
  readSetRef.current = readSet
  const historyRef = useRef(history)
  historyRef.current = history
  const alertsRef = useRef(alerts)
  alertsRef.current = alerts

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
    unlockAlertSound()
    if (next) playAlertBeep()
  }

  useEffect(() => {
    const unlock = () => unlockAlertSound()
    window.addEventListener('pointerdown', unlock, { once: true })
    window.addEventListener('keydown', unlock, { once: true })
    return () => {
      window.removeEventListener('pointerdown', unlock)
      window.removeEventListener('keydown', unlock)
    }
  }, [])

  const markRead = useCallback((item) => {
    const markedOnly = addAlertToReadSet(new Set(), item)
    setReadSet((prev) => {
      const next = addAlertToReadSet(prev, item)
      saveReadSet(next)
      readSetRef.current = next
      return next
    })
    setAlerts((prev) => prev.filter((a) => !isAlertRead(markedOnly, a)))
  }, [])

  const markReadKeys = useCallback((keys) => {
    if (!keys?.length) return
    const keySet = new Set(keys)
    let nextRead = null
    setReadSet((prev) => {
      let next = new Set(prev)
      for (const k of keys) next.add(k)
      for (const item of [...(alertsRef.current || []), ...(historyRef.current || [])]) {
        if (keySet.has(alertKey(item)) || isAlertRead(keySet, item)) {
          next = addAlertToReadSet(next, item)
        }
      }
      saveReadSet(next)
      readSetRef.current = next
      nextRead = next
      return next
    })
    setAlerts((prev) => prev.filter((a) => !isAlertRead(nextRead || readSetRef.current, a)))
    setSelectedKeys((prev) => {
      const next = new Set(prev)
      for (const k of keys) next.delete(k)
      return next
    })
  }, [])

  const toggleSelect = useCallback((key) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }, [])

  const selectAllInList = useCallback((list) => {
    setSelectedKeys(new Set(list.map((item) => alertKey(item))))
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedKeys(new Set())
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const res = await apiFetch('/api/anomalies?limit=100')
      if (!res.ok) return
      const data = await res.json()
      const items = data.items || []
      setHistory(items)

      // Okunmamış geçmiş → canlı kuyruk (sayfa yenilenince sayı korunur)
      const read = readSetRef.current
      setAlerts((prev) => mergeUnreadAlerts(prev, items, read))

      const wsOpen = wsRef.current?.readyState === WebSocket.OPEN
      if (!wsOpen && items.length > 0 && items[0].id > lastDbIdRef.current) {
        const latest = items[0]
        if (lastDbIdRef.current > 0) {
          const mapped = historyToAlert(latest)
          if (!isAlertRead(read, mapped)) {
            showAlert(mapped, setAlerts, setPopup, soundRef.current)
          }
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
    unlockAlertSound()
    if (soundRef.current) playAlertBeep()
    try {
      const res = await apiFetch('/api/test-alert', { method: 'POST' })
      const data = await res.json()
      if (data.alert) {
        showAlert(data.alert, setAlerts, setPopup, false)
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

  // Okunmamış: geçmiş + canlı (yenilemede history ile korunur)
  const unreadKeys = useMemo(() => {
    const keys = new Set()
    for (const a of alerts) {
      if (!isAlertRead(readSet, a)) keys.add(alertKey(a))
    }
    for (const h of history) {
      if (!isAlertRead(readSet, h)) keys.add(alertKey(h))
    }
    return [...keys]
  }, [alerts, history, readSet])

  const unreadCount = unreadKeys.length
  const selectedCount = selectedKeys.size
  const allLiveSelected =
    filteredAlerts.length > 0 && filteredAlerts.every((a) => selectedKeys.has(alertKey(a)))
  const allHistorySelected =
    filteredHistory.length > 0 && filteredHistory.every((h) => selectedKeys.has(alertKey(h)))
  const unreadLiveKeys = unreadKeys
  const unreadHistoryKeys = filteredHistory
    .filter((h) => !isAlertRead(readSet, h))
    .map((h) => alertKey(h))
  const selectedUnreadKeys = [...selectedKeys].filter((k) => !readSet.has(k))

  return {
    alerts,
    history,
    connected,
    popup,
    setPopup,
    testMsg,
    llmStatus,
    cameras,
    theme,
    soundOn,
    filters,
    setFilters,
    selectedAlert,
    setSelectedAlert,
    previewCam,
    setPreviewCam,
    readSet,
    selectedKeys,
    toggleTheme,
    toggleSound,
    markRead,
    markReadKeys,
    toggleSelect,
    selectAllInList,
    clearSelection,
    sendTestAlert,
    filteredAlerts,
    filteredHistory,
    unreadCount,
    selectedCount,
    allLiveSelected,
    allHistorySelected,
    unreadLiveKeys,
    unreadHistoryKeys,
    selectedUnreadKeys,
  }
}
