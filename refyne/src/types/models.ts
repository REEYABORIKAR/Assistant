export type User = { id: string; email: string; full_name: string; created_at?: string };
export type Project = { id: string; user_id: string; name: string; description: string | null; created_at: string; updated_at: string };
export type Workspace = { id: string; project_id: string; name: string; created_at: string; updated_at: string };
export type DocumentRecord = { id: string; project_id: string; workspace_id: string; file_name: string; file_type: string; file_size: number; status: string; error_message?: string | null; created_at: string; updated_at: string };
export type Citation = { document_id?: string; document_name?: string; file_name?: string; page?: number | null; chunk_index?: number | null; chunk_id?: string; display_text?: string; source_type?: string; [key: string]: unknown };
export type SearchResult = { content?: string; text?: string; score?: number; hybrid_score?: number; rerank_score?: number | null; file_name?: string; citation: Citation; metadata?: Record<string, unknown>; [key: string]: unknown };
export type SearchMetadata = { semantic_results_count?: number; bm25_results_count?: number; merged_candidates_count?: number; final_results_count?: number; query_expansion_enabled?: boolean; expanded_query?: string | null; rerank_enabled?: boolean; rerank_results_count?: number; [key: string]: unknown };
export type SearchResponse = { results?: SearchResult[]; citations?: Citation[]; source_documents?: Array<{ document_id: string; file_name: string }>; context?: string; metadata?: SearchMetadata; retrieval_metadata?: Record<string, unknown>; [key: string]: unknown };
export type GenerateResponse = { query?: string; project_id?: string; answer?: string; configured?: boolean; message?: string | null; citations?: Citation[]; source_documents?: Array<{ document_id: string; file_name: string }>; context?: string; metadata?: SearchMetadata; [key: string]: unknown };
export type Conversation = { id: string; project_id: string; title: string; pinned?: boolean; created_at: string; updated_at: string };
export type ChatMessage = { id: string; conversation_id: string; role: 'user' | 'assistant'; content: string; created_at: string; citations?: Citation[] };
export type DocumentGenerationResponse = { title: string; content: string; action: string; citations?: Citation[]; source_documents?: Array<{ document_id: string; file_name: string }> };
export type SupervisorChatResponse = { intent: string; route: string; requires_rag: boolean; confidence: number; workflow_status: string; session_id: string; conversation_id: string; content?: string | null; title?: string | null; action?: string | null; citations?: Citation[]; source_documents?: Array<{ document_id: string; file_name: string }>; error?: string | null };

export type ArtifactRecord = {
  id: string;
  project_id: string;
  type: string;
  title: string;
  file_name: string;
  version: string;
  content: string;
  status: 'pending_validation' | 'approved' | 'changes_requested' | 'rejected';
  approved_by?: string | null;
  approved_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type RequirementRecord = {
  id: string;
  project_id: string;
  req_code: string;
  title: string;
  description: string;
  category: string;
  priority: string;
  source_doc?: string | null;
  user_story?: string | null;
  acceptance_criteria?: string | null;
  brd_ref?: string | null;
  srs_ref?: string | null;
  test_case?: string | null;
  status: 'Linked' | 'Unlinked' | 'Pending';
  created_at: string;
};

export type ChecklistItem = {
  id: string;
  label: string;
  checked: boolean;
};

export type ValidationRunRecord = {
  id: string;
  project_id: string;
  artifact_id?: string | null;
  artifact_title: string;
  status: 'approved' | 'needs_review' | 'changes_requested';
  total_requirements: number;
  valid_requirements: number;
  issues_found: number;
  ambiguities: number;
  gaps_identified: number;
  feedback?: string | null;
  checklist: ChecklistItem[];
  created_at: string;
};

export type RecentProjectItem = {
  id: string;
  name: string;
  updated_at: string;
  documents_count: number;
  requirements_count: number;
};

export type RecentActivityItem = {
  id: string;
  action: string;
  description: string;
  timestamp: string;
  project_name?: string | null;
};

export type DashboardStats = {
  total_projects: number;
  total_documents: number;
  total_requirements: number;
  total_validations: number;
  recent_projects: RecentProjectItem[];
  recent_activities: RecentActivityItem[];
};
