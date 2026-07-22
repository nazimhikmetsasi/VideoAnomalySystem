import { useEffect, useState } from 'react'
import { ANOMALY_LABELS, ANOMALY_TYPES, DATE_RANGES, exportAlertsCsv } from '../constants'

export default function AlertFilters({ filters, onChange, cameras, exportRows }) {
  const [qDraft, setQDraft] = useState(filters.q || '')

  useEffect(() => {
    setQDraft(filters.q || '')
  }, [filters.q])

  const patch = (partial) => {
    onChange((prev) => ({ ...prev, ...partial }))
  }

  const applySearch = () => {
    patch({ q: qDraft.trim() })
  }

  const clear = () => {
    setQDraft('')
    onChange({ q: '', type: '', camera: '', date: '', range: '' })
  }

  const hasFilter = filters.q || filters.type || filters.camera || filters.date || filters.range || qDraft

  return (
    <section className="panel-surface p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 items-end">
        <label className="block text-xs text-[var(--muted)] sm:col-span-2 lg:col-span-2">
          Arama
          <div className="mt-1.5 flex gap-2">
            <input
              type="search"
              value={qDraft}
              onChange={(e) => setQDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  applySearch()
                }
              }}
              placeholder="Rapor, Varlık ID, kamera…"
              className="w-full min-w-0 px-3 py-2 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
            />
            <button
              type="button"
              onClick={applySearch}
              className="shrink-0 px-3.5 py-2 rounded-lg text-sm font-semibold bg-[var(--accent)] text-[#04120f] hover:brightness-110 transition"
            >
              Ara
            </button>
          </div>
        </label>
        <label className="block text-xs text-[var(--muted)]">
          Tip
          <select
            value={filters.type}
            onChange={(e) => patch({ type: e.target.value })}
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
          >
            {ANOMALY_TYPES.map((t) => (
              <option key={t.value || 'all'} value={t.value}>{t.label}</option>
            ))}
          </select>
        </label>
        <label className="block text-xs text-[var(--muted)]">
          Kamera
          <select
            value={filters.camera}
            onChange={(e) => patch({ camera: e.target.value })}
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
          >
            <option value="">Tüm kameralar</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>{c.name || c.id}</option>
            ))}
          </select>
        </label>
        <label className="block text-xs text-[var(--muted)]">
          Dönem
          <select
            value={filters.range}
            onChange={(e) => patch({ range: e.target.value })}
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
          >
            {DATE_RANGES.map((t) => (
              <option key={t.value || 'all'} value={t.value}>{t.label}</option>
            ))}
          </select>
        </label>
        <label className="block text-xs text-[var(--muted)]">
          Tarih (gün)
          <input
            type="date"
            value={filters.date}
            onChange={(e) => patch({ date: e.target.value })}
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
          />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {hasFilter && (
          <button type="button" onClick={clear} className="text-xs text-[var(--accent)] hover:underline">
            Filtreleri temizle
          </button>
        )}
        {filters.q ? (
          <span className="text-xs text-[var(--muted)]">
            Arama: “{filters.q}” · {(exportRows || []).length} sonuç
          </span>
        ) : null}
        <button
          type="button"
          onClick={() => exportAlertsCsv(exportRows || [])}
          className="ml-auto px-3 py-1.5 rounded-md text-xs font-medium border border-[var(--line)] hover:bg-[var(--bg2)]"
        >
          CSV indir ({(exportRows || []).length})
        </button>
      </div>
    </section>
  )
}

function startOfToday() {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}

function startOfWeek() {
  const d = startOfToday()
  const day = d.getDay()
  const diff = day === 0 ? 6 : day - 1
  d.setDate(d.getDate() - diff)
  return d
}

export function matchFilters(item, filters) {
  if (filters.type && item.anomaly_type !== filters.type) return false
  if (filters.camera && item.camera_id !== filters.camera) return false

  const rawTs = item.timestamp
  const d = new Date(typeof rawTs === 'number' && rawTs < 1e12 ? rawTs * 1000 : rawTs)

  if (filters.date) {
    const iso = Number.isNaN(d.getTime()) ? '' : d.toISOString().slice(0, 10)
    if (iso !== filters.date) return false
  }

  if (filters.range === 'today') {
    if (Number.isNaN(d.getTime()) || d < startOfToday()) return false
  }
  if (filters.range === 'week') {
    if (Number.isNaN(d.getTime()) || d < startOfWeek()) return false
  }

  if (filters.q) {
    const q = String(filters.q).toLowerCase().trim()
    if (!q) return true

    const track = String(item.track_id ?? '').toLowerCase()
    const report = String(item.report || item.ai_generated_report || '').toLowerCase()
    const cam = String(item.camera_id || '').toLowerCase()
    const tip = String(ANOMALY_LABELS[item.anomaly_type] || item.anomaly_type || '').toLowerCase()

    // Sadece rakam: tam Varlık ID eşleşmesi (1 → 11 gelmesin)
    if (/^\d+$/.test(q)) {
      return track === q
    }

    return (
      track.includes(q) ||
      report.includes(q) ||
      cam.includes(q) ||
      tip.includes(q)
    )
  }
  return true
}
