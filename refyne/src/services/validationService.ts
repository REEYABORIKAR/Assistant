import { api } from './api';
import type { ChecklistItem, ValidationRunRecord } from '../types/models';

export const validationService = {
  list: (projectId: string) => api<ValidationRunRecord[]>(`/api/projects/${projectId}/validations`),
  run: (projectId: string, data?: { artifact_id?: string; artifact_title?: string }) =>
    api<ValidationRunRecord>(`/api/projects/${projectId}/validations/run`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),
  review: (projectId: string, validationId: string, status: string, feedback?: string, checklist?: ChecklistItem[]) =>
    api<ValidationRunRecord>(`/api/projects/${projectId}/validations/${validationId}/review`, {
      method: 'PUT',
      body: JSON.stringify({ status, feedback, checklist }),
    }),
};
