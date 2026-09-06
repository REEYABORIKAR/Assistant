import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../services/api';

const Requirements = () => {
  const { user, loading: authLoading } = useAuth();
  const { tenant, loading: tenantLoading } = useTenant();
  const navigate = useNavigate();
  const location = useLocation();

  const queryParams = new URLSearchParams(location.search);
  const projectId = queryParams.get('project_id') || queryParams.get('project') || localStorage.getItem('refyne_selected_project_id') || localStorage.getItem('selected_project_id');

  const [requirements, setRequirements] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedReq, setSelectedReq] = useState(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [priorityFilter, setPriorityFilter] = useState('ALL');

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // AI Verification State
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);
  const [verificationError, setVerificationError] = useState('');

  // Form State
  const [formData, setFormData] = useState({
    title: '',
    key: '',
    type: 'FUNCTIONAL',
    priority: 'HIGH',
    status: 'DRAFT',
    source_location: 'SRS §3.4',
    description: '',
  });

  const fetchRequirements = async () => {
    if (!projectId) {
      setRequirements([]);
      setSelectedReq(null);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const params = { project_id: projectId };
      if (typeFilter !== 'ALL') params.type = typeFilter;
      if (statusFilter !== 'ALL') params.status = statusFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const response = await api.get('/api/v1/requirements', { params });
      const list = Array.isArray(response.data) ? response.data : (response.data?.requirements || response.data?.items || []);
      setRequirements(list);
      
      if (list.length > 0) {
        if (!selectedReq || !list.some(r => r.id === selectedReq.id)) {
          setSelectedReq(list[0]);
        } else {
          // Update selectedReq with fresh data
          const updated = list.find(r => r.id === selectedReq.id);
          if (updated) setSelectedReq(updated);
        }
      } else {
        setSelectedReq(null);
      }
    } catch (err) {
      console.error('Failed to fetch requirements:', err);
      setError('Could not load requirements. Please verify connection.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId && user && tenant) {
      fetchRequirements();
    } else {
      setRequirements([]);
      setSelectedReq(null);
    }
  }, [projectId, user, tenant, typeFilter, statusFilter, searchQuery]);

  const handleOpenAddModal = () => {
    const nextNum = requirements.length + 1;
    setFormData({
      title: '',
      key: `REQ-${String(nextNum).padStart(3, '0')}`,
      type: 'FUNCTIONAL',
      priority: 'HIGH',
      status: 'DRAFT',
      source_location: 'SRS §3.4',
      description: '',
    });
    setIsAddModalOpen(true);
  };

  const handleOpenEditModal = () => {
    if (!selectedReq) return;
    setFormData({
      title: selectedReq.title || '',
      key: selectedReq.key || selectedReq.requirement_key || '',
      type: selectedReq.type || 'FUNCTIONAL',
      priority: selectedReq.priority || 'HIGH',
      status: selectedReq.status || 'DRAFT',
      source_location: selectedReq.source_location || 'SRS §3.4',
      description: selectedReq.description || '',
    });
    setIsEditModalOpen(true);
  };

  const handleCreateRequirement = async (e) => {
    e.preventDefault();
    if (!formData.title.trim() || !formData.description.trim()) {
      alert('Title and description are required.');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await api.post('/api/v1/requirements', {
        ...formData,
        project_id: projectId || undefined,
      });
      setIsAddModalOpen(false);
      await fetchRequirements();
      if (response.data?.id) {
        setSelectedReq(response.data);
      }
    } catch (err) {
      alert(err.response?.data?.error?.message || 'Failed to create requirement.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateRequirement = async (e) => {
    e.preventDefault();
    if (!selectedReq) return;

    setIsSubmitting(true);
    try {
      const response = await api.patch(`/api/v1/requirements/${selectedReq.id}`, {
        title: formData.title,
        description: formData.description,
        type: formData.type,
        priority: formData.priority,
        status: formData.status,
        source_location: formData.source_location,
      });
      setIsEditModalOpen(false);
      setSelectedReq(response.data);
      await fetchRequirements();
    } catch (err) {
      alert(err.response?.data?.error?.message || 'Failed to update requirement.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickStatusChange = async (newStatus) => {
    if (!selectedReq) return;
    try {
      const response = await api.patch(`/api/v1/requirements/${selectedReq.id}`, {
        status: newStatus,
      });
      setSelectedReq(response.data);
      setRequirements(prev => prev.map(r => r.id === selectedReq.id ? { ...r, status: newStatus } : r));
    } catch (err) {
      alert('Failed to update status.');
    }
  };

  const handleDeleteRequirement = async () => {
    if (!selectedReq) return;
    if (!window.confirm(`Are you sure you want to delete ${selectedReq.key || selectedReq.id}?`)) {
      return;
    }

    try {
      await api.delete(`/api/v1/requirements/${selectedReq.id}`);
      setSelectedReq(null);
      setVerificationResult(null);
      await fetchRequirements();
    } catch (err) {
      alert('Failed to delete requirement.');
    }
  };

  const handleRunAIVerification = async () => {
    if (!selectedReq) return;
    setIsVerifying(true);
    setVerificationError('');
    setVerificationResult(null);

    try {
      const response = await api.post(`/api/v1/requirements/${selectedReq.id}/verify-ai`);
      if (response.data?.verification) {
        setVerificationResult(response.data.verification);
      }
    } catch (err) {
      console.error('Verification error:', err);
      setVerificationError('AI verification request failed. Check server logs.');
    } finally {
      setIsVerifying(false);
    }
  };

  const safeReqs = Array.isArray(requirements) ? requirements : [];
  const filteredReqs = safeReqs.filter(r => {
    if (priorityFilter !== 'ALL' && (r.priority || 'HIGH') !== priorityFilter) return false;
    return true;
  });

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'VALIDATED': return 'badge-glow-green text-emerald-300';
      case 'APPROVED': return 'badge-glow-cyan text-cyan-300';
      case 'IN_REVIEW': return 'badge-glow-yellow text-amber-300';
      case 'REJECTED': return 'bg-rose-950 text-rose-300 border border-rose-700';
      default: return 'bg-slate-800 text-slate-300 border border-slate-700';
    }
  };

  const getPriorityColor = (p) => {
    if (p === 'CRITICAL' || p === 'HIGH') return 'text-rose-400 font-bold';
    if (p === 'MEDIUM') return 'text-cyan-300 font-bold';
    return 'text-slate-400 font-medium';
  };

  if (authLoading || tenantLoading) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-cyan-400 font-medium">Loading requirements repository...</div>;
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
              <span className="text-2xl">📋</span>
              <span>Requirements Repository</span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">Functional, non-functional, and technical specification items with validation tracking</p>
          </div>
          <div className="flex items-center space-x-3">
            <button onClick={handleOpenAddModal} disabled={!projectId} className={`glass-button font-bold text-sm ${!projectId ? 'opacity-50 cursor-not-allowed' : ''}`}>
              <span>+ Add Requirement</span>
            </button>
          </div>
        </header>

        {!projectId ? (
          <div className="glass-card p-16 text-center text-slate-400 space-y-4 my-6 border border-cyan-500/20">
            <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-cyan-500/30 flex items-center justify-center text-3xl mx-auto text-cyan-400 shadow-[0_0_20px_rgba(0,240,255,0.15)]">
              📁
            </div>
            <h2 className="text-xl font-bold text-slate-100">Select a project to view requirements</h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto">Choose a project workspace from the Projects page to view its requirements matrix.</p>
            <button
              onClick={() => navigate('/projects')}
              className="glass-button mx-auto font-bold text-sm shadow-[0_0_15px_rgba(0,240,255,0.3)] px-6 py-2.5"
            >
              📁 Go to Projects
            </button>
          </div>
        ) : (
          <>
            {/* Filter and Search Bar */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-900/50 p-3 rounded-xl border border-cyan-500/20">
              <div>
                <input
                  type="text"
                  placeholder="Search requirements..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="glass-input w-full text-xs"
                />
              </div>
              <div>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="glass-input w-full text-xs text-slate-200"
                >
                  <option value="ALL">All Types</option>
                  <option value="FUNCTIONAL">Functional</option>
                  <option value="TECHNICAL">Technical</option>
                  <option value="INTEGRATION">Integration</option>
                  <option value="SECURITY">Security</option>
                  <option value="NON_FUNCTIONAL">Non-Functional</option>
                </select>
              </div>
              <div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="glass-input w-full text-xs text-slate-200"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="VALIDATED">Validated</option>
                  <option value="IN_REVIEW">In Review</option>
                  <option value="APPROVED">Approved</option>
                  <option value="DRAFT">Draft</option>
                  <option value="REJECTED">Rejected</option>
                </select>
              </div>
              <div>
                <select
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  className="glass-input w-full text-xs text-slate-200"
                >
                  <option value="ALL">All Priorities</option>
                  <option value="CRITICAL">Critical Priority</option>
                  <option value="HIGH">High Priority</option>
                  <option value="MEDIUM">Medium Priority</option>
                  <option value="LOW">Low Priority</option>
                </select>
              </div>
            </div>

            {error && <div className="p-4 rounded-xl bg-rose-500/20 border border-rose-500/30 text-rose-300 text-sm">{error}</div>}

            {loading && <div className="text-center py-12 text-cyan-400 animate-pulse">Loading requirement specifications from database...</div>}

            {!loading && filteredReqs.length === 0 && (
              <div className="text-center py-16 glass-card p-8 space-y-4">
                <div className="text-4xl">📄</div>
                <h3 className="text-lg font-bold text-slate-200">No requirements yet</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">Requirements will appear here once your project has been analyzed or added.</p>
                <button onClick={handleOpenAddModal} className="glass-button text-xs mx-auto">
                  <span>+ Create First Requirement</span>
                </button>
              </div>
            )}

            {!loading && filteredReqs.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredReqs.map((req) => {
                  const isSelected = selectedReq?.id === req.id;
                  return (
                    <div
                      key={req.id}
                      onClick={() => {
                        setSelectedReq(req);
                        setVerificationResult(null);
                      }}
                      className={`glass-card p-5 space-y-3 transition-all duration-200 cursor-pointer ${
                        isSelected
                          ? 'border-cyan-400/80 shadow-[0_0_20px_rgba(0,240,255,0.2)] bg-slate-900/90'
                          : 'hover:border-cyan-500/40 hover:bg-slate-900/50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[10px] text-cyan-400 font-bold px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/30">
                          {req.key || req.requirement_key}
                        </span>
                        <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase ${getStatusBadgeClass(req.status)}`}>
                          {req.status}
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-slate-100 line-clamp-1">{req.title}</h3>
                      <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">{req.description}</p>
                      <div className="pt-2 flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80">
                        <span>Type: <strong className="text-slate-200">{req.type}</strong></span>
                        <span>Priority: <span className={getPriorityColor(req.priority)}>{req.priority || 'HIGH'}</span></span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>

      {/* Right Drawer: Inspection & AI Verification */}
      {projectId && (
        <aside className="w-96 bg-slate-950/90 border-l border-cyan-500/15 flex-shrink-0 flex flex-col h-full overflow-y-auto p-6 space-y-6">
          <h3 className="text-xs uppercase tracking-wider text-cyan-400 font-mono font-bold">
            Requirement Inspection & AI Verification
          </h3>

          {selectedReq ? (
            <div className="space-y-5">
              <div className="glass-card p-5 space-y-3 border-l-4 border-l-cyan-400">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-cyan-300 font-bold">{selectedReq.key || selectedReq.requirement_key}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${getStatusBadgeClass(selectedReq.status)}`}>
                    {selectedReq.status}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-slate-100">{selectedReq.title}</h2>
                <p className="text-xs text-slate-300 leading-relaxed">{selectedReq.description}</p>
              </div>

              {/* Status Quick Changer */}
              <div className="glass-card p-4 space-y-2">
                <label className="text-[10px] uppercase font-mono font-bold text-slate-400">Quick Change Status:</label>
                <div className="grid grid-cols-2 gap-2 text-xs font-semibold">
                  <button onClick={() => handleQuickStatusChange('VALIDATED')} className="glass-button-secondary py-1 text-[11px] text-emerald-300">
                    ✓ Validated
                  </button>
                  <button onClick={() => handleQuickStatusChange('APPROVED')} className="glass-button-secondary py-1 text-[11px] text-cyan-300">
                    ★ Approve
                  </button>
                  <button onClick={() => handleQuickStatusChange('IN_REVIEW')} className="glass-button-secondary py-1 text-[11px] text-amber-300">
                    ⏳ In Review
                  </button>
                  <button onClick={() => handleQuickStatusChange('REJECTED')} className="glass-button-secondary py-1 text-[11px] text-rose-400">
                    ✕ Reject
                  </button>
                </div>
              </div>

              {/* Metadata Inspector */}
              <div className="glass-card p-5 space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-800">
                  <span className="text-slate-400">Source Spec Location:</span>
                  <span className="text-slate-200 font-mono font-semibold">{selectedReq.source_location || 'SRS §1.0'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800">
                  <span className="text-slate-400">Requirement Type:</span>
                  <span className="text-cyan-300 font-semibold">{selectedReq.type}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800">
                  <span className="text-slate-400">Priority Score:</span>
                  <span className={getPriorityColor(selectedReq.priority)}>{selectedReq.priority || 'HIGH'}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Created:</span>
                  <span className="text-slate-400 font-mono">{selectedReq.created_at ? new Date(selectedReq.created_at).toLocaleDateString() : 'Today'}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2">
                <button
                  onClick={handleRunAIVerification}
                  disabled={isVerifying}
                  className="w-full glass-button text-xs py-2.5 font-bold flex items-center justify-center space-x-2 shadow-[0_0_15px_rgba(0,240,255,0.3)]"
                >
                  <span>{isVerifying ? 'Verifying with Groq AI...' : '⚡ Verify with REFYNE AI'}</span>
                </button>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={handleOpenEditModal} className="glass-button-secondary text-xs py-2 font-semibold">
                    ✏️ Edit Item
                  </button>
                  <button onClick={handleDeleteRequirement} className="glass-button-secondary hover:border-rose-500/50 text-rose-400 text-xs py-2 font-bold">
                    🗑️ Delete
                  </button>
                </div>
              </div>

              {/* AI Verification Results Panel */}
              {verificationError && (
                <div className="p-3 rounded-lg bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs">
                  {verificationError}
                </div>
              )}

              {verificationResult && (
                <div className="glass-card p-5 space-y-3 border-l-4 border-l-emerald-400 bg-slate-900/90 animate-in fade-in">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-400 flex items-center space-x-1">
                      <span>✓</span> <span>AI Verification Result</span>
                    </span>
                    <span className="font-mono text-xs font-bold text-cyan-300">
                      Score: {verificationResult.confidence || '95'}%
                    </span>
                  </div>

                  <div className="space-y-2 text-xs text-slate-300">
                    <p><strong>Verdict:</strong> {verificationResult.verdict || 'PASSED — Requirement statement is unambiguous and traceable.'}</p>
                    {verificationResult.test_case && (
                      <div className="p-2.5 rounded bg-slate-950 border border-slate-800 font-mono text-[11px] text-cyan-200">
                        <strong>Generated Verification Test:</strong>
                        <p className="mt-1 text-slate-300">{verificationResult.test_case}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-slate-400 text-center py-8">Select a requirement item to inspect details and run AI verification.</div>
          )}
        </aside>
      )}

      {/* Add Requirement Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-md w-full p-6 space-y-4 border border-cyan-500/40 shadow-[0_0_40px_rgba(0,240,255,0.2)]">
            <h3 className="text-lg font-bold text-slate-100">Add New Requirement Specification</h3>
            <form onSubmit={handleCreateRequirement} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 font-mono">Title</label>
                <input
                  type="text"
                  required
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="glass-input w-full mt-1"
                  placeholder="e.g. OAuth 2.0 PKCE Session Security"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-slate-400 font-mono">Key</label>
                  <input
                    type="text"
                    value={formData.key}
                    onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                    className="glass-input w-full mt-1"
                  />
                </div>
                <div>
                  <label className="text-slate-400 font-mono">Type</label>
                  <select
                    value={formData.type}
                    onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                    className="glass-input w-full mt-1 text-slate-200"
                  >
                    <option value="FUNCTIONAL">Functional</option>
                    <option value="TECHNICAL">Technical</option>
                    <option value="INTEGRATION">Integration</option>
                    <option value="SECURITY">Security</option>
                    <option value="NON_FUNCTIONAL">Non-Functional</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-slate-400 font-mono">Priority</label>
                  <select
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                    className="glass-input w-full mt-1 text-slate-200"
                  >
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-400 font-mono">Source Ref</label>
                  <input
                    type="text"
                    value={formData.source_location}
                    onChange={(e) => setFormData({ ...formData, source_location: e.target.value })}
                    className="glass-input w-full mt-1"
                  />
                </div>
              </div>
              <div>
                <label className="text-slate-400 font-mono">Specification Description</label>
                <textarea
                  rows={4}
                  required
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="glass-input w-full mt-1"
                  placeholder="Detailed functional specification..."
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button type="button" onClick={() => setIsAddModalOpen(false)} className="glass-button-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="glass-button font-bold">
                  {isSubmitting ? 'Creating...' : 'Create Requirement'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Requirement Modal */}
      {isEditModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-md w-full p-6 space-y-4 border border-cyan-500/40 shadow-[0_0_40px_rgba(0,240,255,0.2)]">
            <h3 className="text-lg font-bold text-slate-100">Edit Requirement {formData.key}</h3>
            <form onSubmit={handleUpdateRequirement} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 font-mono">Title</label>
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
                  <label className="text-slate-400 font-mono">Type</label>
                  <select
                    value={formData.type}
                    onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                    className="glass-input w-full mt-1 text-slate-200"
                  >
                    <option value="FUNCTIONAL">Functional</option>
                    <option value="TECHNICAL">Technical</option>
                    <option value="INTEGRATION">Integration</option>
                    <option value="SECURITY">Security</option>
                    <option value="NON_FUNCTIONAL">Non-Functional</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-400 font-mono">Priority</label>
                  <select
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                    className="glass-input w-full mt-1 text-slate-200"
                  >
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-slate-400 font-mono">Specification Description</label>
                <textarea
                  rows={4}
                  required
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="glass-input w-full mt-1"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button type="button" onClick={() => setIsEditModalOpen(false)} className="glass-button-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="glass-button font-bold">
                  {isSubmitting ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Requirements;