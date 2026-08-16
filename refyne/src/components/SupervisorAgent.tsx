import { useEffect } from 'react';
import { Bot, FileText, BarChart3, Upload, LayoutDashboard, Download, RefreshCw, Edit3, ThumbsUp, ThumbsDown, HelpCircle } from 'lucide-react';

export type ConversationEvent =
  | { type: 'generating'; documentType: string }
  | { type: 'document_generated'; documentTitle: string; documentSize: string; documentContent: string }
  | { type: 'next_action' }
  | { type: 'asking_question' }
  | { type: 'question_answered' }
  | { type: 'confirm_no_thanks' }
  | { type: 'waiting' };

interface SupervisorAgentProps {
  conversationHistory: ConversationEvent[];
  onUploadDocument: () => void;
  onViewDashboard: () => void;
  onGenerateDocument: (type: string) => void;
  onAskAnotherQuestion: () => void;
  onNoThanksFirst: () => void;
  onNoThanksConfirm: () => void;
  onNextAction: (action: 'generate' | 'ask' | 'none') => void;
  onFeedback: (helpful: boolean) => void;
  showWelcome: boolean;
  inputRef?: React.RefObject<HTMLTextAreaElement | null>;
}

const generationActions = [
  { id: 'brd', label: 'Generate BRD', icon: FileText },
  { id: 'srs', label: 'Generate SRS', icon: FileText },
  { id: 'rtm', label: 'Generate RTM', icon: FileText },
  { id: 'user_stories', label: 'Generate User Stories', icon: FileText },
  { id: 'acceptance_criteria', label: 'Acceptance Criteria', icon: FileText },
  { id: 'business_rules', label: 'Business Rules', icon: FileText },
  { id: 'validation_rules', label: 'Validation Rules', icon: FileText },
  { id: 'edge_cases', label: 'Edge Cases', icon: FileText },
  { id: 'assumptions', label: 'Assumptions', icon: FileText },
  { id: 'risk_analysis', label: 'Generate Risk Analysis', icon: BarChart3 },
  { id: 'missing_requirements', label: 'Identify Missing Requirements', icon: FileText },
];

function SupervisorBubble({ children, timestamp }: { children: React.ReactNode; timestamp?: string }) {
  const time = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="supervisor-avatar">
        <Bot size={16} className="text-violet-600" />
      </div>
      <div className="supervisor-message">
        <div className="mb-1 text-xs font-medium text-slate-500">Supervisor AI • {time}</div>
        {children}
      </div>
    </div>
  );
}

function ActionButtons({
  onUploadDocument,
  onViewDashboard,
  onGenerateDocument,
  onAskAnotherQuestion,
  onNoThanksFirst,
}: {
  onUploadDocument: () => void;
  onViewDashboard: () => void;
  onGenerateDocument: (type: string) => void;
  onAskAnotherQuestion: () => void;
  onNoThanksFirst: () => void;
}) {
  return (
    <div className="ml-11 space-y-3">
      <div className="flex flex-wrap gap-2">
        <button
          onClick={onUploadDocument}
          className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700"
        >
          <Upload size={14} />
          Upload Document
        </button>
        <button
          onClick={onViewDashboard}
          className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50"
        >
          <LayoutDashboard size={14} />
          View Dashboard
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {generationActions.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.id}
              onClick={() => onGenerateDocument(action.id)}
              className="action-btn action-btn-secondary"
            >
              <Icon size={12} />
              {action.label}
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={onAskAnotherQuestion}
          className="inline-flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 transition hover:bg-violet-100"
        >
          <HelpCircle size={14} />
          Ask Question (Based on Uploaded Document)
        </button>
        <button
          onClick={onNoThanksFirst}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-50"
        >
          No, Not Now
        </button>
      </div>
    </div>
  );
}

function renderEvent(event: ConversationEvent, index: number, props: {
  onUploadDocument: () => void;
  onViewDashboard: () => void;
  onGenerateDocument: (type: string) => void;
  onAskAnotherQuestion: () => void;
  onNoThanksFirst: () => void;
  onNoThanksConfirm: () => void;
  onNextAction: (action: 'generate' | 'ask' | 'none') => void;
  onFeedback: (helpful: boolean) => void;
  handleDownload: (content: string, title: string) => void;
}) {
  const key = `${event.type}-${index}`;

  if (event.type === 'generating') {
    const action = generationActions.find(a => a.id === event.documentType);
    const docLabel = action?.label.replace(/^(Generate|Identify)\s*/i, '').trim() || event.documentType?.replace(/_/g, ' ') || 'document';
    return (
      <div key={key} className="ml-11 mt-4">
        <div className="flex items-center gap-2 text-sm text-violet-600">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
          <span>Generating {docLabel}...</span>
        </div>
      </div>
    );
  }

  if (event.type === 'document_generated') {
    return (
      <div key={key} className="ml-11 mt-4">
        <SupervisorBubble>
          <p className="text-slate-800">Here is the generated {event.documentTitle || 'document'} document based on your uploaded requirements.</p>
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-violet-100">
                <FileText size={18} className="text-violet-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800">{event.documentTitle || 'Generated Document'}.docx</p>
                <p className="text-xs text-slate-500">{event.documentSize || '2.4 MB'}</p>
              </div>
              <button
                onClick={() => props.handleDownload(event.documentContent, event.documentTitle)}
                className="ml-auto rounded-lg p-2 text-slate-400 hover:bg-slate-100"
                title="Download"
              >
                <Download size={16} />
              </button>
            </div>
          </div>
          <p className="mt-3 text-sm text-slate-600">You can review, download or refine the document.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => props.handleDownload(event.documentContent, event.documentTitle)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
            >
              <Download size={14} />
              Download
            </button>
            <button className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50">
              <RefreshCw size={14} />
              Regenerate
            </button>
            <button className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50">
              <Edit3 size={14} />
              Edit / Refine
            </button>
          </div>
        </SupervisorBubble>
      </div>
    );
  }

  if (event.type === 'next_action') {
    return (
      <div key={key} className="ml-11 mt-4">
        <SupervisorBubble>
          <p className="text-slate-800">What would you like to do next?</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => props.onNextAction('generate')}
              className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700"
            >
              <FileText size={14} />
              Generate Document
            </button>
            <button
              onClick={() => props.onNextAction('ask')}
              className="inline-flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 transition hover:bg-violet-100"
            >
              Ask Another Question
            </button>
            <button
              onClick={() => props.onNextAction('none')}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-50"
            >
              No, Not Now
            </button>
          </div>
        </SupervisorBubble>
      </div>
    );
  }

  if (event.type === 'asking_question') {
    return (
      <div key={key} className="ml-11 mt-4">
        <SupervisorBubble>
          <p className="text-slate-800">Sure! What would you like to know?</p>
        </SupervisorBubble>
      </div>
    );
  }

  if (event.type === 'question_answered') {
    return (
      <div key={key} className="ml-11 mt-4">
        <SupervisorBubble>
          <p className="text-slate-800">Was this helpful?</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => props.onFeedback(true)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
            >
              <ThumbsUp size={14} />
            </button>
            <button
              onClick={() => props.onFeedback(false)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
            >
              <ThumbsDown size={14} />
            </button>
            <button
              onClick={props.onAskAnotherQuestion}
              className="inline-flex items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3 py-1.5 text-sm font-medium text-violet-700 transition hover:bg-violet-100"
            >
              Ask another question
            </button>
          </div>
        </SupervisorBubble>
      </div>
    );
  }

  if (event.type === 'confirm_no_thanks') {
    return (
      <div key={key} className="ml-11 mt-4">
        <SupervisorBubble>
          <p className="text-slate-800">Would you like to perform any other action?</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => props.onNextAction('generate')}
              className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700"
            >
              <FileText size={14} />
              Generate Document
            </button>
            <button
              onClick={() => props.onNextAction('ask')}
              className="inline-flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 transition hover:bg-violet-100"
            >
              Ask Another Question
            </button>
            <button
              onClick={props.onNoThanksConfirm}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-50"
            >
              No, Not Now
            </button>
          </div>
        </SupervisorBubble>
      </div>
    );
  }

  if (event.type === 'waiting') {
    return (
      <div key={key} className="ml-11 mt-4">
        <SupervisorBubble>
          <p className="text-slate-800">Okay, no action will be taken now. I'll wait for your next request. Whenever you need anything, just let me know!</p>
        </SupervisorBubble>
        <div className="ml-11 mt-2">
          <div className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-500">
            <div className="h-2 w-2 rounded-full bg-slate-400 animate-pulse" />
            Waiting for your input...
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export function SupervisorAgent({
  conversationHistory,
  onUploadDocument,
  onViewDashboard,
  onGenerateDocument,
  onAskAnotherQuestion,
  onNoThanksFirst,
  onNoThanksConfirm,
  onNextAction,
  onFeedback,
  showWelcome,
  inputRef,
}: SupervisorAgentProps) {
  useEffect(() => {
    if (conversationHistory.length > 0 && conversationHistory[conversationHistory.length - 1].type === 'asking_question' && inputRef?.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [conversationHistory, inputRef]);

  const handleDownload = (content: string, title: string) => {
    if (!content) return;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = window.document.createElement('a');
    a.href = url;
    a.download = `${title || 'document'}.md`;
    window.document.body.appendChild(a);
    a.click();
    window.document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const renderProps = {
    onUploadDocument,
    onViewDashboard,
    onGenerateDocument,
    onAskAnotherQuestion,
    onNoThanksFirst,
    onNoThanksConfirm,
    onNextAction,
    onFeedback,
    handleDownload,
  };

  return (
    <div className="mb-5">
      {showWelcome && (
        <ActionButtons
          onUploadDocument={onUploadDocument}
          onViewDashboard={onViewDashboard}
          onGenerateDocument={onGenerateDocument}
          onAskAnotherQuestion={onAskAnotherQuestion}
          onNoThanksFirst={onNoThanksFirst}
        />
      )}

      {conversationHistory.map((event, index) => renderEvent(event, index, renderProps))}
    </div>
  );
}
