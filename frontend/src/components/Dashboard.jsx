import DashboardNeo from './DashboardNeo'

/** Ana panel — şablon (neo) düzeni. */
export default function Dashboard({ user, onLogout }) {
  return <DashboardNeo user={user} onLogout={onLogout} />
}
