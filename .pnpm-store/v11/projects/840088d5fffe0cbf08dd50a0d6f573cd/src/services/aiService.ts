import type { GenerateResponse, SearchResponse, DocumentGenerationResponse } from '../types/models';
import { api } from './api';

export type GenerationAction = 'brd' | 'srs' | 'rtm' | 'user_stories' | 'acceptance_criteria' | 'business_rules' | 'validation_rules' | 'edge_cases' | 'assumptions' | 'risk_analysis' | 'missing_requirements';

export const aiService = { 
  search: (projectId: string, query: string, document_ids?: string[]) => api<SearchResponse>(`/api/projects/${projectId}/search`, { method: 'POST', body: JSON.stringify({ query, top_k: 5, ...(document_ids?.length ? { document_ids } : {}) }) }), 
  generate: (projectId: string, query: string, document_ids?: string[]) => api<GenerateResponse>(`/api/projects/${projectId}/generate`, { method: 'POST', body: JSON.stringify({ query, top_k: 8, ...(document_ids?.length ? { document_ids } : {}) }) }),
  generateDocument: (projectId: string, action: GenerationAction) => api<DocumentGenerationResponse>(`/api/projects/${projectId}/generate/${action}`, { method: 'POST' })
};