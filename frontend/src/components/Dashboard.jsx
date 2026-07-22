import { useState } from 'react'
import DashboardClassic from './DashboardClassic'
import DashboardNeo from './DashboardNeo'
import { getStoredLayout, applyLayout } from '../constants'

/**
 * Panel giriş noktası — klasik (eski) ve neo (şablon) arasında geçiş.
 * Tercih localStorage'da saklanır; önceki sürüm kaybolmaz.
 */
export default function Dashboard({ user, onLogout }) {
  const [layout, setLayout] = useState(() => getStoredLayout())

  const onLayoutChange = (next) => {
    setLayout(next)
    applyLayout(next)
  }

  if (layout === 'neo') {
    return (
      <DashboardNeo
        user={user}
        onLogout={onLogout}
        layout={layout}
        onLayoutChange={onLayoutChange}
      />
    )
  }

  return (
    <DashboardClassic
      user={user}
      onLogout={onLogout}
      layout={layout}
      onLayoutChange={onLayoutChange}
    />
  )
}
