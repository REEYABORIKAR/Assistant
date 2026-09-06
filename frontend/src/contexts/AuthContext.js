import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadUser = async () => {
      if (token) {
        try {
          const response = await api.get('/api/v1/auth/me', {
            headers: { Authorization: `Bearer ${token}` }
          });
          const userData = response.data.user || response.data;
          setUser(userData);
        } catch (err) {
          // Token invalid or unauthenticated
          localStorage.removeItem('token');
          setToken('');
          setUser(null);
        }
      } else {
        // Safe fallback user for demo preview when not authenticated
        setUser({ id: 'demo-user-id', name: 'Demo Engineer', email: 'demo@refyne.ai' });
      }
      setLoading(false);
    };
    loadUser();
  }, [token]);

  const login = async (credentials) => {
    try {
      const response = await api.post('/api/v1/auth/login', credentials);
      const { access_token, user: loggedUser } = response.data;
      localStorage.setItem('token', access_token);
      setToken(access_token);
      if (loggedUser) {
        setUser(loggedUser);
      } else {
        const userResp = await api.get('/api/v1/auth/me', {
          headers: { Authorization: `Bearer ${access_token}` }
        });
        setUser(userResp.data.user || userResp.data);
      }
    } catch (err) {
      throw err;
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken('');
    setUser({ id: 'demo-user-id', name: 'Demo Engineer', email: 'demo@refyne.ai' });
  };

  const register = async (data) => {
    await api.post('/api/v1/auth/register', data);
  };

  const value = {
    token,
    user,
    loading,
    login,
    logout,
    register
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};