import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { TenderListPage } from './pages/TenderListPage';
import { TenderDetailPage } from './pages/TenderDetailPage';
import { DocumentLibraryPage } from './pages/DocumentLibraryPage';
import { AccountPage } from './pages/AccountPage';
import { Loader2 } from 'lucide-react';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-text-mute" />
      </div>
    );
  }

  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Navbar />
            <main>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/tenders" element={<TenderListPage />} />
                <Route path="/tenders/:id" element={<TenderDetailPage />} />
                <Route path="/documents" element={<DocumentLibraryPage />} />
                <Route path="/account" element={<AccountPage />} />
              </Routes>
            </main>
          </ProtectedRoute>
        }
      />
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
