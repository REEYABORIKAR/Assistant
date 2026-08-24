import { api } from './api';
import type { ArtifactRecord } from '../types/models';

export const artifactService = {
  list: (projectId: string, type?: string) =>
    api<ArtifactRecord[]>(`/api/projects/${projectId}/artifacts${type ? `?type=${type}` : ''}`),
  get: (projectId: string, artifactId: string) =>
    api<ArtifactRecord>(`/api/projects/${projectId}/artifacts/${artifactId}`),
  create: (projectId: string, data: { type: string; title: string; file_name: string; content: string; version?: string }) =>
    api<ArtifactRecord>(`/api/projects/${projectId}/artifacts`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateStatus: (projectId: string, artifactId: string, status: string, comments?: string) =>
    api<ArtifactRecord>(`/api/projects/${projectId}/artifacts/${artifactId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status, comments }),
    }),
};
