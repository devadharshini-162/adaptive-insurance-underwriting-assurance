import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import type { UserRole } from '../services/api';

export default function LoginPage({ role }: { role: UserRole }) {
  const { session, login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const portal = role === 'underwriter' ? '/underwriter' : '/customer';
  const title = role === 'underwriter' ? 'Underwriter sign in' : 'Customer sign in';

  if (session) return <Navigate to={session.role === 'underwriter' ? '/underwriter' : '/customer'} replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email, password, role);
      const from = location.state?.from?.pathname;
      navigate(from || portal, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'We could not sign you in. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <p className="auth-eyebrow">Insurance Assurance</p>
        <h1>{title}</h1>
        <p className="subtitle">
          {role === 'underwriter' ? 'Review and manage insurance applications.' : 'Start and manage your insurance application.'}
        </p>
        {error && <div className="error-box" role="alert">{error}</div>}
        <label htmlFor={`${role}-email`}>Email address</label>
        <input id={`${role}-email`} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <label htmlFor={`${role}-password`}>Password</label>
        <input id={`${role}-password`} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <button className="btn-primary" disabled={submitting} type="submit">{submitting ? 'Signing in…' : 'Sign in'}</button>
        <p className="auth-switch">
          {role === 'underwriter' ? <>Looking for the customer portal? <Link to="/login/customer">Customer sign in</Link></> : <>Are you an underwriter? <Link to="/login/underwriter">Underwriter sign in</Link></>}
        </p>
      </form>
    </div>
  );
}
