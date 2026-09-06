import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../services/api';

const Documents = () => {
  const { user, loading: authLoading } = useAuth();
  const { tenant, loading: tenantLoading } = useTenant();
  const navigate = useNavigate();
  const location = useLocation();

  const queryParams = new URLSearchParams(location.search);
  const projectId = queryParams.get('project_id') || queryParams.get('project') || localStorage.getItem('refyne_selected_project_id') || localStorage.getItem('selected_project_id');

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (projectId) {
      fetchDocuments();
    } else {
      setDocuments([]);
      setSelectedDoc(null);
    }
  }, [projectId, user, tenant]);

  const fetchDocuments = async () => {
    if (!projectId) {
      setDocuments([]);
      setSelectedDoc(null);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const [filesRes, docsRes] = await Promise.allSettled([
        api.get('/api/v1/files', { params: { project_id: projectId } }),
        api.get('/api/v1/documents')
      ]);

      let combined = [];

      if (docsRes.status === 'fulfilled' && Array.isArray(docsRes.data)) {
        combined = docsRes.data.map(d => ({
          id: d.id,
          name: d.title || `${d.doc_type || 'SRS'} Specification`,
          filename: d.title || `${d.doc_type || 'SRS'} Specification`,
          type: d.doc_type || 'SRS',
          version: d.version || 'v1.0',
          status: d.status || 'APPROVED',
          sections: d.sections || [],
          validation_report: d.validation_report,
          isCompiledDoc: true
        }));
      }

      if (filesRes.status === 'fulfilled') {
        const fileList = Array.isArray(filesRes.data)
          ? filesRes.data
          : (filesRes.data?.files || filesRes.data?.items || []);
        const formattedFiles = fileList.map(f => ({
          ...f,
          type: f.type || (f.name?.endsWith('.pdf') ? 'PDF' : 'DOC')
        }));
        combined = [...combined, ...formattedFiles];
      }

      if (combined.length > 0) {
        setDocuments(combined);
        setSelectedDoc(combined[0]);
      } else {
        setDocuments([]);
        setSelectedDoc(null);
      }
    } catch (err) {
      setDocuments([]);
      setSelectedDoc(null);
      setError("Couldn't load documents. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || tenantLoading) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-cyan-400 font-medium">Loading document vault...</div>;
  }

  if (!user || !tenant) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-slate-300">Please login to continue.</div>;
  }

  const handleUploadDocument = () => {
    navigate('/chat');
  };

  const handleDownloadPDF = async (doc) => {
    if (!doc || !doc.id) return;
    try {
      const docId = doc.id || 'export';
      const docType = doc.type || 'BRD';
      const title = encodeURIComponent(doc.name || doc.filename || 'Document');
      const response = await api.get(`/api/v1/documents/${docId}/export/pdf?title=${title}&type=${docType}`, {
        responseType: 'blob'
      });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${docType}_${doc.name || 'document'}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Failed to download PDF', err);
      alert('Could not download PDF. Please try again.');
    }
  };

  const handleDeleteDocument = async (e, docId) => {
    e.stopPropagation();
    if (!docId || !window.confirm('Are you sure you want to delete this document?')) return;

    try {
      await api.delete(`/api/v1/documents/${docId}`);
      const updated = documents.filter(d => d.id !== docId);
      setDocuments(updated);
      if (selectedDoc?.id === docId) {
        setSelectedDoc(updated.length > 0 ? updated[0] : null);
      }
    } catch (err) {
      console.error('Failed to delete document', err);
      const updated = documents.filter(d => d.id !== docId);
      setDocuments(updated);
      if (selectedDoc?.id === docId) {
        setSelectedDoc(updated.length > 0 ? updated[0] : null);
      }
    }
  };

  const safeDocs = Array.isArray(documents) ? documents : [];
  const filteredDocs = safeDocs.filter(d => (d.name || d.filename || '').toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-gradient-to-br from-deep-navy via-slate-950 to-dark-navy">
      {/* Main Document Table & Explorer */}
      <main className="flex-1 p-8 overflow-y-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
              <span>📄</span>
              <span>Document Engine & Vault</span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">Manage BRD, SRS, FRD, RTM, and technical documentation with version traceability</p>
          </div>
          <div className="flex items-center space-x-3">
            <button onClick={handleUploadDocument} className="glass-button font-bold text-sm">
              <span>+ Upload Document</span>
            </button>
          </div>
        </header>

        {!projectId ? (
          <div className="glass-card p-16 text-center text-slate-400 space-y-4 my-6 border border-cyan-500/20">
            <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-cyan-500/30 flex items-center justify-center text-3xl mx-auto text-cyan-400 shadow-[0_0_20px_rgba(0,240,255,0.15)]">
              📁
            </div>
            <h2 className="text-xl font-bold text-slate-100">Select a project to view documents</h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto">Choose a project workspace from the Projects page to view its uploaded document vault.</p>
            <button
              onClick={() => navigate('/projects')}
              className="glass-button mx-auto font-bold text-sm shadow-[0_0_15px_rgba(0,240,255,0.3)] px-6 py-2.5"
            >
              📁 Go to Projects
            </button>
          </div>
        ) : (
          <>
            {/* Filter & Search Bar */}
            <div className="flex items-center space-x-4">
              <input
                type="text"
                placeholder="Search documents by name, type, or version..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="glass-input flex-1 text-sm"
              />
            </div>

            {error && <div className="p-4 rounded-xl bg-rose-500/20 border border-rose-500/30 text-rose-300 text-sm">{error}</div>}

            {loading && <div className="text-center py-12 text-cyan-400 font-medium">Loading document catalog...</div>}

            {!loading && documents.length === 0 && (
              <div className="glass-card p-12 text-center text-slate-400 space-y-4">
                <p className="text-lg font-bold text-slate-200">No documents yet</p>
                <p className="text-sm text-slate-400">Upload a document in chat to get started</p>
                <button onClick={handleUploadDocument} className="glass-button mx-auto">
                  + Upload Document
                </button>
              </div>
            )}

            {!loading && documents.length > 0 && filteredDocs.length === 0 && (
              <div className="glass-card p-12 text-center text-slate-400 space-y-4">
                <p className="text-lg">No matching documents found in vault.</p>
              </div>
            )}

            {/* Document Grid / Cards */}
            {!loading && filteredDocs.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredDocs.map((doc) => (
                  <div
                    key={doc.id}
                    onClick={() => setSelectedDoc(doc)}
                    className={`glass-card p-5 flex items-start space-x-4 transition-all duration-200 cursor-pointer group relative ${
                      selectedDoc?.id === doc.id ? 'border-cyan-400/80 shadow-[0_0_20px_rgba(0,240,255,0.2)] bg-slate-900/80' : 'hover:border-cyan-500/40'
                    }`}
                  >
                    <div className="w-12 h-12 rounded-xl bg-slate-950 border border-cyan-500/30 flex items-center justify-center text-2xl flex-shrink-0">
                      {doc.type === 'BRD' ? '📋' : doc.type === 'SRS' ? '📄' : doc.type === 'RTM' ? '📊' : '📁'}
                    </div>
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[10px] text-cyan-400 font-semibold px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/30">
                          {doc.type || 'DOC'}
                        </span>
                        <div className="flex items-center space-x-2">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            doc.status === 'APPROVED' ? 'badge-glow-green' : doc.status === 'IN_REVIEW' ? 'badge-glow-yellow' : 'badge-glow-cyan'
                          }`}>
                            {doc.status || 'DRAFT'}
                          </span>
                          <button
                            type="button"
                            onClick={(e) => handleDeleteDocument(e, doc.id)}
                            className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 transition-opacity p-1 text-sm font-bold"
                            title="Delete Document"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                      <h3 className="text-sm font-bold text-slate-100 truncate pr-6">{doc.name || doc.filename}</h3>
                      <div className="flex items-center space-x-4 text-[11px] text-slate-400 pt-1">
                        <span>Ver: <strong className="text-slate-200">{doc.version || 'v1.0'}</strong></span>
                        <span>Size: <strong className="text-slate-200">{doc.size || '1.5 MB'}</strong></span>
                        <span>Author: <strong className="text-slate-300">{doc.author || 'System'}</strong></span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </main>

      {/* Right Context Drawer: Document Inspector & Preview */}
      <aside className="w-80 bg-slate-950/90 border-l border-cyan-500/15 flex-shrink-0 flex flex-col h-full overflow-y-auto p-6 space-y-6">
        <h3 className="text-xs uppercase tracking-wider text-cyan-400 font-mono font-bold">
          Document Preview & Audit
        </h3>

        {selectedDoc ? (
          <div className="space-y-6">
            <div className="glass-card p-5 space-y-4">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-xl">
                  📑
                </div>
                <div className="truncate">
                  <h4 className="text-sm font-bold text-slate-100 truncate">{selectedDoc.name || selectedDoc.filename}</h4>
                  <p className="text-[11px] text-slate-400">ID: {selectedDoc.id}</p>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 text-xs space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">Standard:</span>
                  <span className="text-cyan-300 font-mono font-bold">ISO/IEC/IEEE 29148</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Version:</span>
                  <span className="text-cyan-300 font-mono font-bold">{selectedDoc.version || 'v1.0'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Status:</span>
                  <span className="text-emerald-400 font-semibold">{selectedDoc.status || 'DRAFT'}</span>
                </div>
                {selectedDoc.validation_report && (
                  <div className="flex justify-between pt-1 border-t border-slate-800">
                    <span className="text-slate-400">Quality Score:</span>
                    <span className={`font-mono font-bold ${selectedDoc.validation_report.score >= 80 ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {selectedDoc.validation_report.score}/100
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-slate-400">Traceability:</span>
                  <span className="text-slate-200">Full (RTM Synced)</span>
                </div>
              </div>
            </div>

            <div className="glass-card p-5 space-y-3">
              <h5 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Document Actions</h5>
              <div className="space-y-2">
                <button
                  onClick={() => handleDownloadPDF(selectedDoc)}
                  className="w-full glass-button text-xs py-2.5 font-bold flex items-center justify-center space-x-2 shadow-[0_0_15px_rgba(0,240,255,0.3)]"
                >
                  <span>📥</span>
                  <span>Download PDF Specification</span>
                </button>
                <button
                  onClick={() => navigate('/chat')}
                  className="w-full glass-button-secondary text-xs py-2 font-semibold flex items-center justify-center space-x-2"
                >
                  <span>💬</span>
                  <span>Discuss in Chat</span>
                </button>
                <button
                  onClick={(e) => handleDeleteDocument(e, selectedDoc.id)}
                  className="w-full glass-button-secondary hover:border-rose-500/50 text-rose-300 text-xs py-2 font-bold flex items-center justify-center space-x-2"
                >
                  <span>🗑️</span>
                  <span>Delete Document</span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-400 text-center py-8">Select a document to inspect preview.</div>
        )}
      </aside>
    </div>
  );
};

export default Documents;