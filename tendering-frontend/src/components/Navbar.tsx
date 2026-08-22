import { useState, useRef, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, FolderOpen, Library, LogOut, Settings, ShieldCheck, Building2, Users } from 'lucide-react';
import { useAuth, PLATFORM_ADMIN_EMAILS } from '../context/AuthContext';

const NAV_LINKS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/tenders', label: 'Tenders', icon: FolderOpen },
  { to: '/documents', label: 'Document Library', icon: Library },
];

export function Navbar() {
  const { user, signOut, orgCtx } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const isPlatformAdmin = PLATFORM_ADMIN_EMAILS.includes(user?.email ?? '');
  const hasOrg = !!orgCtx?.org_id;

  const fullName = ((user?.user_metadata?.full_name as string | undefined) ?? '').trim();
  const email = user?.email ?? '';
  const displayName = fullName || email;
  const initials = displayName.slice(0, 2).toUpperCase();

  useEffect(() => {
    function handleClickOutside(clickEvent: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(clickEvent.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [menuOpen]);

  async function handleSignOut() {
    setMenuOpen(false);
    await signOut();
    navigate('/login', { replace: true });
  }

  const orgSettingsLabel = orgCtx?.role === 'org_admin'
    ? 'Org Settings'
    : orgCtx?.role === 'supervisor'
    ? 'Team'
    : 'My Team';

  return (
    <header className="fixed top-0 inset-x-0 z-50">
      <div className="bg-navy-deep h-13 flex items-center px-6 justify-between">
        <div className="flex items-center gap-3">
          <img
            src="/NG logo.jpeg"
            alt="NextGen Spark"
            className="w-7 h-7 rounded-md object-contain bg-white p-0.5 shrink-0"
          />
          <span className="text-white font-semibold text-sm tracking-wide">Tendering Intelligence</span>
        </div>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(open => !open)}
            className="bg-teal hover:bg-teal-soft text-white font-semibold text-sm w-8 h-8 flex items-center justify-center rounded-full transition-colors"
            aria-label="Account menu"
          >
            {initials}
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-2 w-60 bg-panel border border-border rounded-xl shadow-lg overflow-hidden z-50">
              <div className="px-4 py-3 border-b border-border">
                <p className="text-sm font-semibold text-text truncate">{displayName}</p>
                {fullName && <p className="text-xs text-text-mute truncate mt-0.5">{email}</p>}
                {orgCtx?.org_name && (
                  <p className="text-[10px] text-text-mute mt-1 truncate">{orgCtx.org_name}</p>
                )}
                {isPlatformAdmin && (
                  <p className="text-[10px] font-semibold text-teal mt-1 uppercase tracking-wide">Platform Admin</p>
                )}
              </div>

              {isPlatformAdmin && (
                <button
                  onClick={() => { setMenuOpen(false); navigate('/admin'); }}
                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-mid hover:bg-panel-2 hover:text-text transition-colors"
                >
                  <ShieldCheck size={14} className="text-text-mute" />
                  Platform Admin
                </button>
              )}

              {hasOrg && (
                <button
                  onClick={() => { setMenuOpen(false); navigate('/org/settings'); }}
                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-mid hover:bg-panel-2 hover:text-text transition-colors"
                >
                  {orgCtx?.role === 'org_admin'
                    ? <Building2 size={14} className="text-text-mute" />
                    : <Users size={14} className="text-text-mute" />
                  }
                  {orgSettingsLabel}
                </button>
              )}

              <button
                onClick={() => { setMenuOpen(false); navigate('/account'); }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-mid hover:bg-panel-2 hover:text-text transition-colors"
              >
                <Settings size={14} className="text-text-mute" />
                Account Settings
              </button>

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

      <nav className="bg-navy flex items-center px-6 gap-1 border-b border-white/10">
        {NAV_LINKS.map(({ to, label, icon: Icon, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                isActive ? 'text-white border-teal' : 'text-white/60 border-transparent hover:text-white/90'
              }`
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
