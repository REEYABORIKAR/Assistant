export type Project = { id: string; user_id: string; name: string; description: string | null; created_at: string; updated_at: string };
export type Workspace = { id: string; project_id: string; name: string; created_at: string };
export type Chat = { id: string; project_id: string; user_id: string; title: string | null; created_at: string; updated_at: string };
export type ChatMessage = { id: string; chat_id: string; role: 'user' | 'assistant'; content: string; created_at: string };
export type DocumentRecord = { id: string; project_id: string; workspace_id: string; user_id: string; file_name: string; file_path: string; file_type: string | null; file_size: number | null; upload_status: string; uploaded_at: string };
