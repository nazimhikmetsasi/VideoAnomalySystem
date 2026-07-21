import { useEffect, useMemo, useState } from 'react'
import { fetchMediaUrl } from '../media'
import { ANOMALY_LABELS, ANOMALY_BADGE, alertKey } from '../constants'

function toMs(ts) {
  if (ts == null) return 0
  if (typeof ts === 'number') return ts < 1e12 ? ts * 1000 : ts
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? 0 : d.getTime()
}

export default function SnapshotModal({
  alert,
  onClose,
  history = [],
  liveAlerts = [],
  readSet,
  onMarkRead,
  onSelectAlert,
}) {
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

  const timeline = useMemo(() => {
    if (!alert || alert.track_id == null || alert.track_id === '') return []
    const tid = String(alert.track_id)
    const merged = []
    const seen = new Set()

    const softKey = (item) => {
      const t = Math.round(toMs(item.timestamp) / 2000)
      return `${item.camera_id}|${item.track_id}|${item.anomaly_type}|${t}`
    }

    const push = (item, source) => {
      if (item == null || String(item.track_id) !== tid) return
      const hard =
        item.id != null
          ? `id:${item.id}`
          : item.snapshot_id
            ? `snap:${item.snapshot_id}`
            : alertKey(item)
      const soft = softKey(item)
      if (seen.has(hard) || seen.has(soft)) return
      seen.add(hard)
      seen.add(soft)
      merged.push({
        ...item,
        report: item.report || item.ai_generated_report,
        _source: source,
      })
    }

    for (const h of history) push(h, 'geçmiş')
    for (const a of liveAlerts) push(a, 'canlı')
    push(alert, 'seçili')

    return merged.sort((a, b) => toMs(b.timestamp) - toMs(a.timestamp)).slice(0, 12)
  }, [alert, history, liveAlerts])

  if (!alert) return null

  const currentKey = alertKey(alert)
  const isRead = readSet?.has?.(currentKey)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/55 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="panel-surface max-w-3xl w-full overflow-hidden toast-in max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Uyarı detayı"
      >
        <div className="px-5 py-4 border-b border-[var(--line)] flex items-start justify-between gap-3 shrink-0">
          <div>
            <h3 className="font-display font-semibold">
              {ANOMALY_LABELS[alert.anomaly_type] || alert.anomaly_type}
            </h3>
            <p className="text-xs text-[var(--muted)] mt-1">
              {alert.camera_id} · Varlık ID {alert.track_id}
              {isRead ? ' · Okundu' : ''}
            </p>
          </div>
          <div className="flex gap-2">
            {onMarkRead && !isRead && (
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

        <div className="overflow-y-auto flex-1 min-h-0">
          {/* Zaman çizelgesi — hemen üstte, kullanılabilir */}
          <div className="px-5 py-4 border-b border-[var(--line)] bg-[var(--bg2)]/35">
            <h4 className="font-display text-sm font-semibold mb-1">
              Zaman çizelgesi — Varlık ID {alert.track_id}
            </h4>
            <p className="text-[11px] text-[var(--muted)] mb-3">
              Bu varlığa ait önceki uyarılar. Satıra tıklayınca o kayda geçersin.
            </p>
            {timeline.length <= 1 ? (
              <p className="text-xs text-[var(--muted)] leading-relaxed">
                Bu varlık ID için şu an tek kayıt var. Aynı ID’ye yeni uyarı düşerse burada listelenir;
                satıra tıklayarak kayıtlar arasında gezebilirsin.
              </p>
            ) : null}
            {timeline.length > 0 ? (
              <ul className={`space-y-2 ${timeline.length <= 1 ? 'mt-2' : ''}`}>
                {timeline.map((h, i) => {
                  const key = alertKey(h)
                  const active =
                    (h.id != null && alert.id != null && h.id === alert.id) ||
                    (h.snapshot_id && alert.snapshot_id && h.snapshot_id === alert.snapshot_id) ||
                    key === currentKey
                  const rowRead = readSet?.has?.(key)
                  return (
                    <li key={`${key}-${i}`}>
                      <button
                        type="button"
                        onClick={() => onSelectAlert?.({
                          ...h,
                          report: h.report || h.ai_generated_report,
                        })}
                        className={`w-full flex items-center justify-between gap-3 text-xs rounded-lg border px-3 py-2.5 text-left transition ${
                          active
                            ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                            : 'border-[var(--line)] bg-[var(--bg1)] hover:bg-[var(--bg2)]'
                        } ${rowRead ? 'alert-card--read' : ''}`}
                      >
                        <span className={`px-2 py-0.5 rounded font-medium shrink-0 ${ANOMALY_BADGE[h.anomaly_type] || ''}`}>
                          {ANOMALY_LABELS[h.anomaly_type] || h.anomaly_type}
                        </span>
                        <span className="text-[var(--muted)] tabular-nums flex-1">
                          {h.timestamp ? new Date(toMs(h.timestamp)).toLocaleString('tr-TR') : '—'}
                        </span>
                        <span className="tabular-nums text-[var(--muted)] shrink-0">
                          {h.confidence_score != null ? Number(h.confidence_score).toFixed(2) : '—'}
                        </span>
                        {rowRead && <span className="alert-read-pill shrink-0">Okundu</span>}
                      </button>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="text-xs text-[var(--muted)]">
                Bu varlık ID için geçmiş veya canlı listede kayıt bulunamadı.
              </p>
            )}
          </div>

          <div className="bg-black/30 min-h-[140px] flex items-center justify-center">
            {url ? (
              <img src={url} alt="Anlık görüntü" className="max-h-[40vh] w-full object-contain" />
            ) : (
              <p className="text-sm text-[var(--muted)] p-6 text-center">
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
        </div>
      </div>
    </div>
  )
}
