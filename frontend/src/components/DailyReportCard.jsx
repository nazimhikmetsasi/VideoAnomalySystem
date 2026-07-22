import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../api'
import {
  buildDailySummary,
  buildTemplateDailyReport,
  copyText,
  downloadTxt,
  downloadPdfViaPrint,
  exportTodayCsv,
} from '../reportUtils'

export default function DailyReportCard({ history, cameras, llmStatus }) {
  const summary = useMemo(
    () => buildDailySummary(history, cameras),
    [history, cameras],
  )

  const [report, setReport] = useState('')
  const [mode, setMode] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [reportTotal, setReportTotal] = useState(null)

  const modeLabel =
    mode === 'llm'
      ? 'Gemini AI'
      : mode === 'template'
        ? 'Şablon'
        : llmStatus?.mode === 'llm'
          ? 'Gemini hazır'
          : 'Şablon hazır'

  const stale = report && reportTotal != null && reportTotal !== summary.total

  useEffect(() => {
    if (stale) {
      setMsg('Yeni uyarılar eklendi — raporu temizleyip yeniden oluşturun.')
    }
  }, [stale])

  const clearReport = () => {
    setReport('')
    setMode(null)
    setReportTotal(null)
    setMsg('Rapor temizlendi.')
  }

  const generate = async () => {
    setBusy(true)
    setMsg('')
    try {
      const res = await apiFetch('/api/reports/daily', {
        method: 'POST',
        body: JSON.stringify({ summary }),
      })
      if (res.ok) {
        const data = await res.json()
        setReport(data.report || '')
        setMode(data.mode || 'template')
        setReportTotal(summary.total)
        setMsg('Rapor oluşturuldu.')
      } else {
        const text = buildTemplateDailyReport(summary)
        setReport(text)
        setMode('template')
        setReportTotal(summary.total)
        setMsg('API yanıt vermedi — şablon rapor kullanıldı.')
      }
    } catch {
      const text = buildTemplateDailyReport(summary)
      setReport(text)
      setMode('template')
      setReportTotal(summary.total)
      setMsg('Bağlantı yok — şablon rapor kullanıldı.')
    } finally {
      setBusy(false)
    }
  }

  const onCopy = async () => {
    if (!report) {
      setMsg('Önce rapor oluşturun.')
      return
    }
    const ok = await copyText(report)
    setMsg(ok ? 'Panoya kopyalandı.' : 'Kopyalama başarısız.')
  }

  const onTxt = () => {
    if (!report) {
      setMsg('Önce rapor oluşturun.')
      return
    }
    const day = new Date().toISOString().slice(0, 10)
    downloadTxt(report, `mcbu_gunluk_rapor_${day}.txt`)
    setMsg('TXT indirildi.')
  }

  const onPdf = () => {
    if (!report) {
      setMsg('Önce rapor oluşturun.')
      return
    }
    const ok = downloadPdfViaPrint(report, 'MCBU Gunluk Durum Raporu')
    setMsg(ok ? 'PDF dosyası indirildi.' : 'PDF indirilemedi.')
  }

  const onCsv = () => {
    const n = exportTodayCsv(history)
    setMsg(n ? `Bugünün CSV’si indirildi (${n} kayıt).` : 'Bugün dışa aktarılacak kayıt yok.')
  }

  return (
    <section className="neo-card">
      <div className="flex items-start justify-between gap-3 flex-wrap mb-3">
        <div>
          <h2 className="neo-card__title">Günlük durum raporu</h2>
          <p className="text-xs text-[var(--muted)] mt-1">
            {summary.date} · {summary.total} uyarı · {modeLabel}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {report ? (
            <button type="button" className="neo-btn neo-btn--ghost" onClick={clearReport}>
              Temizle
            </button>
          ) : null}
          <button
            type="button"
            className="neo-btn neo-btn--lime"
            disabled={busy}
            onClick={generate}
          >
            {busy ? 'Oluşturuluyor…' : 'Rapor oluştur'}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <button
          type="button"
          className="neo-btn neo-btn--ghost !text-xs disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={onCopy}
          disabled={!report}
        >
          Kopyala
        </button>
        <button
          type="button"
          className="neo-btn neo-btn--ghost !text-xs disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={onTxt}
          disabled={!report}
        >
          TXT indir
        </button>
        <button
          type="button"
          className="neo-btn neo-btn--ghost !text-xs disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={onPdf}
          disabled={!report}
        >
          PDF indir
        </button>
        <button type="button" className="neo-btn neo-btn--ghost !text-xs" onClick={onCsv}>
          Bugünün CSV’si
        </button>
      </div>

      {report ? (
        <div className={`rounded-xl border p-4 ${stale ? 'border-amber-500/50 bg-amber-500/5' : 'border-[var(--line)] bg-[var(--bg0)]/40'}`}>
          <div className="flex items-center justify-between gap-2 mb-2">
            <p className="text-[11px] uppercase tracking-wider text-[var(--muted)]">
              {mode === 'llm' ? 'Gemini özeti' : 'Şablon özeti'}
              {stale ? ' · güncel değil' : ''}
            </p>
            <button
              type="button"
              className="text-[11px] text-[var(--muted)] hover:text-[var(--danger)] underline"
              onClick={clearReport}
            >
              Metni sil
            </button>
          </div>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{report}</p>
        </div>
      ) : (
        <p className="text-sm text-[var(--muted)] py-2">
          Bugünkü uyarı sayısı, tip dağılımı, kamera ve kritik olaylardan kısa Türkçe özet üretir.
          Gemini açıksa AI, değilse şablon kullanılır.
        </p>
      )}

      {msg && (
        <p className="mt-3 text-xs text-[var(--accent)]">{msg}</p>
      )}
    </section>
  )
}
