import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import api from '../services/api';

const Dashboard = () => {
  const { user, loading: authLoading } = useAuth();
  const { tenant, loading: tenantLoading } = useTenant();
  const location = useLocation();
  const navigate = useNavigate();

  const queryParams = new URLSearchParams(location.search);
  const sessionParam = queryParams.get('session');
  const fileParam = queryParams.get('file');

  const [loading, setLoading] = useState(false);
  const [reAuditing, setReAuditing] = useState(false);
  const [auditData, setAuditData] = useState(null);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('overview'); // 'overview', 'risks', 'conflicts', 'missing', 'rtm'

  // Multi-document management
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [selectedFileId, setSelectedFileId] = useState(fileParam || null);
  const [loadingFiles, setLoadingFiles] = useState(false);

  useEffect(() => {
    fetchUploadedFiles();
  }, [sessionParam, user, tenant]);

  useEffect(() => {
    if (selectedFileId) {
      fetchAuditForFile(selectedFileId);
    } else if (sessionParam) {
      fetchAuditForSession(sessionParam);
    } else {
      setAuditData(null);
    }
  }, [selectedFileId, sessionParam]);

  const fetchUploadedFiles = async () => {
    setLoadingFiles(true);
    setError('');
    try {
      const res = await api.get('/api/v1/files');
      const files = res.data?.files || (Array.isArray(res.data) ? res.data : []);
      setUploadedFiles(files);

      if (fileParam && files.some(f => f.id === fileParam)) {
        setSelectedFileId(fileParam);
      } else if (files.length > 0) {
        setSelectedFileId(files[0].id);
      } else {
        setSelectedFileId(null);
        setAuditData(null);
      }
    } catch (err) {
      console.error('Error loading uploaded files', err);
      setError("Couldn't load audit data. Please try again.");
      setUploadedFiles([]);
      setSelectedFileId(null);
      setAuditData(null);
    } finally {
      setLoadingFiles(false);
    }
  };

  const fetchAuditForFile = async (fileId) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/api/v1/documents/audit/${fileId}`);
      if (res.data && res.data.readiness_score !== undefined) {
        setAuditData(res.data);
      } else {
        const targetFile = uploadedFiles.find(f => f.id === fileId);
        const auditRes = await api.post('/api/v1/documents/audit', {
          file_id: fileId,
          conversation_id: sessionParam || undefined,
          filename: targetFile?.name || 'Uploaded Document'
        });
        if (auditRes.data && auditRes.data.readiness_score !== undefined) {
          setAuditData(auditRes.data);
        } else {
          setAuditData(null);
        }
      }
    } catch (err) {
      console.error('Error fetching audit for file', err);
      setAuditData(null);
      setError("Couldn't load audit data. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const fetchAuditForSession = async (convId) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/api/v1/documents/audit/${convId}`);
      if (res.data && res.data.readiness_score !== undefined) {
        setAuditData(res.data);
      } else {
        setAuditData(null);
      }
    } catch (err) {
      console.error('Error loading session audit', err);
      setAuditData(null);
      setError("Couldn't load audit data. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectFile = (fileId) => {
    setSelectedFileId(fileId);
    if (sessionParam) {
      navigate(`/dashboard?session=${sessionParam}&file=${fileId}`);
    } else {
      navigate(`/dashboard?file=${fileId}`);
    }
  };

  const handleReAudit = async () => {
    if (!selectedFileId && !sessionParam) return;
    setReAuditing(true);
    setError('');
    try {
      const targetFile = uploadedFiles.find(f => f.id === selectedFileId);
      const res = await api.post('/api/v1/documents/audit', {
        file_id: selectedFileId || undefined,
        conversation_id: sessionParam || undefined,
        filename: targetFile?.name || auditData?.filename || 'Uploaded Document'
      });
      setAuditData(res.data);
    } catch (err) {
      console.error('Failed to re-audit', err);
      setError("Couldn't load audit data. Please try again.");
    } finally {
      setReAuditing(false);
    }
  };

  if (authLoading || tenantLoading) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-cyan-400 font-medium">Loading Document Intelligence Dashboard...</div>;
  }

  if (!user || !tenant) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-slate-300">Please login to continue.</div>;
  }

  const score = auditData?.readiness_score || 0;
  const scoreColor = score >= 80 ? 'text-emerald-400 border-emerald-500/50 shadow-[0_0_25px_rgba(16,185,129,0.3)]' :
                     score >= 60 ? 'text-cyan-300 border-cyan-400/50 shadow-[0_0_25px_rgba(0,240,255,0.3)]' :
                     score >= 40 ? 'text-amber-400 border-amber-500/50 shadow-[0_0_25px_rgba(245,158,11,0.3)]' :
                     'text-rose-400 border-rose-500/50 shadow-[0_0_25px_rgba(244,63,94,0.3)]';

  const riskFactors = auditData?.risk_factors || [];
  const conflicts = auditData?.conflicts_and_ambiguities || [];
  const missingSections = auditData?.missing_sections_and_details || [];
  const rtmMatrix = auditData?.rtm_matrix || [];
  const recommendations = auditData?.ai_recommendations || [];

  const currentFile = uploadedFiles.find(f => f.id === selectedFileId);

  const renderVerificationBadge = (v, sourceRef) => {
    if (!v && !sourceRef) return null;
    const isHigh = v && v.confidence >= 60;
    return (
      <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-[10px] font-mono">
        <div className="flex items-center space-x-1.5 min-w-0">
          {v && (
            isHigh ? (
              <span className="inline-flex items-center gap-1 text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-500/40 font-bold shrink-0">
                <span>✓</span> <span>Verified ({v.confidence}%)</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-amber-400 bg-amber-950/80 px-2 py-0.5 rounded border border-amber-500/40 font-bold shrink-0" title={v.reason}>
                <span>⚠</span> <span>Unconfirmed ({v.confidence}%)</span>
              </span>
            )
          )}
          {v?.reason && (
            <span className="text-slate-400 truncate max-w-[240px]" title={v.reason}>
              {v.reason}
            </span>
          )}
        </div>
        {sourceRef && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-cyan-300 font-mono shrink-0 ml-2">
            📄 {sourceRef}
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto bg-gradient-to-br from-deep-navy via-slate-950 to-dark-navy p-8 space-y-6">
      {/* Header */}
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <span className="text-3xl">📊</span>
            <div>
              <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
                <span>Document Intelligence & Quality Audit Dashboard</span>
              </h1>
              <p className="text-xs text-slate-400 mt-1">
                Real-time, genuine AI evaluation of uploaded project specifications: risk factors, requirement conflicts, missing gaps, and RTM traceability.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate(sessionParam ? `/chat?session=${sessionParam}` : '/chat')}
            className="glass-button-secondary text-xs px-4 py-2 font-semibold flex items-center space-x-1.5"
          >
            <span>💬</span>
            <span>Back to Chat</span>
          </button>
          <button
            onClick={handleReAudit}
            disabled={!auditData || !selectedFileId || reAuditing || loading}
            className={`glass-button text-xs px-5 py-2 font-bold flex items-center space-x-2 shadow-[0_0_15px_rgba(0,240,255,0.4)] ${
              (!auditData || !selectedFileId || reAuditing || loading) ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            <span>{reAuditing ? 'Auditing with AI...' : '⚡ Re-Audit with AI'}</span>
          </button>
        </div>
      </header>

      {/* DOCUMENT SELECTOR BAR */}
      <div className="glass-card p-4 border border-cyan-500/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 bg-slate-900/90 shadow-[0_0_20px_rgba(0,240,255,0.1)]">
        <div className="flex items-center space-x-3 flex-1">
          <span className="text-lg">📁</span>
          <div>
            <label className="text-[10px] uppercase font-mono font-bold text-cyan-400 tracking-wider block">
              Active Audited Document:
            </label>
            {uploadedFiles.length > 0 ? (
              <select
                value={selectedFileId || ''}
                onChange={(e) => handleSelectFile(e.target.value)}
                className="mt-1 bg-slate-950 border border-cyan-500/40 rounded-lg px-3 py-1.5 text-xs text-slate-100 font-semibold focus:outline-none focus:border-cyan-400 cursor-pointer"
              >
                {uploadedFiles.map((file) => (
                  <option key={file.id} value={file.id}>
                    📄 {file.name} ({file.size}) — {file.has_extracted_text ? 'Ready' : 'Ingested'}
                  </option>
                ))}
              </select>
            ) : (
              <span className="text-xs text-slate-400 font-medium">
                No documents uploaded for audit
              </span>
            )}
          </div>
        </div>

        {currentFile && auditData && (
          <div className="flex items-center space-x-2 text-[11px] text-slate-400 font-mono">
            <span className="px-2 py-1 rounded bg-slate-950 border border-slate-800 text-cyan-300 font-bold">
              {currentFile.size}
            </span>
            <span className="px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-400">
              {currentFile.mime_type?.split('/')[1]?.toUpperCase() || 'DOCUMENT'}
            </span>
            {auditData?.analyzed_at && (
              <span className="text-slate-500 text-[10px]">
                Audited: {new Date(auditData.analyzed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        )}
      </div>

      {loading || loadingFiles ? (
        <div className="p-16 text-center space-y-3">
          <div className="inline-block animate-spin text-3xl">⏳</div>
          <p className="text-cyan-400 text-sm font-bold">Auditing document with REFYNE AI...</p>
          <p className="text-slate-500 text-xs">Extracting architectural risks, requirement gaps, and traceability matrix from document text.</p>
        </div>
      ) : error ? (
        <div className="glass-card p-12 text-center text-rose-300 space-y-4 border border-rose-500/30 bg-rose-500/10">
          <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-rose-500/40 flex items-center justify-center text-3xl mx-auto text-rose-400">
            ⚠️
          </div>
          <h2 className="text-lg font-bold text-slate-100">{error}</h2>
          <button
            onClick={fetchUploadedFiles}
            className="glass-button-secondary text-xs px-5 py-2 font-bold mx-auto"
          >
            Try Again
          </button>
        </div>
      ) : !auditData ? (
        <div className="glass-card p-16 text-center text-slate-400 space-y-4 my-6 border border-cyan-500/20">
          <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-cyan-500/30 flex items-center justify-center text-3xl mx-auto text-cyan-400 shadow-[0_0_20px_rgba(0,240,255,0.15)]">
            📑
          </div>
          <h2 className="text-xl font-bold text-slate-100">No document has been audited yet</h2>
          <p className="text-sm text-slate-400 max-w-md mx-auto">Upload a document to run an AI audit</p>
          <button
            onClick={() => navigate(sessionParam ? `/chat?session=${sessionParam}` : '/chat')}
            className="glass-button mx-auto font-bold text-sm shadow-[0_0_15px_rgba(0,240,255,0.3)] px-6 py-2.5"
          >
            💬 Upload Document in Chat
          </button>
        </div>
      ) : (
        <>
          {/* Primary Scorecard Metric Ribbon */}
          <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            {/* Main Readiness Meter */}
            <div className={`glass-card p-5 border rounded-2xl flex flex-col justify-between ${scoreColor}`}>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Document Readiness</span>
              <div className="flex items-baseline space-x-2 my-2">
                <span className="text-4xl font-extrabold font-mono">{score}%</span>
                <span className="text-xs font-semibold text-slate-300">
                  {score >= 80 ? 'Production Ready' : score >= 60 ? 'Good / Minor Gaps' : score >= 40 ? 'Needs Expansion' : 'Early Draft'}
                </span>
              </div>
              <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                <div
                  className="h-2 rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-500"
                  style={{ width: `${score}%` }}
                />
              </div>
            </div>

            {/* Clarity Score */}
            <div className="glass-card p-5 flex flex-col justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Clarity & Precision</span>
              <p className="text-3xl font-extrabold text-cyan-300 my-1 font-mono">{auditData?.clarity_score || 0}%</p>
              <p className="text-[11px] text-slate-400">Ambiguity & terminology check</p>
            </div>

            {/* Completeness Score */}
            <div className="glass-card p-5 flex flex-col justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Completeness</span>
              <p className="text-3xl font-extrabold text-blue-400 my-1 font-mono">{auditData?.completeness_score || 0}%</p>
              <p className="text-[11px] text-slate-400">Functional & NFR scope depth</p>
            </div>

            {/* Security & SAIF Score */}
            <div className="glass-card p-5 flex flex-col justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Security & SAIF</span>
              <p className="text-3xl font-extrabold text-purple-400 my-1 font-mono">{auditData?.security_score || 0}%</p>
              <p className="text-[11px] text-slate-400">OWASP, auth & data privacy</p>
            </div>

            {/* RTM Traceability Score */}
            <div className="glass-card p-5 flex flex-col justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">RTM Traceability</span>
              <p className="text-3xl font-extrabold text-emerald-400 my-1 font-mono">{auditData?.rtm_score || 0}%</p>
              <p className="text-[11px] text-slate-400">Test & component mapping</p>
            </div>
          </section>

          {/* §9.7 Audit Diff Banner on Re-upload / Version Comparison */}
          {auditData?.audit_diff && (
            <div className="p-3.5 px-4 rounded-xl bg-gradient-to-r from-blue-950/80 via-slate-900 to-indigo-950/80 border border-blue-500/40 flex items-center justify-between text-xs text-slate-200 shadow-lg shrink-0">
              <div className="flex items-center space-x-3">
                <span className="text-xl">🔄</span>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-blue-300">Re-Upload Audit Delta:</span>
                    <span className={`px-2 py-0.5 rounded font-mono font-bold text-xs ${
                      (auditData.audit_diff.score_delta || 0) >= 0 ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40' : 'bg-rose-950 text-rose-300 border border-rose-500/40'
                    }`}>
                      {(auditData.audit_diff.score_delta || 0) >= 0 ? `+${auditData.audit_diff.score_delta}%` : `${auditData.audit_diff.score_delta}%`} Readiness Score
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-0.5">
                    Previous Score: <span className="font-mono">{auditData.audit_diff.previous_score}%</span> → Current Score: <span className="font-mono text-cyan-300">{auditData.audit_diff.current_score}%</span>
                    {auditData.audit_diff.resolved_risks_count > 0 && (
                      <span className="text-emerald-400 font-semibold ml-2">✓ {auditData.audit_diff.resolved_risks_count} prior risk(s) resolved</span>
                    )}
                    {auditData.audit_diff.new_risks_count > 0 && (
                      <span className="text-rose-400 font-semibold ml-2">⚠️ {auditData.audit_diff.new_risks_count} new risk(s) detected</span>
                    )}
                  </p>
                </div>
              </div>
              <span className="text-[10px] uppercase font-mono px-2 py-1 rounded bg-blue-900/40 border border-blue-500/30 text-blue-300">
                Version Delta
              </span>
            </div>
          )}

          {/* Document Summary Banner - Dynamic & Scrollable */}
          {auditData?.summary && (
            <div className="p-3 px-4 rounded-xl bg-slate-900/90 border border-cyan-500/30 flex items-start space-x-3 text-xs text-slate-200 shadow-md shrink-0">
              <span className="text-lg text-cyan-400 shrink-0 mt-0.5">💡</span>
              <div className="min-w-0 flex-1">
                <strong className="text-cyan-300 font-bold block mb-1 text-xs">
                  AI Executive Summary ({auditData.filename || 'Uploaded File'}):
                </strong>
                <div className="max-h-14 overflow-y-auto text-slate-300 text-xs leading-relaxed pr-2 custom-scrollbar">
                  <p>{auditData.summary}</p>
                </div>
              </div>
            </div>
          )}

          {/* Tab Navigation Bar matching reference */}
          <div className="flex items-center space-x-2 my-2 overflow-x-auto pb-1 scrollbar-none shrink-0">
            <button
              type="button"
              onClick={() => setActiveTab('overview')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all whitespace-nowrap flex items-center space-x-1.5 shrink-0 ${
                activeTab === 'overview'
                  ? 'bg-cyan-950/80 border border-cyan-400 text-cyan-300 shadow-[0_0_12px_rgba(0,240,255,0.35)]'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <span>🔍</span>
              <span>Full Analysis Overview</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('risks')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all flex items-center space-x-1.5 whitespace-nowrap shrink-0 ${
                activeTab === 'risks'
                  ? 'bg-rose-950/80 border border-rose-400 text-rose-300 shadow-[0_0_12px_rgba(244,63,94,0.35)]'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <span>🛡️</span>
              <span>Risk Factors</span>
              <span className="px-1.5 py-0.2 rounded-full bg-rose-900 text-rose-200 text-[10px] font-mono font-bold">
                {riskFactors.length}
              </span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('conflicts')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all flex items-center space-x-1.5 whitespace-nowrap shrink-0 ${
                activeTab === 'conflicts'
                  ? 'bg-amber-950/80 border border-amber-400 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.35)]'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <span>⚡</span>
              <span>Conflicts & Ambiguities</span>
              <span className="px-1.5 py-0.2 rounded-full bg-amber-900 text-amber-200 text-[10px] font-mono font-bold">
                {conflicts.length}
              </span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('missing')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all flex items-center space-x-1.5 whitespace-nowrap shrink-0 ${
                activeTab === 'missing'
                  ? 'bg-purple-950/80 border border-purple-400 text-purple-300 shadow-[0_0_12px_rgba(168,85,247,0.35)]'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <span>🧩</span>
              <span>Missing Sections & Gaps</span>
              <span className="px-1.5 py-0.2 rounded-full bg-purple-900 text-purple-200 text-[10px] font-mono font-bold">
                {missingSections.length}
              </span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('rtm')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all flex items-center space-x-1.5 whitespace-nowrap shrink-0 ${
                activeTab === 'rtm'
                  ? 'bg-emerald-950/80 border border-emerald-400 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.35)]'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <span>📊</span>
              <span>RTM Matrix</span>
              <span className="px-1.5 py-0.2 rounded-full bg-emerald-900 text-emerald-200 text-[10px] font-mono font-bold">
                {rtmMatrix.length}
              </span>
            </button>
          </div>

          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Section 1: Identified Risks */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
                    <span className="text-blue-400">🛡️</span>
                    <span>Identified Architectural & Security Risk Factors</span>
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">{riskFactors.length} Risks Flagged</span>
                </div>
                {riskFactors.length === 0 ? (
                  <div className="p-6 rounded-xl bg-slate-900/40 border border-slate-800 text-slate-400 text-xs">
                    No critical risk factors identified for this document.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {riskFactors.map((rf, idx) => (
                      <div key={idx} className={`glass-card p-5 space-y-3 border-l-4 ${
                        rf.severity === 'CRITICAL' || rf.severity === 'HIGH' ? 'border-l-rose-500' :
                        rf.severity === 'MEDIUM' ? 'border-l-amber-500' : 'border-l-cyan-500'
                      }`}>
                        <div className="flex items-center justify-between">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase font-mono tracking-wider ${
                            rf.severity === 'CRITICAL' ? 'bg-rose-950/90 text-rose-200 border border-rose-500' :
                            rf.severity === 'HIGH' ? 'bg-rose-950/80 text-rose-300 border border-rose-700/60' :
                            rf.severity === 'MEDIUM' ? 'bg-amber-950/80 text-amber-300 border border-amber-700/60' :
                            'bg-cyan-950/80 text-cyan-300 border border-cyan-700/60'
                          }`}>
                            {rf.severity || 'HIGH'}
                          </span>
                          <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">{rf.category || 'SECURITY'}</span>
                        </div>
                        <h4 className="font-bold text-sm text-slate-100">{rf.title}</h4>
                        <p className="text-xs text-slate-300 leading-relaxed">{rf.description}</p>
                        {rf.mitigation && (
                          <div className="pt-2 border-t border-slate-800/80 text-xs">
                            <strong className="text-cyan-400 font-bold block mb-1 text-[11px]">Recommended Mitigation:</strong>
                            <p className="text-slate-300 text-xs leading-relaxed">{rf.mitigation}</p>
                          </div>
                        )}
                        {renderVerificationBadge(rf.verification, rf.source_ref)}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Section 2: Conflicts & Ambiguities */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
                    <span className="text-amber-400">⚡</span>
                    <span>Requirement Conflicts & Ambiguities</span>
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">{conflicts.length} Ambiguities Detected</span>
                </div>
                {conflicts.length === 0 ? (
                  <div className="p-6 rounded-xl bg-slate-900/40 border border-slate-800 text-slate-400 text-xs">
                    No requirement conflicts or ambiguous clauses detected.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {conflicts.map((conf, idx) => (
                      <div key={idx} className="glass-card p-5 space-y-2 border-l-4 border-l-amber-500">
                        <h4 className="font-bold text-sm text-amber-300">{conf.issue}</h4>
                        <p className="text-xs text-slate-300"><strong>Context in Text:</strong> {conf.context}</p>
                        <p className="text-xs text-cyan-300"><strong>Suggested Clarification:</strong> {conf.suggested_resolution}</p>
                        {renderVerificationBadge(conf.verification, conf.source_ref)}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Section 3: Missing Sections & Recommendations */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="glass-card p-5 space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-purple-300 flex items-center space-x-2">
                    <span>🧩 Missing Specification Sections</span>
                  </h4>
                  {missingSections.length === 0 ? (
                    <p className="text-xs text-slate-400">All standard specification sections present.</p>
                  ) : (
                    <div className="space-y-2.5">
                      {missingSections.map((ms, idx) => (
                        <div key={idx} className="p-3 rounded-lg bg-slate-900/80 border border-purple-500/20 text-xs space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-slate-100">{ms.section_name}</span>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-500/40">
                              {ms.priority || 'HIGH'}
                            </span>
                          </div>
                          <p className="text-slate-400 text-[11px]">{ms.why_missing}</p>
                          <p className="text-cyan-300 text-[11px]"><strong>Recommendation:</strong> {ms.recommended_addition}</p>
                          {renderVerificationBadge(ms.verification, ms.source_ref)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="glass-card p-5 space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-300 flex items-center space-x-2">
                    <span>💡 Actionable AI Recommendations</span>
                  </h4>
                  <div className="space-y-2">
                    {recommendations.map((rec, idx) => (
                      <div key={idx} className="p-3 rounded-lg bg-slate-900/80 border border-emerald-500/20 text-xs text-slate-200 flex items-start space-x-2">
                        <span className="text-emerald-400 font-bold">✓</span>
                        <span className="leading-relaxed">{rec}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: RISKS */}
          {activeTab === 'risks' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {riskFactors.map((rf, idx) => (
                  <div key={idx} className="glass-card p-5 space-y-3 border border-rose-500/30 bg-gradient-to-b from-rose-950/20 to-slate-900">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-700 font-mono">
                        {rf.severity || 'HIGH'} SEVERITY
                      </span>
                      <span className="text-xs font-mono text-cyan-400">{rf.category}</span>
                    </div>
                    <h4 className="font-bold text-base text-slate-100">{rf.title}</h4>
                    <p className="text-xs text-slate-300 leading-relaxed">{rf.description}</p>
                    {rf.mitigation && (
                      <div className="p-3 rounded-lg bg-slate-950 border border-cyan-500/30 text-xs text-cyan-300">
                        <strong className="block text-slate-200 mb-1">Architecture Mitigation:</strong>
                        {rf.mitigation}
                      </div>
                    )}
                    {renderVerificationBadge(rf.verification, rf.source_ref)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: CONFLICTS */}
          {activeTab === 'conflicts' && (
            <div className="space-y-4">
              {conflicts.map((conf, idx) => (
                <div key={idx} className="glass-card p-5 space-y-2 border border-amber-500/30">
                  <h4 className="font-bold text-sm text-amber-300">{conf.issue}</h4>
                  <p className="text-xs text-slate-300"><strong>Document Excerpt:</strong> {conf.context}</p>
                  <p className="text-xs text-cyan-300"><strong>Resolution Guidance:</strong> {conf.suggested_resolution}</p>
                  {renderVerificationBadge(conf.verification, conf.source_ref)}
                </div>
              ))}
            </div>
          )}

          {/* TAB 4: MISSING SECTIONS */}
          {activeTab === 'missing' && (
            <div className="space-y-4">
              {missingSections.map((ms, idx) => (
                <div key={idx} className="glass-card p-5 space-y-2 border border-purple-500/30">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-sm text-purple-300">{ms.section_name}</h4>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-950 text-purple-400 border border-purple-700">
                      {ms.priority} PRIORITY
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">{ms.why_missing}</p>
                  <p className="text-cyan-300 text-[11px]"><strong>Recommended Specification:</strong> {ms.recommended_addition}</p>
                  {renderVerificationBadge(ms.verification, ms.source_ref)}
                </div>
              ))}
            </div>
          )}

          {/* TAB 5: RTM MATRIX */}
          {activeTab === 'rtm' && (
            <div className="glass-card p-5 space-y-4 border border-cyan-500/30">
              <h4 className="text-sm font-bold text-slate-100">
                Traceability Matrix (RTM) extracted from {auditData?.filename || 'Document'}
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-700 text-slate-400 font-mono">
                      <th className="py-2.5 px-3">Req ID</th>
                      <th className="py-2.5 px-3">Business Requirement</th>
                      <th className="py-2.5 px-3">Technical Subsystem</th>
                      <th className="py-2.5 px-3">Test Case Verification</th>
                      <th className="py-2.5 px-3">Traceability Status</th>
                      <th className="py-2.5 px-3">Verification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 text-slate-200">
                    {rtmMatrix.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-900/60">
                        <td className="py-3 px-3 font-mono font-bold text-cyan-400">{item.req_id}</td>
                        <td className="py-3 px-3">{item.business_goal}</td>
                        <td className="py-3 px-3 font-mono text-slate-300">{item.technical_component}</td>
                        <td className="py-3 px-3 text-slate-400">{item.test_case_verification}</td>
                        <td className="py-3 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                            item.status === 'COVERED' ? 'badge-glow-green text-emerald-300' :
                            item.status === 'PARTIAL' ? 'badge-glow-cyan text-cyan-300' :
                            'bg-rose-950 text-rose-400 border border-rose-700'
                          }`}>
                            {item.status || 'COVERED'}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          {item.verification ? (
                            <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                              item.verification.confidence >= 60 ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40' : 'bg-amber-950 text-amber-300 border border-amber-500/40'
                            }`} title={item.verification.reason}>
                              {item.verification.confidence >= 60 ? '✓' : '⚠'} {item.verification.confidence}%
                            </span>
                          ) : (
                            <span className="text-slate-500 font-mono text-[10px]">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default Dashboard;