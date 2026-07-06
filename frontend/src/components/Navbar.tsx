import { useState, useRef, useEffect } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

function getInitials(email: string): string {
  const local = email.split('@')[0]
  const parts = local.split(/[._-]/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return local.slice(0, 2).toUpperCase()
}

export default function Navbar() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Seed the input from the current URL so it stays in sync when the user
  // arrives on /cases via other routes or hits back/forward.
  const [search, setSearch] = useState(() => {
    return new URLSearchParams(location.search).get('q') ?? ''
  })
  useEffect(() => {
    if (location.pathname === '/cases') {
      setSearch(new URLSearchParams(location.search).get('q') ?? '')
    }
  }, [location.pathname, location.search])

  function handleSearchChange(v: string) {
    setSearch(v)
    const target = v.trim() ? `/cases?q=${encodeURIComponent(v)}` : '/cases'
    // Replace history so back button doesn't get littered with per-keystroke entries.
    navigate(target, { replace: true })
  }

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [menuOpen])

  async function handleSignOut() {
    setMenuOpen(false)
    await signOut()
    navigate('/login', { replace: true })
  }

  const initials = user?.email ? getInitials(user.email) : '??'
  const email = user?.email ?? ''

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-50">
        {/* Top bar */}
        <div className="bg-navy-deep h-13 flex items-center px-4 gap-3">
          {/* Brand */}
          <div className="bg-teal text-white font-mono font-semibold text-sm w-8 h-8 flex items-center justify-center rounded shrink-0">
            II
          </div>
          <span className="text-white font-medium text-sm tracking-wide flex-1">
            Investigation Intelligence
          </span>
          {/* Search — wired to /cases?q= filter */}
          <div className="relative">
            <input
              type="text"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search cases..."
              className="
                bg-white/10 border border-white/20 text-white placeholder-white/40
                text-sm rounded px-3 py-1.5 w-48
                focus:outline-none focus:border-teal-soft focus:bg-white/15
                transition-colors duration-150
              "
            />
          </div>
          {/* Avatar + dropdown */}
          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="bg-teal hover:bg-teal-soft text-white font-semibold text-sm w-8 h-8 flex items-center justify-center rounded-full shrink-0 transition-colors"
              aria-label="Account menu"
            >
              {initials}
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full mt-2 w-56 bg-panel border border-border rounded-xl shadow-lg overflow-hidden z-50">
                {/* Email row */}
                <div className="px-4 py-3 border-b border-border">
                  <p className="text-xs text-text-mute truncate">{email}</p>
                </div>
                {/* Sign out */}
                <button
                  onClick={handleSignOut}
                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-mid hover:bg-panel-2 hover:text-text transition-colors"
                >
                  <LogOut size={14} className="text-text-mute" />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Tab bar */}
        <div
          className="bg-navy h-11 flex items-center px-4 gap-1"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.10)' }}
        >
          {[
            { to: '/cases', label: 'Cases' },
            { to: '/account', label: 'Account' },
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

      {/* Spacer */}
      <div className="h-24" />
    </>
  )
}
