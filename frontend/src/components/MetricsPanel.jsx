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
        console.error('Metrikler alinamadi', e)
      }
    }
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])

  const a = metrics?.available ? metrics.results?.anomaly : null
  const d = metrics?.available ? metrics.results?.detection : null

  return (
    <section className="bg-slate-800 rounded-xl p-5 mb-6">
      <h2 className="text-lg font-semibold mb-4">Pilot Metrikler</h2>
      {!metrics?.available ? (
        <p className="text-slate-400 text-sm">{metrics?.message || 'Henuz pilot degerlendirme yok. run_pilot_eval.bat calistirin.'}</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <MetricCard label="Precision" value={a?.precision} />
          <MetricCard label="Recall" value={a?.recall} />
          <MetricCard label="Accuracy" value={a?.accuracy} />
          <MetricCard label="Latency (ms)" value={a?.avg_frame_latency_ms} />
          <MetricCard label="mAP@0.5" value={d?.map50} />
          <MetricCard label="mAP@0.5:0.95" value={d?.map50_95} />
          <MetricCard label="Video sayisi" value={metrics.results?.videos_processed} />
          <MetricCard label="F1" value={a?.f1} />
        </div>
      )}
      {training && (
        <div className="mt-4 pt-4 border-t border-slate-700 text-sm text-slate-300">
          <span className="font-medium">Model: </span>
          {training.finetuned_ready ? (
            <span className="text-emerald-400">Fine-tune hazir — {training.best_finetuned}</span>
          ) : (
            <span>Aktif: {training.current_model} | Fine-tune: {training.status}</span>
          )}
        </div>
      )}
    </section>
  )
}

function MetricCard({ label, value }) {
  const display = value === null || value === undefined ? '—' : value
  return (
    <div className="bg-slate-700 rounded-lg p-3">
      <div className="text-slate-400 text-xs">{label}</div>
      <div className="text-lg font-semibold mt-1">{display}</div>
    </div>
  )
}
