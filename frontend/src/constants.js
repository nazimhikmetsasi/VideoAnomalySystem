export const ANOMALY_LABELS = {
  FALL: 'Düşme',
  PERSON_ENTERED: 'Kişi Girdi',
  RUN: 'Koşma',
  ZONE_VIOLATION: 'Alan İhlali',
  RUN_ZONE: 'Koşarak Alan İhlali',
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

export const THEME_KEY = 'mcbu_theme'
export const SOUND_KEY = 'mcbu_sound'

export function getStoredTheme() {
  const t = localStorage.getItem(THEME_KEY)
  return t === 'light' || t === 'dark' ? t : 'dark'
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem(THEME_KEY, theme)
}

export function playAlertBeep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = 880
    gain.gain.value = 0.04
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.18)
    osc.stop(ctx.currentTime + 0.2)
    setTimeout(() => ctx.close(), 300)
  } catch {
    /* sessiz */
  }
}
