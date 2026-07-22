import { ANOMALY_LABELS } from '../constants'

function isToday(ts) {
  const d = new Date(typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts)
  if (Number.isNaN(d.getTime())) return false
  const now = new Date()
  return d.toDateString() === now.toDateString()
}

export default function StatsSummary({ history }) {
  const today = (history || []).filter((h) => isToday(h.timestamp))
  const byType = {}
  for (const h of today) {
    byType[h.anomaly_type] = (byType[h.anomaly_type] || 0) + 1
  }
  const entries = Object.entries(byType).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...entries.map(([, n]) => n))

  // Pasta için açı
  let angle = 0
  const colors = {
    RUN_ZONE: '#e8a54b',
    RUN: '#d4923a',
    ZONE_VIOLATION: '#3d9a8b',
    FALL: '#e05656',
    PERSON_ENTERED: '#38bdf8',
  }
  const slices = entries.map(([type, n]) => {
    const sweep = (n / Math.max(today.length, 1)) * 360
    const start = angle
    angle += sweep
    return { type, n, start, sweep, color: colors[type] || '#6b7c8f' }
  })

  function polar(cx, cy, r, deg) {
    const rad = ((deg - 90) * Math.PI) / 180
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)]
  }

  function arcPath(cx, cy, r, startDeg, sweepDeg) {
    if (sweepDeg >= 359.9) {
      return `M ${cx} ${cy - r} A ${r} ${r} 0 1 1 ${cx - 0.01} ${cy - r} Z`
    }
    const [x1, y1] = polar(cx, cy, r, startDeg)
    const [x2, y2] = polar(cx, cy, r, startDeg + sweepDeg)
    const large = sweepDeg > 180 ? 1 : 0
    return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`
  }

  return (
    <section className="panel-surface overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between">
        <h2 className="font-display text-base font-semibold">Bugünkü Özet</h2>
        <span className="text-sm font-semibold tabular-nums text-[var(--accent)]">
          {today.length} uyarı
        </span>
      </div>
      <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
        <div className="flex justify-center">
          {today.length === 0 ? (
            <p className="text-sm text-[var(--muted)] py-8">Bugün henüz uyarı yok.</p>
          ) : (
            <svg viewBox="0 0 120 120" className="w-36 h-36" aria-label="Tip dağılımı">
              {slices.map((s) => (
                <path
                  key={s.type}
                  d={arcPath(60, 60, 52, s.start, s.sweep)}
                  fill={s.color}
                  opacity="0.9"
                />
              ))}
              <circle cx="60" cy="60" r="28" fill="var(--bg1)" />
              <text x="60" y="64" textAnchor="middle" fill="var(--text)" fontSize="14" fontWeight="600">
                {today.length}
              </text>
            </svg>
          )}
        </div>
        <div className="space-y-2.5">
          {entries.length === 0 && (
            <p className="text-sm text-[var(--muted)]">Dağılım için veri yok.</p>
          )}
          {entries.map(([type, n]) => (
            <div key={type}>
              <div className="flex justify-between text-xs mb-1">
                <span>{ANOMALY_LABELS[type] || type}</span>
                <span className="tabular-nums text-[var(--muted)]">{n}</span>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--chart-track)' }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${(n / max) * 100}%`,
                    background: colors[type] || '#6b7c8f',
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
