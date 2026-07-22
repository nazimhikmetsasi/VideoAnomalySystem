import { LAYOUT_LABELS } from '../constants'

/** Klasik ↔ Neo şablon geçişi */
export default function LayoutToggle({ layout, onChange }) {
  const next = layout === 'neo' ? 'classic' : 'neo'
  return (
    <button
      type="button"
      className="layout-toggle"
      onClick={() => onChange(next)}
      title={`Görünüm: ${LAYOUT_LABELS[layout]} — tıkla: ${LAYOUT_LABELS[next]}`}
      aria-label={`Panel görünümü: ${LAYOUT_LABELS[layout]}`}
    >
      <span className={`layout-toggle__opt ${layout === 'classic' ? 'is-on' : ''}`}>Klasik</span>
      <span className={`layout-toggle__opt ${layout === 'neo' ? 'is-on' : ''}`}>Şablon</span>
    </button>
  )
}
