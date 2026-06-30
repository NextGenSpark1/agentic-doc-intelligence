import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AccountPage() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="max-w-screen-sm mx-auto px-6 py-10 flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-text">Account</h1>
        <p className="text-sm text-text-mute mt-0.5">Your profile and session settings</p>
      </div>

      {/* Profile card */}
      <div className="bg-panel border border-border rounded-xl shadow-sm p-6 flex flex-col gap-4">
        <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Profile</p>
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-teal rounded-full flex items-center justify-center text-white font-semibold text-sm shrink-0">
            {user?.email ? user.email.slice(0, 2).toUpperCase() : '??'}
          </div>
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium text-text">{user?.email ?? '—'}</p>
            <p className="text-xs text-text-mute">Signed in via Supabase Auth</p>
          </div>
        </div>
        <button
          onClick={handleSignOut}
          className="flex items-center gap-2 text-sm text-text-mid hover:text-text border border-border hover:border-border-strong rounded-lg px-4 py-2.5 transition-colors duration-150 w-fit"
        >
          <LogOut size={14} className="text-text-mute" />
          Sign out
        </button>
      </div>

      {/* Preferences placeholder */}
      <div className="bg-panel border border-border rounded-xl shadow-sm p-6 flex flex-col gap-3">
        <p className="text-[10px] font-semibold text-text-mute uppercase tracking-wider">Preferences</p>
        <p className="text-sm text-text-mute">More settings coming soon.</p>
      </div>
    </div>
  )
}
