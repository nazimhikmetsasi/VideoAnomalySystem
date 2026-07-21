import { useEffect, useState, useRef, useCallback } from 'react'
import { apiFetch } from '../api'
import { fetchMediaUrl } from '../media'

const MOTION_TR = {
  RUNNING: 'Koşuyor',
  WALKING: 'Yürüyor',
  STANDING: 'Duruyor',
  FALLING: 'Düşüyor',
  FALL: 'Düşüyor',
}

/** Net varlık anları galerisi — sol/sağ oklarla gezinme. */
export default function LivePreview({ cameraId = 'cam_01' }) {
  const [items, setItems] = useState([])
  const [index, setIndex] = useState(0)
  const [url, setUrl] = useState(null)
  const [liveUrl, setLiveUrl] = useState(null)
  const [error, setError] = useState('')
  const [paused, setPaused] = useState(false)
  const inFlight = useRef(false)
  const urlRef = useRef(null)
  const liveRef = useRef(null)

  const current = items[index] || null

  const loadGallery = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/media/gallery/${cameraId}?limit=40`)
      if (!res.ok) return
      const data = await res.json()
      const next = data.items || []
      setItems((prev) => {
        const newer = next.length > 0 && (!prev.length || next[0]?.id !== prev[0]?.id)
        if (newer) queueMicrotask(() => setIndex(0))
        return next
      })
      setError('')
    } catch {
      /* sessiz */
    }
  }, [cameraId])

  useEffect(() => {
    if (items.length === 0) {
      setIndex(0)
      return
    }
    if (index >= items.length) setIndex(items.length - 1)
  }, [items, index])

  // Galeri listesi
  useEffect(() => {
    let active = true
    const tick = () => {
      if (!active || paused || document.hidden) return
      loadGallery()
    }
    tick()
    const id = setInterval(tick, 2500)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [loadGallery, paused])

  // Secili galeri goruntusu
  useEffect(() => {
    let alive = true
    ;(async () => {
      if (!current?.id) {
        if (urlRef.current) {
          URL.revokeObjectURL(urlRef.current)
          urlRef.current = null
        }
        setUrl(null)
        return
      }
      const next = await fetchMediaUrl(`/api/media/gallery/image/${current.id}`)
      if (!alive) {
        if (next) URL.revokeObjectURL(next)
        return
      }
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
      urlRef.current = next
      setUrl(next)
    })()
    return () => {
      alive = false
    }
  }, [current?.id])

  // Galeri bosken canli kare yedegi
  useEffect(() => {
    let active = true
    const tick = async () => {
      if (!active || paused || document.hidden || inFlight.current) return
      if (items.length > 0) return
      inFlight.current = true
      try {
        const next = await fetchMediaUrl(`/api/media/live/${cameraId}?t=${Date.now()}`)
        if (!active) {
          if (next) URL.revokeObjectURL(next)
          return
        }
        if (next) {
          if (liveRef.current) URL.revokeObjectURL(liveRef.current)
          liveRef.current = next
          setLiveUrl(next)
          setError('')
        } else {
          setError('Görüntü yok — video pipeline çalışıyor mu?')
        }
      } catch {
        if (active) setError('Görüntü alınamadı')
      } finally {
        inFlight.current = false
      }
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [cameraId, paused, items.length])

  useEffect(() => () => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    if (liveRef.current) URL.revokeObjectURL(liveRef.current)
  }, [])

  const go = (dir) => {
    if (items.length === 0) return
    setIndex((i) => (i + dir + items.length) % items.length)
  }

  const showUrl = url || liveUrl
  const motionLabel = current?.motion
    ? (MOTION_TR[current.motion] || current.motion)
    : null

  return (
    <section className="panel-surface overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="font-display text-base font-semibold">Canlı Önizleme</h2>
          <p className="text-xs text-[var(--muted)] mt-0.5">
            Net varlık anları · oklarla gez · asıl izleme OpenCV penceresinde
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--muted)]">{cameraId}</span>
          {items.length > 0 && (
            <span className="text-xs text-[var(--muted)] tabular-nums">
              {index + 1} / {items.length}
            </span>
          )}
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            className="px-2.5 py-1 rounded-md text-xs border border-[var(--line)] hover:bg-[var(--bg2)]"
          >
            {paused ? 'Devam' : 'Duraklat'}
          </button>
        </div>
      </div>

      <div className="live-preview-stage live-preview-stage--gallery">
        {items.length > 1 && (
          <button
            type="button"
            className="gallery-nav gallery-nav--prev"
            onClick={() => go(-1)}
            aria-label="Önceki varlık anı"
          >
            ‹
          </button>
        )}

        {showUrl ? (
          <img
            src={showUrl}
            alt={current ? `Varlık ${current.track_id}` : 'Canlı kamera'}
            className="live-preview-img"
            decoding="async"
          />
        ) : (
          <p className="text-sm text-[var(--muted)] px-4 text-center m-0">
            {error || 'Görüntü bekleniyor… Video başlatılınca net varlık anları burada birikir.'}
          </p>
        )}

        {items.length > 1 && (
          <button
            type="button"
            className="gallery-nav gallery-nav--next"
            onClick={() => go(1)}
            aria-label="Sonraki varlık anı"
          >
            ›
          </button>
        )}
      </div>

      {current && (
        <div className="px-4 py-2.5 text-xs text-[var(--muted)] border-t border-[var(--line)] flex flex-wrap gap-x-4 gap-y-1">
          <span>Varlık ID <strong className="text-[var(--text)]">{current.track_id}</strong></span>
          {motionLabel && <span>{motionLabel}</span>}
          {current.confidence != null && (
            <span>Güven {Number(current.confidence).toFixed(2)}</span>
          )}
          {current.timestamp && (
            <span>{new Date(current.timestamp * 1000).toLocaleTimeString('tr-TR')}</span>
          )}
        </div>
      )}

      {error && showUrl && (
        <p className="px-4 py-2 text-xs text-[var(--muted)] border-t border-[var(--line)]">{error}</p>
      )}
    </section>
  )
}
