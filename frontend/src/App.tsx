import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './context/AuthContext'
import Navbar from './components/Navbar'
import CasesPage from './pages/CasesPage'
import CaseWorkspacePage from './pages/CaseWorkspacePage'
import AccountPage from './pages/AccountPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import InviteAcceptPage from './pages/InviteAcceptPage'
import PlatformAdminPage from './pages/PlatformAdminPage'
import OrgSettingsPage from './pages/OrgSettingsPage'

function AuthLayout() {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-canvas">
        <div className="w-5 h-5 border-2 border-teal border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return (
    <>
      <Navbar />
      <div className="min-h-[calc(100vh-3.25rem)]">
        <Outlet />
      </div>
    </>
  )
}

function GuestLayout() {
  const { user, loading } = useAuth()
  if (loading) return null
  if (user) return <Navigate to="/cases" replace />
  return <Outlet />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster position="top-right" toastOptions={{ style: { fontSize: '0.875rem' } }} />
        <Routes>
          {/* Public routes — no auth required */}
          <Route path="/invite/:token" element={<InviteAcceptPage />} />
          <Route element={<GuestLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Route>
          {/* Standalone — must not be inside GuestLayout (Supabase sets a recovery session on arrival) */}
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route element={<AuthLayout />}>
            <Route index element={<Navigate to="/cases" replace />} />
            <Route path="/cases" element={<CasesPage />} />
            <Route path="/cases/:caseId" element={<CaseWorkspacePage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/org-settings" element={<OrgSettingsPage />} />
            <Route path="/admin" element={<PlatformAdminPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
