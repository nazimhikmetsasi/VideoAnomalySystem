import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

/**
 * Zone haritası: zones.json içindeki yasaklı alanı,
 * kamera karesini temsil eden dikdörtgen üzerinde kırmızı poligon olarak çizer.
 * Videoyu izlemeden hangi bölgenin ihlal alanı olduğu anlaşılır.
 */
export default function ZoneMap({ cameraId = 'cam_01' }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const res = await apiFetch('/api/zones')
        if (res.ok && alive) setData(await res.json())
      } catch {
        /* yok say */
      }
    })()
    return () => { alive = false }
  }, [])

  const fw = data?.frame_width || 960
  const fh = data?.frame_height || 540
  const polygons = data?.zones?.[cameraId] || []

  return (
    <section className="panel-surface overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--line)]">
        <h2 className="font-display text-base font-semibold">Bölge Haritası</h2>
        <p className="text-xs text-[var(--muted)] mt-1">
          Yasaklı alanın kamera karesindeki konumu (zones.json)
        </p>
      </div>
      <div className="p-4">
        <svg
          viewBox={`0 0 ${fw} ${fh}`}
          className="w-full rounded-lg border border-[var(--line)] bg-[var(--bg2)]"
          role="img"
          aria-label="Yasaklı bölge şeması"
        >
          <rect x="0" y="0" width={fw} height={fh} fill="currentColor" className="text-[var(--bg0)]" opacity="0.35" />
          {polygons.map((poly, i) => (
            <polygon
              key={i}
              points={poly.map(([x, y]) => `${x},${y}`).join(' ')}
              fill="rgba(224, 86, 86, 0.28)"
              stroke="#e05656"
              strokeWidth="3"
            />
          ))}
          {!polygons.length && (
            <text x={fw / 2} y={fh / 2} textAnchor="middle" fill="currentColor" className="text-[var(--muted)]" fontSize="28">
              Bu kamera için bölge yok
            </text>
          )}
        </svg>
        <div className="mt-3 flex items-center gap-2 text-xs text-[var(--muted)]">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#e05656]/40 border border-[#e05656]" />
          Yasaklı alan
        </div>
      </div>
    </section>
  )
}
