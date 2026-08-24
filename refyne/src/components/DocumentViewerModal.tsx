import { useState } from 'react';
import { X, Download, FileText, CheckCircle2 } from 'lucide-react';

interface DocumentViewerModalProps {
  title: string;
  content: string;
  version?: string;
  status?: string;
  onClose: () => void;
  onValidateNow?: () => void;
}

export function DocumentViewerModal({
  title,
  content,
  version = 'v1.0',
  status = 'pending_validation',
  onClose,
  onValidateNow,
}: DocumentViewerModalProps) {
  const [copied, setCopied] = useState(false);

  // Extract headings for table of contents
  const headings = content
    .split('\n')
    .filter(line => line.startsWith('#'))
    .map(line => {
      const level = (line.match(/^#+/) || [''])[0].length;
      const text = line.replace(/^#+\s*/, '').trim();
      return { level, text };
    });

  const handleDownload = (format: 'md' | 'txt') => {
    const blob = new Blob([content], { type: format === 'md' ? 'text/markdown' : 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.replace(/\s+/g, '_')}.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm">
      <div className="flex h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Modal Header */}
        <header className="flex items-center justify-between border-b px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-violet-100 text-violet-600">
              <FileText size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900">{title}</h2>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">{version}</span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  status === 'approved' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                }`}>
                  {status === 'approved' ? 'Approved' : 'Pending Validation'}
                </span>
              </div>
              <p className="text-xs text-slate-500">Generated requirement artifact</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onValidateNow && status !== 'approved' && (
              <button onClick={onValidateNow} className="btn-primary flex items-center gap-1.5 py-1.5 text-xs">
                <CheckCircle2 size={14} /> Validate Now
              </button>
            )}
            <button onClick={handleCopy} className="rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50">
              {copied ? 'Copied!' : 'Copy Text'}
            </button>
            <button onClick={() => handleDownload('md')} className="flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-slate-50">
              <Download size={14} /> Download MD
            </button>
            <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <X size={18} />
            </button>
          </div>
        </header>

        {/* Body Content */}
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Table of Contents sidebar */}
          <aside className="w-64 border-r bg-slate-50/50 p-4 overflow-auto hidden md:block">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Document Sections</p>
            <nav className="space-y-1 text-sm">
              {headings.map((h, i) => (
                <div
                  key={i}
                  className={`truncate px-2 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 cursor-pointer ${
                    h.level === 1 ? 'font-semibold text-violet-700' : h.level === 2 ? 'ml-3' : 'ml-5 text-xs text-slate-500'
                  }`}
                >
                  {h.text}
                </div>
              ))}
            </nav>
          </aside>

          {/* Document Content Reader */}
          <main className="flex-1 overflow-auto p-6 sm:p-8 bg-white font-sans leading-relaxed text-slate-800">
            <div className="prose prose-violet max-w-none">
              {content.split('\n').map((line, idx) => {
                if (line.startsWith('# ')) return <h1 key={idx} className="text-2xl font-bold text-slate-900 mt-4 mb-2 pb-2 border-b">{line.replace('# ', '')}</h1>;
                if (line.startsWith('## ')) return <h2 key={idx} className="text-xl font-semibold text-slate-800 mt-6 mb-3">{line.replace('## ', '')}</h2>;
                if (line.startsWith('### ')) return <h3 key={idx} className="text-lg font-medium text-slate-800 mt-4 mb-2">{line.replace('### ', '')}</h3>;
                if (line.startsWith('- ')) return <li key={idx} className="ml-5 list-disc text-slate-700 my-1">{line.replace('- ', '')}</li>;
                if (line.match(/^\d+\.\s/)) return <li key={idx} className="ml-5 list-decimal text-slate-700 my-1">{line.replace(/^\d+\.\s/, '')}</li>;
                if (!line.trim()) return <div key={idx} className="h-2" />;
                return <p key={idx} className="my-2 text-slate-700 leading-relaxed">{line}</p>;
              })}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
