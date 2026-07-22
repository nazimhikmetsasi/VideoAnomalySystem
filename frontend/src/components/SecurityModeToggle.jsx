/** Evde / Koruma (Kur-Birak) anahtari */
export default function SecurityModeToggle({ mode, armed, busy, onToggle, canEdit }) {
  const label = armed ? 'Koruma açık' : 'Evde'
  const title = armed
    ? 'Koruma: anomaliler bildirim üretir. Tıklayınca Evde moduna geçer.'
    : 'Evde: izleme devam, bildirim/ses yok. Tıklayınca Koruma açılır.'

  if (!canEdit) {
    return (
      <span
        className={`neo-pill ${armed ? 'neo-pill--ok' : 'neo-pill--muted'}`}
        title={title}
      >
        {label}
      </span>
    )
  }

  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={busy}
      title={title}
      className={`neo-btn !text-xs ${armed ? 'neo-btn--lime' : 'neo-btn--ghost'}`}
      aria-pressed={armed}
      aria-label={label}
    >
      {busy ? '…' : label}
    </button>
  )
}
