import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';
import { useAuth } from './AuthContext';

const TenantContext = createContext();

export const useTenant = () => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error('useTenant must be used within a TenantProvider');
  }
  return context;
};

export const TenantProvider = ({ children }) => {
  const { token, user } = useAuth();
  const [tenant, setTenant] = useState({ id: 'tenant-default', name: 'REFYNE Enterprise Workspace', slug: 'refyne-enterprise' });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchTenant = async () => {
      if (token && user) {
        setLoading(true);
        try {
          const response = await api.get('/api/v1/tenants/current', {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (response.data) {
            setTenant(response.data);
          }
        } catch (err) {
          console.error('Failed to fetch tenant', err);
        } finally {
          setLoading(false);
        }
      }
    };
    fetchTenant();
  }, [token, user]);

  const value = {
    tenant,
    loading
  };

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
};