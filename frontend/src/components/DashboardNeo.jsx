import { useEffect, useMemo, useState } from 'react'
import MetricsPanel from './MetricsPanel'
import LivePreview from './LivePreview'
import AlertGallery from './AlertGallery'
import ZoneMap from './ZoneMap'
import AlertFilters from './AlertFilters'
import StatsSummary from './StatsSummary'
import SnapshotModal from './SnapshotModal'
import ThemeToggle from './ThemeToggle'
import SoundToggle from './SoundToggle'
import SecurityModeToggle from './SecurityModeToggle'
import HourlyTrend from './HourlyTrend'
import DailyReportCard from './DailyReportCard'
import SystemStatusCard from './SystemStatusCard'
import { useDashboard } from '../hooks/useDashboard'
import {
  ANOMALY_LABELS,
  ANOMALY_BADGE,
  alertKey,
  isAlertRead,
  getStoredNav,
  saveNav,
} from '../constants'

const NAV = [
  { id: 'overview', label: 'Özet', sub: 'Durum kartları ve günlük özet', icon: IconGrid },
  { id: 'live', label: 'Canlı', sub: 'Anlık uyarı kuyruğu', icon: IconPulse },
  { id: 'history', label: 'Geçmiş', sub: 'Kayıtlı anomali listesi', icon: IconClock },
  { id: 'camera', label: 'Kamera', sub: 'Canlı önizleme ve galeri', icon: IconCam },
  { id: 'zones', label: 'Bölgeler', sub: 'Yasaklı alan haritası', icon: IconMap },
  { id: 'metrics', label: 'Metrik', sub: 'Pilot değerlendirme sonuçları', icon: IconChart },
]

/** Ana panel — kenar menü ile tek sayfa görünümü. */
export default function DashboardNeo({ user, onLogout }) {
  const d = useDashboard()
  const {
    alerts, history, connected, popup, testMsg, llmStatus, cameras,
    theme, soundOn, filters, setFilters, selectedAlert, setSelectedAlert,
    previewCam, setPreviewCam, readSet,
    securityMode, securityBusy,
    toggleTheme, toggleSound, toggleSecurityMode, markRead, markReadKeys, sendTestAlert,
    filteredAlerts, filteredHistory, unreadCount, unreadLiveKeys,
  } = d

  const [nav, setNav] = useState(() => getStoredNav())
  const userLabel = user?.username || 'kullanıcı'
  const activeNav = NAV.find((n) => n.id === nav) || NAV[0]

  useEffect(() => {
    saveNav(nav)
  }, [nav])

  const todayCount = useMemo(() => {
    const now = new Date()
    return (history || []).filter((h) => {
      const t = new Date(typeof h.timestamp === 'number' && h.timestamp < 1e12 ? h.timestamp * 1000 : h.timestamp)
      return !Number.isNaN(t.getTime()) && t.toDateString() === now.toDateString()
    }).length
  }, [history])

  const cameraList = cameras.length ? cameras : [{ id: previewCam, name: previewCam }]

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
                onClick={() => setNav(item.id)}
              >
                <Icon />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div className="neo-sidebar__foot">
          <div className="neo-sidebar__toggles">
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
            <SoundToggle soundOn={soundOn} onToggle={toggleSound} />
          </div>
          <button type="button" className="neo-btn neo-btn--lime w-full" onClick={onLogout}>
            Çıkış
          </button>
        </div>
      </aside>

      <div className="neo-main">
        <header className="neo-topbar">
          <div>
            <h1 className="neo-topbar__title">{activeNav.label}</h1>
            <p className="neo-topbar__sub">{activeNav.sub}</p>
          </div>
          <div className="neo-topbar__actions">
            <SecurityModeToggle
              mode={securityMode?.mode}
              armed={securityMode?.armed !== false}
              busy={securityBusy}
              canEdit={user?.role === 'admin'}
              onToggle={toggleSecurityMode}
            />
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
                onClick={() => {
                  setSelectedAlert(popup)
                  setNav('live')
                }}
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

          {nav === 'overview' && (
            <section className="neo-bento">
              <article className="neo-card neo-card--gradient neo-span-2">
                <p className="neo-card__eyebrow">Okunmamış</p>
                <p className="neo-card__hero-num">{unreadCount}</p>
                <p className="neo-card__hint">Canlı uyarı kuyruğu</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {unreadLiveKeys.length > 0 && (
                    <button
                      type="button"
                      className="neo-btn neo-btn--lime"
                      onClick={() => markReadKeys(unreadLiveKeys)}
                    >
                      Tümünü okundu işaretle
                    </button>
                  )}
                  <button
                    type="button"
                    className="neo-btn neo-btn--ghost"
                    onClick={() => setNav('live')}
                  >
                    Canlı uyarılar
                  </button>
                </div>
              </article>

              <article className="neo-card neo-card--gradient-alt">
                <p className="neo-card__eyebrow">Bugün</p>
                <p className="neo-card__hero-num">{todayCount}</p>
                <p className="neo-card__hint">Toplam olay</p>
              </article>

              <article className="neo-card">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="neo-card__title">Kameralar</h2>
                  <span className="text-xs text-[var(--muted)]">{cameraList.length}</span>
                </div>
                <ul className="neo-list">
                  {cameraList.map((c, i) => {
                    const active = previewCam === c.id
                    const colors = ['#7dffa0', '#6ec8ff', '#4db8a8']
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
                            setNav('camera')
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
                <StatsSummary history={history} />
              </article>

              <SystemStatusCard
                connected={connected}
                llmStatus={llmStatus}
                activeCamera={
                  cameraList.find((c) => c.id === previewCam) || cameraList[0] || null
                }
                cameras={cameraList}
                todayCount={todayCount}
                onOpenCamera={(id) => {
                  setPreviewCam(id)
                  setNav('camera')
                }}
              />

              <div className="neo-span-4">
                <HourlyTrend history={history} />
              </div>

              <div className="neo-span-4">
                <DailyReportCard
                  history={history}
                  cameras={cameras}
                  llmStatus={llmStatus}
                />
              </div>
            </section>
          )}

          {nav === 'live' && (
            <section className="space-y-5">
              <AlertFilters
                filters={filters}
                onChange={setFilters}
                cameras={cameras}
                exportRows={filteredHistory}
              />
              <article className="neo-card overflow-hidden !p-0">
                <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between">
                  <h2 className="neo-card__title">Canlı uyarılar</h2>
                  <span className="text-xs text-[var(--muted)]">
                    {unreadCount} okunmamış · {filteredAlerts.length} toplam
                  </span>
                </div>
                <div className="p-3 max-h-[min(70vh,40rem)] overflow-auto">
                  {filteredAlerts.length === 0 ? (
                    <p className="text-sm text-[var(--muted)] text-center py-10">Bildirim yok.</p>
                  ) : (
                    <ul className="space-y-2">
                      {filteredAlerts.map((a, i) => {
                        const key = alertKey(a)
                        const isRead = isAlertRead(readSet, a)
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
            </section>
          )}

          {nav === 'history' && (
            <section className="space-y-5">
              <AlertFilters
                filters={filters}
                onChange={setFilters}
                cameras={cameras}
                exportRows={filteredHistory}
              />
              <article className="neo-card overflow-hidden !p-0">
                <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between">
                  <h2 className="neo-card__title">Geçmiş kayıtlar</h2>
                  <span className="text-xs text-[var(--muted)]">{filteredHistory.length}</span>
                </div>
                <div className="overflow-auto max-h-[min(70vh,40rem)]">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-[var(--neo-card)]">
                      <tr className="text-[var(--muted)] text-left border-b border-[var(--line)]">
                        <th className="px-4 py-3 font-medium">Zaman</th>
                        <th className="px-3 py-3 font-medium">Tip</th>
                        <th className="px-3 py-3 font-medium">Kamera</th>
                        <th className="px-3 py-3 font-medium">Varlık ID</th>
                        <th className="px-4 py-3 font-medium text-right">Güven</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredHistory.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-4 py-8 text-center text-[var(--muted)]">Kayıt yok.</td>
                        </tr>
                      ) : (
                        filteredHistory.map((h) => (
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
                            <td className="px-3 py-3 tabular-nums text-[var(--text)]">{h.track_id ?? '—'}</td>
                            <td className="px-4 py-3 text-right tabular-nums">{h.confidence_score?.toFixed(2)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </article>
            </section>
          )}

          {nav === 'camera' && (
            <section className="space-y-5">
              {cameraList.length > 1 && (
                <div className="flex flex-wrap gap-2">
                  {cameraList.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => setPreviewCam(c.id)}
                      className={`neo-btn !text-xs ${
                        previewCam === c.id ? 'neo-btn--lime' : 'neo-btn--ghost'
                      }`}
                    >
                      {c.name || c.id}
                    </button>
                  ))}
                </div>
              )}
              <div className="neo-card !p-0 overflow-hidden">
                <LivePreview cameraId={previewCam} />
              </div>
              <AlertGallery cameraId={previewCam} refreshKey={alerts.length} liveAlerts={alerts} />
            </section>
          )}

          {nav === 'zones' && (
            <section className="max-w-3xl">
              {cameraList.length > 1 && (
                <div className="flex flex-wrap gap-2 mb-5">
                  {cameraList.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => setPreviewCam(c.id)}
                      className={`neo-btn !text-xs ${
                        previewCam === c.id ? 'neo-btn--lime' : 'neo-btn--ghost'
                      }`}
                    >
                      {c.name || c.id}
                    </button>
                  ))}
                </div>
              )}
              <div className="neo-card !p-0 overflow-hidden">
                <ZoneMap cameraId={previewCam} />
              </div>
            </section>
          )}

          {nav === 'metrics' && (
            <section className="max-w-3xl">
              <div className="neo-card !p-0 overflow-hidden">
                <MetricsPanel />
              </div>
            </section>
          )}
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
