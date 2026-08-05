import { NavLink } from 'react-router-dom';
import { BarChart3, FileSearch, BookOpen, LayoutDashboard } from 'lucide-react';

const NAV_LINKS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/tenders', label: 'Tender Library', icon: FileSearch },
  { to: '/compliance', label: 'Compliance', icon: BarChart3 },
  { to: '/reference-library', label: 'Reference Library', icon: BookOpen },
];

export function Navbar() {
  return (
    <header className="fixed top-0 inset-x-0 z-50">
      {/* Top bar */}
      <div className="bg-navy-deep h-13 flex items-center px-6 justify-between">
        <span className="text-white font-semibold text-sm tracking-wide">
          Tendering Intelligence
        </span>
        <span className="text-white/40 text-xs font-mono">NextGen Spark</span>
      </div>

      {/* Nav tab row */}
      <nav className="bg-navy flex items-center px-6 gap-1 border-b border-white/10">
        {NAV_LINKS.map(({ to, label, icon: Icon, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              `flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                isActive
                  ? 'text-white border-teal'
                  : 'text-white/60 border-transparent hover:text-white/90'
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
