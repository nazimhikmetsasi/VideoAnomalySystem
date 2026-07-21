import { useEffect, useState } from 'react'
import { fetchMediaUrl } from '../media'
import { ANOMALY_LABELS } from '../constants'

export default function SnapshotModal({ alert, onClose }) {
  const [url, setUrl] = useState(null)

  useEffect(() => {
    let revoked = null
    let alive = true
    ;(async () => {
      if (!alert?.snapshot_id) return
      const u = await fetchMediaUrl(`/api/media/snapshot/${alert.snapshot_id}`)
      if (!alive) {
        if (u) URL.revokeObjectURL(u)
        return
      }
      revoked = u
      setUrl(u)
    })()
    return () => {
      alive = false
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [alert])

  if (!alert) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/55 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="panel-surface max-w-3xl w-full overflow-hidden toast-in"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Uyarı anlık görüntüsü"
      >
        <div className="px-5 py-4 border-b border-[var(--line)] flex items-start justify-between gap-3">
          <div>
            <h3 className="font-display font-semibold">
              {ANOMALY_LABELS[alert.anomaly_type] || alert.anomaly_type}
            </h3>
            <p className="text-xs text-[var(--muted)] mt-1">
              {alert.camera_id} · Varlık {alert.track_id}
              {alert.snapshot_id ? '' : ' · Anlık görüntü yok'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded-md border border-[var(--line)] hover:bg-[var(--bg2)]"
          >
            Kapat
          </button>
        </div>
        <div className="bg-black/30 min-h-[200px] flex items-center justify-center">
          {url ? (
            <img src={url} alt="Anlık görüntü" className="max-h-[70vh] w-full object-contain" />
          ) : (
            <p className="text-sm text-[var(--muted)] p-8 text-center">
              {alert.snapshot_id
                ? 'Görüntü yükleniyor…'
                : 'Bu uyarı için kayıtlı anlık görüntü yok. Yeni uyarılar video çalışırken kaydedilir.'}
            </p>
          )}
        </div>
        {alert.report && (
          <p className="px-5 py-4 text-sm text-[var(--muted)] border-t border-[var(--line)] leading-relaxed">
            {alert.report}
          </p>
        )}
      </div>
    </div>
  )
}
