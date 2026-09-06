import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTenant } from '../contexts/TenantContext';
import api from '../services/api';

const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const activeSessionId = searchParams.get('session');
  
  const { user, logout } = useAuth();
  const { tenant } = useTenant();

  const [conversations, setConversations] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [editingConvId, setEditingConvId] = useState(null);
  const [editTitle, setEditTitle] = useState('');

  useEffect(() => {
    fetchChatHistory();
  }, [location.search]);

  // Close context menu when clicking outside
  useEffect(() => {
    const handleGlobalClick = () => setActiveMenuId(null);
    window.addEventListener('click', handleGlobalClick);
    return () => window.removeEventListener('click', handleGlobalClick);
  }, []);

  const fetchChatHistory = async () => {
    try {
      setLoadingHistory(true);
      const response = await api.get('/api/v1/conversations');
      const list = response.data?.conversations || response.data?.items || [];
      setConversations(Array.isArray(list) ? list : []);
    } catch (err) {
      console.error('Failed to load chat history', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleNewChat = async () => {
    try {
      const response = await api.post('/api/v1/conversations', { title: 'New Requirements Chat' });
      const newId = response.data?.id || Date.now();
      navigate(`/chat?session=${newId}`);
      fetchChatHistory();
    } catch (err) {
      const fallbackId = `chat-${Date.now()}`;
      navigate(`/chat?session=${fallbackId}`);
    }
  };

  const toggleMenu = (e, convId) => {
    e.stopPropagation();
    setActiveMenuId(prev => (prev === convId ? null : convId));
  };

  const handleStartRename = (e, conv) => {
    e.stopPropagation();
    setActiveMenuId(null);
    setEditingConvId(conv.id);
    setEditTitle(conv.title);
  };

  const handleSaveRename = async (e, convId) => {
    e.stopPropagation();
    if (!editTitle.trim()) {
      setEditingConvId(null);
      return;
    }
    const updatedTitle = editTitle.trim();
    setConversations(prev =>
      prev.map(c => (c.id === convId ? { ...c, title: updatedTitle } : c))
    );
    setEditingConvId(null);

    try {
      await api.patch(`/api/v1/conversations/${convId}`, { title: updatedTitle });
      fetchChatHistory();
    } catch (err) {
      console.error('Failed to rename conversation', err);
    }
  };

  const handleForkSession = async (e, convId) => {
    e.stopPropagation();
    setActiveMenuId(null);
    try {
      const response = await api.post(`/api/v1/conversations/${convId}/fork`);
      const forkedId = response.data?.id;
      if (forkedId) {
        await fetchChatHistory();
        navigate(`/chat?session=${forkedId}`);
      }
    } catch (err) {
      console.error('Failed to fork conversation', err);
    }
  };

  const handleDeleteSession = async (e, convId) => {
    e.stopPropagation();
    setActiveMenuId(null);
    try {
      await api.delete(`/api/v1/conversations/${convId}`);
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (activeSessionId === convId) {
        handleNewChat();
      }
    } catch (err) {
      console.error('Failed to delete chat session', err);
    }
  };

  const navItems = [
    { label: 'Audit Dashboard', path: '/dashboard', icon: '📊' },
    { label: 'Projects', path: '/projects', icon: '📁' },
    { label: 'Documents', path: '/documents', icon: '📄' },
    { label: 'Workflows', path: '/workflows', icon: '⚡' },
    { label: 'Requirements', path: '/requirements', icon: '📋' },
    { label: 'Risks', path: '/risks', icon: '⚠️' },
    { label: 'Reports', path: '/reports', icon: '📈', disabled: true, tooltip: 'Feature locked / coming soon' },
    { label: 'Integrations', path: '/integrations', icon: '🔌' },
    { label: 'Admin', path: '/admin', icon: '⚙️' },
  ];

  return (
    <aside className="w-64 bg-slate-950/80 backdrop-blur-xl border-r border-cyan-500/20 flex-shrink-0 flex flex-col h-screen select-none z-30 relative">
      {/* Brand Header */}
      <div className="p-5 border-b border-cyan-500/10 flex items-center justify-between">
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => navigate('/chat')}>
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(0,240,255,0.4)]">
            <span className="text-slate-950 font-black text-xl">R</span>
          </div>
          <div>
            <h1 className="font-extrabold text-lg tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 via-sky-200 to-blue-400">
              REFYNE
            </h1>
            <p className="text-[10px] text-cyan-400/70 uppercase tracking-widest font-mono">AI Requirement Suite</p>
          </div>
        </div>
      </div>

      {/* Primary Action: New Chat */}
      <div className="p-4 border-b border-cyan-500/10 space-y-3">
        <button
          onClick={handleNewChat}
          className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-slate-950 font-bold hover:shadow-[0_0_20px_rgba(0,240,255,0.4)] hover:brightness-110 active:scale-[0.98] transition-all flex items-center justify-center space-x-2"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
          </svg>
          <span>New Chat</span>
        </button>

        {/* Chat History List */}
        <div className="space-y-1">
          <div className="flex items-center justify-between px-2 text-[10px] uppercase font-mono tracking-wider text-cyan-400/70 font-semibold">
            <span>Chat History</span>
            <span className="text-[9px] text-slate-500">{conversations.length}</span>
          </div>
          
          <div className="max-h-48 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
            {conversations.length === 0 ? (
              <div className="text-[11px] text-slate-500 px-2 py-1 font-mono">No previous chats</div>
            ) : (
              conversations.map((conv) => {
                const isSelected = activeSessionId === conv.id;
                const isEditing = editingConvId === conv.id;
                const isMenuOpen = activeMenuId === conv.id;

                return (
                  <div
                    key={conv.id}
                    onClick={() => navigate(`/chat?session=${conv.id}`)}
                    className={`group relative flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                    }`}
                  >
                    {isEditing ? (
                      <div className="flex items-center space-x-1 w-full" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          autoFocus
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveRename(e, conv.id);
                            if (e.key === 'Escape') setEditingConvId(null);
                          }}
                          className="bg-slate-900 border border-cyan-400 text-cyan-200 rounded px-1.5 py-0.5 text-xs w-full focus:outline-none"
                        />
                        <button
                          type="button"
                          onClick={(e) => handleSaveRename(e, conv.id)}
                          className="text-cyan-400 font-bold px-1"
                        >
                          ✓
                        </button>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center space-x-2 truncate pr-2">
                          <span className="text-xs">💬</span>
                          <span className="truncate max-w-[130px]">{conv.title}</span>
                        </div>

                        {/* Three Dots Action Trigger */}
                        <div className="relative flex items-center">
                          <button
                            type="button"
                            onClick={(e) => toggleMenu(e, conv.id)}
                            className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-cyan-300 font-bold px-1 text-sm rounded hover:bg-slate-800/80 transition-opacity"
                            title="Chat actions"
                          >
                            ⋮
                          </button>

                          {/* Context Dropdown Menu */}
                          {isMenuOpen && (
                            <div
                              onClick={(e) => e.stopPropagation()}
                              className="absolute right-0 top-6 w-36 bg-slate-900 border border-cyan-500/40 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.8)] py-1 z-50 text-left font-normal"
                            >
                              <button
                                type="button"
                                onClick={(e) => handleStartRename(e, conv)}
                                className="w-full px-3 py-1.5 text-xs text-slate-200 hover:bg-cyan-500/20 hover:text-cyan-300 flex items-center space-x-2 transition-colors"
                              >
                                <span>✏️</span>
                                <span>Rename</span>
                              </button>
                              <button
                                type="button"
                                onClick={(e) => handleForkSession(e, conv.id)}
                                className="w-full px-3 py-1.5 text-xs text-slate-200 hover:bg-cyan-500/20 hover:text-cyan-300 flex items-center space-x-2 transition-colors"
                              >
                                <span>🔱</span>
                                <span>Fork / Duplicate</span>
                              </button>
                              <div className="border-t border-slate-800 my-0.5" />
                              <button
                                type="button"
                                onClick={(e) => handleDeleteSession(e, conv.id)}
                                className="w-full px-3 py-1.5 text-xs text-rose-400 hover:bg-rose-500/20 flex items-center space-x-2 transition-colors"
                              >
                                <span>🗑️</span>
                                <span>Delete</span>
                              </button>
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = location.pathname.startsWith(item.path);

          if (item.disabled) {
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full group relative flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 font-semibold'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'
                }`}
              >
                <span className="text-lg mr-3">{item.icon}</span>
                <span>{item.label}</span>
                <span className="ml-auto text-[9px] uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">{item.label === 'Reports' ? 'Soon' : 'Blocked'}</span>
              </button>
            );
          }

          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)] font-semibold'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'
              }`}
            >
              <span className="text-lg mr-3">{item.icon}</span>
              <span>{item.label}</span>
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_6px_#00f0ff]" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Tenant & User Footer */}
      <div className="p-4 border-t border-cyan-500/10 bg-slate-900/40">
        {tenant && (
          <div className="mb-3 px-3 py-1.5 rounded-lg bg-slate-950/70 border border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-400">Tenant:</span>
            <span className="text-cyan-300 font-semibold truncate max-w-[120px]">{tenant.name || tenant.id}</span>
          </div>
        )}

        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-cyan-500/30 flex items-center justify-center text-cyan-300 font-bold text-xs">
              {user?.name ? user.name.charAt(0).toUpperCase() : user?.email ? user.email.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="truncate">
              <div className="text-xs font-semibold text-slate-200 truncate">{user?.name || 'User'}</div>
              <div className="text-[10px] text-slate-400 truncate">{user?.email}</div>
            </div>
          </div>
          <button
            onClick={logout}
            title="Log Out"
            className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
