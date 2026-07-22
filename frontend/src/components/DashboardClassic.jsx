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
  ANOMALY_ACCENT,
  ANOMALY_BADGE,
  alertKey,
} from '../constants'

/**
 * Klasik panel düzeni (önceki sürüm).
 * Neo şablona LayoutToggle ile geçilebilir.
 */
export default function DashboardClassic({ user, onLogout, layout, onLayoutChange }) {
  const d = useDashboard()
  const {
    alerts, history, connected, popup, setPopup, testMsg, llmStatus, cameras,
    theme, soundOn, filters, setFilters, selectedAlert, setSelectedAlert,
    previewCam, setPreviewCam, readSet, selectedKeys,
    toggleTheme, toggleSound, markRead, markReadKeys, toggleSelect,
    selectAllInList, clearSelection, sendTestAlert,
    filteredAlerts, filteredHistory, unreadCount, selectedCount,
    allLiveSelected, allHistorySelected, unreadLiveKeys, unreadHistoryKeys,
    selectedUnreadKeys,
  } = d

  const btnGhost = 'px-3.5 py-1.5 rounded-md text-sm font-medium border border-[var(--line)] text-[var(--text)] hover:bg-[var(--bg2)] transition'
  const btnPrimary = 'px-3.5 py-1.5 rounded-md text-sm font-medium bg-[var(--accent)] text-[#04120f] hover:brightness-110 transition'
  const btnTiny = 'px-2 py-1 text-[11px] rounded-md border border-[var(--line)] hover:bg-[var(--bg2)] disabled:opacity-40 disabled:cursor-not-allowed'
  const userLabel = user?.username || 'kullanıcı'

  return (
    <div className="min-h-screen text-[var(--text)]">
      <header className="border-b border-[var(--line)] bg-[var(--bg1)]/85 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-4 min-w-0">
            <div className="header-toggles">
              <ThemeToggle theme={theme} onToggle={toggleTheme} />
              <SoundToggle soundOn={soundOn} onToggle={toggleSound} />
              <LayoutToggle layout={layout} onChange={onLayoutChange} />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--accent)] font-semibold mb-1">
                MCBU
              </p>
              <h1 className="font-display text-xl md:text-2xl font-semibold">
                Video Anomali Paneli
              </h1>
              <p className="text-sm text-[var(--muted)] mt-0.5">
                Video tabanlı anomali tespiti ve davranış analizi
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium border border-[var(--line)] ${
              connected ? 'text-emerald-600 bg-emerald-500/10' : 'text-rose-500 bg-rose-500/10'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
              {connected ? 'Bağlı' : 'Bağlantı yok'}
            </span>

            {llmStatus && (
              <span
                className="px-3 py-1.5 rounded-md text-xs font-medium border border-[var(--line)] text-[var(--muted)] bg-[var(--bg2)]"
                title={llmStatus.mode === 'llm' ? `${llmStatus.provider} / ${llmStatus.model}` : 'GEMINI_API_KEY tanımlı değil'}
              >
                {llmStatus.mode === 'llm' ? 'Gemini AI' : 'Şablon rapor'}
              </span>
            )}

            <span className="text-sm text-[var(--muted)] hidden sm:inline">{userLabel}</span>

            {user?.role === 'admin' && (
              <button type="button" onClick={sendTestAlert} className={btnPrimary}>
                Test bildirimi
              </button>
            )}

            <button type="button" onClick={onLogout} className={btnGhost}>
              Çıkış Yap
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-5 py-6 space-y-5">
        {testMsg && (
          <div className="toast-in px-4 py-3 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10 text-sm">
            {testMsg}
          </div>
        )}

        {popup && (
          <div className="fixed top-20 right-5 z-50 max-w-sm toast-in">
            <button
              type="button"
              onClick={() => setSelectedAlert(popup)}
              className={`w-full text-left rounded-lg border border-[var(--line)] bg-[var(--bg1)] p-4 shadow-2xl border-l-4 ${ANOMALY_ACCENT[popup.anomaly_type] || 'border-l-[#e05656]'}`}
            >
              <h3 className="font-display font-semibold">
                {ANOMALY_LABELS[popup.anomaly_type] || popup.anomaly_type}
              </h3>
              <p className="mt-2 text-sm text-[var(--muted)] leading-relaxed">{popup.report}</p>
              <p className="mt-3 text-xs text-[var(--muted)]">
                {popup.camera_id} · Varlık {popup.track_id} · Güven {Number(popup.confidence_score).toFixed(2)}
              </p>
            </button>
          </div>
        )}

        <AlertFilters
          filters={filters}
          onChange={setFilters}
          cameras={cameras}
          exportRows={filteredHistory}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <section className="panel-surface overflow-hidden">
            <div className="px-5 py-4 border-b border-[var(--line)] space-y-3">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <h2 className="font-display text-base font-semibold">Canlı Uyarılar</h2>
                <span className="text-xs text-[var(--muted)]">
                  {unreadCount} okunmamış · {filteredAlerts.length} toplam
                  {selectedCount > 0 ? ` · ${selectedCount} seçili` : ''}
                </span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <label className="inline-flex items-center gap-2 text-xs text-[var(--muted)] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    className="alert-check"
                    checked={allLiveSelected}
                    disabled={filteredAlerts.length === 0}
                    onChange={() => {
                      if (allLiveSelected) clearSelection()
                      else selectAllInList(filteredAlerts)
                    }}
                  />
                  Tümünü seç
                </label>
                <button type="button" className={btnTiny} disabled={selectedCount === 0} onClick={clearSelection}>
                  Seçimi kaldır
                </button>
                <button type="button" className={btnTiny} disabled={selectedUnreadKeys.length === 0} onClick={() => markReadKeys(selectedUnreadKeys)}>
                  Seçilenleri okundu
                </button>
                <button type="button" className={btnTiny} disabled={unreadLiveKeys.length === 0} onClick={() => markReadKeys(unreadLiveKeys)}>
                  Tümünü okundu
                </button>
              </div>
            </div>
            <div className="p-3 max-h-[28rem] overflow-auto">
              {filteredAlerts.length === 0 ? (
                <p className="text-[var(--muted)] text-sm px-2 py-6 text-center">
                  Filtreye uyan bildirim yok.
                </p>
              ) : (
                <ul className="space-y-2">
                  {filteredAlerts.map((a, i) => {
                    const key = alertKey(a)
                    const isRead = readSet.has(key)
                    const isSelected = selectedKeys.has(key)
                    return (
                      <li key={`${key}-${i}`} className={isRead ? 'alert-card--read' : ''}>
                        <div
                          className={`rounded-lg bg-[var(--bg2)]/80 border border-l-4 p-3.5 flex items-start gap-3 ${
                            ANOMALY_ACCENT[a.anomaly_type] || 'border-l-[#e8a54b]'
                          } ${isSelected ? 'border-[var(--accent)]/50 bg-[var(--accent)]/5' : 'border-[var(--line)]'}`}
                        >
                          <input
                            type="checkbox"
                            className="alert-check mt-1 shrink-0"
                            checked={isSelected}
                            onChange={() => toggleSelect(key)}
                            aria-label="Uyarıyı seç"
                          />
                          <button
                            type="button"
                            className="text-left flex-1 min-w-0"
                            onClick={() => setSelectedAlert(a)}
                          >
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={`text-xs font-medium px-2 py-0.5 rounded ${ANOMALY_BADGE[a.anomaly_type] || 'bg-black/5'}`}>
                                {ANOMALY_LABELS[a.anomaly_type] || a.anomaly_type}
                              </span>
                              {isRead && <span className="alert-read-pill">Okundu</span>}
                            </div>
                            <p className="text-sm mt-2 text-[var(--muted)] leading-relaxed">{a.report}</p>
                            <p className="text-xs text-[var(--muted)] mt-1">{a.camera_id} · Varlık {a.track_id}</p>
                          </button>
                          <div className="flex flex-col items-end gap-2 shrink-0">
                            {!isRead ? (
                              <button type="button" onClick={() => markRead(a)} className={btnTiny}>
                                Okundu
                              </button>
                            ) : null}
                          </div>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </section>

          <section className="panel-surface overflow-hidden">
            <div className="px-5 py-4 border-b border-[var(--line)] space-y-3">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <h2 className="font-display text-base font-semibold">Geçmiş Kayıtlar</h2>
                <span className="text-xs text-[var(--muted)]">
                  {filteredHistory.length}
                  {selectedCount > 0 ? ` · ${selectedCount} seçili` : ''}
                </span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <label className="inline-flex items-center gap-2 text-xs text-[var(--muted)] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    className="alert-check"
                    checked={allHistorySelected}
                    disabled={filteredHistory.length === 0}
                    onChange={() => {
                      if (allHistorySelected) clearSelection()
                      else selectAllInList(filteredHistory)
                    }}
                  />
                  Tümünü seç
                </label>
                <button type="button" className={btnTiny} disabled={selectedCount === 0} onClick={clearSelection}>
                  Seçimi kaldır
                </button>
                <button type="button" className={btnTiny} disabled={selectedUnreadKeys.length === 0} onClick={() => markReadKeys(selectedUnreadKeys)}>
                  Seçilenleri okundu
                </button>
                <button type="button" className={btnTiny} disabled={unreadHistoryKeys.length === 0} onClick={() => markReadKeys(unreadHistoryKeys)}>
                  Tümünü okundu
                </button>
              </div>
            </div>
            <div className="overflow-auto max-h-[28rem]">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[var(--bg1)]">
                  <tr className="text-[var(--muted)] text-left border-b border-[var(--line)]">
                    <th className="pl-4 pr-1 py-3 w-10" aria-hidden="true" />
                    <th className="px-3 py-3 font-medium">Zaman</th>
                    <th className="px-3 py-3 font-medium">Tip</th>
                    <th className="px-3 py-3 font-medium">Kamera</th>
                    <th className="px-5 py-3 font-medium text-right">Güven</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHistory.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-8 text-center text-[var(--muted)]">
                        Kayıt yok.
                      </td>
                    </tr>
                  ) : (
                    filteredHistory.map((h) => {
                      const key = alertKey(h)
                      const isRead = readSet.has(key)
                      const isSelected = selectedKeys.has(key)
                      return (
                        <tr
                          key={h.id}
                          className={`border-b border-[var(--line)] hover:bg-black/[0.03] ${isRead ? 'alert-card--read' : ''} ${isSelected ? 'bg-[var(--accent)]/5' : ''}`}
                        >
                          <td className="pl-4 pr-1 py-3" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              className="alert-check"
                              checked={isSelected}
                              onChange={() => toggleSelect(key)}
                              aria-label="Kaydı seç"
                            />
                          </td>
                          <td
                            className="px-3 py-3 text-xs text-[var(--muted)] whitespace-nowrap cursor-pointer"
                            onClick={() => setSelectedAlert({ ...h, report: h.ai_generated_report })}
                          >
                            {new Date(h.timestamp).toLocaleString('tr-TR')}
                          </td>
                          <td
                            className="px-3 py-3 cursor-pointer"
                            onClick={() => setSelectedAlert({ ...h, report: h.ai_generated_report })}
                          >
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={`text-xs font-medium px-2 py-0.5 rounded ${ANOMALY_BADGE[h.anomaly_type] || ''}`}>
                                {ANOMALY_LABELS[h.anomaly_type] || h.anomaly_type}
                              </span>
                              {isRead && <span className="alert-read-pill">Okundu</span>}
                            </div>
                          </td>
                          <td
                            className="px-3 py-3 text-[var(--muted)] cursor-pointer"
                            onClick={() => setSelectedAlert({ ...h, report: h.ai_generated_report })}
                          >
                            {h.camera_id}
                            <span className="block text-[10px] opacity-70">ID {h.track_id}</span>
                          </td>
                          <td
                            className="px-5 py-3 text-right tabular-nums cursor-pointer"
                            onClick={() => setSelectedAlert({ ...h, report: h.ai_generated_report })}
                          >
                            {h.confidence_score?.toFixed(2)}
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 space-y-5">
            <LivePreview cameraId={previewCam} />
            {cameras.length > 1 && (
              <div className="flex flex-wrap gap-2 -mt-2">
                {cameras.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setPreviewCam(c.id)}
                    className={`px-3 py-1 rounded-md text-xs border ${
                      previewCam === c.id
                        ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent)]/10'
                        : 'border-[var(--line)] text-[var(--muted)]'
                    }`}
                  >
                    {c.name || c.id}
                  </button>
                ))}
              </div>
            )}
            <AlertGallery cameraId={previewCam} refreshKey={alerts.length} liveAlerts={alerts} />
            <StatsSummary history={history} />
          </div>
          <div className="space-y-5">
            <ZoneMap cameraId={previewCam} />
            <MetricsPanel />
          </div>
        </div>
      </main>

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
