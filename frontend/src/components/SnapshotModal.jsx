import { useEffect, useState } from 'react'
import { fetchMediaUrl } from '../media'
import { ANOMALY_LABELS, ANOMALY_BADGE } from '../constants'

export default function SnapshotModal({ alert, onClose, history = [], onMarkRead }) {
  const [url, setUrl] = useState(null)

  useEffect(() => {
    let revoked = null
    let alive = true
    setUrl(null)
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

  const timeline = (history || [])
    .filter((h) =>
      String(h.track_id) === String(alert.track_id)
      && h.camera_id === alert.camera_id
    )
    .slice(0, 8)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/55 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="panel-surface max-w-3xl w-full overflow-hidden toast-in max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Uyarı detayı"
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
          <div className="flex gap-2">
            {onMarkRead && (
              <button
                type="button"
                onClick={() => onMarkRead(alert)}
                className="px-3 py-1.5 text-sm rounded-md border border-[var(--line)] hover:bg-[var(--bg2)]"
              >
                Okundu
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-sm rounded-md border border-[var(--line)] hover:bg-[var(--bg2)]"
            >
              Kapat
            </button>
          </div>
        </div>

        <div className="bg-black/30 min-h-[160px] flex items-center justify-center">
          {url ? (
            <img src={url} alt="Anlık görüntü" className="max-h-[50vh] w-full object-contain" />
          ) : (
            <p className="text-sm text-[var(--muted)] p-8 text-center">
              {alert.snapshot_id
                ? 'Görüntü yükleniyor…'
                : 'Bu uyarı için kayıtlı anlık görüntü yok.'}
            </p>
          )}
        </div>

        {(alert.report || alert.ai_generated_report) && (
          <p className="px-5 py-4 text-sm text-[var(--muted)] border-t border-[var(--line)] leading-relaxed">
            {alert.report || alert.ai_generated_report}
          </p>
        )}

        <div className="px-5 py-4 border-t border-[var(--line)]">
          <h4 className="font-display text-sm font-semibold mb-3">
            Aynı varlık — zaman çizelgesi
          </h4>
          {timeline.length === 0 ? (
            <p className="text-xs text-[var(--muted)]">Bu varlık için başka kayıt yok.</p>
          ) : (
            <ul className="space-y-2">
              {timeline.map((h, i) => (
                <li
                  key={h.id || i}
                  className="flex items-center justify-between gap-3 text-xs rounded-lg border border-[var(--line)] bg-[var(--bg2)]/50 px-3 py-2"
                >
                  <span className={`px-2 py-0.5 rounded font-medium ${ANOMALY_BADGE[h.anomaly_type] || ''}`}>
                    {ANOMALY_LABELS[h.anomaly_type] || h.anomaly_type}
                  </span>
                  <span className="text-[var(--muted)] tabular-nums">
                    {h.timestamp ? new Date(h.timestamp).toLocaleString('tr-TR') : '—'}
                  </span>
                  <span className="tabular-nums text-[var(--muted)]">
                    {h.confidence_score != null ? Number(h.confidence_score).toFixed(2) : '—'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
