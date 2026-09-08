import { createContext, useContext, useEffect, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import type { OrgContext } from '../types';

const PLATFORM_ADMIN_EMAILS = ['nextgenspark2025@gmail.com'];

interface AuthContextValue {
  user: User | null;
  session: Session | null;
  loading: boolean;
  orgCtx: OrgContext | null;
  orgLoading: boolean;
  signUp: (email: string, password: string) => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  refreshOrg: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchOrgContext(accessToken: string): Promise<OrgContext | null> {
  try {
    const response = await fetch(
      `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/orgs/me`,
      { headers: { Authorization: `Bearer ${accessToken}`, 'X-Platform': 'tendering' } },
    );
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [orgCtx, setOrgCtx] = useState<OrgContext | null>(null);
  const [orgLoading, setOrgLoading] = useState(false);

  async function loadOrg(currentUser: User | null, accessToken: string | undefined) {
    if (!currentUser || !accessToken) { setOrgCtx(null); return; }
    if (PLATFORM_ADMIN_EMAILS.includes(currentUser.email ?? '')) {
      setOrgCtx({ role: 'platform_admin' });
      return;
    }
    setOrgLoading(true);
    const context = await fetchOrgContext(accessToken);
    setOrgCtx(context);
    setOrgLoading(false);
  }

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const currentSession = data.session;
      setSession(currentSession);
      setUser(currentSession?.user ?? null);
      loadOrg(currentSession?.user ?? null, currentSession?.access_token).finally(() => setLoading(false));
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, updatedSession) => {
      setSession(updatedSession);
      setUser(updatedSession?.user ?? null);
      if (updatedSession) {
        localStorage.setItem('sb-session', JSON.stringify(updatedSession));
        loadOrg(updatedSession.user, updatedSession.access_token);
      } else {
        localStorage.removeItem('sb-session');
        setOrgCtx(null);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  async function refreshOrg() {
    if (session?.access_token) {
      await loadOrg(user, session.access_token);
    }
  }

  async function signUp(email: string, password: string) {
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
  }

  async function signInWithPassword(email: string, password: string) {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  }

  async function signInWithGoogle() {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/` },
    });
    if (error) throw error;
  }

  async function signOut() {
    await supabase.auth.signOut();
  }

  return (
    <AuthContext.Provider value={{
      user, session, loading, orgCtx, orgLoading,
      signUp, signInWithPassword, signInWithGoogle, signOut, refreshOrg,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const authContext = useContext(AuthContext);
  if (!authContext) throw new Error('useAuth must be used inside AuthProvider');
  return authContext;
}

export { PLATFORM_ADMIN_EMAILS };
