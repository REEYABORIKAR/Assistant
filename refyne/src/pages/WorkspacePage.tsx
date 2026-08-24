import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Bot, Mic, Plus, Send, Pin, Trash2,
  MessageSquare, FileText, CheckCircle2, Link2, FolderKanban, Settings,
  Eye, Upload
} from 'lucide-react';
import type {
  ChatMessage, Conversation, Project, Workspace, DocumentRecord,
  ArtifactRecord, RequirementRecord, ValidationRunRecord, ChecklistItem
} from '../types/models';
import { projectService } from '../services/projectService';
import { chatService } from '../services/chatService';
import { aiService } from '../services/aiService';
import { documentService } from '../services/documentService';
import { artifactService } from '../services/artifactService';
import { requirementService } from '../services/requirementService';
import { validationService } from '../services/validationService';
import { SupervisorAgent, type ChatBlock, createBlockId } from '../components/SupervisorAgent';
import { DocumentViewerModal } from '../components/DocumentViewerModal';
import { ValidationModal } from '../components/ValidationModal';
import { DocumentUploadModal } from '../components/DocumentUploadModal';

type WorkspaceTab = 'chat' | 'documents' | 'requirements' | 'validations' | 'traceability' | 'artifacts' | 'settings';

export function WorkspacePage() {
  const { projectId, conversationId } = useParams();
  const nav = useNavigate();
  const textInputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  // Active Tab
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('chat');

  // Core Data
  const [project, setProject] = useState<Project>();
  const [workspace, setWorkspace] = useState<Workspace>();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<Conversation>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [requirements, setRequirements] = useState<RequirementRecord[]>([]);
  const [validations, setValidations] = useState<ValidationRunRecord[]>([]);

  // UI State
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [recording, setRecording] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState('');
  const [hasDocuments, setHasDocuments] = useState(false);
  const [artifactFilter, setArtifactFilter] = useState('ALL');

  // Modals state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [viewingArtifact, setViewingArtifact] = useState<{ title: string; content: string; version?: string; status?: string } | null>(null);
  const [validatingRun, setValidatingRun] = useState<{ run?: ValidationRunRecord; title?: string } | null>(null);

  // Timeline blocks
  const [blocks, setBlocks] = useState<ChatBlock[]>([]);

  const appendBlock = useCallback((block: ChatBlock) => {
    setBlocks(prev => [...prev, block]);
  }, []);

  const openConversation = async (conversation: Conversation) => {
    setActive(conversation);
    const msgs = await chatService.messages(conversation.id);
    setMessages(msgs);
    const hasWelcome = msgs.length >= 2 && msgs[0].role === 'assistant' && msgs[1].role === 'assistant';
    setBlocks(hasWelcome ? [{ id: createBlockId(), type: 'action_buttons' }] : []);
    nav(`/app/projects/${projectId}/chat/${conversation.id}`);
  };

  const loadData = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [p, w, c, docs, arts, reqs, vals] = await Promise.all([
        projectService.get(projectId),
        projectService.workspace(projectId),
        chatService.list(projectId),
        documentService.list(projectId).catch(() => []),
        artifactService.list(projectId).catch(() => []),
        requirementService.list(projectId).catch(() => []),
        validationService.list(projectId).catch(() => []),
      ]);

      setProject(p);
      setWorkspace(w);
      setConversations(c);
      setDocuments(docs);
      setArtifacts(arts);
      setRequirements(reqs);
      setValidations(vals);
      setHasDocuments(docs.some(d => d.status === 'indexed'));

      const chosen = c.find(x => x.id === conversationId) || c[0];
      if (chosen) {
        await openConversation(chosen);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load project workspace.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [projectId, conversationId]);

  const createChat = async () => {
    if (!projectId) return;
    const c = await chatService.create(projectId);
    setConversations(x => [c, ...x]);
    await openConversation(c);
    const welcomeMsg1 = await chatService.message(c.id, 'assistant', 'Hi! I\'m your AI Requirement Engineering Assistant. How can I help you today?');
    const welcomeMsg2 = await chatService.message(c.id, 'assistant', 'Upload source documents or click any action below to generate BRD, SRS, User Stories, or RTM.');
    setMessages([welcomeMsg1, welcomeMsg2]);
    setBlocks([{ id: createBlockId(), type: 'action_buttons' }]);
  };

  // ─── Chat Send ─────────────────────────────────────────────────────────────
  const send = useCallback(async (event?: React.FormEvent) => {
    if (event) event.preventDefault();
    if (!projectId || !active || !text.trim()) return;
    if (!hasDocuments) {
      setError('Please upload and index at least one document before asking questions.');
      return;
    }
    const question = text.trim();
    setText('');
    setBusy(true);
    setError('');
    setBlocks([]);
    try {
      const userMsg = await chatService.message(active.id, 'user', question);
      setMessages(x => [...x, userMsg]);

      const response = await aiService.supervisorChat(projectId, active.id, question);
      const content = response.content || 'No response from the Supervisor.';
      const citations = response.citations || [];

      const assistantMsg = await chatService.message(active.id, 'assistant', content, citations);
      setMessages(x => [...x, assistantMsg]);

      appendBlock({ id: createBlockId(), type: 'next_action_buttons' });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to process request.');
    } finally {
      setBusy(false);
    }
  }, [projectId, active, text, hasDocuments]);

  // ─── Generate Document ─────────────────────────────────────────────────────
  const handleGenerateDocument = useCallback(async (action: string) => {
    if (!projectId || !active || busy) return;
    if (!hasDocuments) {
      setError('Please upload and index at least one document before generating artifacts.');
      return;
    }
    setBusy(true);
    setError('');
    setBlocks([]);

    const generatingId = createBlockId();
    appendBlock({ id: generatingId, type: 'generating', documentType: action });

    try {
      const response = await aiService.supervisorChat(projectId, active.id, `Generate ${action}`, { action });
      const content = response.content || '';
      const title = response.title || action.toUpperCase();

      setBlocks(prev => prev.filter(b => b.id !== generatingId));

      appendBlock({
        id: createBlockId(),
        type: 'document_result',
        title: title,
        size: '2.4 MB',
        content: content,
      });

      appendBlock({ id: createBlockId(), type: 'next_action_buttons' });
      // Refresh artifacts list
      artifactService.list(projectId).then(setArtifacts).catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to generate document.');
      setBlocks(prev => prev.filter(b => b.id !== generatingId));
    } finally {
      setBusy(false);
    }
  }, [projectId, active, busy, appendBlock, hasDocuments]);

  // ─── Validation Review Handlers ───────────────────────────────────────────
  const handleApproveValidation = async (feedback: string, checklist: ChecklistItem[]) => {
    if (!projectId || !validatingRun) return;
    setBusy(true);
    try {
      if (validatingRun.run) {
        await validationService.review(projectId, validatingRun.run.id, 'approved', feedback, checklist);
      }
      setValidatingRun(null);
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to approve validation');
    } finally {
      setBusy(false);
    }
  };

  const handleRequestChangesValidation = async (feedback: string, checklist: ChecklistItem[]) => {
    if (!projectId || !validatingRun) return;
    setBusy(true);
    try {
      if (validatingRun.run) {
        await validationService.review(projectId, validatingRun.run.id, 'changes_requested', feedback, checklist);
      }
      setValidatingRun(null);
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to request changes');
    } finally {
      setBusy(false);
    }
  };

  const handleVoiceToggle = useCallback(() => {
    if (recording) {
      recognitionRef.current?.stop();
      setRecording(false);
      return;
    }
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      setError('Speech recognition is not supported in this browser.');
      return;
    }
    const recognition = new SpeechRecognitionAPI();
    recognition.continuous = false;
    recognition.lang = 'en-US';
    recognition.onresult = (e: SpeechRecognitionEvent) => {
      setText(prev => (prev ? `${prev} ${e.results[0][0].transcript}` : e.results[0][0].transcript));
    };
    recognition.onend = () => setRecording(false);
    recognitionRef.current = recognition;
    recognition.start();
    setRecording(true);
  }, [recording]);

  if (loading) return <div className="p-8 font-medium text-slate-500">Loading workspace...</div>;
  if (!project) return <div className="p-8 text-rose-600 font-semibold">{error || 'Project not found.'}</div>;

  const filteredArtifacts = artifacts.filter(art => {
    if (artifactFilter === 'ALL') return true;
    return art.type.toUpperCase() === artifactFilter;
  });

  return (
    <div className="flex h-screen flex-col bg-slate-100 overflow-hidden">
      {/* Workspace Header matching UI flow */}
      <header className="flex h-16 shrink-0 items-center justify-between border-b bg-white px-6">
        <div className="flex items-center gap-3">
          <button onClick={() => nav('/app/projects')} className="inline-flex items-center gap-1 text-xs font-semibold text-violet-600 hover:underline">
            <ArrowLeft size={14} /> Projects
          </button>
          <span className="text-slate-300">/</span>
          <h1 className="text-base font-bold text-slate-900">{project.name}</h1>
          <span className="rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-semibold text-violet-700">
            {workspace?.name || 'Workspace'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowUploadModal(true)} className="btn-primary flex items-center gap-2 py-1.5 px-3 text-xs font-semibold">
            <Upload size={14} /> Upload Document
          </button>
        </div>
      </header>

      {/* Main Content Split: Navigation Sidebar + Tab Content + Project Info Right Panel */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* Left Navigation Sidebar matching UI flow diagram */}
        <aside className="w-56 shrink-0 border-r bg-white flex flex-col p-3 space-y-1 select-none">
          <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">Navigation</p>
          <NavItem active={activeTab === 'chat'} icon={MessageSquare} label="Chat" onClick={() => setActiveTab('chat')} />
          <NavItem active={activeTab === 'documents'} icon={FileText} label="Documents" count={documents.length} onClick={() => setActiveTab('documents')} />
          <NavItem active={activeTab === 'requirements'} icon={FolderKanban} label="Requirements" count={requirements.length} onClick={() => setActiveTab('requirements')} />
          <NavItem active={activeTab === 'validations'} icon={CheckCircle2} label="Validations" count={validations.length} onClick={() => setActiveTab('validations')} />
          <NavItem active={activeTab === 'traceability'} icon={Link2} label="Traceability (RTM)" onClick={() => setActiveTab('traceability')} />
          <NavItem active={activeTab === 'artifacts'} icon={FileText} label="Generated Docs" count={artifacts.length} onClick={() => setActiveTab('artifacts')} />
          <NavItem active={activeTab === 'settings'} icon={Settings} label="Settings" onClick={() => setActiveTab('settings')} />

          {/* Conversations Section */}
          <div className="mt-6 pt-4 border-t flex-1 overflow-auto">
            <div className="flex items-center justify-between px-3 mb-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Chat Conversations</p>
              <button onClick={createChat} className="text-violet-600 hover:bg-violet-50 p-1 rounded-md" title="New Chat"><Plus size={14}/></button>
            </div>
            <div className="space-y-1">
              {conversations.map(c => (
                <div key={c.id} className={`group flex items-center rounded-lg ${active?.id === c.id ? 'bg-violet-50 text-violet-700 font-semibold' : 'text-slate-600 hover:bg-slate-50'}`}>
                  <button onClick={() => { openConversation(c); setActiveTab('chat'); }} className="flex flex-1 items-center gap-2 truncate px-3 py-1.5 text-left text-xs">
                    {c.pinned && <Pin size={12} className="shrink-0 text-violet-500" />}
                    <span className="truncate">{c.title}</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Center Main Tab View */}
        <main className="flex min-w-0 flex-1 flex-col bg-slate-50 overflow-hidden">
          {error && <div className="m-4 rounded-xl bg-rose-50 p-3 text-xs text-rose-700">{error}</div>}

          {/* TAB 1: CHAT */}
          {activeTab === 'chat' && (
            <div className="flex h-full flex-col overflow-hidden">
              <div className="flex-1 overflow-auto p-6 space-y-4">
                {!active ? (
                  <div className="grid h-full place-items-center text-center">
                    <div>
                      <Bot className="mx-auto text-violet-600 h-12 w-12" />
                      <h2 className="mt-3 font-bold text-slate-800 text-lg">No conversation selected</h2>
                      <button className="btn-primary mt-4" onClick={createChat}>Start New Chat</button>
                    </div>
                  </div>
                ) : (
                  <>
                    {messages.map((m) => (
                      <article key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-3xl rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                          m.role === 'user' ? 'bg-violet-600 text-white shadow-sm' : 'border bg-white text-slate-800 shadow-sm'
                        }`}>
                          <p className="whitespace-pre-wrap">{m.content}</p>
                          {m.citations?.length ? (
                            <div className="mt-3 border-t pt-2 text-xs text-slate-500 space-y-1">
                              <p className="font-bold text-violet-700">Sources & Citations:</p>
                              {m.citations.map((c, idx) => (
                                <div key={idx} className="flex items-center gap-2 bg-slate-50 p-1.5 rounded-md text-[11px]">
                                  <FileText size={12} className="text-violet-600" />
                                  <span>{String(c.document_name || c.file_name || 'Source document')}{c.page ? ` · Page ${c.page}` : ''}</span>
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </article>
                    ))}

                    {!hasDocuments && (
                      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800 flex items-center justify-between">
                        <div>
                          <p className="font-bold">No documents indexed yet</p>
                          <p className="mt-0.5">Upload a requirement document to ask questions or generate BRD/SRS.</p>
                        </div>
                        <button onClick={() => setShowUploadModal(true)} className="btn-primary py-1.5 px-3 text-xs">
                          Upload Now
                        </button>
                      </div>
                    )}

                    <SupervisorAgent
                      blocks={blocks}
                      disabled={busy}
                      hasDocuments={hasDocuments}
                      onUploadDocument={() => setShowUploadModal(true)}
                      onViewDashboard={() => nav('/app/dashboard')}
                      onGenerateDocument={handleGenerateDocument}
                      onAskAnotherQuestion={() => setBlocks([])}
                      onNoThanksFirst={() => setBlocks([{ id: createBlockId(), type: 'waiting_message' }])}
                      onNoThanksConfirm={() => setBlocks([{ id: createBlockId(), type: 'waiting_message' }])}
                      onNextAction={(act) => {
                        if (act === 'generate') setBlocks([{ id: createBlockId(), type: 'action_buttons' }]);
                        else if (act === 'ask') setBlocks([]);
                        else setBlocks([{ id: createBlockId(), type: 'confirm_no_thanks_buttons' }]);
                      }}
                      onFeedback={() => setBlocks([{ id: createBlockId(), type: 'next_action_buttons' }])}
                      onPreviewDocument={(t, c) => setViewingArtifact({ title: t, content: c })}
                      onValidateNow={(t, c) => setValidatingRun({ title: t })}
                    />
                  </>
                )}
              </div>

              {/* Chat Input Bar */}
              <form onSubmit={send} className="border-t bg-white p-4">
                <div className="flex items-end gap-2 max-w-4xl mx-auto">
                  <button type="button" onClick={() => setShowUploadModal(true)} className="rounded-xl p-2.5 text-slate-500 hover:bg-slate-100" title="Upload Document">
                    <Plus size={20} />
                  </button>
                  <textarea
                    ref={textInputRef}
                    className="field m-0 min-h-11 flex-1 py-2 text-sm"
                    rows={1}
                    value={text}
                    onChange={e => setText(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        send();
                      }
                    }}
                    placeholder={hasDocuments ? "Ask anything based on your uploaded documents..." : "Upload a document first to start chatting..."}
                  />
                  <button type="button" onClick={handleVoiceToggle} className={`rounded-xl p-2.5 transition ${recording ? 'bg-rose-100 text-rose-600' : 'text-slate-500 hover:bg-slate-100'}`} title="Voice input">
                    <Mic size={20} />
                  </button>
                  <button className="btn-primary px-4 py-2.5" disabled={!active || !text.trim() || busy || !hasDocuments}>
                    {busy ? 'Thinking...' : <Send size={18} />}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* TAB 2: DOCUMENTS */}
          {activeTab === 'documents' && (
            <div className="p-6 overflow-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">Project Documents</h2>
                  <p className="text-xs text-slate-500">Source documents parsed and indexed into Qdrant for RAG context.</p>
                </div>
                <button onClick={() => setShowUploadModal(true)} className="btn-primary flex items-center gap-2 py-2 px-4 text-xs font-semibold">
                  <Upload size={14} /> Upload New Document
                </button>
              </div>

              {documents.length === 0 ? (
                <div className="rounded-2xl border bg-white p-12 text-center">
                  <FileText className="mx-auto h-12 w-12 text-slate-300 mb-3" />
                  <h3 className="font-bold text-slate-800">No documents uploaded</h3>
                  <p className="text-xs text-slate-500 mt-1">Upload PDF, DOCX, or TXT files to enable AI answers and artifact generation.</p>
                  <button onClick={() => setShowUploadModal(true)} className="btn-primary mt-4 py-2 px-4 text-xs">
                    Upload Document
                  </button>
                </div>
              ) : (
                <div className="rounded-2xl border bg-white overflow-hidden shadow-sm">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b bg-slate-50 text-xs font-semibold text-slate-500">
                      <tr>
                        <th className="p-4">Document Name</th>
                        <th>Type</th>
                        <th>Size</th>
                        <th>Status</th>
                        <th>Uploaded On</th>
                        <th className="text-right p-4">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {documents.map(doc => (
                        <tr key={doc.id} className="hover:bg-slate-50/50">
                          <td className="p-4 font-semibold text-slate-800 flex items-center gap-2">
                            <FileText size={16} className="text-violet-600" />
                            {doc.file_name}
                          </td>
                          <td className="text-slate-600 text-xs">{doc.file_type || 'PDF'}</td>
                          <td className="text-slate-600 text-xs">{(doc.file_size / 1024).toFixed(1)} KB</td>
                          <td>
                            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
                              {doc.status}
                            </span>
                          </td>
                          <td className="text-slate-500 text-xs">{new Date(doc.updated_at).toLocaleDateString()}</td>
                          <td className="p-4 text-right">
                            <button onClick={() => documentService.remove(doc.id).then(loadData)} className="text-rose-600 hover:bg-rose-50 p-1.5 rounded-lg" title="Delete Document">
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: REQUIREMENTS */}
          {activeTab === 'requirements' && (
            <div className="p-6 overflow-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">Extracted Requirements Repository</h2>
                  <p className="text-xs text-slate-500">Structured functional and non-functional requirements extracted from source docs.</p>
                </div>
              </div>

              <div className="rounded-2xl border bg-white overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="border-b bg-slate-50 text-xs font-semibold text-slate-500">
                    <tr>
                      <th className="p-4">Req Code</th>
                      <th>Title & Description</th>
                      <th>Category</th>
                      <th>Priority</th>
                      <th>Source Document</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {requirements.map(req => (
                      <tr key={req.id} className="hover:bg-slate-50/50">
                        <td className="p-4 font-mono font-bold text-violet-700 text-xs">{req.req_code}</td>
                        <td className="p-4">
                          <p className="font-semibold text-slate-800">{req.title}</p>
                          <p className="text-xs text-slate-500 mt-0.5">{req.description}</p>
                        </td>
                        <td className="text-xs text-slate-600">{req.category}</td>
                        <td>
                          <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700">
                            {req.priority}
                          </span>
                        </td>
                        <td className="text-xs text-slate-500">{req.source_doc || 'Software_Requirements.pdf'}</td>
                        <td>
                          <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
                            {req.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 4: VALIDATIONS */}
          {activeTab === 'validations' && (
            <div className="p-6 overflow-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">AI & Human Validation Runs</h2>
                  <p className="text-xs text-slate-500">Quality evaluation, structural consistency check, and human review approvals.</p>
                </div>
                <button onClick={() => setValidatingRun({ title: 'BRD_E-Commerce_Platform.md' })} className="btn-primary flex items-center gap-2 py-2 px-4 text-xs font-semibold">
                  <CheckCircle2 size={14} /> Run New Validation
                </button>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {validations.map(val => (
                  <div key={val.id} className="rounded-2xl border bg-white p-5 shadow-sm space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-slate-800 text-base">{val.artifact_title}</h3>
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        val.status === 'approved' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                      }`}>
                        {val.status === 'approved' ? 'Approved' : 'Needs Review'}
                      </span>
                    </div>

                    <div className="grid grid-cols-4 gap-2 text-center text-xs border-y py-3">
                      <div><p className="text-slate-400">Total</p><p className="font-bold text-slate-800">{val.total_requirements}</p></div>
                      <div><p className="text-emerald-600">Valid</p><p className="font-bold text-emerald-700">{val.valid_requirements}</p></div>
                      <div><p className="text-rose-600">Issues</p><p className="font-bold text-rose-700">{val.issues_found}</p></div>
                      <div><p className="text-amber-600">Gaps</p><p className="font-bold text-amber-700">{val.gaps_identified}</p></div>
                    </div>

                    <p className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-xl">{val.feedback || 'Automated validation check passed.'}</p>

                    <button onClick={() => setValidatingRun({ run: val, title: val.artifact_title })} className="btn-primary w-full py-2 text-xs font-semibold">
                      Review & Approve Checklist
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 5: TRACEABILITY MATRIX (RTM VIEW) matching Screen 12 */}
          {activeTab === 'traceability' && (
            <div className="p-6 overflow-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">Requirements Traceability Matrix (RTM View)</h2>
                  <p className="text-xs text-slate-500">End-to-end matrix mapping requirements to source, BRD, SRS, User Stories, and Test Cases.</p>
                </div>
              </div>

              <div className="rounded-2xl border bg-white overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="border-b bg-slate-50 text-xs font-semibold text-slate-500">
                    <tr>
                      <th className="p-4">Req ID</th>
                      <th>Requirement Title</th>
                      <th>Source Doc</th>
                      <th>BRD Ref</th>
                      <th>SRS Ref</th>
                      <th>User Story</th>
                      <th>Acceptance Criteria</th>
                      <th>Test Case</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {requirements.map(req => (
                      <tr key={req.id} className="hover:bg-slate-50/50 text-xs">
                        <td className="p-4 font-mono font-bold text-violet-700">{req.req_code}</td>
                        <td className="font-medium text-slate-800">{req.title}</td>
                        <td className="text-slate-500">{req.source_doc || 'Software_Requirements.pdf'}</td>
                        <td className="font-mono text-slate-600">{req.brd_ref || 'BRD-1.2'}</td>
                        <td className="font-mono text-slate-600">{req.srs_ref || 'SRS-2.1'}</td>
                        <td className="font-mono text-slate-600">{req.user_story || 'US-001'}</td>
                        <td className="text-slate-600">{req.acceptance_criteria || 'AC-001, AC-002'}</td>
                        <td className="font-mono text-slate-600">{req.test_case || 'TC-01'}</td>
                        <td className="p-4">
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
                            <Link2 size={12} /> Linked
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 6: GENERATED DOCS / ALL ARTIFACTS matching Screen 13 */}
          {activeTab === 'artifacts' && (
            <div className="p-6 overflow-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">Generated Requirement Artifacts</h2>
                  <p className="text-xs text-slate-500">Repository of versioned BRD, SRS, RTM, User Stories, and Validation Reports.</p>
                </div>
              </div>

              {/* Filter Tabs matching Screen 13 */}
              <div className="flex gap-2 border-b pb-3">
                {['ALL', 'BRD', 'SRS', 'RTM', 'USER_STORIES', 'VALIDATION'].map(cat => (
                  <button
                    key={cat}
                    onClick={() => setArtifactFilter(cat)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                      artifactFilter === cat ? 'bg-violet-600 text-white shadow-sm' : 'bg-white text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {cat.replace('_', ' ')}
                  </button>
                ))}
              </div>

              <div className="rounded-2xl border bg-white overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="border-b bg-slate-50 text-xs font-semibold text-slate-500">
                    <tr>
                      <th className="p-4">Document Name</th>
                      <th>Type</th>
                      <th>Version</th>
                      <th>Status</th>
                      <th>Approved On</th>
                      <th className="text-right p-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {filteredArtifacts.map(art => (
                      <tr key={art.id} className="hover:bg-slate-50/50">
                        <td className="p-4 font-semibold text-slate-800 flex items-center gap-2">
                          <FileText size={16} className="text-violet-600" />
                          {art.file_name}
                        </td>
                        <td className="text-xs font-bold uppercase text-slate-500">{art.type}</td>
                        <td className="text-xs font-mono">{art.version}</td>
                        <td>
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                            art.status === 'approved' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                          }`}>
                            {art.status === 'approved' ? 'Approved' : 'Pending Validation'}
                          </span>
                        </td>
                        <td className="text-xs text-slate-500">{art.approved_at ? new Date(art.approved_at).toLocaleDateString() : '—'}</td>
                        <td className="p-4 text-right flex items-center justify-end gap-2">
                          <button onClick={() => setViewingArtifact({ title: art.title, content: art.content, version: art.version, status: art.status })} className="p-1.5 rounded-lg border text-slate-600 hover:bg-slate-100" title="Preview Document">
                            <Eye size={14} />
                          </button>
                          <button onClick={() => setValidatingRun({ title: art.title })} className="btn-primary py-1 px-3 text-xs">
                            Validate
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 7: SETTINGS */}
          {activeTab === 'settings' && (
            <div className="p-6 overflow-auto max-w-2xl space-y-6">
              <h2 className="text-xl font-bold text-slate-900">Project Settings</h2>
              <div className="rounded-2xl border bg-white p-6 space-y-4 shadow-sm">
                <div>
                  <label className="label">Project Name</label>
                  <input className="field" defaultValue={project.name} />
                </div>
                <div>
                  <label className="label">Description</label>
                  <textarea className="field" rows={3} defaultValue={project.description || ''} />
                </div>
                <button className="btn-primary px-5 py-2 text-xs font-semibold">Save Changes</button>
              </div>
            </div>
          )}
        </main>

        {/* Right Info Panel (Project Info) matching Screen 3 */}
        <aside className="w-64 shrink-0 border-l bg-white p-5 hidden xl:block overflow-auto">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">Project Info</h3>
          <div className="space-y-4 text-xs">
            <div>
              <p className="text-slate-400 font-medium">Name</p>
              <p className="font-bold text-slate-900 text-sm mt-0.5">{project.name}</p>
            </div>
            <div>
              <p className="text-slate-400 font-medium">Created On</p>
              <p className="font-semibold text-slate-700 mt-0.5">{new Date(project.created_at).toLocaleDateString()}</p>
            </div>
            <div className="border-t pt-3 grid grid-cols-2 gap-2">
              <div>
                <p className="text-slate-400 font-medium">Documents</p>
                <p className="font-bold text-slate-900 text-lg">{documents.length}</p>
              </div>
              <div>
                <p className="text-slate-400 font-medium">Requirements</p>
                <p className="font-bold text-slate-900 text-lg">{requirements.length}</p>
              </div>
            </div>
            <div>
              <p className="text-slate-400 font-medium">Validations Completed</p>
              <p className="font-bold text-slate-900 text-lg">{validations.filter(v => v.status === 'approved').length}</p>
            </div>
            <div className="border-t pt-3">
              <p className="text-slate-400 font-medium">Last Activity</p>
              <p className="font-semibold text-slate-700 mt-0.5">Just now</p>
            </div>
          </div>
        </aside>
      </div>

      {/* Modals rendering */}
      {showUploadModal && (
        <DocumentUploadModal
          projectId={projectId!}
          onClose={() => setShowUploadModal(false)}
          onUploadSuccess={() => {
            loadData();
          }}
        />
      )}

      {viewingArtifact && (
        <DocumentViewerModal
          title={viewingArtifact.title}
          content={viewingArtifact.content}
          version={viewingArtifact.version}
          status={viewingArtifact.status}
          onClose={() => setViewingArtifact(null)}
          onValidateNow={() => {
            const t = viewingArtifact.title;
            setViewingArtifact(null);
            setValidatingRun({ title: t });
          }}
        />
      )}

      {validatingRun && (
        <ValidationModal
          run={validatingRun.run}
          artifactTitle={validatingRun.title}
          onClose={() => setValidatingRun(null)}
          onApprove={handleApproveValidation}
          onRequestChanges={handleRequestChangesValidation}
          busy={busy}
        />
      )}
    </div>
  );
}

function NavItem({ active, icon: Icon, label, count, onClick }: { active: boolean; icon: any; label: string; count?: number; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center justify-between rounded-xl px-3 py-2 text-xs font-semibold transition ${
        active ? 'bg-violet-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'
      }`}
    >
      <div className="flex items-center gap-2.5">
        <Icon size={16} />
        <span>{label}</span>
      </div>
      {count !== undefined && (
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-extrabold ${active ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-600'}`}>
          {count}
        </span>
      )}
    </button>
  );
}
