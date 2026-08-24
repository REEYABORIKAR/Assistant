import { api } from './api';
import type { DashboardStats } from '../types/models';

export const dashboardService = {
  stats: () => api<DashboardStats>('/api/dashboard/stats'),
};
