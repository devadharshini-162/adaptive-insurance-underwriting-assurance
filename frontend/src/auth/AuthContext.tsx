import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, getStoredSession, type UserRole } from '../services/api';

const SESSION_KEY = 'insurance-assurance.session';

interface Session {
  token: string;
  role: UserRole;
}

interface AuthContextValue {
  session: Session | null;
  login: (email: string, password: string, expectedRole: UserRole) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => getStoredSession());

  const logout = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  }, []);

  const login = useCallback(async (email: string, password: string, expectedRole: UserRole) => {
    const nextSession = await api.login(email, password);
    if (nextSession.role !== expectedRole) {
      throw new Error('This account does not have access to that portal. Please use the correct sign-in page.');
    }
    localStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
    setSession(nextSession);
  }, []);

  useEffect(() => {
    window.addEventListener('insurance-assurance:unauthorized', logout);
    return () => window.removeEventListener('insurance-assurance:unauthorized', logout);
  }, [logout]);

  const value = useMemo(() => ({ session, login, logout }), [session, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
