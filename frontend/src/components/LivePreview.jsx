import { useEffect, useState, useRef } from 'react'
import { fetchMediaUrl } from '../media'

/** Panel canli onizleme — OpenCV penceresinin dusuk frekansli kopyasi. */
export default function LivePreview({ cameraId = 'cam_01' }) {
  const [url, setUrl] = useState(null)
  const [error, setError] = useState('')
  const [paused, setPaused] = useState(false)
  const inFlight = useRef(false)

  useEffect(() => {
    let active = true
    let current = null

    const tick = async () => {
      if (!active || paused || document.hidden || inFlight.current) return
      inFlight.current = true
      try {
        const next = await fetchMediaUrl(`/api/media/live/${cameraId}?t=${Date.now()}`)
        if (!active) {
          if (next) URL.revokeObjectURL(next)
          return
        }
        if (next) {
          if (current) URL.revokeObjectURL(current)
          current = next
          setUrl(next)
          setError('')
        } else {
          setError('Canlı kare yok — video pipeline çalışıyor mu?')
        }
      } catch {
        if (active) setError('Canlı görüntü alınamadı')
      } finally {
        inFlight.current = false
      }
    }

    tick()
    const id = setInterval(tick, 1500)
    const onVis = () => {
      if (!document.hidden) tick()
    }
    document.addEventListener('visibilitychange', onVis)

    return () => {
      active = false
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVis)
      if (current) URL.revokeObjectURL(current)
    }
  }, [cameraId, paused])

  return (
    <section className="panel-surface overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="font-display text-base font-semibold">Canlı Önizleme</h2>
          <p className="text-xs text-[var(--muted)] mt-0.5">
            Canlı panel görüntüsü · asıl izleme OpenCV penceresinde
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--muted)]">{cameraId}</span>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            className="px-2.5 py-1 rounded-md text-xs border border-[var(--line)] hover:bg-[var(--bg2)]"
          >
            {paused ? 'Devam' : 'Duraklat'}
          </button>
        </div>
      </div>

      <div className="live-preview-stage">
        {url ? (
          <img src={url} alt="Canlı kamera" className="live-preview-img" decoding="async" />
        ) : (
          <p className="text-sm text-[var(--muted)] px-4 text-center m-0">
            {error || 'Görüntü bekleniyor…'}
          </p>
        )}
      </div>

      {error && url && (
        <p className="px-4 py-2 text-xs text-[var(--muted)] border-t border-[var(--line)]">{error}</p>
      )}
    </section>
  )
}
