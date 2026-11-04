import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  FlaskConical,
  Zap,
  Settings,
  SlidersHorizontal,
  Activity,
} from '../utils/lucide'
import { useState } from 'react'
import './Layout.css'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Scenarios', href: '/scenarios', icon: FileText },
  { name: 'Studio', href: '/studio', icon: SlidersHorizontal },
  { name: 'Workspace', href: '/workspace', icon: Activity },
  { name: 'Experiments', href: '/experiments', icon: FlaskConical },
  { name: 'Network', href: '/network', icon: Zap },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h1>SAEA</h1>
          <p>Service-Aware Energy Agents</p>
        </div>
        <nav className="sidebar-nav">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                `nav-link ${isActive ? 'active' : ''}`
              }
            >
              <item.icon size={20} />
              <span>{item.name}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <NavLink to="/settings" className="nav-link">
            <Settings size={20} />
            <span>Settings</span>
          </NavLink>
        </div>
      </aside>

      {/* Mobile menu button */}
      <button
        className="mobile-menu-btn"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle menu"
      >
        <svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          {sidebarOpen ? (
            <path d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path d="M3 12h18M3 6h18M3 18h18" />
          )}
        </svg>
      </button>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Main content */}
      <main className="main-content">
        <header className="top-bar">
          <div className="top-bar-left">
            <h1>{location.pathname === '/' ? 'Dashboard' : location.pathname.slice(1)}</h1>
          </div>
          <div className="top-bar-right">
            <div className="user-menu">
              <span>Admin</span>
            </div>
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  )
}