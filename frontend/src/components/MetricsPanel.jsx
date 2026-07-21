import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

export default function MetricsPanel() {
  const [metrics, setMetrics] = useState(null)
  const [training, setTraining] = useState(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [evalRes, trainRes] = await Promise.all([
          apiFetch('/api/evaluation/latest'),
          apiFetch('/api/training/status'),
        ])
        if (evalRes.ok) setMetrics(await evalRes.json())
        if (trainRes.ok) setTraining(await trainRes.json())
      } catch (e) {
        console.error('Metrikler alınamadı', e)
      }
    }
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])

  const a = metrics?.available ? metrics.results?.anomaly : null
  const d = metrics?.available ? metrics.results?.detection : null

  return (
    <section className="panel-surface overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--line)]">
        <h2 className="font-display text-base font-semibold">Pilot Metrikler</h2>
      </div>
      <div className="p-5">
        {!metrics?.available ? (
          <p className="text-[var(--muted)] text-sm">
            {metrics?.message || 'Henüz pilot değerlendirme yok. run_pilot_eval.bat çalıştırın.'}
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <MetricCard label="Precision" value={a?.precision} />
            <MetricCard label="Recall" value={a?.recall} />
            <MetricCard label="Accuracy" value={a?.accuracy} />
            <MetricCard label="Gecikme (ms)" value={a?.avg_frame_latency_ms} />
            <MetricCard label="mAP@0.5" value={d?.map50} />
            <MetricCard label="mAP@0.5:0.95" value={d?.map50_95} />
            <MetricCard label="Video sayısı" value={metrics.results?.videos_processed} />
            <MetricCard label="F1" value={a?.f1} />
          </div>
        )}
        {training && (
          <p className="mt-4 pt-4 border-t border-[var(--line)] text-sm text-[var(--muted)] break-all">
            <span className="text-[var(--text)]/80 font-medium">Model: </span>
            {training.finetuned_ready ? (
              <span className="text-[var(--accent)]">Fine-tune hazır — {training.best_finetuned}</span>
            ) : (
              <span>Aktif: {training.current_model} · Fine-tune: {training.status}</span>
            )}
          </p>
        )}
      </div>
    </section>
  )
}

function MetricCard({ label, value }) {
  const display = value === null || value === undefined ? '—' : value
  return (
    <div className="rounded-lg border border-[var(--line)] bg-[var(--bg2)]/60 px-3.5 py-3">
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <div className="text-lg font-semibold mt-1 tabular-nums">{display}</div>
    </div>
  )
}
