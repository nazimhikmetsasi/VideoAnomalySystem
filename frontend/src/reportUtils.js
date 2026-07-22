import { ANOMALY_LABELS, SEVERITY_RANK, exportAlertsCsv } from './constants'

function parseTs(ts) {
  if (ts == null) return null
  const d = new Date(typeof ts === 'number' && ts < 1e12 ? ts * 1000 : ts)
  return Number.isNaN(d.getTime()) ? null : d
}

export function isSameDay(ts, day = new Date()) {
  const d = parseTs(ts)
  if (!d) return false
  return d.toDateString() === day.toDateString()
}

export function getTodayItems(history) {
  return (history || []).filter((h) => isSameDay(h.timestamp))
}

/** Özet / API için günlük özet nesnesi */
export function buildDailySummary(history, cameras = []) {
  const today = getTodayItems(history)
  const byType = {}
  const camSet = new Set()
  const hourly = Array.from({ length: 24 }, () => 0)

  for (const h of today) {
    byType[h.anomaly_type] = (byType[h.anomaly_type] || 0) + 1
    if (h.camera_id) camSet.add(h.camera_id)
    const d = parseTs(h.timestamp)
    if (d) hourly[d.getHours()] += 1
  }

  for (const c of cameras || []) {
    if (c?.id) camSet.add(c.id)
  }

  let peakHour = null
  let peakVal = -1
  hourly.forEach((n, hour) => {
    if (n > peakVal) {
      peakVal = n
      peakHour = hour
    }
  })
  if (peakVal <= 0) peakHour = null

  const topEvents = [...today]
    .sort((a, b) => {
      const sa = SEVERITY_RANK[a.anomaly_type] || 0
      const sb = SEVERITY_RANK[b.anomaly_type] || 0
      if (sb !== sa) return sb - sa
      return (Number(b.confidence_score) || 0) - (Number(a.confidence_score) || 0)
    })
    .slice(0, 5)
    .map((h) => ({
      anomaly_type: h.anomaly_type,
      camera_id: h.camera_id,
      track_id: h.track_id,
      confidence_score: h.confidence_score,
      timestamp: h.timestamp,
      report: h.ai_generated_report || h.report,
    }))

  const date = new Date().toLocaleDateString('tr-TR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  return {
    date,
    total: today.length,
    by_type: byType,
    cameras: [...camSet],
    hourly,
    peak_hour: peakHour,
    top_events: topEvents,
    items: today,
  }
}

/** İstemci tarafı şablon (API yoksa yedek) */
export function buildTemplateDailyReport(summary) {
  const total = summary.total || 0
  const date = summary.date || 'Bugün'
  if (total === 0) {
    return (
      `${date} tarihli MCBU anomali durum raporu: Bugün kayıtlı uyarı bulunmamaktadır. ` +
      `İzlenen kamera sayısı: ${(summary.cameras || []).length}. Sistem izlemeye devam etmektedir.`
    )
  }
  const parts = Object.entries(summary.by_type || {})
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${ANOMALY_LABELS[k] || k} (${v})`)
  const dist = parts.join(', ') || 'dağılım yok'
  const cams = (summary.cameras || []).join(', ') || 'belirtilmedi'
  const peak =
    summary.peak_hour != null
      ? ` En yoğun saat dilimi ${String(summary.peak_hour).padStart(2, '0')}:00 civarıdır.`
      : ''
  const crit = (summary.top_events || []).slice(0, 3).map((e) => {
    const tip = ANOMALY_LABELS[e.anomaly_type] || e.anomaly_type
    const conf = Number(e.confidence_score)
    const confS = Number.isFinite(conf) ? conf.toFixed(2) : String(e.confidence_score ?? '')
    return `${tip} (kamera ${e.camera_id}, varlık ${e.track_id}, güven ${confS})`
  })
  const critTxt = crit.length ? ` Öne çıkan olaylar: ${crit.join('; ')}.` : ''
  return (
    `${date} tarihli MCBU anomali durum raporu: Bugün toplam ${total} uyarı kaydedilmiştir. ` +
    `Tip dağılımı: ${dist}. İlgili kameralar: ${cams}.${peak}${critTxt}`
  )
}

export function exportTodayCsv(history) {
  const rows = getTodayItems(history).map((h) => ({
    ...h,
    report: h.ai_generated_report || h.report,
  }))
  exportAlertsCsv(rows)
  return rows.length
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      return true
    } catch {
      return false
    }
  }
}

export function downloadTxt(text, filename) {
  triggerBlobDownload(
    new Blob([text], { type: 'text/plain;charset=utf-8' }),
    filename.endsWith('.txt') ? filename : `${filename}.txt`,
  )
}

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  a.remove()
  // Hemen revoke edilirse bazi tarayicilarda indirme iptal olur
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

/** Türkçe / unicode → PDF Helvetica (WinAnsi) guvenli ASCII */
function toPdfLatin(text) {
  const map = {
    ş: 's', Ş: 'S', ı: 'i', İ: 'I', ğ: 'g', Ğ: 'G',
    ü: 'u', Ü: 'U', ö: 'o', Ö: 'O', ç: 'c', Ç: 'C',
    â: 'a', Â: 'A', î: 'i', Î: 'I', û: 'u', Û: 'U',
    '‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-',
    '…': '...', '·': '-', '•': '-', '\u00a0': ' ',
  }
  return String(text)
    .replace(/./g, (ch) => map[ch] || ch)
    .replace(/[^\x09\x0A\x0D\x20-\x7E]/g, '?')
}

function pdfEscape(str) {
  return String(str).replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)')
}

function encodePdfBytes(str) {
  const bytes = new Uint8Array(str.length)
  for (let i = 0; i < str.length; i++) bytes[i] = str.charCodeAt(i) & 0xff
  return bytes
}

/**
 * Gerçek .pdf dosyası indirir (Türkçe karakterler Latin'e çevrilir).
 * Ekrandaki / TXT raporda Türkçe tam kalır.
 */
export function downloadPdfFile(text, filename, title = 'MCBU Gunluk Durum Raporu') {
  try {
    const body = toPdfLatin(text || ' ')
    const safeTitle = toPdfLatin(title || 'MCBU Rapor')
    const dateLine = toPdfLatin(
      new Date().toLocaleString('en-GB', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }),
    )

    const lines = []
    const wrapWidth = 86
    for (const raw of body.split(/\r?\n/)) {
      const paragraph = raw.length ? raw : ' '
      let rest = paragraph
      while (rest.length > wrapWidth) {
        let cut = rest.lastIndexOf(' ', wrapWidth)
        if (cut < 40) cut = wrapWidth
        lines.push(rest.slice(0, cut))
        rest = rest.slice(cut).trimStart()
      }
      lines.push(rest || ' ')
    }
    if (!lines.length) lines.push(' ')

    const pageW = 595
    const pageH = 842
    const left = 50
    const top = 800
    const leading = 16
    const maxLines = Math.floor((top - 60) / leading)

    const pageChunks = []
    for (let i = 0; i < lines.length; i += maxLines) {
      pageChunks.push(lines.slice(i, i + maxLines))
    }

    const objects = []
    const add = (content) => {
      objects.push(content)
      return objects.length
    }

    const fontId = add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    const kids = []

    pageChunks.forEach((pageLines, pageIdx) => {
      let y = top
      const contentLines = []
      if (pageIdx === 0) {
        contentLines.push(`BT /F1 14 Tf ${left} ${y} Td (${pdfEscape(safeTitle)}) Tj ET`)
        y -= 26
        contentLines.push(`BT /F1 9 Tf ${left} ${y} Td (${pdfEscape(dateLine)}) Tj ET`)
        y -= 22
      }
      contentLines.push('BT')
      contentLines.push('/F1 11 Tf')
      contentLines.push(`${left} ${y} Td`)
      contentLines.push(`${leading} TL`)
      pageLines.forEach((line, idx) => {
        const safe = pdfEscape(line)
        contentLines.push(idx === 0 ? `(${safe}) Tj` : `T* (${safe}) Tj`)
      })
      contentLines.push('ET')

      const stream = contentLines.join('\n')
      const contentId = add(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`)
      const pageId = add(
        `<< /Type /Page /Parent PAGES_REF /MediaBox [0 0 ${pageW} ${pageH}] ` +
          `/Contents ${contentId} 0 R /Resources << /Font << /F1 ${fontId} 0 R >> >> >>`,
      )
      kids.push(pageId)
    })

    const pagesId = add(
      `<< /Type /Pages /Kids [${kids.map((id) => `${id} 0 R`).join(' ')}] /Count ${kids.length} >>`,
    )
    for (const pageId of kids) {
      objects[pageId - 1] = objects[pageId - 1].replace('PAGES_REF', `${pagesId} 0 R`)
    }
    const catalogId = add(`<< /Type /Catalog /Pages ${pagesId} 0 R >>`)

    const parts = ['%PDF-1.4\n']
    const offsets = [0]
    for (let i = 0; i < objects.length; i++) {
      offsets.push(parts.reduce((n, p) => n + p.length, 0))
      parts.push(`${i + 1} 0 obj\n${objects[i]}\nendobj\n`)
    }
    const xrefPos = parts.reduce((n, p) => n + p.length, 0)
    let xref = `xref\n0 ${objects.length + 1}\n`
    xref += '0000000000 65535 f \n'
    for (let i = 1; i <= objects.length; i++) {
      xref += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`
    }
    parts.push(xref)
    parts.push(`trailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\n`)
    parts.push(`startxref\n${xrefPos}\n%%EOF\n`)

    const pdfStr = parts.join('')
    const bytes = encodePdfBytes(pdfStr)
    const name = filename.endsWith('.pdf') ? filename : `${filename}.pdf`
    triggerBlobDownload(new Blob([bytes], { type: 'application/pdf' }), name)
    return true
  } catch (err) {
    console.error('PDF indirme hatasi', err)
    return false
  }
}

/** PDF indir (blob + gecikmeli revoke). */
export function downloadPdfViaPrint(text, title = 'MCBU Gunluk Durum Raporu') {
  const day = new Date().toISOString().slice(0, 10)
  return downloadPdfFile(text, `mcbu_gunluk_rapor_${day}.pdf`, title)
}
