import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Loader2, ShieldOff } from 'lucide-react';
import { AuthProvider, useAuth, PLATFORM_ADMIN_EMAILS } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { InviteAcceptPage } from './pages/InviteAcceptPage';
import { DashboardPage } from './pages/DashboardPage';
import { TenderListPage } from './pages/TenderListPage';
import { TenderDetailPage } from './pages/TenderDetailPage';
import { DocumentLibraryPage } from './pages/DocumentLibraryPage';
import { AccountPage } from './pages/AccountPage';
import { OrgSettingsPage } from './pages/OrgSettingsPage';
import { PlatformAdminPage } from './pages/PlatformAdminPage';

function Spinner() {
  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center">
      <Loader2 size={20} className="animate-spin text-text-mute" />
    </div>
  );
}

function NoAccessWall() {
  const { user, signOut } = useAuth();
  return (
    <div className="min-h-screen bg-canvas flex flex-col items-center justify-center px-6">
      <div className="w-14 h-14 bg-navy/10 rounded-2xl flex items-center justify-center mb-5">
        <ShieldOff size={26} className="text-navy/40" />
      </div>
      <h1 className="text-xl font-semibold text-text mb-2">No access</h1>
      <p className="text-sm text-text-mute text-center max-w-xs mb-6 leading-relaxed">
        {user?.email && <><span className="text-text font-medium">{user.email}</span>{' '}</>}
        is not a member of any organisation on this platform. Contact your administrator for an invitation.
      </p>
      <button
        onClick={() => signOut()}
        className="text-sm text-text-mute hover:text-text transition-colors"
      >
        Sign out
      </button>
    </div>
  );
}

function GuestLayout() {
  const { session, loading } = useAuth();
  if (loading) return null;
  if (session) return <Navigate to="/" replace />;
  return <Outlet />;
}

function AuthLayout() {
  const { session, loading, orgCtx, orgLoading, user } = useAuth();

  if (loading || orgLoading) return <Spinner />;
  if (!session) return <Navigate to="/login" replace />;

  const isPlatformAdmin = PLATFORM_ADMIN_EMAILS.includes(user?.email ?? '');
  const hasAccess = isPlatformAdmin || !!orgCtx?.org_id;

  if (!hasAccess) return <NoAccessWall />;

  return (
    <>
      <Navbar />
      <Outlet />
    </>
  );
}

function AppRoutes() {
  return (
    <Routes>
      {/* Landing page — always accessible, auth-aware CTAs */}
      <Route index element={<LandingPage />} />

      {/* Public — no auth required */}
      <Route path="/invite/:token" element={<InviteAcceptPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Guest only — redirect to / if already logged in */}
      <Route element={<GuestLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<Navigate to="/" replace />} />
      </Route>

      {/* Authenticated */}
      <Route element={<AuthLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/tenders" element={<TenderListPage />} />
        <Route path="/tenders/:id" element={<TenderDetailPage />} />
        <Route path="/documents" element={<DocumentLibraryPage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/org/settings" element={<OrgSettingsPage />} />
        <Route path="/admin" element={<PlatformAdminPage />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster
          position="bottom-right"
          toastOptions={{ style: { fontFamily: 'IBM Plex Sans', fontSize: 13 } }}
        />
      </AuthProvider>
    </BrowserRouter>
  );
}
