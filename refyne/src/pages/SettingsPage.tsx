import { useAuth } from '../contexts/AuthContext';
import { Bot, Bell, Laptop, UserRound } from 'lucide-react';

export function SettingsPage() {
  const { user } = useAuth();
  return <div className="max-w-4xl p-5 sm:p-8"><p className="text-sm font-semibold text-indigo-600">WORKSPACE</p><h1 className="mt-1 text-3xl font-bold">Settings</h1><p className="mt-2 text-sm text-slate-500">Manage your local workspace and future-ready preferences.</p>
    <section className="card mt-7 p-6"><div className="flex items-center gap-3"><UserRound className="text-indigo-600"/><h2 className="font-semibold">Local workspace</h2></div><div className="mt-5 grid gap-4 sm:grid-cols-2"><div><p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Workspace role</p><p className="mt-1 text-sm">{user.user_metadata.full_name}</p></div><div><p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Data location</p><p className="mt-1 text-sm">This browser</p></div></div></section>
    <section className="card mt-4 p-6"><div className="flex items-center gap-3"><Laptop className="text-indigo-600"/><div><h2 className="font-semibold">Local persistence</h2><p className="mt-1 text-sm text-slate-500">Projects and conversations are saved in this browser. Clearing browser site data removes them.</p></div></div></section>
    <section className="card mt-4 p-6"><div className="flex items-center gap-3"><Bot className="text-indigo-600"/><div><h2 className="font-semibold">AI configuration</h2><p className="mt-1 text-sm text-slate-500">Generation can be connected through VITE_API_BASE_URL. API keys are never stored in the browser.</p></div></div></section>
    <section className="card mt-4 p-6"><div className="flex items-center gap-3"><Bell className="text-indigo-600"/><div><h2 className="font-semibold">Notification preferences</h2><p className="mt-1 text-sm text-slate-500">Notification controls are reserved for a future release.</p></div></div></section>
  </div>;
}
