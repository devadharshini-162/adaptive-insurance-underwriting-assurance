import { BrowserRouter, Routes, Route, Navigate, Link, useParams } from 'react-router-dom';
import NewSubmission from './pages/NewSubmission';
import CustomerDashboard from './pages/CustomerDashboard';
import ApplicationFlow from './pages/ApplicationFlow';
import Questionnaire from './pages/Questionnaire';
import ReviewPage from './pages/ReviewPage';
import UnderwriterDashboard from './pages/UnderwriterDashboard';
import SubmissionDetail from './pages/SubmissionDetail';
import LoginPage from './pages/LoginPage';
import { AuthProvider, useAuth } from './auth/AuthContext';
import ProtectedRoute from './auth/ProtectedRoute';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

function AppRoutes() {
  const { session, logout } = useAuth();
  const portal = session?.role === 'underwriter' ? '/underwriter' : '/customer';

  return (
    <>
      <header className="app-header">
        <div className="header-left">
          <Link to={portal} className="app-logo" aria-label="InsuranceAssurance home">InsuranceAssurance</Link>
        </div>
        <div className="header-right">
          {session && <>
            <Link to={portal} className="header-link">{session.role === 'underwriter' ? 'Underwriter portal' : 'Customer portal'}</Link>
            <button className="header-link header-button" onClick={logout}>Log out</button>
          </>}
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to={session ? portal : '/login/customer'} replace />} />
          <Route path="/login/customer" element={<LoginPage role="customer" />} />
          <Route path="/login/underwriter" element={<LoginPage role="underwriter" />} />
          <Route element={<ProtectedRoute role="customer" />}>
            <Route path="/customer" element={<CustomerDashboard />} />
            <Route path="/customer/new" element={<NewSubmission />} />
            <Route path="/application/:submissionId/:step" element={<ApplicationFlow />} />
            <Route path="/questionnaire/:submissionId/:productId" element={<Questionnaire />} />
            <Route path="/review/:submissionId" element={<ReviewPage />} />
          </Route>
          <Route element={<ProtectedRoute role="underwriter" />}>
            <Route path="/underwriter" element={<UnderwriterDashboard />} />
            <Route path="/underwriter/:submissionId" element={<SubmissionDetail />} />
            <Route path="/dashboard" element={<Navigate to="/underwriter" replace />} />
            <Route path="/dashboard/:submissionId" element={<LegacyDashboardRedirect />} />
          </Route>
          <Route path="*" element={<Navigate to={session ? portal : '/login/customer'} replace />} />
        </Routes>
      </main>
    </>
  );
}

function LegacyDashboardRedirect() {
  const { submissionId } = useParams();
  return <Navigate to={`/underwriter/${submissionId}`} replace />;
}

export default App;
