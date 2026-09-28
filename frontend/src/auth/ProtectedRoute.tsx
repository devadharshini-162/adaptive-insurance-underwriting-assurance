import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import type { UserRole } from '../services/api';

export default function ProtectedRoute({ role }: { role: UserRole }) {
  const { session } = useAuth();
  const location = useLocation();

  if (!session) {
    return <Navigate to={role === 'underwriter' ? '/login/underwriter' : '/login/customer'} replace state={{ from: location }} />;
  }

  if (session.role !== role) {
    return <Navigate to={session.role === 'underwriter' ? '/underwriter' : '/customer'} replace />;
  }

  return <Outlet />;
}
