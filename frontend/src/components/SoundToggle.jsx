/** Ses açık/kapalı — tema anahtarı ile aynı stil. */
export default function SoundToggle({ soundOn, onToggle }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={soundOn}
      aria-label={soundOn ? 'Sesi kapat' : 'Sesi aç'}
      title={soundOn ? 'Ses açık' : 'Ses kapalı'}
      onClick={onToggle}
      className={`theme-switch sound-switch ${soundOn ? 'sound-switch--on' : 'sound-switch--off'}`}
    >
      <span className="theme-switch__icon sound-switch__icon--on" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M11 5 6 9H3v6h3l5 4V5z" />
          <path d="M15.5 8.5a5 5 0 0 1 0 7" />
          <path d="M18 6a8 8 0 0 1 0 12" />
        </svg>
      </span>
      <span className="theme-switch__icon sound-switch__icon--off" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M11 5 6 9H3v6h3l5 4V5z" />
          <path d="M22 9l-6 6M16 9l6 6" />
        </svg>
      </span>
      <span className="theme-switch__knob" />
    </button>
  )
}
