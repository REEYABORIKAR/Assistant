import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import api from '../services/api';

const Approvals = () => {
  const { user } = useAuth();
  const { tenant } = useTenant();

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('ALL'); // 'ALL' | 'PENDING_APPROVAL' | 'APPROVED'
  const [rejectingDocId, setRejectingDocId] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, [user, tenant]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const res = await api.get('/api/v1/documents');
      setDocuments(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
      // Fallback empty if backend offline
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (docId) => {
    try {
      setActionLoading(true);
      const res = await api.post(`/api/v1/documents/${docId}/approve`);
      setDocuments(prev => prev.map(d => d.id === docId ? res.data : d));
    } catch (err) {
      console.error('Approval failed:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (docId) => {
    if (!feedback.trim()) return;
    try {
      setActionLoading(true);
      const res = await api.post(`/api/v1/documents/${docId}/reject`, { feedback: feedback.trim() });
      setDocuments(prev => prev.map(d => d.id === docId ? res.data : d));
      setRejectingDocId(null);
      setFeedback('');
    } catch (err) {
      console.error('Rejection failed:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDownloadPDF = async (doc) => {
    try {
      const response = await api.get(`/api/v1/documents/${doc.id}/export/pdf?title=${encodeURIComponent(doc.title || '')}&type=${doc.doc_type || 'BRD'}`, {
        responseType: 'blob'
      });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${doc.doc_type || 'DOCUMENT'}_${doc.id?.slice(0, 8) || 'export'}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF export failed:', err);
    }
  };

  if (!user || !tenant) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-slate-300">Please login to continue.</div>;
  }

  const filteredDocs = documents.filter(d => {
    if (activeFilter === 'ALL') return true;
    return d.status === activeFilter;
  });

  const pendingCount = documents.filter(d => d.status === 'PENDING_APPROVAL').length;
  const approvedCount = documents.filter(d => d.status === 'APPROVED').length;

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-gradient-to-br from-deep-navy via-slate-950 to-dark-navy">
      {/* Main Approvals Queue */}
      <main className="flex-1 p-8 overflow-y-auto space-y-6">
        <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
              <span>✅</span>
              <span>Human Approval & Review Queue</span>
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Review AI-generated requirements specifications, verify source grounding, and approve formal documents or request revisions.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setActiveFilter('ALL')}
              className={`px-3 py-1.5 rounded-full text-xs font-bold font-mono transition-all ${
                activeFilter === 'ALL'
                  ? 'bg-cyan-950 border border-cyan-400 text-cyan-300 shadow-[0_0_10px_rgba(0,240,255,0.3)]'
                  : 'text-slate-400 hover:text-white bg-slate-900/60'
              }`}
            >
              All ({documents.length})
            </button>
            <button
              onClick={() => setActiveFilter('PENDING_APPROVAL')}
              className={`px-3 py-1.5 rounded-full text-xs font-bold font-mono transition-all ${
                activeFilter === 'PENDING_APPROVAL'
                  ? 'bg-amber-950 border border-amber-400 text-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.3)]'
                  : 'text-slate-400 hover:text-white bg-slate-900/60'
              }`}
            >
              Pending ({pendingCount})
            </button>
            <button
              onClick={() => setActiveFilter('APPROVED')}
              className={`px-3 py-1.5 rounded-full text-xs font-bold font-mono transition-all ${
                activeFilter === 'APPROVED'
                  ? 'bg-emerald-950 border border-emerald-400 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.3)]'
                  : 'text-slate-400 hover:text-white bg-slate-900/60'
              }`}
            >
              Approved ({approvedCount})
            </button>
          </div>
        </header>

        {loading ? (
          <div className="p-12 text-center text-cyan-400 font-mono text-xs">
            Loading approval queue documents…
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="glass-card p-12 text-center space-y-3">
            <span className="text-4xl">📑</span>
            <h3 className="text-base font-bold text-slate-200">No Documents in Approval Queue</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              Generate a formal specification (BRD, SRS, RTM, User Stories) in Chat to review and approve documents here.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {filteredDocs.map((doc) => {
              const isApproved = doc.status === 'APPROVED';
              const revCount = doc.revision_history?.length || 0;
              const maxRevs = revCount >= 3;

              return (
                <div key={doc.id} className="glass-card p-6 flex flex-col justify-between space-y-4 border border-cyan-500/25 bg-slate-900/80">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs text-cyan-300 font-bold px-2 py-0.5 rounded bg-cyan-950 border border-cyan-500/30">
                          {doc.doc_type || 'SPEC'}
                        </span>
                        <span className="text-xs font-mono text-slate-400">
                          {doc.version || 'v1.0'}
                        </span>
                        {revCount > 0 && (
                          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-purple-950 text-purple-300 border border-purple-500/40">
                            Rev {revCount + 1}
                          </span>
                        )}
                      </div>
                      <span className={`text-[10px] font-bold font-mono px-2.5 py-0.5 rounded-full ${
                        isApproved ? 'badge-glow-green text-emerald-300' : 'badge-glow-yellow text-amber-300'
                      }`}>
                        {doc.status || 'PENDING_APPROVAL'}
                      </span>
                    </div>

                    <h3 className="text-base font-bold text-slate-100">{doc.title}</h3>

                    {/* Verification Summary Badge */}
                    {doc.verification_summary && (
                      <div className="p-2 rounded bg-slate-950/90 border border-slate-800 text-[11px] font-mono flex items-center justify-between">
                        <span className="text-cyan-400 font-semibold">🎯 Grounding Traced:</span>
                        <span className="text-emerald-400 font-bold">
                          {doc.verification_summary.verified_count} of {doc.verification_summary.total_claims} verified
                        </span>
                      </div>
                    )}

                    {doc.sections && (
                      <p className="text-xs text-slate-400">
                        Contains <strong className="text-slate-300">{doc.sections.length} specification sections</strong> structured per IEEE 830 / ISO 29148 standards.
                      </p>
                    )}
                  </div>

                  <div className="pt-4 border-t border-slate-800 space-y-3">
                    {isApproved ? (
                      <div className="flex items-center space-x-3">
                        <button
                          onClick={() => handleDownloadPDF(doc)}
                          className="glass-button w-full text-xs py-2 font-bold flex items-center justify-center space-x-2"
                        >
                          <span>📥</span>
                          <span>Download Approved PDF</span>
                        </button>
                      </div>
                    ) : rejectingDocId === doc.id ? (
                      <div className="space-y-2">
                        <label className="text-[11px] text-slate-300 font-bold block">
                          Feedback for Revision:
                        </label>
                        <textarea
                          value={feedback}
                          onChange={(e) => setFeedback(e.target.value)}
                          placeholder="What needs to change? (e.g. 'Add explicit SLAs and define OAuth2 JWT login requirements')"
                          className="w-full text-xs p-2 rounded bg-slate-950 border border-cyan-500/30 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                          rows={2}
                        />
                        <div className="flex space-x-2">
                          <button
                            onClick={() => handleReject(doc.id)}
                            disabled={!feedback.trim() || actionLoading}
                            className="glass-button-danger flex-1 text-xs py-1.5 font-bold disabled:opacity-50"
                          >
                            {actionLoading ? 'Regenerating…' : '⚡ Submit & Regenerate'}
                          </button>
                          <button
                            onClick={() => { setRejectingDocId(null); setFeedback(''); }}
                            className="glass-button-secondary text-xs py-1.5 px-3"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="flex space-x-3">
                          <button
                            onClick={() => handleApprove(doc.id)}
                            disabled={actionLoading}
                            className="glass-button flex-1 text-xs py-2 font-bold text-emerald-300 border-emerald-500/50 hover:bg-emerald-950/40"
                          >
                            ✓ Approve
                          </button>
                          {!maxRevs && (
                            <button
                              onClick={() => { setRejectingDocId(doc.id); setFeedback(''); }}
                              disabled={actionLoading}
                              className="glass-button-danger flex-1 text-xs py-2 font-bold"
                            >
                              ✕ Request Revisions
                            </button>
                          )}
                        </div>
                        {maxRevs && (
                          <p className="text-[10px] text-amber-400 bg-amber-950/40 p-2 rounded border border-amber-800/40 font-mono">
                            ⚠️ Maximum 3 revision cycles reached for this document.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Right Context Drawer */}
      <aside className="w-80 bg-slate-950/90 border-l border-cyan-500/15 flex-shrink-0 flex flex-col h-full overflow-y-auto p-6 space-y-6">
        <h3 className="text-xs uppercase tracking-wider text-cyan-400 font-mono font-bold">
          Approval Governance
        </h3>
        <div className="glass-card p-4 space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-400">Audit Grounding:</span>
            <span className="text-emerald-400 font-semibold">ENFORCED</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Max Revision Cap:</span>
            <span className="text-cyan-300 font-mono">3 Cycles</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Export Gate:</span>
            <span className="text-cyan-300">Requires Sign-off</span>
          </div>
        </div>
      </aside>
    </div>
  );
};

export default Approvals;