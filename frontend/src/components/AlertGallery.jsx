import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { apiFetch } from '../api'
import { fetchMediaUrl } from '../media'
import { ANOMALY_LABELS } from '../constants'

function formatTs(ts) {
  if (ts == null) return '—'
  const ms = typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts
  const d = new Date(ms)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('tr-TR')
}

function AlbumThumb({ snapshotId, selected, onToggle }) {
  const [src, setSrc] = useState(null)

  useEffect(() => {
    let alive = true
    let url = null
    ;(async () => {
      url = await fetchMediaUrl(`/api/media/snapshot/${snapshotId}`)
      if (!alive) {
        if (url) URL.revokeObjectURL(url)
        return
      }
      setSrc(url)
    })()
    return () => {
      alive = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [snapshotId])

  return (
    <button
      type="button"
      onClick={() => onToggle(snapshotId)}
      className={`album-thumb ${selected ? 'album-thumb--selected' : ''}`}
      aria-pressed={selected}
      title="Seçmek için tıkla"
    >
      {src ? (
        <img src={src} alt="" className="album-thumb__img" decoding="async" />
      ) : (
        <span className="album-thumb__placeholder">…</span>
      )}
      <span className={`album-thumb__check ${selected ? 'is-on' : ''}`} aria-hidden="true" />
    </button>
  )
}

/**
 * Bildirim anı görüntüleri + albüm (seç / sil).
 */
export default function AlertGallery({ cameraId = 'cam_01', refreshKey = 0, liveAlerts = [] }) {
  const [items, setItems] = useState([])
  const [index, setIndex] = useState(0)
  const [url, setUrl] = useState(null)
  const [status, setStatus] = useState('')
  const [albumOpen, setAlbumOpen] = useState(false)
  const [selected, setSelected] = useState(() => new Set())
  const [deleting, setDeleting] = useState(false)
  const urlRef = useRef(null)

  const current = items[index] || null
  const selectedCount = selected.size
  const allSelected = items.length > 0 && items.every((it) => selected.has(String(it.id || it.snapshot_id)))

  const mergeLive = useCallback((list) => {
    const byId = new Map()
    for (const it of list) {
      const id = it.snapshot_id || it.id
      if (id) byId.set(String(id), { ...it, id, snapshot_id: id })
    }
    for (const a of liveAlerts) {
      if (!a?.snapshot_id) continue
      if (cameraId && a.camera_id && a.camera_id !== cameraId) continue
      const id = String(a.snapshot_id)
      if (byId.has(id)) continue
      byId.set(id, {
        id,
        snapshot_id: id,
        camera_id: a.camera_id,
        track_id: a.track_id,
        timestamp: a.timestamp,
        anomaly_type: a.anomaly_type,
        confidence_score: a.confidence_score,
        report: a.report,
      })
    }
    return [...byId.values()].sort((a, b) => {
      const ta = typeof a.timestamp === 'number' ? a.timestamp : new Date(a.timestamp || 0).getTime() / 1000
      const tb = typeof b.timestamp === 'number' ? b.timestamp : new Date(b.timestamp || 0).getTime() / 1000
      return tb - ta
    })
  }, [liveAlerts, cameraId])

  const load = useCallback(async () => {
    try {
      const q = cameraId
        ? `?camera_id=${encodeURIComponent(cameraId)}&limit=80`
        : '?limit=80'
      let res = await apiFetch(`/api/media/alert-snapshots${q}`)
      if (res.status === 404) {
        setStatus('API eski sürüm — run_api.bat ile API’yi yeniden başlat.')
        setItems(mergeLive([]))
        return
      }
      if (!res.ok) {
        res = await apiFetch('/api/media/alert-snapshots?limit=80')
      }
      if (!res.ok) {
        setStatus('Alarm görüntüleri alınamadı.')
        setItems(mergeLive([]))
        return
      }
      const data = await res.json()
      let next = data.items || []
      if (next.length === 0 && cameraId) {
        const all = await apiFetch('/api/media/alert-snapshots?limit=80')
        if (all.ok) {
          const d2 = await all.json()
          next = d2.items || []
        }
      }
      next = mergeLive(next)
      setItems((prev) => {
        const newer = next.length > 0 && (!prev.length || next[0]?.id !== prev[0]?.id)
        if (newer) queueMicrotask(() => setIndex(0))
        return next
      })
      setSelected((prev) => {
        const valid = new Set(next.map((it) => String(it.id || it.snapshot_id)))
        return new Set([...prev].filter((id) => valid.has(id)))
      })
      setStatus(next.length ? '' : 'Henüz kayıtlı alarm görüntüsü yok.')
    } catch {
      setStatus('Bağlantı hatası — API çalışıyor mu?')
      setItems(mergeLive([]))
    }
  }, [cameraId, mergeLive])

  useEffect(() => {
    load()
    const id = setInterval(load, 2500)
    return () => clearInterval(id)
  }, [load, refreshKey])

  useEffect(() => {
    if (items.length === 0) {
      setIndex(0)
      return
    }
    if (index >= items.length) setIndex(items.length - 1)
  }, [items, index])

  useEffect(() => {
    let alive = true
    ;(async () => {
      if (!current?.snapshot_id && !current?.id) {
        if (urlRef.current) {
          URL.revokeObjectURL(urlRef.current)
          urlRef.current = null
        }
        setUrl(null)
        return
      }
      const sid = current.snapshot_id || current.id
      const next = await fetchMediaUrl(`/api/media/snapshot/${sid}`)
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
  }, [current?.id, current?.snapshot_id])

  useEffect(() => () => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current)
  }, [])

  const go = (dir) => {
    if (items.length === 0) return
    setIndex((i) => (i + dir + items.length) % items.length)
  }

  const toggleSelect = (id) => {
    const key = String(id)
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const selectAll = () => {
    setSelected(new Set(items.map((it) => String(it.id || it.snapshot_id))))
  }

  const clearSelection = () => setSelected(new Set())

  const deleteSelected = async () => {
    const ids = [...selected]
    if (!ids.length) return
    if (!window.confirm(`${ids.length} görüntü silinsin mi?`)) return
    setDeleting(true)
    try {
      const res = await apiFetch('/api/media/alert-snapshots', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids }),
      })
      if (!res.ok) {
        setStatus('Silme başarısız — API’yi yeniden başlatmayı dene.')
        return
      }
      clearSelection()
      await load()
    } catch {
      setStatus('Silme sırasında bağlantı hatası.')
    } finally {
      setDeleting(false)
    }
  }

  const btnTiny = 'px-2.5 py-1 text-[11px] rounded-md border border-[var(--line)] hover:bg-[var(--bg2)] disabled:opacity-40 disabled:cursor-not-allowed'
  const btnAccent = 'px-2.5 py-1 text-[11px] rounded-md border border-[var(--accent)]/40 bg-[var(--accent)]/15 text-[var(--accent)] hover:bg-[var(--accent)]/25 disabled:opacity-40'

  const metaLine = useMemo(() => {
    if (!current) return null
    return (
      <>
        {current.anomaly_type && (
          <span className="text-[var(--text)] font-medium">
            {ANOMALY_LABELS[current.anomaly_type] || current.anomaly_type}
          </span>
        )}
        <span>
          Varlık ID <strong className="text-[var(--text)]">{current.track_id ?? '—'}</strong>
        </span>
        {current.camera_id && <span>{current.camera_id}</span>}
        {current.confidence_score != null && (
          <span>Güven {Number(current.confidence_score).toFixed(2)}</span>
        )}
        <span>{formatTs(current.timestamp)}</span>
      </>
    )
  }, [current])

  return (
    <section className="panel-surface overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="font-display text-base font-semibold">Alarm Anlık Görüntüleri</h2>
          <p className="text-xs text-[var(--muted)] mt-0.5">
            Bildirim düştüğü anda · ne girdi, neden öttü · oklarla gez
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {items.length > 0 && (
            <span className="text-xs text-[var(--muted)] tabular-nums">
              {index + 1} / {items.length}
            </span>
          )}
          <button
            type="button"
            className={btnAccent}
            disabled={items.length === 0}
            onClick={() => setAlbumOpen(true)}
          >
            Albüm
          </button>
        </div>
      </div>

      <div className="live-preview-stage live-preview-stage--gallery">
        {items.length > 1 && (
          <button
            type="button"
            className="gallery-nav gallery-nav--prev"
            onClick={() => go(-1)}
            aria-label="Önceki alarm görüntüsü"
          >
            ‹
          </button>
        )}

        {url ? (
          <img
            src={url}
            alt={current ? `Alarm varlık ${current.track_id}` : 'Alarm anı'}
            className="live-preview-img"
            decoding="async"
          />
        ) : (
          <p className="text-sm text-[var(--muted)] px-4 text-center m-0">
            {status || 'Henüz alarm görüntüsü yok. Varlık girip uyarı düşünce burada birikir.'}
          </p>
        )}

        {items.length > 1 && (
          <button
            type="button"
            className="gallery-nav gallery-nav--next"
            onClick={() => go(1)}
            aria-label="Sonraki alarm görüntüsü"
          >
            ›
          </button>
        )}
      </div>

      {current && (
        <div className="px-4 py-2.5 text-xs text-[var(--muted)] border-t border-[var(--line)] flex flex-wrap gap-x-4 gap-y-1">
          {metaLine}
        </div>
      )}

      {albumOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/55 backdrop-blur-sm"
          onClick={() => setAlbumOpen(false)}
          role="presentation"
        >
          <div
            className="panel-surface w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden toast-in"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Alarm albümü"
          >
            <div className="px-5 py-4 border-b border-[var(--line)] flex items-start justify-between gap-3 flex-wrap shrink-0">
              <div>
                <h3 className="font-display font-semibold">Alarm Albümü</h3>
                <p className="text-xs text-[var(--muted)] mt-1">
                  Fotoğrafa tıklayarak seç · {items.length} görüntü
                  {selectedCount > 0 ? ` · ${selectedCount} seçili` : ''}
                </p>
              </div>
              <button
                type="button"
                className={btnTiny}
                onClick={() => setAlbumOpen(false)}
              >
                Kapat
              </button>
            </div>

            <div className="px-5 py-3 border-b border-[var(--line)] flex items-center gap-2 flex-wrap shrink-0 bg-[var(--bg2)]/30">
              <label className="inline-flex items-center gap-2 text-xs text-[var(--muted)] cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="alert-check"
                  checked={allSelected}
                  disabled={items.length === 0}
                  onChange={() => {
                    if (allSelected) clearSelection()
                    else selectAll()
                  }}
                />
                Tümünü seç
              </label>
              <button type="button" className={btnTiny} disabled={selectedCount === 0} onClick={clearSelection}>
                Seçimi kaldır
              </button>
              <button
                type="button"
                className={btnTiny}
                disabled={selectedCount === 0 || deleting}
                onClick={deleteSelected}
              >
                {deleting ? 'Siliniyor…' : `Seçilenleri sil${selectedCount ? ` (${selectedCount})` : ''}`}
              </button>
            </div>

            <div className="overflow-y-auto p-4 flex-1 min-h-0">
              {items.length === 0 ? (
                <p className="text-sm text-[var(--muted)] text-center py-10">Albüm boş.</p>
              ) : (
                <div className="album-grid">
                  {items.map((it) => {
                    const id = String(it.id || it.snapshot_id)
                    return (
                      <div key={id} className="album-cell">
                        <AlbumThumb
                          snapshotId={id}
                          selected={selected.has(id)}
                          onToggle={toggleSelect}
                        />
                        <div className="album-cell__meta">
                          <span className="truncate">
                            {ANOMALY_LABELS[it.anomaly_type] || it.anomaly_type || 'Alarm'}
                          </span>
                          <span className="opacity-70">ID {it.track_id ?? '—'}</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
