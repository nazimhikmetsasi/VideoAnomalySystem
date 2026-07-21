export const ANOMALY_LABELS = {
  FALL: 'Düşme',
  PERSON_ENTERED: 'Kişi Girdi',
  RUN: 'Koşma',
  ZONE_VIOLATION: 'Alan İhlali',
  RUN_ZONE: 'Koşarak Alan İhlali',
}

/** Yüksek = daha kritik (liste sıralaması) */
export const SEVERITY_RANK = {
  FALL: 100,
  RUN_ZONE: 90,
  RUN: 70,
  ZONE_VIOLATION: 50,
  PERSON_ENTERED: 20,
}

export const ANOMALY_ACCENT = {
  FALL: 'border-l-[#e05656]',
  PERSON_ENTERED: 'border-l-sky-500',
  RUN: 'border-l-[#e8a54b]',
  ZONE_VIOLATION: 'border-l-violet-400',
  RUN_ZONE: 'border-l-[#e8a54b]',
}

export const ANOMALY_BADGE = {
  FALL: 'bg-[#e05656]/15 text-[#e05656]',
  PERSON_ENTERED: 'bg-sky-500/15 text-sky-600',
  RUN: 'bg-[#e8a54b]/20 text-[#c47d2c]',
  ZONE_VIOLATION: 'bg-violet-500/15 text-violet-600',
  RUN_ZONE: 'bg-[#e8a54b]/25 text-[#c47d2c]',
}

export const ANOMALY_TYPES = [
  { value: '', label: 'Tüm tipler' },
  { value: 'RUN_ZONE', label: 'Koşarak Alan İhlali' },
  { value: 'RUN', label: 'Koşma' },
  { value: 'ZONE_VIOLATION', label: 'Alan İhlali' },
  { value: 'FALL', label: 'Düşme' },
  { value: 'PERSON_ENTERED', label: 'Kişi Girdi' },
]

export const DATE_RANGES = [
  { value: '', label: 'Tüm zamanlar' },
  { value: 'today', label: 'Bugün' },
  { value: 'week', label: 'Bu hafta' },
]

export const THEME_KEY = 'mcbu_theme'
export const SOUND_KEY = 'mcbu_sound'
export const READ_KEY = 'mcbu_read_alerts'

export function alertKey(a) {
  return [
    a.id ?? '',
    a.camera_id ?? '',
    a.track_id ?? '',
    a.anomaly_type ?? '',
    a.timestamp ?? '',
  ].join('|')
}

export function loadReadSet() {
  try {
    const raw = JSON.parse(localStorage.getItem(READ_KEY) || '[]')
    return new Set(Array.isArray(raw) ? raw : [])
  } catch {
    return new Set()
  }
}

export function saveReadSet(set) {
  const arr = [...set].slice(-300)
  localStorage.setItem(READ_KEY, JSON.stringify(arr))
}

export function getStoredTheme() {
  const t = localStorage.getItem(THEME_KEY)
  return t === 'light' || t === 'dark' ? t : 'dark'
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem(THEME_KEY, theme)
}

let _alarmAudio = null
let _alarmUnlocked = false

/** PCM siren WAV (HTML Audio — WebAudio kilidine takilmaz). */
function buildAlarmWavUrl() {
  const sampleRate = 22050
  const duration = 2.6
  const n = Math.floor(sampleRate * duration)
  const dataSize = n * 2
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  const writeStr = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }
  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeStr(36, 'data')
  view.setUint32(40, dataSize, true)

  const amp = 0.32
  for (let i = 0; i < n; i++) {
    const t = i / sampleRate
    const freq = (Math.floor(t / 0.2) % 2 === 0) ? 980 : 560
    const phase = (i % Math.max(1, Math.floor(sampleRate / freq))) < (sampleRate / freq) / 2 ? 1 : -1
    // Yumusak fade in/out
    let env = 1
    if (t < 0.05) env = t / 0.05
    else if (t > duration - 0.2) env = Math.max(0, (duration - t) / 0.2)
    const sample = Math.max(-1, Math.min(1, phase * amp * env))
    view.setInt16(44 + i * 2, sample * 0x7fff, true)
  }

  const blob = new Blob([buffer], { type: 'audio/wav' })
  return URL.createObjectURL(blob)
}

function getAlarmAudio() {
  if (!_alarmAudio) {
    _alarmAudio = new Audio(buildAlarmWavUrl())
    _alarmAudio.preload = 'auto'
  }
  return _alarmAudio
}

/** Tarayici ses kilidini ac (kullanici tiklamasi). */
export function unlockAlertSound() {
  _alarmUnlocked = true
  try {
    const a = getAlarmAudio()
    a.muted = true
    const p = a.play()
    if (p && typeof p.then === 'function') {
      p.then(() => {
        a.pause()
        a.currentTime = 0
        a.muted = false
      }).catch(() => {
        a.muted = false
      })
    } else {
      a.muted = false
    }
  } catch {
    /* sessiz */
  }
}

/** Uzun siren alarmı (~2.6 sn). */
export function playAlertBeep() {
  try {
    const a = getAlarmAudio()
    a.muted = false
    a.volume = 0.85
    a.currentTime = 0
    const p = a.play()
    if (p && typeof p.catch === 'function') {
      p.catch(() => {
        // Ilk engelde kilidi zorla acmayi dene
        if (!_alarmUnlocked) unlockAlertSound()
      })
    }
  } catch {
    /* sessiz */
  }
}

export function exportAlertsCsv(rows) {
  const header = ['Zaman', 'Tip', 'Kamera', 'Varlık ID', 'Güven', 'Rapor']
  const lines = [header.join(';')]
  for (const r of rows) {
    const tip = ANOMALY_LABELS[r.anomaly_type] || r.anomaly_type || ''
    const ts = r.timestamp ? new Date(r.timestamp).toLocaleString('tr-TR') : ''
    const report = String(r.report || r.ai_generated_report || '').replace(/;/g, ',').replace(/\n/g, ' ')
    lines.push([
      ts,
      tip,
      r.camera_id ?? '',
      r.track_id ?? '',
      r.confidence_score ?? '',
      report,
    ].join(';'))
  }
  const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `mcbu_uyarilar_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
