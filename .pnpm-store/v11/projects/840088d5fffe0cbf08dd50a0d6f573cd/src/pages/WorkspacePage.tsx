import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Bot, Mic, Plus, Send, Pin, Pencil, Trash2 } from 'lucide-react';
import type { ChatMessage, Citation, Conversation, Project, Workspace } from '../types/models';
import { projectService } from '../services/projectService';
import { chatService } from '../services/chatService';
import { aiService, type GenerationAction } from '../services/aiService';
import { documentService } from '../services/documentService';
import { SupervisorAgent, type ChatBlock, createBlockId } from '../components/SupervisorAgent';
import { EntityActionMenu } from '../components/EntityActionMenu';

function retrievalText(response: Awaited<ReturnType<typeof aiService.search>>) {
  const results = response.results || [];
  if (!results.length) return 'No matching indexed content was found for this question.';
  return results.map((result, index) => `${index + 1}. ${result.content || result.text || 'Matching source content available.'}`).join('\n\n');
}

export function WorkspacePage() {
  const { projectId, conversationId } = useParams();
  const nav = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textInputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  const [project, setProject] = useState<Project>();
  const [workspace, setWorkspace] = useState<Workspace>();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<Conversation>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState('');

  // Append-only block timeline
  const [blocks, setBlocks] = useState<ChatBlock[]>([]);

  const appendBlock = useCallback((block: ChatBlock) => {
    setBlocks(prev => [...prev, block]);
  }, []);

  const open = async (conversation: Conversation) => {
    setActive(conversation);
    const msgs = await chatService.messages(conversation.id);
    setMessages(msgs);
    // Show action buttons if conversation has welcome messages (no user messages yet)
    const hasWelcome = msgs.length >= 2 && msgs[0].role === 'assistant' && msgs[1].role === 'assistant';
    setBlocks(hasWelcome ? [{ id: createBlockId(), type: 'action_buttons' }] : []);
    nav(`/app/projects/${projectId}/chat/${conversation.id}`);
  };

  const handleRename = async (id: string) => {
    if (!renameText.trim()) return;
    const updated = await chatService.rename(id, renameText.trim());
    setConversations(x => x.map(c => c.id === id ? updated : c));
    if (active?.id === id) setActive(updated);
    setRenamingId(null);
    setRenameText('');
  };

  const handleDelete = async (id: string) => {
    await chatService.remove(id);
    setConversations(x => x.filter(c => c.id !== id));
    if (active?.id === id) {
      setActive(undefined);
      setMessages([]);
      nav(`/app/projects/${projectId}`);
    }
  };

  const handleTogglePin = async (id: string) => {
    const updated = await chatService.togglePin(id);
    setConversations(x => x.map(c => c.id === id ? updated : c));
  };

  const startRename = (conversation: Conversation) => {
    setRenamingId(conversation.id);
    setRenameText(conversation.title);
  };

  const load = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [p, w, c] = await Promise.all([
        projectService.get(projectId),
        projectService.workspace(projectId),
        chatService.list(projectId),
      ]);
      setProject(p);
      setWorkspace(w);
      setConversations(c);
      const chosen = c.find(x => x.id === conversationId) || c[0];
      if (chosen) {
        await open(chosen);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load project.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [projectId, conversationId]);

  const create = async () => {
    if (!projectId) return;
    const c = await chatService.create(projectId);
    setConversations(x => [c, ...x]);
    await open(c);
    const welcomeMsg1 = await chatService.message(c.id, 'assistant', 'Hi, welcome! How can I help you with your requirements?');
    const welcomeMsg2 = await chatService.message(c.id, 'assistant', 'Which document or action would you like to generate?');
    setMessages([welcomeMsg1, welcomeMsg2]);
    setBlocks([{ id: createBlockId(), type: 'action_buttons' }]);
  };

  // ─── Send question (Ask Another Question flow) ───────────────────────────
  const send = useCallback(async (event?: React.FormEvent) => {
    if (event) event.preventDefault();
    if (!projectId || !active || !text.trim()) return;
    const question = text.trim();
    setText('');
    setBusy(true);
    setError('');
    try {
      const user = await chatService.message(active.id, 'user', question);
      setMessages(x => [...x, user]);

      const generated = await aiService.generate(projectId, question);
      let citations: Citation[] = generated.citations || [];
      let content: string;
      if (generated.configured && generated.answer) {
        content = generated.answer;
      } else {
        const search = await aiService.search(projectId, question);
        citations = citations.length ? citations : (search.citations || []);
        content = `${generated.message ? generated.message + '\n\n' : ''}${retrievalText(search)}`;
      }

      const assistant = await chatService.message(active.id, 'assistant', content, citations);
      setMessages(x => [...x, assistant]);

      // Append answer + next action buttons to block timeline
      appendBlock({ id: createBlockId(), type: 'next_action_buttons' });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to search project documents.');
    } finally {
      setBusy(false);
    }
  }, [projectId, active, text, appendBlock]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }, []);

  // ─── Generate Document flow ──────────────────────────────────────────────
  const handleGenerateDocument = useCallback(async (action: string) => {
    if (!projectId || !active || busy) return;
    setBusy(true);
    setError('');

    // 1. Append generating block
    const generatingId = createBlockId();
    appendBlock({ id: generatingId, type: 'generating', documentType: action });

    try {
      const generated = await aiService.generateDocument(projectId, action as GenerationAction);
      const title = generated.title || action.replace('_', ' ');

      // 2. Remove generating block, then append document result + next action
      setBlocks(prev => prev.filter(b => b.id !== generatingId));

      appendBlock({
        id: createBlockId(),
        type: 'document_result',
        title: title,
        size: '2.4 MB',
        content: generated.content || '',
      });

      appendBlock({ id: createBlockId(), type: 'next_action_buttons' });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to generate document.');
      // Remove the generating block on error
      setBlocks(prev => prev.filter(b => b.id !== generatingId));
    } finally {
      setBusy(false);
    }
  }, [projectId, active, busy, appendBlock]);

  // ─── Ask Another Question flow ──────────────────────────────────────────
  const handleAskAnotherQuestion = useCallback(() => {
    appendBlock({ id: createBlockId(), type: 'supervisor_message', text: 'Sure! What would you like to know?' });
  }, [appendBlock]);

  // ─── No, Not Now flow ───────────────────────────────────────────────────
  const handleNoThanksFirst = useCallback(() => {
    appendBlock({ id: createBlockId(), type: 'confirm_no_thanks_buttons' });
  }, [appendBlock]);

  const handleNoThanksConfirm = useCallback(() => {
    appendBlock({ id: createBlockId(), type: 'waiting_message' });
  }, [appendBlock]);

  // ─── Next Action flow (from "What would you like to do next?") ─────────
  const handleNextAction = useCallback((action: 'generate' | 'ask' | 'none') => {
    if (action === 'generate') {
      appendBlock({ id: createBlockId(), type: 'action_buttons' });
    } else if (action === 'ask') {
      appendBlock({ id: createBlockId(), type: 'supervisor_message', text: 'Sure! What would you like to know?' });
    } else {
      appendBlock({ id: createBlockId(), type: 'confirm_no_thanks_buttons' });
    }
  }, [appendBlock]);

  // ─── Feedback flow ──────────────────────────────────────────────────────
  const handleFeedback = useCallback((_helpful: boolean) => {
    appendBlock({ id: createBlockId(), type: 'next_action_buttons' });
  }, [appendBlock]);

  const openFileUpload = () => fileInputRef.current?.click();

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;
    setUploading(true);
    setError('');
    try {
      await documentService.upload(projectId, file);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Document upload failed.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const toggleVoice = useCallback(() => {
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
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript;
      setText(prev => prev ? `${prev} ${transcript}` : transcript);
    };
    recognition.onerror = () => setRecording(false);
    recognition.onend = () => setRecording(false);
    recognitionRef.current = recognition;
    recognition.start();
    setRecording(true);
  }, [recording]);

  if (loading) return <div className="p-8">Loading workspace…</div>;
  if (!project) return <div className="p-8 text-rose-600">{error || 'Project not found.'}</div>;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b bg-white px-5 py-4">
        <div>
          <button className="inline-flex items-center gap-1 text-sm text-violet-600" onClick={() => nav('/app/projects')}><ArrowLeft size={15}/>Projects</button>
          <h1 className="mt-1 text-xl font-bold">{project.name}</h1>
          <p className="text-xs text-slate-500">Workspace: {workspace?.name || 'No data available'}</p>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-64 shrink-0 border-r bg-white p-4 lg:block">
          <button className="btn-primary w-full" onClick={create}><Plus size={16}/>New Chat</button>
          <p className="mt-5 text-xs font-semibold text-slate-400">LOCAL CONVERSATION HISTORY</p>
          {conversations.length ? (
            <div className="mt-2 space-y-1">
              {conversations.map(c => (
                <div key={c.id} className={`group flex items-center rounded-lg ${active?.id === c.id ? 'bg-violet-50' : 'hover:bg-slate-50'}`}>
                  {renamingId === c.id ? (
                    <input
                      autoFocus
                      value={renameText}
                      onChange={e => setRenameText(e.target.value)}
                      onBlur={() => handleRename(c.id)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') handleRename(c.id);
                        if (e.key === 'Escape') { setRenamingId(null); setRenameText(''); }
                      }}
                      className="flex-1 truncate rounded-lg px-3 py-2 text-left text-sm outline-none ring-2 ring-violet-500"
                    />
                  ) : (
                    <button
                      className="flex flex-1 items-center gap-2 truncate px-3 py-2 text-left text-sm"
                      onClick={() => open(c)}
                    >
                      {c.pinned && <Pin size={12} className="shrink-0 text-violet-500" />}
                      <span className={`truncate ${active?.id === c.id ? 'font-semibold text-violet-700' : 'text-slate-700'}`}>{c.title}</span>
                    </button>
                  )}
                  <EntityActionMenu
                    actions={[
                      { label: 'Rename', icon: <Pencil size={14} />, onClick: () => startRename(c) },
                      { label: c.pinned ? 'Unpin' : 'Pin', icon: <Pin size={14} />, onClick: () => handleTogglePin(c.id) },
                      { label: 'Delete', icon: <Trash2 size={14} />, onClick: () => handleDelete(c.id), danger: true },
                    ]}
                  />
                </div>
              ))}
            </div>
          ) : <p className="mt-3 text-sm text-slate-500">No conversations yet</p>}
        </aside>
        <section className="flex min-w-0 flex-1 flex-col bg-slate-50">
          <div className="flex-1 overflow-auto p-5 sm:p-8">
            {error && <p className="mb-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
            {!active ? (
              <div className="grid h-full place-items-center text-center">
                <div>
                  <Bot className="mx-auto text-violet-600"/>
                  <h2 className="mt-3 font-semibold">No conversations yet</h2>
                  <button className="btn-primary mt-4" onClick={create}>Start New Chat</button>
                </div>
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <article key={message.id} className={`mb-5 flex ${message.role === 'user' ? 'justify-end' : ''}`}>
                    <div className={`max-w-2xl whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === 'user' ? 'bg-violet-600 text-white' : 'border bg-white'}`}>
                      {message.content}
                      {message.citations?.length ? (
                        <div className="mt-4 border-t pt-3 text-xs text-slate-500">
                          <b>Sources</b>
                          {message.citations.map((citation, i) => (
                            <p key={i}>{String(citation.document_name || citation.file_name || citation.document_id || 'Source document')}{citation.page ? ` · Page ${citation.page}` : ''}{citation.chunk_index !== undefined ? ` · Chunk ${citation.chunk_index}` : ''}</p>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </article>
                ))}

                {active && (
                  <SupervisorAgent
                    blocks={blocks}
                    disabled={busy}
                    onUploadDocument={openFileUpload}
                    onViewDashboard={() => nav('/app/dashboard')}
                    onGenerateDocument={handleGenerateDocument}
                    onAskAnotherQuestion={handleAskAnotherQuestion}
                    onNoThanksFirst={handleNoThanksFirst}
                    onNoThanksConfirm={handleNoThanksConfirm}
                    onNextAction={handleNextAction}
                    onFeedback={handleFeedback}
                  />
                )}
              </>
            )}
          </div>
          <form className="border-t bg-white p-4" onSubmit={send}>
            {uploading && <p className="mb-2 text-xs text-violet-600">Uploading and indexing document…</p>}
            {recording && <p className="mb-2 text-xs text-rose-600">Listening… speak now</p>}
            <div className="flex items-end gap-2">
              <button type="button" onClick={openFileUpload} className="shrink-0 rounded-lg p-2.5 text-slate-500 hover:bg-slate-100" disabled={busy || uploading} aria-label="Upload document" title="Upload document"><Plus size={18}/></button>
              <textarea
                ref={textInputRef}
                className="field m-0 min-h-11 flex-1"
                rows={1}
                value={text}
                onChange={e => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything based on your uploaded documents..."
              />
              <button type="button" onClick={toggleVoice} className={`shrink-0 rounded-lg p-2.5 transition ${recording ? 'bg-rose-100 text-rose-600' : 'text-slate-500 hover:bg-slate-100'}`} disabled={busy} aria-label="Voice input" title="Voice input"><Mic size={18}/></button>
              <button className="btn-primary shrink-0" disabled={!active || !text.trim() || busy} aria-label="Ask">{busy ? 'Thinking…' : <Send size={17}/>}</button>
            </div>
            <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileUpload} accept=".pdf,.doc,.docx,.xlsx,.csv,.txt"/>
          </form>
        </section>
      </div>
    </div>
  );
}
