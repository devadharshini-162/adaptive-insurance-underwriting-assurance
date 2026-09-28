import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import NewSubmission from './pages/NewSubmission';
import Questionnaire from './pages/Questionnaire';
import ReviewPage from './pages/ReviewPage';
import UnderwriterDashboard from './pages/UnderwriterDashboard';
import SubmissionDetail from './pages/SubmissionDetail';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <header className="app-header">
        <div className="header-left">
          <span className="app-logo">🛡 InsuranceAssurance</span>
        </div>
        <div className="header-right">
          <a href="/dashboard" className="header-link">Underwriter Dashboard</a>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<NewSubmission />} />
          <Route path="/questionnaire/:submissionId/:productId" element={<Questionnaire />} />
          <Route path="/review/:submissionId" element={<ReviewPage />} />
          <Route path="/dashboard" element={<UnderwriterDashboard />} />
          <Route path="/dashboard/:submissionId" element={<SubmissionDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

export default App;
