import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { CircleHelp, FileText, FolderKanban, LayoutDashboard, Menu, MessageSquare, Settings, UserRound, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const nav = [
  { to: '/app/conversations', label: 'Conversations', icon: MessageSquare },
  { to: '/app/projects', label: 'Projects', icon: FolderKanban },
  { to: '/app/dashboard', label: 'Requirement Dashboard', icon: LayoutDashboard },
  { to: '/app/documents', label: 'Documents', icon: FileText },
  { to: '/app/templates', label: 'Templates', icon: FileText },
  { to: '/app/settings', label: 'Settings', icon: Settings },
  { to: '/app/profile', label: 'Profile', icon: UserRound },
  { to: '/app/help', label: 'Help & Support', icon: CircleHelp },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => { setDrawer(false); }, [location.pathname]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === 'Escape' && setDrawer(false);
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, []);

  const side = (
    <aside className={`flex h-full flex-col bg-[#10152c] text-slate-300 transition-all ${collapsed ? 'md:w-[72px] p-2' : 'md:w-64 p-3'} w-72`}>
      {/* Header: logo + toggle */}
      <div className={`mb-4 flex flex-col items-center gap-2 ${collapsed ? 'pt-2' : 'flex-row px-2 pt-2'}`}>
        <button onClick={() => navigate('/app/projects')} className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-violet-500 font-bold text-white" aria-label="Refyne home">R</button>
        {!collapsed && <span className="flex-1 font-bold text-white">Refyne</span>}
        <button
          className={`rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white transition ${collapsed ? 'mt-1' : 'ml-auto'}`}
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronsRight size={18}/> : <ChevronsLeft size={18}/>}
        </button>
      </div>

      {/* Nav links */}
      <nav className="flex-1 space-y-1">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center rounded-xl py-2.5 text-sm font-medium transition hover:bg-white/10 ${collapsed ? 'justify-center px-2' : 'gap-3 px-3'} ${isActive ? 'bg-violet-500/25 text-white' : ''}`
            }
          >
            <Icon size={18} className="shrink-0"/>
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer: user + sign out */}
      <div className="mt-auto border-t border-white/10 pt-3">
        <NavLink to="/app/profile" className={`flex items-center ${collapsed ? 'justify-center px-1' : 'gap-2 px-2'}`} title={collapsed ? (user?.full_name || user?.email || 'Profile') : undefined}>
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-violet-500 text-xs font-bold text-white">
            {user?.full_name?.slice(0, 1).toUpperCase() || user?.email?.slice(0, 1).toUpperCase()}
          </span>
          {!collapsed && <span className="min-w-0 flex-1 truncate text-sm text-white">{user?.full_name || user?.email}</span>}
        </NavLink>
        {!collapsed && (
          <button className="mt-3 w-full rounded-lg px-2 py-2 text-left text-xs hover:bg-white/10" onClick={() => { logout(); navigate('/login'); }}>Sign out</button>
        )}
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen bg-[#f5f7fb]">
      {/* Mobile header */}
      <header className="flex h-16 items-center border-b bg-white px-4 md:hidden">
        <button onClick={() => setDrawer(true)} aria-label="Open sidebar"><Menu/></button>
        <span className="ml-3 font-bold">Refyne</span>
      </header>

      {/* Desktop sidebar */}
      <div className="fixed inset-y-0 left-0 z-40 hidden md:block">{side}</div>

      {/* Mobile drawer overlay */}
      {drawer && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button aria-label="Close sidebar overlay" className="absolute inset-0 bg-slate-950/50" onClick={() => setDrawer(false)}/>
          <div className="relative h-full w-72">{side}</div>
        </div>
      )}

      {/* Main content */}
      <main className={`min-h-screen transition-all ${collapsed ? 'md:ml-[72px]' : 'md:ml-64'}`}>{children}</main>
    </div>
  );
}
