import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import api from '../services/api';

const DEFAULT_INTEGRATIONS = [
  {
    id: 'jira',
    name: 'Jira Software',
    icon: '🎫',
    description: 'Automated epic creation, ticket mapping, and RTM sync to Atlassian Jira',
    category: 'Issue Tracking',
    status: 'DISCONNECTED',
    fields: [
      { key: 'baseUrl', label: 'Jira Base URL', placeholder: 'https://your-domain.atlassian.net', type: 'text', required: true },
      { key: 'email', label: 'Account Email', placeholder: 'developer@company.com', type: 'email', required: true },
      { key: 'apiToken', label: 'API Token / Key', placeholder: 'ATATT3xFfGF0...', type: 'password', required: true },
      { key: 'projectKey', label: 'Target Project Key', placeholder: 'REQ or PROJ', type: 'text', required: true },
      { key: 'issueType', label: 'Default Issue Type', placeholder: 'Story or Task', type: 'text', required: false, default: 'Story' }
    ],
    config: {},
    sync_stats: { items_synced: 0, last_action: 'Never synced' },
    recent_events: []
  },
  {
    id: 'confluence',
    name: 'Confluence',
    icon: '📚',
    description: 'Publish generated BRD & SRS documents and architecture specs into team spaces',
    category: 'Documentation',
    status: 'DISCONNECTED',
    fields: [
      { key: 'baseUrl', label: 'Confluence URL', placeholder: 'https://your-domain.atlassian.net/wiki', type: 'text', required: true },
      { key: 'email', label: 'Account Email', placeholder: 'pm@company.com', type: 'email', required: true },
      { key: 'apiToken', label: 'API Token', placeholder: 'ATATT3xFfGF0...', type: 'password', required: true },
      { key: 'spaceKey', label: 'Target Space Key', placeholder: 'ENG or REQ', type: 'text', required: true },
      { key: 'parentPageId', label: 'Parent Page ID (Optional)', placeholder: '12345678', type: 'text', required: false }
    ],
    config: {},
    sync_stats: { items_synced: 0, last_action: 'Never synced' },
    recent_events: []
  },
  {
    id: 'notion',
    name: 'Notion Workspace',
    icon: '📓',
    description: 'Sync requirement databases, traceability matrices, and stakeholder feedback pages',
    category: 'Productivity',
    status: 'DISCONNECTED',
    fields: [
      { key: 'apiKey', label: 'Notion Internal Integration Secret', placeholder: 'ntn_... or secret_...', type: 'password', required: true },
      { key: 'databaseId', label: 'Requirements Database / Page ID', placeholder: '32-character database id', type: 'text', required: true }
    ],
    config: {},
    sync_stats: { items_synced: 0, last_action: 'Never synced' },
    recent_events: []
  },
  {
    id: 'slack',
    name: 'Slack Platform',
    icon: '💬',
    description: 'Workflow approval notifications, security risk alerts, and real-time document audit alerts',
    category: 'Notifications',
    status: 'DISCONNECTED',
    fields: [
      { key: 'webhookUrl', label: 'Incoming Webhook URL', placeholder: 'https://hooks.slack.com/services/T.../B.../...', type: 'password', required: true },
      { key: 'channel', label: 'Channel Name', placeholder: '#engineering-requirements', type: 'text', required: false, default: '#engineering-requirements' },
      { key: 'botName', label: 'Custom Bot Name', placeholder: 'REFYNE AI Assistant', type: 'text', required: false, default: 'REFYNE AI Assistant' }
    ],
    config: {},
    sync_stats: { items_synced: 0, last_action: 'Never synced' },
    recent_events: []
  },
  {
    id: 'github',
    name: 'GitHub Enterprise',
    icon: '💻',
    description: 'Automated requirement issue tracking, PR spec compliance auditing, and markdown export',
    category: 'Source Control',
    status: 'DISCONNECTED',
    fields: [
      { key: 'token', label: 'Personal Access Token (PAT)', placeholder: 'ghp_... or github_pat_...', type: 'password', required: true },
      { key: 'repo', label: 'Target Repository (owner/repo)', placeholder: 'my-org/core-platform', type: 'text', required: true },
      { key: 'branch', label: 'Target Branch', placeholder: 'main', type: 'text', required: false, default: 'main' }
    ],
    config: {},
    sync_stats: { items_synced: 0, last_action: 'Never synced' },
    recent_events: []
  }
];

const Integrations = () => {
  const { user } = useAuth();
  const { tenant } = useTenant();

  const [integrations, setIntegrations] = useState(DEFAULT_INTEGRATIONS);
  const [loading, setLoading] = useState(true);
  const [activeModalItem, setActiveModalItem] = useState(null);
  const [formData, setFormData] = useState({});
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [syncingId, setSyncingId] = useState(null);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    fetchIntegrations();
  }, [user, tenant]);

  const showToast = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchIntegrations = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/v1/integrations');
      if (res.data?.integrations && Array.isArray(res.data.integrations)) {
        setIntegrations(res.data.integrations);
      }
    } catch (err) {
      console.warn('Using local fallback integration states:', err);
    } finally {
      setLoading(false);
    }
  };

  const openConfigModal = (item) => {
    setActiveModalItem(item);
    setFormData(item.config || {});
    setTestResult(null);
  };

  const handleInputChange = (fieldKey, value) => {
    setFormData(prev => ({
      ...prev,
      [fieldKey]: value
    }));
  };

  const handleTestConnection = async () => {
    if (!activeModalItem) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.post(`/api/v1/integrations/${activeModalItem.id}/test`, {
        config: formData
      });
      setTestResult(res.data);
    } catch (err) {
      setTestResult({
        success: false,
        latency_ms: 0,
        message: err.response?.data?.detail || err.message || 'Connection test failed.'
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSaveConfig = async (e) => {
    e.preventDefault();
    if (!activeModalItem) return;
    setSaving(true);
    try {
      const res = await api.post(`/api/v1/integrations/${activeModalItem.id}/configure`, {
        config: formData
      });
      if (res.data?.status === 'ok') {
        showToast(`${activeModalItem.name} configured and connected successfully!`);
        await fetchIntegrations();
        setActiveModalItem(null);
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to save configuration', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDisconnect = async (item) => {
    if (!window.confirm(`Are you sure you want to disconnect ${item.name}? Saved credentials will be removed.`)) {
      return;
    }
    try {
      await api.post(`/api/v1/integrations/${item.id}/disconnect`);
      showToast(`${item.name} disconnected.`);
      await fetchIntegrations();
    } catch (err) {
      showToast('Failed to disconnect integration', 'error');
    }
  };

  const handleSyncNow = async (item) => {
    setSyncingId(item.id);
    try {
      const res = await api.post(`/api/v1/integrations/${item.id}/sync`, {
        payload: {
          items_count: 7,
          summary: 'REFYNE SRS & RTM Traceability Specification'
        }
      });
      if (res.data?.success) {
        showToast(res.data.message || `Synchronized ${item.name} successfully!`);
        await fetchIntegrations();
      }
    } catch (err) {
      showToast(`Failed to sync ${item.name}`, 'error');
    } finally {
      setSyncingId(null);
    }
  };

  const allEvents = integrations.flatMap(i => (i.recent_events || []).map(e => ({ ...e, integration: i.name, icon: i.icon })));
  const connectedCount = integrations.filter(i => i.status === 'CONNECTED').length;

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

      {/* Main Integrations Grid */}
      <main className="flex-1 p-8 overflow-y-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-100 flex items-center space-x-3">
              <span>🔌</span>
              <span>Enterprise Integration Hub</span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Connect REFYNE with Jira, Confluence, Notion, Slack, and GitHub with bidirectional sync and live telemetry.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={fetchIntegrations}
              className="glass-button-secondary text-xs px-4 py-2 flex items-center space-x-2 font-semibold"
            >
              <span>🔄</span>
              <span>Refresh Status</span>
            </button>
          </div>
        </header>

        {/* Integration Cards Grid */}
        {loading ? (
          <div className="text-center py-16 text-cyan-400 text-sm font-semibold">
            Loading active enterprise connectors...
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {integrations.map((item) => {
              const isConnected = item.status === 'CONNECTED';
              const isSyncing = syncingId === item.id;

              return (
                <div key={item.id} className="glass-card p-6 flex flex-col justify-between space-y-5 border border-cyan-500/20 hover:border-cyan-500/40 transition-all shadow-md">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="w-12 h-12 rounded-xl bg-slate-950 border border-cyan-500/30 flex items-center justify-center text-2xl shadow-inner">
                        {item.icon}
                      </div>
                      <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full uppercase font-mono tracking-wider border ${
                        isConnected
                          ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.3)]'
                          : 'bg-slate-950 text-slate-400 border-slate-700'
                      }`}>
                        {isConnected ? '● Connected' : '○ Disconnected'}
                      </span>
                    </div>

                    <div>
                      <div className="flex items-center justify-between">
                        <h3 className="text-lg font-bold text-slate-100">{item.name}</h3>
                        <span className="text-[10px] text-cyan-400/80 font-mono">{item.category}</span>
                      </div>
                      <p className="text-xs text-slate-400 leading-relaxed mt-1.5">{item.description}</p>
                    </div>

                    {/* Stats & Sync Info */}
                    {isConnected && (
                      <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] space-y-1">
                        <div className="flex justify-between text-slate-300">
                          <span>Items Synced:</span>
                          <span className="font-mono text-cyan-300 font-bold">{item.sync_stats?.items_synced || 0} items</span>
                        </div>
                        {item.last_synced_at && (
                          <div className="flex justify-between text-slate-400 text-[10px]">
                            <span>Last Synced:</span>
                            <span>{new Date(item.last_synced_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="pt-4 border-t border-slate-800/80 flex items-center space-x-2">
                    <button
                      onClick={() => openConfigModal(item)}
                      className="glass-button flex-1 text-xs py-2 font-bold"
                    >
                      {isConnected ? 'Manage Connection' : 'Connect Tool'}
                    </button>

                    {isConnected && (
                      <button
                        onClick={() => handleSyncNow(item)}
                        disabled={isSyncing}
                        className="glass-button-secondary text-xs py-2 px-3 text-cyan-300 font-bold hover:border-cyan-400/80"
                        title="Sync Requirements to this tool"
                      >
                        {isSyncing ? '⏳' : '⚡ Sync'}
                      </button>
                    )}

                    {isConnected && (
                      <button
                        onClick={() => handleDisconnect(item)}
                        className="glass-button-danger text-xs py-2 px-3"
                        title="Disconnect tool"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Right Telemetry & Status Drawer */}
      <aside className="w-80 bg-slate-950/95 border-l border-cyan-500/20 flex-shrink-0 flex flex-col h-full overflow-y-auto p-6 space-y-6 shadow-2xl">
        <div>
          <h3 className="text-xs uppercase tracking-wider text-cyan-400 font-mono font-bold">
            Integration Status & Scope
          </h3>
          <p className="text-[11px] text-slate-400 mt-1">Tenant connector health & credentials</p>
        </div>

        <div className="glass-card p-4 space-y-3 text-xs border border-cyan-500/30">
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Connected Tools:</span>
            <span className="text-emerald-400 font-bold font-mono">{connectedCount} of {integrations.length} Active</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Credential Vault:</span>
            <span className="text-cyan-300 font-semibold font-mono">AES-256 GCM</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Sync Pipeline:</span>
            <span className="text-purple-300 font-mono">Real-time Webhook</span>
          </div>
        </div>

        {/* Live Integration Event Stream */}
        <div className="flex-1 flex flex-col space-y-2">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-[11px] font-bold font-mono text-cyan-300">RECENT INTEGRATION LOGS</span>
            <span className="flex items-center space-x-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
              <span className="text-[10px] text-slate-400 font-mono">LIVE</span>
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 font-mono text-[11px] space-y-2 flex-1 max-h-80 overflow-y-auto custom-scrollbar">
            {allEvents.length === 0 ? (
              <div className="text-slate-500 text-center py-6 text-xs">
                No integration events yet. Connect Jira, Slack, or GitHub to stream live actions.
              </div>
            ) : (
              allEvents.map((evt, idx) => (
                <div key={idx} className="leading-relaxed border-b border-slate-800/60 pb-1.5">
                  <div className="flex items-center justify-between text-[10px] text-slate-400 mb-0.5">
                    <span>{evt.icon} {evt.integration}</span>
                    <span>[{evt.time}]</span>
                  </div>
                  <p className="text-slate-200 text-xs">{evt.message}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </aside>

      {/* Configuration & Connection Modal */}
      {activeModalItem && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="glass-card max-w-lg w-full p-6 space-y-5 border border-cyan-500/40 shadow-[0_0_50px_rgba(0,240,255,0.25)] animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <div className="flex items-center space-x-3">
                <span className="text-3xl">{activeModalItem.icon}</span>
                <div>
                  <h3 className="text-lg font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-blue-400">
                    Configure {activeModalItem.name}
                  </h3>
                  <p className="text-xs text-slate-400">{activeModalItem.category} Integration</p>
                </div>
              </div>
              <button
                onClick={() => setActiveModalItem(null)}
                className="text-slate-400 hover:text-rose-400 font-bold text-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveConfig} className="space-y-4">
              {activeModalItem.fields?.map((field) => (
                <div key={field.key}>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                    {field.label} {field.required && <span className="text-cyan-400">*</span>}
                  </label>
                  <input
                    type={field.type || 'text'}
                    required={field.required}
                    value={formData[field.key] || ''}
                    onChange={(e) => handleInputChange(field.key, e.target.value)}
                    placeholder={field.placeholder}
                    className="glass-input w-full py-2 px-3 text-xs"
                  />
                </div>
              ))}

              {/* Live Test Diagnostic Card */}
              {testResult && (
                <div className={`p-3 rounded-xl border text-xs leading-relaxed space-y-1 ${
                  testResult.success
                    ? 'bg-emerald-950/90 border-emerald-500/50 text-emerald-200'
                    : 'bg-rose-950/90 border-rose-500/50 text-rose-200'
                }`}>
                  <div className="flex items-center justify-between font-bold">
                    <span>{testResult.success ? '✓ Connectivity Test Passed' : '✕ Test Failed'}</span>
                    {testResult.latency_ms > 0 && <span className="font-mono text-[10px]">{testResult.latency_ms}ms</span>}
                  </div>
                  <p className="text-[11px]">{testResult.message}</p>
                </div>
              )}

              <div className="pt-4 border-t border-cyan-500/20 flex items-center justify-between">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testing}
                  className="glass-button-secondary text-xs px-4 py-2 text-cyan-300 font-bold hover:border-cyan-400"
                >
                  {testing ? '⚡ Testing...' : '⚡ Test Connection'}
                </button>

                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => setActiveModalItem(null)}
                    className="glass-button-secondary text-xs px-4 py-2"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="glass-button text-xs px-5 py-2 font-bold shadow-[0_0_15px_rgba(0,240,255,0.4)]"
                  >
                    {saving ? 'Saving...' : 'Save & Connect'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Integrations;