/** Özet sayfası — sistem durumu kartı */
export default function SystemStatusCard({
  connected,
  llmStatus,
  activeCamera,
  cameras = [],
  todayCount = 0,
  onOpenCamera,
}) {
  const camLabel = activeCamera?.name || activeCamera?.id || previewFallback(cameras)
  const camId = activeCamera?.id || cameras[0]?.id
  const llmMode = llmStatus?.mode === 'llm' ? 'llm' : 'template'
  const llmTitle =
    llmMode === 'llm'
      ? `${llmStatus?.provider || 'Gemini'} · ${llmStatus?.model || 'AI'}`
      : 'Şablon rapor motoru'

  const rows = [
    {
      key: 'ws',
      label: 'Canlı bağlantı',
      value: connected ? 'Bağlı' : 'Kopuk',
      tone: connected ? 'ok' : 'bad',
      hint: connected ? 'WebSocket açık' : 'Yeniden bağlanılıyor…',
      icon: IconPulse,
    },
    {
      key: 'llm',
      label: 'Rapor motoru',
      value: llmMode === 'llm' ? 'Gemini AI' : 'Şablon',
      tone: llmMode === 'llm' ? 'ok' : 'warn',
      hint: llmTitle,
      icon: IconSpark,
    },
    {
      key: 'cam',
      label: 'Aktif kamera',
      value: camLabel || '—',
      tone: camId ? 'ok' : 'muted',
      hint: camId || 'Kamera yok',
      icon: IconCam,
      action: camId && onOpenCamera ? () => onOpenCamera(camId) : null,
    },
    {
      key: 'today',
      label: 'Bugün olay',
      value: String(todayCount),
      tone: todayCount > 0 ? 'accent' : 'muted',
      hint: todayCount > 0 ? 'Kayıtlı uyarı' : 'Henüz uyarı yok',
      icon: IconChart,
    },
  ]

  return (
    <article className="neo-card neo-span-2 system-status">
      <div className="flex items-center justify-between gap-2 mb-4">
        <div>
          <h2 className="neo-card__title">Sistem durumu</h2>
          <p className="text-xs text-[var(--muted)] mt-1">Anlık panel sağlığı</p>
        </div>
        <span className={`system-status__badge ${connected ? 'is-ok' : 'is-bad'}`}>
          <span className="system-status__badge-dot" />
          {connected ? 'Çevrimiçi' : 'Çevrimdışı'}
        </span>
      </div>

      <ul className="system-status__list">
        {rows.map((row) => {
          const Icon = row.icon
          const body = (
            <>
              <span className={`system-status__icon tone-${row.tone}`}>
                <Icon />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[11px] uppercase tracking-wider text-[var(--muted)]">
                  {row.label}
                </span>
                <span className="block text-sm font-semibold truncate mt-0.5">{row.value}</span>
                <span className="block text-[11px] text-[var(--muted)] truncate mt-0.5">{row.hint}</span>
              </span>
              <span className={`system-status__pill tone-${row.tone}`} aria-hidden>
                {row.tone === 'ok' ? '●' : row.tone === 'bad' ? '●' : '○'}
              </span>
            </>
          )
          return (
            <li key={row.key}>
              {row.action ? (
                <button type="button" className="system-status__row is-clickable" onClick={row.action}>
                  {body}
                </button>
              ) : (
                <div className="system-status__row">{body}</div>
              )}
            </li>
          )
        })}
      </ul>
    </article>
  )
}

function previewFallback(cameras) {
  if (!cameras?.length) return null
  return cameras[0].name || cameras[0].id
}

function IconPulse() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 12h4l2-5 4 10 2-5h6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function IconSpark() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z" strokeLinejoin="round" />
    </svg>
  )
}
function IconCam() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="2" y="6" width="14" height="12" rx="2" />
      <path d="M16 10l6-3v10l-6-3" strokeLinejoin="round" />
    </svg>
  )
}
function IconChart() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 19V5M4 19h16" strokeLinecap="round" />
      <path d="M8 15l3-4 3 2 4-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
