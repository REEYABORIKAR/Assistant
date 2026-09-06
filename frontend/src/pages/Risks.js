import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../services/api';

const Risks = () => {
  const { user, loading: authLoading } = useAuth();
  const { tenant, loading: tenantLoading } = useTenant();
  const navigate = useNavigate();
  const location = useLocation();

  const queryParams = new URLSearchParams(location.search);
  const projectId = queryParams.get('project_id') || queryParams.get('project') || localStorage.getItem('refyne_selected_project_id') || localStorage.getItem('selected_project_id');

  const [risks, setRisks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedRisk, setSelectedRisk] = useState(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [impactFilter, setImpactFilter] = useState('ALL');
  const [likelihoodFilter, setLikelihoodFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');

  // Modals
  const [isLogModalOpen, setIsLogModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGeneratingMitigation, setIsGeneratingMitigation] = useState(false);

  // AI Assessment State
  const [isAssessing, setIsAssessing] = useState(false);
  const [assessmentResult, setAssessmentResult] = useState(null);
  const [assessmentError, setAssessmentError] = useState('');

  // Form State
  const [formData, setFormData] = useState({
    title: '',
    key: '',
    project: 'AI Requirement Suite',
    category: 'TECHNICAL',
    impact: 'HIGH',
    likelihood: 'MEDIUM',
    status: 'OPEN',
    description: '',
    mitigation_strategy: '',
    contingency_plan: '',
  });

  const fetchRisks = async () => {
    if (!projectId) {
      setRisks([]);
      setSelectedRisk(null);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const params = { project_id: projectId };
      if (impactFilter !== 'ALL') params.impact = impactFilter;
      if (likelihoodFilter !== 'ALL') params.likelihood = likelihoodFilter;
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (categoryFilter !== 'ALL') params.category = categoryFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const response = await api.get('/api/v1/risks', { params });
      const list = Array.isArray(response.data) ? response.data : [];
      setRisks(list);

      if (list.length > 0) {
        if (!selectedRisk || !list.some(r => r.id === selectedRisk.id)) {
          setSelectedRisk(list[0]);
        } else {
          const updated = list.find(r => r.id === selectedRisk.id);
          if (updated) setSelectedRisk(updated);
        }
      } else {
        setSelectedRisk(null);
      }
    } catch (err) {
      console.error('Failed to fetch risks:', err);
      setError('Could not load risks from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId && user && tenant) {
      fetchRisks();
    } else {
      setRisks([]);
      setSelectedRisk(null);
    }
  }, [projectId, user, tenant, impactFilter, likelihoodFilter, statusFilter, categoryFilter, searchQuery]);

  const handleOpenLogModal = () => {
    const nextNum = risks.length + 101;
    setFormData({
      title: '',
      key: `RSK-${nextNum}`,
      project: 'Enterprise ERP Modernization',
      category: 'TECHNICAL',
      impact: 'HIGH',
      likelihood: 'MEDIUM',
      status: 'OPEN',
      description: '',
      mitigation_strategy: '',
      contingency_plan: '',
    });
    setIsLogModalOpen(true);
  };

  const handleOpenEditModal = () => {
    if (!selectedRisk) return;
    setFormData({
      title: selectedRisk.title || '',
      key: selectedRisk.risk_key || selectedRisk.key || '',
      project: selectedRisk.project || selectedRisk.owner || 'AI Requirement Suite',
      category: selectedRisk.category || 'TECHNICAL',
      impact: selectedRisk.impact || 'HIGH',
      likelihood: selectedRisk.likelihood || 'MEDIUM',
      status: selectedRisk.status || 'OPEN',
      description: selectedRisk.description || '',
      mitigation_strategy: selectedRisk.mitigation_strategy || '',
      contingency_plan: selectedRisk.contingency_plan || '',
    });
    setIsEditModalOpen(true);
  };

  const handleAutoSuggestMitigation = async () => {
    if (!formData.title.trim()) {
      alert('Please enter a risk title first.');
      return;
    }
    setIsGeneratingMitigation(true);
    try {
      const response = await api.post('/api/v1/risks/suggest-mitigation-ai', {
        title: formData.title,
        category: formData.category,
      });
      if (response.data) {
        setFormData(prev => ({
          ...prev,
          mitigation_strategy: response.data.mitigation_strategy || prev.mitigation_strategy,
          contingency_plan: response.data.contingency_plan || prev.contingency_plan,
        }));
      }
    } catch (err) {
      console.error('Failed to generate mitigation AI', err);
    } finally {
      setIsGeneratingMitigation(false);
    }
  };

  const handleCreateRisk = async (e) => {
    e.preventDefault();
    if (!formData.title.trim() || !formData.description.trim()) {
      alert('Title and description are required.');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await api.post('/api/v1/risks', {
        ...formData,
        project_id: projectId || undefined,
      });
      setIsLogModalOpen(false);
      await fetchRisks();
      if (response.data?.id) {
        setSelectedRisk(response.data);
      }
    } catch (err) {
      alert(err.response?.data?.error?.message || 'Failed to create risk.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateRisk = async (e) => {
    e.preventDefault();
    if (!selectedRisk) return;

    setIsSubmitting(true);
    try {
      const response = await api.patch(`/api/v1/risks/${selectedRisk.id}`, {
        title: formData.title,
        description: formData.description,
        category: formData.category,
        impact: formData.impact,
        likelihood: formData.likelihood,
        status: formData.status,
        mitigation_strategy: formData.mitigation_strategy,
        contingency_plan: formData.contingency_plan,
        owner: formData.project,
      });
      setIsEditModalOpen(false);
      setSelectedRisk(response.data);
      await fetchRisks();
    } catch (err) {
      alert(err.response?.data?.error?.message || 'Failed to update risk.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteRisk = async () => {
    if (!selectedRisk) return;
    if (!window.confirm(`Are you sure you want to delete ${selectedRisk.risk_key || selectedRisk.title}?`)) {
      return;
    }

    try {
      await api.delete(`/api/v1/risks/${selectedRisk.id}`);
      setSelectedRisk(null);
      setAssessmentResult(null);
      await fetchRisks();
    } catch (err) {
      alert('Failed to delete risk.');
    }
  };

  const handleAssessRiskAI = async () => {
    if (!selectedRisk) return;
    setIsAssessing(true);
    setAssessmentError('');
    setAssessmentResult(null);

    try {
      const response = await api.post(`/api/v1/risks/${selectedRisk.id}/assess-ai`);
      if (response.data?.assessment) {
        setAssessmentResult(response.data.assessment);
      }
    } catch (err) {
      console.error('Risk assessment error:', err);
      setAssessmentError('AI Risk Assessment failed. Check server logs.');
    } finally {
      setIsAssessing(false);
    }
  };

  const safeRisks = Array.isArray(risks) ? risks : [];
  const totalRisks = safeRisks.length;
  const criticalHighCount = safeRisks.filter(r => r.impact === 'CRITICAL' || r.impact === 'HIGH').length;
  const openCount = safeRisks.filter(r => r.status === 'OPEN' || r.status === 'IN_REVIEW').length;
  const mitigatedCount = safeRisks.filter(r => r.status === 'MITIGATED' || r.status === 'CLOSED').length;

  const getImpactBadge = (impact) => {
    switch (impact) {
      case 'CRITICAL': return 'bg-rose-950/90 text-rose-200 border border-rose-500 font-bold';
      case 'HIGH': return 'bg-rose-950/80 text-rose-300 border border-rose-700/60 font-bold';
      case 'MEDIUM': return 'bg-amber-950/80 text-amber-300 border border-amber-700/60 font-bold';
      default: return 'bg-slate-800 text-slate-300 border border-slate-700';
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'MITIGATED':
      case 'CLOSED': return 'badge-glow-green text-emerald-300';
      case 'IN_REVIEW': return 'badge-glow-yellow text-amber-300';
      case 'OPEN': return 'badge-glow-rose text-rose-300';
      default: return 'bg-slate-800 text-slate-300 border border-slate-700';
    }
  };

  if (authLoading || tenantLoading) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-cyan-400 font-medium">Loading risks matrix...</div>;
  }

  if (!user || !tenant) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-slate-300">Please login to continue.</div>;
  }

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-gradient-to-br from-deep-navy via-slate-950 to-dark-navy">
      {/* Main Content Area */}
      <main className="flex-1 p-8 overflow-y-auto space-y-6">
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
              <span className="text-2xl">⚠️</span>
              <span>Risk Management & Analysis</span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">Enterprise security, compliance, and operational risk assessment matrix</p>
          </div>
          <button onClick={handleOpenLogModal} disabled={!projectId} className={`glass-button font-bold text-sm ${!projectId ? 'opacity-50 cursor-not-allowed' : ''}`}>
            <span>+ Log New Risk</span>
          </button>
        </header>

        {!projectId ? (
          <div className="glass-card p-16 text-center text-slate-400 space-y-4 my-6 border border-cyan-500/20">
            <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-cyan-500/30 flex items-center justify-center text-3xl mx-auto text-cyan-400 shadow-[0_0_20px_rgba(0,240,255,0.15)]">
              📁
            </div>
            <h2 className="text-xl font-bold text-slate-100">Select a project to view risks</h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto">Choose a project workspace from the Projects page to view its architectural risk register.</p>
            <button
              onClick={() => navigate('/projects')}
              className="glass-button mx-auto font-bold text-sm shadow-[0_0_15px_rgba(0,240,255,0.3)] px-6 py-2.5"
            >
              📁 Go to Projects
            </button>
          </div>
        ) : (
          <>
            {/* Metrics Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="glass-card p-4 flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-slate-400 uppercase font-medium">Total Risks</span>
                  <p className="text-xl font-extrabold text-slate-100 mt-0.5">{totalRisks}</p>
                </div>
                <span className="text-2xl">📊</span>
              </div>
              <div className="glass-card p-4 flex items-center justify-between border-rose-500/30">
                <div>
                  <span className="text-[11px] text-rose-300 uppercase font-medium">Critical / High</span>
                  <p className="text-xl font-extrabold text-rose-400 mt-0.5">{criticalHighCount}</p>
                </div>
                <span className="text-2xl">🔥</span>
              </div>
              <div className="glass-card p-4 flex items-center justify-between border-cyan-500/30">
                <div>
                  <span className="text-[11px] text-cyan-300 uppercase font-medium">Open Risks</span>
                  <p className="text-xl font-extrabold text-cyan-400 mt-0.5">{openCount}</p>
                </div>
                <span className="text-2xl">⏳</span>
              </div>
              <div className="glass-card p-4 flex items-center justify-between border-emerald-500/30">
                <div>
                  <span className="text-[11px] text-emerald-300 uppercase font-medium">Mitigated</span>
                  <p className="text-xl font-extrabold text-emerald-400 mt-0.5">{mitigatedCount}</p>
                </div>
                <span className="text-2xl">🛡️</span>
              </div>
            </div>

            {/* Filter and Search Bar */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-900/50 p-3 rounded-xl border border-cyan-500/20">
              <div>
                <input
                  type="text"
                  placeholder="Search risks & projects..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="glass-input w-full text-xs"
                />
              </div>
              <div>
                <select
                  value={impactFilter}
                  onChange={(e) => setImpactFilter(e.target.value)}
                  className="glass-input w-full text-xs text-slate-200"
                >
                  <option value="ALL">All Impacts</option>
                  <option value="CRITICAL">Critical Impact</option>
                  <option value="HIGH">High Impact</option>
                  <option value="MEDIUM">Medium Impact</option>
                  <option value="LOW">Low Impact</option>
                </select>
              </div>
              <div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="glass-input w-full text-xs text-slate-200"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="OPEN">Open</option>
                  <option value="IN_REVIEW">In Review</option>
                  <option value="MITIGATED">Mitigated</option>
                  <option value="ACCEPTED">Accepted</option>
                  <option value="CLOSED">Closed</option>
                </select>
              </div>
              <div>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="glass-input w-full text-xs text-slate-200"
                >
                  <option value="ALL">All Categories</option>
                  <option value="SECURITY">Security</option>
                  <option value="COMPLIANCE">Compliance</option>
                  <option value="OPERATIONAL">Operational</option>
                  <option value="TECHNICAL">Technical</option>
                  <option value="DATA_GOVERNANCE">Data Governance</option>
                </select>
              </div>
            </div>

            {error && <div className="p-4 rounded-xl bg-rose-500/20 border border-rose-500/40 text-rose-300 text-sm">{error}</div>}

            {loading && <div className="text-center py-12 text-cyan-400 animate-pulse">Loading enterprise risk items...</div>}

            {!loading && risks.length === 0 && (
              <div className="text-center py-16 glass-card p-8 space-y-4">
                <div className="text-4xl">🛡️</div>
                <h3 className="text-lg font-bold text-slate-200">No risks identified yet</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">Risks will appear here after a document audit or when manually logged.</p>
                <button onClick={handleOpenLogModal} className="glass-button text-xs mx-auto">
                  <span>+ Log First Risk</span>
                </button>
              </div>
            )}

            {/* Risk Grid matching screenshot */}
            {!loading && risks.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {risks.map((risk) => {
                  const isSelected = selectedRisk?.id === risk.id;
                  return (
                    <div
                      key={risk.id}
                      onClick={() => {
                        setSelectedRisk(risk);
                        setAssessmentResult(null);
                      }}
                      className={`glass-card p-5 space-y-3 transition-all duration-200 cursor-pointer ${
                        isSelected
                          ? 'border-rose-500/80 shadow-[0_0_25px_rgba(244,63,94,0.25)] bg-slate-900/90'
                          : 'hover:border-rose-500/40 hover:bg-slate-900/50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[10px] text-rose-400 font-bold px-2 py-0.5 rounded bg-rose-950/80 border border-rose-500/30">
                          {risk.risk_key || risk.key}
                        </span>
                        <div className="flex items-center space-x-2">
                          <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded ${getImpactBadge(risk.impact)}`}>
                            {risk.impact} IMPACT
                          </span>
                          <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase ${getStatusBadge(risk.status)}`}>
                            {risk.status}
                          </span>
                        </div>
                      </div>
                      <h3 className="text-base font-bold text-slate-100 line-clamp-1">{risk.title}</h3>
                      <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">{risk.description}</p>
                      <p className="text-xs text-slate-400 mt-1">Associated Project: <span className="text-slate-300 font-medium">{risk.project}</span></p>
                      <div className="pt-2 flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80 font-mono">
                        <span>Category: <strong className="text-cyan-300">{risk.category}</strong></span>
                        <span>Likelihood: <strong className="text-amber-300">{risk.likelihood}</strong></span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>

      {/* Right Drawer: Risk Details & Groq AI Assessment */}
      {projectId && (
        <aside className="w-96 bg-slate-950/90 border-l border-cyan-500/15 flex-shrink-0 flex flex-col h-full overflow-y-auto p-6 space-y-6">
          <h3 className="text-xs uppercase tracking-wider text-rose-400 font-mono font-bold">
            Risk Analysis & Mitigation Inspector
          </h3>

          {selectedRisk ? (
            <div className="space-y-5">
              <div className="glass-card p-5 space-y-3 border-l-4 border-l-rose-500 bg-slate-900/90">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-rose-400 font-bold">{selectedRisk.risk_key || selectedRisk.key}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${getStatusBadge(selectedRisk.status)}`}>
                    {selectedRisk.status}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-slate-100">{selectedRisk.title}</h2>
                <p className="text-xs text-slate-400 mt-1">Project: <span className="text-slate-200">{selectedRisk.project}</span></p>
                <p className="text-xs text-slate-300 leading-relaxed pt-2 border-t border-slate-800">{selectedRisk.description}</p>
              </div>

              {/* Mitigation & Contingency Strategy Display */}
              <div className="glass-card p-5 space-y-3">
                <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">Mitigation & Contingency Strategy</h4>
                {selectedRisk.mitigation_strategy ? (
                  <div className="p-3 rounded bg-slate-950 border border-cyan-500/30 text-xs text-slate-200 space-y-1">
                    <strong className="text-cyan-400 block text-[11px]">Primary Mitigation:</strong>
                    <p className="leading-relaxed">{selectedRisk.mitigation_strategy}</p>
                  </div>
                ) : (
                  <div className="p-3 rounded bg-slate-950 border border-slate-800 text-xs text-slate-400">
                    No mitigation strategy specified yet. Click edit or run AI assessment to generate recommendations.
                  </div>
                )}
                {selectedRisk.contingency_plan && (
                  <div className="p-3 rounded bg-slate-950 border border-amber-500/30 text-xs text-slate-200 space-y-1">
                    <strong className="text-amber-400 block text-[11px]">Contingency Plan:</strong>
                    <p className="leading-relaxed">{selectedRisk.contingency_plan}</p>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="space-y-2">
                <button
                  onClick={handleAssessRiskAI}
                  disabled={isAssessing}
                  className="w-full glass-button text-xs py-2.5 font-bold flex items-center justify-center space-x-2 shadow-[0_0_15px_rgba(244,63,94,0.3)]"
                >
                  <span>{isAssessing ? 'Running Groq AI Assessment...' : '⚡ Run AI Risk Assessment'}</span>
                </button>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={handleOpenEditModal} className="glass-button-secondary text-xs py-2 font-semibold">
                    ✏️ Edit Risk
                  </button>
                  <button onClick={handleDeleteRisk} className="glass-button-secondary hover:border-rose-500/50 text-rose-400 text-xs py-2 font-bold">
                    🗑️ Delete Risk
                  </button>
                </div>
              </div>

              {/* Assessment Output Panel */}
              {assessmentError && (
                <div className="p-3 rounded-lg bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs">
                  {assessmentError}
                </div>
              )}

              {assessmentResult && (
                <div className="glass-card p-5 space-y-3 border-l-4 border-l-rose-500 bg-slate-900/90 animate-in fade-in">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-rose-400 flex items-center space-x-1">
                      <span>⚡</span> <span>Groq AI Risk Evaluation</span>
                    </span>
                    <span className="font-mono text-xs font-bold text-amber-300">
                      Severity: {assessmentResult.severity_rating || 'HIGH'}
                    </span>
                  </div>
                  <div className="space-y-2 text-xs text-slate-300">
                    <p><strong>Evaluation:</strong> {assessmentResult.evaluation || assessmentResult.summary}</p>
                    {assessmentResult.suggested_mitigation && (
                      <div className="p-2.5 rounded bg-slate-950 border border-cyan-500/30 text-cyan-200">
                        <strong>AI Mitigation Suggestion:</strong>
                        <p className="mt-1 text-slate-300">{assessmentResult.suggested_mitigation}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-slate-400 text-center py-8">Select a risk item to view analysis and run AI evaluation.</div>
          )}
        </aside>
      )}

      {/* Log New Risk Modal */}
      {isLogModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-lg w-full p-6 space-y-4 border border-rose-500/40 shadow-[0_0_40px_rgba(244,63,94,0.2)]">
            <h3 className="text-lg font-bold text-slate-100">Log New Architectural & Security Risk</h3>
            <form onSubmit={handleCreateRisk} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 font-mono">Risk Title</label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="glass-input w-full mt-1"
                  placeholder="e.g. Unencrypted API Credentials in Legacy Adapter"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-slate-400 font-mono">Risk Key</label>
                  <input
                    type="text"
                    value={formData.key}
                    onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                    className="glass-input w-full mt-1"
                  />
                </div>
                <div>
                  <label className="text-slate-400 font-mono">Category</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="glass-input w-full mt-1 text-slate-200"
                  >
                    <option value="SECURITY">Security</option>
                    <option value="COMPLIANCE">Compliance</option>
                    <option value="OPERATIONAL">Operational</option>
                    <option value="TECHNICAL">Technical</option>
                    <option value="DATA_GOVERNANCE">Data Governance</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-slate-400 font-mono">Impact Level</label>
                  <select
                    value={formData.impact}
                    onChange={(e) => setFormData({ ...formData, impact: e.target.value })}
                    className="glass-input w-full mt-1 text-slate-200"
                  >
                    <option value="CRITICAL">Critical Impact</option>
                    <option value="HIGH">High Impact</option>
                    <option value="MEDIUM">Medium Impact</option>
                    <option value="LOW">Low Impact</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-400 font-mono">Likelihood</label>
                  <select
                    value={formData.likelihood}
                    onChange={(e) => setFormData({ ...formData, likelihood: e.target.value })}
                    className="glass-input w-full mt-1 text-slate-200"
                  >
                    <option value="HIGH">High Likelihood</option>
                    <option value="MEDIUM">Medium Likelihood</option>
                    <option value="LOW">Low Likelihood</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-slate-400 font-mono">Associated Project / Subsystem</label>
                <input
                  type="text"
                  value={formData.project}
                  onChange={(e) => setFormData({ ...formData, project: e.target.value })}
                  className="glass-input w-full mt-1"
                />
              </div>
              <div>
                <label className="text-slate-400 font-mono">Risk Description</label>
                <textarea
                  rows={3}
                  required
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="glass-input w-full mt-1"
                  placeholder="Detailed description of risk exposure..."
                />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-slate-400 font-mono">Mitigation Strategy</label>
                  <button
                    type="button"
                    onClick={handleAutoSuggestMitigation}
                    disabled={isGeneratingMitigation}
                    className="text-[10px] text-cyan-400 hover:text-cyan-300 font-bold"
                  >
                    {isGeneratingMitigation ? 'Generating AI Suggestion...' : '⚡ Auto-Suggest with AI'}
                  </button>
                </div>
                <textarea
                  rows={2}
                  value={formData.mitigation_strategy}
                  onChange={(e) => setFormData({ ...formData, mitigation_strategy: e.target.value })}
                  className="glass-input w-full"
                  placeholder="Primary mitigation procedure..."
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button type="button" onClick={() => setIsLogModalOpen(false)} className="glass-button-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="glass-button font-bold">
                  {isSubmitting ? 'Logging...' : 'Log Risk'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Risk Modal */}
      {isEditModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-lg w-full p-6 space-y-4 border border-rose-500/40 shadow-[0_0_40px_rgba(244,63,94,0.2)]">
            <h3 className="text-lg font-bold text-slate-100">Edit Risk {formData.key}</h3>
            <form onSubmit={handleUpdateRisk} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 font-mono">Risk Title</label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="glass-input w-full mt-1"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-slate-400 font-mono">Impact</label>
                  <select
                    value={formData.impact}
                    onChange={(e) => setFormData({ ...formData, impact: e.target.value })}
                    className="glass-input w-full mt-1 text-slate-200"
                  >
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-400 font-mono">Status</label>
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                    className="glass-input w-full mt-1 text-slate-200"
                  >
                    <option value="OPEN">Open</option>
                    <option value="IN_REVIEW">In Review</option>
                    <option value="MITIGATED">Mitigated</option>
                    <option value="ACCEPTED">Accepted</option>
                    <option value="CLOSED">Closed</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-slate-400 font-mono">Description</label>
                <textarea
                  rows={3}
                  required
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="glass-input w-full mt-1"
                />
              </div>
              <div>
                <label className="text-slate-400 font-mono">Mitigation Strategy</label>
                <textarea
                  rows={2}
                  value={formData.mitigation_strategy}
                  onChange={(e) => setFormData({ ...formData, mitigation_strategy: e.target.value })}
                  className="glass-input w-full mt-1"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button type="button" onClick={() => setIsEditModalOpen(false)} className="glass-button-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="glass-button font-bold">
                  {isSubmitting ? 'Saving...' : 'Save Risk'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Risks;
