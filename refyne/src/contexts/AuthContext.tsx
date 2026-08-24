import { createContext, useContext, useEffect, useState } from 'react';
import type { User } from '../types/models';
import { api, tokenStore } from '../services/api';

type State = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, full_name: string) => Promise<void>;
  logout: () => void;
};

const Context = createContext<State>({
  user: null,
  loading: true,
  login: async () => {},
  register: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = () => {
    tokenStore.clear();
    setUser(null);
  };

  const refresh = async () => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    try {
      setUser(await api<User>('/api/auth/me'));
    } catch {
      logout();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    window.addEventListener('refyne:unauthorized', logout);
    return () => window.removeEventListener('refyne:unauthorized', logout);
  }, []);

  const login = async (email: string, password: string) => {
    const result = await api<{ access_token: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    tokenStore.set(result.access_token);
    setUser(await api<User>('/api/auth/me'));
  };

  const register = async (email: string, password: string, full_name: string) => {
    await api<User>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name }),
    });
    await login(email, password);
  };

  return (
    <Context.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </Context.Provider>
  );
}

export const useAuth = () => useContext(Context);
