import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { HomePage } from './pages/HomePage';
import { AnalysisPage } from './pages/AnalysisPage';
import { ReportPage } from './pages/ReportPage';

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/analysis/:jobId" element={<AnalysisPage />} />
          <Route path="/report/:jobId" element={<ReportPage />} />
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  );
}