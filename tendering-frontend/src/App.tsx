import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Navbar } from './components/Navbar';
import { DashboardPage } from './pages/DashboardPage';
import { TenderListPage } from './pages/TenderListPage';
import { TenderDetailPage } from './pages/TenderDetailPage';
import { DocumentLibraryPage } from './pages/DocumentLibraryPage';

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <main>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/tenders" element={<TenderListPage />} />
          <Route path="/tenders/:id" element={<TenderDetailPage />} />
          <Route path="/documents" element={<DocumentLibraryPage />} />
        </Routes>
      </main>
      <Toaster position="bottom-right" toastOptions={{ style: { fontFamily: 'IBM Plex Sans', fontSize: 13 } }} />
    </BrowserRouter>
  );
}
