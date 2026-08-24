import { useRef, useState } from 'react';
import { X, UploadCloud, FileText } from 'lucide-react';
import { documentService } from '../services/documentService';

interface DocumentUploadModalProps {
  projectId: string;
  onClose: () => void;
  onUploadSuccess: () => void;
}

type FileProcessState = {
  file: File;
  docId?: string;
  status: 'uploading' | 'parsing' | 'embedding' | 'indexed' | 'failed';
  progress: number;
  error?: string | null;
};

export function DocumentUploadModal({ projectId, onClose, onUploadSuccess }: DocumentUploadModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [fileList, setFileList] = useState<FileProcessState[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileSelect = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const newStates: FileProcessState[] = Array.from(files).map(f => ({
      file: f,
      status: 'uploading',
      progress: 20,
    }));
    setFileList(prev => [...prev, ...newStates]);
    processFiles(newStates);
  };

  const processFiles = async (states: FileProcessState[]) => {
    setIsUploading(true);
    for (const item of states) {
      try {
        const doc = await documentService.upload(projectId, item.file);
        if (doc.status === 'indexed') {
          setFileList(prev =>
            prev.map(p => (p.file === item.file ? { ...p, docId: doc.id, progress: 100, status: 'indexed' } : p))
          );
          setIsUploading(false);
          onUploadSuccess();
        } else if (doc.status === 'failed') {
          setFileList(prev =>
            prev.map(p => (p.file === item.file ? { ...p, docId: doc.id, progress: 100, status: 'failed', error: doc.error_message } : p))
          );
          setIsUploading(false);
        } else {
          setFileList(prev =>
            prev.map(p => (p.file === item.file ? { ...p, docId: doc.id, progress: 60, status: 'embedding' } : p))
          );

          // Poll status if still processing
          const poll = setInterval(async () => {
            try {
              const res = await documentService.status(doc.id);
              if (res.status === 'indexed') {
                clearInterval(poll);
                setFileList(prev =>
                  prev.map(p => (p.docId === doc.id ? { ...p, status: 'indexed', progress: 100 } : p))
                );
                setIsUploading(false);
                onUploadSuccess();
              } else if (res.status === 'failed') {
                clearInterval(poll);
                setFileList(prev =>
                  prev.map(p => (p.docId === doc.id ? { ...p, status: 'failed', progress: 100, error: res.error_message } : p))
                );
                setIsUploading(false);
              }
            } catch {
              // Keep polling
            }
          }, 1500);
        }
      } catch (err) {
        setFileList(prev =>
          prev.map(p => (p.file === item.file ? { ...p, status: 'failed', error: (err as Error).message } : p))
        );
        setIsUploading(false);
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <header className="flex items-center justify-between border-b px-6 py-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Upload Document</h2>
            <p className="text-xs text-slate-500">Supports PDF, DOCX, TXT (Max 50MB)</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 overflow-auto p-6 space-y-6">
          {/* Dropzone */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/50 p-8 text-center cursor-pointer transition hover:border-violet-400 hover:bg-violet-50/30"
          >
            <div className="grid h-12 w-12 place-items-center rounded-full bg-violet-100 text-violet-600 mb-3">
              <UploadCloud size={24} />
            </div>
            <p className="text-sm font-semibold text-slate-800">
              Drag and drop files here or <span className="text-violet-600 underline">click to browse</span>
            </p>
            <p className="mt-1 text-xs text-slate-400">PDF, DOCX, TXT, CSV, XLSX up to 50MB</p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={e => handleFileSelect(e.target.files)}
              accept=".pdf,.doc,.docx,.xlsx,.csv,.txt"
            />
          </div>

          {/* Upload & processing progress list */}
          {fileList.length > 0 && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Document Processing Status</h3>
              <div className="space-y-3">
                {fileList.map((item, i) => (
                  <div key={i} className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="flex items-center justify-between text-sm mb-2">
                      <div className="flex items-center gap-2">
                        <FileText size={16} className="text-violet-600" />
                        <span className="font-medium text-slate-800">{item.file.name}</span>
                        <span className="text-xs text-slate-400">({(item.file.size / (1024 * 1024)).toFixed(1)} MB)</span>
                      </div>
                      <span className="text-xs font-semibold text-slate-600">
                        {item.status === 'indexed' ? 'Completed 100%' : item.status === 'failed' ? 'Failed' : `${item.progress}%`}
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full transition-all duration-300 ${
                          item.status === 'indexed'
                            ? 'bg-emerald-500'
                            : item.status === 'failed'
                            ? 'bg-rose-500'
                            : 'bg-violet-600'
                        }`}
                        style={{ width: `${item.progress}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <footer className="flex items-center justify-end gap-3 border-t bg-slate-50 px-6 py-4">
          <button onClick={onClose} className="btn-primary py-2 px-6">
            {isUploading ? 'Uploading...' : 'Done'}
          </button>
        </footer>
      </div>
    </div>
  );
}
