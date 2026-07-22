import { useMemo } from 'react'
import { ANOMALY_LABELS } from '../constants'
import { getTodayItems } from '../reportUtils'

function parseTs(ts) {
  if (ts == null) return null
  const d = new Date(typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts)
  return Number.isNaN(d.getTime()) ? null : d
}

function timeOfDayHours(d) {
  return d.getHours() + d.getMinutes() / 60 + d.getSeconds() / 3600
}

/** Bugünkü uyarılar — gerçek saate göre nokta + kronolojik liste. */
export default function HourlyTrend({ history }) {
  const { events, total } = useMemo(() => {
    const today = getTodayItems(history)
      .map((h) => {
        const d = parseTs(h.timestamp)
        if (!d) return null
        return {
          ...h,
          _date: d,
          _tod: timeOfDayHours(d),
          _label: d.toLocaleTimeString('tr-TR', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          }),
        }
      })
      .filter(Boolean)
      .sort((a, b) => a._tod - b._tod || a._date - b._date)

    return { events: today, total: today.length }
  }, [history])

  const chart = useMemo(() => {
    const W = 960
    const H = 240
    const pad = { top: 28, right: 20, bottom: 36, left: 40 }
    const innerW = W - pad.left - pad.right
    const innerH = H - pad.top - pad.bottom

    // X: veri varsa uyarı saatlerine göre daralt (en az 1 saat pay)
    let xMin = 0
    let xMax = 24
    if (events.length) {
      const t0 = events[0]._tod
      const t1 = events[events.length - 1]._tod
      xMin = Math.max(0, Math.floor(t0) - 1)
      xMax = Math.min(24, Math.ceil(t1) + 1)
      if (xMax - xMin < 3) {
        xMin = Math.max(0, Math.floor(t0) - 1)
        xMax = Math.min(24, xMin + 3)
      }
    }
    const xSpan = Math.max(xMax - xMin, 1)

    // Aynı saniyeye düşenleri dikey ayır
    const slotCount = {}
    const points = events.map((e, idx) => {
      const key = e._date.toISOString().slice(0, 19)
      const stack = slotCount[key] || 0
      slotCount[key] = stack + 1
      const x = pad.left + ((e._tod - xMin) / xSpan) * innerW
      // Y: olay sırası (1…n) — iki uyarı yan yana / üst üste ayrı görünür
      const yVal = idx + 1
      return { ...e, x, yVal, stack }
    })

    const yMax = Math.max(1, points.length)
    const yTicks = []
    const yStep = Math.max(1, Math.ceil(yMax / 4))
    for (let v = 0; v <= yMax; v += yStep) yTicks.push(v)
    if (yTicks[yTicks.length - 1] !== yMax) yTicks.push(yMax)

    const toY = (v) => pad.top + innerH - (v / yMax) * innerH

    // Kümülatif çizgi (doğrusal — 0 altına inmez)
    const linePts = points.map((p, i) => ({
      x: p.x,
      y: toY(i + 1),
    }))
    let line = ''
    if (linePts.length === 1) {
      line = `M ${linePts[0].x} ${toY(0)} L ${linePts[0].x} ${linePts[0].y}`
    } else if (linePts.length > 1) {
      line = `M ${linePts[0].x} ${linePts[0].y}`
      for (let i = 1; i < linePts.length; i++) {
        line += ` L ${linePts[i].x} ${linePts[i].y}`
      }
    }

    const baseY = toY(0)
    const area =
      linePts.length > 0
        ? `${line} L ${linePts[linePts.length - 1].x} ${baseY} L ${linePts[0].x} ${baseY} Z`
        : ''

    // X etiketleri: düz saat sayıları (yalnızca görünür aralık)
    const xLabels = []
    for (let h = Math.ceil(xMin); h <= Math.floor(xMax); h++) {
      if (h < 0 || h > 23) continue
      xLabels.push({
        hour: h,
        x: pad.left + ((h - xMin) / xSpan) * innerW,
      })
    }

    return {
      W,
      H,
      pad,
      innerW,
      innerH,
      yMax,
      yTicks,
      toY,
      points,
      line,
      area,
      baseY,
      xLabels,
      xMin,
      xMax,
    }
  }, [events])

  return (
    <section className="neo-card overflow-hidden">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
        <div>
          <h2 className="neo-card__title" style={{ color: 'var(--neo-lime)' }}>
            Saatlik trend
          </h2>
          <p className="text-xs text-[var(--muted)] mt-1">
            Bugün · {total} olay · gerçek saate göre
          </p>
        </div>
      </div>

      {total === 0 ? (
        <p className="text-sm text-[var(--muted)] py-8 text-center">
          Bugün henüz saatlik veri yok.
        </p>
      ) : (
        <>
          <div className="overflow-x-auto -mx-1 px-1">
            <svg
              viewBox={`0 0 ${chart.W} ${chart.H}`}
              className="w-full min-w-[640px] h-auto"
              role="img"
              aria-label="Uyarıların saate göre dağılımı"
            >
              <defs>
                <linearGradient id="hourlyFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--neo-lime)" stopOpacity="0.28" />
                  <stop offset="100%" stopColor="var(--neo-lime)" stopOpacity="0.02" />
                </linearGradient>
              </defs>

              {chart.yTicks.map((v) => {
                const y = chart.toY(v)
                return (
                  <g key={`y-${v}`}>
                    <line
                      x1={chart.pad.left}
                      x2={chart.pad.left + chart.innerW}
                      y1={y}
                      y2={y}
                      stroke="var(--line)"
                      strokeWidth="1"
                    />
                    <text
                      x={chart.pad.left - 8}
                      y={y + 3}
                      textAnchor="end"
                      fill="var(--muted)"
                      fontSize="10"
                    >
                      {v}
                    </text>
                  </g>
                )
              })}

              {chart.xLabels.map(({ hour, x }) => (
                <line
                  key={`vx-${hour}`}
                  x1={x}
                  x2={x}
                  y1={chart.pad.top}
                  y2={chart.pad.top + chart.innerH}
                  stroke="var(--line)"
                  strokeWidth="1"
                  opacity="0.5"
                />
              ))}

              {chart.area && <path d={chart.area} fill="url(#hourlyFill)" />}
              {chart.line && (
                <path
                  d={chart.line}
                  fill="none"
                  stroke="var(--neo-lime)"
                  strokeWidth="2.5"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              )}

              {chart.points.map((p, i) => (
                <g key={`pt-${p.id ?? i}-${p._label}`}>
                  <line
                    x1={p.x}
                    x2={p.x}
                    y1={chart.baseY}
                    y2={chart.toY(i + 1)}
                    stroke="var(--neo-lime)"
                    strokeWidth="1"
                    opacity="0.35"
                  />
                  <circle
                    cx={p.x}
                    cy={chart.toY(i + 1)}
                    r="5"
                    fill="var(--neo-card)"
                    stroke="var(--neo-lime)"
                    strokeWidth="2"
                  >
                    <title>
                      {`${p._label} · ${ANOMALY_LABELS[p.anomaly_type] || p.anomaly_type} · ID ${p.track_id}`}
                    </title>
                  </circle>
                </g>
              ))}

              {chart.xLabels.map(({ hour, x }) => (
                <text
                  key={`xl-${hour}`}
                  x={x}
                  y={chart.H - 12}
                  textAnchor="middle"
                  fill="var(--muted)"
                  fontSize="11"
                  fontWeight="500"
                >
                  {hour}
                </text>
              ))}
            </svg>
          </div>

          <div className="mt-4 border-t border-[var(--line)] pt-3">
            <p className="text-xs text-[var(--muted)] mb-2">Saate göre uyarılar</p>
            <ul className="max-h-40 overflow-auto space-y-1.5">
              {events.map((e, i) => (
                <li
                  key={`row-${e.id ?? i}-${e._label}`}
                  className="flex items-center gap-3 text-sm px-2 py-1.5 rounded-lg bg-[var(--bg0)]/35"
                >
                  <span className="tabular-nums text-[var(--neo-lime)] font-semibold w-20 shrink-0">
                    {e._label}
                  </span>
                  <span className="text-[var(--text)] truncate">
                    {ANOMALY_LABELS[e.anomaly_type] || e.anomaly_type}
                  </span>
                  <span className="text-xs text-[var(--muted)] ml-auto shrink-0">
                    {e.camera_id} · ID {e.track_id}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </section>
  )
}
