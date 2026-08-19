import { useState } from 'react';
import { Loader2, User, Mail, Lock, Building2, CheckCircle2 } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { useAuth } from '../context/AuthContext';
import toast from 'react-hot-toast';

export function AccountPage() {
  const { user } = useAuth();

  const displayName = (user?.user_metadata?.full_name as string) ?? '';
  const email = user?.email ?? '';
  const orgName = (user?.user_metadata?.org_name as string) ?? 'NextGen Spark';

  const [nameValue, setNameValue] = useState(displayName);
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [savingPw, setSavingPw] = useState(false);
  const [pwError, setPwError] = useState('');

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    setSavingProfile(true);
    const { error } = await supabase.auth.updateUser({ data: { full_name: nameValue } });
    setSavingProfile(false);
    if (error) toast.error(error.message);
    else toast.success('Profile updated');
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwError('');
    if (newPw !== confirmPw) { setPwError('Passwords do not match'); return; }
    if (newPw.length < 8) { setPwError('Password must be at least 8 characters'); return; }
    setSavingPw(true);
    // Re-authenticate first, then update password
    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password: currentPw });
    if (signInError) { setPwError('Current password is incorrect'); setSavingPw(false); return; }
    const { error } = await supabase.auth.updateUser({ password: newPw });
    setSavingPw(false);
    if (error) toast.error(error.message);
    else {
      toast.success('Password changed');
      setCurrentPw(''); setNewPw(''); setConfirmPw('');
    }
  }

  return (
    <div className="pt-[6.5rem] px-6 pb-12 max-w-2xl mx-auto">

      <div className="mb-6">
        <h1 className="text-xl font-bold text-text">Account Settings</h1>
        <p className="text-sm text-text-mute mt-0.5">Manage your profile and security</p>
      </div>

      {/* Profile card */}
      <div className="bg-panel border border-border rounded-xl p-6 mb-5">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-full bg-teal/20 flex items-center justify-center text-teal font-bold text-lg flex-shrink-0">
            {(nameValue || email).charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="text-sm font-semibold text-text">{nameValue || email}</p>
            <p className="text-xs text-text-mute mt-0.5 flex items-center gap-1.5">
              <Building2 size={11} /> {orgName}
            </p>
          </div>
        </div>

        <form onSubmit={handleSaveProfile} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
              <span className="flex items-center gap-1.5"><User size={11} /> Display Name</span>
            </label>
            <input
              value={nameValue}
              onChange={(e) => setNameValue(e.target.value)}
              placeholder="Your full name"
              className="w-full px-3 py-2.5 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
              <span className="flex items-center gap-1.5"><Mail size={11} /> Email Address</span>
            </label>
            <input
              value={email}
              disabled
              className="w-full px-3 py-2.5 text-sm bg-panel-2 border border-border rounded-lg text-text-mute cursor-not-allowed"
            />
            <p className="text-[11px] text-text-mute mt-1">Email cannot be changed. Contact your administrator.</p>
          </div>

          <div className="flex justify-end pt-1">
            <button
              type="submit"
              disabled={savingProfile}
              className="flex items-center gap-2 px-5 py-2 bg-navy hover:bg-navy-soft disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              {savingProfile ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
              {savingProfile ? 'Saving…' : 'Save Profile'}
            </button>
          </div>
        </form>
      </div>

      {/* Change password */}
      <div className="bg-panel border border-border rounded-xl p-6">
        <div className="flex items-center gap-2 mb-5">
          <Lock size={15} className="text-teal" />
          <h2 className="text-sm font-semibold text-text">Change Password</h2>
        </div>

        <form onSubmit={handleChangePassword} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">Current Password</label>
            <input
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              className="w-full px-3 py-2.5 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">New Password</label>
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                placeholder="Min 8 characters"
                autoComplete="new-password"
                className="w-full px-3 py-2.5 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">Confirm Password</label>
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                placeholder="Repeat new password"
                autoComplete="new-password"
                className="w-full px-3 py-2.5 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
              />
            </div>
          </div>

          {pwError && (
            <p className="text-xs text-red bg-red-bg border border-red/20 rounded-lg px-3 py-2">{pwError}</p>
          )}

          <div className="flex justify-end pt-1">
            <button
              type="submit"
              disabled={savingPw || !currentPw || !newPw || !confirmPw}
              className="flex items-center gap-2 px-5 py-2 bg-navy hover:bg-navy-soft disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
            >
              {savingPw ? <Loader2 size={14} className="animate-spin" /> : <Lock size={14} />}
              {savingPw ? 'Updating…' : 'Update Password'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
