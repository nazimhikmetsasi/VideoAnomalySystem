/** Güneş / ay tema anahtarı (referans: düz pill toggle). */
export default function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? 'Açık temaya geç' : 'Karanlık temaya geç'}
      title={isDark ? 'Açık tema' : 'Karanlık tema'}
      onClick={onToggle}
      className={`theme-switch ${isDark ? 'theme-switch--dark' : 'theme-switch--light'}`}
    >
      <span className="theme-switch__icon theme-switch__icon--sun" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      </span>
      <span className="theme-switch__icon theme-switch__icon--moon" aria-hidden="true">
        {/* Klasik hilal ay */}
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M12.1 2a9.9 9.9 0 0 0-1.3.1A10 10 0 1 0 21.9 13.2 8.2 8.2 0 0 1 12.1 2z" />
        </svg>
      </span>
      <span className="theme-switch__knob" />
    </button>
  )
}
