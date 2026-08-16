import { useEffect, useRef } from 'react';
import { Bot, FileText, BarChart3, Upload, LayoutDashboard, Download, RefreshCw, Edit3, ThumbsUp, ThumbsDown, HelpCircle } from 'lucide-react';

// ─── Block types (append-only timeline) ───────────────────────────────────────
export type ChatBlock =
  | { id: string; type: 'action_buttons' }
  | { id: string; type: 'generating'; documentType: string }
  | { id: string; type: 'document_result'; title: string; size: string; content: string }
  | { id: string; type: 'next_action_buttons' }
  | { id: string; type: 'supervisor_message'; text: string }
  | { id: string; type: 'question_answer_buttons' }
  | { id: string; type: 'confirm_no_thanks_buttons' }
  | { id: string; type: 'waiting_message' };

// ─── Props ────────────────────────────────────────────────────────────────────
interface SupervisorAgentProps {
  blocks: ChatBlock[];
  disabled?: boolean;
  onUploadDocument: () => void;
  onViewDashboard: () => void;
  onGenerateDocument: (type: string) => void;
  onAskAnotherQuestion: () => void;
  onNoThanksFirst: () => void;
  onNoThanksConfirm: () => void;
  onNextAction: (action: 'generate' | 'ask' | 'none') => void;
  onFeedback: (helpful: boolean) => void;
}

// ─── Constants ────────────────────────────────────────────────────────────────
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

// ─── Helpers ──────────────────────────────────────────────────────────────────
let _blockCounter = 0;
export function createBlockId(): string {
  return `block-${Date.now()}-${++_blockCounter}`;
}

function SupervisorBubble({ children, timestamp }: { children: React.ReactNode; timestamp?: string }) {
  const time = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="supervisor-avatar">
        <Bot size={16} className="text-violet-600" />
      </div>
      <div className="supervisor-message">
        <div className="mb-1 text-xs font-medium text-slate-500">Supervisor AI · {time}</div>
        {children}
      </div>
    </div>
  );
}

function downloadFile(content: string, title: string) {
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
}

// ─── Block renderers ──────────────────────────────────────────────────────────

function ActionButtonsBlock({
  disabled, onUploadDocument, onViewDashboard, onGenerateDocument, onAskAnotherQuestion, onNoThanksFirst,
}: {
  disabled?: boolean;
  onUploadDocument: () => void;
  onViewDashboard: () => void;
  onGenerateDocument: (type: string) => void;
  onAskAnotherQuestion: () => void;
  onNoThanksFirst: () => void;
}) {
  return (
    <div className="ml-11 space-y-3">
      <div className="flex flex-wrap gap-2">
        <button onClick={onUploadDocument} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed">
          <Upload size={14} /> Upload Document
        </button>
        <button onClick={onViewDashboard} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed">
          <LayoutDashboard size={14} /> View Dashboard
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {generationActions.map((action) => {
          const Icon = action.icon;
          return (
            <button key={action.id} onClick={() => onGenerateDocument(action.id)} disabled={disabled} className="action-btn action-btn-secondary disabled:opacity-50 disabled:cursor-not-allowed">
              <Icon size={12} /> {action.label}
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        <button onClick={onAskAnotherQuestion} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 transition hover:bg-violet-100 disabled:opacity-50 disabled:cursor-not-allowed">
          <HelpCircle size={14} /> Ask Question (Based on Uploaded Document)
        </button>
        <button onClick={onNoThanksFirst} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed">
          No, Not Now
        </button>
      </div>
    </div>
  );
}

function GeneratingBlock({ documentType }: { documentType: string }) {
  const action = generationActions.find(a => a.id === documentType);
  const label = action?.label.replace(/^(Generate|Identify)\s*/i, '').trim() || documentType?.replace(/_/g, ' ') || 'document';
  return (
    <div className="ml-11 mt-4">
      <div className="flex items-center gap-2 text-sm text-violet-600">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
        <span>Generating {label}...</span>
      </div>
    </div>
  );
}

function DocumentResultBlock({ title, size, content }: { title: string; size: string; content: string }) {
  return (
    <div className="ml-11 mt-4">
      <SupervisorBubble>
        <p className="text-slate-800">Here is the generated {title || 'document'} document based on your uploaded requirements.</p>
        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-violet-100">
              <FileText size={18} className="text-violet-600" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-800">{title || 'Generated Document'}.docx</p>
              <p className="text-xs text-slate-500">{size || '2.4 MB'}</p>
            </div>
            <button onClick={() => downloadFile(content, title)} className="ml-auto rounded-lg p-2 text-slate-400 hover:bg-slate-100" title="Download">
              <Download size={16} />
            </button>
          </div>
        </div>
        <p className="mt-3 text-sm text-slate-600">You can review, download or refine the document.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={() => downloadFile(content, title)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50">
            <Download size={14} /> Download
          </button>
          <button className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50">
            <RefreshCw size={14} /> Regenerate
          </button>
          <button className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50">
            <Edit3 size={14} /> Edit / Refine
          </button>
        </div>
      </SupervisorBubble>
    </div>
  );
}

function NextActionButtonsBlock({ disabled, onNextAction }: { disabled?: boolean; onNextAction: (action: 'generate' | 'ask' | 'none') => void }) {
  return (
    <div className="ml-11 mt-4">
      <SupervisorBubble>
        <p className="text-slate-800">What would you like to do next?</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={() => onNextAction('generate')} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed">
            <FileText size={14} /> Generate Document
          </button>
          <button onClick={() => onNextAction('ask')} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 transition hover:bg-violet-100 disabled:opacity-50 disabled:cursor-not-allowed">
            Ask Another Question
          </button>
          <button onClick={() => onNextAction('none')} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed">
            No, Not Now
          </button>
        </div>
      </SupervisorBubble>
    </div>
  );
}

function SupervisorMessageBlock({ text }: { text: string }) {
  return (
    <div className="ml-11 mt-4">
      <SupervisorBubble>
        <p className="text-slate-800">{text}</p>
      </SupervisorBubble>
    </div>
  );
}

function QuestionAnswerButtonsBlock({ onFeedback, onAskAnotherQuestion }: { onFeedback: (helpful: boolean) => void; onAskAnotherQuestion: () => void }) {
  return (
    <div className="ml-11 mt-4">
      <SupervisorBubble>
        <p className="text-slate-800">Was this helpful?</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={() => onFeedback(true)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50">
            <ThumbsUp size={14} />
          </button>
          <button onClick={() => onFeedback(false)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50">
            <ThumbsDown size={14} />
          </button>
          <button onClick={onAskAnotherQuestion} className="inline-flex items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3 py-1.5 text-sm font-medium text-violet-700 transition hover:bg-violet-100">
            Ask another question
          </button>
        </div>
      </SupervisorBubble>
    </div>
  );
}

function ConfirmNoThanksButtonsBlock({ disabled, onNextAction, onNoThanksConfirm }: { disabled?: boolean; onNextAction: (action: 'generate' | 'ask' | 'none') => void; onNoThanksConfirm: () => void }) {
  return (
    <div className="ml-11 mt-4">
      <SupervisorBubble>
        <p className="text-slate-800">Would you like to perform any other action?</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={() => onNextAction('generate')} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed">
            <FileText size={14} /> Generate Document
          </button>
          <button onClick={() => onNextAction('ask')} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2 text-sm font-medium text-violet-700 transition hover:bg-violet-100 disabled:opacity-50 disabled:cursor-not-allowed">
            Ask Another Question
          </button>
          <button onClick={onNoThanksConfirm} disabled={disabled} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-500 transition hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed">
            No, Not Now
          </button>
        </div>
      </SupervisorBubble>
    </div>
  );
}

function WaitingMessageBlock() {
  return (
    <div className="ml-11 mt-4">
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

// ─── Main component ───────────────────────────────────────────────────────────
export function SupervisorAgent({
  blocks,
  disabled,
  onUploadDocument,
  onViewDashboard,
  onGenerateDocument,
  onAskAnotherQuestion,
  onNoThanksFirst,
  onNoThanksConfirm,
  onNextAction,
  onFeedback,
}: SupervisorAgentProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [blocks.length]);

  return (
    <div className="mb-5">
      {blocks.map((block) => {
        switch (block.type) {
          case 'action_buttons':
            return (
              <ActionButtonsBlock
                key={block.id}
                disabled={disabled}
                onUploadDocument={onUploadDocument}
                onViewDashboard={onViewDashboard}
                onGenerateDocument={onGenerateDocument}
                onAskAnotherQuestion={onAskAnotherQuestion}
                onNoThanksFirst={onNoThanksFirst}
              />
            );
          case 'generating':
            return <GeneratingBlock key={block.id} documentType={block.documentType} />;
          case 'document_result':
            return <DocumentResultBlock key={block.id} title={block.title} size={block.size} content={block.content} />;
          case 'next_action_buttons':
            return <NextActionButtonsBlock key={block.id} disabled={disabled} onNextAction={onNextAction} />;
          case 'supervisor_message':
            return <SupervisorMessageBlock key={block.id} text={block.text} />;
          case 'question_answer_buttons':
            return <QuestionAnswerButtonsBlock key={block.id} onFeedback={onFeedback} onAskAnotherQuestion={onAskAnotherQuestion} />;
          case 'confirm_no_thanks_buttons':
            return <ConfirmNoThanksButtonsBlock key={block.id} disabled={disabled} onNextAction={onNextAction} onNoThanksConfirm={onNoThanksConfirm} />;
          case 'waiting_message':
            return <WaitingMessageBlock key={block.id} />;
          default:
            return null;
        }
      })}
      <div ref={endRef} />
    </div>
  );
}
