import { ANOMALY_LABELS, ANOMALY_TYPES } from '../constants'

export default function AlertFilters({ filters, onChange, cameras }) {
  const set = (key, value) => onChange({ ...filters, [key]: value })

  return (
    <section className="panel-surface p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <label className="block text-xs text-[var(--muted)]">
          Arama
          <input
            type="search"
            value={filters.q}
            onChange={(e) => set('q', e.target.value)}
            placeholder="Rapor, ID, kamera…"
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
          />
        </label>
        <label className="block text-xs text-[var(--muted)]">
          Tip
          <select
            value={filters.type}
            onChange={(e) => set('type', e.target.value)}
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
            onChange={(e) => set('camera', e.target.value)}
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
          >
            <option value="">Tüm kameralar</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>{c.name || c.id}</option>
            ))}
          </select>
        </label>
        <label className="block text-xs text-[var(--muted)]">
          Tarih
          <input
            type="date"
            value={filters.date}
            onChange={(e) => set('date', e.target.value)}
            className="mt-1.5 w-full px-3 py-2 rounded-lg bg-[var(--bg2)] border border-[var(--line)] text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
          />
        </label>
      </div>
      {(filters.q || filters.type || filters.camera || filters.date) && (
        <button
          type="button"
          onClick={() => onChange({ q: '', type: '', camera: '', date: '' })}
          className="mt-3 text-xs text-[var(--accent)] hover:underline"
        >
          Filtreleri temizle
        </button>
      )}
    </section>
  )
}

export function matchFilters(item, filters) {
  if (filters.type && item.anomaly_type !== filters.type) return false
  if (filters.camera && item.camera_id !== filters.camera) return false
  if (filters.date) {
    const d = new Date(item.timestamp || 0)
    const iso = Number.isNaN(d.getTime()) ? '' : d.toISOString().slice(0, 10)
    if (iso !== filters.date) return false
  }
  if (filters.q) {
    const q = filters.q.toLowerCase()
    const hay = [
      item.report,
      item.ai_generated_report,
      item.camera_id,
      String(item.track_id),
      ANOMALY_LABELS[item.anomaly_type] || item.anomaly_type,
    ].join(' ').toLowerCase()
    if (!hay.includes(q)) return false
  }
  return true
}
