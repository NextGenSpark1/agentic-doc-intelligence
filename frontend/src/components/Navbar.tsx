import { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { LogOut, Settings } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { getInitialsFromUser } from '../pages/AccountPage'

export default function Navbar() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

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

  const initials = user ? getInitialsFromUser(user) : '??'
  const email = user?.email ?? ''
  const fullName = (user?.user_metadata?.full_name as string | undefined)?.trim() ?? ''
  const displayName = fullName || email

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-50">
        <div className="bg-navy-deep h-13 flex items-center px-4 gap-3">
          {/* Brand */}
          <img src="/NG logo.jpeg" alt="NextGen Spark" className="w-8 h-8 rounded object-contain bg-white p-0.5 shrink-0" />
          <span className="text-white font-medium text-sm tracking-wide flex-1">
            NextGen Spark
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
              <div className="absolute right-0 top-full mt-2 w-60 bg-panel border border-border rounded-xl shadow-lg overflow-hidden z-50">
                {/* User info */}
                <div className="px-4 py-3 border-b border-border">
                  <p className="text-sm font-semibold text-text truncate">{displayName}</p>
                  {fullName && (
                    <p className="text-xs text-text-mute truncate mt-0.5">{email}</p>
                  )}
                </div>
                {/* Account Settings */}
                <button
                  onClick={() => { setMenuOpen(false); navigate('/account') }}
                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-mid hover:bg-panel-2 hover:text-text transition-colors"
                >
                  <Settings size={14} className="text-text-mute" />
                  Account Settings
                </button>
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
      </header>

      {/* Spacer */}
      <div className="h-13" />
    </>
  )
}
