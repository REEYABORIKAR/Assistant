import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderKanban, FileText, CheckCircle2, ListFilter, ArrowRight, Clock, Plus, Activity } from 'lucide-react';
import type { DashboardStats } from '../types/models';
import { dashboardService } from '../services/dashboardService';
import { useAuth } from '../contexts/AuthContext';

export function DashboardPage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    dashboardService.stats()
      .then(res => setStats(res))
      .catch(e => setError(e instanceof Error ? e.message : 'Unable to load stats'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 font-medium text-slate-500">Loading requirement dashboard...</div>;

  return (
    <div className="p-5 sm:p-8 max-w-7xl mx-auto space-y-8">
      {/* Welcome Banner matching Screen 2 */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-700 p-6 text-white shadow-lg">
        <div>
          <h1 className="text-2xl font-bold">Welcome back, {user?.full_name || 'Reeya'}!</h1>
          <p className="mt-1 text-sm text-violet-100">Here's what's happening with your requirements engineering projects today.</p>
        </div>
        <button onClick={() => nav('/app/projects')} className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-violet-700 shadow transition hover:bg-violet-50">
          <Plus size={16} /> New Project
        </button>
      </div>

      {error && <p className="rounded-xl bg-rose-50 p-4 text-sm text-rose-600">{error}</p>}

      {/* Metrics Row matching Screen 2 */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Total Projects" value={stats?.total_projects || 0} icon={FolderKanban} color="violet" />
        <MetricCard label="Total Documents" value={stats?.total_documents || 0} icon={FileText} color="blue" />
        <MetricCard label="Requirements Extracted" value={stats?.total_requirements || 0} icon={ListFilter} color="emerald" />
        <MetricCard label="Completed Validations" value={stats?.total_validations || 0} icon={CheckCircle2} color="amber" />
      </div>

      {/* Two Column Grid: Recent Projects & Recent Activity */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Projects Card */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <FolderKanban size={18} className="text-violet-600" />
              <h2 className="font-bold text-slate-900">Recent Projects</h2>
            </div>
            <button onClick={() => nav('/app/projects')} className="text-xs font-semibold text-violet-600 hover:underline flex items-center gap-1">
              View all <ArrowRight size={12} />
            </button>
          </div>

          {stats?.recent_projects?.length ? (
            <div className="space-y-3">
              {stats.recent_projects.map(p => (
                <div
                  key={p.id}
                  onClick={() => nav(`/app/projects/${p.id}`)}
                  className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/50 p-4 transition hover:border-violet-300 hover:bg-violet-50/30 cursor-pointer"
                >
                  <div>
                    <h3 className="font-semibold text-slate-800 text-sm">{p.name}</h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {p.documents_count} Docs · {p.requirements_count} Requirements
                    </p>
                  </div>
                  <span className="text-xs text-slate-400 flex items-center gap-1">
                    <Clock size={12} /> {new Date(p.updated_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 py-6 text-center">No recent projects available</p>
          )}
        </div>

        {/* Recent Activity Card */}
        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-violet-600" />
              <h2 className="font-bold text-slate-900">Recent Activity</h2>
            </div>
          </div>

          {stats?.recent_activities?.length ? (
            <div className="space-y-3">
              {stats.recent_activities.map(act => (
                <div key={act.id} className="flex items-start gap-3 rounded-xl border border-slate-100 bg-slate-50/50 p-3 text-xs">
                  <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-violet-100 text-violet-600 font-bold">
                    {act.action === 'ARTIFACT_GENERATED' ? 'A' : act.action === 'DOCUMENT_UPLOADED' ? 'D' : 'V'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-800 truncate">{act.description}</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">{new Date(act.timestamp).toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 py-6 text-center">No recent activity logged yet</p>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, icon: Icon, color }: { label: string; value: number; icon: any; color: string }) {
  const colorMap: Record<string, string> = {
    violet: 'bg-violet-100 text-violet-600',
    blue: 'bg-blue-100 text-blue-600',
    emerald: 'bg-emerald-100 text-emerald-600',
    amber: 'bg-amber-100 text-amber-600',
  };

  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm flex items-center justify-between">
      <div>
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{label}</p>
        <p className="mt-2 text-3xl font-extrabold text-slate-900">{value}</p>
      </div>
      <div className={`grid h-12 w-12 place-items-center rounded-2xl ${colorMap[color] || 'bg-slate-100 text-slate-600'}`}>
        <Icon size={24} />
      </div>
    </div>
  );
}
