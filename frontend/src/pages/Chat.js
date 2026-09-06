import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import api from '../services/api';

// Simple lightweight Markdown formatter
const FormattedMessage = ({ text }) => {
  if (!text) return null;

  // Split lines
  const lines = text.split('\n');

  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {lines.map((line, idx) => {
        const trimmed = line.trim();

        // Headers
        if (trimmed.startsWith('### ')) {
          return <h4 key={idx} className="text-base font-bold text-cyan-300 mt-2 mb-1">{trimmed.replace('### ', '')}</h4>;
        }
        if (trimmed.startsWith('## ')) {
          return <h3 key={idx} className="text-lg font-bold text-cyan-200 mt-3 mb-1">{trimmed.replace('## ', '')}</h3>;
        }
        if (trimmed.startsWith('# ')) {
          return <h2 key={idx} className="text-xl font-extrabold text-white mt-3 mb-1">{trimmed.replace('# ', '')}</h2>;
        }

        // Bullet points
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div key={idx} className="flex items-start space-x-2 pl-2">
              <span className="text-cyan-400 mt-1 text-xs">•</span>
              <span className="flex-1" dangerouslySetInnerHTML={{ __html: formatInline(trimmed.substring(2)) }} />
            </div>
          );
        }

        // Numbered list
        const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
        if (numMatch) {
          return (
            <div key={idx} className="flex items-start space-x-2 pl-2">
              <span className="text-cyan-400 font-mono text-xs">{numMatch[1]}.</span>
              <span className="flex-1" dangerouslySetInnerHTML={{ __html: formatInline(numMatch[2]) }} />
            </div>
          );
        }

        // Horizontal Rule
        if (trimmed === '---' || trimmed === '***') {
          return <hr key={idx} className="border-slate-700 my-2" />;
        }

        // Empty line
        if (!trimmed) {
          return <div key={idx} className="h-1.5" />;
        }

        // Regular paragraph with inline formatting
        return (
          <p key={idx} dangerouslySetInnerHTML={{ __html: formatInline(line) }} />
        );
      })}
    </div>
  );
};

// Helper for bold, code, inline badges
const formatInline = (str) => {
  if (!str) return '';
  return str
    .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-slate-950/80 border border-cyan-500/30 text-cyan-300 font-mono text-xs">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="font-bold text-slate-100">$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em class="italic text-slate-300">$1</em>');
};

const DocumentApprovalCard = ({ docInfo, onDecisionMade, onDownloadPDF, onNavigateVault, onGenerateNext }) => {
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [showSections, setShowSections] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(false);
  const [versions, setVersions] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(docInfo);
  const [isVersionDropdownOpen, setIsVersionDropdownOpen] = useState(false);

  const generationId = docInfo.generation_id || docInfo.id;

  // Fetch version history for this generation thread
  const fetchVersions = async () => {
    if (!generationId) return;
    try {
      const res = await api.get(`/api/v1/generations/${generationId}/versions`);
      if (Array.isArray(res.data) && res.data.length > 0) {
        setVersions(res.data);
      }
    } catch (err) {
      console.warn('Could not fetch generation versions:', err);
    }
  };

  useEffect(() => {
    setSelectedDoc(docInfo);
    fetchVersions();
  }, [docInfo]);

  const handleSelectVersion = async (vSummary) => {
    setIsVersionDropdownOpen(false);
    if (!vSummary || vSummary.id === selectedDoc.id) return;
    try {
      setLoading(true);
      let loadedDoc = null;
      if (vSummary.id) {
        try {
          const res = await api.get(`/api/v1/documents/${vSummary.id}`);
          if (res.data && res.data.sections) {
            loadedDoc = res.data;
          }
        } catch (e) {
          console.warn('Direct document get failed, trying generation version:', e);
        }
      }
      if (!loadedDoc) {
        const verParam = vSummary.version_num || vSummary.version || vSummary.id;
        const res = await api.get(`/api/v1/generations/${generationId}/versions/${verParam}`);
        if (res.data) {
          loadedDoc = res.data;
        }
      }
      if (loadedDoc) {
        setSelectedDoc(loadedDoc);
      }
    } catch (err) {
      console.error('Failed to load version detail:', err);
    } finally {
      setLoading(false);
    }
  };

  const latestDoc = (versions.length > 0) ? versions[0] : docInfo;
  const isViewingLatest = selectedDoc.id === latestDoc.id;
  const isApproved = selectedDoc.status === 'APPROVED' || selectedDoc.status === 'ACCEPTED';
  const isRejected = selectedDoc.status === 'REJECTED';
  const isRegenerating = docInfo.status === 'REGENERATING' || loading;
  const revisionCount = (versions.length > 0) ? (versions.length - 1) : (docInfo.revision_history?.length || 0);
  const maxRevisionsReached = revisionCount >= 3;

  const handleApprove = async () => {
    try {
      setLoading(true);
      const res = await api.post(`/api/v1/documents/${selectedDoc.id}/approve`);
      setSelectedDoc(res.data);
      if (onDecisionMade) onDecisionMade(res.data);
      await fetchVersions();
    } catch (err) {
      console.error('Approval failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!feedback.trim()) return;
    try {
      setLoading(true);
      const res = await api.post(`/api/v1/documents/${selectedDoc.id}/reject`, { feedback: feedback.trim() });
      setShowRejectInput(false);
      setFeedback('');
      setSelectedDoc(res.data);
      if (onDecisionMade) onDecisionMade(res.data);
      await fetchVersions();
    } catch (err) {
      console.error('Rejection/Regeneration failed:', err);
    } finally {
      setLoading(false);
    }
  };

  if (isRegenerating) {
    return (
      <div className="mt-3 p-4 rounded-xl bg-slate-900/90 border border-cyan-500/40 space-y-2 animate-pulse">
        <div className="flex items-center space-x-2 text-cyan-300 font-bold text-xs">
          <span>⚙️</span>
          <span>Regenerating {selectedDoc.doc_type} based on your feedback…</span>
        </div>
        <p className="text-[11px] text-slate-400">Executing iterative revision engine while preserving verified context.</p>
      </div>
    );
  }

  return (
    <div className="mt-3 p-4 rounded-xl bg-slate-900/90 border border-cyan-500/40 space-y-3 relative">
      {/* Header with Title & Version Selector Dropdown */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800">
        <div className="flex items-center space-x-2.5">
          <span className="text-2xl">📑</span>
          <div>
            <h5 className="font-bold text-sm text-cyan-200">{selectedDoc.title}</h5>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[11px] text-slate-400">
                Type: <strong className="text-cyan-400">{selectedDoc.doc_type}</strong>
              </span>
              {selectedDoc.quality_score && (
                <span className="px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 font-mono text-[10px] border border-cyan-500/40 font-bold">
                  Quality: {selectedDoc.quality_score}%
                </span>
              )}
            </div>
          </div>
        </div>

        {/* VERSION DROPDOWN SELECTOR */}
        <div className="flex items-center space-x-2">
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsVersionDropdownOpen(!isVersionDropdownOpen)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-950 border border-cyan-500/40 hover:border-cyan-400 text-xs font-bold text-cyan-300 transition-all shadow-[0_0_10px_rgba(0,240,255,0.15)]"
            >
              <span>Version: <strong className="text-slate-100">{selectedDoc.version}</strong></span>
              {isViewingLatest && <span className="text-[10px] text-cyan-400 font-normal">(Current)</span>}
              <span className="text-[10px] text-cyan-400">▾</span>
            </button>

            {/* Backdrop click outside to close dropdown */}
            {isVersionDropdownOpen && (
              <div 
                className="fixed inset-0 z-40 bg-black/20" 
                onClick={() => setIsVersionDropdownOpen(false)} 
              />
            )}

            {/* Dropdown Menu - Positioned cleanly inside the card without clipping */}
            {isVersionDropdownOpen && (
              <div className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-3rem)] rounded-xl bg-slate-950/98 backdrop-blur-md border border-cyan-500/50 shadow-[0_10px_35px_rgba(0,0,0,0.9)] z-50 overflow-hidden divide-y divide-slate-800/80 custom-scrollbar">
                <div className="p-2.5 bg-slate-900/90 text-[10px] uppercase font-mono font-bold text-cyan-400 flex items-center justify-between">
                  <span>Version History</span>
                  <span>{versions.length || 1} iterations</span>
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {(versions.length > 0 ? versions : [selectedDoc]).map((v, idx) => {
                    const isSelected = v.id === selectedDoc.id;
                    const isVAccepted = v.status === 'APPROVED' || v.status === 'ACCEPTED';
                    const isVRejected = v.status === 'REJECTED';
                    const isCurrent = idx === 0;

                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSelectVersion(v)}
                        className={`w-full text-left p-3 hover:bg-slate-900 transition-colors flex flex-col space-y-1.5 ${
                          isSelected ? 'bg-cyan-950/50 border-l-4 border-cyan-400' : ''
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs text-slate-100 flex items-center gap-1.5">
                            <span>{v.version || `v${idx + 1}.0`}</span>
                            {isCurrent && <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-900/60 text-cyan-300 font-normal">Current</span>}
                          </span>
                          <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                            isVAccepted ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40' :
                            isVRejected ? 'bg-rose-950 text-rose-300 border border-rose-500/40' :
                            'bg-amber-950 text-amber-300 border border-amber-500/40'
                          }`}>
                            {v.status || 'PENDING_APPROVAL'}
                          </span>
                        </div>
                        {v.rejection_feedback && (
                          <p className="text-[11px] text-amber-200/80 line-clamp-2 italic bg-slate-900/60 p-1.5 rounded border border-slate-800">
                            "{v.rejection_feedback}"
                          </p>
                        )}
                        {v.created_at && (
                          <span className="text-[10px] text-slate-400">
                            {new Date(v.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <span className={`text-[10px] font-mono font-bold px-2 py-1 rounded ${
            isApproved ? 'badge-glow-green text-emerald-300' :
            isRejected ? 'bg-rose-950/80 text-rose-300 border border-rose-500/40' :
            'badge-glow-yellow text-amber-300'
          }`}>
            {selectedDoc.status || 'PENDING_APPROVAL'}
          </span>
        </div>
      </div>

      {/* Historical / Rejected Version Banner */}
      {!isViewingLatest && (
        <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-500/40 text-xs flex items-center justify-between gap-2">
          <div className="space-y-0.5 text-amber-200">
            <span className="font-bold flex items-center gap-1">
              <span>⚠️</span>
              <span>Viewing Historical Version ({selectedDoc.version} — {selectedDoc.status}):</span>
            </span>
            {selectedDoc.rejection_feedback && (
              <p className="text-[11px] text-amber-300/90 italic pl-4">
                Rejected with feedback: "{selectedDoc.rejection_feedback}"
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => handleSelectVersion(latestDoc)}
            className="px-2.5 py-1 rounded bg-amber-500 text-slate-950 font-bold text-[11px] hover:bg-amber-400 transition-colors flex-shrink-0"
          >
            Jump to Current ({latestDoc.version}) →
          </button>
        </div>
      )}

      {/* Diff Badges (Changes against parent) */}
      {(selectedDoc.added_story_ids?.length > 0 || selectedDoc.changed_story_ids?.length > 0 || selectedDoc.removed_story_ids?.length > 0) && (
        <div className="flex flex-wrap items-center gap-2 p-2 rounded-lg bg-slate-950/80 border border-slate-800 text-xs">
          <span className="text-slate-400 font-mono text-[11px]">Diff vs {selectedDoc.parent_version ? `V${selectedDoc.parent_version}` : 'Parent'}:</span>
          {selectedDoc.added_story_ids?.length > 0 && (
            <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/40 font-mono font-bold text-[10px]">
              +{selectedDoc.added_story_ids.length} Added ({selectedDoc.added_story_ids.slice(0, 3).join(', ')}{selectedDoc.added_story_ids.length > 3 ? '...' : ''})
            </span>
          )}
          {selectedDoc.changed_story_ids?.length > 0 && (
            <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-500/40 font-mono font-bold text-[10px]">
              ~{selectedDoc.changed_story_ids.length} Modified
            </span>
          )}
          {selectedDoc.removed_story_ids?.length > 0 && (
            <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-500/40 font-mono font-bold text-[10px]">
              -{selectedDoc.removed_story_ids.length} Removed
            </span>
          )}
        </div>
      )}

      {/* Verification Summary Badge Line */}
      {selectedDoc.verification_summary && (
        <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-xs">
          <div className="flex items-center justify-between font-mono">
            <span className="text-cyan-300 font-bold flex items-center gap-1.5">
              <span>🎯</span>
              <span>Grounding Verification:</span>
            </span>
            <span className="text-emerald-400 font-bold">
              {selectedDoc.verification_summary.verified_count} of {selectedDoc.verification_summary.total_claims} traced to source
              {selectedDoc.verification_summary.flagged_count > 0 && (
                <span className="text-amber-400 ml-1.5">({selectedDoc.verification_summary.flagged_count} below 60% confidence)</span>
              )}
            </span>
          </div>
        </div>
      )}

      {/* Expandable Document Sections Preview */}
      {selectedDoc.sections && selectedDoc.sections.length > 0 && (
        <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-950/60">
          <button
            type="button"
            onClick={() => setShowSections(!showSections)}
            className="w-full px-3 py-2 text-xs flex items-center justify-between text-cyan-300 hover:bg-slate-900/60 font-semibold transition-colors"
          >
            <span className="flex items-center gap-1.5">
              <span>📖</span>
              <span>{showSections ? 'Hide Specification Content' : `Read Full Specification (${selectedDoc.sections.length} Sections & Tables)`}</span>
            </span>
            <span className="text-slate-400 font-mono text-[10px]">{showSections ? '▲ Collapse' : '▼ Expand & Read'}</span>
          </button>
          {showSections && (
            <div className="p-3 border-t border-slate-800/80 space-y-3 max-h-96 overflow-y-auto text-xs custom-scrollbar">
              {selectedDoc.sections.map((sec, sIdx) => (
                <div key={sIdx} className="space-y-1.5 pb-2.5 border-b border-slate-800/50 last:border-0">
                  <h6 className="font-bold text-slate-100 text-xs flex items-center gap-1">
                    <span className="text-cyan-400">§</span>
                    <span>{sec.title}</span>
                  </h6>
                  {sec.body && (
                    <p className="text-slate-300 text-[11px] leading-relaxed whitespace-pre-wrap">{sec.body}</p>
                  )}
                  {sec.table && Array.isArray(sec.table) && sec.table.length > 0 && (
                    <div className="overflow-x-auto my-1.5">
                      <table className="w-full text-left text-[11px] border border-slate-800 border-collapse bg-slate-950">
                        <tbody>
                          {sec.table.map((tRow, rIdx) => (
                            <tr key={rIdx} className={rIdx === 0 ? 'bg-slate-900 font-bold text-cyan-300 border-b border-slate-800' : 'border-b border-slate-800/40 text-slate-300'}>
                              {Array.isArray(tRow) ? tRow.map((cell, cIdx) => (
                                <td key={cIdx} className="p-1.5 px-2 border-r border-slate-800/40 last:border-0">{cell}</td>
                              )) : null}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Action Area */}
      <div className="space-y-2.5 pt-2 border-t border-slate-800">
        {isApproved ? (
          <div className="space-y-2">
            <div className="p-2 rounded bg-emerald-950/40 border border-emerald-500/30 text-xs text-emerald-300 flex items-center gap-2">
              <span>✓</span>
              <span><strong>Specification Approved ({selectedDoc.version}):</strong> Baseline established and ready for downstream pipeline.</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => onDownloadPDF(selectedDoc)}
                className="glass-button text-xs py-2 px-3.5 font-bold flex items-center space-x-1.5 shadow-[0_0_15px_rgba(0,240,255,0.3)] bg-gradient-to-r from-cyan-500/20 to-blue-600/20 border border-cyan-400"
              >
                <span>📥</span>
                <span>Download PDF ({selectedDoc.version})</span>
              </button>
              {selectedDoc.doc_type === 'BRD' && onGenerateNext && (
                <button
                  onClick={() => onGenerateNext('SRS')}
                  className="glass-button text-xs py-2 px-3 font-semibold text-purple-300 border-purple-500/40 hover:bg-purple-950/40"
                >
                  + Generate SRS →
                </button>
              )}
              {(selectedDoc.doc_type === 'BRD' || selectedDoc.doc_type === 'SRS') && onGenerateNext && (
                <button
                  onClick={() => onGenerateNext('RTM')}
                  className="glass-button text-xs py-2 px-3 font-semibold text-emerald-300 border-emerald-500/40 hover:bg-emerald-950/40"
                >
                  + Build RTM Matrix →
                </button>
              )}
              {onGenerateNext && (
                <button
                  onClick={() => onGenerateNext('USER_STORIES')}
                  className="glass-button-secondary text-xs py-2 px-3 font-semibold text-cyan-300"
                >
                  + User Stories
                </button>
              )}
            </div>
          </div>
        ) : isViewingLatest ? (
          <div className="space-y-2">
            {!showRejectInput ? (
              <div className="space-y-2">
                <div className="flex space-x-3">
                  <button
                    onClick={handleApprove}
                    className="glass-button flex-1 text-xs py-2 font-bold text-emerald-300 border-emerald-500/50 hover:bg-emerald-950/40 shadow-[0_0_15px_rgba(16,185,129,0.2)]"
                  >
                    ✓ Accept & Approve ({selectedDoc.version})
                  </button>
                  {!maxRevisionsReached ? (
                    <button
                      onClick={() => setShowRejectInput(true)}
                      className="glass-button-danger flex-1 text-xs py-2 font-bold"
                    >
                      ✕ Request Revisions
                    </button>
                  ) : (
                    <button
                      onClick={onNavigateVault}
                      className="glass-button-secondary flex-1 text-xs py-2"
                    >
                      Inspect in Vault
                    </button>
                  )}
                </div>
                <div className="flex items-center justify-between pt-1">
                  <button
                    onClick={() => onDownloadPDF(selectedDoc)}
                    className="text-xs text-cyan-400 hover:text-cyan-200 flex items-center gap-1 font-semibold"
                  >
                    <span>📥</span>
                    <span>Download Draft PDF</span>
                  </button>
                  <button
                    onClick={onNavigateVault}
                    className="text-xs text-slate-400 hover:text-slate-200"
                  >
                    View in Vault →
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <label className="text-[11px] text-slate-300 font-bold block">
                  Describe needed adjustments (e.g. "The pharmacy and billing stories are still too broad. Split them further"):
                </label>
                <textarea
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="What needs to change in this draft? (Non-empty feedback required)"
                  className="w-full text-xs p-2.5 rounded-lg bg-slate-950 border border-cyan-500/30 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
                  rows={3}
                />
                <div className="flex justify-end space-x-2">
                  <button
                    onClick={() => {
                      setShowRejectInput(false);
                      setFeedback('');
                    }}
                    className="glass-button-secondary text-xs px-3 py-1.5"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleReject}
                    disabled={!feedback.trim() || loading}
                    className="glass-button text-xs px-4 py-1.5 font-bold shadow-[0_0_12px_rgba(0,240,255,0.3)] disabled:opacity-50"
                  >
                    {loading ? 'Submitting…' : 'Submit Feedback & Regenerate'}
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <button
              onClick={() => onDownloadPDF(selectedDoc)}
              className="glass-button text-xs py-2 px-3.5 font-bold flex items-center space-x-1.5 shadow-[0_0_15px_rgba(0,240,255,0.3)] bg-gradient-to-r from-cyan-500/20 to-blue-600/20 border border-cyan-400"
            >
              <span>📥</span>
              <span>Download {selectedDoc.version} PDF</span>
            </button>
            <button
              type="button"
              onClick={() => handleSelectVersion(latestDoc)}
              className="glass-button-secondary text-xs py-2 px-3 text-cyan-300"
            >
              View Active Version ({latestDoc.version}) →
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const Chat = () => {
  const { user } = useAuth();
  const { tenant } = useTenant();
  const location = useLocation();
  const navigate = useNavigate();

  // Conversations & active state
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [activeConv, setActiveConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);

  // Input & Sending
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Editing / Renaming
  const [editingConvId, setEditingConvId] = useState(null);
  const [editTitleInput, setEditTitleInput] = useState('');

  // Delete Modal State
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingConvId, setDeletingConvId] = useState(null);

  // File Upload & Context
  const [uploadingFile, setUploadingFile] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [documentContext, setDocumentContext] = useState('');
  const [generatedDocs, setGeneratedDocs] = useState([]);
  const [generatingDoc, setGeneratingDoc] = useState(false);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Parse session from URL query parameter
  const queryParams = new URLSearchParams(location.search);
  const sessionParam = queryParams.get('session');

  useEffect(() => {
    fetchConversations();
  }, [user, tenant]);

  useEffect(() => {
    if (sessionParam && sessionParam !== activeConvId) {
      selectConversation(sessionParam);
    }
  }, [sessionParam]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && showDeleteModal) {
        setShowDeleteModal(false);
        setDeletingConvId(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showDeleteModal]);

  const fetchConversations = async () => {
    setLoadingConversations(true);
    try {
      const res = await api.get('/api/v1/conversations');
      const list = res.data?.conversations || [];
      setConversations(list);

      // Select conversation: either from URL, or the first in list, or create one
      if (sessionParam) {
        selectConversation(sessionParam);
      } else if (list.length > 0) {
        selectConversation(list[0].id);
      } else {
        // Create initial conversation
        await handleCreateNewChat();
      }
    } catch (err) {
      console.error('Failed to load conversations', err);
    } finally {
      setLoadingConversations(false);
    }
  };

  const selectConversation = async (convId) => {
    if (!convId) return;
    setActiveConvId(convId);
    setLoadingMessages(true);

    try {
      const res = await api.get(`/api/v1/conversations/${convId}`);
      const data = res.data || {};
      setActiveConv(data);
      setMessages(data.messages || []);
      setAttachedFiles(data.attachedFiles || []);
      setGeneratedDocs(data.generatedDocs || []);

      // Build initial document context from files
      if (data.attachedFiles && data.attachedFiles.length > 0) {
        const ctx = data.attachedFiles.map(f => `File: ${f.name}\n${f.text_content || ''}`).join('\n\n');
        setDocumentContext(ctx);
      } else {
        setDocumentContext('');
      }
    } catch (err) {
      console.error('Failed to load conversation messages', err);
    } finally {
      setLoadingMessages(false);
    }
  };

  const handleCreateNewChat = async (customTitle = null) => {
    try {
      const title = customTitle || `Requirements Chat ${conversations.length + 1}`;
      const res = await api.post('/api/v1/conversations', {
        title: title,
        initial_message: "👋 Hello! I am **REFYNE AI**, your Enterprise Requirements Engineering Assistant.\n\nYou can chat with me to:\n- 📋 **Gather & refine software requirements**\n- 📎 **Upload PRDs, PDFs, or DOCX specifications**\n- 📄 **Generate formal BRD, SRS, and Traceability Matrices (RTM)**\n- 🛡️ **Audit compliance and detect architectural risks**\n\nHow can I help you today?"
      });

      const newConv = res.data;
      setConversations(prev => [
        { id: newConv.id, title: newConv.title, created_at: newConv.created_at, status: 'ACTIVE' },
        ...prev
      ]);
      setActiveConvId(newConv.id);
      setActiveConv(newConv);
      setMessages(newConv.messages || []);
      setAttachedFiles([]);
      setGeneratedDocs([]);
      setDocumentContext('');
      navigate(`/chat?session=${newConv.id}`);
    } catch (err) {
      console.error('Failed to create new conversation', err);
    }
  };

  const handleDeleteConversation = (e, convId) => {
    e.stopPropagation();
    setDeletingConvId(convId);
    setShowDeleteModal(true);
  };

  const confirmDeleteConversation = async () => {
    if (!deletingConvId) return;
    const convId = deletingConvId;
    setShowDeleteModal(false);
    setDeletingConvId(null);

    try {
      await api.delete(`/api/v1/conversations/${convId}`);
      const updated = conversations.filter(c => c.id !== convId);
      setConversations(updated);

      if (activeConvId === convId) {
        if (updated.length > 0) {
          selectConversation(updated[0].id);
          navigate(`/chat?session=${updated[0].id}`);
        } else {
          handleCreateNewChat();
        }
      }
    } catch (err) {
      console.error('Failed to delete conversation', err);
    }
  };

  const handleStartRename = (e, conv) => {
    e.stopPropagation();
    setEditingConvId(conv.id);
    setEditTitleInput(conv.title);
  };

  const handleSaveRename = async (convId) => {
    if (!editTitleInput.trim()) {
      setEditingConvId(null);
      return;
    }

    try {
      await api.patch(`/api/v1/conversations/${convId}`, {
        title: editTitleInput.trim()
      });

      setConversations(prev => prev.map(c => c.id === convId ? { ...c, title: editTitleInput.trim() } : c));
      if (activeConv?.id === convId) {
        setActiveConv(prev => ({ ...prev, title: editTitleInput.trim() }));
      }
    } catch (err) {
      console.error('Failed to rename conversation', err);
    } finally {
      setEditingConvId(null);
    }
  };

  const handleSendMessage = async (e) => {
    if (e) e.preventDefault();
    const messageText = input.trim();
    if (!messageText || sending) return;

    const userMsg = {
      id: Date.now(),
      text: messageText,
      sender: 'user',
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setSending(true);

    try {
      // Build formatted conversation history
      const formattedHistory = messages.map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text
      }));
      formattedHistory.push({ role: 'user', content: messageText });

      const res = await api.post('/api/v1/chat/completions', {
        message: messageText,
        conversation_id: activeConvId,
        document_context: documentContext,
        messages: formattedHistory
      });

      const replyText = res.data?.reply || 'Response received.';
      const botMsg = {
        id: Date.now() + 1,
        text: replyText,
        sender: 'bot',
        timestamp: res.data?.timestamp || new Date().toISOString()
      };

      setMessages(prev => [...prev, botMsg]);

      // Update sidebar title if default
      if (activeConv?.title === 'New Requirements Chat' || activeConv?.title?.startsWith('Requirements Chat')) {
        const autoTitle = messageText.slice(0, 30) + (messageText.length > 30 ? '...' : '');
        setConversations(prev => prev.map(c => c.id === activeConvId ? { ...c, title: autoTitle } : c));
      }
    } catch (err) {
      console.error('Error in chat completion', err);
      const errorMsg = {
        id: Date.now() + 1,
        text: '⚠️ An error occurred while generating the AI response. Please verify backend connection and try again.',
        sender: 'bot',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setSending(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingFile(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/api/v1/files/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'X-Conversation-Id': activeConvId || ''
        }
      });

      const fileData = res.data;
      setAttachedFiles(prev => [...prev, fileData]);

      // Update document context
      const newCtx = (documentContext ? documentContext + '\n\n' : '') + `File: ${fileData.name}\n${fileData.text_content || ''}`;
      setDocumentContext(newCtx);

      // Add file ingested message to chat
      const uploadBotMsg = {
        id: Date.now(),
        text: `📎 **Document Ingested:** \`${fileData.name}\` (${fileData.size})\n\nPyPDF text extraction completed successfully. What formal document would you like REFYNE AI to generate from this file?`,
        sender: 'bot',
        isUploadPrompt: true,
        fileName: fileData.name,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, uploadBotMsg]);
    } catch (err) {
      console.error('Failed to upload file', err);
      alert('Failed to upload and parse file. Please try again.');
    } finally {
      setUploadingFile(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleGenerateDocument = async (docType) => {
    if (generatingDoc) return;
    setGeneratingDoc(true);

    const docTitle = activeConv?.title || `${docType} Specification`;

    try {
      const res = await api.post('/api/v1/documents/generate', {
        doc_type: docType,
        title: docTitle,
        conversation_id: activeConvId,
        document_context: documentContext
      });

      const docData = res.data;
      setGeneratedDocs(prev => [...prev, docData]);

      const docCardMsg = {
        id: Date.now(),
        text: `### 📄 ${docData.doc_type} Document Generated Successfully\n\n**Title:** ${docData.title}\n**Version:** ${docData.version} | **Status:** ${docData.status}\n\nThe formal **${docData.doc_type}** specification has been compiled with complete functional specifications, architecture diagram mapping, and compliance matrix.`,
        sender: 'bot',
        isDocumentCard: true,
        docInfo: docData,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, docCardMsg]);
    } catch (err) {
      console.error('Failed to generate document', err);
      alert('Failed to generate document. Please ensure backend is running.');
    } finally {
      setGeneratingDoc(false);
    }
  };

  const handleDownloadPDF = async (docInfo) => {
    try {
      const docId = docInfo.id || 'export';
      const docType = docInfo.doc_type || 'BRD';
      const title = encodeURIComponent(docInfo.title || 'Document');
      
      const response = await api.get(`/api/v1/documents/${docId}/export/pdf?title=${title}&type=${docType}`, {
        responseType: 'blob'
      });

      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${docType}_${docInfo.title || 'document'}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Error downloading PDF', err);
      alert('Could not download PDF. Please try again.');
    }
  };

  const filteredConversations = conversations.filter(c => 
    (c.title || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-gradient-to-br from-deep-navy via-slate-950 to-dark-navy">
      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        className="hidden"
        accept=".pdf,.docx,.doc,.txt,.md,.json"
      />

      {/* LEFT SIDEBAR: Chat History & Sessions */}
      <aside className="w-72 glass-card flex-shrink-0 flex flex-col h-full border-r border-cyan-500/15 p-4 space-y-4">
        {/* Header & New Chat Button */}
        <div className="flex items-center justify-between pb-2 border-b border-cyan-500/20">
          <div className="flex items-center space-x-2">
            <span className="text-xl">💬</span>
            <h2 className="font-extrabold text-base text-slate-100">Chats & Portfolios</h2>
          </div>
          <button
            onClick={() => handleCreateNewChat()}
            className="glass-button text-xs px-2.5 py-1.5 font-bold shadow-[0_0_12px_rgba(0,240,255,0.3)]"
            title="Create New Chat"
          >
            + New
          </button>
        </div>

        {/* Search Chats */}
        <div>
          <input
            type="text"
            placeholder="Search chat sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="glass-input w-full text-xs py-2 px-3"
          />
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
          {loadingConversations ? (
            <div className="text-xs text-cyan-400 text-center py-6">Loading chats...</div>
          ) : filteredConversations.length === 0 ? (
            <div className="text-xs text-slate-500 text-center py-6">No chat sessions found.</div>
          ) : (
            filteredConversations.map((conv) => {
              const isActive = activeConvId === conv.id;
              const isEditing = editingConvId === conv.id;

              return (
                <div
                  key={conv.id}
                  onClick={() => selectConversation(conv.id)}
                  className={`group p-3 rounded-xl transition-all duration-200 cursor-pointer border flex flex-col space-y-1 ${
                    isActive
                      ? 'bg-slate-900/90 border-cyan-400/70 shadow-[0_0_15px_rgba(0,240,255,0.15)] text-white'
                      : 'bg-slate-950/40 border-slate-800/80 hover:border-cyan-500/30 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    {isEditing ? (
                      <div className="flex items-center space-x-1 w-full" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          value={editTitleInput}
                          onChange={(e) => setEditTitleInput(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleSaveRename(conv.id)}
                          className="glass-input text-xs py-1 px-2 flex-1"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveRename(conv.id)}
                          className="text-xs text-cyan-400 hover:text-cyan-200 font-bold px-1"
                        >
                          ✓
                        </button>
                        <button
                          onClick={() => setEditingConvId(null)}
                          className="text-xs text-slate-400 hover:text-rose-400 font-bold px-1"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <>
                        <span className="font-bold text-xs truncate flex-1 pr-2">
                          {conv.title || 'Requirements Chat'}
                        </span>
                        <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={(e) => handleStartRename(e, conv)}
                            className="p-1 text-slate-400 hover:text-cyan-300 text-xs"
                            title="Rename Chat"
                          >
                            ✏️
                          </button>
                          <button
                            onClick={(e) => handleDeleteConversation(e, conv.id)}
                            className="p-1 text-slate-400 hover:text-rose-400 text-xs"
                            title="Delete Chat"
                          >
                            🗑️
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-slate-500">
                    <span>{conv.status || 'ACTIVE'}</span>
                    <span>{conv.created_at ? new Date(conv.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : 'Today'}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* User / Tenant Badge */}
        <div className="pt-3 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
          <span className="truncate">👤 {user?.full_name || user?.email || 'User'}</span>
          <span className="font-mono text-[9px] text-cyan-400 uppercase">{tenant?.name || 'Enterprise'}</span>
        </div>
      </aside>

      {/* MAIN CHAT AREA */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Chat Header */}
        <header className="px-6 py-3.5 bg-slate-950/80 border-b border-cyan-500/15 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-sm font-bold text-cyan-300">
              AI
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-100 flex items-center space-x-2">
                <span>{activeConv?.title || 'Requirements Chat'}</span>
                <span className="text-[10px] text-cyan-400 font-mono px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/30">
                  {activeConv?.id?.slice(0, 8)}
                </span>
              </h3>
              <p className="text-[11px] text-slate-400">Contextual Requirements Gathering & Automated Spec Generator</p>
            </div>
          </div>

          {/* Quick Document Generation Header Bar */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleGenerateDocument('BRD')}
              disabled={generatingDoc}
              className="glass-button-secondary text-xs px-3 py-1.5 font-bold hover:border-cyan-400/80"
              title="Generate Business Requirements Document"
            >
              📋 Generate BRD
            </button>
            <button
              onClick={() => handleGenerateDocument('SRS')}
              disabled={generatingDoc}
              className="glass-button-secondary text-xs px-3 py-1.5 font-bold hover:border-cyan-400/80"
              title="Generate Software Requirements Specification"
            >
              📄 Generate SRS
            </button>
            <button
              onClick={() => handleGenerateDocument('RTM')}
              disabled={generatingDoc}
              className="glass-button-secondary text-xs px-3 py-1.5 font-bold hover:border-cyan-400/80"
              title="Generate Traceability Matrix"
            >
              📊 Generate RTM
            </button>
          </div>
        </header>

        {/* Chat Messages Stream */}
        <div className="flex-1 p-6 overflow-y-auto space-y-5 custom-scrollbar">
          {loadingMessages ? (
            <div className="flex items-center justify-center h-full text-cyan-400 font-medium text-sm">
              Loading chat messages...
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 space-y-3">
              <span className="text-4xl">🚀</span>
              <p className="text-sm font-semibold text-slate-200">Start by typing your requirements or uploading a specification file.</p>
            </div>
          ) : (
            messages.map((msg) => {
              const isUser = msg.sender === 'user';

              return (
                <div
                  key={msg.id}
                  className={`flex ${isUser ? 'justify-end' : 'justify-start'} w-full animate-in fade-in duration-200`}
                >
                  <div className={`flex items-start space-x-3 max-w-[85%] ${isUser ? 'flex-row-reverse space-x-reverse' : 'flex-row'}`}>
                    {/* Avatar */}
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                      isUser
                        ? 'bg-gradient-to-tr from-cyan-600 to-blue-600 text-white shadow-[0_0_10px_rgba(0,240,255,0.4)]'
                        : 'bg-slate-900 border border-cyan-500/40 text-cyan-300'
                    }`}>
                      {isUser ? 'ME' : '🤖'}
                    </div>

                    {/* Message Bubble */}
                    <div className={`rounded-2xl p-4 space-y-2 border ${
                      isUser
                        ? 'bg-gradient-to-br from-cyan-950/90 to-slate-900 border-cyan-500/40 text-slate-100 shadow-[0_0_15px_rgba(0,240,255,0.1)]'
                        : 'bg-slate-950/85 border-slate-800/90 text-slate-200 shadow-xl'
                    }`}>
                      <FormattedMessage text={msg.text} />

                      {/* Interactive Document Generation Card with Approval/Rejection Loop */}
                      {msg.isDocumentCard && msg.docInfo && (
                        <DocumentApprovalCard
                          docInfo={msg.docInfo}
                          onDecisionMade={(updatedDoc) => {
                            setMessages(prev => prev.map(m => {
                              if (m.id === msg.id) {
                                return {
                                  ...m,
                                  docInfo: updatedDoc,
                                  text: updatedDoc.status === 'APPROVED'
                                    ? `### 📄 ${updatedDoc.doc_type} Approved\n\n**Title:** ${updatedDoc.title}\n**Version:** ${updatedDoc.version} | **Status:** APPROVED\n\nThe specification has been approved and is ready for export.`
                                    : `### 📄 ${updatedDoc.doc_type} Revised (${updatedDoc.version})\n\n**Title:** ${updatedDoc.title}\n**Status:** PENDING_APPROVAL\n\nRevised based on feedback. Please review and approve.`
                                };
                              }
                              return m;
                            }));
                          }}
                          onDownloadPDF={handleDownloadPDF}
                          onNavigateVault={() => navigate('/documents')}
                          onGenerateNext={handleGenerateDocument}
                        />
                      )}

                      {/* File Upload Action Card */}
                      {msg.isUploadPrompt && (
                        <div className="mt-3 pt-3 border-t border-slate-800 space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              onClick={() => navigate(activeConvId ? `/dashboard?session=${activeConvId}` : '/dashboard')}
                              className="glass-button text-xs py-2 px-3.5 font-bold flex items-center space-x-1.5 shadow-[0_0_15px_rgba(0,240,255,0.3)] bg-gradient-to-r from-cyan-500/30 to-blue-600/30 border border-cyan-400"
                            >
                              <span>📊</span>
                              <span>View Document Audit Dashboard</span>
                            </button>
                            <button
                              onClick={() => handleGenerateDocument('BRD')}
                              className="glass-button-secondary text-xs py-1.5 px-3 font-semibold"
                            >
                              + Generate BRD
                            </button>
                            <button
                              onClick={() => handleGenerateDocument('SRS')}
                              className="glass-button-secondary text-xs py-1.5 px-3 font-semibold"
                            >
                              + Generate SRS
                            </button>
                            <button
                              onClick={() => handleGenerateDocument('RTM')}
                              className="glass-button-secondary text-xs py-1.5 px-3 font-semibold"
                            >
                              + Generate RTM
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Timestamp */}
                      <span className="text-[10px] text-slate-500 block text-right pt-1">
                        {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          )}

          {/* Typing Indicator */}
          {sending && (
            <div className="flex items-center space-x-3 animate-pulse">
              <div className="w-8 h-8 rounded-xl bg-slate-900 border border-cyan-500/40 flex items-center justify-center text-xs text-cyan-300">
                🤖
              </div>
              <div className="p-3.5 rounded-2xl bg-slate-950/80 border border-slate-800 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce"></span>
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce [animation-delay:0.2s]"></span>
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce [animation-delay:0.4s]"></span>
                <span className="text-xs text-slate-400 pl-2">REFYNE AI is analyzing requirements...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-slate-950/90 border-t border-cyan-500/15 flex-shrink-0 space-y-2">
          {/* File attachment preview pill */}
          {attachedFiles.length > 0 && (
            <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs">
              <span className="text-slate-400 font-mono text-[11px]">Context Files:</span>
              {attachedFiles.map((file, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-cyan-950/80 border border-cyan-500/30 text-cyan-300 text-[11px] flex items-center space-x-1.5"
                >
                  <span>📎</span>
                  <span className="max-w-[150px] truncate">{file.name}</span>
                </span>
              ))}
            </div>
          )}

          <form onSubmit={handleSendMessage} className="flex items-center space-x-3">
            {/* Upload Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingFile}
              className="p-3 rounded-xl bg-slate-900 hover:bg-slate-800 border border-cyan-500/30 text-cyan-400 hover:text-cyan-200 transition-colors flex-shrink-0"
              title="Upload Requirement Document (PDF, DOCX, TXT)"
            >
              {uploadingFile ? '⏳' : '📎'}
            </button>

            {/* Main text input */}
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask REFYNE AI to draft requirements, audit risks, analyze PRD, or generate SRS..."
              className="glass-input flex-1 py-3 px-4 text-sm"
              disabled={sending}
            />

            {/* Send Button */}
            <button
              type="submit"
              disabled={!input.trim() || sending}
              className="glass-button px-6 py-3 text-sm font-bold shadow-[0_0_15px_rgba(0,240,255,0.4)] flex-shrink-0 flex items-center space-x-2"
            >
              <span>{sending ? 'Analyzing...' : 'Send'}</span>
              <span>🚀</span>
            </button>
          </form>
        </div>
      </main>

      {/* RIGHT SIDEBAR: Context, Attached Files & Generated Documents */}
      <aside className="w-80 bg-slate-950/90 border-l border-cyan-500/15 flex-shrink-0 flex flex-col h-full overflow-y-auto p-5 space-y-6">
        <h3 className="text-xs uppercase tracking-wider text-cyan-400 font-mono font-bold">
          Workspace Context & Artifacts
        </h3>

        {/* Quick Requirement Prompts */}
        <div className="glass-card p-4 space-y-3">
          <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Quick AI Actions</h4>
          <div className="space-y-1.5">
            <button
              onClick={() => {
                setInput('Analyze our project requirements and generate a comprehensive functional specification with user stories and acceptance criteria.');
              }}
              className="w-full text-left p-2 rounded-lg bg-slate-900/60 hover:bg-cyan-950/60 border border-slate-800 hover:border-cyan-500/30 text-xs text-slate-300 transition-colors"
            >
              ⚡ Draft Functional Spec & User Stories
            </button>
            <button
              onClick={() => {
                setInput('Perform a cybersecurity, data privacy (GDPR/HIPAA), and system architectural risk assessment on these requirements.');
              }}
              className="w-full text-left p-2 rounded-lg bg-slate-900/60 hover:bg-cyan-950/60 border border-slate-800 hover:border-cyan-500/30 text-xs text-slate-300 transition-colors"
            >
              🛡️ Audit Architectural & Security Risks
            </button>
            <button
              onClick={() => {
                setInput('Generate a detailed Requirements Traceability Matrix (RTM) mapping business goals to technical components and test cases.');
              }}
              className="w-full text-left p-2 rounded-lg bg-slate-900/60 hover:bg-cyan-950/60 border border-slate-800 hover:border-cyan-500/30 text-xs text-slate-300 transition-colors"
            >
              📊 Build Traceability Matrix (RTM)
            </button>
          </div>
        </div>

        {/* Document Health & Audit Dashboard Card */}
        <div className="glass-card p-4 space-y-3 border border-cyan-500/40 bg-gradient-to-b from-cyan-950/40 to-slate-900 shadow-[0_0_20px_rgba(0,240,255,0.15)]">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-cyan-300 uppercase tracking-wider flex items-center space-x-1.5">
              <span>📊</span>
              <span>Document Intelligence</span>
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-500/30">
              Live Audit
            </span>
          </div>
          <p className="text-xs text-slate-300">
            Audit scores, risk factors, requirement conflicts, missing gaps, and RTM coverage for this session's specification.
          </p>
          <button
            onClick={() => {
              if (attachedFiles.length > 0 && attachedFiles[attachedFiles.length - 1].id) {
                navigate(`/dashboard?session=${activeConvId}&file=${attachedFiles[attachedFiles.length - 1].id}`);
              } else if (activeConvId) {
                navigate(`/dashboard?session=${activeConvId}`);
              } else {
                navigate('/dashboard');
              }
            }}
            className="w-full glass-button text-xs py-2 px-3 font-bold flex items-center justify-center space-x-2 shadow-[0_0_15px_rgba(0,240,255,0.3)]"
          >
            <span>📊</span>
            <span>Open Audit Dashboard →</span>
          </button>
        </div>

        {/* Attached Files Ingested */}
        <div className="glass-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Uploaded Files</h4>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-[11px] text-cyan-400 hover:underline font-semibold"
            >
              + Upload
            </button>
          </div>

          {attachedFiles.length === 0 ? (
            <p className="text-xs text-slate-500">No documents uploaded for this session yet.</p>
          ) : (
            <div className="space-y-2">
              {attachedFiles.map((file, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs space-y-1.5 hover:border-cyan-500/40 transition-colors">
                  <div className="flex items-center justify-between font-bold text-slate-200">
                    <span className="truncate pr-2">📎 {file.name}</span>
                    <span className="text-[10px] text-cyan-400 font-mono">{file.size}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-slate-400">Status: Ingested & Extracted</span>
                    <button
                      onClick={() => navigate(`/dashboard?session=${activeConvId}&file=${file.id}`)}
                      className="text-[10px] font-bold text-cyan-300 hover:underline flex items-center space-x-1"
                    >
                      <span>Audit Document →</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>


        {/* Generated Documents in Session */}
        <div className="glass-card p-4 space-y-3">
          <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Generated Documents</h4>
          {generatedDocs.length === 0 ? (
            <p className="text-xs text-slate-500">No documents compiled yet. Use "Generate BRD/SRS" above.</p>
          ) : (
            <div className="space-y-2">
              {generatedDocs.map((doc, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-slate-900 border border-cyan-500/30 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-cyan-300">{doc.doc_type}</span>
                    <span className="badge-glow-green text-[9px]">{doc.status || 'APPROVED'}</span>
                  </div>
                  <p className="text-slate-200 font-medium truncate">{doc.title}</p>
                  <button
                    onClick={() => handleDownloadPDF(doc)}
                    className="w-full glass-button text-[11px] py-1.5 font-bold flex items-center justify-center space-x-1"
                  >
                    <span>📥</span>
                    <span>Download PDF</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Delete Chat Session Confirmation Modal */}
      {showDeleteModal && (
        <div
          className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-150"
          onClick={() => {
            setShowDeleteModal(false);
            setDeletingConvId(null);
          }}
        >
          <div
            className="glass-card max-w-md w-full p-6 space-y-4 border border-rose-500/40 shadow-[0_0_40px_rgba(244,63,94,0.2)] animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center space-x-3 text-rose-400">
              <span className="text-2xl">⚠️</span>
              <h3 className="text-lg font-bold text-slate-100">Delete Chat Session?</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              This action cannot be undone. Are you sure you want to delete this chat session?
            </p>
            <div className="flex justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeletingConvId(null);
                }}
                className="glass-button-secondary text-xs px-4 py-2 font-semibold text-slate-300"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDeleteConversation}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow-[0_0_15px_rgba(244,63,94,0.4)] transition-all"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Chat;