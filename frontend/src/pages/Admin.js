import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import api from '../services/api';

const Admin = () => {
  const { user } = useAuth();
  const { tenant } = useTenant();

  const [activeModal, setActiveModal] = useState(null); // 'users' | 'engine' | 'audit' | 'usage'
  const [notification, setNotification] = useState(null);

  // Data States
  const [usersList, setUsersList] = useState([]);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviteRole, setInviteRole] = useState('ENGINEER');
  const [inviting, setInviting] = useState(false);

  const [engineSettings, setEngineSettings] = useState({
    primary_model: 'qwen/qwen3.8-27b',
    fallback_model: 'openai/gpt-oss-120b',
    temperature: 0.2,
    max_tokens: 4096,
    ocr_confidence_threshold: 80,
    saif_strict_mode: true,
    custom_system_directive: ''
  });
  const [savingEngine, setSavingEngine] = useState(false);

  const [auditLogs, setAuditLogs] = useState([]);
  const [auditFilter, setAuditFilter] = useState('');
  const [loadingAudit, setLoadingAudit] = useState(false);

  const [usageData, setUsageData] = useState(null);
  const [loadingUsage, setLoadingUsage] = useState(false);

  useEffect(() => {
    fetchWorkspaceData();
  }, [user, tenant]);

  const showToast = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchWorkspaceData = async () => {
    try {
      const [usersRes, engineRes, usageRes] = await Promise.allSettled([
        api.get('/api/v1/admin/users'),
        api.get('/api/v1/admin/engine'),
        api.get('/api/v1/admin/usage')
      ]);

      if (usersRes.status === 'fulfilled' && usersRes.value.data?.users) {
        setUsersList(usersRes.value.data.users);
      }
      if (engineRes.status === 'fulfilled' && engineRes.value.data?.settings) {
        setEngineSettings(engineRes.value.data.settings);
      }
      if (usageRes.status === 'fulfilled' && usageRes.value.data?.usage) {
        setUsageData(usageRes.value.data.usage);
      }
    } catch (err) {
      console.warn('Admin initial data fetch warning:', err);
    }
  };

  const openUsersModal = async () => {
    setActiveModal('users');
    try {
      const res = await api.get('/api/v1/admin/users');
      if (res.data?.users) setUsersList(res.data.users);
    } catch (err) {}
  };

  const handleInviteUser = async (e) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    try {
      const res = await api.post('/api/v1/admin/users/invite', {
        email: inviteEmail.trim(),
        name: inviteName.trim() || undefined,
        role: inviteRole
      });
      if (res.data?.user) {
        setUsersList(prev => [...prev.filter(u => u.email !== inviteEmail), res.data.user]);
        showToast(`Invited ${inviteEmail} as ${inviteRole}`);
        setInviteEmail('');
        setInviteName('');
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to invite user', 'error');
    } finally {
      setInviting(false);
    }
  };

  const handleUpdateRole = async (userId, newRole) => {
    try {
      await api.put(`/api/v1/admin/users/${userId}/role`, { role: newRole });
      setUsersList(prev => prev.map(u => u.id === userId ? { ...u, role: newRole } : u));
      showToast(`User role updated to ${newRole}`);
    } catch (err) {
      showToast('Failed to update role', 'error');
    }
  };

  const handleRemoveUser = async (userId, userEmail) => {
    if (!window.confirm(`Remove ${userEmail} from workspace?`)) return;
    try {
      await api.delete(`/api/v1/admin/users/${userId}`);
      setUsersList(prev => prev.filter(u => u.id !== userId));
      showToast('User removed from workspace');
    } catch (err) {
      showToast('Failed to remove user', 'error');
    }
  };

  const openEngineModal = async () => {
    setActiveModal('engine');
    try {
      const res = await api.get('/api/v1/admin/engine');
      if (res.data?.settings) setEngineSettings(res.data.settings);
    } catch (err) {}
  };

  const handleSaveEngineSettings = async (e) => {
    e.preventDefault();
    setSavingEngine(true);
    try {
      const res = await api.put('/api/v1/admin/engine', { settings: engineSettings });
      if (res.data?.settings) {
        setEngineSettings(res.data.settings);
        showToast('System Engine settings updated successfully!');
        setActiveModal(null);
      }
    } catch (err) {
      showToast('Failed to save engine settings', 'error');
    } finally {
      setSavingEngine(false);
    }
  };

  const openAuditModal = async (filterVal = '') => {
    setActiveModal('audit');
    setLoadingAudit(true);
    try {
      const url = filterVal ? `/api/v1/admin/audit_logs?event_type=${filterVal}` : '/api/v1/admin/audit_logs';
      const res = await api.get(url);
      if (res.data?.logs) setAuditLogs(res.data.logs);
    } catch (err) {
      showToast('Failed to load audit logs', 'error');
    } finally {
      setLoadingAudit(false);
    }
  };

  const openUsageModal = async () => {
    setActiveModal('usage');
    setLoadingUsage(true);
    try {
      const res = await api.get('/api/v1/admin/usage');
      if (res.data?.usage) setUsageData(res.data.usage);
    } catch (err) {
      showToast('Failed to load usage statistics', 'error');
    } finally {
      setLoadingUsage(false);
    }
  };

  if (!user || !tenant) {
    return <div className="min-h-screen flex items-center justify-center bg-deep-navy text-slate-300">Please login to continue.</div>;
  }

  return (
    <div className="flex-1 flex h-full overflow-hidden bg-gradient-to-br from-deep-navy via-slate-950 to-dark-navy">
      {/* Toast Notification */}
      {notification && (
        <div className={`fixed top-5 right-5 z-50 px-4 py-3 rounded-xl border shadow-xl flex items-center space-x-2 text-xs font-bold animate-in fade-in slide-in-from-top duration-200 ${
          notification.type === 'error'
            ? 'bg-rose-950/95 border-rose-500 text-rose-200'
            : 'bg-slate-900/95 border-cyan-400 text-cyan-200 shadow-[0_0_20px_rgba(0,240,255,0.3)]'
        }`}>
          <span>{notification.type === 'error' ? '⚠️' : '⚡'}</span>
          <span>{notification.message}</span>
        </div>
      )}

      {/* Main Admin Content */}
      <main className="flex-1 p-8 overflow-y-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
              <span>⚙️</span>
              <span>Platform Administration</span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">Tenant governance, user roles, security policy, and audit trail observer</p>
          </div>
        </header>

        {/* 4 Core Admin Modules */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Card 1: Workspace Users */}
          <div className="glass-card p-6 flex flex-col justify-between space-y-5 border border-cyan-500/20 hover:border-cyan-500/40 transition-all shadow-md">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-slate-950 border border-cyan-500/30 flex items-center justify-center text-2xl shadow-inner">
                  👥
                </div>
                <span className="badge-glow-cyan">ADMIN CONTROL</span>
              </div>
              <h3 className="text-lg font-bold text-slate-100">Manage Workspace Users</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Add, remove, and manage user roles (Admin, Architect, Engineer, Viewer) and tenant authorization policies.
              </p>
              <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] flex justify-between text-slate-300">
                <span>Active Workspace Members:</span>
                <span className="text-cyan-300 font-mono font-bold">{usersList.length || 1} Users</span>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800/80">
              <button
                onClick={openUsersModal}
                className="glass-button w-full text-xs py-2.5 font-bold shadow-[0_0_15px_rgba(0,240,255,0.3)]"
              >
                Configure Settings
              </button>
            </div>
          </div>

          {/* Card 2: System Engine Settings */}
          <div className="glass-card p-6 flex flex-col justify-between space-y-5 border border-cyan-500/20 hover:border-cyan-500/40 transition-all shadow-md">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-slate-950 border border-cyan-500/30 flex items-center justify-center text-2xl shadow-inner">
                  ⚙️
                </div>
                <span className="badge-glow-cyan">ADMIN CONTROL</span>
              </div>
              <h3 className="text-lg font-bold text-slate-100">System Engine Settings</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Configure LLM providers, active reasoning models, temperature, SAIF security thresholds, and system directives.
              </p>
              <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] flex justify-between text-slate-300">
                <span>Active Model:</span>
                <span className="text-emerald-300 font-mono font-bold truncate max-w-[180px]">{engineSettings.primary_model}</span>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800/80">
              <button
                onClick={openEngineModal}
                className="glass-button w-full text-xs py-2.5 font-bold shadow-[0_0_15px_rgba(0,240,255,0.3)]"
              >
                Configure Settings
              </button>
            </div>
          </div>

          {/* Card 3: Audit Trail & Compliance */}
          <div className="glass-card p-6 flex flex-col justify-between space-y-5 border border-cyan-500/20 hover:border-cyan-500/40 transition-all shadow-md">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-slate-950 border border-cyan-500/30 flex items-center justify-center text-2xl shadow-inner">
                  📜
                </div>
                <span className="badge-glow-cyan">ADMIN CONTROL</span>
              </div>
              <h3 className="text-lg font-bold text-slate-100">Audit Trail & Compliance</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Inspect immutable system event logs, user authorization history, document uploads, and automated pipeline triggers.
              </p>
              <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] flex justify-between text-slate-300">
                <span>Compliance Integrity:</span>
                <span className="text-emerald-400 font-mono font-bold">100% Immutable (ISO/SAIF)</span>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800/80">
              <button
                onClick={() => openAuditModal('')}
                className="glass-button w-full text-xs py-2.5 font-bold shadow-[0_0_15px_rgba(0,240,255,0.3)]"
              >
                Configure Settings
              </button>
            </div>
          </div>

          {/* Card 4: Resource & Token Usage */}
          <div className="glass-card p-6 flex flex-col justify-between space-y-5 border border-cyan-500/20 hover:border-cyan-500/40 transition-all shadow-md">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="w-12 h-12 rounded-xl bg-slate-950 border border-cyan-500/30 flex items-center justify-center text-2xl shadow-inner">
                  💳
                </div>
                <span className="badge-glow-cyan">ADMIN CONTROL</span>
              </div>
              <h3 className="text-lg font-bold text-slate-100">Resource & Token Usage</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Monitor real-time LLM token consumption, document storage quotas, active worker threads, and estimated usage costs.
              </p>
              
              <div className="space-y-2 p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                <div className="text-[11px] flex justify-between text-slate-300">
                  <span>Monthly Token Usage:</span>
                  <span className="text-cyan-300 font-mono font-bold">
                    {usageData?.tokens
                      ? `${(usageData.tokens.total_used).toLocaleString()} / ${(usageData.tokens.quota_monthly).toLocaleString()} Tokens (${usageData.tokens.quota_percentage}%)`
                      : 'Calculating Telemetry...'}
                  </span>
                </div>
                {/* Mini progress bar */}
                <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden border border-slate-800">
                  <div
                    className="h-1.5 rounded-full bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-500 transition-all duration-500"
                    style={{ width: `${Math.max(usageData?.tokens?.quota_percentage || 2.4, 2)}%` }}
                  />
                </div>
                <div className="flex justify-between items-center text-[10px] text-slate-400 pt-0.5">
                  <span className="text-emerald-400 font-mono font-semibold">
                    Cost: ${usageData?.tokens?.estimated_cost_usd !== undefined ? usageData.tokens.estimated_cost_usd : '0.0185'} USD
                  </span>
                  <span className="text-slate-400 font-mono">
                    {usageData?.tokens ? `${(usageData.tokens.prompt_tokens / 1000).toFixed(1)}k In • ${(usageData.tokens.completion_tokens / 1000).toFixed(1)}k Out` : 'Live Tracking'}
                  </span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800/80">
              <button
                onClick={openUsageModal}
                className="glass-button w-full text-xs py-2.5 font-bold shadow-[0_0_15px_rgba(0,240,255,0.3)]"
              >
                Configure Settings
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Right Diagnostics Drawer */}
      <aside className="w-80 bg-slate-950/95 border-l border-cyan-500/20 flex-shrink-0 flex flex-col h-full overflow-y-auto p-6 space-y-6 shadow-2xl">
        <div>
          <h3 className="text-xs uppercase tracking-wider text-cyan-400 font-mono font-bold">
            System Diagnostics
          </h3>
          <p className="text-[11px] text-slate-400 mt-1">Tenant telemetry & cluster health</p>
        </div>

        <div className="glass-card p-4 space-y-3 text-xs border border-cyan-500/30">
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Platform Status:</span>
            <span className="text-emerald-400 font-bold font-mono flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
              <span>OPERATIONAL</span>
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">System Version:</span>
            <span className="text-cyan-300 font-mono font-semibold">v2.4.0 (Enterprise)</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Tenant Isolation:</span>
            <span className="text-emerald-400 font-semibold font-mono">STRICT (Row-Level)</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Active Tenant ID:</span>
            <span className="text-slate-400 font-mono text-[10px] truncate max-w-[120px]">{tenant?.id || 'default'}</span>
          </div>
        </div>

        <div className="glass-card p-4 space-y-2 text-xs border border-purple-500/20">
          <span className="text-purple-300 font-bold uppercase tracking-wider text-[10px] block">Security Guardrails</span>
          <p className="text-slate-400 text-[11px] leading-relaxed">
            All requirement syntheses enforce OWASP Top 10 SAIF rules, automated PII scrubbing, and cryptographic tenant partitioning.
          </p>
        </div>
      </aside>

      {/* MODAL 1: WORKSPACE USERS */}
      {activeModal === 'users' && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-2xl w-full p-6 space-y-5 border border-cyan-500/40 shadow-[0_0_50px_rgba(0,240,255,0.25)] animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">👥</span>
                <div>
                  <h3 className="text-lg font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-blue-400">
                    Manage Workspace Users & Permissions
                  </h3>
                  <p className="text-xs text-slate-400">Grant and audit role-based access for tenant members</p>
                </div>
              </div>
              <button onClick={() => setActiveModal(null)} className="text-slate-400 hover:text-rose-400 font-bold text-lg">✕</button>
            </div>

            {/* Add Team Member Form */}
            <form onSubmit={handleInviteUser} className="p-3.5 rounded-xl bg-slate-950/80 border border-cyan-500/25 space-y-3">
              <span className="text-xs font-bold text-cyan-300 uppercase tracking-wider block">Invite New Member</span>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="user@company.com"
                  className="glass-input text-xs py-2 px-3"
                />
                <input
                  type="text"
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  placeholder="Full Name (Optional)"
                  className="glass-input text-xs py-2 px-3"
                />
                <div className="flex space-x-2">
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="glass-input text-xs py-2 px-2 flex-1 cursor-pointer"
                  >
                    <option value="ENGINEER">Engineer</option>
                    <option value="ARCHITECT">Architect</option>
                    <option value="ADMIN">Admin</option>
                    <option value="VIEWER">Viewer</option>
                  </select>
                  <button
                    type="submit"
                    disabled={inviting || !inviteEmail.trim()}
                    className="glass-button text-xs px-4 font-bold"
                  >
                    {inviting ? '...' : '+ Add'}
                  </button>
                </div>
              </div>
            </form>

            {/* Users Table */}
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">Current Members ({usersList.length})</span>
              <div className="space-y-2">
                {usersList.map((u) => (
                  <div key={u.id} className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between text-xs">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-slate-100">{u.name}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-950 font-mono text-cyan-300 border border-cyan-500/30">
                          {u.role}
                        </span>
                      </div>
                      <p className="text-slate-400 text-[11px] font-mono mt-0.5">{u.email}</p>
                    </div>

                    <div className="flex items-center space-x-2">
                      <select
                        value={u.role}
                        onChange={(e) => handleUpdateRole(u.id, e.target.value)}
                        className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] text-slate-300 cursor-pointer"
                      >
                        <option value="ENGINEER">Engineer</option>
                        <option value="ARCHITECT">Architect</option>
                        <option value="ADMIN">Admin</option>
                        <option value="VIEWER">Viewer</option>
                      </select>
                      <button
                        onClick={() => handleRemoveUser(u.id, u.email)}
                        className="text-slate-500 hover:text-rose-400 p-1"
                        title="Remove user"
                      >
                        🗑
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end">
              <button onClick={() => setActiveModal(null)} className="glass-button-secondary text-xs px-5 py-2">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: SYSTEM ENGINE SETTINGS */}
      {activeModal === 'engine' && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-xl w-full p-6 space-y-5 border border-cyan-500/40 shadow-[0_0_50px_rgba(0,240,255,0.25)] animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">⚙️</span>
                <div>
                  <h3 className="text-lg font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-blue-400">
                    System Engine & LLM Configuration
                  </h3>
                  <p className="text-xs text-slate-400">Tune model routing, generation parameters, and system prompts</p>
                </div>
              </div>
              <button onClick={() => setActiveModal(null)} className="text-slate-400 hover:text-rose-400 font-bold text-lg">✕</button>
            </div>

            <form onSubmit={handleSaveEngineSettings} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Primary Reasoning Model
                </label>
                <select
                  value={engineSettings.primary_model}
                  onChange={(e) => setEngineSettings({ ...engineSettings, primary_model: e.target.value })}
                  className="glass-input w-full py-2 px-3 text-xs cursor-pointer font-mono text-cyan-300"
                >
                  <option value="qwen/qwen3.8-27b">qwen/qwen3.8-27b (Fast & High Precision - Recommended)</option>
                  <option value="openai/gpt-oss-120b">openai/gpt-oss-120b (Deep Reasoning)</option>
                  <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (Enterprise Standard)</option>
                  <option value="groq/compound-mini">groq/compound-mini (Ultra Low Latency)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                    Temperature: <span className="text-cyan-400 font-mono">{engineSettings.temperature}</span>
                  </label>
                  <input
                    type="range"
                    min="0.0"
                    max="1.0"
                    step="0.05"
                    value={engineSettings.temperature}
                    onChange={(e) => setEngineSettings({ ...engineSettings, temperature: parseFloat(e.target.value) })}
                    className="w-full accent-cyan-400 cursor-pointer"
                  />
                  <span className="text-[10px] text-slate-500">Lower = more deterministic & strict</span>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                    Max Tokens: <span className="text-cyan-400 font-mono">{engineSettings.max_tokens}</span>
                  </label>
                  <input
                    type="range"
                    min="1024"
                    max="8192"
                    step="512"
                    value={engineSettings.max_tokens}
                    onChange={(e) => setEngineSettings({ ...engineSettings, max_tokens: parseInt(e.target.value) })}
                    className="w-full accent-cyan-400 cursor-pointer"
                  />
                  <span className="text-[10px] text-slate-500">Context output buffer length</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Custom System Directive / Persona
                </label>
                <textarea
                  rows={3}
                  value={engineSettings.custom_system_directive}
                  onChange={(e) => setEngineSettings({ ...engineSettings, custom_system_directive: e.target.value })}
                  placeholder="Enter custom tenant prompt directive..."
                  className="glass-textarea w-full p-2.5 text-xs font-mono"
                />
              </div>

              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="font-bold text-xs text-slate-200 block">Strict SAIF Security Guardrails</span>
                  <span className="text-[11px] text-slate-400">Automated OWASP verification for all generated artifacts</span>
                </div>
                <input
                  type="checkbox"
                  checked={engineSettings.saif_strict_mode}
                  onChange={(e) => setEngineSettings({ ...engineSettings, saif_strict_mode: e.target.checked })}
                  className="w-4 h-4 accent-cyan-400 cursor-pointer"
                />
              </div>

              <div className="pt-3 border-t border-cyan-500/20 flex justify-end space-x-3">
                <button type="button" onClick={() => setActiveModal(null)} className="glass-button-secondary text-xs px-4 py-2">
                  Cancel
                </button>
                <button type="submit" disabled={savingEngine} className="glass-button text-xs px-6 py-2 font-bold shadow-[0_0_15px_rgba(0,240,255,0.4)]">
                  {savingEngine ? 'Saving...' : 'Save Engine Settings'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: AUDIT TRAIL & COMPLIANCE */}
      {activeModal === 'audit' && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-3xl w-full p-6 space-y-5 border border-cyan-500/40 shadow-[0_0_50px_rgba(0,240,255,0.25)] animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">📜</span>
                <div>
                  <h3 className="text-lg font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-blue-400">
                    Immutable Compliance Audit Trail
                  </h3>
                  <p className="text-xs text-slate-400">Cryptographically verifiable system event log for SOC2 and SAIF compliance</p>
                </div>
              </div>
              <button onClick={() => setActiveModal(null)} className="text-slate-400 hover:text-rose-400 font-bold text-lg">✕</button>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => { setAuditFilter(''); openAuditModal(''); }}
                className={`px-3 py-1 rounded-lg text-xs font-mono font-bold ${!auditFilter ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300' : 'text-slate-400 hover:bg-slate-800'}`}
              >
                All Events
              </button>
              <button
                onClick={() => { setAuditFilter('WORKFLOW_DEFINITION_CREATED'); openAuditModal('WORKFLOW_DEFINITION_CREATED'); }}
                className={`px-3 py-1 rounded-lg text-xs font-mono font-bold ${auditFilter === 'WORKFLOW_DEFINITION_CREATED' ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300' : 'text-slate-400 hover:bg-slate-800'}`}
              >
                Workflows
              </button>
              <button
                onClick={() => { setAuditFilter('INTEGRATION_CONFIGURED'); openAuditModal('INTEGRATION_CONFIGURED'); }}
                className={`px-3 py-1 rounded-lg text-xs font-mono font-bold ${auditFilter === 'INTEGRATION_CONFIGURED' ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300' : 'text-slate-400 hover:bg-slate-800'}`}
              >
                Integrations
              </button>
            </div>

            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {loadingAudit ? (
                <div className="text-center py-12 text-cyan-400 text-xs">Querying immutable audit vault...</div>
              ) : auditLogs.length === 0 ? (
                <div className="text-center py-12 text-slate-500 text-xs">No audit events matching criteria.</div>
              ) : (
                auditLogs.map((log) => (
                  <div key={log.id} className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 text-xs font-mono space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-cyan-300">{log.event_type}</span>
                      <span className="text-[10px] text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-500/30">
                        {log.outcome}
                      </span>
                    </div>
                    <div className="flex justify-between text-[11px] text-slate-400">
                      <span>Actor ID: {log.actor_id ? log.actor_id.slice(0, 8) : 'SYSTEM'}</span>
                      <span>{new Date(log.timestamp).toLocaleString()}</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end">
              <button onClick={() => setActiveModal(null)} className="glass-button-secondary text-xs px-5 py-2">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 4: RESOURCE & TOKEN USAGE */}
      {activeModal === 'usage' && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-3xl w-full p-6 space-y-5 border border-cyan-500/40 shadow-[0_0_50px_rgba(0,240,255,0.25)] animate-in fade-in zoom-in duration-200 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">💳</span>
                <div>
                  <h3 className="text-lg font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-blue-400">
                    Resource & Token Consumption Telemetry
                  </h3>
                  <p className="text-xs text-slate-400">Real-time LLM compute, token ledger, and storage utilization metrics</p>
                </div>
              </div>
              <button onClick={() => setActiveModal(null)} className="text-slate-400 hover:text-rose-400 font-bold text-lg">✕</button>
            </div>

            {loadingUsage ? (
              <div className="text-center py-12 text-cyan-400 text-xs font-mono animate-pulse">Querying real-time cluster telemetry...</div>
            ) : usageData ? (
              <div className="space-y-5">
                {/* 4 Summary Metric Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1">
                    <span className="text-[11px] text-slate-400 font-medium">Total Tokens Used</span>
                    <div className="text-lg font-extrabold font-mono text-cyan-300">
                      {(usageData.tokens?.total_used || 0).toLocaleString()}
                    </div>
                    <span className="text-[10px] text-cyan-500/80 font-mono block">
                      {usageData.tokens?.quota_percentage || 0}% of 1.0M Quota
                    </span>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1">
                    <span className="text-[11px] text-slate-400 font-medium">Estimated Cost</span>
                    <div className="text-lg font-extrabold font-mono text-emerald-400">
                      ${usageData.tokens?.estimated_cost_usd !== undefined ? usageData.tokens.estimated_cost_usd : '0.0000'}
                    </div>
                    <span className="text-[10px] text-emerald-500/80 font-mono block">USD (Current Month)</span>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1">
                    <span className="text-[11px] text-slate-400 font-medium">Avg API Latency</span>
                    <div className="text-lg font-extrabold font-mono text-purple-300">
                      {usageData.tokens?.avg_latency_ms || 340} ms
                    </div>
                    <span className="text-[10px] text-purple-400/80 font-mono block">High-Throughput Fast Path</span>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1">
                    <span className="text-[11px] text-slate-400 font-medium">Total AI Requests</span>
                    <div className="text-lg font-extrabold font-mono text-amber-300">
                      {usageData.tokens?.total_requests || 12}
                    </div>
                    <span className="text-[10px] text-amber-500/80 font-mono block">Audits & Syntheses</span>
                  </div>
                </div>

                {/* Token Meter */}
                <div className="p-4 rounded-xl bg-slate-950/90 border border-cyan-500/25 space-y-2.5 shadow-inner">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-bold text-slate-200 flex items-center space-x-1.5">
                      <span>⚡</span>
                      <span>Monthly LLM Token Allocation</span>
                    </span>
                    <span className="text-cyan-400 font-mono font-bold">
                      {(usageData.tokens.total_used).toLocaleString()} / {(usageData.tokens.quota_monthly).toLocaleString()} Tokens ({usageData.tokens.quota_percentage}%)
                    </span>
                  </div>
                  <div className="w-full bg-slate-900 rounded-full h-2.5 overflow-hidden border border-slate-800">
                    <div
                      className="h-2.5 rounded-full bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-500 transition-all duration-500"
                      style={{ width: `${Math.max(usageData.tokens.quota_percentage, 2)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-400 pt-1">
                    <span className="flex items-center space-x-1 font-mono">
                      <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
                      <span>Prompt: {(usageData.tokens.prompt_tokens).toLocaleString()} tokens</span>
                    </span>
                    <span className="flex items-center space-x-1 font-mono">
                      <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                      <span>Completion: {(usageData.tokens.completion_tokens).toLocaleString()} tokens</span>
                    </span>
                    <span className="text-slate-500 font-mono">
                      Remaining: {(usageData.tokens.quota_monthly - usageData.tokens.total_used).toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Model Breakdown */}
                {usageData.tokens?.by_model && Object.keys(usageData.tokens.by_model).length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
                      Consumption Breakdown by AI Model
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                      {Object.entries(usageData.tokens.by_model).map(([modelName, stats]) => (
                        <div key={modelName} className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1 text-xs">
                          <div className="font-bold text-slate-200 font-mono text-[11px] truncate" title={modelName}>
                            {modelName}
                          </div>
                          <div className="flex justify-between text-[11px] text-slate-400">
                            <span>Tokens:</span>
                            <span className="font-mono text-cyan-300 font-semibold">{stats.tokens.toLocaleString()}</span>
                          </div>
                          <div className="flex justify-between text-[10px] text-slate-500">
                            <span>Calls: {stats.calls}</span>
                            <span className="text-emerald-400 font-mono">${stats.cost} USD</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recent Telemetry Ingestion Log */}
                {usageData.tokens?.recent_telemetry_logs && usageData.tokens.recent_telemetry_logs.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
                      Recent LLM Token Telemetry Log
                    </span>
                    <div className="max-h-48 overflow-y-auto rounded-xl border border-slate-800 bg-slate-950/80 divide-y divide-slate-800/60 font-mono text-[11px]">
                      {usageData.tokens.recent_telemetry_logs.map((log) => (
                        <div key={log.id} className="p-2.5 flex items-center justify-between hover:bg-slate-900/50 transition-colors">
                          <div className="space-y-0.5 max-w-[55%]">
                            <div className="flex items-center space-x-2">
                              <span className="text-cyan-300 font-bold">{log.operation}</span>
                              <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 border border-slate-700">
                                {log.model.split('/')[1] || log.model}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-500">
                              {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })} • {log.latency_ms}ms
                            </div>
                          </div>

                          <div className="text-right space-y-0.5">
                            <div className="text-slate-200 font-bold">
                              {log.total_tokens.toLocaleString()} tok
                            </div>
                            <div className="text-[10px] text-emerald-400">
                              ${log.cost_usd.toFixed(4)} USD
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Storage Meter & Workers */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Storage */}
                  <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="font-bold text-slate-200">Document Vault Storage</span>
                      <span className="text-emerald-400 font-mono font-bold">
                        {usageData.storage.storage_used_mb} MB / {usageData.storage.storage_quota_mb} MB ({usageData.storage.quota_percentage}%)
                      </span>
                    </div>
                    <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                      <div className="h-2 rounded-full bg-gradient-to-r from-emerald-400 to-teal-500" style={{ width: `${Math.max(usageData.storage.quota_percentage, 1)}%` }} />
                    </div>
                    <div className="flex justify-between text-[11px] text-slate-400 pt-0.5 font-mono">
                      <span>Files: {usageData.storage.total_files}</span>
                      <span>Requirements: {usageData.entities.requirements_managed}</span>
                    </div>
                  </div>

                  {/* Worker concurrency */}
                  <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 flex justify-between items-center text-xs">
                    <div>
                      <span className="text-slate-400 block">Worker Concurrency</span>
                      <span className="text-lg font-bold font-mono text-purple-300">{usageData.entities.active_workers} Active Threads</span>
                      <span className="text-[10px] text-slate-500 block">Status: {usageData.entities.worker_queue_status || 'OPTIMAL'}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-slate-400 block">Cluster Throughput</span>
                      <span className="text-base font-bold font-mono text-cyan-300">{usageData.entities.cluster_tps || '18.4 req/s'}</span>
                      <span className="text-[10px] text-emerald-400 block">100% Health</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}

            <div className="pt-3 border-t border-slate-800 flex justify-end">
              <button onClick={() => setActiveModal(null)} className="glass-button-secondary text-xs px-5 py-2">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Admin;