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
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/** Türkçe karakterleri PDF Helvetica için sadeleştir */
function toPdfLatin(text) {
  const map = {
    ş: 's', Ş: 'S', ı: 'i', İ: 'I', ğ: 'g', Ğ: 'G',
    ü: 'u', Ü: 'U', ö: 'o', Ö: 'O', ç: 'c', Ç: 'C',
    â: 'a', Â: 'A', î: 'i', Î: 'I', û: 'u', Û: 'U',
  }
  return String(text).replace(/./g, (ch) => map[ch] || ch)
}

function pdfEscape(str) {
  return String(str).replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)')
}

/**
 * Gerçek .pdf dosyası indirir (Türkçe karakterler Latin'e çevrilir).
 * Ekrandaki / TXT raporda Türkçe tam kalır.
 */
export function downloadPdfFile(text, filename, title = 'MCBU Gunluk Durum Raporu') {
  const body = toPdfLatin(text)
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
    lines.push(rest)
  }
  if (!lines.length) lines.push(' ')

  const pageW = 595
  const pageH = 842
  const left = 50
  const top = 800
  const leading = 16
  const maxLines = Math.floor((top - 50) / leading)

  const pages = []
  for (let i = 0; i < lines.length; i += maxLines) {
    pages.push(lines.slice(i, i + maxLines))
  }
  if (!pages.length) pages.push([' '])

  const objects = []
  const add = (content) => {
    objects.push(content)
    return objects.length
  }

  const kids = []
  const fontId = add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')

  pages.forEach((pageLines, pageIdx) => {
    let y = top
    const contentLines = []
    if (pageIdx === 0) {
      contentLines.push(`BT /F1 14 Tf ${left} ${y} Td (${pdfEscape(toPdfLatin(title))}) Tj ET`)
      y -= 28
      contentLines.push(
        `BT /F1 9 Tf ${left} ${y} Td (${pdfEscape(toPdfLatin(new Date().toLocaleString('tr-TR')))}) Tj ET`,
      )
      y -= 24
    }
    contentLines.push('BT')
    contentLines.push(`/F1 11 Tf`)
    contentLines.push(`${left} ${y} Td`)
    contentLines.push(`${leading} TL`)
    pageLines.forEach((line, idx) => {
      const safe = pdfEscape(line)
      if (idx === 0) contentLines.push(`(${safe}) Tj`)
      else contentLines.push(`T* (${safe}) Tj`)
    })
    contentLines.push('ET')
    const stream = contentLines.join('\n')
    const contentId = add(
      `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    )
    const pageId = add(
      `<< /Type /Page /Parent 0 0 R /MediaBox [0 0 ${pageW} ${pageH}] ` +
        `/Contents ${contentId} 0 R /Resources << /Font << /F1 ${fontId} 0 R >> >> >>`,
    )
    kids.push(pageId)
  })

  const pagesId = add(
    `<< /Type /Pages /Kids [${kids.map((id) => `${id} 0 R`).join(' ')}] /Count ${kids.length} >>`,
  )
  // Patch parent refs in page objects
  for (const pageId of kids) {
    objects[pageId - 1] = objects[pageId - 1].replace('/Parent 0 0 R', `/Parent ${pagesId} 0 R`)
  }

  const catalogId = add(`<< /Type /Catalog /Pages ${pagesId} 0 R >>`)

  let pdf = '%PDF-1.4\n'
  const offsets = [0]
  for (let i = 0; i < objects.length; i++) {
    offsets.push(pdf.length)
    pdf += `${i + 1} 0 obj\n${objects[i]}\nendobj\n`
  }
  const xrefPos = pdf.length
  pdf += `xref\n0 ${objects.length + 1}\n`
  pdf += '0000000000 65535 f \n'
  for (let i = 1; i <= objects.length; i++) {
    pdf += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`
  }
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\n`
  pdf += `startxref\n${xrefPos}\n%%EOF`

  const blob = new Blob([pdf], { type: 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.endsWith('.pdf') ? filename : `${filename}.pdf`
  a.click()
  URL.revokeObjectURL(url)
  return true
}

/** Yazdırılabilir HTML indir + isteğe bağlı yazdır (eski blank sekme hatasını önler) */
export function downloadPdfViaPrint(text, title = 'MCBU Günlük Rapor') {
  const day = new Date().toISOString().slice(0, 10)
  // Asıl indirme: gerçek PDF dosyası
  downloadPdfFile(text, `mcbu_gunluk_rapor_${day}.pdf`, title)
  return true
}
