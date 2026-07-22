import { useMemo, useState } from 'react'
import MetricsPanel from './MetricsPanel'
import LivePreview from './LivePreview'
import AlertGallery from './AlertGallery'
import ZoneMap from './ZoneMap'
import AlertFilters from './AlertFilters'
import StatsSummary from './StatsSummary'
import SnapshotModal from './SnapshotModal'
import ThemeToggle from './ThemeToggle'
import SoundToggle from './SoundToggle'
import LayoutToggle from './LayoutToggle'
import { useDashboard } from '../hooks/useDashboard'
import {
  ANOMALY_LABELS,
  ANOMALY_BADGE,
  alertKey,
} from '../constants'

const NAV = [
  { id: 'overview', label: 'Özet', icon: IconGrid },
  { id: 'live', label: 'Canlı', icon: IconPulse },
  { id: 'history', label: 'Geçmiş', icon: IconClock },
  { id: 'camera', label: 'Kamera', icon: IconCam },
  { id: 'zones', label: 'Bölgeler', icon: IconMap },
  { id: 'metrics', label: 'Metrik', icon: IconChart },
]

function scrollTo(id) {
  document.getElementById(`neo-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

/**
 * Şablon (neo) panel — sidebar + bento kart düzeni.
 * Klasik sürüme LayoutToggle ile dönülebilir.
 */
export default function DashboardNeo({ user, onLogout, layout, onLayoutChange }) {
  const d = useDashboard()
  const {
    alerts, history, connected, popup, testMsg, llmStatus, cameras,
    theme, soundOn, filters, setFilters, selectedAlert, setSelectedAlert,
    previewCam, setPreviewCam, readSet,
    toggleTheme, toggleSound, markRead, markReadKeys, sendTestAlert,
    filteredAlerts, filteredHistory, unreadCount, unreadLiveKeys,
  } = d

  const [nav, setNav] = useState('overview')
  const userLabel = user?.username || 'kullanıcı'

  const todayCount = useMemo(() => {
    const now = new Date()
    return (history || []).filter((h) => {
      const t = new Date(typeof h.timestamp === 'number' && h.timestamp < 1e12 ? h.timestamp * 1000 : h.timestamp)
      return !Number.isNaN(t.getTime()) && t.toDateString() === now.toDateString()
    }).length
  }, [history])

  const go = (id) => {
    setNav(id)
    scrollTo(id)
  }

  return (
    <div className="neo-shell min-h-screen text-[var(--text)]">
      <aside className="neo-sidebar">
        <div className="neo-brand">
          <span className="neo-brand__mark" aria-hidden />
          <div>
            <p className="neo-brand__name">MCBU</p>
            <p className="neo-brand__sub">Anomali</p>
          </div>
        </div>

        <nav className="neo-nav" aria-label="Panel menüsü">
          {NAV.map((item) => {
            const Icon = item.icon
            const active = nav === item.id
            return (
              <button
                key={item.id}
                type="button"
                className={`neo-nav__item ${active ? 'is-active' : ''}`}
                onClick={() => go(item.id)}
              >
                <Icon />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div className="neo-sidebar__foot">
          <LayoutToggle layout={layout} onChange={onLayoutChange} />
          <div className="flex gap-2 items-center">
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
            <SoundToggle soundOn={soundOn} onToggle={toggleSound} />
          </div>
          <button type="button" className="neo-btn neo-btn--ghost w-full" onClick={onLogout}>
            Çıkış
          </button>
        </div>
      </aside>

      <div className="neo-main">
        <header className="neo-topbar">
          <div>
            <h1 className="neo-topbar__title">Anomali Paneli</h1>
            <p className="neo-topbar__sub">Canlı izleme · uyarı · rapor</p>
          </div>
          <div className="neo-topbar__actions">
            <span className={`neo-pill ${connected ? 'neo-pill--ok' : 'neo-pill--bad'}`}>
              <span className="neo-dot" />
              {connected ? 'Bağlı' : 'Kopuk'}
            </span>
            {llmStatus && (
              <span className="neo-pill neo-pill--muted">
                {llmStatus.mode === 'llm' ? 'Gemini AI' : 'Şablon rapor'}
              </span>
            )}
            <span className="neo-user">{userLabel}</span>
            {user?.role === 'admin' && (
              <button type="button" className="neo-btn neo-btn--lime" onClick={sendTestAlert}>
                Test bildirimi
              </button>
            )}
          </div>
        </header>

        <div className="neo-content space-y-5">
          {testMsg && (
            <div className="toast-in neo-toast">{testMsg}</div>
          )}

          {popup && (
            <div className="fixed top-6 right-6 z-50 max-w-sm toast-in">
              <button
                type="button"
                onClick={() => setSelectedAlert(popup)}
                className="neo-card neo-card--popup text-left w-full"
              >
                <p className="text-xs text-[var(--neo-lime)] font-semibold uppercase tracking-wider mb-1">
                  Yeni uyarı
                </p>
                <h3 className="font-display font-semibold text-lg">
                  {ANOMALY_LABELS[popup.anomaly_type] || popup.anomaly_type}
                </h3>
                <p className="mt-2 text-sm text-[var(--muted)] leading-relaxed">{popup.report}</p>
                <p className="mt-3 text-xs text-[var(--muted)]">
                  {popup.camera_id} · Varlık {popup.track_id}
                </p>
              </button>
            </div>
          )}

          <section id="neo-overview" className="neo-bento">
            <article className="neo-card neo-card--gradient neo-span-2">
              <p className="neo-card__eyebrow">Okunmamış</p>
              <p className="neo-card__hero-num">{unreadCount}</p>
              <p className="neo-card__hint">Canlı uyarı kuyruğu</p>
              {unreadLiveKeys.length > 0 && (
                <button
                  type="button"
                  className="neo-btn neo-btn--lime mt-4"
                  onClick={() => markReadKeys(unreadLiveKeys)}
                >
                  Tümünü okundu işaretle
                </button>
              )}
            </article>

            <article className="neo-card neo-card--gradient-alt">
              <p className="neo-card__eyebrow">Bugün</p>
              <p className="neo-card__hero-num">{todayCount}</p>
              <p className="neo-card__hint">Toplam olay</p>
            </article>

            <article className="neo-card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="neo-card__title">Kameralar</h2>
                <span className="text-xs text-[var(--muted)]">{cameras.length || 1}</span>
              </div>
              <ul className="neo-list">
                {(cameras.length ? cameras : [{ id: previewCam, name: previewCam }]).map((c, i) => {
                  const active = previewCam === c.id
                  const colors = ['#7dffa0', '#6ec8ff', '#b794ff']
                  return (
                    <li key={c.id} className="neo-list__row">
                      <span className="neo-avatar" style={{ background: colors[i % colors.length] }} />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{c.name || c.id}</p>
                        <p className="text-[11px] text-[var(--muted)]">{c.id}</p>
                      </div>
                      <button
                        type="button"
                        className={`neo-btn ${active ? 'neo-btn--lime' : 'neo-btn--ghost'} !py-1 !px-3 !text-xs`}
                        onClick={() => {
                          setPreviewCam(c.id)
                          go('camera')
                        }}
                      >
                        {active ? 'Aktif' : 'Aç'}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </article>

            <article className="neo-card neo-span-2">
              <div className="flex items-center justify-between mb-3">
                <h2 className="neo-card__title">Bugünkü özet</h2>
                <button type="button" className="neo-btn neo-btn--lime !text-xs" onClick={() => go('metrics')}>
                  Metrikler
                </button>
              </div>
              <StatsSummary history={history} />
            </article>
          </section>

          <div id="neo-live" className="scroll-mt-4">
            <AlertFilters
              filters={filters}
              onChange={setFilters}
              cameras={cameras}
              exportRows={filteredHistory}
            />
          </div>

          <section className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <article className="neo-card overflow-hidden !p-0">
              <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between">
                <h2 className="neo-card__title">Canlı uyarılar</h2>
                <span className="text-xs text-[var(--muted)]">{filteredAlerts.length}</span>
              </div>
              <div className="p-3 max-h-[26rem] overflow-auto">
                {filteredAlerts.length === 0 ? (
                  <p className="text-sm text-[var(--muted)] text-center py-10">Bildirim yok.</p>
                ) : (
                  <ul className="space-y-2">
                    {filteredAlerts.slice(0, 12).map((a, i) => {
                      const key = alertKey(a)
                      const isRead = readSet.has(key)
                      return (
                        <li key={`${key}-${i}`} className={isRead ? 'alert-card--read' : ''}>
                          <button
                            type="button"
                            className="neo-alert-row w-full text-left"
                            onClick={() => setSelectedAlert(a)}
                          >
                            <span className={`text-xs font-medium px-2 py-0.5 rounded ${ANOMALY_BADGE[a.anomaly_type] || ''}`}>
                              {ANOMALY_LABELS[a.anomaly_type] || a.anomaly_type}
                            </span>
                            <p className="text-sm mt-2 text-[var(--muted)] line-clamp-2">{a.report}</p>
                            <div className="mt-2 flex items-center justify-between gap-2">
                              <p className="text-[11px] text-[var(--muted)]">{a.camera_id} · ID {a.track_id}</p>
                              {!isRead && (
                                <span
                                  role="button"
                                  tabIndex={0}
                                  className="neo-btn neo-btn--lime !py-0.5 !px-2 !text-[10px]"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    markRead(a)
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                      e.stopPropagation()
                                      markRead(a)
                                    }
                                  }}
                                >
                                  Okundu
                                </span>
                              )}
                            </div>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            </article>

            <article id="neo-history" className="neo-card overflow-hidden !p-0 scroll-mt-4">
              <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between">
                <h2 className="neo-card__title">Geçmiş kayıtlar</h2>
                <span className="text-xs text-[var(--muted)]">{filteredHistory.length}</span>
              </div>
              <div className="overflow-auto max-h-[26rem]">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-[var(--neo-card)]">
                    <tr className="text-[var(--muted)] text-left border-b border-[var(--line)]">
                      <th className="px-4 py-3 font-medium">Zaman</th>
                      <th className="px-3 py-3 font-medium">Tip</th>
                      <th className="px-3 py-3 font-medium">Kamera</th>
                      <th className="px-4 py-3 font-medium text-right">Güven</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredHistory.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-[var(--muted)]">Kayıt yok.</td>
                      </tr>
                    ) : (
                      filteredHistory.slice(0, 40).map((h) => (
                        <tr
                          key={h.id}
                          className="border-b border-[var(--line)] hover:bg-white/[0.03] cursor-pointer"
                          onClick={() => setSelectedAlert({ ...h, report: h.ai_generated_report })}
                        >
                          <td className="px-4 py-3 text-xs text-[var(--muted)] whitespace-nowrap">
                            {new Date(h.timestamp).toLocaleString('tr-TR')}
                          </td>
                          <td className="px-3 py-3">
                            <span className={`text-xs font-medium px-2 py-0.5 rounded ${ANOMALY_BADGE[h.anomaly_type] || ''}`}>
                              {ANOMALY_LABELS[h.anomaly_type] || h.anomaly_type}
                            </span>
                          </td>
                          <td className="px-3 py-3 text-[var(--muted)]">{h.camera_id}</td>
                          <td className="px-4 py-3 text-right tabular-nums">{h.confidence_score?.toFixed(2)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </article>
          </section>

          <section id="neo-camera" className="grid grid-cols-1 lg:grid-cols-3 gap-5 scroll-mt-4">
            <div className="lg:col-span-2 space-y-5">
              <div className="neo-card !p-0 overflow-hidden">
                <div className="px-5 py-3 border-b border-[var(--line)] flex items-center justify-between">
                  <h2 className="neo-card__title">Canlı önizleme</h2>
                  <span className="text-xs text-[var(--muted)]">{previewCam}</span>
                </div>
                <LivePreview cameraId={previewCam} />
              </div>
              <AlertGallery cameraId={previewCam} refreshKey={alerts.length} liveAlerts={alerts} />
            </div>
            <div id="neo-zones" className="space-y-5 scroll-mt-4">
              <div className="neo-card !p-0 overflow-hidden">
                <ZoneMap cameraId={previewCam} />
              </div>
              <div id="neo-metrics" className="neo-card !p-0 overflow-hidden scroll-mt-4">
                <MetricsPanel />
              </div>
            </div>
          </section>
        </div>
      </div>

      <SnapshotModal
        alert={selectedAlert}
        history={history}
        liveAlerts={alerts}
        readSet={readSet}
        onClose={() => setSelectedAlert(null)}
        onMarkRead={markRead}
        onSelectAlert={setSelectedAlert}
      />
    </div>
  )
}

function IconGrid() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  )
}
function IconPulse() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 12h4l2-6 4 12 2-6h6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
function IconClock() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v5l3 2" strokeLinecap="round" />
    </svg>
  )
}
function IconCam() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="2" y="6" width="14" height="12" rx="2" />
      <path d="M16 10l6-3v10l-6-3" strokeLinejoin="round" />
    </svg>
  )
}
function IconMap() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2z" strokeLinejoin="round" />
      <path d="M9 4v14M15 6v14" />
    </svg>
  )
}
function IconChart() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 19V5M4 19h16" strokeLinecap="round" />
      <path d="M8 15l3-4 3 2 4-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
