import { api } from './api';
import type { RequirementRecord } from '../types/models';

export const requirementService = {
  list: (projectId: string) => api<RequirementRecord[]>(`/api/projects/${projectId}/requirements`),
};
