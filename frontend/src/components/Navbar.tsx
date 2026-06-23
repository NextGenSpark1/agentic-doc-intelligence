import { NavLink } from 'react-router-dom'

export default function Navbar() {
  return (
    <>
      {/* Fixed two-bar header */}
      <header className="fixed top-0 left-0 right-0 z-50">
        {/* Top bar */}
        <div className="bg-navy-deep h-13 flex items-center px-4 gap-3">
          {/* Brand square */}
          <div className="bg-teal text-white font-mono font-semibold text-sm w-8 h-8 flex items-center justify-center rounded shrink-0">
            II
          </div>
          {/* Title */}
          <span className="text-white font-medium text-sm tracking-wide flex-1">
            Investigation Intelligence
          </span>
          {/* Search */}
          <div className="relative">
            <input
              type="text"
              placeholder="Search..."
              className="
                bg-white/10 border border-white/20 text-white placeholder-white/40
                text-sm rounded px-3 py-1.5 w-48
                focus:outline-none focus:border-teal-soft focus:bg-white/15
                transition-colors duration-150
              "
            />
          </div>
          {/* Avatar */}
          <div className="bg-teal text-white font-semibold text-sm w-8 h-8 flex items-center justify-center rounded-full shrink-0">
            H
          </div>
        </div>

        {/* Tab bar */}
        <div
          className="bg-navy h-11 flex items-center px-4 gap-1"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.10)' }}
        >
          {[
            { to: '/cases', label: 'Cases' },
            { to: '/settings', label: 'Settings' },
          ].map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                isActive
                  ? 'px-3 py-1 rounded bg-white text-navy text-sm font-medium transition-colors duration-150'
                  : 'px-3 py-1 rounded text-white/60 text-sm font-medium hover:text-white/90 transition-colors duration-150'
              }
            >
              {label}
            </NavLink>
          ))}
        </div>
      </header>

      {/* Spacer so content starts below fixed header (h-13 + h-11 = 52+44=96px) */}
      <div className="h-24" />
    </>
  )
}
