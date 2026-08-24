import { useState } from 'react';
import { X, CheckCircle2, FileText, Check } from 'lucide-react';
import type { ChecklistItem, ValidationRunRecord } from '../types/models';

interface ValidationModalProps {
  run?: ValidationRunRecord;
  artifactTitle?: string;
  onClose: () => void;
  onApprove: (feedback: string, checklist: ChecklistItem[]) => void;
  onRequestChanges: (feedback: string, checklist: ChecklistItem[]) => void;
  busy?: boolean;
}

const defaultChecklist: ChecklistItem[] = [
  { id: 'c1', label: 'All functional requirements are captured', checked: true },
  { id: 'c2', label: 'Business goals are clearly defined', checked: true },
  { id: 'c3', label: 'Scope is clearly defined', checked: true },
  { id: 'c4', label: 'Constraints & assumptions are included', checked: true },
  { id: 'c5', label: 'Stakeholders are identified', checked: true },
  { id: 'c6', label: 'Anything missing or unclear?', checked: false },
];

export function ValidationModal({
  run,
  artifactTitle = 'BRD_E-Commerce_Platform.md',
  onClose,
  onApprove,
  onRequestChanges,
  busy,
}: ValidationModalProps) {
  const [items, setItems] = useState<ChecklistItem[]>(run?.checklist?.length ? run.checklist : defaultChecklist);
  const [comments, setComments] = useState(run?.feedback || '');

  const toggleCheck = (id: string) => {
    setItems(prev => prev.map(i => i.id === id ? { ...i, checked: !i.checked } : i));
  };

  const totalReqs = run?.total_requirements || 38;
  const validReqs = run?.valid_requirements || 32;
  const issuesFound = run?.issues_found || 6;
  const ambiguities = run?.ambiguities || 4;
  const gapsIdentified = run?.gaps_identified || 3;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <header className="flex items-center justify-between border-b px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-violet-100 text-violet-600">
              <CheckCircle2 size={20} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Validate Document</h2>
              <p className="text-xs text-slate-500">Please review the generated artifact and provide feedback.</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <X size={18} />
          </button>
        </header>

        {/* Modal Body */}
        <div className="flex-1 overflow-auto p-6 space-y-6">
          {/* Document metadata box */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText size={20} className="text-violet-600" />
              <div>
                <p className="text-sm font-semibold text-slate-900">{run?.artifact_title || artifactTitle}</p>
                <p className="text-xs text-slate-500">Generated on {new Date().toLocaleDateString()} · By Requirement Agent</p>
              </div>
            </div>
            <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700">
              {run?.status === 'approved' ? 'Approved' : 'Pending Review'}
            </span>
          </div>

          {/* Validation Metrics Grid */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Validation Summary</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <div className="rounded-xl border bg-white p-3 text-center">
                <p className="text-xs text-slate-500">Total Reqs</p>
                <p className="text-xl font-bold text-slate-800">{totalReqs}</p>
              </div>
              <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-3 text-center">
                <p className="text-xs text-emerald-600 font-medium">Valid</p>
                <p className="text-xl font-bold text-emerald-700">{validReqs}</p>
              </div>
              <div className="rounded-xl border border-rose-100 bg-rose-50/50 p-3 text-center">
                <p className="text-xs text-rose-600 font-medium">Issues</p>
                <p className="text-xl font-bold text-rose-700">{issuesFound}</p>
              </div>
              <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3 text-center">
                <p className="text-xs text-amber-600 font-medium">Ambiguities</p>
                <p className="text-xl font-bold text-amber-700">{ambiguities}</p>
              </div>
              <div className="rounded-xl border border-violet-100 bg-violet-50/50 p-3 text-center">
                <p className="text-xs text-violet-600 font-medium">Gaps</p>
                <p className="text-xl font-bold text-violet-700">{gapsIdentified}</p>
              </div>
            </div>
          </div>

          {/* Validation Checklist */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Validation Checklist</h3>
            <div className="space-y-2 rounded-xl border p-4 bg-white">
              {items.map(item => (
                <label key={item.id} className="flex items-center gap-3 text-sm text-slate-700 cursor-pointer hover:bg-slate-50 p-1.5 rounded-lg transition">
                  <input
                    type="checkbox"
                    checked={item.checked}
                    onChange={() => toggleCheck(item.id)}
                    className="h-4 w-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
                  />
                  <span className={item.checked ? 'font-medium text-slate-800' : 'text-slate-500'}>{item.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Comment Box */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
              Reviewer Comments / Request Changes
            </label>
            <textarea
              rows={3}
              value={comments}
              onChange={e => setComments(e.target.value)}
              placeholder="Add your comments, missing scope details, or feedback for refinement..."
              className="w-full rounded-xl border border-slate-200 p-3 text-sm focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-200"
            />
          </div>
        </div>

        {/* Modal Footer Actions */}
        <footer className="flex items-center justify-end gap-3 border-t bg-slate-50 px-6 py-4">
          <button
            type="button"
            onClick={() => onRequestChanges(comments, items)}
            disabled={busy}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-100 disabled:opacity-50"
          >
            Request Changes
          </button>
          <button
            type="button"
            onClick={() => onApprove(comments, items)}
            disabled={busy}
            className="btn-primary flex items-center gap-2 px-5 py-2 text-sm font-semibold shadow-md disabled:opacity-50"
          >
            <Check size={16} /> Approve Document
          </button>
        </footer>
      </div>
    </div>
  );
}
